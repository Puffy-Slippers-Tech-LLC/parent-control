"""Selected native/PAM composition using private files, libpam and OS doubles.

No host account, PAM configuration, bus, service or privilege transition is used.
Module-scoped compiler outputs and all helper children stay within pytest scratch.
"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import ctypes
import fcntl
import importlib.util
import json
import os
import subprocess
import time
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT
from tools.test_storage import scratch_descriptors

PROFILES = ROOT / 'data/pam-configs'
LOGIN_CHECK = ROOT / 'tools/oh-no-parent-control-login-check'
PAM_MODULE = ROOT / 'tools/pam_oh_no_parent_control.c'
DISTRO_PAM = ROOT / 'packaging/distro_pam.py'


def prepared_pam_output(root, distribution):
    """Render selected production profiles through the maintained distro translator."""
    source = root / 'profile-source'
    profiles = source / 'data/pam-configs'
    profiles.mkdir(parents=True)
    for name in ('oh-no-parent-control-kiosk-only', 'oh-no-parent-control-session-limits'):
        (profiles / name).write_bytes((PROFILES / name).read_bytes())
    namespace = {'__name__': 'prepared_profile_stage'}
    path = ROOT / 'packaging/stage_distribution.py'
    exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
    stack = namespace['pam_stack'](source)
    if distribution == 'fedora':
        return {name: stack for name in ('system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth')}
    stack = stack.replace('ingroup wheel', 'ingroup sudo')
    result = {}
    for name, kind in (('common-auth', 'auth'), ('common-account', 'account'), ('common-password', 'password'),
                       ('common-session', 'session'), ('common-session-noninteractive', 'session')):
        result[name] = ''.join(line + '\n' for line in stack.splitlines() if line.startswith(kind + ' '))
    return result


@pytest.fixture
def routing(monkeypatch, tmp_path):
    # Module globals must remain writable for test doubles.
    spec = importlib.util.spec_from_loader('selected_login', loader=None)
    helper = importlib.util.module_from_spec(spec)
    exec(compile(LOGIN_CHECK.read_bytes(), str(LOGIN_CHECK), 'exec'), helper.__dict__)
    monkeypatch.setattr(helper, 'OWNERSHIP_ROOT', tmp_path)
    monkeypatch.setattr(helper, '_OWNER_UID', os.getuid())
    monkeypatch.setattr(helper, '_OWNER_GID', os.getgid())
    marker = tmp_path / helper.KIOSK_OWNERSHIP
    marker.parent.mkdir(parents=True)
    marker.write_text('12345\n')
    marker.chmod(0o600)
    state = SimpleNamespace(reply='s "oh-no-parent-control"\ns "wayland"\n',
                            calls=[], records=[], fault=None)
    monkeypatch.setenv('PAM_USER', helper.KIOSK_USER)
    monkeypatch.setenv('PAM_SERVICE', 'gdm-password')
    monkeypatch.setenv('XDG_SESSION_TYPE', 'wayland')
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=12345))
    monkeypatch.setattr(helper.syslog, 'syslog', lambda level, value: state.records.append(value))

    def command(arguments, **options):
        state.calls.append(arguments)
        if state.fault:
            raise state.fault
        return SimpleNamespace(stdout=state.reply)

    monkeypatch.setattr(subprocess, 'run', command)
    return helper, state


@pytest.mark.parametrize('service', ['gdm-password', 'gdm-autologin', 'adjacent-graphical'])
def test_public_identity_checks_have_no_bus_dependency(routing, monkeypatch, service):
    helper, state = routing
    monkeypatch.setenv('PAM_SERVICE', service)
    assert helper.main(['--kiosk-account']) == helper.main(['--kiosk-session']) == 0
    assert state.calls == []
    assert state.records == [
        'onpc.pam kiosk identity stage=account outcome=allowed reason=none',
        'onpc.pam kiosk identity stage=session outcome=allowed reason=none']


@pytest.mark.parametrize('reply,fault', [
    ('s "ubuntu"\ns "wayland"\n', None), ('s ""\ns ""\n', None),
    ('s "oh-no-parent-control"\ns "x11"\n', None), ('malformed routing reply', None),
    ('', subprocess.TimeoutExpired('private-account', 5)),
])
def test_saved_routing_and_discovery_failures_do_not_affect_admission(routing, reply, fault):
    helper, state = routing
    state.reply, state.fault = reply, fault
    assert helper.main(['--kiosk-account']) == helper.main(['--kiosk-session']) == 0
    assert state.calls == []
    assert (state.reply, state.fault) == (reply, fault)
    state.fault = None
    assert helper.main(['--kiosk-account']) == 0


@pytest.mark.parametrize('transport', ['x11', '', 'tty'])
def test_pam_transport_is_not_an_identity_admission_input(routing, monkeypatch, transport):
    helper, state = routing
    monkeypatch.setenv('XDG_SESSION_TYPE', transport)
    assert helper.main(['--kiosk-session']) == 0
    assert state.calls == []


@pytest.mark.parametrize('user,service,result', [
    ('ordinary', 'sshd', 0), ('oh-no-parent-control', 'gdm-password', 0),
    ('oh-no-parent-control', 'systemd-user', 0), ('oh-no-parent-control', 'su-l', 1),
    ('ordinary', 'su-l', 0), ('oh-no-parent-control', 'gdm-autologin', 0),
    ('oh-no-parent-control', 'adjacent-graphical', 0), ('oh-no-parent-control', '', 2),
])
def test_service_dispatch_preserves_ordinary_control_without_bus(routing, monkeypatch, user, service, result):
    helper, state = routing
    monkeypatch.setenv('PAM_USER', user)
    monkeypatch.setenv('PAM_SERVICE', service)
    assert helper.main([]) == result
    assert state.calls == []


@pytest.mark.parametrize('fault', [KeyError('private-account'), OSError('private-account'), None])
def test_invalid_identity_is_unavailable_and_diagnostic_has_no_os_values(routing, monkeypatch, fault):
    helper, state = routing
    def account(name):
        assert name == helper.KIOSK_USER
        if fault is not None:
            raise fault
        return SimpleNamespace(pw_uid=0)
    monkeypatch.setattr(helper.pwd, 'getpwnam', account)
    assert helper.main(['--kiosk-account']) == helper.main(['--kiosk-session']) == 2
    assert state.records[-1] == 'onpc.pam kiosk identity stage=session outcome=unavailable reason=account'
    assert 'private-account' not in ''.join(state.records)
    assert state.calls == []
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=12345))
    assert helper.main(['--kiosk-account']) == 0


def test_identity_check_requires_root(routing, monkeypatch):
    helper, state = routing
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 12345)
    assert helper.main(['--kiosk-account']) == helper.main(['--kiosk-session']) == 2
    assert state.calls == []


@pytest.mark.parametrize('conflict', ['different-uid', 'missing', 'symlink', 'writable'])
def test_ownership_conflict_rejects_entry_and_restoration_allows_retry(routing, conflict):
    helper, state = routing
    marker = helper.OWNERSHIP_ROOT / helper.KIOSK_OWNERSHIP
    if conflict == 'different-uid':
        marker.write_text('23456\n')
    elif conflict == 'missing':
        marker.unlink()
    elif conflict == 'symlink':
        saved = marker.with_name('saved-uid')
        marker.rename(saved)
        marker.symlink_to(saved.name)
    else:
        marker.chmod(0o666)
    assert helper.main(['--kiosk-account']) != 0
    assert helper.main(['--kiosk-session']) != 0
    assert state.records[-1] == 'onpc.pam kiosk identity stage=session outcome=unavailable reason=account'
    assert state.calls == []
    if marker.is_symlink():
        marker.unlink()
        saved.rename(marker)
    marker.write_text('12345\n')
    marker.chmod(0o600)
    assert helper.main(['--kiosk-account']) == helper.main(['--kiosk-session']) == 0


@pytest.fixture(scope='module')
def compiled(tmp_path_factory):
    directory = tmp_path_factory.mktemp('onpc-prepared-pam')
    module, runtime = directory / 'product.so', directory / 'runtime.so'
    helper = directory / 'helper'
    common = ['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror']
    subprocess.run([*common, f'-DLOGIN_CHECK_PATH="{helper}"', f'-DSESSION_LIMIT_CHECK_PATH="{helper}"',
                    '-DKIOSK_ACCOUNT_NAME="kiosk-canary"',
                    f'-DKIOSK_ADMISSION_LOCK="{directory / "admission"}"',
                    f'-DKIOSK_ADMISSION_DISABLED="{directory / "removing"}"',
                    f'-DKIOSK_ADMISSION_LOCK_OWNER={os.getuid()}', '-DKIOSK_LOGIN_TIMEOUT_SECONDS=1',
                    '-DKIOSK_ADMISSION_TIMEOUT_SECONDS=1',
                    '-o', str(module), str(PAM_MODULE), '-lpam'],
                   check=True, capture_output=True, text=True, timeout=30, pass_fds=scratch_descriptors())
    subprocess.run([*common, '-o', str(runtime), str(ROOT / 'tests/support/pam_runtime_fixture.c'), '-lpam'],
                   check=True, capture_output=True, text=True, timeout=30, pass_fds=scratch_descriptors())
    helper.write_text('''#!/usr/bin/python3 -I
import json, os, pathlib, sys, time
directory = pathlib.Path(__file__).parent
with (directory / 'calls').open('a') as stream:
    stream.write(json.dumps([sys.argv[1:], dict(os.environ)]) + '\\n')
status = int((directory / 'status').read_text())
if status == 99:
    time.sleep(10)
sys.exit(status)
''')
    helper.chmod(0o700)
    return directory, module, runtime


@pytest.fixture
def native(compiled, tmp_path):
    directory, module, runtime = compiled
    (directory / 'calls').write_text('')
    (directory / 'status').write_text('0')
    for name in ('admission', 'removing'):
        (directory / name).unlink(missing_ok=True)
    pam = ctypes.CDLL('libpam.so.0')

    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]

    pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(Conversation),
                                    ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
    for name in ('pam_authenticate', 'pam_setcred', 'pam_acct_mgmt', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    pam.pam_putenv.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    @contextmanager
    def transaction(user='kiosk-canary', service='gdm-password', transport='wayland', stack=None):
        (tmp_path / service).write_text(stack if stack is not None else
            f'account required {module} kiosk\nsession required {module} kiosk\n')
        handle, conversation = ctypes.c_void_p(), Conversation()
        assert pam.pam_start_confdir(service.encode(), user.encode(), ctypes.byref(conversation),
                                    str(tmp_path).encode(), ctypes.byref(handle)) == 0
        try:
            if transport is not None:
                assert pam.pam_putenv(handle, f'XDG_SESSION_TYPE={transport}'.encode()) == 0
            yield handle
        finally:
            assert pam.pam_end(handle, 0) == 0

    return SimpleNamespace(directory=directory, module=module, runtime=runtime, pam=pam, transaction=transaction,
                           calls=lambda: [json.loads(line) for line in (directory / 'calls').read_text().splitlines()])


def test_native_account_session_binding_and_exact_environment(native, monkeypatch):
    monkeypatch.setenv('XDG_SESSION_TYPE', 'process-poison')
    monkeypatch.setenv('PYTHONPATH', 'process-poison')
    with native.transaction(transport=None) as handle:
        assert native.pam.pam_open_session(handle, 0) != 0
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        assert native.pam.pam_open_session(handle, 0) == 0
    calls = native.calls()
    assert [call[0] for call in calls] == [['--kiosk-account'], ['--kiosk-session']]
    # Python may inject locale coercion state, so check the privileged inputs
    # and absence of caller injection separately from that runtime detail.
    for _arguments, environment in calls:
        assert environment['PAM_USER'] == 'kiosk-canary'
        assert environment['PAM_SERVICE'] == 'gdm-password'
        assert 'XDG_SESSION_TYPE' not in environment
        assert environment['PATH'] == '/usr/sbin:/usr/bin:/sbin:/bin'
        assert 'PYTHONPATH' not in environment


@pytest.mark.parametrize('status,expected', [(1, 6), (2, 4), (99, 4)])
def test_native_denial_operational_error_timeout_and_fresh_retry(native, status, expected):
    (native.directory / 'status').write_text(str(status))
    with native.transaction() as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == expected
        assert native.pam.pam_open_session(handle, 0) != 0
    (native.directory / 'status').write_text('0')
    with native.transaction() as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == native.pam.pam_open_session(handle, 0) == 0


def test_later_failed_account_check_revokes_handle_session_binding(native):
    with native.transaction() as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        (native.directory / 'status').write_text('1')
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.pam.pam_open_session(handle, 0) != 0


@pytest.mark.parametrize('user,service,allowed', [
    ('kiosk-canary', 'systemd-user', True), ('kiosk-canary', 'su-l', False),
    ('kiosk-canary', 'gdm-autologin', True), ('kiosk-canary', 'adjacent-graphical', True),
    ('ordinary', 'su-l', True), ('ordinary', 'sshd', True),
    ('ordinary', 'polkit-1', True), ('root', 'sudo', True),
])
def test_native_service_scope_and_ordinary_user_control(native, user, service, allowed):
    with native.transaction(user=user, service=service) as handle:
        assert (native.pam.pam_acct_mgmt(handle, 0) == 0) is allowed
        assert (native.pam.pam_open_session(handle, 0) == 0) is allowed
    calls = native.calls()
    if user == 'kiosk-canary' and allowed and service != 'systemd-user':
        assert [call[0] for call in calls] == [['--kiosk-account'], ['--kiosk-session']]
        assert all(environment['PAM_SERVICE'] == service for _arguments, environment in calls)
    else:
        assert calls == []
    assert (native.directory / 'admission').exists() is (user == 'kiosk-canary' and allowed)


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
@pytest.mark.parametrize('existing', [False, True])
def test_removal_exclusion_spans_close_until_pam_end_and_releases(native, service, existing):
    path = native.directory / 'admission'
    if existing:
        path.touch(mode=0o600)
    with native.transaction(service=service) as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == native.pam.pam_open_session(handle, 0) == 0
        assert native.pam.pam_close_session(handle, 0) == 0
        identity = path.stat()
        leases = []
        # Observe only this process's real held inode, before opening the
        # lifecycle competitor. Both acquisition paths must avoid requesting
        # SELinux write authority while retaining the removal exclusion.
        for name in os.listdir('/proc/self/fd'):
            try:
                opened = os.fstat(int(name))
            except OSError:
                continue
            if (opened.st_dev, opened.st_ino) == (identity.st_dev, identity.st_ino):
                leases.append(int(name))
        assert len(leases) == 1
        assert fcntl.fcntl(leases[0], fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
        with path.open('rb') as owner:
            with pytest.raises(BlockingIOError):
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with path.open('rb') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with native.transaction(service=service) as handle:
            start = time.monotonic()
            assert native.pam.pam_acct_mgmt(handle, 0) != 0
            assert 0.9 <= time.monotonic() - start < 2
            start = time.monotonic()
            assert native.pam.pam_open_session(handle, 0) != 0
            assert 0.9 <= time.monotonic() - start < 2
        # A busy kiosk lifecycle must not delay or deny ordinary account PAM.
        calls = native.calls()
        with native.transaction(user='ordinary') as handle:
            assert native.pam.pam_acct_mgmt(handle, 0) == native.pam.pam_open_session(handle, 0) == 0
        assert native.calls() == calls
        assert (path.stat().st_dev, path.stat().st_ino) == (identity.st_dev, identity.st_ino)


@pytest.mark.parametrize('change', [None, 'replace', 'mode', 'marker'])
def test_native_waits_for_transient_writer_then_checks_same_lease(native, change):
    path = native.directory / 'admission'
    path.touch(mode=0o600)
    before = path.stat()
    original = native.directory / 'original'
    marker = native.directory / 'removing'
    with path.open('rb') as owner, native.transaction() as handle:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def release_writer():
            try:
                time.sleep(0.15)
                if change == 'replace':
                    path.rename(original)
                    path.touch(mode=0o600)
                elif change == 'mode':
                    path.chmod(0o640)
                elif change == 'marker':
                    marker.write_text('removing\n')
            finally:
                fcntl.flock(owner, fcntl.LOCK_UN)

        # The private writer thread is joined before touching its descriptor,
        # ending PAM or leaving this test's private module fixture.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(release_writer)
            start = time.monotonic()
            result = native.pam.pam_acct_mgmt(handle, 0)
            elapsed = time.monotonic() - start
            future.result(timeout=5)
        assert 0.1 <= elapsed < 1
        assert (result == 0) is (change is None)
        if change is None:
            assert native.pam.pam_open_session(handle, 0) == 0
            assert [call[0] for call in native.calls()] == [['--kiosk-account'], ['--kiosk-session']]
            # The recovered login retains its shared lease through PAM end.
            with path.open('rb') as competitor:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            assert native.calls() == []
    if change == 'replace':
        assert (original.stat().st_dev, original.stat().st_ino) == (before.st_dev, before.st_ino)
        original.unlink()
    else:
        after = path.stat()
        assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
        assert after.st_mode & 0o7777 == (0o640 if change == 'mode' else 0o600)
        assert marker.exists() is (change == 'marker')


@pytest.mark.parametrize('change', ['replace', 'symlink', 'hardlink', 'mode', 'marker'])
def test_retained_lease_refuses_changed_identity_without_repair(native, change):
    path = native.directory / 'admission'
    with native.transaction(service='systemd-user') as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        if change in ('replace', 'symlink'):
            path.rename(native.directory / 'original')
            if change == 'replace':
                path.touch(mode=0o600)
            else:
                path.symlink_to(native.directory / 'original')
        elif change == 'hardlink':
            os.link(path, native.directory / 'sibling')
        elif change == 'mode':
            path.chmod(0o640)
        else:
            (native.directory / 'removing').write_text('removing\n')
        assert native.pam.pam_open_session(handle, 0) != 0
    # No child or handle survives cleanup; fixture deletes only its own files.
    for name in ('original', 'sibling'):
        (native.directory / name).unlink(missing_ok=True)


@pytest.mark.parametrize('mask', [0o077, 0o777])
def test_new_native_lease_mode_ignores_umask_without_changing_it(native, mask):
    # Prepare the private readable PAM configuration before exercising the
    # module under an inherited restrictive mask.
    with native.transaction(service='systemd-user') as handle:
        previous = os.umask(mask)
        try:
            assert native.pam.pam_open_session(handle, 0) == 0
            assert (native.directory / 'admission').stat().st_mode & 0o7777 == 0o600
            assert os.umask(mask) == mask
        finally:
            os.umask(previous)


def test_existing_native_lease_is_not_repaired_or_unlinked(native):
    path = native.directory / 'admission'
    path.touch(mode=0o644)
    before = path.stat()
    with native.transaction(service='systemd-user') as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.pam.pam_open_session(handle, 0) != 0
    after = path.stat()
    assert (before.st_dev, before.st_ino, before.st_mode) == (after.st_dev, after.st_ino, after.st_mode)


@pytest.mark.parametrize('service,expected', [('gdm-password', 'infinity'), ('sshd', '1'), ('sudo', '1')])
@pytest.mark.parametrize('denied', [False, True])
def test_ordinary_runtime_cap_preserves_other_resources_and_account_denial(native, service, expected, denied):
    stack = (f'account required {native.runtime} memory seed=1{" expired" if denied else ""}\n'
             f'account required {native.module}\nsession required {native.runtime} {expected}\n')
    with native.transaction(user='ordinary', service=service, stack=stack) as handle:
        assert (native.pam.pam_acct_mgmt(handle, 0) == 0) is (not denied)
        if not denied:
            assert native.pam.pam_open_session(handle, 0) == 0
    assert native.calls() == []


@pytest.mark.parametrize('service', ['gdm-password', 'sshd', 'sudo', 'polkit-1'])
@pytest.mark.parametrize('status,expected', [(0, 0), (1, 13), (2, 4)])
def test_ordinary_authentication_time_status_and_vendor_denial(native, service, status, expected):
    (native.directory / 'status').write_text(str(status))
    stack = f'auth required {native.module}\nauth required pam_permit.so\n'
    with native.transaction(user='ordinary', service=service, stack=stack) as handle:
        assert native.pam.pam_authenticate(handle, 0) == expected
    with native.transaction(user='ordinary', service=service,
                            stack=f'auth required {native.module}\nauth required pam_deny.so\n') as handle:
        assert native.pam.pam_authenticate(handle, 0) != 0
    assert all(call[0] == ['--authenticate'] for call in native.calls())


@pytest.mark.parametrize('kind', ['auth', 'account'])
def test_administrator_denial_prefix_keeps_native_status_and_ordinary_positive(native, kind):
    # Use real existing identities with private PAM configuration only. The
    # installed history substitutes its reserved kiosk name for this root input.
    prefix = (f'{kind} [success=1 default=ignore] pam_succeed_if.so quiet user != root\n'
              f'{kind} requisite pam_deny.so\n')
    stack = prefix + f'{kind} required pam_permit.so\n'
    operation = native.pam.pam_authenticate if kind == 'auth' else native.pam.pam_acct_mgmt
    with native.transaction(user='root', stack=stack) as handle:
        assert operation(handle, 0) == 7  # pam_deny's PAM_AUTH_ERR, including account.
    with native.transaction(user='nobody', stack=stack) as handle:
        assert operation(handle, 0) == 0


@pytest.fixture
def ubuntu(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('prepared_distro', DISTRO_PAM)
    helper = importlib.util.module_from_spec(spec)
    exec(compile(DISTRO_PAM.read_bytes(), str(DISTRO_PAM), 'exec'), helper.__dict__)
    monkeypatch.setattr(helper, 'PAM', tmp_path / 'pam')
    monkeypatch.setattr(helper, 'BASELINE', tmp_path / 'state/baseline')
    helper.PAM.mkdir()
    helper.BASELINE.parent.mkdir(mode=0o700)
    original = '# administrator comment\naccount required pam_unix.so\n'
    generated = prepared_pam_output(tmp_path, 'ubuntu')
    state = SimpleNamespace(commands=[], original=original, malcontent='enabled', no_write=False)
    for name in helper.FILES['ubuntu']:
        (helper.PAM / name).write_text(original)
    # Stand in only for privileged ownership. Keep actual type/mode validation.
    real_lstat = helper.Path.lstat

    def info(path):
        observed = real_lstat(path)
        return SimpleNamespace(st_mode=observed.st_mode, st_uid=0)

    monkeypatch.setattr(helper.Path, 'lstat', info)

    def run(arguments, *, input=None):
        state.commands.append((arguments, input))
        if 'debconf-communicate' in arguments[0]:
            return SimpleNamespace(stdout='0 unix, malcontent, systemd\n' if state.malcontent == 'enabled' else '0 unix, systemd\n')
        assert arguments[:2] == ['/usr/sbin/pam-auth-update', '--package']
        assert '--force' not in arguments and input == ''
        if not state.no_write:
            installing = '--remove' not in arguments
            for name in helper.FILES['ubuntu']:
                entry = generated[name] if installing else ''
                (helper.PAM / name).write_text(entry + original)
        return SimpleNamespace(stdout='')

    monkeypatch.setattr(helper, 'run', run)
    return helper, state


@pytest.mark.parametrize('choice', ['enabled', 'disabled'])
def test_ubuntu_install_restore_remove_preserves_baseline_and_vendor_content(ubuntu, choice):
    helper, state = ubuntu
    state.malcontent = choice
    helper.configure('ubuntu', 'install')
    assert helper.BASELINE.read_text() == choice + '\n'
    state.malcontent = 'disabled' if choice == 'enabled' else 'enabled'
    helper.configure('ubuntu', 'restore')
    assert len([command for command, _ in state.commands if 'debconf-communicate' in command[0]]) == 1
    helper.configure('ubuntu', 'remove')
    assert state.commands[-1][0][-2:] == ['--enable' if choice == 'enabled' else '--disable', 'malcontent']
    assert all((helper.PAM / name).read_text() == state.original for name in helper.FILES['ubuntu'])
    helper.configure('ubuntu', 'remove')


def test_ubuntu_local_edit_and_failed_removal_preserve_owned_retry(ubuntu):
    helper, state = ubuntu
    helper.configure('ubuntu', 'install')
    before = {name: (helper.PAM / name).read_bytes() for name in helper.FILES['ubuntu']}
    state.no_write = True
    with pytest.raises(ValueError, match='references remain'):
        helper.configure('ubuntu', 'remove')
    assert before == {name: (helper.PAM / name).read_bytes() for name in helper.FILES['ubuntu']}
    assert helper.BASELINE.read_text() == 'enabled\n'
    state.no_write = False
    helper.configure('ubuntu', 'remove')
    state.no_write = True
    with pytest.raises(ValueError, match='not activated'):
        helper.configure('ubuntu', 'restore')
    assert all((helper.PAM / name).read_text() == state.original for name in helper.FILES['ubuntu'])


def test_ubuntu_failed_first_configuration_keeps_original_choice_for_retry(ubuntu, monkeypatch):
    helper, state = ubuntu
    command = helper.run

    def fail(arguments, *, input=None):
        if arguments[0].endswith('pam-auth-update'):
            raise subprocess.CalledProcessError(1, arguments)
        return command(arguments, input=input)

    monkeypatch.setattr(helper, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        helper.configure('ubuntu', 'install')
    assert helper.BASELINE.read_text() == 'enabled\n'
    assert all((helper.PAM / name).read_text() == state.original for name in helper.FILES['ubuntu'])
    monkeypatch.setattr(helper, 'run', command)
    helper.configure('ubuntu', 'install')
    helper.configure('ubuntu', 'remove')


def test_ubuntu_failed_baseline_write_leaves_no_partial_authority_or_temporary(ubuntu, monkeypatch):
    helper, state = ubuntu
    fsync = helper.os.fsync

    def failed_sync(descriptor):
        raise OSError('owned baseline write failed')

    monkeypatch.setattr(helper.os, 'fsync', failed_sync)
    with pytest.raises(OSError, match='baseline write failed'):
        helper.configure('ubuntu', 'install')
    assert not helper.BASELINE.exists()
    assert list(helper.BASELINE.parent.iterdir()) == []
    assert len(state.commands) == 1
    monkeypatch.setattr(helper.os, 'fsync', fsync)
    helper.configure('ubuntu', 'install')
    assert helper.BASELINE.read_text() == 'enabled\n'


def test_ubuntu_no_baseline_removal_does_not_invent_dependency_choice(ubuntu):
    helper, state = ubuntu
    helper.configure('ubuntu', 'remove')
    assert 'malcontent' not in state.commands[-1][0]
    assert not helper.BASELINE.exists()


@pytest.mark.parametrize('kind', ['symlink', 'directory', 'mode', 'invalid'])
def test_ubuntu_foreign_baseline_is_preserved_before_any_command(ubuntu, kind):
    helper, state = ubuntu
    if kind == 'symlink':
        helper.BASELINE.symlink_to(helper.PAM / 'common-account')
    elif kind == 'directory':
        helper.BASELINE.mkdir()
    else:
        helper.BASELINE.write_text('invalid\n' if kind == 'invalid' else 'enabled\n')
        helper.BASELINE.chmod(0o644 if kind == 'mode' else 0o600)
    with pytest.raises(ValueError, match='original PAM selection'):
        helper.configure('ubuntu', 'install')
    assert state.commands == []


def test_readiness_reads_effective_pam_and_required_installed_payload_without_writes(ubuntu, tmp_path, monkeypatch):
    helper, _state = ubuntu
    helper.configure('ubuntu', 'install')
    payload = []
    for name, mode in [('module', 0o644), ('login', 0o755), ('time', 0o755)]:
        path = tmp_path / name
        path.write_text('installed fixture')
        path.chmod(mode)
        payload.append(path)
    monkeypatch.setattr(helper, 'MODULES', {'ubuntu': payload[0]})
    monkeypatch.setattr(helper, 'LOGIN_CHECK', payload[1])
    monkeypatch.setattr(helper, 'TIME_CHECK', payload[2])
    real_stat = helper.Path.stat
    monkeypatch.setattr(helper.Path, 'stat', lambda path, **kwargs:
                        SimpleNamespace(st_mode=real_stat(path, **kwargs).st_mode, st_uid=0))
    # Arbitrary native optional callbacks are accepted without inventory.
    with (helper.PAM / 'common-session').open('a') as stream:
        stream.write('session optional pam_example.so reviewed-option\n')
    before = {path: path.read_bytes() for path in [*payload, *(helper.PAM / n for n in helper.FILES['ubuntu'])]}
    assert helper.runtime_ready('ubuntu') is None
    assert before == {path: path.read_bytes() for path in before}
    payload[1].chmod(0o644)
    with pytest.raises(ValueError, match='payload unavailable'):
        helper.runtime_ready('ubuntu')
    payload[1].chmod(0o755)
    (helper.PAM / 'common-account').write_text('account required pam_unix.so\n')
    with pytest.raises(ValueError, match='not activated'):
        helper.runtime_ready('ubuntu')


def test_selected_profiles_preserve_current_ordinary_policy_and_supported_distro_translation(tmp_path):
    spec = importlib.util.spec_from_file_location('pam_stage', ROOT / 'packaging/stage_distribution.py')
    stage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage)
    directory = tmp_path / 'data/pam-configs'
    directory.mkdir(parents=True)
    for name in ('oh-no-parent-control-kiosk-only', 'oh-no-parent-control-session-limits'):
        contents = (PROFILES / name).read_text()
        (directory / name).write_text(contents)
    stack = stage.pam_stack(tmp_path)
    assert stack == stage.pam_stack(ROOT)
    assert 'ingroup wheel' in stack and 'ingroup sudo' not in stack
    assert stack.index('account required pam_oh_no_parent_control.so kiosk') < stack.index('service = systemd-user')
    assert 'pam_malcontent.so' in stack


@pytest.fixture
def distro_profile_machine(tmp_path, monkeypatch, distribution):
    source = DISTRO_PAM
    spec = importlib.util.spec_from_file_location('prepared_policy_verification', source)
    helper = importlib.util.module_from_spec(spec)
    exec(compile(source.read_bytes(), str(source), 'exec'), helper.__dict__)
    monkeypatch.setattr(helper, 'PAM', tmp_path / 'pam')
    helper.PAM.mkdir()
    for name, contents in prepared_pam_output(tmp_path, distribution).items():
        (helper.PAM / name).write_text(contents)
    return helper


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('kind,index', [('auth', index) for index in range(3)] +
                         [('account', index) for index in range(6)])
def test_distro_policy_omission_cannot_pass_configuration_readiness(distro_profile_machine, distribution, kind, index):
    helper = distro_profile_machine
    path = helper.PAM / (f'common-{kind}' if distribution == 'ubuntu' else 'password-auth')
    before = path.read_text()
    removed = helper.time_policy(distribution)[kind][index]
    assert before.count(removed + '\n') == 1
    path.write_text(before.replace(removed + '\n', ''))
    with pytest.raises(ValueError, match='not activated'):
        helper.verify(distribution, installed=True)
    assert path.read_text() == before.replace(removed + '\n', '')
    path.write_text(before)
    assert helper.verify(distribution, installed=True) is None


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('kind,left,right', [('auth', 0, 1), ('account', 0, 1),
                                          ('account', 3, 4), ('account', 4, 5)])
def test_distro_owned_skip_and_time_order_is_required(distro_profile_machine, distribution, kind, left, right):
    helper = distro_profile_machine
    path = helper.PAM / (f'common-{kind}' if distribution == 'ubuntu' else 'smartcard-auth')
    rows = path.read_text().splitlines()
    expected = helper.time_policy(distribution)[kind]
    first, second = rows.index(expected[left]), rows.index(expected[right])
    rows[first], rows[second] = rows[second], rows[first]
    path.write_text('\n'.join(rows) + '\n')
    with pytest.raises(ValueError, match='time policy was not activated'):
        helper.verify(distribution, installed=True)


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('kind', ['auth', 'account'])
@pytest.mark.parametrize('callback', ['native', 'quiet-native', 'include'])
def test_vendor_callback_cannot_change_owned_relative_jump_targets(distro_profile_machine, distribution, kind, callback):
    helper = distro_profile_machine
    path = helper.PAM / (f'common-{kind}' if distribution == 'ubuntu' else 'system-auth')
    before = path.read_text()
    first = helper.time_policy(distribution)[kind][0]
    inserted = '@include vendor-stack' if callback == 'include' else (
        f'{"-" if callback == "quiet-native" else ""}{kind} optional pam_vendor.so')
    path.write_text(before.replace(first + '\n', first + '\n' + inserted + '\n'))
    with pytest.raises(ValueError, match='time policy was not activated'):
        helper.verify(distribution, installed=True)


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_product_policy_accepts_whitespace_comments_and_opaque_vendor_callbacks(distro_profile_machine, distribution):
    helper = distro_profile_machine
    for name in helper.FILES[distribution]:
        path = helper.PAM / name
        rows = path.read_text().splitlines()
        # Ubuntu may place its separate kiosk profile before or after the
        # time-policy block. It must not fall inside an integer skip sequence.
        gate = 'account required pam_oh_no_parent_control.so kiosk'
        if gate in rows:
            rows.remove(gate)
            rows.append(gate)
        changed = '\n# generated comment\n'.join('\t' + '\t  '.join(row.split()) + '  ' for row in rows)
        path.write_text('@include vendor-before\n-auth optional pam_unfamiliar.so native-option\n'
                        '-account optional pam_vendor.so unrelated\n' + changed +
                        '\nauth optional pam_more_vendor.so\nsession optional pam_vendor_session.so\n'
                        '@include vendor-after\n')
    assert helper.verify(distribution, installed=True) is None


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_other_management_types_do_not_change_owned_jump_targets(distro_profile_machine, distribution):
    helper = distro_profile_machine
    for kind, other in [('auth', 'session'), ('account', 'auth')]:
        path = helper.PAM / (f'common-{kind}' if distribution == 'ubuntu' else 'system-auth')
        first = helper.time_policy(distribution)[kind][0]
        path.write_text(path.read_text().replace(first + '\n', first + f'\n{other} optional pam_vendor.so\n'))
    assert helper.verify(distribution, installed=True) is None


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('formatting', ['continuation', 'inline-comment', 'both'])
def test_distro_checks_share_pam_logical_line_formatting(distro_profile_machine, distribution, formatting):
    helper = distro_profile_machine
    for name in helper.FILES[distribution]:
        path = helper.PAM / name
        rows = []
        for row in path.read_text().splitlines():
            if formatting in ('continuation', 'both'):
                kind, _separator, rest = row.partition(' ')
                row = kind + ' \\\n\t' + rest.replace(' pam_', ' \\\n  pam_', 1)
            if formatting in ('inline-comment', 'both'):
                row += ' # local formatting; /usr/libexec/oh-no-parent-control-login-check'
            rows.append(row)
        path.write_text('\n'.join(rows) + '\n')
    assert helper.verify(distribution, installed=True) is None


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('kind', ['auth', 'session'])
@pytest.mark.parametrize('wrong', ['pam_wrong#pam_oh_no_parent_control.so', 'pam_oh_no_parent_control#wrong.so'])
def test_hash_in_wrong_module_name_cannot_satisfy_required_entry(distro_profile_machine, distribution, kind, wrong):
    helper = distro_profile_machine
    path = helper.PAM / (f'common-{kind}' if distribution == 'ubuntu' else 'system-auth')
    path.write_text(path.read_text().replace(f'{kind} required pam_oh_no_parent_control.so',
                                            f'{kind} required {wrong}'))
    with pytest.raises(ValueError, match='not activated'):
        helper.verify(distribution, installed=True)


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('contents,active', [
    ('# pam_oh_no_parent_control.so\n', False),
    ('auth optional pam_unix.so # pam_oh_no_parent_control.so\n', False),
    ('account required pam_wrong#pam_oh_no_parent_control.so\n', False),
    ('# comment ends here \\\naccount required pam_oh_no_parent_control.so\n', True),
    ('account \\\n required pam_oh_no_parent_control.so\n', True),
    ('account required pam_oh_no_parent_control.so # active reference\n', True),
])
def test_removal_uses_logical_active_references_only(distro_profile_machine, distribution, contents, active):
    helper = distro_profile_machine
    for name in helper.FILES[distribution]:
        (helper.PAM / name).write_text(contents)
    if active:
        with pytest.raises(ValueError, match='references remain'):
            helper.verify(distribution, installed=False)
    else:
        assert helper.verify(distribution, installed=False) is None


def test_pam_comment_terminates_continuation_and_preserves_wrong_prefix(ubuntu):
    helper, _state = ubuntu
    # Linux-PAM trims the first '#', rather than treating it as a shell quote
    # or joining through a commented physical line's trailing backslash.
    assert helper.logical_lines(
        'auth required pam_permit.so#comment\n'
        'account required \\\n # comment \\\n'
        'session required pam_wrong#pam_oh_no_parent_control.so\n') == [
            'auth required pam_permit.so', 'account required', 'session required pam_wrong']
    with pytest.raises(ValueError, match='unterminated PAM continuation'):
        helper.logical_lines('auth required pam_permit.so \\')
