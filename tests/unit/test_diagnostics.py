from datetime import date, datetime, timezone
from io import BytesIO
from zipfile import ZipFile

import pytest

from oh_no_parent_control import diagnostics
from oh_no_parent_control.logs import DailyLogWriter
from common.oh_no_parent_control_ui.diagnostic_events import encode, event
from common.oh_no_parent_control_ui.diagnostic_bundle import validate_bundle
from common.oh_no_parent_control_ui.diagnostic_report import read_report


def _dependency_state_output(invocation="a" * 32, **overrides):
    from oh_no_parent_control.dependency_diagnostics import DEPENDENCIES
    blocks = []
    for unit in DEPENDENCIES:
        properties = dict(Id=unit, LoadState="loaded", ActiveState="failed",
                          Result="exit-code", ExecMainCode="1", ExecMainStatus="1",
                          Restart="on-abnormal", NRestarts="0", InvocationID=invocation)
        properties.update(overrides)
        blocks.append("\n".join(f"{key}={value}" for key, value in properties.items()))
    return "\n\n".join(blocks) + "\n"


def _backend_journal(message, invocation="a" * 32, **overrides):
    import json
    fields = {"MESSAGE": message, "_SYSTEMD_INVOCATION_ID": invocation,
              "_EXE": "/usr/sbin/fapolicyd", "__REALTIME_TIMESTAMP": "1791478326000000",
              "_HOSTNAME": "private-host", "_PID": "60579", "_UID": "123456"}
    fields.update(overrides)
    return json.dumps(fields)


def test_failed_backend_cause_survives_customer_archive_without_machine_access(
        tmp_path, monkeypatch, caplog):
    import json
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from oh_no_parent_control.execution_policy import FapolicydPolicy, ExecutionPolicyError
    from oh_no_parent_control.logs import BrokerFileHandler
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    secret = "private@example.test /home/private-child secret-token"
    caplog.set_level(logging.INFO)
    replies = iter([
        subprocess.CompletedProcess([], 0, secret, secret),
        subprocess.CompletedProcess([], 1, secret,
                                    "Open: /run/fapolicyd/fapolicyd.fifo -> No such file or directory\n"),
        subprocess.CompletedProcess([], 0, secret, secret),
        subprocess.CompletedProcess([], 1, secret,
                                    "Open: /run/fapolicyd/fapolicyd.fifo -> No such file or directory\n"),
        subprocess.CompletedProcess([], 0, _dependency_state_output(), secret),
        subprocess.CompletedProcess([], 0, "\n".join([
            _backend_journal("Updating trust database"),
            _backend_journal("Cannot delete database (1)"),
            _backend_journal("Cannot update trust database!"),
            _backend_journal(secret),
            _backend_journal("Cannot delete database (4)", invocation="b" * 32),
            _backend_journal("Cannot delete database (3)", _EXE="/private/program"),
        ]), secret),
    ])
    commands = []

    def run(command, **options):
        commands.append(command)
        assert options["stdin"] == subprocess.DEVNULL
        assert options["check"] is False
        assert options["env"]["LC_ALL"] == "C"
        assert 0 < options["timeout"] <= 15
        return next(replies)

    monkeypatch.setattr(dependency.subprocess, "run", run)
    monkeypatch.setattr(dependency, "_run_bounded", lambda command, timeout: run(
        command, stdin=subprocess.DEVNULL, check=False, env={"LC_ALL": "C"}, timeout=timeout))
    policy = FapolicydPolicy(rules_path=tmp_path / "rules" / "89-oh-no-parent-control.rules")
    with pytest.raises(ExecutionPolicyError, match="rollback could not be activated"):
        policy.reconcile({})
    dependency.collect_dependency_diagnostics()
    values = [decode(record.onpc_payload) for record in caplog.records]
    state = next(value for value in values if value["event"] == "execution-policy.backend-state")
    assert state["fields"] == {"dependency": "fapolicyd", "loaded": "loaded",
        "active": "failed", "result": "exit-code", "exit_kind": "exited",
        "exit_status": 1, "restart": "on-abnormal", "restarts": 0}
    command = next(value for value in values if value["event"] == "execution-policy.command-failure")
    assert command["fields"] == {"stage": "notify", "reason": "notification-endpoint-missing"}
    assert sum(value["event"] == "execution-policy.command-failure" for value in values) == 2
    assert any(value["event"] == "execution-policy.006" for value in values)
    assert policy._last_notified_contents is None
    markers = [value["fields"] for value in values if value["event"] == "execution-policy.backend-journal"]
    assert [value["reason"] for value in markers] == [
        "trust-update-started", "trust-delete-failed", "trust-update-failed", "trust-delete-failed"]
    assert markers[1]["diagnostic_code"] == 1
    assert markers[1]["invocation_relation"] == "current"
    assert markers[-1]["invocation_relation"] == "previous"
    assert markers[1]["occurred_at"] == "2026-10-08T16:52:06.000+00:00"
    assert len(commands) == 6
    assert commands[4][0] == "/usr/bin/systemctl"
    assert commands[5][0] == "/usr/bin/journalctl"
    assert "--boot=0" in commands[5]
    assert any(argument.startswith("--grep=") for argument in commands[5])
    writer = DailyLogWriter(tmp_path / "logs")
    handler = BrokerFileHandler(writer)
    for record in caplog.records:
        handler.emit(record)
    with ZipFile(BytesIO(validate_bundle(writer.snapshot()))) as archive:
        logs, _ = read_report(archive)
        exported_records = [record for rows in logs.values() for record in rows]
        # The writer suppresses identical events within 60 seconds, including
        # repeated reload steps. Every distinct failure and rollback survives.
        expected = [decode(payload) for payload in dict.fromkeys(encode(value) for value in values)]
        assert [(value["event"], value["fields"]) for value in exported_records] == [
            (value["event"], value["fields"]) for value in expected]
        assert writer.summary()["suppressed"] == len(values) - len(expected)
        text = "".join(archive.read(name).decode() for name in archive.namelist())
    assert "1=LMDB write transaction start" in text
    assert "original LMDB error" in text
    for forbidden in (secret, "60579", "123456", "private-host", "a" * 32, "b" * 32, "/private/program"):
        assert forbidden not in text and forbidden not in caplog.text


@pytest.mark.parametrize("fault", ["command", "timeout", "oversize", "malformed-state", "missing-invocation",
                                   "journal-command", "journal-malformed", "journal-time", "journal-full"])
def test_dependency_observation_is_bounded_and_failed_evidence_is_explicit(monkeypatch, caplog, fault):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    caplog.set_level(logging.INFO)
    calls = []

    def run(command, timeout):
        calls.append(command)
        assert 0 < timeout <= 3
        if fault == "timeout":
            raise subprocess.TimeoutExpired(["private-command"], 3, stderr="private-output")
        if len(calls) == 1:
            output = _dependency_state_output()
            if fault == "oversize":
                output = "x" * (dependency.MAX_OUTPUT + 1)
            if fault == "malformed-state":
                output += "private-output"
            if fault == "missing-invocation":
                output = _dependency_state_output(InvocationID="")
            return subprocess.CompletedProcess([], 1 if fault == "command" else 0, output, "private-output")
        output = ""
        if fault == "journal-malformed":
            output = "private-output"
        if fault == "journal-time":
            output = _backend_journal("Cannot delete database (1)", __REALTIME_TIMESTAMP="private-output")
        if fault == "journal-full":
            output = "\n".join(_backend_journal("unreviewed private text") for _ in range(200))
        return subprocess.CompletedProcess([], 1 if fault == "journal-command" else 0, output, "private-output")

    monkeypatch.setattr(dependency, "_run_bounded", run)
    dependency.collect_dependency_diagnostics()
    values = [decode(record.onpc_payload) for record in caplog.records]
    observation = values[-1]
    assert observation["event"] == "execution-policy.backend-observation"
    partial = fault not in {"timeout", "journal-command"}
    assert observation["fields"]["outcome"] == ("partial" if partial else "unavailable")
    assert observation["fields"]["count"] == 0
    if fault in {"command", "timeout", "oversize", "malformed-state"}:
        assert any(value["fields"] == {"source": "service", "outcome": "unavailable", "count": 0}
                   for value in values if value["event"] == "execution-policy.backend-observation")
    assert len(calls) <= 2
    assert "private" not in caplog.text


def test_dependency_unknown_fields_never_serialize_service_payload(monkeypatch, caplog):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    caplog.set_level(logging.INFO)
    replies = iter([_dependency_state_output(ActiveState="private-user", ExecMainStatus="1234567890",
                   NRestarts="private-id", Restart="private-setting"), ""])
    monkeypatch.setattr(dependency, "_run_bounded", lambda *_a, **_kw:
                        subprocess.CompletedProcess([], 0, next(replies), "private-output"))
    dependency.collect_dependency_diagnostics()
    state = decode(caplog.records[0].onpc_payload)["fields"]
    assert state["active"] == "unknown" and state["restart"] == "unknown"
    assert state["exit_status"] == 256 and state["restarts"] == 2147483647
    assert "private" not in caplog.text and "1234567890" not in caplog.text


@pytest.mark.parametrize("text,reason", [
    ("Open: /run/fapolicyd/fapolicyd.fifo -> Permission denied\n", "notification-permission-denied"),
    ("Open: /run/fapolicyd/fapolicyd.fifo -> No such device or address\n", "notification-reader-missing"),
    ("Open: /private/user -> No such file or directory", "other"),
    ("private text Permission denied", "other"), (None, "other"),
])
def test_backend_command_classifier_requires_exact_reviewed_marker(text, reason):
    from oh_no_parent_control.dependency_diagnostics import notification_error_reason
    assert notification_error_reason(text) == reason


def test_empty_reviewed_journal_is_complete_not_a_query_failure(monkeypatch, caplog):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode
    caplog.set_level(logging.INFO)
    replies = iter([subprocess.CompletedProcess([], 0, _dependency_state_output(), ''),
                    subprocess.CompletedProcess([], 1, '', '')])
    monkeypatch.setattr(dependency, '_run_bounded', lambda *_a, **_kw: next(replies))
    dependency.collect_dependency_diagnostics()
    assert decode(caplog.records[-1].onpc_payload)['fields'] == {
        'source': 'journal', 'outcome': 'complete', 'count': 0}


@pytest.mark.parametrize("service", ["failed-query", "missing-invocation", "recovered"])
@pytest.mark.parametrize("executable", ["/usr/sbin/fapolicyd", "/usr/bin/fapolicyd"])
def test_dependency_history_survives_unavailable_state_and_recovery(monkeypatch, caplog, service, executable):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    caplog.set_level(logging.INFO)
    replies = iter([
        subprocess.CompletedProcess([], 1 if service == "failed-query" else 0,
            _dependency_state_output(invocation="" if service == "missing-invocation" else "b" * 32,
                                     ActiveState="active", Result="success", ExecMainStatus="0"), ""),
        subprocess.CompletedProcess([], 0, _backend_journal("Cannot delete database (1)", _EXE=executable), ""),
    ])
    monkeypatch.setattr(dependency, "_run_bounded", lambda *_a: next(replies))
    dependency.collect_dependency_diagnostics()
    values = [decode(record.onpc_payload) for record in caplog.records]
    marker = next(value["fields"] for value in values if value["event"] == "execution-policy.backend-journal")
    assert marker["diagnostic_code"] == 1
    assert marker["invocation_relation"] == ("previous" if service == "recovered" else "other")
    assert values[-1]["fields"] == {"source": "journal", "count": 1,
                                    "outcome": "complete" if service == "recovered" else "partial"}
    for secret in ("a" * 32, "b" * 32, executable, "private-host"):
        assert secret not in caplog.text


@pytest.mark.parametrize("mode", ["success", "stdout", "stderr", "timeout", "closed-pipes"])
def test_dependency_command_caps_live_pipes_and_reaps_its_process(monkeypatch, mode):
    import subprocess
    import sys
    from oh_no_parent_control import dependency_diagnostics as dependency

    children = []
    popen = subprocess.Popen

    def spawn(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(dependency.subprocess, "Popen", spawn)
    script = {
        "success": "import os; os.write(1, b'result'); os.write(2, b'warning')",
        "stdout": "import os; os.write(1, b'x' * 524288)",
        "stderr": "import os; os.write(2, b'x' * 524288)",
        "timeout": "import time; time.sleep(30)",
        "closed-pipes": "import os, time; os.close(1); os.close(2); time.sleep(30)",
    }[mode]
    command = [sys.executable, "-I", "-c", script]
    if mode == "success":
        result = dependency._run_bounded(command, 3)
        assert (result.returncode, result.stdout, result.stderr) == (0, "result", "warning")
    else:
        with pytest.raises(ValueError if mode in {"stdout", "stderr"} else
                           (TimeoutError, subprocess.TimeoutExpired)):
            dependency._run_bounded(command, 1)
    assert len(children) == 1 and children[0].returncode is not None
    assert children[0].stdout.closed and children[0].stderr.closed


def _admission_journal(message, producer='preparation', **overrides):
    import json
    item = {'MESSAGE': message, '__REALTIME_TIMESTAMP': '1792266283591440',
            '_UID': '0', '_EXE': '/usr/bin/python3.14', '_COMM': 'oh-no-parent-co',
            '_TRANSPORT': 'stdout', 'SYSLOG_IDENTIFIER': 'systemd',
            '_SYSTEMD_UNIT': 'user@123456.service', '_BOOT_ID': 'private-previous-boot',
            '_PID': '60579', '_HOSTNAME': 'private-host'}
    if producer in ('pam', 'authentication'):
        item.update(_EXE='/usr/libexec/gdm-session-worker', _COMM='gdm-session-wor',
                    SYSLOG_IDENTIFIER='gdm-password]', _SYSTEMD_UNIT='gdm.service',
                    _TRANSPORT='syslog')
    elif producer == 'routing':
        item.update(SYSLOG_IDENTIFIER='oh-no-parent-control-login-check', _TRANSPORT='syslog')
    item.update(overrides)
    return json.dumps(item)


ADMISSION_FAILURE = ('onpc.kiosk confinement preparation outcome=denied role=manager '
                     'stage=directory-layout reason=unsafe-directory-entry '
                     'source=kiosk-confinement line=238')
ADMISSION_DIRECTORY = ('onpc.kiosk confinement directory-entry action=denied '
                       'reason=non-root-owner kind=file ownership=non-root '
                       'access=owner-change scope=required area=bin count=1')


def test_kiosk_admission_failure_survives_reboot_recovery_and_feedback_archive(
        tmp_path, monkeypatch, caplog):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from oh_no_parent_control.logs import BrokerFileHandler
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    caplog.set_level(logging.INFO)
    rows = [
        _admission_journal('pam_unix(gdm-password:auth): user [oh-no-parent-control] has blank '
                           'password; authenticated without it', 'authentication'),
        _admission_journal('onpc.pam kiosk routing stage=account outcome=allowed '
                           'session=dedicated type=wayland recovery=none reason=none', 'routing'),
        _admission_journal('pam_oh_no_parent_control(gdm-password:account): '
                           'onpc.pam kiosk confinement stage=account outcome=allowed status=0', 'pam'),
        _admission_journal(ADMISSION_DIRECTORY),
        _admission_journal(ADMISSION_FAILURE),
        _admission_journal('pam_oh_no_parent_control(systemd-user:session): '
                           'onpc.pam kiosk execution-boundary outcome=denied stage=prepare', 'pam',
                           _EXE='/usr/lib/systemd/systemd-executor', _COMM='(systemd)',
                           SYSLOG_IDENTIFIER='(systemd)', _SYSTEMD_UNIT='user@123456.service'),
        _admission_journal('pam_oh_no_parent_control(gdm-password:session): '
                           'onpc.pam kiosk execution-boundary outcome=armed stage=armed', 'pam',
                           _BOOT_ID='private-current-boot', __REALTIME_TIMESTAMP='1792266293591440'),
    ]
    commands = []

    def run(command, timeout):
        commands.append(command)
        assert 0 < timeout <= 3
        return subprocess.CompletedProcess([], 0, '\n'.join(rows), '')

    monkeypatch.setattr(dependency, '_run_bounded', run)
    monkeypatch.setattr(dependency.config, 'load', lambda _path: (_ for _ in ()).throw(
        AssertionError('admission must not need kiosk configuration')))
    dependency.collect_kiosk_admission_diagnostics()
    values = [decode(record.onpc_payload) for record in caplog.records]
    markers = [row for row in values if row['event'] != 'kiosk.admission-observation']
    assert len(markers) == 7
    assert markers[0]['fields']['reason'] == 'passwordless-authenticated'
    assert markers[1]['fields']['source'] == 'routing'
    assert markers[2]['fields']['stage'] == 'account' and markers[2]['fields']['status'] == 0
    assert markers[3]['fields']['scope'] == 'required' and markers[3]['fields']['kind'] == 'file'
    failure = markers[4]['fields']
    assert failure['stage'] == 'directory-layout' and failure['reason'] == 'unsafe-directory-entry'
    assert failure['line'] == 238 and failure['occurred_at'] == '2026-10-17T19:44:43.591+00:00'
    assert markers[5]['fields']['stage'] == 'prepare' and markers[5]['fields']['outcome'] == 'denied'
    assert markers[6]['fields']['outcome'] == 'armed'
    assert values[-1]['fields'] == dict(outcome='complete', count=7, recognized_count=7,
                                        rejected_count=0, dropped_count=0)
    assert len(commands) == 1 and '_UID=0' in commands[0]
    assert '--since=-24hours' in commands[0] and '--lines=200' in commands[0]
    assert not any(part.startswith('--boot') for part in commands[0])
    writer = DailyLogWriter(tmp_path / 'logs')
    handler = BrokerFileHandler(writer)
    for record in caplog.records:
        assert not record.args and not record.exc_info
        handler.emit(record)
    with ZipFile(BytesIO(validate_bundle(writer.snapshot()))) as archive:
        logs, _ = read_report(archive)
        exported = [row for records in logs.values() for row in records
                    if row['event'].startswith('kiosk.admission-')]
        assert [row['fields'] for row in exported] == [row['fields'] for row in values]
        text = ''.join(archive.read(name).decode() for name in archive.namelist())
    assert 'passwordless-authenticated' in text and 'unsafe-directory-entry' in text
    assert 'source_line=238' in text and 'scope=required area=bin count=1' in text
    for secret in ('private-', '123456', '60579', '/usr/', 'pam_unix', 'gdm-password]'):
        assert secret not in text and secret not in caplog.text


@pytest.mark.parametrize('fault', [
    {'_UID': '123456'}, {'_UID': 0}, {'_EXE': '/home/private/python3.14'},
    {'_COMM': 'private-command'}, {'SYSLOG_IDENTIFIER': 'private-identifier'},
    {'_SYSTEMD_UNIT': 'private.service'}, {'_TRANSPORT': 'audit'},
    {'MESSAGE': ADMISSION_FAILURE + ' account=private@example.test'},
    {'MESSAGE': ADMISSION_FAILURE.replace('unsafe-directory-entry', 'private@example.test')},
    {'MESSAGE': ADMISSION_FAILURE.replace('directory-layout', 'private-stage')},
    {'MESSAGE': ADMISSION_FAILURE.replace('line=238', 'line=9999999')},
    {'MESSAGE': ADMISSION_FAILURE.replace('role=manager', 'role=gate')},
    {'__REALTIME_TIMESTAMP': 'private@example.test'},
])
def test_kiosk_admission_rejects_untrusted_provenance_unknown_fields_and_text(monkeypatch, caplog, fault):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(dependency, '_run_bounded', lambda *_args: subprocess.CompletedProcess(
        [], 0, _admission_journal(ADMISSION_FAILURE, **fault), ''))
    dependency.collect_kiosk_admission_diagnostics()
    values = [decode(record.onpc_payload) for record in caplog.records]
    assert len(values) == 1 and values[0]['event'] == 'kiosk.admission-observation'
    assert values[0]['fields'] == dict(outcome='partial', count=0, recognized_count=0,
                                      rejected_count=1, dropped_count=0)
    assert 'private' not in caplog.text and '123456' not in caplog.text


@pytest.mark.parametrize('reason,details,expected', [
    ('os-error', ' errno=13', {'errno': 13, 'status': -256}),
    ('command-failed', ' status=-9', {'errno': -1, 'status': -9}),
    ('command-timeout', '', {'errno': -1, 'status': -256}),
])
def test_kiosk_admission_keeps_only_bounded_numeric_failure_details(monkeypatch, caplog,
                                                                  reason, details, expected):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode
    caplog.set_level(logging.INFO)
    message = ('onpc.kiosk confinement preparation outcome=denied role=manager '
               f'stage=generation-create reason={reason}{details} source=kiosk-confinement line=345')
    monkeypatch.setattr(dependency, '_run_bounded', lambda *_args: subprocess.CompletedProcess(
        [], 0, _admission_journal(message), 'private@example.test'))
    dependency.collect_kiosk_admission_diagnostics()
    fields = decode(caplog.records[0].onpc_payload)['fields']
    assert fields['reason'] == reason and fields['line'] == 345
    assert {key: fields[key] for key in expected} == expected
    assert 'private' not in caplog.text


def test_kiosk_admission_accepts_gate_classifications_and_rejects_native_spoofing(monkeypatch, caplog):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode
    caplog.set_level(logging.INFO)
    passwordless = ('pam_unix(gdm-password:auth): user [oh-no-parent-control] has blank '
                    'password; authenticated without it')
    rows = [
        _admission_journal(ADMISSION_DIRECTORY.replace('action=denied', 'action=omitted')
                           .replace('scope=required', 'scope=sibling'),
                           _SYSTEMD_UNIT='session-6.scope', SYSLOG_IDENTIFIER='gdm-session-worker'),
        _admission_journal('onpc.kiosk confinement directory-view outcome=masked '
                           'reason=writable-sibling-directory count=2'),
        _admission_journal(passwordless, 'authentication', _UID='123456'),
        _admission_journal(passwordless, 'authentication', _EXE='/home/private/gdm-session-worker'),
        _admission_journal(passwordless + ' private@example.test', 'authentication'),
        _admission_journal(passwordless.replace('oh-no-parent-control', 'private-child'), 'authentication'),
        _admission_journal(ADMISSION_FAILURE.replace('unsafe-directory-entry', 'os-error errno=4096')),
        _admission_journal(ADMISSION_FAILURE.replace('unsafe-directory-entry', 'command-failed status=256')),
        _admission_journal(ADMISSION_DIRECTORY + ' entry=/home/private'),
        _admission_journal(ADMISSION_DIRECTORY.replace('kind=file', 'kind=private-kind')),
    ]
    monkeypatch.setattr(dependency, '_run_bounded', lambda *_args: subprocess.CompletedProcess(
        [], 0, '\n'.join(rows), ''))
    dependency.collect_kiosk_admission_diagnostics()
    values = [decode(record.onpc_payload) for record in caplog.records]
    assert len(values) == 3
    assert values[0]['fields']['role'] == 'gate' and values[0]['fields']['action'] == 'omitted'
    assert values[1]['fields']['outcome'] == 'masked' and values[1]['fields']['count'] == 2
    assert values[-1]['fields'] == dict(outcome='partial', count=2, recognized_count=2,
                                       rejected_count=8, dropped_count=0)
    with pytest.raises(ValueError):
        event('kiosk.admission-directory', {**values[0]['fields'], 'entry': '/home/private'})
    assert 'private' not in caplog.text


@pytest.mark.parametrize('fault', ['command', 'timeout', 'oversize', 'malformed',
                                  'full-tail', 'marker-limit', 'empty', 'budget'])
def test_kiosk_admission_collection_is_independent_bounded_and_failure_preserving(
        monkeypatch, caplog, fault):
    import logging
    import subprocess
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode
    caplog.set_level(logging.INFO)
    calls = []

    def run(command, timeout):
        calls.append(command)
        assert 0 < timeout <= 3
        if fault == 'command':
            return subprocess.CompletedProcess([], 1, '', 'private@example.test')
        if fault == 'timeout':
            raise subprocess.TimeoutExpired(['private'], 3, stderr='private@example.test')
        if fault == 'empty':
            return subprocess.CompletedProcess([], 1, '', '')
        success = _admission_journal('onpc.pam kiosk routing stage=account outcome=allowed '
                                     'session=dedicated type=wayland recovery=none reason=none', 'routing')
        output = {'oversize': 'x' * (dependency.MAX_OUTPUT + 1), 'malformed': 'private@example.test',
                  'full-tail': '\n'.join([_admission_journal(ADMISSION_FAILURE)] + [success] * 199),
                  'marker-limit': '\n'.join([_admission_journal(ADMISSION_FAILURE)] + [success] * 21),
                  }.get(fault, '')
        return subprocess.CompletedProcess([], 0, output, '')

    monkeypatch.setattr(dependency, '_run_bounded', run)
    if fault == 'budget':
        ticks = iter([0, 6])
        monkeypatch.setattr(dependency.time, 'monotonic', lambda: next(ticks))
    dependency.collect_kiosk_admission_diagnostics()
    values = [decode(record.onpc_payload) for record in caplog.records]
    observation = values[-1]['fields']
    unavailable = fault in ('command', 'timeout', 'oversize', 'budget')
    assert observation['outcome'] == ('unavailable' if unavailable else
                                       'complete' if fault == 'empty' else 'partial')
    count = 20 if fault in ('full-tail', 'marker-limit') else 0
    assert observation['count'] == count
    assert observation['recognized_count'] == (200 if fault == 'full-tail' else
                                               22 if fault == 'marker-limit' else 0)
    assert observation['dropped_count'] == (180 if fault == 'full-tail' else
                                            2 if fault == 'marker-limit' else 0)
    if count:
        assert values[0]['fields']['reason'] == 'unsafe-directory-entry'
        assert values[0]['fields']['line'] == 238
    assert len(calls) == (0 if fault == 'budget' else 1)
    assert 'private' not in caplog.text


def _kiosk_journal(message, **overrides):
    import json
    item = {"MESSAGE": message, "__REALTIME_TIMESTAMP": "1792266283591440",
            "_UID": "123456", "_PID": "60579", "_HOSTNAME": "private-host",
            "_EXE": "/usr/bin/python3.14", "_TRANSPORT": "journal",
            "_SYSTEMD_USER_UNIT": "oh-no-parent-control-app.service"}
    item.update(overrides)
    return json.dumps(item)


KIOSK_GPU_DENIAL = (
    'AVC avc:  denied  { map } for  pid=60579 comm="python3" '
    'path="/dev/dri/renderD128" dev="private-device" ino=999 '
    'scontext=system_u:system_r:onpc_kiosk_app_t:s0 '
    'tcontext=system_u:object_r:dri_device_t:s0 tclass=chr_file permissive=0')
KIOSK_VULKAN_FAILURE = (
    'Vulkan: ../src/intel/vulkan/anv_allocator.c:1871: mmap failed: Permission denied '
    '(VK_ERROR_MEMORY_MAP_FAILED)')


def test_kiosk_pre_paint_crash_chain_survives_feedback_without_machine_access(
        tmp_path, monkeypatch, caplog):
    import logging
    import subprocess
    from types import SimpleNamespace
    from oh_no_parent_control import dependency_diagnostics as dependency
    from oh_no_parent_control.logs import BrokerFileHandler
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    caplog.set_level(logging.INFO)
    monkeypatch.setattr(dependency.config, "load", lambda _path: SimpleNamespace(kiosk_uid=123456))
    app = dependency.KIOSK_APP_UNIT
    renderer = [
        _kiosk_journal(KIOSK_VULKAN_FAILURE),
        _kiosk_journal('vkCreateDevice(): Mapping of a memory object has failed. '
                       '(VK_ERROR_MEMORY_MAP_FAILED) (-5)', __REALTIME_TIMESTAMP="1792266283591964"),
        _kiosk_journal('private@example.test /home/private-child secret-token'),
        _kiosk_journal(KIOSK_VULKAN_FAILURE, _UID="987654"),
        _kiosk_journal(KIOSK_VULKAN_FAILURE, _SYSTEMD_USER_UNIT="private.service"),
        _kiosk_journal(KIOSK_VULKAN_FAILURE, _EXE="/private/program"),
    ]
    security = [
        _kiosk_journal(KIOSK_GPU_DENIAL, _TRANSPORT="audit", _UID=None, _EXE=None),
        _kiosk_journal('python3[60579]: segfault at 40 ip 012345 sp 6789 error 6 '
                       'in libgallium-26.2.4.so[12345] likely on CPU 2',
                       _TRANSPORT="kernel", __REALTIME_TIMESTAMP="1792266283611381"),
        _kiosk_journal(KIOSK_GPU_DENIAL),  # Text copied by an app is not an audit record.
        _kiosk_journal(KIOSK_GPU_DENIAL.replace('permissive=0', 'permissive=1'), _TRANSPORT="audit"),
        _kiosk_journal(KIOSK_GPU_DENIAL.replace('onpc_kiosk_app_t', 'unconfined_t'), _TRANSPORT="audit"),
        _kiosk_journal('python3[987654]: segfault in libgallium-26.2.4.so[12345]', _TRANSPORT="kernel"),
    ]
    session = [
        _kiosk_journal(message, _COMM="systemd", _EXE="/usr/lib/systemd/systemd",
                       __REALTIME_TIMESTAMP=str(1792266283619000 + index * 1000))
        for index, message in enumerate([
            app + ': Main process exited, code=dumped, status=11/SEGV',
            app + ": Failed with result 'core-dump'.",
            app + ': Triggering OnFailure= dependencies.',
            'Stopped target gnome-session@oh-no-parent-control.target - '
            'GNOME Session (session: oh-no-parent-control).',
        ])
    ]
    session.extend([
        _kiosk_journal(app + ': Main process exited, code=dumped, status=11/SEGV',
                       _COMM="systemd", _EXE="/private/systemd"),
        _kiosk_journal(app + ': Main process exited, code=dumped, status=11/SEGV',
                       _COMM="systemd", _EXE="/usr/lib/systemd/systemd", _UID="987654"),
    ])
    outputs = iter([renderer, security, session])
    commands = []

    def run(command, timeout):
        commands.append(command)
        assert 0 < timeout <= 3
        return subprocess.CompletedProcess([], 0, '\n'.join(next(outputs)), '')

    monkeypatch.setattr(dependency, '_run_bounded', run)
    dependency.collect_kiosk_diagnostics('/private/config')
    values = [decode(record.onpc_payload) for record in caplog.records]
    markers = [value['fields'] for value in values if value['event'] == 'kiosk.session-journal']
    assert [value['reason'] for value in markers] == [
        'vulkan-mmap-permission-denied', 'vulkan-device-map-failed',
        'selinux-gpu-map-denied', 'mesa-segfault', 'app-exit', 'app-core-dump',
        'app-failure-shutdown', 'session-stopped']
    assert markers[4]['exit_kind'] == 'dumped' and markers[4]['exit_status'] == 11
    assert markers[0]['occurred_at'] == '2026-10-17T19:44:43.591+00:00'
    assert [value['fields']['count'] for value in values
            if value['event'] == 'kiosk.session-observation'] == [2, 2, 4]
    assert len(commands) == 3
    assert '_UID=123456' in commands[0] and '_UID=123456' in commands[2]
    assert '_TRANSPORT=audit' in commands[1] and '_TRANSPORT=kernel' in commands[1]
    assert all(command[0] == '/usr/bin/journalctl' and '--boot=0' in command
               and '--since=-24hours' in command and '--lines=200' in command
               and any(part.startswith('--grep=') for part in command) for command in commands)

    writer = DailyLogWriter(tmp_path / 'logs')
    handler = BrokerFileHandler(writer)
    for record in caplog.records:
        assert not record.args and not record.exc_info
        handler.emit(record)
    with ZipFile(BytesIO(validate_bundle(writer.snapshot()))) as archive:
        logs, _ = read_report(archive)
        exported_markers = [row['fields'] for rows in logs.values() for row in rows
                            if row['event'] == 'kiosk.session-journal']
        assert exported_markers == markers
        text = ''.join(archive.read(name).decode() for name in archive.namelist())
    # A fresh reader can establish the same chain from the archive alone.
    assert 'selinux-gpu-map-denied' in text and 'vulkan-mmap-permission-denied' in text
    assert 'mesa-segfault' in text and 'exit_kind=dumped exit_status=11' in text
    assert 'app-failure-shutdown' in text and 'session-stopped' in text
    for secret in ('123456', '987654', '60579', 'private-host', 'private-device',
                   '/dev/dri/renderD128', '/private/', 'private@example.test', '/home/private-child'):
        assert secret not in text and secret not in caplog.text


@pytest.mark.parametrize('fault', ['command', 'timeout', 'oversize', 'malformed', 'timestamp',
                                  'full-tail', 'marker-limit', 'empty', 'identity', 'budget'])
def test_kiosk_collection_preserves_failures_and_bounds_history(monkeypatch, caplog, fault):
    import logging
    import subprocess
    from types import SimpleNamespace
    from oh_no_parent_control import dependency_diagnostics as dependency
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    caplog.set_level(logging.INFO)
    calls = []

    def load(_path):
        if fault == 'identity':
            raise ValueError('private@example.test')
        return SimpleNamespace(kiosk_uid=123456)

    def run(command, timeout):
        calls.append(command)
        assert 0 < timeout <= 3
        if len(calls) > 1:
            return subprocess.CompletedProcess([], 1, '', '')
        if fault == 'command':
            return subprocess.CompletedProcess([], 1, '', 'private@example.test')
        if fault == 'timeout':
            raise subprocess.TimeoutExpired(['private'], 3, stderr='private@example.test')
        output = {
            'oversize': 'x' * (dependency.MAX_OUTPUT + 1),
            'malformed': 'private@example.test',
            'timestamp': _kiosk_journal(KIOSK_VULKAN_FAILURE, __REALTIME_TIMESTAMP='private@example.test'),
            'full-tail': '\n'.join(_kiosk_journal('private@example.test') for _ in range(200)),
            'marker-limit': '\n'.join(_kiosk_journal(KIOSK_VULKAN_FAILURE) for _ in range(21)),
        }.get(fault, '')
        return subprocess.CompletedProcess([], 0, output, 'private@example.test')

    monkeypatch.setattr(dependency.config, 'load', load)
    monkeypatch.setattr(dependency, '_run_bounded', run)
    if fault == 'budget':
        ticks = iter([0, 6, 6, 6])
        monkeypatch.setattr(dependency.time, 'monotonic', lambda: next(ticks))
    dependency.collect_kiosk_diagnostics('/private/config')
    values = [decode(record.onpc_payload) for record in caplog.records]
    observations = [value['fields'] for value in values if value['event'] == 'kiosk.session-observation']
    expected = ('unavailable' if fault in ('command', 'timeout', 'oversize', 'identity', 'budget')
                else 'complete' if fault == 'empty' else 'partial')
    assert observations[0] == {
        'source': 'identity' if fault == 'identity' else 'renderer',
        'outcome': expected, 'count': 20 if fault == 'marker-limit' else 0}
    if fault in ('identity', 'budget'):
        assert not calls
    else:
        assert len(calls) == 3
        assert observations[-1] == {'source': 'session', 'outcome': 'complete', 'count': 0}
    assert 'private' not in caplog.text


def test_pre_enable_import_failure_and_policy_cause_survive_report_privately(tmp_path, monkeypatch):
    import logging
    import subprocess
    from types import SimpleNamespace
    from gi.repository import GLib
    from oh_no_parent_control.extension_manager import ExtensionManager, UUID
    from oh_no_parent_control.logs import BrokerFileHandler

    secret = "private@example.test /home/private-child"
    message = (f"ImportError: Unable to load file from: file:///usr/share/gnome-shell/extensions/{UUID}/"
               "indicatorLogic.mjs (" + secret + ": Operation not permitted)")
    info = GLib.Variant("(a{sv})", ({"state": GLib.Variant("d", 3),
                                   "error": GLib.Variant("s", message)},)).print_(True)
    manager = ExtensionManager()
    monkeypatch.setattr(manager, "_account", lambda _uid: (object(), None))
    monkeypatch.setattr(manager, "_session_transport", lambda _account: "live-session")
    replies = iter(["(true,)", info])
    monkeypatch.setattr(manager, "_run_command", lambda *_args, **_kwargs:
                        SimpleNamespace(stdout=next(replies)))
    policy = iter(["application/javascript", "rpmdb /home/private-child/private app.js 1 " + "a" * 64,
                   "decision exclude", "%languages=application/javascript\n"
                   "allow perm=open all : ftype=%languages trust=1\n"
                   "deny_audit perm=any all : ftype=%languages"])
    monkeypatch.setattr("oh_no_parent_control.extension_manager.subprocess.run",
                        lambda *_args, **_kwargs: subprocess.CompletedProcess(
                            [], 0, stdout=next(policy), stderr=secret))
    writer = DailyLogWriter(tmp_path, now=lambda: datetime.now(timezone.utc))
    logger = logging.getLogger("onpc.extension-manager")
    monkeypatch.setattr(logger, "handlers", [BrokerFileHandler(writer)])
    monkeypatch.setattr(logger, "level", logging.INFO)
    manager.collect_diagnostics([123456])
    bundle = validate_bundle(writer.snapshot())
    with ZipFile(BytesIO(bundle)) as archive:
        logs, _info = read_report(archive)
        records = [record for rows in logs.values() for record in rows]
        load = next(record for record in records if record["event"] == "extension-manager.load-state")
        cause = next(record for record in records if record["event"] == "extension-manager.payload-policy")
        assert load["fields"]["reason"] == "import-operation-not-permitted"
        assert cause["fields"]["trust"] == "absent"
        assert cause["fields"]["filter"] == "excluded"
        assert cause["fields"]["language_policy"] == "trusted-only-rule-present"
        assert all(b"private" not in archive.read(name) and b"123456" not in archive.read(name)
                   for name in archive.namelist())


def test_packaged_diagnostic_modules_include_their_local_dependencies():
    """Source-tree imports must not conceal missing installed modules."""
    import ast
    from tests.support.paths import ROOT

    sources = next(line.split(":=", 1)[1].split()
                   for line in (ROOT / "Makefile").read_text().splitlines()
                   if line.startswith("COMMON_SOURCES :="))
    pending = ["diagnostics.py", "diagnostic_bundle.py"]
    checked = set()
    while pending:
        filename = pending.pop()
        if filename in checked:
            continue
        assert filename in sources, f"Diagnostic dependency missing from package: {filename}"
        checked.add(filename)
        tree = ast.parse((ROOT / "common/oh_no_parent_control_ui" / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                pending.append(node.module.split(".")[0] + ".py")


def test_export_includes_only_newest_three_dates_of_validated_events(tmp_path):
    for day in (10, 11, 15, 20, 21):
        writer = DailyLogWriter(tmp_path, now=lambda day=day: datetime(2026, 1, day))
        writer.write("parent", "INFO", encode(event("diagnostic.rejected", operation=day)))
    # Old files, including content that looks like an event, are never imported.
    (tmp_path / "parent" / "2026-01-21.log").write_text("private@example.test")
    bundle = diagnostics.collect_logs(tmp_path, date(2026, 1, 21))
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        logs, info = read_report(archive)
        assert set(logs) == {f"parent/2026-01-{day}.log" for day in (15, 20, 21)}
        records = [record for rows in logs.values() for record in rows]
        assert {record["operation"] for record in records} == {15, 20, 21}
        assert all(b"private@example.test" not in archive.read(name) for name in archive.namelist())


def test_export_orders_events_across_components_and_counts_corruption(tmp_path):
    writer = DailyLogWriter(tmp_path, now=lambda: datetime(2026, 1, 21))
    for index, component in enumerate(("parent", "broker", "child"), 1):
        writer.write(component, "INFO", encode(event("diagnostic.rejected", operation=index)))
    (tmp_path / "parent" / "2026-01-21.events.1").write_text("private@example.test\n")
    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        logs, info = read_report(archive)
        records = sorted((record for rows in logs.values() for record in rows), key=lambda r: r["sequence"])
        assert [record["operation"] for record in records] == [1, 2, 3]
        assert info["counts"]["invalid"] == 1


def test_export_refuses_symlinks_without_reading_target(tmp_path):
    component = tmp_path / "parent"
    component.mkdir()
    (component / "2026-09-04.events").symlink_to(tmp_path / "private")
    with pytest.raises(OSError):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 4))


def test_empty_export_explains_missing_history(tmp_path):
    bundle = diagnostics.collect_logs(tmp_path, date(2026, 9, 4))
    validate_bundle(bundle)
    with ZipFile(BytesIO(bundle)) as archive:
        logs, info = read_report(archive)
        assert not logs
        assert info["counts"]["missing"] == 4
        assert {name for name in archive.namelist() if name.endswith("/")} == {
            "broker/", "parent/", "child/", "kiosk/"}


def test_export_rejects_hard_links(tmp_path):
    component = tmp_path / "kiosk"
    component.mkdir()
    source = tmp_path / "private"
    source.write_text("not a product log")
    (component / "2026-09-09.events").hardlink_to(source)
    with pytest.raises(ValueError, match="Unsupported diagnostic file"):
        diagnostics.collect_logs(tmp_path, date(2026, 9, 9))


def test_trim_preserves_incident_context_before_routine_history(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "MAX_RECORDS", 3)
    writer = DailyLogWriter(tmp_path)
    writer.write("broker", "ERROR", encode(event("diagnostic.rejected", operation=1)))
    for index in range(2, 12):
        writer.write("broker", "INFO", encode(event("diagnostic.rejected", operation=index)))
    with ZipFile(BytesIO(writer.snapshot())) as archive:
        logs, info = read_report(archive)
        records = [record for rows in logs.values() for record in rows]
        assert [record["operation"] for record in records] == [1, 10, 11]
        assert info["counts"]["truncated"] == 8


def test_export_selects_three_dates_independently_for_each_component(tmp_path):
    for component, days in (("broker", (18, 19, 20)), ("child", (2, 5, 9))):
        for day in days:
            writer = DailyLogWriter(tmp_path, now=lambda day=day: datetime(2026, 1, day))
            writer.write(component, "INFO", encode(event("diagnostic.rejected", operation=day)))
    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        logs, _ = read_report(archive)
        assert set(logs) == {f"{component}/2026-01-{day:02}.log"
            for component, days in (("broker", (18, 19, 20)), ("child", (2, 5, 9))) for day in days}


def test_midnight_incident_does_not_move_retained_events_to_the_next_day(tmp_path):
    now = [datetime(2026, 1, 20, 23, 59, tzinfo=timezone.utc)]
    writer = DailyLogWriter(tmp_path, now=lambda: now[0])
    writer.write("broker", "INFO", encode(event("diagnostic.rejected", operation=1)))
    now[0] = datetime(2026, 1, 21, tzinfo=timezone.utc)
    writer.write("broker", "ERROR", encode(event("diagnostic.rejected", operation=2)))
    with ZipFile(BytesIO(diagnostics.collect_logs(tmp_path, date(2026, 1, 21)))) as archive:
        logs, _ = read_report(archive)
        assert [r["operation"] for r in logs["broker/2026-01-20.log"]] == [1]
        assert [r["operation"] for r in logs["broker/2026-01-21.log"]] == [2]


def test_download_saves_exact_archive_privately(tmp_path):
    from types import SimpleNamespace
    from gi.repository import Gio, GLib
    from common.oh_no_parent_control_ui.feedback import FeedbackDialog

    path = tmp_path / "download.zip"
    loop = GLib.MainLoop()
    messages = []
    dialog = SimpleNamespace()

    def done(message):
        messages.append(message)
        loop.quit()

    dialog._download_done = done
    dialog._download_saved = lambda *args: FeedbackDialog._download_saved(dialog, *args)
    chooser = SimpleNamespace(save_finish=lambda _: Gio.File.new_for_path(str(path)))
    FeedbackDialog._download_selected(dialog, chooser, None, b"archive contents")
    timeout = GLib.timeout_add_seconds(5, lambda: (loop.quit(), False)[1])
    try:
        loop.run()
    finally:
        GLib.source_remove(timeout)
    assert messages == ["Downloaded · Ready to examine"]
    assert path.read_bytes() == b"archive contents"
    assert path.stat().st_mode & 0o777 == 0o600
