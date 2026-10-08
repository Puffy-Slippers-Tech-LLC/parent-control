"""One-shot grant and asynchronous-observation contracts, with no real OS calls."""

import json
from configparser import ConfigParser
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_graphical_expiry as expiry


@pytest.fixture
def boot_rig(tmp_path, monkeypatch):
    system = tmp_path / 'system'
    # Model the protected systemd directory regardless of the host's umask.
    system.mkdir(mode=0o755)
    service = system / expiry.BOOT_UNIT
    dropin = system / 'display-manager.service.d' / 'onpc-test-graphical-expiry.conf'
    monkeypatch.setattr(expiry, 'BOOT_SERVICE', service)
    monkeypatch.setattr(expiry, 'BOOT_DROPIN', dropin)
    monkeypatch.setattr(expiry.guest, 'guard', lambda: {'run': 'a' * 32})
    lstat = Path.lstat
    def owned_directory(path):
        info = lstat(path)
        if path in (system, dropin.parent):
            return SimpleNamespace(st_mode=info.st_mode, st_uid=0, st_gid=0)
        return info
    monkeypatch.setattr(Path, 'lstat', owned_directory)
    run = Mock(side_effect=lambda args: (
        expiry.guest.BROKER if args[2] == expiry.BOOT_UNIT else expiry.BOOT_UNIT
    ) if args[:2] == ['systemctl', 'show'] else '')
    monkeypatch.setattr(expiry.guest, 'run', run)
    return service, dropin, run


@pytest.mark.parametrize('fedora', [False, True])
def test_broker_boot_precedes_gdm_without_starting_services_from_pam(boot_rig, fedora):
    service, dropin, run = boot_rig
    expiry.prepare_broker_boot(fedora=fedora)
    for path, dependency, relationship in (
            (service, expiry.guest.BROKER, 'Wants'), (dropin, expiry.BOOT_UNIT, 'Requires')):
        configuration = ConfigParser(interpolation=None)
        configuration.read_string(path.read_text())
        assert dependency in configuration['Unit'][relationship].split()
        assert dependency in configuration['Unit']['After'].split()
        if path == service:
            # A later broker recovery must not stop this witness and, through
            # GDM's Requires edge, terminate the desktop being verified.
            for stop_relationship in ('Requires', 'Requisite', 'BindsTo', 'PartOf'):
                assert expiry.guest.BROKER not in configuration['Unit'].get(
                    stop_relationship, '').split()
            assert configuration['Service']['Type'] == 'oneshot'
            assert configuration['Service']['RemainAfterExit'] == 'yes'
            command = configuration['Service']['ExecStart'].split()
            assert command == ['/usr/bin/env', 'ONPC_EXPECTED_RUN=' + 'a' * 32,
                               '/usr/bin/python3', '-B',
                               str(expiry.guest.PAYLOAD / 'system_graphical_expiry.py'), 'broker-ready']
    assert stat.S_IMODE(service.stat().st_mode) == stat.S_IMODE(dropin.stat().st_mode) == 0o644
    calls = [c.args[0] for c in run.call_args_list]
    labels = [['restorecon', str(service), str(dropin.parent), str(dropin)]] if fedora else []
    assert calls == labels + [['systemctl', 'daemon-reload']] + [
        ['systemctl', 'show', unit, '--property=' + property, '--value']
        for unit, relationship in ((expiry.BOOT_UNIT, 'Wants'),
                                   ('display-manager.service', 'Requires'))
        for property in (relationship, 'After')]


@pytest.mark.parametrize('target', ['service', 'dropin', 'directory-link', 'directory-writable'])
def test_boot_fixture_preserves_foreign_configuration(boot_rig, tmp_path, target):
    service, dropin, run = boot_rig
    path = service if target == 'service' else dropin
    if target == 'directory-link':
        dropin.parent.symlink_to(tmp_path, target_is_directory=True)
    else:
        dropin.parent.mkdir()
        if target == 'directory-writable':
            dropin.parent.chmod(0o777)
        else:
            path.write_text('foreign')
    with pytest.raises(expiry.guest.GuestError, match='broker-boot-(fixture-collision|directory)'):
        expiry.prepare_broker_boot(fedora=True)
    if target in ('service', 'dropin'):
        assert path.read_text() == 'foreign'
    run.assert_not_called()


def test_boot_fixture_requires_loaded_dependency_order(boot_rig):
    _, _, run = boot_rig
    run.side_effect = None
    run.return_value = ''
    with pytest.raises(expiry.guest.GuestError, match='broker-boot-ordering'):
        expiry.prepare_broker_boot(fedora=False)


@pytest.fixture
def broker_rig(tmp_path, monkeypatch):
    monkeypatch.setattr(expiry, 'FIXTURE', tmp_path)
    (tmp_path / 'prepared.json').write_text(json.dumps({'run': 'run', 'boot': 'old'}))
    monkeypatch.setattr(expiry.guest, 'guard', lambda: {'run': 'run'})
    monkeypatch.setattr(expiry.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(expiry, 'Path', lambda value: SimpleNamespace(read_text=lambda: 'new'))
    run = Mock(side_effect=['active', 'a' * 32])
    monkeypatch.setattr(expiry.guest, 'run', run)
    return tmp_path, run


def test_boot_broker_witness_is_current_and_does_not_issue_a_grant(broker_rig, monkeypatch):
    path, run = broker_rig
    grant = Mock()
    monkeypatch.setattr(expiry, 'grant', grant)
    expiry.broker_ready()
    assert json.loads((path / 'broker-ready.json').read_text()) == {
        'run': 'run', 'boot': 'new', 'broker_invocation': 'a' * 32}
    grant.assert_not_called()
    assert [c.args[0] for c in run.call_args_list] == [
        ['systemctl', 'is-active', expiry.guest.BROKER],
        ['systemctl', 'show', expiry.guest.BROKER, '--property=InvocationID', '--value']]
    run.side_effect = ['active', 'a' * 32]
    with pytest.raises(FileExistsError):
        expiry.broker_ready()


@pytest.mark.parametrize(('active', 'invocation'), [
    ('inactive', 'a' * 32), ('active', ''), ('active', '0' * 32), ('active', 'invalid'),
])
def test_boot_broker_does_not_publish_an_inactive_or_unidentified_service(broker_rig, active, invocation):
    path, run = broker_rig
    run.side_effect = [active, invocation]
    with pytest.raises(expiry.guest.GuestError, match='broker-boot-(inactive|invocation)'):
        expiry.broker_ready()
    assert not (path / 'broker-ready.json').exists()


@pytest.mark.parametrize(('fedora', 'anchor'), [
    (False, '@include common-account'),
    (True, 'account include system-auth'),
    (True, 'account    substack password-auth # native account stack'),
])
def test_one_second_seed_precedes_native_account_stack_without_reordering(fedora, anchor):
    original = ('auth required pam_env.so\naccount required pam_nologin.so\n'
                + anchor + '\nsession required pam_systemd.so\n')
    seeded = expiry.seed_account_stack(original, fedora=fedora)
    seed = f'account required pam_exec.so quiet quiet_log {expiry.SEED}\n'
    assert seeded == original.replace(anchor + '\n', seed + anchor + '\n')
    assert seeded.replace(seed, '') == original


@pytest.mark.parametrize(('fedora', 'original'), [
    (True, '@include common-account\n'),
    (False, 'account include system-auth\n'),
    (True, '# account include system-auth\n'),
    (True, 'account include system-auth\naccount substack password-auth\n'),
    (False, '@include common-account\n@include common-account\n'),
])
def test_seed_refuses_missing_or_ambiguous_platform_account_stack(fedora, original):
    with pytest.raises(expiry.guest.GuestError, match='gdm-pam-account-include'):
        expiry.seed_account_stack(original, fedora=fedora)


@pytest.mark.parametrize('fresh', [False, True])
def test_verify_retains_observations_before_later_failure(tmp_path, monkeypatch, fresh):
    output = tmp_path / 'results'
    if not fresh:
        output.mkdir()
    monkeypatch.setattr(expiry.guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'FIXTURE', tmp_path)
    monkeypatch.setattr(expiry, 'identities', lambda: {'child': 1001})
    observations = [['prerequisite', 'verified']]
    (tmp_path / 'prerequisites.json').write_text(json.dumps(observations))
    monkeypatch.setattr(expiry, 'wait_for', Mock(side_effect=RuntimeError('later failure')))
    publish = Mock()
    with pytest.raises(RuntimeError, match='later failure'):
        expiry.verify(publish)
    assert json.loads((output / 'session-observations.json').read_text()) == observations
    assert not (output / 'session-observations.pending').exists()
    publish.assert_called_once_with('prerequisite', 'verified')


@pytest.fixture
def seed_rig(monkeypatch, tmp_path):
    monkeypatch.setattr(expiry, 'FIXTURE', tmp_path)
    (tmp_path / 'prepared.json').write_text(json.dumps({'run': 'run', 'boot': 'old'}))
    (tmp_path / 'broker-ready.json').write_text(json.dumps({
        'run': 'run', 'boot': 'new', 'broker_invocation': 'a' * 32}))
    monkeypatch.setattr(expiry.guest, 'guard', lambda: {'run': 'run'})
    monkeypatch.setattr(expiry, 'identities', lambda: {'child': 1001})
    monkeypatch.setattr(expiry, 'Path', lambda value: SimpleNamespace(read_text=lambda: 'new'))
    monkeypatch.setattr(expiry.pwd, 'getpwuid', lambda uid: SimpleNamespace(pw_name='fixture-child'))
    monkeypatch.setenv('PAM_TYPE', 'account')
    monkeypatch.setenv('PAM_SERVICE', 'gdm-autologin')
    monkeypatch.setenv('PAM_USER', 'fixture-child')
    monkeypatch.setattr(expiry.guest, 'run', Mock(return_value='a' * 32))
    monkeypatch.setattr(expiry, '_seed_security_type', lambda: 'xdm_t')
    monkeypatch.setattr(expiry.time, 'time', lambda: 10.1)
    monkeypatch.setattr(expiry.time, 'sleep', Mock())
    grant = Mock(return_value=11)
    monkeypatch.setattr(expiry, 'grant', grant)
    return tmp_path, grant


def test_seed_publishes_only_complete_result_and_never_regrants(seed_rig):
    path, grant = seed_rig
    def issue(*args):
        assert (path / 'seed-attempt.json').exists()
        assert not (path / 'seeded.json').exists()
        return 11
    grant.side_effect = issue
    expiry.seed()
    result = json.loads((path / 'seeded.json').read_text())
    assert result['remaining_seconds'] == 0.9
    assert result['boot'] == 'new'
    assert result['broker_invocation'] == 'a' * 32
    expiry.guest.run.assert_not_called()
    with pytest.raises(expiry.guest.GuestError, match='seed-already-complete'):
        expiry.seed()
    grant.assert_called_once_with(1001, 1)


def test_failed_seed_is_not_published_or_retried(seed_rig):
    path, grant = seed_rig
    grant.side_effect = RuntimeError('fixed test failure')
    with pytest.raises(RuntimeError, match='fixed test failure'):
        expiry.seed()
    assert not (path / 'seeded.json').exists()
    with pytest.raises(FileExistsError):
        expiry.seed()
    grant.assert_called_once()


@pytest.mark.parametrize('witness', [None,
    {'run': 'other-run', 'boot': 'new', 'broker_invocation': 'a' * 32},
    {'run': 'run', 'boot': 'old', 'broker_invocation': 'a' * 32},
    {'run': 'run', 'boot': 'new', 'broker_invocation': '0' * 32},
    {'run': 'run', 'boot': 'new', 'broker_invocation': 'invalid'},
])
def test_missing_or_stale_broker_witness_retains_context_without_grant_or_retry(seed_rig, witness):
    path, grant = seed_rig
    if witness is None:
        (path / 'broker-ready.json').unlink()
    else:
        (path / 'broker-ready.json').write_text(json.dumps(witness))
    with pytest.raises((FileNotFoundError, expiry.guest.GuestError)):
        expiry.seed()
    attempt = json.loads((path / 'seed-attempt.json').read_text())
    assert attempt['stage'] == 'broker-witness' and attempt['failed']
    assert attempt['security_type'] == 'xdm_t'
    assert not (path / 'seeded.json').exists()
    grant.assert_not_called()
    expiry.guest.run.assert_not_called()
    with pytest.raises(FileExistsError):
        expiry.seed()
    expiry.guest.run.assert_not_called()


@pytest.mark.parametrize('prefix', [b'', b'node=fixture-host '])
def test_audit_denial_keeps_security_coordinates_without_command_lines(prefix):
    raw = (prefix + b'type=USER_AVC msg=audit(123.456:42): pid=1 uid=0 '
           b'msg=\'avc:  denied { start } for '
           b'path="/usr/lib/systemd/system/oh-no-parent-control-broker.service" '
           b'cmdline="fixture-secret" scontext=system_u:system_r:xdm_t:s0 '
           b'tcontext=system_u:object_r:systemd_unit_file_t:s0 tclass=service permissive=0\'\n'
           b'type=PROCTITLE msg=audit(123.456:42): proctitle=66697874757265\n')
    rows = expiry.guest._audit_denials(raw)
    assert rows == [{'type': 'USER_AVC', 'epoch': '123.456', 'serial': '42',
                     'broker_unit': True, 'permissions': ['start'], 'pid': '1', 'uid': '0',
                     'scontext': 'system_u:system_r:xdm_t:s0',
                     'tcontext': 'system_u:object_r:systemd_unit_file_t:s0',
                     'tclass': 'service', 'permissive': '0'}]
    assert 'fixture-secret' not in json.dumps(rows) and 'proctitle' not in json.dumps(rows)


@pytest.mark.parametrize('reader', [None, '/usr/sbin/ausearch'])
def test_access_collector_uses_log_files_and_redacts_optional_reader_errors(
        tmp_path, monkeypatch, reader):
    guest = expiry.guest
    monkeypatch.setattr(guest, 'guard', Mock())
    monkeypatch.setattr(guest.shutil, 'which', lambda name: reader)
    journal = Mock()
    journal.run.return_value = b'fixture-user access denied'
    audit = Mock(last_returncode=1)
    def search(command, **options):
        assert '--input-logs' in command  # stdin is deliberately closed by Commands.
        options['on_output'](b'fixture-user reader error', 'stderr')
        return b''
    audit.run.side_effect = search
    commands = Mock(side_effect=[journal, audit])
    monkeypatch.setattr(guest, 'Commands', commands)
    guest.collect_seed_access(tmp_path, lambda text: text.replace('fixture-user', '[Child user]'))
    assert (tmp_path / 'graphical-expiry-access-journal.txt').read_text() == (
        '[Child user] access denied')
    result = json.loads((tmp_path / 'graphical-expiry-access-audit.json').read_text())
    assert result['denials'] == []
    if reader is None:
        assert result['status'] == 'reader-unavailable' and commands.call_count == 1
        audit.run.assert_not_called()
    else:
        assert result['returncode'] == 1 and result['stderr'] == '[Child user] reader error'
        audit.run.assert_called_once()


def test_wait_requires_observation_and_keeps_one_deadline(monkeypatch):
    times = iter([0, 1, 91])
    monkeypatch.setattr(expiry.time, 'monotonic', lambda: next(times))
    pause = Mock()
    monkeypatch.setattr(expiry.time, 'sleep', pause)
    observe = Mock(return_value=False)
    with pytest.raises(expiry.guest.GuestError, match='test:missing'):
        expiry.wait_for(observe, 'test:missing')
    assert observe.call_count == 2
    pause.assert_called_once()


@pytest.mark.parametrize('properties', [
    'User=2000\nClass=user\nTTY=tty7',
    'User=1005\nClass=user\nTTY=tty3',
])
def test_foreground_fixture_refuses_an_occupied_vt_or_existing_other_session(monkeypatch, properties):
    monkeypatch.setattr(expiry.guest, 'guard', lambda: {'run': 'fixed-run'})
    monkeypatch.setattr(expiry, 'identities', lambda: {'other': 1005})
    run = Mock(side_effect=['9 2000 user seat0 tty7', properties])
    monkeypatch.setattr(expiry.guest, 'run', run)
    issue = Mock()
    monkeypatch.setattr(expiry, 'grant', issue)
    with pytest.raises(expiry.guest.GuestError, match='foreground-fixture-collision'):
        expiry.verify_other_foreground(1004, '4', Mock())
    assert all(c.args[0][0] == 'loginctl' for c in run.call_args_list)
    issue.assert_not_called()


@pytest.mark.parametrize(('hint', 'active'), [('no', True), ('yes', False)])
def test_lock_observer_preserves_hint_but_uses_native_activity(monkeypatch, hint, active):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'child_session', lambda uid: ('4', {'LockedHint': hint}))
    monkeypatch.setattr(expiry, 'account_property', lambda *args: 0)
    manager = Mock()
    manager._run_command.side_effect = [SimpleNamespace(stdout=value) for value in
        ('(true,)' if active else '(false,)', 'true', 'false')]
    state = expiry.screen_lock_observation(1004, '4', manager, Mock())
    assert state['screensaver_active'] is active
    assert state['logind_locked'] is (hint == 'yes')
    assert all(call.kwargs == {'require_live': True} for call in manager._run_command.call_args_list)


@pytest.mark.parametrize(('password_mode', 'enabled', 'disabled', 'category'), [
    (2, 'true', 'false', 'lock-policy-not-enforcing'),
    (0, 'false', 'false', 'lock-policy-not-enforcing'),
    (0, 'true', 'true', 'lock-policy-not-enforcing'),
    (0, 'unknown', 'false', 'lock-observation-response'),
])
def test_active_screensaver_alone_cannot_satisfy_lock_observer(
        monkeypatch, password_mode, enabled, disabled, category):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'child_session', lambda uid: ('4', {'LockedHint': 'yes'}))
    monkeypatch.setattr(expiry, 'account_property', lambda *args: password_mode)
    manager = Mock()
    manager._run_command.side_effect = [SimpleNamespace(stdout=value) for value in
                                       ('(true,)', enabled, disabled)]
    with pytest.raises(expiry.guest.GuestError, match=category):
        expiry.screen_lock_observation(1004, '4', manager, Mock())


def test_lock_observer_refuses_replacement_session_before_shell_query(monkeypatch):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'child_session', lambda uid: ('5', {'LockedHint': 'yes'}))
    manager = Mock()
    with pytest.raises(expiry.guest.GuestError, match='desktop-ended'):
        expiry.screen_lock_observation(1004, '4', manager, Mock())
    manager._run_command.assert_not_called()
