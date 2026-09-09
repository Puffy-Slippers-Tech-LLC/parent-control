"""SSH quoting, archive confinement and reboot regressions; no live VM calls."""

import io
from contextlib import nullcontext
import shlex
import tarfile
from unittest.mock import Mock

import pytest

import vm_transport as transport


def config():
    return {'directory': '/tmp/onpc-system-example', 'hostname': '192.168.122.20',
            'run': 'a' * 32, 'domain_uuid': 'f95890e1-88e7-4779-8ae3-53fdcc34330a', 'domain_id': 71}


def client():
    commands = Mock()
    commands.run.return_value = b''
    commands.last_returncode = 0
    return transport.Transport(config(), commands, guard=Mock())


@pytest.fixture(autouse=True)
def no_live_readiness_timer(monkeypatch):
    event = Mock()
    monkeypatch.setattr(transport, 'readiness_events', lambda: nullcontext(event))
    return event


def test_readiness_waits_through_ssh_handshake_reset(no_live_readiness_timer):
    value = client()
    def result(*args, **kwargs):
        value.commands.last_returncode = 255 if value.commands.run.call_count == 1 else 0
        return b'ready'
    value.commands.run.side_effect = result
    assert value.probe_ready() == b'ready'
    assert value.commands.run.call_count == value.guard.call_count == 2
    no_live_readiness_timer.wait.assert_called_once()


def test_guest_guard_failure_is_not_retried():
    value = client()
    value.commands.last_returncode = 1
    with pytest.raises(transport.Error, match='guest-probe-failed'):
        value.probe_ready()
    assert value.commands.run.call_count == 1


def test_readiness_transport_failure_has_one_bounded_deadline(monkeypatch):
    value = client()
    value.commands.last_returncode = 255
    times = iter([0, 0, 1, 2])
    monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
    with pytest.raises(transport.Error, match='readiness-timeout'):
        value.probe_ready(timeout=1)
    assert value.commands.run.call_count == 1


def test_replaced_domain_during_readiness_is_not_retried():
    value = client()
    value.guard.side_effect = transport.Error('transport:domain-replaced-or-shared')
    with pytest.raises(transport.Error, match='domain-replaced'):
        value.probe_ready()
    value.commands.run.assert_not_called()


def test_shell_metacharacters_remain_literal_arguments():
    args = ['printf', '%s', "x; touch /danger $(echo no) 'value'\n"]
    command = transport.remote(config(), args).split(' && exec ', 1)[1]
    assert shlex.split(command) == args


def test_ssh_uses_only_run_key_and_pinned_host_key():
    args = transport.ssh(config())
    for option in ('StrictHostKeyChecking=yes', 'BatchMode=yes', 'IdentitiesOnly=yes',
                   'GlobalKnownHostsFile=/dev/null'):
        assert option in args
    assert args[-1] == 'root@192.168.122.20'


def test_replaced_domain_cannot_receive_any_command():
    value = client()
    value.guard.side_effect = transport.Error('transport:domain-replaced-or-shared')
    with pytest.raises(transport.Error):
        value.call(['true'])
    value.commands.run.assert_not_called()


def test_reboot_requires_observed_boot_id_change():
    value = client()
    value.commands.run.side_effect = [b'a' * 64 + b'\n', b'', b'b' * 64 + b'\n']
    value.reboot()
    assert value.guard.call_count == 4


def test_reboot_waits_for_old_boot_to_finish(no_live_readiness_timer):
    value = client()
    responses = iter([(0, b'a' * 64 + b'\n'), (255, b''),
                      (0, b'a' * 64 + b'\n'), (255, b''), (0, b'b' * 64 + b'\n')])
    def result(*args, **kwargs):
        value.commands.last_returncode, raw = next(responses)
        return raw
    value.commands.run.side_effect = result
    value.reboot()
    assert value.commands.run.call_count == 5
    assert no_live_readiness_timer.wait.call_count == 2


def test_reboot_never_observed_fails_at_transition_deadline(monkeypatch):
    value = client()
    value.commands.run.side_effect = [b'a' * 64 + b'\n', b'', b'a' * 64 + b'\n']
    times = iter([0, 0, 1, 330])
    monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
    with pytest.raises(transport.Error, match='readiness-timeout'):
        value.reboot()
    assert value.commands.run.call_count == 3


def test_reboot_command_failure_does_not_start_observation():
    value = client()
    def result(*args, **kwargs):
        value.commands.last_returncode = 0 if value.commands.run.call_count == 1 else 1
        return b'a' * 64 + b'\n'
    value.commands.run.side_effect = result
    with pytest.raises(transport.Error, match='reboot-command-failed'):
        value.reboot()
    assert value.commands.run.call_count == 2


def test_customer_reboot_waits_through_old_boot_and_connection_reset(no_live_readiness_timer):
    value = client()
    responses = iter([(0, b'a'*64 + b'\n'), (255, b'private-canary'),
                      (0, b'b'*64 + b'\n')])
    def result(*args, **kwargs):
        value.commands.last_returncode, raw = next(responses)
        return raw
    value.commands.run.side_effect = result
    assert value.wait_boot_change('a'*64) == b'b'*64 + b'\n'
    assert value.guard.call_count == 6
    assert no_live_readiness_timer.wait.call_count == 2
    for call in value.commands.run.call_args_list:
        command = call.args[0][-1].split(' && exec ', 1)[1]
        assert shlex.split(command) == ['/usr/bin/python3', '-c', transport.BOOT_SHA256_PROBE]


@pytest.mark.parametrize('ssh_status', [255, 1, 127, -15])
@pytest.mark.parametrize('raw', [b'', b'b' * 64 + b'\n'])
def test_customer_reboot_guard_cannot_replace_ssh_status(ssh_status, raw, no_live_readiness_timer):
    value = client()
    responses = iter([(ssh_status, raw), (0, b'b' * 64 + b'\n')])
    def result(*args, **kwargs):
        value.commands.last_returncode, raw = next(responses)
        return raw
    value.commands.run.side_effect = result
    # The real Lease guard calls Capture.revalidate -> Commands.info using
    # this same Commands instance. Its successful qemu-img call overwrites
    # last_returncode after SSH returned. Model that actual shared state.
    value.guard.side_effect = lambda _: setattr(value.commands, 'last_returncode', 0)
    reports = []
    if ssh_status == 255:
        assert value.wait_boot_change('a' * 64, on_diagnostic=reports.append) == b'b' * 64 + b'\n'
        assert value.commands.run.call_count == 2
        no_live_readiness_timer.wait.assert_called_once()
        assert reports == [{'old_boot': 0, 'ssh_unavailable': 1, 'changed_boot': 1,
                            'outcome': 'changed-boot'}]
    else:
        with pytest.raises(transport.Error, match='guest-probe-failed'):
            value.wait_boot_change('a' * 64, on_diagnostic=reports.append)
        assert value.commands.run.call_count == 1
        no_live_readiness_timer.wait.assert_not_called()
        assert reports[0]['outcome'] == 'guest-probe-failed'


@pytest.mark.parametrize('raw', [b'', b'b'*64, b'b'*64 + b'\r\n',
                               b'B'*64 + b'\n', b'private-canary\n'])
def test_customer_reboot_malformed_output_is_terminal(raw, no_live_readiness_timer):
    value = client()
    value.commands.run.return_value = raw
    with pytest.raises(transport.Error, match='invalid-boot-output'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1
    no_live_readiness_timer.wait.assert_not_called()


@pytest.mark.parametrize('status', [1, 127, -15])
def test_customer_reboot_guest_failure_is_not_transient(status, no_live_readiness_timer):
    value = client()
    value.commands.last_returncode = status
    with pytest.raises(transport.Error, match='guest-probe-failed'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1
    no_live_readiness_timer.wait.assert_not_called()


@pytest.mark.parametrize('status,raw', [(0, b'a'*64 + b'\n'), (255, b'')])
def test_customer_reboot_old_boot_and_disconnect_share_deadline(monkeypatch, status, raw):
    value = client()
    value.commands.last_returncode = status
    value.commands.run.return_value = raw
    times = iter([0, 0, 1, 330])
    monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
    with pytest.raises(transport.Error, match='readiness-timeout'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1


@pytest.mark.parametrize('when', ['before', 'after', 'next-poll'])
def test_customer_reboot_ownership_loss_never_accepts_or_retries(when):
    value = client()
    value.commands.run.side_effect = [b'a'*64 + b'\n', b'b'*64 + b'\n']
    guards = {'before': 0, 'after': 1, 'next-poll': 2}[when]
    value.guard.side_effect = [None]*guards + [transport.Error('transport:domain-replaced')]
    with pytest.raises(transport.Error, match='domain-replaced'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == (0 if when == 'before' else 1)


@pytest.mark.parametrize('when', ['command', 'wait'])
def test_customer_reboot_configuration_cannot_change_between_probes(when, no_live_readiness_timer):
    value = client()
    value.commands.run.return_value = b'a'*64 + b'\n'
    def replace(*args, **kwargs):
        value.config['hostname'] = 'replaced.invalid'
        return b'b'*64 + b'\n'
    if when == 'command':
        value.commands.run.side_effect = replace
    else:
        no_live_readiness_timer.wait.side_effect = replace
    with pytest.raises(transport.Error, match='configuration-changed'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1


@pytest.mark.parametrize('before', [None, True, 'a'*63, 'A'*64, 'a'*64 + '\n'])
def test_customer_reboot_invalid_previous_identity_cannot_open_transport(before):
    value = client()
    with pytest.raises(transport.Error, match='invalid-previous-boot'):
        value.wait_boot_change(before)
    value.commands.run.assert_not_called()


@pytest.mark.parametrize('fault,expected', [
    ('old', 'readiness-timeout'), ('ssh', 'readiness-timeout'),
    ('malformed', 'invalid-boot-output'), ('guest', 'guest-probe-failed'),
    ('ownership', 'domain-replaced-or-shared'), ('unknown', 'unknown-error'),
    ('interrupt', 'interrupted'),
])
def test_reboot_diagnostics_retain_fixed_counts_and_terminal_cause(monkeypatch, fault, expected):
    value = client()
    reports = []
    value.commands.run.return_value = b'a'*64 + b'\n'
    if fault in ('old', 'ssh'):
        times = iter([0, 0, 1, 330])
        monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
        value.commands.last_returncode = 255 if fault == 'ssh' else 0
    elif fault == 'malformed':
        value.commands.run.return_value = b'private-canary'
    elif fault == 'guest':
        value.commands.last_returncode = 1
    elif fault == 'ownership':
        value.guard.side_effect = transport.Error('transport:domain-replaced-or-shared')
    else:
        value.commands.run.side_effect = (KeyboardInterrupt('private-canary') if fault == 'interrupt'
                                          else RuntimeError('private-canary'))
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else RuntimeError):
        value.wait_boot_change('a'*64, on_diagnostic=reports.append)
    assert reports == [{'old_boot': int(fault == 'old'), 'ssh_unavailable': int(fault == 'ssh'),
                        'changed_boot': 0, 'outcome': expected}]


def test_reboot_diagnostic_checkpoint_failure_cannot_return_success():
    value = client()
    value.commands.run.return_value = b'b'*64 + b'\n'
    with pytest.raises(RuntimeError, match='checkpoint-failed'):
        value.wait_boot_change('a'*64,
            on_diagnostic=Mock(side_effect=RuntimeError('checkpoint-failed')))


@pytest.mark.parametrize('name', ['../../escape', '/etc/escape'])
def test_archive_path_escape_is_refused_before_extraction(tmp_path, name):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        archive.addfile(tarfile.TarInfo(name), io.BytesIO())
    with pytest.raises(transport.Error, match='archive-path'):
        transport.extract(stream.getvalue(), tmp_path / 'output')


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE])
def test_archive_links_devices_and_fifos_are_refused(tmp_path, kind):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        entry = tarfile.TarInfo('unexpected')
        entry.type, entry.linkname = kind, '/etc/passwd'
        archive.addfile(entry)
    with pytest.raises(transport.Error, match='archive-special-file'):
        transport.extract(stream.getvalue(), tmp_path / 'output')


def test_copyup_cannot_escape_owned_run_directory():
    value = client()
    with pytest.raises(transport.Error, match='host-path'):
        value.copy(True, '/etc/passwd', '/etc/host-overwrite')
    value.commands.run.assert_not_called()


def test_plain_files_round_trip_through_safe_archive(tmp_path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        entry = tarfile.TarInfo('results.xml')
        entry.size = 7
        archive.addfile(entry, io.BytesIO(b'<test/>'))
    transport.extract(stream.getvalue(), tmp_path / 'output')
    assert (tmp_path / 'output/results.xml').read_bytes() == b'<test/>'
