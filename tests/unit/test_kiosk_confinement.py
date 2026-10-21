"""Private confinement lifecycle machines; no host PAM or kernel policy changes."""
import importlib.util
import hashlib
import json
import fcntl
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

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


@pytest.mark.parametrize('fault', [None, 'collision', 'link', 'wrong-copy',
                                  'changed-fragment', 'body-failure'])
def test_copied_probe_trust_preserves_foreign_inputs_and_cleans_owned_entries(
        census_model, tmp_path, monkeypatch, fault):
    import system_enforcement
    helper = census_model
    directory = tmp_path / 'onpc-confinement-input-private'
    directory.mkdir()
    copied = directory / 'copied-systemctl'
    copied.write_bytes(b'copied native executable')
    copied.chmod(0o755)
    trust_directory = tmp_path / 'trust.d'
    trust_directory.mkdir()
    fragment = trust_directory / ('onpc-system-' + directory.name + '-' + copied.name + '.trust')
    monkeypatch.setattr(helper, 'PROBE_TRUST_DIRECTORY', trust_directory)
    monkeypatch.setattr(helper.guest, 'guard', lambda: None)
    digest = hashlib.sha256(copied.read_bytes()).hexdigest()
    monkeypatch.setattr(helper.guest, 'sha', lambda path: (
        'wrong' if fault == 'wrong-copy' and path == Path('/usr/bin/systemctl') else digest))
    native_lstat = Path.lstat

    def metadata(path, *args, **kwargs):
        info = native_lstat(path, *args, **kwargs)
        if path in trust_directory.parents or path in (trust_directory, fragment):
            return SimpleNamespace(st_uid=0, st_mode=info.st_mode & ~0o022,
                st_nlink=info.st_nlink, st_dev=info.st_dev, st_ino=info.st_ino,
                st_size=info.st_size)
        return info

    monkeypatch.setattr(Path, 'lstat', metadata)
    waits = []
    monkeypatch.setattr(system_enforcement, 'TrustRefreshDiagnostic', lambda: 'diagnostic')
    monkeypatch.setattr(system_enforcement, 'TrustRefreshCompletion', lambda: SimpleNamespace(
        wait=lambda deadline, diagnostic: waits.append(diagnostic)))
    calls = []

    def run(command):
        calls.append(command)
        if command[:3] == ['fapolicyd-cli', '--file', 'add']:
            with fragment.open('x') as stream:
                stream.write(f'{copied} {copied.stat().st_size} {digest}\n')
        return ''

    monkeypatch.setattr(helper.guest, 'run', run)
    if fault == 'collision':
        fragment.write_text('foreign trust entries')
    elif fault == 'link':
        fragment.symlink_to(tmp_path / 'foreign')
    reason = {'collision': 'trust-collision', 'link': 'trust-collision',
              'wrong-copy': 'probe-copy-digest', 'changed-fragment': 'trust-fragment-changed'}

    def exercise():
        with helper.trusted_probe_copy(copied, 'selinux'):
            assert fragment.exists()
            assert waits == ['diagnostic']
            if fault == 'changed-fragment':
                fragment.write_text('foreign replacement entries')
            elif fault == 'body-failure':
                raise RuntimeError('original assertion failure')

    if fault in reason:
        with pytest.raises(helper.guest.GuestError, match='kiosk-input:' + reason[fault]):
            exercise()
    elif fault == 'body-failure':
        with pytest.raises(RuntimeError, match='original assertion failure'):
            exercise()
    else:
        exercise()
    if fault in ('collision', 'link', 'wrong-copy'):
        assert calls == []
    elif fault == 'changed-fragment':
        assert fragment.read_text() == 'foreign replacement entries'
        assert waits == ['diagnostic']
    else:
        assert not fragment.exists()
        assert waits == ['diagnostic', 'diagnostic']
        assert calls == [
            ['fapolicyd-cli', '--file', 'add', str(copied), '--trust-file', fragment.name],
            ['restorecon', str(fragment)], ['fapolicyd-cli', '--update'],
            ['fapolicyd-cli', '--update']]


@pytest.mark.parametrize('fault', [None, 'inode', 'owner', 'bytes', 'mode'])
def test_required_ancestor_restoration_preserves_foreign_inputs(census_model, tmp_path, monkeypatch, fault):
    import system_native_update
    helper = census_model
    path = tmp_path / 'required'
    path.mkdir()
    executable = path / 'systemd'
    executable.write_bytes(b'original native canary')
    monkeypatch.setattr(helper, 'REQUIRED_ANCESTOR', path)
    monkeypatch.setattr(helper, 'REQUIRED_EXECUTABLE', executable)
    monkeypatch.setattr(helper.guest, 'guard', lambda: None)
    original = helper.required_ancestor_state()
    checkpoint = tmp_path / 'required-ancestor.json'
    checkpoint.write_text('{}')
    monkeypatch.setattr(system_native_update, 'private', lambda: tmp_path)
    monkeypatch.setattr(helper, 'required_ancestor_checkpoint', lambda: {'original': original, 'ordinary': {}})
    monkeypatch.setattr(helper, 'required_ordinary_access', lambda expected: None)
    published = []
    monkeypatch.setattr(system_native_update, 'publish', lambda *args: published.append(args))
    path.chmod(stat.S_IMODE(original['identity'][2]) | 0o020)
    if fault == 'inode':
        path.rename(tmp_path / 'original')
        path.mkdir()
        (path / 'systemd').write_bytes(b'original native canary')
    elif fault == 'owner':
        original['identity'][3] += 1
    elif fault == 'bytes':
        executable.write_bytes(b'foreign bytes')
    elif fault == 'mode':
        path.chmod(0o777)
    before = helper.required_ancestor_state()
    if fault:
        with pytest.raises(helper.guest.GuestError, match='restoration-identity'):
            helper.restore_required_ancestor()
        assert helper.required_ancestor_state() == before
        assert not published
    else:
        helper.restore_required_ancestor()
        assert helper.required_ancestor_state() == original
        assert published[0][0] == 'required-restored.json'


@pytest.mark.parametrize('fault', [False, True])
def test_appended_probe_restores_bytes_inode_mode_and_nanosecond_times(
        census_model, tmp_path, fault):
    path = tmp_path / 'package-input'
    path.write_bytes(b'original package bytes')
    path.chmod(0o640)
    os.utime(path, ns=(1_600_000_000_123_456_789, 1_600_000_001_987_654_321))
    before = path.stat()

    def exercise():
        with census_model.appended_probe(path, b'\nowned fault\n'):
            assert path.read_bytes() == b'original package bytes\nowned fault\n'
            if fault:
                raise RuntimeError('probe failed')

    if fault:
        with pytest.raises(RuntimeError, match='probe failed'):
            exercise()
    else:
        exercise()
    after = path.stat()
    for field in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid',
                  'st_size', 'st_atime_ns', 'st_mtime_ns'):
        assert getattr(after, field) == getattr(before, field)
    assert path.read_bytes() == b'original package bytes'


def test_appended_probe_refuses_symlink_without_changing_target(census_model, tmp_path):
    target = tmp_path / 'foreign'
    target.write_bytes(b'preserved bytes')
    path = tmp_path / 'package-input'
    path.symlink_to(target)
    with pytest.raises(OSError):
        with census_model.appended_probe(path, b'\nfault\n'):
            pytest.fail('symlink admitted')
    assert path.is_symlink() and target.read_bytes() == b'preserved bytes'


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
    guard.assert_called_once_with(expected_selinux='Enforcing')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('service,role', [('gdm-password', 'ordinary'),
                                         ('login', 'kiosk'), ('sshd', 'kiosk')])
def test_other_fedora_account_probes_preserve_the_original_caller_command(
        admission_model, monkeypatch, service, role):
    helper = admission_model
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


@pytest.mark.parametrize('service,context,label', [
    ('gdm-password', 'system_u:system_r:xdm_t:s0', 'xdm_exec_t'),
    ('systemd-user', 'system_u:system_r:init_t:s0', 'init_exec_t'),
])
@pytest.mark.parametrize('fault', [None, 'command', 'missing-result', 'empty-result', 'diagnostic-capacity'])
def test_final_pam_probe_enters_real_vendor_caller_without_policy_changes(
        census_model, tmp_path, monkeypatch, capfd, service, context, label, fault):
    from unittest.mock import Mock
    helper = census_model
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    original_read = Path.read_text
    original_is_file = Path.is_file
    def read(path, *args, **kwargs):
        if str(path) == '/usr/share/oh-no-parent-control/confinement/config.json':
            return '{"backend":"selinux"}'
        if str(path) == '/proc/self/attr/current':
            return 'unconfined_u:unconfined_r:unconfined_t:s0\0'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(Path, 'is_file', lambda path: (
        str(path) == '/usr/lib64/security/pam_oh_no_parent_control.so'
        if path.name == 'pam_oh_no_parent_control.so' else original_is_file(path)))
    monkeypatch.setattr(helper.shutil, 'copyfile',
                        lambda source, target: target.write_bytes(b'private interpreter fixture'))
    run = Mock()
    monkeypatch.setattr(helper.guest, 'run', run)
    commands = Mock()
    monkeypatch.setattr(helper.guest, 'commands', commands)
    channels = []
    original_pipe = helper.os.pipe2
    def pipe(flags):
        descriptors = original_pipe(flags)
        channels.extend(descriptors)
        return descriptors
    monkeypatch.setattr(helper.os, 'pipe2', pipe)
    diagnostic = b'original native refusal\n'
    diagnostic_size = len(diagnostic)
    def enter(argv, **kwargs):
        nonlocal diagnostic_size
        assert argv[:2] == ['/usr/bin/runcon', context]
        caller = Path(argv[2])
        assert caller.is_relative_to(tmp_path) and caller.stat().st_mode & 0o777 == 0o700
        assert run.call_args.args[0] == ['/usr/bin/chcon', '-t', label, str(caller)]
        request = json.loads(argv[-1])
        result_fd = request.pop('result_fd')
        diagnostic_fd = request.pop('diagnostic_fd')
        assert diagnostic_fd != result_fd
        assert not os.get_blocking(diagnostic_fd)
        assert not os.get_inheritable(diagnostic_fd)
        assert not os.get_inheritable(result_fd)
        assert request == {'command': ['/usr/bin/true'], 'directory': str(tmp_path),
                           'service': service, 'armed': True, 'fd_mode': 'file',
                           'expected_selinux': 'Enforcing'}
        assert kwargs == {'timeout': 90, 'merge_stderr': False,
                          'pass_fds': (result_fd, diagnostic_fd)}
        os.write(diagnostic_fd, diagnostic)
        if fault == 'diagnostic-capacity':
            # Filling the actual pipe must return EAGAIN, never block while
            # the parent waits for its finite caller command to finish.
            for _ in range(257):
                try:
                    diagnostic_size += os.write(diagnostic_fd, b'x' * 4096)
                except BlockingIOError:
                    break
            else:
                pytest.fail('diagnostic channel did not reach its finite capacity')
        assert (tmp_path / service).read_text() == (
            'session required /usr/lib64/security/pam_oh_no_parent_control.so kiosk-confinement\n')
        if fault == 'command':
            raise helper.guest.GuestError('command:failed:runcon')
        if fault == 'empty-result':
            return b''
        os.write(result_fd, b'help output' if fault == 'missing-result' else
                 b'onpc-first-exec:{"status":126,"data":"7b7d"}')
        return b'caller stdout must stay private\n'
    commands.run.side_effect = enter
    if fault in ('command', 'missing-result', 'empty-result'):
        with pytest.raises(helper.guest.GuestError):
            helper.first_exec(SimpleNamespace(), tmp_path, ['/usr/bin/true'],
                              service=service, fd_mode='file')
    elif fault == 'diagnostic-capacity':
        try:
            result = helper.first_exec(SimpleNamespace(), tmp_path, ['/usr/bin/true'],
                                       service=service, fd_mode='file')
        except helper.guest.GuestError as error:
            assert diagnostic_size > 65536
            assert str(error) == 'kiosk-confinement:caller-diagnostic-size'
        else:
            assert diagnostic_size <= 65536
            assert result == (126, b'{}')
    else:
        assert helper.first_exec(SimpleNamespace(), tmp_path, ['/usr/bin/true'],
                                 service=service, fd_mode='file') == (126, b'{}')
    captured = capfd.readouterr()
    assert captured.out == ''
    if fault == 'diagnostic-capacity':
        if diagnostic_size > 65536:
            assert captured.err == ''
        else:
            assert captured.err.startswith(diagnostic.decode())
            assert set(captured.err[len(diagnostic):]) == {'x'}
    else:
        assert captured.err == diagnostic.decode()
    assert len(channels) == 4
    for descriptor in channels:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert list(tmp_path.iterdir()) == [tmp_path / service]


@pytest.mark.parametrize('service,gid', [('gdm-password', 41002), ('systemd-user', 0)])
@pytest.mark.parametrize('pam_status', [0, 7])
def test_first_exec_caller_credentials_and_receipt_precede_native_pam(
        census_model, tmp_path, monkeypatch, service, gid, pam_status):
    """Credential doubles prove order; installed probes own actual vendor IDs."""
    import ctypes
    helper = census_model
    events = []
    account = SimpleNamespace(pw_name='private-kiosk', pw_gid=41002)
    status = tmp_path / 'self/status'
    status.parent.mkdir()
    status.write_text('Uid:\t0 0 0 0\nGid:\t' + ' '.join([str(gid)] * 4) + '\nUmask:\t0022\n')
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    monkeypatch.setattr(helper.os, 'setgroups', lambda groups: events.append(('groups', groups)))
    monkeypatch.setattr(helper.os, 'setgid', lambda value: events.append(('gid', value)))
    monkeypatch.setattr(helper.os, 'umask', lambda value: events.append(('umask', value)))
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        def start(*args):
            assert events == [('groups', []), ('gid', gid), ('umask', 0o022)]
            with pytest.raises(BlockingIOError):
                os.read(read_fd, 4096)
            events.append(('start', service))
            return 0
        def opened(handle, flags):
            receipt = json.loads(os.read(read_fd, 4096))
            assert receipt == {'phase': 'caller', 'pid': os.getpid(),
                'context': {'uid': [0] * 4, 'gid': [gid] * 4, 'umask': 0o022}}
            events.append(('open', service))
            return pam_status
        pam = SimpleNamespace(pam_start_confdir=start, pam_open_session=opened)
        assert helper.first_exec_pam_session(pam, ctypes.c_void_p(), ctypes.c_void_p(),
            tmp_path, account, service, {'events': write_fd}) == pam_status
        assert events[-2:] == [('start', service), ('open', service)]
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.parametrize('field,value', [('uid', [0, 0, 0, 1]), ('gid', [0, 0, 0, 41002]),
                                        ('gid', [41002, 41002, 41002, 0]), ('umask', 0o777)])
def test_first_exec_caller_rejects_wrong_filesystem_credentials_before_pam(
        census_model, monkeypatch, field, value):
    helper = census_model
    context = {'uid': [0] * 4, 'gid': [41002] * 4, 'umask': 0o022}
    context[field] = value
    with pytest.raises(helper.guest.GuestError, match='pre-pam-credentials'):
        helper.first_exec_validate_context(context, SimpleNamespace(pw_gid=41002), 'gdm-password')


def test_first_exec_pidfd_failure_reaps_its_own_child_and_closes_pipe(census_model, monkeypatch):
    import signal

    helper = census_model
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(read_fd)
        os.close(write_fd)
        signal.pause()
        os._exit(0)
    os.close(write_fd)
    try:
        def unavailable(pid):
            assert pid == child
            raise OSError('pidfd unavailable')
        monkeypatch.setattr(helper.os, 'pidfd_open', unavailable)
        with pytest.raises(OSError, match='pidfd unavailable'):
            helper.wait_first_exec(child, read_fd, armed=True)
        with pytest.raises(ChildProcessError):
            os.waitpid(child, os.WNOHANG)
        with pytest.raises(OSError):
            os.fstat(read_fd)
    finally:
        # Only this test's unreaped fork child can still own this PID.
        try:
            waited, _ = os.waitpid(child, os.WNOHANG)
        except ChildProcessError:
            waited = child
        if waited == 0:
            os.kill(child, signal.SIGKILL)
            os.waitpid(child, 0)
        try:
            os.close(read_fd)
        except OSError:
            pass


def test_final_pam_probe_refuses_unknown_caller(census_model):
    helper = census_model
    with pytest.raises(helper.guest.GuestError, match='unsupported-pam-caller'):
        helper.caller_identity('sshd')


@pytest.mark.parametrize('fault', [None, 'close', 'label'])
def test_pam_lifecycle_teardown_retains_denials_after_real_callback_order(census_model, monkeypatch, fault):
    helper = census_model
    calls = []
    def callback(name, result=0):
        def run(handle, flags):
            calls.append((name, handle, flags))
            return result
        return run
    pam = SimpleNamespace(pam_close_session=callback('close', 1 if fault == 'close' else 0),
                          pam_setcred=callback('credentials', 7), pam_end=callback('end'))
    expected = 'system_u:system_r:onpc_kiosk_manager_pam_t:s0'
    monkeypatch.setattr(helper, 'lifecycle_label', lambda backend: 'init_t' if fault == 'label' else expected)
    denials = []
    monkeypatch.setattr(helper, 'lifecycle_denials', lambda: denials.append(len(calls)))
    if fault == 'label':
        with pytest.raises(helper.guest.GuestError, match='kiosk-lifecycle:'):
            helper.lifecycle_teardown(pam, 'handle', 'selinux', expected)
        assert not any(call[0] == 'end' for call in calls)
    else:
        stages = helper.lifecycle_teardown(pam, 'handle', 'selinux', expected)
        assert calls == [('close', 'handle', 0), ('credentials', 'handle', 4),
                         ('end', 'handle', 0x40000000)]
        assert denials == [0, 1, 2, 3]
        assert stages[1]['pam_status'] == (1 if fault == 'close' else 0)
        assert stages[2] == {'stage': 'delete-credentials', 'pam_status': 7}


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


def test_pam_lifecycle_denial_workers_reap_and_validate_exec_errno(census_model, monkeypatch):
    helper = census_model
    def denied(*args):
        raise PermissionError(13, 'private exec denial')
    monkeypatch.setattr(helper.os, 'execve', denied)
    helper.lifecycle_denials()


def test_pam_lifecycle_generation_diagnostic_records_bounded_system_path_differences(
        census_model, tmp_path, monkeypatch):
    import system_kiosk_accounts as accounts

    helper = census_model
    runtime = tmp_path / 'runtime'
    runtime.mkdir(mode=0o700)
    before, after = 'a' * 64, 'b' * 64
    manifests = {
        before: {'records': [{'path': '/usr/bin/required', 'sha256': 'before'}],
                 'preserved': [{'path': '/usr/lib/polkit-1/helper'}],
                 'layout': [{'path': '/usr/lib/removed-' + str(index), 'kind': 'file'}
                            for index in range(10)] +
                           [{'path': '/usr/lib/changed-' + str(index), 'kind': 'file'}
                            for index in range(10)]},
        after: {'records': [{'path': '/usr/bin/required', 'sha256': 'after'}],
                'preserved': [],
                'layout': [{'path': '/usr/lib/added-' + str(index), 'kind': 'directory'}
                           for index in range(10)] +
                          [{'path': '/usr/lib/changed-' + str(index), 'kind': 'directory'}
                           for index in range(10)]},
    }
    for generation, manifest in manifests.items():
        directory = runtime / generation
        directory.mkdir()
        (directory / 'records.json').write_text(json.dumps(manifest))

    def trusted(path, **options):
        return path if path.is_relative_to(runtime) else (
            runtime / path.relative_to('/run/oh-no-parent-control-confinement'))

    monkeypatch.setattr(helper.runpy, 'run_path', Mock(return_value={'trusted': trusted}))
    reader = Mock(side_effect=lambda path, **options: path.read_bytes())
    monkeypatch.setattr(accounts, 'owned_bytes', reader)
    events = {}
    helper.lifecycle_generation_diagnostic(before + '\n', after + '\n', events.__setitem__)
    assert events['onpc.kiosk.pam-lifecycle.manager-generation'] == before
    assert events['onpc.kiosk.pam-lifecycle.helper-generation'] == after
    result = json.loads(events['onpc.kiosk.pam-lifecycle.generation-diagnostic'])
    assert result['status'] == 'compared'
    assert result['records']['changed'] == {'count': 1, 'paths': ['/usr/bin/required']}
    assert result['preserved']['removed'] == {'count': 1, 'paths': ['/usr/lib/polkit-1/helper']}
    for change in ('added', 'removed', 'changed'):
        assert result['layout'][change]['count'] == 10
        assert len(result['layout'][change]['paths']) == 8
        assert all(path.startswith('/usr/') for path in result['layout'][change]['paths'])
    assert all(call.kwargs == {'private': True} for call in reader.call_args_list)


@pytest.mark.parametrize('fault', [None, 'waiting-label', 'finished', 'credential-status',
                                  'establish-status', 'invalid-generation', 'diagnostic-read'])
def test_pam_lifecycle_observer_pins_and_reaps_owned_executor_and_orphan(
        census_model, tmp_path, monkeypatch, fault):
    helper = census_model
    observer = os.getpid()
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: observer)
    # This existing plain-stack fixture declares no optional LXC callback.
    monkeypatch.setattr(helper, 'optional_cgfs_session', lambda backend: False)
    original_read = Path.read_text
    expected = 'onpc-kiosk-manager (enforce)'
    def read(path, *args, **kwargs):
        if path.name == 'current' and 'attr' in path.parts:
            return 'unconfined' if fault == 'waiting-label' else expected
        if path.name == 'generation':
            if fault in ('invalid-generation', 'diagnostic-read'):
                if str(observer) in path.parts:
                    return 'a' * 64 + '\n'
                return '../outside-runtime\n' if fault == 'invalid-generation' else 'b' * 64 + '\n'
            return 'private generation'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(helper.shutil, 'copyfile', lambda source, target: target.write_bytes(b'private executor'))
    diagnostic_source = Mock(side_effect=OSError('private diagnostic read failure'))
    if fault in ('invalid-generation', 'diagnostic-read'):
        monkeypatch.setattr(helper.runpy, 'run_path', diagnostic_source)
    # Keep the real observer/forks, PIDFDs, subreaper, pipe protocol, identity
    # checks and cleanup. The fixture replaces only the vendor/PAM executor.
    def executor(program, arguments, environment):
        request = json.loads(arguments[-1])
        child = os.fork()
        if child == 0:
            os.close(request['executor_release'])
            try:
                os.write(request['events'], (json.dumps({'phase': 'ready', 'pid': os.getpid(),
                    'parent': os.getppid()}) + '\n').encode())
                if os.read(request['helper_release'], 1) != b'T':
                    os._exit(1)
                stages = [{'stage': stage, 'pam_status': None if index == 0 else
                           7 if fault == 'credential-status' and index == 2 else 0}
                          for index, stage in enumerate(('parent-exited', 'close-session',
                                                        'delete-credentials', 'end'))]
                result = {'phase': 'finished', 'stages': stages,
                          'establish_status': 7 if fault == 'establish-status' else 0}
                if fault == 'finished':
                    result['stages'] = []
                os.write(request['events'], (json.dumps(result) + '\n').encode())
                os._exit(0)
            except BaseException:
                os._exit(124)
        os.close(request['helper_release'])
        os._exit(0 if os.read(request['executor_release'], 1) == b'E' else 1)
    monkeypatch.setattr(helper.os, 'execve', executor)
    events = []
    account = SimpleNamespace(pw_uid=os.getuid())
    if fault:
        category = ('kiosk-lifecycle:waiting-generation' if fault in (
            'invalid-generation', 'diagnostic-read') else 'kiosk-lifecycle:')
        with pytest.raises(helper.guest.GuestError, match=category):
            helper.verify_pam_lifecycle(account, 'private-unit', 'apparmor', tmp_path,
                                       lambda *event: events.append(event))
    else:
        helper.verify_pam_lifecycle(account, 'private-unit', 'apparmor', tmp_path,
                                   lambda *event: events.append(event))
        assert ('onpc.kiosk.pam-lifecycle.establish-credentials-status', 0) in events
        assert events[-1] == ('onpc.kiosk.pam-lifecycle.post-parent-close-setcred-end-denials', True)
    if fault in ('credential-status', 'establish-status'):
        # Boundary evidence is retained, while a failed delete callback still
        # refuses completed teardown qualification.
        assert events[-1] == ('onpc.kiosk.pam-lifecycle.post-parent-close-setcred-end-denials', True)
    if fault in ('invalid-generation', 'diagnostic-read'):
        assert events[-1] == ('onpc.kiosk.pam-lifecycle.generation-diagnostic',
                              '{"status":"unavailable"}')
        assert diagnostic_source.call_count == (fault == 'diagnostic-read')


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('permissive', [False, True])
def test_waiting_census_requires_enforcing_policy_without_a_password_helper(
        census_model, monkeypatch, backend, permissive):
    helper = census_model
    config = {'backend': backend}
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(pw_uid=1002)))
    monkeypatch.setattr(helper.Path, 'read_text', Mock(return_value=json.dumps(config)))
    failure = 'selinux-domain-not-enforcing' if backend == 'selinux' else 'apparmor-not-enforcing'
    enforcing = Mock(side_effect=ValueError(failure) if permissive else None)
    load = Mock(return_value={'enforcing': enforcing})
    monkeypatch.setattr(helper.runpy, 'run_path', load)
    manager = Mock(return_value=42)
    monkeypatch.setattr(helper, 'manager_pid', manager)
    opened = Mock(return_value=43)
    closed = Mock()
    monkeypatch.setattr(helper.os, 'pidfd_open', opened)
    monkeypatch.setattr(helper.os, 'close', closed)
    processes = Mock(return_value={'backend': backend})
    monkeypatch.setattr(helper, 'census_processes', processes)
    if permissive:
        with pytest.raises(ValueError, match=failure):
            helper.census()
        manager.assert_not_called()
        opened.assert_not_called()
        processes.assert_not_called()
        closed.assert_not_called()
    else:
        assert helper.census() == {'backend': backend}
        processes.assert_called_once()
        closed.assert_called_once_with(43)
    load.assert_called_once_with('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    enforcing.assert_called_once_with(config)


def test_census_stat_parser_handles_parentheses_in_comm(census_model, tmp_path):
    helper = census_model
    fields = ['S', '42'] + ['0'] * 17 + ['123']
    (tmp_path / 'stat').write_text('43 ((sd-pam)) ' + ' '.join(fields))
    (tmp_path / 'status').write_text('PPid:\t42\nUid:\t1002\t1002\t1002\t1002\n')
    assert helper.process_identity(tmp_path) == ('123', 42, ('1002',) * 4)


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'unconfined', 'old-pam-domain', 'process-replaced',
                                    'manager-replaced', 'root-leader-kiosk-thread', 'other-process-changed'])
def test_census_filters_other_users_but_checks_every_kiosk_process(
        census_model, tmp_path, monkeypatch, backend, fault):
    from types import SimpleNamespace
    helper = census_model
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    marker = 'root/usr/share/oh-no-parent-control/confinement/generation'
    roles = ['manager', 'app', 'service', 'wellbeing', 'pipewire', 'manager-pam']
    for pid, role in [(1, None), *enumerate(roles, 42)]:
        process = tmp_path / str(pid)
        process.mkdir()
        uid = '0' if role is None else '1002'
        fields = ['S', '1'] + ['0'] * 17 + [str(pid * 100)]
        (process / 'stat').write_text(f'{pid} (fixture) ' + ' '.join(fields))
        (process / 'status').write_text('PPid:\t1\nUid:\t' + '\t'.join([uid] * 4) + '\n')
        (process / 'ns').mkdir()
        (process / 'ns/mnt').symlink_to('mnt:[host]' if role is None else 'mnt:[private]')
        thread = process / 'task' / str(pid)
        thread.mkdir(parents=True)
        for name in ('stat', 'status', 'ns', 'root'):
            (thread / name).symlink_to(process / name)
        if role is None:
            if fault == 'root-leader-kiosk-thread':
                sibling = process / 'task/2'
                sibling.mkdir()
                (sibling / 'stat').symlink_to(process / 'stat')
                (sibling / 'status').write_text('PPid:\t1\nUid:\t1002\t1002\t1002\t1002\n')
            continue  # No readable root/labels: these must never be requested.
        (process / marker).parent.mkdir(parents=True)
        (process / marker).write_text('fixture generation')
        (process / 'cgroup').write_text('0::/user.slice/user-1002.slice/user@1002.service/init.scope')
        name = 'onpc-kiosk-' + role if backend == 'apparmor' else 'onpc_kiosk_' + role.replace('-', '_') + '_t'
        label = name + ' (enforce)' if backend == 'apparmor' else f'system_u:system_r:{name}:s0'
        if fault == 'unconfined' and role == 'pipewire':
            label = 'unconfined'
        if fault == 'old-pam-domain' and role == 'manager-pam':
            label = 'unconfined' if backend == 'apparmor' else 'system_u:system_r:init_t:s0'
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        for target in (attribute, f'task/{pid}/{attribute}'):
            (process / target).parent.mkdir(parents=True)
            (process / target).write_text(label)
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: pid)
    monkeypatch.setattr(helper.os, 'close', lambda fd: None)
    monkeypatch.setattr(helper, 'exited', lambda fd: False)
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: 99 if fault == 'manager-replaced' else 42)
    identity = helper.process_identity
    reads = {}
    def read_identity(path):
        value = identity(path)
        reads[path] = reads.get(path, 0) + 1
        changed = ((fault == 'process-replaced' and path.name == '43') or
                   (fault == 'other-process-changed' and path.name == '1'))
        return ('changed', *value[1:]) if changed and reads[path] > 1 else value
    monkeypatch.setattr(helper, 'process_identity', read_identity)
    def check():
        return helper.census_processes(SimpleNamespace(pw_uid=1002),
            {'apparmor_profiles': ['onpc-kiosk-' + role for role in roles], 'domains': roles},
            backend, tmp_path / '42', 42, 'user@1002.service', required_roles=roles)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-census:'):
            check()
    else:
        result = check()
        assert result['confined_thread_roles'] == {
            ('onpc-kiosk-' + role if backend == 'apparmor' else
             'onpc_kiosk_' + role.replace('-', '_') + '_t'): 1 for role in roles}


@pytest.fixture
def password_helper_census(census_model, tmp_path, monkeypatch):
    helper = census_model
    proc = tmp_path / 'proc'
    proc.mkdir()
    monkeypatch.setattr(helper, 'PROC', proc)
    generation = 'a' * 64 + '\n'
    marker = 'usr/share/oh-no-parent-control/confinement/generation'
    vendor_path = '/usr/lib/polkit-1/polkit-agent-helper-1'
    parent_path = '/usr/libexec/polkit-gnome-authentication-agent-1'
    expected = dict(path=vendor_path, mode=0o4755,
                    label='system_u:object_r:policykit_auth_exec_t:s0')
    config = {'backend': 'selinux', 'domains': ['manager', 'polkit'],
              'preserved_executables': [expected],
              'executables': [{'role': 'polkit', 'paths': [parent_path]}]}
    root = tmp_path / 'private-root'
    (root / marker).parent.mkdir(parents=True)
    (root / marker).write_text(generation)
    pinned = root / vendor_path.lstrip('/')
    pinned.parent.mkdir(parents=True)
    pinned.write_bytes(b'\x7fELFprivate vendor helper')
    pinned.chmod(0o4755)
    parent_executable = root / parent_path.lstrip('/')
    parent_executable.parent.mkdir(parents=True)
    parent_executable.write_bytes(b'\x7fELFprivate polkit agent')
    for pid, ppid, role, credentials in (
            (1, 0, None, ('0',) * 4),
            (42, 1, 'onpc_kiosk_manager_t', ('1002',) * 4),
            (43, 42, 'onpc_kiosk_polkit_t', ('1002',) * 4),
            (44, 43, 'policykit_auth_t', ('1002', '0', '0', '0'))):
        process = proc / str(pid)
        for tid in (pid, pid + 1000):
            thread = process / 'task' / str(tid)
            thread.mkdir(parents=True)
            fields = ['S', str(ppid)] + ['0'] * 17 + [str(tid * 100)]
            (thread / 'stat').write_text(f'{tid} (private helper) ' + ' '.join(fields))
            (thread / 'status').write_text('PPid:\t' + str(ppid) + '\nUid:\t' +
                                         '\t'.join(credentials) + '\n')
            (thread / 'ns').mkdir()
            (thread / 'ns/mnt').symlink_to('mnt:[host]' if pid == 1 else 'mnt:[private]')
            if role is not None:
                (thread / 'attr').mkdir()
                (thread / 'attr/current').write_text(f'system_u:system_r:{role}:s0')
                (thread / 'root').symlink_to(root)
            if pid == 44:
                (thread / 'exe').symlink_to(pinned)
                (thread / 'mountinfo').write_text(
                    f'25 24 0:1 / {vendor_path} ro,relatime - ext4 /dev/private ro\n')
        for name in ('stat', 'status', 'ns', 'attr', 'root'):
            (process / name).symlink_to(process / 'task' / str(pid) / name)
    manager, parent, process = (proc / str(pid) for pid in (42, 43, 44))
    (manager / 'mountinfo').write_text(
        f'25 24 0:1 / {vendor_path} ro,relatime - ext4 /dev/private ro\n')
    (parent / 'exe').symlink_to(parent_executable)
    manifest = tmp_path / 'records.json'
    manifest.write_text(json.dumps({'preserved': [dict(expected, uid=0, gid=0,
        sha256=helper.hashlib.sha256(pinned.read_bytes()).hexdigest())]}))
    manifest_path = Path('/run/oh-no-parent-control-confinement') / generation.strip() / 'records.json'
    original_read, original_fstat = Path.read_text, os.fstat
    monkeypatch.setattr(helper.Path, 'read_text', lambda path, *args, **kwargs:
                        original_read(manifest if path == manifest_path else path, *args, **kwargs))
    def descriptor_metadata(fd):
        info = original_fstat(fd)
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        return SimpleNamespace(**dict(values, st_uid=0, st_gid=0))
    monkeypatch.setattr(helper.os, 'fstat', descriptor_metadata)
    monkeypatch.setattr(helper.os, 'listxattr', lambda fd: [])
    monkeypatch.setattr(helper.os, 'getxattr', lambda fd, name: expected['label'].encode() + b'\0')
    opened, closed, enforcement = [], [], []
    def enforce(value):
        assert value is config
        enforcement.append(value)
    def preparation(path):
        assert path == '/usr/libexec/oh-no-parent-control-kiosk-confinement'
        return {'enforcing': enforce}
    monkeypatch.setattr(helper.runpy, 'run_path', preparation)
    def acquire(pid):
        opened.append(pid)
        return pid
    monkeypatch.setattr(helper.os, 'pidfd_open', acquire)
    monkeypatch.setattr(helper.os, 'close', closed.append)
    monkeypatch.setattr(helper, 'exited', lambda fd: False)
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: 42)
    return SimpleNamespace(helper=helper, config=config, generation=generation, manager=manager,
        parent=parent, process=process, pinned=pinned, parent_executable=parent_executable,
        manifest=manifest, opened=opened, closed=closed, enforcement=enforcement,
        account=SimpleNamespace(pw_uid=1002))


@pytest.mark.parametrize('fault', [
    None, 'inventory', 'generation-format', 'credentials', 'thread-parent', 'thread-label',
    'host-namespace', 'other-private-namespace', 'thread-generation', 'empty-threads',
    'parent-label', 'parent-credentials', 'parent-namespace', 'parent-generation', 'parent-executable',
    'executable-mode', 'executable-owner', 'executable-group', 'executable-type',
    'executable-hardlink', 'executable-capability', 'executable-label', 'executable-format',
    'record-hash', 'record-mode', 'helper-inode', 'visible-helper-inode', 'visible-inode-replaced',
    'missing-mount', 'writable-mount', 'duplicate-mount', 'manager-writable-mount',
    'parent-exited', 'parent-replaced', 'parent-thread-replaced', 'parent-task-added',
    'parent-label-changed', 'helper-label-changed', 'helper-namespace-changed', 'helper-generation-changed',
])
def test_password_helper_census_requires_exact_live_helper_parent_and_private_file(
        password_helper_census, monkeypatch, tmp_path, fault):
    model = password_helper_census
    helper, parent, process = model.helper, model.parent, model.process
    thread, parent_thread = process / 'task/1044', parent / 'task/1043'
    generation = model.generation
    if fault == 'inventory':
        model.config['preserved_executables'][0]['path'] = '/usr/bin/untrusted-helper'
    elif fault == 'generation-format':
        generation = 'unmeasured-generation\n'
    elif fault in ('credentials', 'thread-parent', 'parent-credentials'):
        target = parent_thread if fault == 'parent-credentials' else thread
        credentials = ('1002',) * 4 if fault == 'credentials' else ('0',) * 4 if fault == 'parent-credentials' else ('1002', '0', '0', '0')
        (target / 'status').write_text('PPid:\t' + ('999' if fault == 'thread-parent' else '42' if fault == 'parent-credentials' else '43') +
                                      '\nUid:\t' + '\t'.join(credentials) + '\n')
    elif fault in ('thread-label', 'parent-label'):
        target = parent_thread if fault == 'parent-label' else thread
        (target / 'attr/current').write_text('system_u:system_r:init_t:s0')
    elif fault in ('host-namespace', 'other-private-namespace', 'parent-namespace'):
        target = parent_thread if fault == 'parent-namespace' else thread
        (target / 'ns/mnt').unlink()
        (target / 'ns/mnt').symlink_to('mnt:[host]' if fault == 'host-namespace' else 'mnt:[foreign-private]')
    elif fault in ('thread-generation', 'parent-generation'):
        target = parent_thread if fault == 'parent-generation' else thread
        (target / 'root').unlink()
        marker = tmp_path / 'foreign-root/usr/share/oh-no-parent-control/confinement/generation'
        marker.parent.mkdir(parents=True)
        marker.write_text('b' * 64 + '\n')
        (target / 'root').symlink_to(tmp_path / 'foreign-root')
    elif fault == 'visible-helper-inode':
        (thread / 'root').unlink()
        root = tmp_path / 'foreign-root'
        marker = root / 'usr/share/oh-no-parent-control/confinement/generation'
        marker.parent.mkdir(parents=True)
        marker.write_text(generation)
        substitute = root / 'usr/lib/polkit-1/polkit-agent-helper-1'
        substitute.parent.mkdir(parents=True)
        substitute.write_bytes(model.pinned.read_bytes())
        (thread / 'root').symlink_to(root)
    elif fault in ('parent-executable', 'helper-inode'):
        substitute = tmp_path / 'foreign-executable'
        substitute.write_bytes(b'\x7fELFprivate substitute')
        target = parent if fault == 'parent-executable' else thread
        (target / 'exe').unlink()
        (target / 'exe').symlink_to(substitute)
    elif fault == 'executable-mode':
        model.pinned.chmod(0o755)
    elif fault in ('executable-owner', 'executable-group', 'executable-type'):
        original = helper.os.fstat
        field, value = (('st_mode', stat.S_IFDIR | 0o4755) if fault == 'executable-type' else
                        ('st_uid' if fault == 'executable-owner' else 'st_gid', 12345))
        monkeypatch.setattr(helper.os, 'fstat', lambda fd:
                            SimpleNamespace(**dict(vars(original(fd)), **{field: value})))
    elif fault == 'executable-hardlink':
        os.link(model.pinned, tmp_path / 'foreign-hardlink')
    elif fault == 'executable-capability':
        monkeypatch.setattr(helper.os, 'listxattr', lambda fd: ['security.capability'])
    elif fault == 'executable-label':
        monkeypatch.setattr(helper.os, 'getxattr', lambda fd, name: b'system_u:object_r:bin_t:s0')
    elif fault == 'executable-format':
        model.pinned.write_bytes(b'#!/bin/sh\nexit 0\n')
        model.pinned.chmod(0o4755)
    elif fault in ('record-hash', 'record-mode'):
        record = json.loads(model.manifest.read_text())
        record['preserved'][0]['sha256' if fault == 'record-hash' else 'mode'] = (
            'b' * 64 if fault == 'record-hash' else 0o755)
        model.manifest.write_text(json.dumps(record))
    elif fault in ('missing-mount', 'writable-mount', 'duplicate-mount', 'manager-writable-mount'):
        target = model.manager if fault == 'manager-writable-mount' else thread
        contents = (target / 'mountinfo').read_text()
        (target / 'mountinfo').write_text('' if fault == 'missing-mount' else
            contents.replace('ro,relatime', 'rw,relatime') if 'writable' in fault else contents * 2)
    elif fault == 'parent-exited':
        monkeypatch.setattr(helper, 'exited', lambda fd: fd == 43)
    elif fault in ('parent-replaced', 'parent-thread-replaced'):
        original = helper.process_identity
        observed = {}
        target = parent if fault == 'parent-replaced' else parent_thread
        def identity(path):
            value = original(path)
            observed[path] = observed.get(path, 0) + 1
            return ('changed', *value[1:]) if path == target and observed[path] > 1 else value
        monkeypatch.setattr(helper, 'process_identity', identity)
    elif fault == 'parent-task-added':
        original = Path.iterdir
        observed = []
        def entries(path):
            if path == parent / 'task':
                observed.append(path)
                if len(observed) == 2:
                    (path / '2043').mkdir()
            return original(path)
        monkeypatch.setattr(helper.Path, 'iterdir', entries)
    elif fault in ('parent-label-changed', 'helper-label-changed', 'helper-namespace-changed',
                   'helper-generation-changed', 'visible-inode-replaced'):
        original = helper.hashlib.file_digest
        def digest(stream, name):
            value = original(stream, name)
            if fault in ('parent-label-changed', 'helper-label-changed'):
                target = parent_thread if fault == 'parent-label-changed' else thread
                (target / 'attr/current').write_text('system_u:system_r:init_t:s0')
            elif fault == 'helper-namespace-changed':
                (thread / 'ns/mnt').unlink()
                (thread / 'ns/mnt').symlink_to('mnt:[foreign-private]')
            elif fault == 'helper-generation-changed':
                (thread / 'root/usr/share/oh-no-parent-control/confinement/generation').write_text('b' * 64 + '\n')
            else:
                replacement = model.pinned.with_name('replacement')
                replacement.write_bytes(model.pinned.read_bytes())
                replacement.chmod(0o4755)
                replacement.replace(model.pinned)
            return value
        monkeypatch.setattr(helper.hashlib, 'file_digest', digest)
    identity = helper.process_identity(process)
    threads = {item: helper.process_identity(item) for item in (process / 'task').iterdir()}
    if fault == 'empty-threads':
        threads.clear()
    def observe():
        return helper.password_helper_process(process, model.account, model.config, model.manager,
                                              generation, 'mnt:[host]', identity, threads)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-(password|census):'):
            observe()
    else:
        assert observe() is None
    assert model.opened == model.closed
    assert len(model.enforcement) == (0 if fault in ('inventory', 'generation-format') else 1)


@pytest.mark.parametrize('fault', [None, 'init-t', 'unknown-label', 'helper-replaced', 'thread-replaced'])
def test_full_census_admits_only_proven_vendor_helper_and_rechecks_its_lifetime(
        password_helper_census, monkeypatch, fault):
    model = password_helper_census
    helper, process = model.helper, model.process
    if fault in ('init-t', 'unknown-label'):
        (process / 'attr/current').write_text('system_u:system_r:' +
            ('init_t' if fault == 'init-t' else 'unconfined_t') + ':s0')
    elif fault in ('helper-replaced', 'thread-replaced'):
        original = helper.process_identity
        target = process if fault == 'helper-replaced' else process / 'task/1044'
        observed = {}
        def identity(path):
            value = original(path)
            observed[path] = observed.get(path, 0) + 1
            return ('changed', *value[1:]) if path == target and observed[path] > 1 else value
        monkeypatch.setattr(helper, 'process_identity', identity)
    def observe():
        return helper.census_processes(model.account, model.config, 'selinux', model.manager, 42,
                                       'user@1002.service', required_roles=('manager', 'polkit'))
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-census:'):
            observe()
    else:
        assert observe()['confined_thread_roles'] == {
            'onpc_kiosk_manager_t': 2, 'onpc_kiosk_polkit_t': 2, 'policykit_auth_t': 2}
    assert sorted(model.opened) == sorted(model.closed)


@pytest.mark.parametrize('field', [
    'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_gid',
])
def test_password_helper_census_refuses_executable_change_during_hashing(
        password_helper_census, monkeypatch, field):
    model = password_helper_census
    helper, process = model.helper, model.process
    original = helper.os.fstat
    observations = []
    def metadata(fd):
        values = vars(original(fd))
        observations.append(fd)
        if len(observations) == 2:
            values[field] += 1
        return SimpleNamespace(**values)
    monkeypatch.setattr(helper.os, 'fstat', metadata)
    identity = helper.process_identity(process)
    threads = {item: helper.process_identity(item) for item in (process / 'task').iterdir()}
    with pytest.raises(helper.guest.GuestError, match='kiosk-password:executable-changed'):
        helper.password_helper_process(process, model.account, model.config, model.manager,
                                       model.generation, 'mnt:[host]', identity, threads)
    assert len(observations) == 2
    assert model.opened == model.closed


def test_password_helper_census_refuses_permissive_installed_policy_before_parent_probe(
        password_helper_census, monkeypatch):
    model = password_helper_census
    helper, process = model.helper, model.process
    def permissive(config):
        raise ValueError('selinux-domain-not-enforcing')
    monkeypatch.setattr(helper.runpy, 'run_path', lambda path: {'enforcing': permissive})
    identity = helper.process_identity(process)
    threads = {item: helper.process_identity(item) for item in (process / 'task').iterdir()}
    with pytest.raises(ValueError, match='selinux-domain-not-enforcing'):
        helper.password_helper_process(process, model.account, model.config, model.manager,
                                       model.generation, 'mnt:[host]', identity, threads)
    assert model.opened == model.closed == []


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'label', 'credentials', 'namespace', 'generation',
                                  'profile-entry', 'proof-write', 'initial-exec'])
def test_bwrap_probe_requires_real_app_boundary_before_arming_or_execution(
        census_model, monkeypatch, backend, fault):
    helper = census_model
    generation = 'a' * 64 + '\n'
    request = dict(backend=backend, uid=1002, gid=1002, namespace=42, generation=generation,
                   arguments=['/usr/bin/bwrap', '--version'], proof_fd=53)
    expected = ('onpc-kiosk-app (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_app_t:s0')
    change = Mock(return_value=-1 if fault == 'profile-entry' else 0)
    monkeypatch.setattr(helper.ctypes, 'CDLL', lambda *args, **kwargs:
                        SimpleNamespace(aa_change_profile=change))
    monkeypatch.setattr(helper, 'lifecycle_label', lambda value:
                        'unconfined' if fault == 'label' else expected)
    credentials = []
    monkeypatch.setattr(helper.os, 'setgroups', lambda value: credentials.append(('groups', value)))
    monkeypatch.setattr(helper.os, 'setgid', lambda value: credentials.append(('gid', value)))
    monkeypatch.setattr(helper.os, 'setuid', lambda value: credentials.append(('uid', value)))
    monkeypatch.setattr(helper, 'process_identity', lambda path:
                        ('start', 1, ('0',) * 4 if fault == 'credentials' else ('1002',) * 4))
    monkeypatch.setattr(helper.os, 'stat', lambda path:
                        SimpleNamespace(st_ino=43 if fault == 'namespace' else 42))
    monkeypatch.setattr(helper.Path, 'read_text', lambda path:
                        'foreign' if fault == 'generation' else generation)
    inherited = []
    monkeypatch.setattr(helper.os, 'set_inheritable', lambda fd, value: inherited.append((fd, value)))
    proofs = []
    diagnostics = []
    def write(fd, data):
        if fd == 2:
            diagnostics.append(json.loads(data))
            return len(data)
        assert fd == 53
        proofs.append(json.loads(data))
        return len(data) - int(fault == 'proof-write')
    monkeypatch.setattr(helper.os, 'write', write)
    executed = []
    def execute(path, arguments, environment):
        executed.append((path, arguments, environment))
        if fault == 'initial-exec':
            raise PermissionError(13, 'private denied fixture')
        raise RuntimeError('exec captured')
    monkeypatch.setattr(helper.os, 'execve', execute)
    monkeypatch.setattr(helper.os, '_exit', Mock(side_effect=RuntimeError('exit captured')))
    failed = fault not in (None, 'initial-exec') and not (fault == 'profile-entry' and backend == 'selinux')
    if failed:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            helper.bwrap_probe_child(request)
        assert not executed
    else:
        with pytest.raises(RuntimeError, match='exit captured' if fault == 'initial-exec' else 'exec captured'):
            helper.bwrap_probe_child(request)
        assert credentials == [('groups', []), ('gid', 1002), ('uid', 1002)]
        assert proofs == [dict(uid=1002, namespace=42, generation=generation, role=expected)]
        assert inherited == [(53, False)]
        assert executed == [('/usr/bin/bwrap', request['arguments'], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})]
        assert diagnostics == ([{'bwrap_setup': 'initial-exec', 'errno': 13}]
                               if fault == 'initial-exec' else [])
    assert change.call_count == int(backend == 'apparmor')


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'pid', 'role', 'operation', 'target', 'permissive',
                                  'old', 'old-time', 'missing', 'setup', 'setup-stderr',
                                  'unsupported-flags', 'success', 'token'])
def test_bwrap_attack_requires_fresh_exact_enforcing_kernel_denial(
        census_model, monkeypatch, backend, fault):
    helper = census_model
    target = '/usr/bin/xdg-dbus-proxy'
    if backend == 'apparmor':
        line = ('audit(1792000000.123:42): apparmor="DENIED" operation="mount" '
                'profile="onpc-kiosk-bwrap" name="/newroot' + target + '" pid=4200 error=-13')
    else:
        line = ('audit(1792000000.123:42): avc:  denied  { execute } for pid=4200 '
                'name="bwrap-canary" dev="tmpfs" ino=43 scontext=system_u:system_r:onpc_kiosk_bwrap_t:s0 '
                'tcontext=unconfined_u:object_r:user_tmp_t:s0 tclass=file permissive=0')
    changes = {'pid': ('pid=4200', 'pid=42001'),
               'role': ('onpc-kiosk-bwrap', 'onpc-kiosk-app') if backend == 'apparmor' else
                       ('onpc_kiosk_bwrap_t', 'onpc_kiosk_app_t'),
               'operation': ('operation="mount"', 'operation="open"') if backend == 'apparmor' else
                            ('{ execute }', '{ read }'),
               'target': (target, '/usr/bin/foreign') if backend == 'apparmor' else
                         ('name="bwrap-canary"', 'name="foreign"'),
               'permissive': ('apparmor="DENIED"', 'apparmor="ALLOWED"') if backend == 'apparmor' else
                             ('permissive=0', 'permissive=1')}
    if fault in changes:
        line = line.replace(*changes[fault])
    if fault == 'old-time':
        line = line.replace('1792000000.123', '1791999999.999')
    before = {line} if fault == 'old' else set()
    audit = Mock(return_value='' if fault == 'missing' else line)
    def wait(predicate, category):
        helper.guest.require(predicate(), category)
    monkeypatch.setitem(sys.modules, 'system_kiosk_platform',
                        SimpleNamespace(kernel_audit=audit, wait_for=wait))
    output = (b'{"bwrap_setup":"initial-exec","errno":13}' if fault == 'setup' else
              b'bwrap: Unknown option --as-pid-1' if fault == 'unsupported-flags' else
              b'canary' if fault == 'token' else b'bwrap: permission denied')
    info = b'' if fault == 'unsupported-flags' else b'{"child-pid":4200,"pid-namespace":1234}'
    records = []
    def exercise():
        stderr = (b'{"bwrap_setup":"initial-exec","errno":13}' if fault == 'setup-stderr' else
                  ('bwrap: execvp ' + target + ': Permission denied\n').encode() if backend == 'selinux' else b'')
        helper.require_bwrap_denial(0 if fault == 'success' else 1, output, info,
            b'canary', backend, target, before, 1792000000.0, lambda *item: records.append(item),
            stderr=stderr, source_inode=43)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            exercise()
        assert not records
    else:
        exercise()
        assert records == [('onpc.kiosk.bwrap.kernel-denial', line)]


@pytest.mark.parametrize('mode,name,context', [
    ('bind', 'bwrap-canary', 'unconfined_u:object_r:user_tmp_t:s0'),
    ('data', None, 'system_u:object_r:tmpfs_t:s0'),
    ('tmpfs-file', 'gst-plugin-scanner', 'system_u:object_r:tmpfs_t:s0'),
])
@pytest.mark.parametrize('fault', [None, 'name', 'context', 'device', 'inode', 'native-target', 'native-stage'])
def test_bwrap_selinux_correlates_native_target_with_each_observed_object_style(
        census_model, monkeypatch, mode, name, context, fault):
    helper = census_model
    target = '/usr/libexec/gstreamer-1.0/gst-plugin-scanner'
    # Only bind preserves the caller's measured inode. The other modes create
    # independent inodes: no equality to the source is claimed or required.
    inode = 43 if mode == 'bind' else 987
    object_name = '' if name is None else 'name="' + name + '" '
    line = ('audit(1792000000.123:42): avc:  denied  { execute } for pid=4200 ' + object_name +
            'dev="tmpfs" ino=' + str(inode) + ' scontext=system_u:system_r:onpc_kiosk_bwrap_t:s0 '
            'tcontext=' + context + ' tclass=file permissive=0')
    if fault == 'name':
        line = line.replace(object_name, 'name="foreign" ', 1) if object_name else line + ' name="foreign"'
    elif fault == 'context':
        line = line.replace('tcontext=' + context, 'tcontext=system_u:object_r:bin_t:s0')
    elif fault == 'device':
        line = line.replace('dev="tmpfs"', 'dev="vda1"')
    elif fault == 'inode':
        line = line.replace('ino=' + str(inode), 'ino=44' if mode == 'bind' else 'ino=0')
    stderr = ('bwrap: execvp ' + target + ': Permission denied\n').encode()
    if fault == 'native-target':
        stderr = stderr.replace(target.encode(), b'/usr/bin/foreign')
    elif fault == 'native-stage':
        stderr = b'bwrap: Failed to mount: Permission denied\n'
    monkeypatch.setitem(sys.modules, 'system_kiosk_platform', SimpleNamespace(
        kernel_audit=lambda backend: line,
        wait_for=lambda predicate, category: helper.guest.require(predicate(), category)))
    records = []
    def exercise():
        helper.require_bwrap_denial(1, b'', b'{"child-pid":4200}', b'canary', 'selinux',
            target, set(), 1792000000.0, lambda *item: records.append(item),
            stderr=stderr, mode=mode, source_inode=43)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            exercise()
        assert not records
    else:
        exercise()
        assert records == [('onpc.kiosk.bwrap.kernel-denial', line)]


@pytest.mark.parametrize('fault', [None, 'operation', 'target', 'mask', 'owner', 'native-stage'])
def test_bwrap_apparmor_tmpfs_file_requires_observed_owned_create_denial(
        census_model, monkeypatch, fault):
    helper = census_model
    target = '/usr/bin/xdg-dbus-proxy'
    line = ('audit(1792000000.123:42): apparmor="DENIED" operation="mknod" class="file" '
            'profile="onpc-kiosk-bwrap" name="/newroot' + target + '" pid=4200 '
            'requested_mask="c" denied_mask="c" fsuid=1002 ouid=1002')
    changes = {'operation': ('operation="mknod"', 'operation="open"'),
               'target': (target, '/usr/bin/foreign'),
               'mask': ('denied_mask="c"', 'denied_mask="w"'),
               'owner': ('ouid=1002', 'ouid=0')}
    if fault in changes:
        line = line.replace(*changes[fault])
    monkeypatch.setitem(sys.modules, 'system_kiosk_platform', SimpleNamespace(
        kernel_audit=lambda backend: line,
        wait_for=lambda predicate, category: helper.guest.require(predicate(), category)))
    records = []
    stderr = ("bwrap: Can't create file " + target + ': Permission denied\n').encode()
    if fault == 'native-stage':
        stderr = ('bwrap: execvp ' + target + ': Permission denied\n').encode()
    def exercise():
        helper.require_bwrap_denial(1, b'', b'{"child-pid":4200}', b'canary', 'apparmor',
            target, set(), 1792000000.0, lambda *item: records.append(item),
            stderr=stderr, mode='tmpfs-file', uid=1002)
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bwrap:'):
            exercise()
        assert not records
    else:
        exercise()
        assert records == [('onpc.kiosk.bwrap.kernel-denial', line)]


@pytest.mark.parametrize('data', [b'', b'not-json', b'{}', b'[]', b'{"child-pid":true}',
                                 b'{"child-pid":1}', b'{"child-pid":"4200"}', b'x' * 4097])
def test_bwrap_native_info_requires_real_host_child_pid(census_model, data):
    with pytest.raises(census_model.guest.GuestError, match='kiosk-bwrap:native-child-info'):
        census_model.bwrap_child_pid(data)


def test_bwrap_diagnostics_keep_setup_stderr_and_bound_each_channel(census_model):
    records = []
    census_model.record_bwrap_probe(lambda *item: records.append(item), 'proxy-bind', 126,
        b'x' * 4097, b'{"child-pid":4200}', b'{"bwrap_setup":"initial-exec","errno":13}')
    assert records[0][0] == 'onpc.kiosk.bwrap.proxy-bind.probe'
    assert json.loads(records[0][1]) == {
        'status': 126, 'stdout': 'x' * 4096, 'native_info': '{"child-pid":4200}',
        'stderr': '{"bwrap_setup":"initial-exec","errno":13}', 'truncated': True}


@pytest.mark.parametrize('backend,row,expected', [
    ('apparmor', 'gdm3\t50.1-0ubuntu0.1\tamd64\tgdm3\t50.1-0ubuntu0.1',
     {'package': 'gdm3', 'version': '50.1-0ubuntu0.1', 'architecture': 'amd64',
      'source_package': 'gdm3', 'source_version': '50.1-0ubuntu0.1'}),
    ('selinux', 'pam\t0:1.7.2-2.fc44\tx86_64\tpam-1.7.2-2.fc44.src.rpm',
     {'package': 'pam', 'version': '0:1.7.2-2.fc44', 'architecture': 'x86_64',
      'source_rpm': 'pam-1.7.2-2.fc44.src.rpm'}),
])
def test_native_package_inventory_preserves_exact_binary_and_source_builds(
        census_model, backend, row, expected):
    assert census_model.native_package_rows(backend, row) == [expected]


@pytest.mark.parametrize('rows', ['', 'pam\t1.7\tx86_64', 'pam\t1.7\tx86_64\t',
                                  'pam\t1.7\tx86_64\tbad source',
                                  'pam\t1.7\tx86_64\tpam.src.rpm\npam\t1.7\tx86_64\tpam.src.rpm'])
def test_native_package_inventory_refuses_missing_or_ambiguous_source_identity(census_model, rows):
    with pytest.raises(census_model.guest.GuestError, match='kiosk-native:package-identity'):
        census_model.native_package_rows('selinux', rows)


@pytest.mark.parametrize('fault', [None, 'absent', 'disappeared', 'missing-map', 'data-only', 'foreign-inode',
                                  'foreign-device', 'deleted', 'receipt', 'changed'])
def test_pam_cgfs_mapping_requires_native_executable_inode_and_receipt(
        census_model, tmp_path, monkeypatch, fault):
    helper = census_model
    native = tmp_path / 'pam_cgfs.so'
    native.write_bytes(b'\x7fELFprivate native callback')
    identity = native.stat()
    digest = helper.guest.sha(native)
    measured = {'role': 'library', 'path': str(native), 'sha256': digest}
    source = Mock(side_effect=[measured, {**measured, 'sha256': 'f' * 64}
                               if fault == 'changed' else measured])
    preparation = {'trusted': Mock(return_value=native), 'source_record': source}
    reader = Mock(return_value=preparation)
    monkeypatch.setattr(helper.runpy, 'run_path', reader)
    original_exists = os.path.lexists
    monkeypatch.setattr(helper.os.path, 'lexists', lambda path: fault not in ('absent', 'disappeared')
                        if str(path) == '/usr/lib/x86_64-linux-gnu/security/pam_cgfs.so'
                        else original_exists(path))
    device = f'{os.major(identity.st_dev):x}:{os.minor(identity.st_dev):x}'
    if fault == 'foreign-device':
        device = 'ff:ff'
    inode = identity.st_ino + (fault == 'foreign-inode')
    permissions = 'r--p' if fault == 'data-only' else 'r-xp'
    mapped = str(native) + (' (deleted)' if fault == 'deleted' else '')
    (tmp_path / 'maps').write_text('' if fault == 'missing-map' else
        f'1000-2000 {permissions} 00000000 {device} {inode} {mapped}\n')
    receipts = [{'path': str(native), 'sha256': '0' * 64 if fault == 'receipt' else digest}]
    if fault == 'absent':
        receipts = []
    events = {}
    if fault is not None:
        with pytest.raises(helper.guest.GuestError, match='kiosk-lifecycle:cgfs-'):
            helper.lifecycle_cgfs_mapping(tmp_path, receipts, events.__setitem__)
        assert not events
    else:
        helper.lifecycle_cgfs_mapping(tmp_path, receipts, events.__setitem__)
        assert json.loads(events['onpc.kiosk.pam-lifecycle.pam-cgfs-native-mapping']) == {
            'path': str(native), 'sha256': digest, 'device': device, 'inode': identity.st_ino}
        assert source.call_args_list[0].args == ('library', native)


@pytest.mark.parametrize('backend,present', [('apparmor', True), ('apparmor', False),
                                          ('selinux', True)])
def test_native_receipts_include_installed_optional_cgfs_bytes_and_package(
        census_model, tmp_path, monkeypatch, backend, present):
    helper = census_model
    # A finite private distro tree keeps package queries and every write off the host.
    library = '/usr/lib/x86_64-linux-gnu' if backend == 'apparmor' else '/usr/lib64'
    names = ['/usr/libexec/gdm-session-worker', '/usr/lib/systemd/systemd-executor',
             library + '/libpam.so.0', library + '/security/pam_namespace.so',
             library + '/security/pam_selinux.so', library + '/libselinux.so.1']
    if backend == 'apparmor':
        names.append(library + '/libapparmor.so.1')
    optional = library + '/security/pam_cgfs.so'
    for name in names + ([optional] if present else []):
        path = tmp_path / name.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\x7fELF' + name.encode())
    def path(value):
        value = Path(value)
        return tmp_path / str(value).lstrip('/') if str(value).startswith('/usr/') else value
    monkeypatch.setattr(helper, 'Path', path)
    original_relative = Path.is_relative_to
    monkeypatch.setattr(Path, 'is_relative_to', lambda value, other:
                        original_relative(value, tmp_path / 'usr') if other == '/usr'
                        else original_relative(value, other))
    original_stat = Path.stat
    def metadata(value, **options):
        info = original_stat(value, **options)
        return SimpleNamespace(st_uid=0, st_mode=info.st_mode & ~0o022)
    monkeypatch.setattr(Path, 'stat', metadata)
    trusted = Mock(side_effect=lambda value, **options: value.resolve(strict=True))
    monkeypatch.setattr(helper.runpy, 'run_path', Mock(return_value={
        'inventory': lambda config: [], 'trusted': trusted}))
    commands = []
    def query(arguments):
        commands.append(arguments)
        if arguments[:2] == ['dpkg-query', '-S']:
            return '\n'.join(('libpam-cgfs:amd64' if value.endswith('/pam_cgfs.so') else
                              'native-input:amd64') + ': ' + value for value in arguments[2:])
        if arguments[:2] == ['dpkg-query', '-W']:
            return '\n'.join(name + '\t6.0.6-1ubuntu2\tamd64\tlxc\t6.0.6-1ubuntu2'
                             for name in arguments[3:])
        if arguments[:2] == ['rpm', '-qf']:
            return 'native-input\n'
        assert arguments[:2] == ['rpm', '-q']
        return 'native-input\t0:1.2-3.fc44\tx86_64\tnative-input-1.2-3.fc44.src.rpm\n'
    monkeypatch.setattr(helper.guest, 'run', query)
    events = {}
    files = helper.record_native_packages({'backend': backend}, events.__setitem__)
    included = backend == 'apparmor' and present
    actual = path(optional)
    if included:
        assert {'path': str(actual), 'sha256': helper.guest.sha(actual)} in files
    else:
        assert not any(item['path'].endswith('/pam_cgfs.so') for item in files)
    packages = json.loads(events['onpc.kiosk.native.packages'])
    assert any(item['package'] == 'libpam-cgfs:amd64' and item['version'] == '6.0.6-1ubuntu2'
               for item in packages) == included
    assert trusted.call_count == included


@pytest.fixture(scope='module')
def fixed_launchers(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-native-launchers')
    target = directory / 'capture'
    target.write_text('#!/usr/bin/python3 -I\nimport json, os, sys\n'
                      'print(json.dumps([sys.argv[1:], dict(os.environ)]))\n')
    target.chmod(0o700)
    source = directory / 'launcher.c'
    # Preserve all argument/environment code. Redirect only the final exec to
    # the private observer and use this fixture UID for the kiosk Wellbeing branch.
    source.write_text((ROOT / 'tools/kiosk_session.c').read_text()
                      .replace('execv(arguments[0], arguments)', f'execv("{target}", arguments)')
                      .replace('getpwnam("oh-no-parent-control")', 'getpwuid(getuid())'))
    paths = {}
    for role in ('wellbeing', 'packages'):
        executable = directory / role
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        f'-DKIOSK_LAUNCH_ROLE="{role}"', '-o', str(executable), str(source)],
                       check=True, capture_output=True, text=True, timeout=30,
                       pass_fds=scratch_descriptors())
        paths[role] = executable
    return paths


@pytest.mark.parametrize('role', ['wellbeing', 'packages'])
def test_fixed_native_launchers_reject_arguments_and_ignore_code_configuration(fixed_launchers, role, tmp_path):
    entry = fixed_launchers[role]
    denied = subprocess.run([str(entry), '--eval=untrusted'], capture_output=True, timeout=5,
                            pass_fds=scratch_descriptors())
    assert denied.returncode == 1 and denied.stdout == b''
    environment = dict(os.environ, HOME=str(tmp_path), WAYLAND_SOCKET='13',
                       PYTHONPATH=str(tmp_path), GJS_PATH=str(tmp_path),
                       WIREPLUMBER_CONFIG_DIR=str(tmp_path), WIREPLUMBER_DATA_DIR=str(tmp_path),
                       WIREPLUMBER_MODULE_DIR=str(tmp_path), GST_PLUGIN_PATH=str(tmp_path),
                       RPM_CONFIGDIR=str(tmp_path), LUA_PATH=str(tmp_path), LUA_CPATH=str(tmp_path),
                       LUA_PATH_5_4=str(tmp_path), LUA_CPATH_5_4=str(tmp_path),
                       LUA_PATH_5_5=str(tmp_path), LUA_CPATH_5_5=str(tmp_path),
                       GIO_USE_VFS=str(tmp_path))
    result = subprocess.run([str(entry)], env=environment, capture_output=True,
                            text=True, check=True, timeout=5,
                            pass_fds=scratch_descriptors())
    arguments, observed = json.loads(result.stdout)
    assert observed['WAYLAND_SOCKET'] == '13'
    assert observed['GIO_USE_VFS'] == 'local'
    for name in ('PYTHONPATH', 'GJS_PATH', 'WIREPLUMBER_MODULE_DIR', 'GST_PLUGIN_PATH',
                 'RPM_CONFIGDIR', 'LUA_PATH_5_4', 'LUA_CPATH_5_4', 'LUA_PATH_5_5', 'LUA_CPATH_5_5'):
        assert name not in observed
    if role == 'packages':
        from common.oh_no_parent_control_ui.system_info import RPM_DIAGNOSTIC_PACKAGES
        assert arguments[arguments.index('--') + 1:] == list(RPM_DIAGNOSTIC_PACKAGES)
        assert '~' not in arguments[arguments.index('--macros') + 1]
        assert observed['HOME'] == '/'
    elif role == 'wellbeing':
        assert arguments == ['-m', '/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/wellbeingService.js']
    assert 'LUA_PATH' not in observed and 'LUA_CPATH' not in observed



@pytest.fixture
def service_denial_evidence(census_model):
    helper = census_model
    account = SimpleNamespace(pw_uid=1234, pw_gid=1234)
    target = {'path': '/usr/bin/private-denied', 'device': 7, 'inode': 987,
              'audit_device': 'privatefs', 'audit_name': 'private-denied', 'sha256': 'target-digest'}
    unit, invocation, boot = 'private-denial.service', 'a' * 32, 'b' * 32

    def native(stage='EXEC'):
        return {'MESSAGE_ID': '641257651c1b4ec9a8624d7a40a9e1e7',
                'CODE_FILE': 'src/core/executor.c', 'USER_UNIT': unit,
                'USER_INVOCATION_ID': invocation, '_PID': '4321', '_UID': '1234',
                '_BOOT_ID': boot, 'EXECUTABLE': target['path'], 'ERRNO': '13',
                '__REALTIME_TIMESTAMP': '100000001',
                'MESSAGE': f'{unit}: Failed at step {stage} spawning {target["path"]}: Permission denied'}

    def audit(backend, profile=False):
        prefix = 'audit(100.001:71): pid=4321 '
        if backend == 'apparmor':
            return prefix + 'apparmor="DENIED" profile="onpc-kiosk-manager" ' + (
                'operation="change_onexec" name="unconfined" target="unconfined"' if profile else
                f'operation="exec" name="{target["path"]}" denied_mask="x" fsuid=1234 ouid=0')
        return prefix + 'avc:  denied ' + (
            '{ setexec } tclass=process ' if profile else
            '{ execute } tclass=file ino=987 name="private-denied" dev="privatefs" ') + (
            f'scontext={helper.MANAGER_SID} tcontext={helper.MANAGER_SID} permissive=0')

    return SimpleNamespace(account=account, target=target, unit=unit, invocation=invocation,
                           boot=boot, command=[target['path']], native=native, audit=audit)


@pytest.mark.parametrize('stage', ['EXEC', 'APPARMOR', 'SELINUX_CONTEXT'])
@pytest.mark.parametrize('fault', [None, 'pid', 'uid', 'unit', 'invocation', 'boot', 'target',
                                  'source', 'message-id', 'stale', 'missing-error',
                                  'wrong-error', 'wrong-stage', 'unrelated-setup', 'trusted-unit'])
def test_service_native_denial_requires_fresh_executor_failure(
        census_model, service_denial_evidence, stage, fault):
    evidence = service_denial_evidence
    row = evidence.native(stage)
    changes = {'pid': ('_PID', '14321'), 'uid': ('_UID', '0'),
               'unit': ('USER_UNIT', 'other.service'),
               'invocation': ('USER_INVOCATION_ID', 'c' * 32), 'boot': ('_BOOT_ID', 'd' * 32),
               'target': ('EXECUTABLE', '/usr/bin/other'),
               'source': ('CODE_FILE', 'src/core/service.c'), 'message-id': ('MESSAGE_ID', 'other'),
               'stale': ('__REALTIME_TIMESTAMP', '99999999'),
               'wrong-error': ('ERRNO', '2'), 'trusted-unit': ('_SYSTEMD_USER_UNIT', 'other.service')}
    if fault in changes:
        key, value = changes[fault]
        row[key] = value
    elif fault == 'missing-error':
        row.pop('ERRNO')
    elif fault == 'wrong-stage':
        row['MESSAGE'] = row['MESSAGE'].replace(f'step {stage}', 'step NAMESPACE')
    elif fault == 'unrelated-setup':
        row['MESSAGE'] = 'Failed to set up mount namespacing: Permission denied'
    assert census_model.service_native_denial(row, evidence.account, evidence.unit,
        evidence.invocation, '4321', evidence.command, stage, evidence.boot, 100) is (fault is None)


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('profile', [False, True], ids=['exec', 'profile'])
@pytest.mark.parametrize('fault', [None, 'pid', 'role', 'operation', 'target', 'unenforced'])
def test_service_audit_denial_requires_exact_enforcing_operation(
        census_model, service_denial_evidence, backend, profile, fault):
    evidence = service_denial_evidence
    line = evidence.audit(backend, profile)
    if fault == 'pid':
        line = line.replace('pid=4321', 'pid=14321')
    elif fault == 'role':
        line = line.replace('onpc-kiosk-manager', 'onpc-kiosk-app').replace(
            'onpc_kiosk_manager_t', 'onpc_kiosk_app_t')
    elif fault == 'operation':
        line = line.replace('change_onexec', 'change_profile').replace('operation="exec"',
            'operation="open"').replace('{ execute }', '{ read }').replace('{ setexec }', '{ transition }')
    elif fault == 'target':
        line = (line.replace('target="unconfined"', 'target="other"') if backend == 'apparmor' and profile
                else line.replace('name="/usr/bin/private-denied"', 'name="/usr/bin/other"')
                if backend == 'apparmor' else
                line.replace('tcontext=' + census_model.MANAGER_SID, 'tcontext=unconfined_u:unconfined_r:unconfined_t:s0')
                if profile else line.replace('ino=987', 'ino=988'))
    elif fault == 'unenforced':
        line = line.replace('apparmor="DENIED"', 'apparmor="ALLOWED"').replace('permissive=0', 'permissive=1')
    assert census_model.service_audit_denial(line, backend, '4321', evidence.target,
        evidence.account.pw_uid, profile=profile) is (fault is None)


@pytest.mark.parametrize('replacement', ['dev="otherfs"', ''])
def test_service_selinux_audit_refuses_wrong_or_missing_device(
        census_model, service_denial_evidence, replacement):
    evidence = service_denial_evidence
    line = evidence.audit('selinux').replace('dev="privatefs"', replacement)
    assert not census_model.service_audit_denial(line, 'selinux', '4321', evidence.target, 1234)


@pytest.mark.parametrize('case', ['private-name', 'canonical-path', 'wrong-name', 'conflicting-path'])
def test_service_selinux_audit_binds_private_copy_name_and_optional_canonical_path(
        census_model, service_denial_evidence, case):
    evidence = service_denial_evidence
    target = {**evidence.target, 'audit_name': '37'}
    line = evidence.audit('selinux').replace('name="private-denied"', 'name="37"')
    if case == 'canonical-path':
        line += ' path="' + target['path'] + '"'
    elif case == 'wrong-name':
        line = line.replace('name="37"', 'name="private-denied"')
    elif case == 'conflicting-path':
        line += ' path="/usr/bin/other"'
    assert census_model.service_audit_denial(line, 'selinux', '4321', target, 1234) is (
        case in ('private-name', 'canonical-path'))


@pytest.mark.parametrize('fault', [None, 'missing-loader', 'nonexecutable-loader', 'bad-elf',
                                  'truncated-loader', 'control-target', 'control-loader', 'garbage-loader'])
def test_service_target_measures_private_namespace_elf_and_loader(
        census_model, tmp_path, monkeypatch, fault):
    import hashlib
    import struct

    helper = census_model
    manager = tmp_path / 'manager'
    command, loader = tmp_path / 'program', tmp_path / 'loader'
    visible = manager / 'root' / command.relative_to('/')
    native = manager / 'root' / loader.relative_to('/')
    native.parent.mkdir(parents=True)
    interpreter = os.fsencode(loader) + b'\0'
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', header, 16, 3, 62, 1)
    struct.pack_into('<Q', header, 32, 64)
    struct.pack_into('<H', header, 52, 64)
    struct.pack_into('<HH', header, 54, 56, 1)
    program = bytearray(56)
    struct.pack_into('<I', program, 0, 3)
    struct.pack_into('<Q', program, 8, 120)
    struct.pack_into('<Q', program, 32, len(interpreter))
    payload = bytes(header + program) + interpreter
    loader_header = bytearray(header)
    struct.pack_into('<Q', loader_header, 32, 0)
    struct.pack_into('<H', loader_header, 56, 0)
    loader_payload = bytes(loader_header) + b'private native loader'
    command.write_bytes(payload + (b'control drift' if fault == 'control-target' else b''))
    command.chmod(0o755)
    loader.write_bytes(loader_payload + (b'control drift' if fault == 'control-loader' else b''))
    loader.chmod(0o755)
    visible.write_bytes(b'invalid' if fault == 'bad-elf' else
                        payload[:-1] if fault == 'truncated-loader' else payload)
    visible.chmod(0o755)
    if fault != 'missing-loader':
        native.write_bytes(b'garbage loader' if fault == 'garbage-loader' else loader_payload)
        native.chmod(0o644 if fault == 'nonexecutable-loader' else 0o755)
    info = visible.stat()
    mount = f'1 0 {os.major(info.st_dev)}:{os.minor(info.st_dev)} / / rw - tmpfs tmpfs rw'
    (manager / 'mountinfo').write_text(mount + '\n')
    if fault is not None:
        expected = FileNotFoundError if fault == 'missing-loader' else helper.guest.GuestError
        reasons = {'nonexecutable-loader': 'loader-not-executable', 'bad-elf': 'target-format',
                   'truncated-loader': 'elf-loader-missing', 'control-target': 'control-target-drift',
                   'control-loader': 'control-loader-drift', 'garbage-loader': 'loader-format'}
        with pytest.raises(expected, match=None if fault == 'missing-loader' else
                           'kiosk-service:' + reasons[fault]):
            helper.service_target(manager, str(command))
        return
    measured = helper.service_target(manager, str(command))
    entry = command.lstat()
    assert measured == {'path': str(command), 'device': info.st_dev, 'inode': info.st_ino,
        'sha256': hashlib.sha256(payload).hexdigest(), 'audit_device': 'tmpfs', 'mount': mount,
        'audit_name': command.name,
        'entry': {'device': entry.st_dev, 'inode': entry.st_ino, 'mode': entry.st_mode,
                  'uid': entry.st_uid, 'gid': entry.st_gid},
        'loader': {'path': str(loader), 'sha256': hashlib.sha256(loader_payload).hexdigest()}}


@pytest.mark.parametrize('bind_first', [False, True], ids=['root-first', 'bind-first'])
def test_service_target_file_bind_uses_backing_device_despite_anonymous_stat_device(
        census_model, tmp_path, monkeypatch, bind_first):
    import struct

    helper = census_model
    manager = tmp_path / 'manager'
    command = tmp_path / 'private program'
    visible = manager / 'root' / command.relative_to('/')
    visible.parent.mkdir(parents=True)
    # A static ELF-shaped target needs no interpreter or live executable reads.
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<Q', header, 32, 64)
    struct.pack_into('<HH', header, 54, 56, 1)
    payload = bytes(header) + bytes(56)
    for path in (command, visible):
        path.write_bytes(payload)
        path.chmod(0o755)
    backing = tmp_path / 'backing-block'
    backing.touch()
    sysfs = tmp_path / 'sysfs'
    (sysfs / '8:17').mkdir(parents=True)
    (sysfs / '8:17/uevent').write_text('MAJOR=8\nMINOR=17\nDEVNAME=private-disk1\n')
    monkeypatch.setattr(helper, 'Path', lambda value: sysfs if value == '/sys/dev/block' else
                        backing if value == '/dev/private-disk1' else Path(value))
    original_stat = Path.stat
    anonymous_device = os.makedev(0, 421)

    def metadata(path, *args, **kwargs):
        info = original_stat(path, *args, **kwargs)
        if path == backing:
            return SimpleNamespace(st_mode=stat.S_IFBLK | 0o600, st_rdev=os.makedev(8, 17))
        if path == visible:
            return SimpleNamespace(st_mode=info.st_mode, st_dev=anonymous_device, st_ino=info.st_ino)
        return info

    monkeypatch.setattr(Path, 'stat', metadata)
    root_mount = '1 0 0:7 / / rw - tmpfs tmpfs rw'
    escaped_target = str(command).replace(' ', r'\040')
    bind_mount = f'2 1 8:17 /subvolume/program {escaped_target} ro - btrfs /dev/private-disk1 ro'
    mounts = [bind_mount, root_mount] if bind_first else [root_mount, bind_mount]
    (manager / 'mountinfo').write_text('\n'.join(mounts) + '\n')
    measured = helper.service_target(manager, str(command))
    assert measured['device'] == anonymous_device
    assert measured['mount'] == bind_mount
    assert measured['audit_device'] == 'private-disk1'
    assert measured['audit_name'] == 'program'
    assert 'loader' not in measured


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('mode', ['transient', 'strict-profile', 'writable'])
@pytest.mark.parametrize('fault', [None, 'old-audit', 'replayed-audit', 'missing-time',
                                  'native-setup', 'executor-target', 'unit-replaced', 'target-replaced'])
def test_service_denial_composes_fresh_proofs_and_guards_owned_reset(
        census_model, service_denial_evidence, tmp_path, monkeypatch, backend, mode, fault):
    helper, evidence = census_model, service_denial_evidence
    strict = mode == 'strict-profile'
    stage = ('APPARMOR' if backend == 'apparmor' else 'SELINUX_CONTEXT') if strict else 'EXEC'
    status = (231 if backend == 'apparmor' else 229) if strict else 203
    setting = ('AppArmorProfile=unconfined' if backend == 'apparmor'
               else 'SELinuxContext=unconfined_u:unconfined_r:unconfined_t:s0') if strict else None
    row = evidence.native(stage)
    if fault == 'native-setup':
        row['MESSAGE'] = 'Failed to set up credentials: Permission denied'
    line = evidence.audit(backend, strict)
    if fault == 'old-audit':
        line = line.replace('100.001', '99.999')
    elif fault == 'missing-time':
        line = line.replace('audit(100.001:71): ', '')
    audit_reads = iter([line if fault == 'replayed-audit' else '', line])

    def wait_for(predicate, reason):
        helper.guest.require(predicate(), reason)

    monkeypatch.setitem(sys.modules, 'system_kiosk_platform', SimpleNamespace(
        settle_kernel_audit=lambda selected: None, kernel_audit=lambda selected: next(audit_reads),
        wait_for=wait_for))
    monkeypatch.setattr(helper, 'PROC', tmp_path / 'proc')
    monkeypatch.setattr(helper, 'manager_pid', lambda unit: 500)
    monkeypatch.setattr(helper, 'process_identity', lambda process: ('start', 1, ('1234',) * 4))
    targets = iter([evidence.target, {**evidence.target, 'sha256': 'replacement'}
                    if fault == 'target-replaced' else evidence.target])
    monkeypatch.setattr(helper, 'service_target', lambda manager, command: next(targets))
    monkeypatch.setattr(helper.time, 'time', lambda: 100)
    boot_file = tmp_path / 'boot-id'
    boot_file.write_text(evidence.boot)
    monkeypatch.setattr(helper, 'Path', lambda value: boot_file
                        if value == '/proc/sys/kernel/random/boot_id' else Path(value))
    properties = {'InvocationID': evidence.invocation, 'ExecMainPID': '4321',
                  'ExecMainCode': '1', 'ExecMainStatus': str(status), 'Result': 'exit-code',
                  'ActiveState': 'failed',
                  'ExecStart': '{ path=' + evidence.command[0] + ' ; argv[]=private ; pid=4321 ; code=exited ; }'}
    if fault == 'executor-target':
        properties['ExecStart'] = properties['ExecStart'].replace(evidence.command[0], '/usr/bin/other')
    commands, records = [], {}

    def user_command(account, command, *, check=True):
        commands.append(command)
        if '--property=InvocationID,ActiveState' in command:
            return b'InvocationID=\nActiveState=inactive\n'
        if any(value.startswith('--property=InvocationID,ExecMainPID,') for value in command):
            return ''.join(f'{key}={value}\n' for key, value in properties.items()).encode()
        if '--property=InvocationID' in command:
            return (('c' * 32 if fault == 'unit-replaced' else evidence.invocation) + '\n').encode()
        helper.guest.commands.last_returncode = status
        return b''

    def run(command):
        if command[0] == 'systemctl':
            return 'manager-invocation'
        if '--show-cursor' in command:
            return '-- cursor: private-cursor'
        assert '--after-cursor=private-cursor' in command
        return json.dumps(row)

    monkeypatch.setattr(helper, 'user_command', user_command)
    monkeypatch.setattr(helper.guest, 'run', run)
    monkeypatch.setattr(helper.guest, 'commands', SimpleNamespace(last_returncode=status))
    reasons = {'old-audit': 'kernel-denial-not-observed', 'replayed-audit': 'kernel-denial-not-observed',
               'missing-time': 'kernel-denial-not-observed', 'native-setup': 'native-denial-not-observed',
               'executor-target': 'executor-target', 'unit-replaced': 'unit-replaced',
               'target-replaced': 'target-changed'}
    if fault is None:
        helper.require_service_denial(evidence.account, backend, evidence.unit, evidence.command,
            records.__setitem__, setting=setting, writable=mode == 'writable')
        assert records['onpc.kiosk.service-denial.' + evidence.unit + '.kernel-denial'] == line
    else:
        with pytest.raises(helper.guest.GuestError, match='kiosk-service:' + reasons[fault]):
            helper.require_service_denial(evidence.account, backend, evidence.unit, evidence.command,
                records.__setitem__, setting=setting, writable=mode == 'writable')
    resets = [command for command in commands if 'reset-failed' in command]
    assert resets == ([] if fault == 'unit-replaced' else
                      [['/usr/bin/systemctl', '--user', 'reset-failed', evidence.unit]])
    launch = commands[1]
    if mode == 'writable':
        assert launch == ['/usr/bin/systemctl', '--user', 'start', evidence.unit]
    else:
        assert launch[:5] == ['/usr/bin/systemd-run', '--user', '--wait', '--pipe', '--unit=' + evidence.unit]
        assert launch[5:] == (['--property=' + setting] if strict else []) + evidence.command


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('retained_view,fault', [
    (retained_view, fault) for retained_view in (False, True)
    for fault in (None, 'sibling-label', 'sibling-uid', 'sibling-namespace',
                  'sibling-generation', 'host-namespace', 'invalid-generation',
                  'manager-replaced', 'exited', 'thread-replaced')
] + [(True, fault) for fault in (
    'marker-header', 'marker-version', 'marker-backend', 'marker-material', 'marker-view',
    'marker-extra-field', 'marker-missing-newline', 'marker-extra-line', 'sibling-view',
    'marker-lifecycle-changed', 'manager-marker-lifecycle-changed')])
def test_manager_reexec_observation_requires_each_live_thread_boundary(
        census_model, tmp_path, monkeypatch, backend, retained_view, fault):
    helper = census_model
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    manager = tmp_path / '42'
    namespace = 'mnt:[host]' if fault == 'host-namespace' else 'mnt:[private]'
    current_marker = 'ONPC-KIOSK-VIEW\t1\t' + backend + '\t' + 'a' * 64 + '\t' + 'b' * 64 + '\n'
    generation = current_marker if retained_view else 'a' * 64 + '\n'
    malformed = {
        'marker-header': current_marker.replace('ONPC-KIOSK-VIEW', 'ONPC-KIOSK-READY'),
        'marker-version': current_marker.replace('\t1\t', '\t2\t'),
        'marker-backend': current_marker.replace(backend, 'selinux' if backend == 'apparmor' else 'apparmor'),
        'marker-material': current_marker.replace('a' * 64, 'a' * 63),
        'marker-view': current_marker.replace('b' * 64, 'B' * 64),
        'marker-extra-field': current_marker.removesuffix('\n') + '\textra\n',
        'marker-missing-newline': current_marker.removesuffix('\n'),
        'marker-extra-line': current_marker + '\n',
        'invalid-generation': 'unconfined\n',
    }
    generation = malformed.get(fault, generation)
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    expected = 'onpc-kiosk-manager (enforce)' if backend == 'apparmor' else helper.MANAGER_SID
    marker_directory = 'root/usr/share/oh-no-parent-control/confinement/'
    marker = marker_directory + ('retained-view' if retained_view else 'generation')
    for target in (manager, manager / 'task/42', manager / 'task/43'):
        target.mkdir(parents=True, exist_ok=True)
        (target / 'stat').write_text('42 (fixture) S 1 ' + '0 ' * 17 + '100')
        (target / 'status').write_text('PPid:\t1\nUid:\t1002\t1002\t1002\t1002\n')
        (target / 'ns').mkdir()
        (target / 'ns/mnt').symlink_to('mnt:[other]' if target.name == '43' and
                                     fault == 'sibling-namespace' else namespace)
        (target / marker).parent.mkdir(parents=True)
        sibling_marker = current_marker.replace('a' * 64, 'c' * 64) if retained_view else 'b' * 64 + '\n'
        if fault == 'sibling-view':
            sibling_marker = current_marker.replace('b' * 64, 'c' * 64)
        (target / marker).write_text(sibling_marker if target.name == '43' and
                                   fault in ('sibling-generation', 'sibling-view') else generation)
        # The marker from the other format cannot authorize this observation.
        (target / (marker_directory + ('generation' if retained_view else 'retained-view'))).write_text(
            'unconfined\n' if retained_view else current_marker)
        (target / attribute).parent.mkdir(parents=True)
        (target / attribute).write_text('unconfined' if target.name == '43' and
                                       fault == 'sibling-label' else expected)
    if fault == 'sibling-uid':
        (manager / 'task/43/status').write_text('PPid:\t1\nUid:\t1002\t0\t0\t0\n')
    (tmp_path / '1/ns').mkdir(parents=True)
    (tmp_path / '1/ns/mnt').symlink_to('mnt:[host]')
    calls, closed = [], []
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda pid: 900)
    monkeypatch.setattr(helper.os, 'close', closed.append)
    monkeypatch.setattr(helper, 'exited', lambda fd: fault == 'exited')
    def manager_pid(unit):
        calls.append(unit)
        return 99 if fault == 'manager-replaced' and len(calls) > 1 else 42
    monkeypatch.setattr(helper, 'manager_pid', manager_pid)
    original = helper.census_thread_identity
    seen = {}
    def thread_identity(thread):
        value = original(thread)
        seen[thread] = seen.get(thread, 0) + 1
        if fault in ('marker-lifecycle-changed', 'manager-marker-lifecycle-changed') and (
                thread.name == '43' and seen[thread] > 1):
            target = manager if fault == 'manager-marker-lifecycle-changed' else thread
            (target / marker).write_text(current_marker.replace('b' * 64, 'c' * 64))
        return ('replacement', *value[1:]) if (fault == 'thread-replaced' and
                thread.name == '43' and seen[thread] > 1) else value
    monkeypatch.setattr(helper, 'census_thread_identity', thread_identity)
    options = {'retained_view': True} if retained_view else {}
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-confinement:manager-'):
            helper.manager_boundary(SimpleNamespace(pw_uid=1002), 'user@1002.service', backend,
                                    **options)
    else:
        result = helper.manager_boundary(SimpleNamespace(pw_uid=1002), 'user@1002.service', backend,
                                         **options)
        assert result == {'pid': 42, 'identity': ('100', 1, ('1002',) * 4),
                          'label': expected, 'namespace': namespace, 'generation': generation}
    assert closed == [900]


@pytest.mark.parametrize('fault', [None, 'exited', 'pid', 'starttime', 'namespace', 'invocation'])
def test_bootstrap_control_refuses_a_foreign_or_changed_manager_before_mutation(
        census_model, monkeypatch, fault):
    helper = census_model
    account = SimpleNamespace(pw_uid=1002)
    unit = 'user@1002.service'
    boundary = {'pid': 42, 'identity': ('100', 1, ('1002',) * 4),
                'label': helper.MANAGER_SID, 'namespace': 'mnt:[private]',
                'generation': 'ONPC-KIOSK-VIEW\t1\tselinux\t' + 'a' * 64 + '\t' + 'b' * 64 + '\n'}
    expected = {**boundary, 'invocation': 'b' * 32}
    observed = dict(boundary)
    if fault == 'pid':
        observed['pid'] = 43
    elif fault == 'starttime':
        observed['identity'] = ('101', 1, ('1002',) * 4)
    elif fault == 'namespace':
        observed['namespace'] = 'mnt:[foreign]'
    monkeypatch.setattr(helper, 'manager_boundary', Mock(return_value=observed))
    monkeypatch.setattr(helper, 'exited', Mock(return_value=fault == 'exited'))
    run = Mock(return_value='c' * 32 if fault == 'invocation' else expected['invocation'])
    monkeypatch.setattr(helper.guest, 'run', run)
    monkeypatch.setattr(helper.os, 'kill', killed := Mock())
    monkeypatch.setattr(helper.signal, 'pidfd_send_signal', signalled := Mock())
    if fault:
        with pytest.raises(helper.guest.GuestError):
            helper.bootstrap_manager_unchanged(account, unit, 'selinux', expected, 900)
    else:
        helper.bootstrap_manager_unchanged(account, unit, 'selinux', expected, 900)
    if fault == 'exited':
        helper.manager_boundary.assert_not_called()
    else:
        helper.manager_boundary.assert_called_once_with(account, unit, 'selinux', retained_view=True)
    # A reused PID or foreign invocation supplies no authority to stop, reload,
    # or signal a manager. Only read-only identity queries may have occurred.
    assert all(call.args[0] == ['systemctl', 'show', '--value',
                              '--property=InvocationID', unit]
               for call in run.call_args_list)
    killed.assert_not_called()
    signalled.assert_not_called()


@pytest.mark.parametrize('retained_view', [False, True])
@pytest.mark.parametrize('fault', [None, 'after-reexec', 'after-denial'])
def test_bootstrap_reexec_preserves_the_selected_marker_boundary(
        census_model, monkeypatch, retained_view, fault):
    helper = census_model
    account, unit = SimpleNamespace(pw_uid=1002), 'user@1002.service'
    marker = ('ONPC-KIOSK-VIEW\t1\tapparmor\t' + 'a' * 64 + '\t' + 'b' * 64 + '\n'
              if retained_view else 'a' * 64 + '\n')
    boundary = {'pid': 42, 'generation': marker}
    changed = {**boundary, 'generation': marker.replace('a' * 64, 'c' * 64)}
    observe = Mock(side_effect=[boundary,
        changed if fault == 'after-reexec' else boundary,
        changed if fault == 'after-denial' else boundary])
    monkeypatch.setattr(helper, 'manager_boundary', observe)
    monkeypatch.setattr(helper.guest, 'run', Mock(side_effect=['notify-reload', '59', '']))
    monkeypatch.setattr(helper, 'user_command', allowed := Mock(return_value=b'systemd 260'))
    monkeypatch.setattr(helper, 'require_service_denial', denied := Mock())
    record = Mock()
    if fault:
        with pytest.raises(helper.guest.GuestError, match='reexec-changed-manager-boundary'):
            helper.bootstrap_reexec(account, unit, 'apparmor', record, retained_view=retained_view)
        record.assert_not_called()
    elif retained_view:
        helper.bootstrap_reexec(account, unit, 'apparmor', record, retained_view=True)
    else:
        helper.bootstrap_reexec(account, unit, 'apparmor', record)
    expected_options = {'retained_view': True} if retained_view else {}
    assert observe.call_count == (2 if fault == 'after-reexec' else 3)
    for call in observe.call_args_list:
        assert call.args == (account, unit, 'apparmor') and call.kwargs == expected_options
    if fault == 'after-reexec':
        allowed.assert_not_called()
        denied.assert_not_called()
    else:
        denied.assert_called_once_with(account, 'apparmor',
            'onpc-confinement-after-reexec-denied.service', ['/bin/sh', '-c', 'exit 0'], record)


@pytest.mark.parametrize('kind,mode,uid,gid,text,accepted', [
    ('link', stat.S_IFLNK | 0o777, 0, 0, '/dev/null', True),
    ('link', stat.S_IFLNK | 0o777, 1002, 0, '/dev/null', False),
    ('link', stat.S_IFLNK | 0o777, 0, 1002, '/dev/null', False),
    ('link', stat.S_IFLNK | 0o777, 0, 0, '/foreign', False),
    ('link', stat.S_IFREG | 0o644, 0, 0, '/dev/null', False),
    ('file', stat.S_IFLNK | 0o777, 0, 0, '/dev/null', False),
    ('file', stat.S_IFREG | 0o755, 0, 0, '', True),
    ('file', stat.S_IFREG | 0o775, 0, 0, '', False),
    ('tree', stat.S_IFDIR | 0o755, 0, 0, '', True),
    ('tree', stat.S_IFDIR | 0o757, 0, 0, '', False),
])
def test_bootstrap_source_trust_preserves_exact_owned_links_and_rejects_writable_sources(
        census_model, monkeypatch, kind, mode, uid, gid, text, accepted):
    helper = census_model
    path = Path('/private-view/usr/share/user-units/masked.service')
    monkeypatch.setattr(helper.os, 'readlink', Mock(return_value=text))
    info = [1, 2, mode, uid, gid, 0, 0, 0, 1]
    if accepted:
        helper.bootstrap_source_trust(path, kind, info, '/dev/null')
    else:
        with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:source-writable'):
            helper.bootstrap_source_trust(path, kind, info, '/dev/null')


@pytest.mark.parametrize('fault', [None, 'executable', 'library', 'link-text', 'link-owner',
                                 'link-group', 'completed', 'marker', 'nested-inode',
                                 'nested-mount', 'writable', 'extra-mount', 'manager-link',
                                 'marker-material', 'marker-backend', 'marker-view',
                                 'marker-mode', 'marker-owner', 'ambient-omitted',
                                 'ambient-link-omitted', 'ambient-permission',
                                 'ambient-stale-mount', 'ambient-required',
                                 'ambient-native', 'ambient-runtime', 'ambient-vendor',
                                 'ambient-payload', 'manager-ambient',
                                 'ambient-directory-masked', 'ambient-directory-populated',
                                 'ambient-directory-mode', 'ambient-directory-owner',
                                 'ambient-directory-group', 'ambient-directory-nlink',
                                 'ambient-directory-foreign-device', 'ambient-directory-stale-mount',
                                 'ambient-directory-nonambient', 'ambient-directory-required'])
def test_bootstrap_gate_observer_accepts_fresh_links_but_preserves_bound_sources_and_manager(
        census_model, tmp_path, monkeypatch, fault):
    """Real private dentries, with finite proc, root, record and permission doubles."""
    helper = census_model
    manager, gate = tmp_path / 'manager', tmp_path / 'gate'
    ambient_directory = bool(fault and fault.startswith('ambient-directory-'))
    paths = {'executable': '/usr/lib/systemd/systemd',
             'library': '/usr/lib/systemd/libsystemd-shared.so',
             'link': '/usr/lib/systemd/user/masked.service',
             'nested': '/usr/lib/vendor/nested.so',
             'ambient': '/usr/lib/games' if ambient_directory else '/usr/bin/VGAuthService'}
    marker_path = '/usr/share/oh-no-parent-control/confinement/retained-view'
    ambient_kind = 'directory' if ambient_directory else (
        'link' if fault == 'ambient-link-omitted' else 'file')
    def actual(process, path):
        return process / 'root' / path.lstrip('/')
    for path in paths.values():
        original, retained = actual(manager, path), actual(gate, path)
        original.parent.mkdir(parents=True, exist_ok=True)
        retained.parent.mkdir(parents=True, exist_ok=True)
        if path == paths['ambient'] and ambient_directory:
            original.mkdir(mode=0o755)
            retained.mkdir(mode=0o755)
            if fault == 'ambient-directory-populated':
                (retained / 'unexpected').write_bytes(b'not an empty mask\n')
            elif fault == 'ambient-directory-mode':
                retained.chmod(0o750)
        elif path == paths['link'] or (path == paths['ambient'] and ambient_kind == 'link'):
            original.symlink_to('/dev/null')
            retained.symlink_to('/dev/null')
        else:
            original.write_bytes(b'original measured source\n')
            original.chmod(0o755)
            # A hard link supplies a real shared inode without host mounts.
            os.link(original, retained)
    boot = tmp_path / 'boot'
    boot.write_text('private-boot\n')
    native_object = helper.bootstrap_object
    def observe(path, *, follow=False):
        result = native_object(path, follow=follow)
        result[3:5] = [0, 0]
        if fault in ('link-owner', 'link-group') and path == actual(gate, paths['link']):
            result[3 if fault == 'link-owner' else 4] = 1002
        if fault == 'marker-owner' and path == actual(gate, marker_path):
            result[3] = 1002
        if ambient_directory and path == actual(gate, paths['ambient']):
            if fault in ('ambient-directory-owner', 'ambient-directory-group'):
                result[3 if fault == 'ambient-directory-owner' else 4] = 1002
            elif fault == 'ambient-directory-nlink':
                result[8] = 3
            elif fault == 'ambient-directory-foreign-device':
                result[0] += 1
        return result
    monkeypatch.setattr(helper, 'bootstrap_object', observe)
    material_bytes = b'{"private":"material"}\n'
    material = hashlib.sha256(b'ONPC-KIOSK-MATERIAL\0' +
                              len(material_bytes).to_bytes(8, 'big') + material_bytes).hexdigest()
    lines = ['\t'.join(['ONPC-KIOSK-RECEIPT', '2', 'V', 'apparmor', 'manager', material, '-', 'a' * 64])]
    ambient_class = fault.removeprefix('ambient-') if fault in (
        'ambient-native', 'ambient-runtime', 'ambient-vendor', 'ambient-payload') else 'ambient'
    if fault == 'ambient-directory-nonambient':
        ambient_class = 'vendor'
    nodes = [('/usr', 'tree', 1, 'skeleton'), (paths['executable'], 'file', 1, 'native'),
             (paths['library'], 'file', 1, 'native'), (paths['link'], 'link', 1, 'vendor'),
             (paths['ambient'], ambient_kind,
              int(fault in ('ambient-required', 'ambient-directory-required')), ambient_class)]
    for slot, (path, kind, required, source_class) in enumerate(nodes):
        info = observe(actual(manager, path))
        lines.append('\t'.join(map(str, ['N', path, kind, required, source_class, 'initial',
            'manager', slot, *info[:2], *info[:2], info[5], info[6], info[7], info[2],
            info[3], info[4], info[8], helper.guest.sha(actual(manager, path)) if kind == 'file' else '-',
            '-', '/dev/null' if kind == 'link' else '-', int(kind != 'link')])))
    info = observe(actual(manager, paths['nested']))
    lines.append('\t'.join(map(str, ['C', 0, paths['nested'], *info[:2], *info[:2],
                                    info[5], info[6], info[7], info[2], info[3], info[4]])))
    encoded = ('\n'.join(lines) + '\n').encode()
    view = hashlib.sha256(b'ONPC-KIOSK-VIEW\0' + len(encoded).to_bytes(8, 'big') + encoded).hexdigest()
    records = tmp_path / 'records' / view
    records.mkdir(parents=True)
    (records / 'material.json').write_bytes(material_bytes)
    (records / 'view').write_bytes(encoded)
    (records / 'pins').write_text('private pins\n')
    (records / 'runtime.json').write_text('{}\n')
    marker = actual(manager, marker_path)
    marker.parent.mkdir(parents=True)
    marker.write_text('\t'.join(['ONPC-KIOSK-VIEW', '1', 'apparmor', material, view]) + '\n')
    marker.chmod(0o444)
    actual(gate, marker_path).parent.mkdir(parents=True)
    gate_marker = actual(gate, marker_path)
    # I is invocation-private: its marker names I, while V's completed records
    # and source inodes stay original. No completed I directory exists.
    gate_marker.write_text('\t'.join(['ONPC-KIOSK-VIEW', '1', 'apparmor', material, 'c' * 64]) + '\n')
    gate_marker.chmod(0o444)
    (records / 'ready').write_text('\t'.join(map(str, ['ONPC-KIOSK-READY', '2', material, view,
        helper.guest.sha(records / 'pins'), 'private-boot', *observe(records)[:2],
        *observe(actual(manager, '/usr'))[:2], *observe(marker)[:2], 41, 42])) + '\n')
    for item in records.iterdir():
        item.chmod(0o600)
    def translated(value):
        if str(value) == '/run/oh-no-parent-control-confinement':
            return records.parent
        if str(value) == '/proc/sys/kernel/random/boot_id':
            return boot
        return Path(value)
    monkeypatch.setattr(helper, 'Path', translated)
    mounts = {path: {'id': 41 + slot, 'options': ['ro'], 'filesystem': 'private',
                     'superoptions': ['ro']} for slot, path in enumerate(
                         ['/usr', paths['executable'], paths['library'], paths['nested'],
                          paths['ambient']])}
    if ambient_kind == 'link':
        del mounts[paths['ambient']]
    def mounted(process):
        result = {path: dict(value) for path, value in mounts.items()}
        if process == gate:
            if fault == 'nested-mount':
                del result[paths['nested']]
            elif fault == 'extra-mount':
                result['/usr/foreign'] = dict(result['/usr'])
            if fault in ('ambient-omitted', 'ambient-required', 'ambient-native',
                         'ambient-runtime', 'ambient-vendor', 'ambient-payload'):
                del result[paths['ambient']]
            if ambient_directory and fault != 'ambient-directory-stale-mount':
                del result[paths['ambient']]
        return result
    monkeypatch.setattr(helper, 'bootstrap_mounts', mounted)
    source = helper.bootstrap_view(manager)
    invocation_marker = observe(gate_marker) + [helper.guest.sha(gate_marker)]
    assert observe(actual(gate, paths['link']))[:2] != observe(actual(manager, paths['link']))[:2]
    assert (observe(actual(gate, paths['ambient']))[:2] ==
            observe(actual(manager, paths['ambient']))[:2]) is (ambient_kind == 'file')
    if ambient_directory:
        if fault == 'ambient-directory-masked':
            result = helper.bootstrap_view(gate, source=source, invocation_marker=invocation_marker)
            assert result['masked_ambient'] == [paths['ambient']]
            assert result['omitted_ambient'] == []
            assert paths['ambient'] not in result['objects']
            assert paths['ambient'] not in result['mounts']
            assert paths['ambient'] in source['objects']
            assert paths['ambient'] in source['mounts']
            assert result['sources'] == source['sources']
            assert result['coverage'] == source['coverage']
            assert result['completed'] == source['completed']
            assert result['invocation_view'] == 'c' * 64 and result['view'] == view
        else:
            reason = 'mounted-source-inode' if fault in (
                'ambient-directory-nonambient', 'ambient-directory-required') else 'ambient-directory-mask'
            with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:' + reason):
                helper.bootstrap_view(gate, source=source, invocation_marker=invocation_marker)
        assert helper.bootstrap_view(manager) == source
        return
    if fault == 'ambient-permission':
        inaccessible = actual(gate, paths['ambient'])
        failure = PermissionError(13, 'private ambient leaf inaccessible', str(inaccessible))
        def denied(path, *, follow=False):
            if path == inaccessible:
                raise failure
            return observe(path, follow=follow)
        with monkeypatch.context() as guard:
            guard.setattr(helper, 'bootstrap_object', denied)
            with pytest.raises(PermissionError) as caught:
                helper.bootstrap_view(gate, source=source, invocation_marker=invocation_marker)
        assert caught.value is failure
        assert helper.bootstrap_view(manager) == source
        return
    if fault == 'manager-ambient':
        actual(manager, paths['ambient']).unlink()
        # Narrowing belongs to I only; the original V must still be observable.
        with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:mounted-source-missing'):
            helper.bootstrap_view(manager)
        return
    if fault and fault.startswith('ambient-'):
        actual(gate, paths['ambient']).unlink()
        if fault not in ('ambient-omitted', 'ambient-link-omitted', 'ambient-stale-mount'):
            # Neither required ambient nor nonambient sources may disappear,
            # even when their old bind mount is absent from the invocation.
            with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:mounted-source-missing'):
                helper.bootstrap_view(gate, source=source, invocation_marker=invocation_marker)
            return
    elif fault in ('executable', 'library', 'nested-inode'):
        path = actual(gate, paths['nested' if fault == 'nested-inode' else fault])
        contents = path.read_bytes()
        path.unlink()
        path.write_bytes(contents)
        path.chmod(0o755)
    elif fault == 'link-text':
        actual(gate, paths['link']).unlink()
        actual(gate, paths['link']).symlink_to('/foreign')
    elif fault == 'completed':
        (records / 'runtime.json').write_text('{"changed":true}\n')
    elif fault == 'marker':
        path = actual(gate, marker_path)
        contents = path.read_bytes()
        path.unlink()
        path.write_bytes(contents)
        path.chmod(0o444)
    elif fault in ('marker-material', 'marker-backend', 'marker-view'):
        values = gate_marker.read_text().rstrip('\n').split('\t')
        values[{'marker-material': 3, 'marker-backend': 2, 'marker-view': 4}[fault]] = {
            'marker-material': 'd' * 64, 'marker-backend': 'selinux', 'marker-view': view}[fault]
        gate_marker.chmod(0o644)
        gate_marker.write_text('\t'.join(values) + '\n')
        gate_marker.chmod(0o444)
        # Even a stable caller snapshot cannot authorize another M/backend
        # or an old V marker masquerading as the current invocation.
        invocation_marker = observe(gate_marker) + [helper.guest.sha(gate_marker)]
    elif fault == 'marker-mode':
        gate_marker.chmod(0o644)
    elif fault == 'writable':
        actual(gate, paths['executable']).chmod(0o777)
    if fault not in (None, 'manager-link', 'ambient-omitted', 'ambient-link-omitted'):
        reasons = {'executable': 'mounted-source-inode', 'library': 'mounted-source-inode',
                   'link-text': 'mounted-link', 'link-owner': 'source-writable',
                   'link-group': 'source-writable', 'completed': 'retained-view-not-manager-source',
                   'marker': 'invocation-marker-changed', 'nested-inode': 'nested-coverage',
                   'nested-mount': 'nested-coverage', 'writable': 'source-writable',
                   'extra-mount': 'unexpected-nested-mount',
                   'ambient-stale-mount': 'unexpected-nested-mount',
                   'marker-material': 'view-header',
                   'marker-backend': 'view-header',
                   'marker-view': 'invocation-marker-changed', 'marker-mode': 'marker-trust',
                   'marker-owner': 'marker-trust'}
        with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:' + reasons[fault]):
            helper.bootstrap_view(gate, source=source, invocation_marker=invocation_marker)
        return
    result = helper.bootstrap_view(gate, source=source, invocation_marker=invocation_marker)
    assert result['invocation_view'] == 'c' * 64 and result['view'] == view
    assert result['marker'] != source['marker']
    assert result['sources'] == source['sources']
    assert result['masked_ambient'] == []
    assert result['objects'][paths['link']] != source['objects'][paths['link']]
    if fault in ('ambient-omitted', 'ambient-link-omitted'):
        assert result['omitted_ambient'] == [paths['ambient']]
        assert paths['ambient'] not in result['objects']
        assert paths['ambient'] not in result['mounts']
        assert paths['ambient'] in source['objects']
        assert (paths['ambient'] in source['mounts']) is (ambient_kind == 'file')
    else:
        assert result['omitted_ambient'] == []
        assert result['objects'][paths['ambient']] == source['objects'][paths['ambient']]
    manager_result = helper.bootstrap_view(manager)
    if fault == 'ambient-omitted':
        # Removing the gate hard link changes the real shared inode's ctime
        # and link count, while the manager dentry remains the original source.
        manager_ambient = manager_result['objects'][paths['ambient']]
        assert manager_ambient[:2] == source['objects'][paths['ambient']][:2]
        assert manager_result == dict(source, objects=dict(source['objects'], **{
            paths['ambient']: manager_ambient}))
    else:
        assert manager_result == source
    if fault == 'manager-link':
        path = actual(manager, paths['link'])
        # Hold the old dentry so inode reuse cannot mask the replacement.
        descriptor = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            path.unlink()
            path.symlink_to('/dev/null')
            assert helper.bootstrap_view(manager) != source
        finally:
            os.close(descriptor)


@pytest.mark.parametrize('kind', [socket.SOCK_DGRAM, socket.SOCK_STREAM])
def test_bootstrap_logger_socket_probes_only_a_duplicate_and_retains_caller_flags(
        census_model, short_runtime, monkeypatch, kind):
    helper = census_model
    endpoint, alias = short_runtime / 'logger', short_runtime / 'dev-log'
    with socket.socket(socket.AF_UNIX, kind) as server, socket.socket(socket.AF_UNIX, kind) as client:
        server.bind(str(endpoint))
        if kind == socket.SOCK_STREAM:
            server.listen(1)
        alias.symlink_to(endpoint)
        client.connect(str(alias))
        connected_peer = client.getpeername()
        original = helper.bootstrap_descriptors(helper.PROC / 'self')[str(client.fileno())]
        duplicated = []
        native_fcntl = fcntl.fcntl
        def command(fd, operation, *args):
            result = native_fcntl(fd, operation, *args)
            if operation == fcntl.F_DUPFD_CLOEXEC:
                duplicated.append(result)
            return result
        monkeypatch.setattr(helper.fcntl, 'fcntl', command)
        observed = helper.bootstrap_logger_endpoint(alias)
        receipt = helper.bootstrap_logger_socket(client.fileno(), observed)
        assert receipt == {'fd': client.fileno(), 'socket_type': kind, 'peer': connected_peer,
                           'endpoint': observed, 'descriptor': original}
        assert helper.bootstrap_descriptors(helper.PROC / 'self')[str(client.fileno())] == original
        assert client.getpeername() == connected_peer
        assert Path(connected_peer).resolve(strict=True) == endpoint
        assert len(duplicated) == 1
        with pytest.raises(OSError):
            os.fstat(duplicated[0])


@pytest.mark.parametrize('fault', [None, 'unconnected', 'extra', 'ambiguous', 'inheritable'])
def test_bootstrap_logger_eager_setup_requires_one_verified_socket_and_no_unknown_fd(
        census_model, short_runtime, monkeypatch, fault):
    from contextlib import ExitStack
    helper = census_model
    endpoint = short_runtime / 'logger'
    with ExitStack() as resources:
        server = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
        server.bind(str(endpoint))
        clients = []
        def eager(_ident, options, facility):
            assert options == 0x08 and facility == 10 << 3
            for _ in range(2 if fault == 'ambiguous' else 1):
                client = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
                clients.append(client)
                if fault != 'unconnected':
                    client.connect(str(endpoint))
                if fault == 'inheritable':
                    os.set_inheritable(client.fileno(), True)
            if fault == 'extra':
                resources.enter_context(open('/dev/null', 'rb'))
        library = SimpleNamespace(openlog=Mock(side_effect=eager), closelog=Mock())
        monkeypatch.setattr(helper.ctypes, 'CDLL', Mock(return_value=library))
        if fault:
            with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:logger-'):
                helper.bootstrap_logger_prepare(endpoint)
        else:
            receipt = helper.bootstrap_logger_prepare(endpoint)
            assert receipt['fd'] == clients[0].fileno()
            assert receipt['introduced'] is True
            assert receipt['socket_type'] == socket.SOCK_DGRAM
            census = helper.bootstrap_descriptors(helper.PROC / 'self')
            assert receipt['descriptor'] == census[str(clients[0].fileno())]
            helper.bootstrap_logger_validate(receipt, census, path=endpoint)
            # A receipt is bounded scenario data, leaving the unchanged shared
            # admission event's 4096-byte writer/reader checks in place.
            assert len(json.dumps(receipt).encode()) < 1024
        library.openlog.assert_called_once_with(None, 0x08, 10 << 3)
        library.closelog.assert_not_called()
        for client in clients:
            assert client.fileno() >= 0 and stat.S_ISSOCK(os.fstat(client.fileno()).st_mode)


@pytest.mark.parametrize('fault', ['constructor', 'peer'])
def test_bootstrap_logger_socket_failure_closes_duplicate_and_preserves_original(
        census_model, short_runtime, monkeypatch, fault):
    helper = census_model
    endpoint = short_runtime / 'logger'
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server, socket.socket(
            socket.AF_UNIX, socket.SOCK_DGRAM) as client:
        server.bind(str(endpoint))
        client.connect(str(endpoint))
        original = os.fstat(client.fileno())
        owned = []
        native_fcntl = fcntl.fcntl
        def duplicate(fd, operation, *args):
            result = native_fcntl(fd, operation, *args)
            if operation == fcntl.F_DUPFD_CLOEXEC:
                owned.append(result)
            return result
        monkeypatch.setattr(helper.fcntl, 'fcntl', duplicate)
        failure = OSError(5, 'owned socket probe failed')
        if fault == 'constructor':
            monkeypatch.setattr(helper.socket, 'socket', Mock(side_effect=failure))
        else:
            class FailedSocket:
                family = socket.AF_UNIX
                def __init__(self, *, fileno):
                    self.fd = fileno
                def getsockopt(self, *_):
                    return socket.SOCK_DGRAM
                def getpeername(self):
                    raise failure
                def close(self):
                    os.close(self.fd)
            monkeypatch.setattr(helper.socket, 'socket', FailedSocket)
        with pytest.raises(OSError) as caught:
            helper.bootstrap_logger_socket(client.fileno(), helper.bootstrap_logger_endpoint(endpoint))
        assert caught.value is failure
        assert os.fstat(client.fileno()) == original
        assert len(owned) == 1
        with pytest.raises(OSError):
            os.fstat(owned[0])


@pytest.mark.parametrize('fault', ['fd', 'identity', 'flags', 'peer', 'endpoint', 'type'])
def test_bootstrap_logger_parent_receipt_requires_independent_endpoint_and_exact_fd(
        census_model, short_runtime, fault):
    helper = census_model
    endpoint, other = short_runtime / 'logger', short_runtime / 'other'
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server, socket.socket(
            socket.AF_UNIX, socket.SOCK_DGRAM) as client, socket.socket(
            socket.AF_UNIX, socket.SOCK_DGRAM) as foreign:
        server.bind(str(endpoint))
        foreign.bind(str(other))
        client.connect(str(endpoint))
        receipt = helper.bootstrap_logger_socket(client.fileno(), helper.bootstrap_logger_endpoint(endpoint))
        receipt['introduced'] = False
        census = helper.bootstrap_descriptors(helper.PROC / 'self')
        receipt['descriptor'] = census[str(client.fileno())].copy()
        if fault == 'fd':
            receipt['fd'] += 10000
        elif fault == 'identity':
            receipt['descriptor'][1] += 1
        elif fault == 'flags':
            census[str(client.fileno())] = [*receipt['descriptor']]
            census[str(client.fileno())][3] &= ~os.O_CLOEXEC
            receipt['descriptor'] = census[str(client.fileno())].copy()
        elif fault == 'peer':
            receipt['peer'] = str(other)
        elif fault == 'endpoint':
            receipt['endpoint']['identity'][1] += 1
        else:
            receipt['socket_type'] = socket.SOCK_RAW
        with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:logger-'):
            helper.bootstrap_logger_validate(receipt, census, path=endpoint)
        assert client.getpeername() == str(endpoint)


@pytest.mark.parametrize('case', ['stable', 'renewed', 'preexisting-stable', 'preexisting-renewed',
                                 'moved', 'peer', 'type', 'endpoint', 'caller', 'extra',
                                 'missing-lease', 'post-error'])
def test_bootstrap_logger_renewal_is_only_its_fixture_owned_fd_with_one_native_lease(
        census_model, short_runtime, monkeypatch, case):
    from contextlib import ExitStack
    helper = census_model
    endpoint, foreign_endpoint = short_runtime / 'logger', short_runtime / 'foreign'
    with ExitStack() as resources:
        server = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
        foreign = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
        server.bind(str(endpoint))
        foreign.bind(str(foreign_endpoint))
        sentry = resources.enter_context(open('/dev/null', 'rb'))
        clients = []
        def create_logger():
            client = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
            client.connect(str(endpoint))
            clients.append(client)
        preexisting = case.startswith('preexisting-')
        if preexisting:
            create_logger()
        library = SimpleNamespace(openlog=Mock(side_effect=lambda *_: None if preexisting else create_logger()))
        monkeypatch.setattr(helper.ctypes, 'CDLL', Mock(return_value=library))
        original = helper.bootstrap_logger_prepare(endpoint)
        assert original['introduced'] is (not preexisting)
        logger_fd = original['fd']
        before = helper.bootstrap_descriptors(helper.PROC / 'self')
        if case not in ('stable', 'preexisting-stable'):
            # Only our explicitly owned logger number is renewed. The actual
            # kernel socket inode changes; every unrelated caller FD stays live.
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as replacement:
                replacement.connect(str(foreign_endpoint if case == 'peer' else endpoint))
                os.dup2(replacement.fileno(), logger_fd, inheritable=False)
        with monkeypatch.context() as guard:
            guard.setattr(helper, 'bootstrap_descriptors', Mock(side_effect=AssertionError('no post-PAM proc census')))
            current = helper.bootstrap_logger_after(original)
        if case == 'type':
            current['socket_type'] = socket.SOCK_STREAM
        elif case == 'moved':
            current['fd'] += 10000
        elif case == 'post-error':
            current = {'error': {'type': 'PermissionError', 'errno': 13, 'category': 'socket-probe'}}
        elif case == 'endpoint':
            endpoint.unlink()
            changed = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
            changed.bind(str(endpoint))
        elif case == 'extra':
            unexpected = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
            unexpected.connect(str(endpoint))
        after = helper.bootstrap_descriptors(helper.PROC / 'self')
        if case == 'caller':
            after[str(sentry.fileno())] = after[str(sentry.fileno())].copy()
            after[str(sentry.fileno())][1] += 1
        if case != 'missing-lease':
            # Finite parent-protocol fixture for the native lease slot. All
            # logger/caller identities above come from actual private FDs.
            after['2147483646'] = [0, 1, stat.S_IFREG | 0o600, os.O_RDWR | os.O_CLOEXEC,
                                  '/run/oh-no-parent-control-kiosk-admission.lock']
        if case in ('stable', 'renewed', 'preexisting-stable'):
            helper.bootstrap_logger_transition(original, current, before, after, path=endpoint)
            assert (original['descriptor'][1] != current['descriptor'][1]) is (case == 'renewed')
        else:
            with pytest.raises(helper.guest.GuestError, match='kiosk-bootstrap:'):
                helper.bootstrap_logger_transition(original, current, before, after, path=endpoint)
        assert len(json.dumps({'logger': original, 'logger_after': current}).encode()) < 2048
        assert os.fstat(sentry.fileno())
        assert clients[0].fileno() == logger_fd


@pytest.mark.parametrize('fault', ['fork', 'pidfd'])
@pytest.mark.parametrize('route', ['pam-witness', 'apparmor-service', 'selinux-service',
                                   'apparmor-manager-pam'])
def test_bootstrap_pam_witness_closes_channels_and_reaps_only_its_direct_child_on_failure(
        census_model, tmp_path, monkeypatch, fault, route):
    helper = census_model
    descriptors = []
    pipe2, opened = os.pipe2, os.open
    read_text = Path.read_text
    def config(path, *args, **kwargs):
        if str(path) == '/usr/share/oh-no-parent-control/confinement/config.json':
            return '{"backend":"apparmor"}'
        return read_text(path, *args, **kwargs)
    def pipe(flags):
        pair = pipe2(flags)
        descriptors.extend(pair)
        return pair
    def sentry(path, flags, *args, **kwargs):
        fd = opened(path, flags, *args, **kwargs)
        descriptors.append(fd)
        return fd
    monkeypatch.setattr(Path, 'read_text', config)
    monkeypatch.setattr(helper.os, 'pipe2', pipe)
    monkeypatch.setattr(helper.os, 'open', sentry)
    original = OSError('owned ' + fault + ' failure')
    monkeypatch.setattr(helper.os, 'fork', Mock(
        side_effect=original if fault == 'fork' else None, return_value=41001))
    acquire = Mock(side_effect=original)
    monkeypatch.setattr(helper.os, 'pidfd_open', acquire)
    monkeypatch.setattr(helper.os, 'kill', killed := Mock())
    monkeypatch.setattr(helper.os, 'waitpid', waited := Mock(return_value=(41001, 0)))
    monkeypatch.setattr(helper.signal, 'pidfd_send_signal', signalled := Mock())
    account = SimpleNamespace(pw_uid=1002, pw_gid=1002)
    user = Mock(return_value=b'InvocationID=\nActiveState=inactive\n')
    monkeypatch.setattr(helper, 'user_command', user)
    if route == 'apparmor-manager-pam':
        manager = tmp_path / 'proc/42'
        (manager / 'ns').mkdir(parents=True)
        (manager / 'ns/mnt').write_bytes(b'private namespace descriptor')
        marker = manager / 'root/usr/share/oh-no-parent-control/confinement/retained-view'
        marker.parent.mkdir(parents=True)
        marker.write_text('ONPC-KIOSK-VIEW\t1\tapparmor\t' + 'b' * 64 + '\t' + 'a' * 64 + '\n')
        monkeypatch.setattr(helper, 'PROC', tmp_path / 'proc')
        monkeypatch.setattr(helper, 'manager_pid', Mock(return_value=42))
        monkeypatch.setattr(helper.ctypes, 'CDLL', Mock(return_value=SimpleNamespace(
            aa_change_profile=Mock(), setns=Mock())))
    record = Mock()
    with pytest.raises(OSError) as caught:
        if route == 'pam-witness':
            helper.bootstrap_pam_witness(account, tmp_path,
                                         ['/usr/lib/systemd/systemd', '--version'], record,
                                         service='systemd-user')
        else:
            helper.bootstrap_service_entrypoint(account,
                'selinux' if route == 'selinux-service' else 'apparmor',
                '/usr/lib/systemd/systemd', {'view': 'a' * 64}, record,
                pam_route=route == 'apparmor-manager-pam', manager_pid_value=42)
    assert caught.value is original
    assert descriptors
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)
    if fault == 'fork':
        acquire.assert_not_called()
        killed.assert_not_called()
        waited.assert_not_called()
    else:
        acquire.assert_called_once_with(41001)
        killed.assert_called_once_with(41001, helper.signal.SIGKILL)
        waited.assert_called_once_with(41001, 0)
    signalled.assert_not_called()
    record.assert_not_called()
    if route in ('apparmor-service', 'selinux-service'):
        user.assert_called_once_with(account, ['/usr/bin/systemctl', '--user', 'show',
            'onpc-bootstrap-systemd.service', '--property=InvocationID,ActiveState'], check=False)
    else:
        user.assert_not_called()


@pytest.mark.parametrize('state', ['inactive', 'active'])
def test_bootstrap_service_entrypoint_preserves_an_existing_invocation_before_allocating(
        census_model, monkeypatch, state):
    helper = census_model
    account = SimpleNamespace(pw_uid=1002)
    user = Mock(return_value=('InvocationID=' + 'a' * 32 + '\nActiveState=' + state + '\n').encode())
    monkeypatch.setattr(helper, 'user_command', user)
    monkeypatch.setattr(helper.os, 'pipe2', allocated := Mock())
    monkeypatch.setattr(helper.os, 'fork', forked := Mock())
    monkeypatch.setattr(helper.os, 'pidfd_open', pinned := Mock())
    monkeypatch.setattr(helper.os, 'kill', killed := Mock())
    monkeypatch.setattr(helper.signal, 'pidfd_send_signal', signalled := Mock())
    record = Mock()
    with pytest.raises(helper.guest.GuestError, match='entrypoint-unit-already-active'):
        helper.bootstrap_service_entrypoint(account, 'apparmor', '/usr/lib/systemd/systemd',
                                             {}, record)
    user.assert_called_once_with(account, ['/usr/bin/systemctl', '--user', 'show',
        'onpc-bootstrap-systemd.service', '--property=InvocationID,ActiveState'], check=False)
    for operation in (allocated, forked, pinned, killed, signalled, record):
        operation.assert_not_called()


@pytest.mark.parametrize('diagnostic_fault', [None, 'read', 'record', 'audit'])
def test_bootstrap_start_preserves_first_failure_and_bounds_its_diagnostics(
        census_model, monkeypatch, diagnostic_fault):
    helper = census_model
    original = helper.guest.GuestError('original-manager-start')
    unit = 'user@1002.service'
    calls = []

    def run(command, *, timeout):
        calls.append((command, timeout))
        if command[:2] == ['systemctl', 'start']:
            raise original
        assert timeout == 10
        if diagnostic_fault == 'read':
            raise OSError('diagnostic read failed')
        return 'x' * 70000

    monkeypatch.setattr(helper.guest, 'run', run)
    audit = Mock(side_effect=OSError('audit unavailable') if diagnostic_fault == 'audit' else None,
                 return_value='k' * 70000)
    monkeypatch.setitem(sys.modules, 'system_kiosk_platform', SimpleNamespace(kernel_audit=audit))
    record = Mock(side_effect=OSError('record unavailable') if diagnostic_fault == 'record' else None)
    with pytest.raises(helper.guest.GuestError) as caught:
        helper.bootstrap_start_manager(unit, 'selinux', record)
    assert caught.value is original
    assert calls[0] == (['systemctl', 'start', unit], 75)
    assert all(command[0] in ('systemctl', 'journalctl') for command, _ in calls[1:])
    if diagnostic_fault != 'record':
        assert calls[1:] == [
            (['systemctl', 'show', unit,
              '--property=InvocationID,MainPID,ActiveState,SubState,Result,ExecMainStatus'], 10),
            (['journalctl', '--no-pager', '--utc', '-b', '-u', unit,
              '-n', '100', '-o', 'short-precise'], 10),
        ]
        audit.assert_called_once_with('selinux')
    assert all(len(call.args[1]) <= 65536 for call in record.call_args_list)


@pytest.mark.parametrize('directory', [True, False])
@pytest.mark.parametrize('body_error', [False, True])
def test_sibling_replacement_restores_exact_original_inode_and_content(
        census_model, tmp_path, monkeypatch, directory, body_error):
    helper = census_model
    monkeypatch.setattr(helper, 'SIBLING_PARENT', tmp_path)
    monkeypatch.setattr(helper.os, 'chown', lambda *args, **kwargs: None)
    path = tmp_path / 'owned'
    original = helper.sibling_create(path, 0o777 if directory else 0o644,
                                    os.getuid(), os.getgid(), b'original', directory=directory)
    row = dict(name=path.name, snapshot=original, directory=directory)

    def exercise():
        with helper.sibling_replacement(row) as replacement:
            assert replacement['snapshot']['identity'][:2] != original['identity'][:2]
            assert helper.sibling_snapshot(path) == replacement['snapshot']
            if body_error:
                raise RuntimeError('body-error')

    if body_error:
        with pytest.raises(RuntimeError, match='body-error'):
            exercise()
    else:
        exercise()
    assert helper.sibling_snapshot(path) == original
    assert not path.with_name('owned-saved').exists()


@pytest.mark.parametrize('fault', ['extra', 'content', 'mode', 'inode', 'symlink', 'hardlink'])
def test_sibling_cleanup_preserves_unknown_or_changed_inputs(
        census_model, tmp_path, fault):
    helper = census_model
    path = tmp_path / 'owned'
    path.mkdir()
    (path / 'canary').write_bytes(b'original')
    expected = helper.sibling_snapshot(path)
    if fault == 'extra':
        (path / 'unknown').write_bytes(b'foreign')
    elif fault == 'content':
        (path / 'canary').write_bytes(b'changed')
    elif fault == 'mode':
        path.chmod(0o700)
    elif fault == 'inode':
        path.rename(tmp_path / 'saved')
        path.mkdir()
        (path / 'canary').write_bytes(b'original')
    elif fault == 'symlink':
        (path / 'canary').rename(tmp_path / 'foreign')
        (path / 'canary').symlink_to(tmp_path / 'foreign')
    elif fault == 'hardlink':
        os.link(path / 'canary', tmp_path / 'another')
    with pytest.raises(helper.guest.GuestError, match='kiosk-sibling:'):
        helper.sibling_remove(path, expected)
    assert path.exists() and (path / 'canary').exists()


@pytest.mark.parametrize('fault', [None, 'contents', 'omitted-file', 'omitted-link', 'same-inode',
                                  'process-replaced'])
def test_sibling_private_view_reads_live_roots_and_refuses_exposure(
        census_model, tmp_path, monkeypatch, fault):
    helper = census_model
    proc = tmp_path / 'proc'
    process = proc / '42'
    share = process / 'root/usr/share'
    share.mkdir(parents=True)
    masked = share / 'masked'
    masked.mkdir()
    omitted = share / 'omitted'
    if fault == 'contents':
        (masked / 'mutable').write_bytes(b'exposed')
    elif fault == 'omitted-file':
        omitted.write_bytes(b'exposed')
    elif fault == 'omitted-link':
        omitted.symlink_to('missing')
    rows = [dict(name='masked', directory=True, snapshot={
        'identity': [masked.stat().st_dev, masked.stat().st_ino] if fault == 'same-inode' else [-1, -1]}),
        dict(name='omitted', directory=False)]
    monkeypatch.setattr(helper, 'PROC', proc)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1234))
    census = Mock(return_value={'backend': 'apparmor', 'confined_thread_roles': {'app': 1}})
    monkeypatch.setattr(helper, 'census', census)
    identities = iter([('start', 1, ('1234',) * 4),
                       ('changed' if fault == 'process-replaced' else 'start', 1, ('1234',) * 4)])
    monkeypatch.setattr(helper, 'process_identity', lambda _: next(identities))
    monkeypatch.setattr(helper.os, 'pidfd_open', lambda _: os.open('/dev/null', os.O_RDONLY))
    monkeypatch.setattr(helper, 'exited', lambda _: False)
    records = {}
    if fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-sibling:'):
            helper.sibling_private_views(rows, records.__setitem__, 'test')
    else:
        helper.sibling_private_views(rows, records.__setitem__, 'test')
        assert json.loads(records['onpc.kiosk.sibling.private.test'])['processes'] == 1
    census.assert_called_once_with()


@pytest.mark.parametrize('stage', ['configuration', 'policy'])
@pytest.mark.parametrize('fault', [None, 'native-admitted', 'load-accepted', 'wrong-load-refusal',
                                   'extended-load-refusal',
                                   'ownership-changed', 'attestation-changed',
                                   'policy-unenforced', 'recovery-failed', 'manager-active'])
@pytest.mark.parametrize('diagnostic_suffix', [b'', b' source=kiosk-confinement line=547'],
                         ids=['reason-only', 'source-location'])
def test_payload_drift_requires_native_and_boot_refusal_before_exact_recovery(
        census_model, tmp_path, monkeypatch, stage, fault, diagnostic_suffix):
    helper = census_model
    config, policy = tmp_path / 'config.json', tmp_path / 'onpc-kiosk.apparmor'
    originals = {config: b'{"backend":"apparmor"}\n', policy: b'original policy\n'}
    for path, data in originals.items():
        path.write_bytes(data)
    identities = {path: (path.stat().st_dev, path.stat().st_ino, path.stat().st_mtime_ns)
                  for path in originals}
    current = {'drift': None, 'loaded': None}
    events, records = [], {}
    def drift():
        changed = [name for name, path in (('configuration', config), ('policy', policy))
                   if path.read_bytes() != originals[path]]
        assert len(changed) <= 1
        return changed[0] if changed else None
    def first_exec(account, directory, command, *, service, armed=True):
        selected = drift()
        assert command == ['/usr/lib/systemd/systemd', '--version'] and service == 'systemd-user'
        events.append(('native', selected, armed))
        if not armed:
            assert selected is not None
            current['drift'] = selected
            return (0, b'') if fault == 'native-admitted' and selected == stage else (125, b'{"pam":14}')
        assert selected is None
        for path, identity in identities.items():
            actual = path.stat()
            assert (actual.st_dev, actual.st_ino, actual.st_mtime_ns) == identity
        return (125, b'{"pam":14}') if (fault == 'recovery-failed' and
                current['loaded'] == stage) else (0, b'')
    monkeypatch.setattr(helper, 'first_exec', first_exec)
    def manager_pid(unit):
        assert unit == 'user@1002.service'
        return 42 if fault == 'manager-active' and (stage == 'configuration' or
                current['loaded'] == 'configuration') else 0
    monkeypatch.setattr(helper, 'manager_pid', manager_pid)
    def ownership():
        return 'changed' if fault == 'ownership-changed' and current['loaded'] == stage else 'original'
    def attestation(path):
        assert str(path) == '/var/lib/oh-no-parent-control/kiosk-confinement.json'
        return 'changed' if fault == 'attestation-changed' and current['loaded'] == stage else 'original'
    monkeypatch.setitem(sys.modules, 'system_removal', SimpleNamespace(
        admission_removal_state=ownership, private_recovery_record=attestation))
    def enforcing(value):
        assert value == {'backend': 'apparmor'}
        events.append(('enforcing', drift()))
        if fault == 'policy-unenforced' and current['loaded'] == stage:
            raise ValueError('policy-unenforced')
    monkeypatch.setattr(helper.runpy, 'run_path', lambda path: {'enforcing': enforcing})
    def load(command, **options):
        assert command == ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'load']
        assert options == {'timeout': 90, 'check': False, 'merge_stderr': True}
        selected = drift()
        assert selected == current['drift']
        events.append(('load', selected))
        current['loaded'] = selected
        helper.guest.commands.last_returncode = 0 if fault == 'load-accepted' and selected == stage else 1
        reason = (b'other' if fault == 'wrong-load-refusal' and selected == stage else
                  b'policy-load-incomplete-reconfigure-required-extra'
                  if fault == 'extended-load-refusal' and selected == stage else
                  b'policy-load-incomplete-reconfigure-required')
        return b'reason=' + reason + diagnostic_suffix + b';'
    monkeypatch.setattr(helper.guest, 'commands', SimpleNamespace(run=load, last_returncode=None))
    if fault:
        category = ('generation-admitted' if fault == 'native-admitted' else
                    'payload-drift-boot-reattested' if fault in (
                        'load-accepted', 'wrong-load-refusal', 'extended-load-refusal') else
                    'payload-drift-ownership-changed' if fault in ('ownership-changed', 'attestation-changed') else
                    'policy-unenforced' if fault == 'policy-unenforced' else
                    'payload-drift-manager-active' if fault == 'manager-active' else
                    'payload-attestation-recovery')
        with pytest.raises((helper.guest.GuestError, ValueError), match=category):
            helper.verify_payload_attestation_faults(SimpleNamespace(pw_uid=1002), tmp_path,
                                                     policy, records.__setitem__)
        assert 'onpc.kiosk.' + stage + '-attestation-recovered' not in records
    else:
        helper.verify_payload_attestation_faults(SimpleNamespace(pw_uid=1002), tmp_path,
                                                 policy, records.__setitem__)
        assert events == [('native', None, True), ('enforcing', None),
                          ('native', 'configuration', False), ('load', 'configuration'),
                          ('enforcing', 'configuration'), ('native', None, True), ('enforcing', None),
                          ('native', 'policy', False), ('load', 'policy'),
                          ('enforcing', 'policy'), ('native', None, True), ('enforcing', None)]
        assert records['onpc.kiosk.unloaded-configuration-generation-denied'] is True
        assert records['onpc.kiosk.unloaded-policy-generation-denied'] is True
        for name in ('configuration', 'policy'):
            assert records['onpc.kiosk.' + name + '-drift-loader-refused'] is True
            assert records['onpc.kiosk.' + name + '-attestation-recovered'] is True
    for path, identity in identities.items():
        actual = path.stat()
        assert (actual.st_dev, actual.st_ino, actual.st_mtime_ns) == identity
        assert path.read_bytes() == originals[path]


@pytest.mark.parametrize('fault', [None, 'accepted-load', 'wrong-refusal', 'holder-changed',
                                   'record-changed', 'pam-changed', 'policy-unenforced',
                                   'drained-load-failed'])
@pytest.mark.parametrize('defer_drain', [False, True])
def test_installed_loader_refusal_preserves_real_admission_and_policy(
        census_model, monkeypatch, fault, defer_drain):
    from contextlib import contextmanager
    helper = census_model
    events, records = [], {}
    native_identity = ('start', 1, ('0',) * 4)
    current = {'held': False, 'attempted': False, 'loads': 0}
    @contextmanager
    def held_account(record):
        events.append('hold')
        current['held'] = True
        try:
            yield 42
        finally:
            current['held'] = False
            events.append('pam-end')
    def owned_bytes(path, *, private):
        assert private and str(path) == '/var/lib/oh-no-parent-control/kiosk-confinement.json'
        return b'changed' if fault == 'record-changed' and current['attempted'] else b'original'
    monkeypatch.setitem(sys.modules, 'system_kiosk_admission', SimpleNamespace(held_account=held_account))
    monkeypatch.setitem(sys.modules, 'system_kiosk_accounts', SimpleNamespace(owned_bytes=owned_bytes))
    def enforcing(config):
        events.append('enforcing')
        if fault == 'policy-unenforced' and current['attempted']:
            raise ValueError('policy-unenforced')
    monkeypatch.setattr(helper.runpy, 'run_path', lambda path: {'enforcing': enforcing})
    def run(command, *, timeout):
        assert command[-1] == 'load' and not current['held'] and timeout == 90
        events.append('load')
        current['loads'] += 1
        if fault == 'drained-load-failed' and current['loads'] == (1 if defer_drain else 2):
            raise helper.guest.GuestError('drained-load-failed')
    monkeypatch.setattr(helper.guest, 'run', run)
    def refused(command, **options):
        assert current['held'] and command[-1] == 'load'
        assert options == {'timeout': 90, 'check': False, 'merge_stderr': True}
        events.append('refused-load')
        current['attempted'] = True
        helper.guest.commands.last_returncode = 0 if fault == 'accepted-load' else 1
        return b'other error' if fault == 'wrong-refusal' else b'kiosk-admissions-active'
    monkeypatch.setattr(helper.guest, 'commands', SimpleNamespace(run=refused, last_returncode=None))
    monkeypatch.setattr(helper.guest, 'pam_service_state', lambda:
        'changed' if fault == 'pam-changed' and current['attempted'] else 'original')
    monkeypatch.setattr(helper, 'process_identity', lambda process:
        ('replacement', *native_identity[1:]) if fault == 'holder-changed' and current['attempted']
        else native_identity)
    def verify():
        digest = helper.verify_loader_admission_refusal(
            {'backend': 'apparmor'}, records.__setitem__, defer_drain=defer_drain)
        assert digest == hashlib.sha256(b'original').hexdigest()
        if defer_drain:
            assert records['onpc.kiosk.loader.drain-deferred-to-retirement'] is True
            assert 'onpc.kiosk.loader.allowed-after-admission' not in records
            assert current['loads'] == 0
            helper.verify_loader_admission_drained(
                {'backend': 'apparmor'}, records.__setitem__, digest, 'original')
    if fault:
        category = ('policy-unenforced' if fault == 'policy-unenforced' else
                    'drained-load-failed' if fault == 'drained-load-failed' else
                    'held-admission-not-refused' if fault in ('accepted-load', 'wrong-refusal') else
                    'refusal-changed-admission-state')
        with pytest.raises((helper.guest.GuestError, ValueError), match=category):
            verify()
        assert 'onpc.kiosk.loader.allowed-after-admission' not in records
    else:
        verify()
        assert events == ([] if defer_drain else ['load']) + ['enforcing', 'hold', 'refused-load', 'enforcing',
                          'pam-end', 'load', 'enforcing']
        assert records.get('onpc.kiosk.loader.allowed-before-admission') is (None if defer_drain else True)
        assert records['onpc.kiosk.loader.allowed-after-admission'] is True
    assert not current['held']


@pytest.mark.parametrize('fault', [None, 'body-error', 'chown-error', 'inode', 'target',
                                   'mode', 'gid', 'mtime', 'foreign-owner'])
def test_native_alias_fault_restores_only_its_unchanged_owned_symlink(
        census_model, monkeypatch, fault):
    helper = census_model
    monkeypatch.setattr(helper, 'os', SimpleNamespace(**vars(os)))
    alias = Path('/usr/bin/python3')
    current = dict(st_dev=7, st_ino=42, st_mode=stat.S_IFLNK | 0o777,
                   st_uid=0, st_gid=0, st_nlink=1, st_atime_ns=90, st_mtime_ns=100)
    link = {'target': 'python3.14'}
    closed, owners, times = [], [], []
    monkeypatch.setattr(helper.guest, 'guard', lambda: None)
    monkeypatch.setattr(helper.os, 'open', lambda path, flags: 900)
    monkeypatch.setattr(helper.os, 'fstat', lambda fd:
                        SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o755))
    def metadata(name, *, dir_fd, follow_symlinks):
        assert (name, dir_fd, follow_symlinks) == ('python3', 900, False)
        return SimpleNamespace(**current)
    monkeypatch.setattr(helper.os, 'stat', metadata)
    def readlink(name, *, dir_fd):
        assert (name, dir_fd) == ('python3', 900)
        current['st_atime_ns'] = 999
        return link['target']
    monkeypatch.setattr(helper.os, 'readlink', readlink)
    def chown(name, uid, gid, *, dir_fd, follow_symlinks):
        assert (name, gid, dir_fd, follow_symlinks) == ('python3', 0, 900, False)
        owners.append(uid)
        if fault == 'chown-error' and uid == 1002:
            raise OSError('chown-error')
        current['st_uid'], current['st_gid'] = uid, gid
    monkeypatch.setattr(helper.os, 'chown', chown)
    def utime(name, *, ns, dir_fd, follow_symlinks):
        assert (name, dir_fd, follow_symlinks) == ('python3', 900, False)
        times.append(ns)
        current['st_atime_ns'], current['st_mtime_ns'] = ns
    monkeypatch.setattr(helper.os, 'utime', utime)
    monkeypatch.setattr(helper.os, 'close', closed.append)
    def exercise():
        with helper.untrusted_alias_owner(alias, 1002):
            assert current['st_uid'] == 1002
            if fault == 'body-error':
                raise RuntimeError('body-error')
            if fault == 'inode':
                current['st_ino'] += 1
            elif fault == 'target':
                link['target'] = 'foreign'
            elif fault == 'mode':
                current['st_mode'] = stat.S_IFREG | 0o755
            elif fault == 'gid':
                current['st_gid'] = 1003
            elif fault == 'mtime':
                current['st_mtime_ns'] += 1
            elif fault == 'foreign-owner':
                current['st_uid'] = 1003
    if fault in ('body-error', 'chown-error'):
        with pytest.raises((OSError, RuntimeError), match=fault):
            exercise()
    elif fault:
        with pytest.raises(helper.guest.GuestError, match='kiosk-alias:fixture-replaced'):
            exercise()
    else:
        exercise()
    if fault in (None, 'body-error', 'chown-error'):
        assert owners == [1002, 0] and current['st_uid'] == current['st_gid'] == 0
        assert times == [(90, 100)]
        assert current['st_atime_ns'] == 90 and current['st_mtime_ns'] == 100
    else:
        assert owners == [1002] and times == []
    assert closed == [900]
