"""Current installed composition, session observations and owned PAM workers."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from tests.support.paths import ROOT
from tools.test_storage import scratch_descriptors

def module(path):
    spec = importlib.util.spec_from_file_location('private_' + path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_postrm_embedded_finalizer_runs_after_payload_erasure(distribution, tmp_path, monkeypatch):
    from tests.support.package_scripts import prepared_lifecycle_machine
    from tests.support.shell import relocate_system_paths
    machine = prepared_lifecycle_machine(tmp_path, monkeypatch)
    helper = machine.migration
    helper.prepare_remove()
    renderer = module(ROOT / 'packaging/render_lifecycle.py')
    postrm = renderer.render(ROOT, distribution, 'postrm')
    assert postrm.index('    remove_package_created_kiosk\n') < postrm.index(
        "/usr/bin/python3 -I - <<'ONPC_CONFINEMENT_FINISH_REMOVE'")
    embedded = renderer.embedded_confinement_finish_remove(ROOT)
    source = embedded.split('\n', 1)[1].rsplit('\nONPC_CONFINEMENT_FINISH_REMOVE', 1)[0]
    # C02 embeds the selected migration, whose constants differ from the old
    # integration helper. Relocate that actual source and model account removal;
    # retain all filesystem/record guards without querying host NSS or policy.
    source = relocate_system_paths(source, tmp_path, prefixes=(
        '/etc/', '/var/', '/run/', '/home/', '/usr/', '/sys/', '/proc/'))
    source = source.replace("ROOT = Path('/')", f'ROOT = Path({str(tmp_path)!r})')
    source = source.replace("Path('/run')", f'Path({str(tmp_path / "run")!r})')
    source = source.replace("Path('/proc')", f'Path({str(tmp_path / "proc")!r})')
    source = source.replace('OWNER = 0', f'OWNER = {os.getuid()}')
    source = source.replace('GROUP = 0', f'GROUP = {os.getgid()}')
    source = source.replace('pwd.getpwnam(USER)', '(_ for _ in ()).throw(KeyError(USER))')
    source = source.replace('pwd.getpwuid(identity)', '(_ for _ in ()).throw(KeyError(identity))')
    # Removing policy bytes demonstrates the finalizer needs only its durable
    # record and standalone deny stacks after the package files have gone.
    for payload in helper.PAYLOAD.iterdir():
        payload.unlink()
    result = subprocess.run([sys.executable, '-I', '-'], input=source,
                            capture_output=True, text=True, timeout=10,
                            pass_fds=scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert not helper.STATE.exists()
    assert not helper.DISABLED.exists()
    assert (helper.PAM / 'gdm-password').read_text() == 'session required pam_unix.so\n'
    assert not (helper.PAM / 'systemd-user').exists()


@pytest.fixture
def census_model(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tests/integration'))
    return module(ROOT / 'tests/integration/system_kiosk_confinement.py')

@pytest.fixture
def admission_model(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tests/integration'))
    return module(ROOT / 'tests/integration/system_kiosk_admission.py')


def test_restart_admission_gates_use_controls_and_exact_denials_without_routing_mutation(
        admission_model, monkeypatch):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'enable_diagnostics', Mock())
    identities = {
        helper.USERS['kiosk']: SimpleNamespace(pw_uid=41001, pw_shell='/usr/sbin/nologin'),
        helper.USERS['ordinary']: SimpleNamespace(pw_uid=41002),
    }
    monkeypatch.setattr(helper.pwd, 'getpwnam', identities.__getitem__)
    probe = Mock()
    mutation = Mock(side_effect=AssertionError('retained routing must stay unchanged'))
    monkeypatch.setattr(helper, 'probe', probe)
    monkeypatch.setattr(helper, 'set_routing', mutation)
    record = Mock()
    helper.verify_gates(record)
    assert [call.args for call in probe.call_args_list] == [
        ('gdm-password', 'ordinary', 0, 'gdm-password.ordinary-before', record),
        ('login', 'ordinary', 0, 'login.ordinary-before', record),
        ('sshd', 'ordinary', 0, 'sshd.ordinary-before', record),
        ('gdm-password', 'kiosk', 0, 'dedicated-before', record),
        ('login', 'kiosk', 6, 'login.denied', record),
        ('login', 'ordinary', 0, 'login.ordinary-after', record),
        ('sshd', 'kiosk', 6, 'sshd.denied', record),
        ('sshd', 'ordinary', 0, 'sshd.ordinary-after', record),
    ]
    mutation.assert_not_called()


def test_restart_admission_guest_refusal_precedes_identity_and_pam_workers(
        admission_model, monkeypatch):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock(side_effect=helper.guest.GuestError('identity')))
    identity, probe = Mock(), Mock()
    monkeypatch.setattr(helper.pwd, 'getpwnam', identity)
    monkeypatch.setattr(helper, 'probe', probe)
    with pytest.raises(helper.guest.GuestError, match='identity'):
        helper.verify_gates(Mock())
    identity.assert_not_called()
    probe.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'worker'])
def test_fedora_kiosk_account_probe_uses_real_gdm_domain_and_removes_owned_fixture(
        admission_model, tmp_path, monkeypatch, fault):
    import system_kiosk_confinement as confinement

    helper = admission_model
    guard = Mock()
    monkeypatch.setattr(helper.guest, 'guard', guard)
    monkeypatch.setattr(helper.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(helper.guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(confinement.shutil, 'copyfile',
                        lambda source, target: target.write_bytes(b'private interpreter fixture'))
    label = Mock()
    monkeypatch.setattr(helper.guest, 'run', label)

    def worker(argv, **options):
        assert argv[:2] == ['/usr/bin/runcon', 'system_u:system_r:xdm_t:s0']
        caller = Path(argv[2])
        assert caller.is_relative_to(tmp_path) and caller.stat().st_mode & 0o777 == 0o700
        assert label.call_args.args[0] == ['/usr/bin/chcon', '-t', 'xdm_exec_t', str(caller)]
        assert argv[3:] == ['-B', str(Path(helper.__file__).resolve()),
                           'pam-account', 'gdm-password', 'kiosk']
        assert options == {'timeout': 45, 'merge_stderr': False}
        if fault:
            raise helper.guest.GuestError('worker-failed')
        return b'{"account":0,"end":0}'

    monkeypatch.setattr(helper.guest.commands, 'run', worker)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='worker-failed'):
            helper.probe('gdm-password', 'kiosk', 0, 'dedicated', Mock())
    else:
        helper.probe('gdm-password', 'kiosk', 0, 'dedicated', Mock())
    assert guard.call_args_list == [call(), call(expected_selinux='Enforcing')]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('service,role', [('gdm-password', 'ordinary'),
                                         ('login', 'kiosk'), ('sshd', 'kiosk')])
def test_other_fedora_account_probes_preserve_the_original_caller_command(
        admission_model, monkeypatch, service, role):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'package_path', lambda: Path('package.rpm'))
    command = Mock(return_value=b'{"account":0,"end":0}')
    monkeypatch.setattr(helper.guest.commands, 'run', command)
    helper.probe(service, role, 0, 'control', Mock())
    command.assert_called_once_with([
        '/usr/bin/python3', '-B', str(Path(helper.__file__).resolve()),
        'pam-account', service, role], timeout=45, merge_stderr=False)


def test_fedora_caller_fixture_guard_refusal_precedes_any_fixture_write(
        census_model, tmp_path, monkeypatch):
    helper = census_model
    monkeypatch.setattr(helper.guest, 'guard', Mock(side_effect=helper.guest.GuestError('identity')))
    copy = Mock()
    monkeypatch.setattr(helper.shutil, 'copyfile', copy)
    with pytest.raises(helper.guest.GuestError, match='identity'):
        with helper.pam_caller_command(tmp_path, 'gdm-password'):
            pytest.fail('refused fixture admitted a worker')
    copy.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_fedora_kiosk_account_worker_refuses_an_unconfined_caller_before_pam(
        admission_model, monkeypatch):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(Path, 'read_text', lambda _: 'unconfined_u:unconfined_r:unconfined_t:s0\0')
    identity, library = Mock(), Mock()
    monkeypatch.setattr(helper.pwd, 'getpwnam', identity)
    monkeypatch.setattr(helper.ctypes, 'CDLL', library)
    with pytest.raises(helper.guest.GuestError, match='caller-context'):
        helper.pam_account('gdm-password', 'kiosk')
    identity.assert_not_called()
    library.assert_not_called()


@pytest.mark.parametrize('result', [b'{"account": 9, "end": 0}',
                                  b'{"account": 6, "end": 4}',
                                  b'{"account": true, "end": 0}', b'not-json'])
def test_installed_admission_never_counts_unavailable_or_malformed_worker_as_denial(
        admission_model, monkeypatch, result):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    command = Mock(return_value=result)
    monkeypatch.setattr(helper.guest.commands, 'run', command)
    with pytest.raises(helper.guest.GuestError, match='kiosk-admission:'):
        helper.probe('sshd', 'kiosk', 6, 'ssh-denied', Mock())
    assert command.call_args.kwargs['timeout'] == 45
    assert command.call_args.args[0][-3:] == ['pam-account', 'sshd', 'kiosk']


@pytest.mark.parametrize('status', [0, 6])
@pytest.mark.parametrize('role', ['kiosk', 'ordinary', 'other'])
def test_installed_admission_uses_real_service_name_and_ends_denied_transactions(
        admission_model, monkeypatch, status, role):
    from unittest.mock import MagicMock
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    service = Mock()
    service.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
    directory = MagicMock()
    directory.__truediv__.return_value = service
    monkeypatch.setattr(helper, 'Path', Mock(return_value=directory))
    monkeypatch.setattr(helper.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(
        pw_uid=41001, pw_name=helper.USERS[role])))
    pam = Mock()
    pam.pam_start.return_value = 0
    pam.pam_acct_mgmt.return_value = status
    pam.pam_end.return_value = 0
    monkeypatch.setattr(helper.ctypes, 'CDLL', Mock(return_value=pam))
    assert helper.pam_account('sshd', role) == {'account': status, 'end': 0}
    helper.pwd.getpwnam.assert_called_once_with(helper.USERS[role])
    assert pam.pam_start.call_args.args[:2] == (b'sshd', helper.USERS[role].encode())
    pam.pam_start_confdir.assert_not_called()
    pam.pam_open_session.assert_not_called()
    assert pam.pam_end.call_args.args[1] == status


@pytest.mark.parametrize('fault', ['positive', 'denial-worker', 'unrepaired'])
def test_installed_admission_requires_positive_and_restores_mutation_on_failure(
        admission_model, monkeypatch, fault):
    helper = admission_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'enable_diagnostics', Mock())
    accounts = {
        helper.USERS['kiosk']: SimpleNamespace(pw_uid=41001, pw_name=helper.USERS['kiosk'],
                                               pw_shell='/usr/sbin/nologin'),
        helper.USERS['ordinary']: SimpleNamespace(pw_uid=41002),
    }
    monkeypatch.setattr(helper.pwd, 'getpwnam', accounts.__getitem__)
    values = {41001: helper.DEDICATED, 41002: ('ordinary', 'wayland')}
    monkeypatch.setattr(helper, 'routing', values.__getitem__)
    writes = []

    def set_routing(uid, value):
        writes.append(value)
        values[uid] = value

    monkeypatch.setattr(helper, 'set_routing', set_routing)
    monkeypatch.setattr(helper.guest, 'run', Mock(return_value='usepam yes\npamservicename sshd'))
    monkeypatch.setattr(helper.guest, 'package_path', Mock(return_value=Path('package.deb')))
    monkeypatch.setattr(helper.Path, 'is_file', Mock(return_value=True))
    stages = []

    def probe(service, role, expected, stage, record):
        stages.append((service, role, expected, stage))
        if fault == 'positive' and stage == 'dedicated-before':
            raise helper.guest.GuestError('positive-failed')
        if stage == 'alternate-session.denied' and fault == 'denial-worker':
            raise helper.guest.GuestError('worker-failed')

    monkeypatch.setattr(helper, 'probe', probe)
    with pytest.raises(helper.guest.GuestError):
        helper.verify(Mock())
    assert values == {41001: helper.DEDICATED, 41002: ('ordinary', 'wayland')}
    if fault == 'positive':
        assert not writes
        assert not any(expected == 6 for _, _, expected, _ in stages)
    else:
        assert stages[:4] == [(service, 'ordinary', 0, service + '.ordinary-before')
                              for service in helper.SERVICES] + [
                                  ('gdm-password', 'kiosk', 0, 'dedicated-before')]
        assert writes == [('ubuntu', 'wayland'), helper.DEDICATED]
        assert not any(stage.endswith('.retry') for _, _, _, stage in stages)


@pytest.mark.parametrize('data', [b'', b'x' * 4097])
def test_pam_lifecycle_event_refuses_missing_and_oversize_protocol(census_model, data):
    helper = census_model
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, data)
        os.close(write_fd)
        write_fd = None
        with pytest.raises(helper.guest.GuestError, match='kiosk-lifecycle:event-'):
            helper.lifecycle_event(read_fd)
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)




def test_process_identity_handles_parentheses_in_comm(census_model, tmp_path):
    fields = ['S', '42'] + ['0'] * 17 + ['123']
    (tmp_path / 'stat').write_text('43 ((sd-pam)) ' + ' '.join(fields))
    (tmp_path / 'status').write_text('PPid:\t42\nUid:\t1002\t1002\t1002\t1002\n')
    assert census_model.process_identity(tmp_path) == ('123', 42, ('1002',) * 4)


@pytest.fixture
def session_model(census_model, tmp_path, monkeypatch):
    helper = census_model
    optional_service_state = helper.optional_service_state
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    account = SimpleNamespace(pw_uid=1007, pw_gid=1007, pw_shell='/usr/sbin/nologin')
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.pwd, 'getpwnam', Mock(return_value=account))
    monkeypatch.setattr(helper, 'manager_pid', Mock(return_value=41))
    monkeypatch.setattr(helper, 'session_target_state', Mock(return_value='active'))
    monkeypatch.setattr(helper, 'optional_service_state', Mock(return_value='inactive'))
    monkeypatch.setattr(helper, 'graphical_session', Mock(return_value=('c1', {
        'User': '1007', 'Type': 'wayland', 'Class': 'user', 'Service': 'gdm-password', 'State': 'active'})))
    closed = Mock()
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: 1000 + pid)
    monkeypatch.setattr(helper.os, 'close', closed)
    monkeypatch.setattr(helper, 'exited', Mock(return_value=False))
    units = {helper.SESSION_TARGET: {
        'ActiveState': 'active', 'InvocationID': '', 'MainPID': '0', 'ControlGroup': ''}}
    for index, (role, name) in enumerate(helper.SERVICES.items(), 42):
        active = role in ('app', 'compositor')
        units[name] = {'ActiveState': 'active' if active else 'inactive',
                       'InvocationID': 'a' * 32 if active else '', 'MainPID': str(index) if active else '0',
                       'ControlGroup': '/user.slice/' + role if active else ''}
    monkeypatch.setattr(helper, 'user_unit', lambda account, name: dict(units[name]))
    for pid, cgroup in ((41, ''), (42, '/user.slice/compositor'), (43, '/user.slice/app')):
        process = tmp_path / str(pid)
        process.mkdir()
        fields = ['S', '1'] + ['0'] * 17 + [str(pid * 100)]
        (process / 'stat').write_text(str(pid) + ' (worker) ' + ' '.join(fields))
        (process / 'status').write_text('PPid:\t1\nUid:\t1007\t1007\t1007\t1007\n')
        (process / 'cgroup').write_text('0::' + cgroup + '\n')
    return SimpleNamespace(helper=helper, account=account, units=units, closed=closed, proc=tmp_path,
                           optional_service_state=optional_service_state)


def test_session_census_observes_current_services_without_optional_feature_veto(session_model):
    model = session_model
    result = model.helper.census()
    assert result == {'scope': 'session-identity-only', 'confinement_qualified': False,
        'session': {'type': 'wayland', 'class': 'user', 'service': 'gdm-password', 'state': 'active'},
        'services': {'compositor': {'active_state': 'active', 'identity_observed': True},
                     'app': {'active_state': 'active', 'identity_observed': True},
                     'polkit': {'active_state': 'inactive', 'identity_observed': False},
                     'notifications': {'active_state': 'inactive', 'identity_observed': False}}}
    assert {call.args[0] for call in model.closed.call_args_list} == {1041, 1042, 1043}


@pytest.mark.parametrize('state', ['unavailable', 'activating', 'deactivating', 'failed', 'active'])
def test_optional_provider_transition_never_gates_or_rechecks_core_session(session_model, state):
    model = session_model
    model.helper.optional_service_state.return_value = state
    result = model.helper.census()
    assert result['services']['polkit'] == {'active_state': state, 'identity_observed': False}
    assert result['services']['notifications'] == {'active_state': state, 'identity_observed': False}
    assert model.helper.optional_service_state.call_count == 2
    assert {call.args[0] for call in model.closed.call_args_list} == {1041, 1042, 1043}


@pytest.mark.parametrize('failure', [
    subprocess.TimeoutExpired(['systemctl'], 3),
    OSError('optional service unavailable'),
    UnicodeError('invalid optional telemetry'),
])
def test_optional_service_query_has_short_deadline_and_absorbs_unavailable_telemetry(
        census_model, monkeypatch, failure):
    helper = census_model
    account = SimpleNamespace(pw_uid=1007, pw_gid=1007)
    command = Mock(side_effect=failure)
    monkeypatch.setattr(helper.guest.commands, 'run', command)
    assert helper.optional_service_state(account, helper.SERVICES['polkit']) == 'unavailable'
    assert command.call_args.kwargs == {'check': False, 'timeout': 3, 'merge_stderr': False}
    assert command.call_args.args[0][-1] == helper.SERVICES['polkit']


def test_optional_query_timeout_preserves_core_session_result_and_closes_descriptors(
        session_model, monkeypatch):
    model = session_model
    monkeypatch.setattr(model.helper, 'optional_service_state', model.optional_service_state)
    command = Mock(side_effect=subprocess.TimeoutExpired(['systemctl'], 3))
    monkeypatch.setattr(model.helper.guest.commands, 'run', command)
    result = model.helper.census()
    assert result['services']['app']['identity_observed'] is True
    assert result['services']['compositor']['identity_observed'] is True
    for role in ('polkit', 'notifications'):
        assert result['services'][role] == {'active_state': 'unavailable', 'identity_observed': False}
    assert command.call_count == 2
    assert all(call.kwargs['timeout'] == 3 for call in command.call_args_list)
    assert {call.args[0] for call in model.closed.call_args_list} == {1041, 1042, 1043}


@pytest.mark.parametrize('fault', ['account', 'manager-uid', 'app-inactive', 'app-uid',
                                   'app-cgroup', 'missing-invocation', 'manager-replaced', 'app-replaced'])
def test_session_census_refuses_wrong_owners_and_lifecycle_changes(session_model, fault):
    model = session_model
    helper = model.helper
    if fault == 'account':
        model.account.pw_shell = '/bin/bash'
    elif fault in ('manager-uid', 'app-uid'):
        pid = '41' if fault == 'manager-uid' else '43'
        (model.proc / pid / 'status').write_text('PPid:\t1\nUid:\t0\t0\t0\t0\n')
    elif fault == 'app-cgroup':
        (model.proc / '43/cgroup').write_text('0::/other.service\n')
    elif fault == 'app-inactive':
        model.units[helper.SERVICES['app']]['ActiveState'] = 'inactive'
    elif fault == 'missing-invocation':
        model.units[helper.SERVICES['app']]['InvocationID'] = '0' * 32
    elif fault == 'app-replaced':
        compositor = model.units[helper.SERVICES['compositor']]
        app = model.units[helper.SERVICES['app']]
        helper.user_unit = Mock(side_effect=[dict(compositor), dict(app), dict(compositor),
                                            {**app, 'InvocationID': 'b' * 32}])
    else:
        helper.manager_pid.side_effect = [41, 99]
    with pytest.raises(helper.guest.GuestError, match='kiosk-session:'):
        helper.census()
    if fault != 'account':
        assert 1041 in {call.args[0] for call in model.closed.call_args_list}
    if fault == 'app-replaced':
        assert {call.args[0] for call in model.closed.call_args_list} == {1041, 1042, 1043}


@pytest.mark.parametrize('fault', ['none', 'ambiguous', 'wrong-transport', 'wrong-user'])
def test_graphical_session_binds_one_current_wayland_station(census_model, monkeypatch, fault):
    helper = census_model
    account = SimpleNamespace(pw_uid=1007)
    sessions = 'c1 1007 station seat0 tty2 active\n'
    if fault == 'none':
        sessions = 'c2 1008 other seat0 tty3 active\n'
    elif fault == 'ambiguous':
        sessions += 'c2 1007 station seat0 tty3 active\n'
    values = {'User': '1008' if fault == 'wrong-user' else '1007',
              'Type': 'x11' if fault == 'wrong-transport' else 'wayland',
              'Class': 'user', 'Service': 'gdm-password', 'State': 'active'}
    command = Mock(side_effect=[sessions, '\n'.join(key + '=' + value for key, value in values.items())])
    monkeypatch.setattr(helper.guest, 'run', command)
    with pytest.raises(helper.guest.GuestError, match='kiosk-session:'):
        helper.graphical_session(account)
    assert command.call_count == (1 if fault in ('none', 'ambiguous') else 2)


@pytest.mark.parametrize('rows', ['User=1007\nUser=1008', 'User=1007\nOther=value', 'invalid'])
def test_observer_refuses_duplicate_missing_and_malformed_properties(census_model, rows):
    with pytest.raises(census_model.guest.GuestError, match='invalid-properties'):
        census_model.properties(rows, ('User',))


def test_composition_uses_current_entry_and_distro_pam_without_starting_a_manager(
        census_model, monkeypatch):
    helper = census_model
    from configparser import ConfigParser
    parser = ConfigParser()
    parser.read_string('[GNOME Session]\nKiosk=true\n')
    account = SimpleNamespace(pw_uid=1007, pw_shell='/usr/sbin/nologin')
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.pwd, 'getpwnam', Mock(return_value=account))
    monkeypatch.setattr(helper.guest, 'package_path', lambda: Path('package.deb'))
    import system_kiosk_admission as admission
    monkeypatch.setattr(admission, 'routing', lambda uid: admission.DEDICATED)
    command = Mock()
    monkeypatch.setattr(helper.guest, 'run', command)
    sections = {
        'Desktop Entry': {'Exec': 'gnome-session --session oh-no-parent-control', 'TryExec': 'gnome-session'},
        'GNOME Session': parser['GNOME Session'],
        'Service': {'ExecStart': '/usr/bin/oh-no-parent-control'},
    }
    monkeypatch.setattr(helper, 'installed_configuration', lambda path, section: sections[section])
    record = Mock()
    assert helper.verify_session_composition(record) == (account, 'apparmor')
    command.assert_called_once_with(['/usr/libexec/oh-no-parent-control-distro-pam',
        '--distribution', 'ubuntu', 'verify'], timeout=45)
    assert json.loads(record.call_args.args[1])['confinement_qualified'] is False
