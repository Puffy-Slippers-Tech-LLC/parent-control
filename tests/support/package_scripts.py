"""Unprivileged maintainer-script machines with explicit service/account doubles.

Both configuration and removal execute real scripts against temporary files.
Their differing command models stay explicit; they share path relocation.
"""

import os
import json
import hashlib
from contextlib import contextmanager
import re
import runpy
import select
import shlex
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest
from tests.support.paths import ROOT
from tests.support.modules import load_module
from tests.support.shell import relocate_system_paths
from tools.test_storage import scratch_descriptors

REBOOT_NOTICE = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"


@contextmanager
def mapped_pam_worker(root):
    """Own one ordinary child retaining a private native-module mapping.

    The fixed child maps inert bytes and exits on its parent's pipe input.
    Kernel maps are read only through this recorded Popen identity. No native
    module is loaded, host PAM touched or outside process scanned/signalled.
    """
    library = root / 'pam_oh_no_parent_control.so'
    library.write_bytes(b'private inert mapping\n' + b'\0' * 4096)
    source = ("import mmap, sys\n"
              "with open(sys.argv[1], 'rb') as stream:\n"
              "    mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)\n"
              "    print('ready', flush=True)\n"
              "    sys.stdin.buffer.read(1)\n")
    child = subprocess.Popen([sys.executable, '-IB', '-c', source, str(library)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             pass_fds=scratch_descriptors())
    try:
        assert select.select([child.stdout], [], [], 5)[0], 'owned mapped worker did not become ready'
        assert child.stdout.readline() == b'ready\n'
        yield SimpleNamespace(child=child, library=library, proc=Path('/proc') / str(child.pid))
    finally:
        try:
            child.communicate(input=b'x', timeout=5)
        except subprocess.TimeoutExpired:
            # The direct child is unreaped, so only its recorded identity can
            # be signalled. The child launches no descendants.
            child.kill()
            child.communicate(timeout=5)


def prepared_lifecycle_machine(root, monkeypatch, backend='apparmor', *, installed=True, pam_original=None):
    """Finite historical installed inputs plus real selected lifecycle migration.

    All paths, descriptor locks, cache xattrs and durable writes remain real in
    this caller-owned tree. No host process/service/account or shared bus is used.
    The retired installer is not executable test setup: these snapshots cover
    only the two historical PAM input pairs consumed by migration histories.
    """
    if backend not in ('apparmor', 'selinux'):
        raise ValueError('unsupported fixture backend')
    def load(relative, name):
        with monkeypatch.context() as context:
            context.setattr(sys, 'dont_write_bytecode', True)
            return load_module(name, ROOT / relative)

    migration = load('packaging/lifecycle_migration.py', 'prepared_lifecycle')
    root.chmod(0o700)
    for name in ('var/lib/oh-no-parent-control', 'var/lib/AccountsService/users', 'run',
                 'etc/pam.d', 'usr/lib/pam.d', 'usr/share/oh-no-parent-control/confinement', 'proc'):
        (root / name).mkdir(parents=True, exist_ok=True)
        (root / name).chmod(0o700)
    for name in ('STATE_DIRECTORY', 'STATE', 'OWNERSHIP', 'EXPIRY', 'DISABLED', 'PAYLOAD', 'RETAINED', 'CAPTURE',
                 'PAM', 'PROCESSES', 'BOOT', 'PROFILES', 'CACHE'):
        monkeypatch.setattr(migration, name, root / getattr(migration, name).relative_to('/'))
    monkeypatch.setattr(migration, 'LOCKS', tuple(root / path.relative_to('/') for path in migration.LOCKS))
    monkeypatch.setattr(migration, 'ROOT', root)
    monkeypatch.setattr(migration, 'OWNER', os.getuid())
    monkeypatch.setattr(migration, 'GROUP', os.getgid())
    migration.BOOT.parent.mkdir(parents=True)
    migration.BOOT.write_text('11111111-1111-1111-1111-111111111111\n')
    migration.PROFILES.parent.mkdir(parents=True)
    migration.PROFILES.write_text('')
    user = SimpleNamespace(pw_name=migration.USER, pw_uid=1006, pw_gid=1006,
                           pw_dir='/home/oh-no-parent-control')
    machine = SimpleNamespace(migration=migration, root=root,
                              user=user, expires=None, loaded=False, commands=[], home_uid=1006)
    home = root / 'home/oh-no-parent-control'
    home.mkdir(parents=True)
    original_lstat = Path.lstat
    def lstat(path):
        info = original_lstat(path)
        if path == home:
            return SimpleNamespace(st_uid=machine.home_uid, st_mode=info.st_mode)
        return info
    monkeypatch.setattr(migration.Path, 'lstat', lstat)
    monkeypatch.setattr(migration.grp, 'getgrall', lambda: [])

    def getpwnam(name):
        if machine.user is not None and name == migration.USER:
            return machine.user
        raise KeyError(name)

    def getpwuid(identity):
        if machine.user is not None and machine.user.pw_uid == identity:
            return machine.user
        raise KeyError(identity)

    monkeypatch.setattr(migration.pwd, 'getpwnam', getpwnam)
    monkeypatch.setattr(migration.pwd, 'getpwuid', getpwuid)

    def run(arguments):
        machine.commands.append(arguments)
        output = ''
        if arguments[:2] == ['getent', 'shadow']:
            output = migration.USER + ':!::::::' + ('' if machine.expires is None else str(machine.expires)) + ':\n'
        elif arguments[:2] == ['usermod', '--expiredate']:
            machine.expires = None if arguments[2] == '-1' else int(arguments[2])
        elif arguments[0] == 'systemctl':
            output = 'ActiveState=activating\nSubState=start-pre\nMainPID=0\n'
        elif arguments[:2] == ['/usr/sbin/semodule', '-l']:
            output = 'onpc-kiosk\n' if machine.loaded else ''
        elif arguments[:2] in (['/usr/sbin/semodule', '-r'], ['/usr/sbin/apparmor_parser', '-R']):
            machine.loaded = False
            migration.PROFILES.write_text('')
        elif arguments[:2] in (['/usr/sbin/semodule', '-i'], ['/usr/sbin/apparmor_parser', '-r']):
            machine.loaded = True
            migration.PROFILES.write_text('onpc-kiosk-manager (enforce)\n')
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(migration, 'run', run)
    migration.OWNERSHIP.write_text('1006\n')
    migration.OWNERSHIP.chmod(0o600)
    (migration.PAYLOAD / 'config.json').write_text(json.dumps({'backend': backend}) + '\n')
    (migration.PAYLOAD / ('onpc-kiosk.cil' if backend == 'selinux' else 'onpc-kiosk.apparmor')).write_text('# owned policy\n')
    (migration.PAM / 'gdm-password').write_text(pam_original or 'session required pam_unix.so\n')
    (root / 'usr/lib/pam.d/systemd-user').write_text(pam_original or 'session required pam_systemd.so\n')
    for path in root.rglob('*'):
        if not path.is_symlink():
            path.chmod(path.stat().st_mode & ~0o022)
    if installed:
        native_original = ('account required pam_oh_no_parent_control.so kiosk\n'
                           'session required pam_oh_no_parent_control.so kiosk\n')
        # Exact historical bytes, not a renderer or a second legacy installer.
        integrity = ('# Oh No Parent Control admission integrity\n'
                     'account requisite pam_oh_no_parent_control.so kiosk-integrity\n'
                     'session requisite pam_oh_no_parent_control.so kiosk-admission\n')
        gate = ('# BEGIN Oh No Parent Control execution confinement\n'
                'session required pam_oh_no_parent_control.so kiosk-confinement\n'
                '# END Oh No Parent Control execution confinement\n')
        credentials = ('# Oh No Parent Control manager credentials (never authentication)\n'
                       'auth [success=done ignore=ignore default=die] '
                       'pam_oh_no_parent_control.so kiosk-manager-credentials\n'
                       'auth include other\n')
        snapshots = {
            None: {
                'gdm-password': ('session required pam_unix.so\n', None,
                                 integrity + 'session required pam_unix.so\n' + gate),
                'systemd-user': (None, 'session required pam_systemd.so\n',
                                 credentials + integrity + 'session required pam_systemd.so\n' + gate),
            },
            native_original: {
                'gdm-password': (native_original, None, integrity + native_original + gate),
                'systemd-user': (None, native_original,
                                 credentials + integrity + native_original + gate),
            },
        }
        if pam_original not in snapshots:
            raise ValueError('unsupported historical PAM fixture')
        saved = {'schema': 1, 'backend': backend, 'admission_protocol': 1, 'kiosk_uid': 1006,
                 'pam': {name: {'before': before, 'vendor': vendor, 'after': after, 'mode': 0o644}
                         for name, (before, vendor, after) in snapshots[pam_original].items()},
                 'loaded_config_sha256': hashlib.sha256(
                     (migration.PAYLOAD / 'config.json').read_bytes()).hexdigest(),
                 'loaded_policy_sha256': hashlib.sha256(
                     (migration.PAYLOAD / ('onpc-kiosk.cil' if backend == 'selinux' else
                                           'onpc-kiosk.apparmor')).read_bytes()).hexdigest()}
        migration.STATE.write_text(json.dumps(saved, sort_keys=True) + '\n')
        migration.STATE.chmod(0o600)
        for name, record in saved['pam'].items():
            (migration.PAM / name).write_text(record['after'])
            (migration.PAM / name).chmod(record['mode'])
        migration.LOCKS[0].write_bytes(b'')
        migration.LOCKS[0].chmod(0o600)
        machine.loaded = True
        if backend == 'apparmor':
            migration.PROFILES.write_text('onpc-kiosk-manager (enforce)\n')
    for path in root.rglob('*'):
        if not path.is_symlink():
            path.chmod(path.stat().st_mode & ~0o022)
    machine.commands.clear()
    return machine


def selected_pam_transactions(root):
    """Compile selected PAM and call it only through a private configuration."""
    import ctypes
    directory = root / 'selected-native'
    directory.mkdir()
    module = directory / 'pam_oh_no_parent_control.so'
    helper = directory / 'routing'
    helper.write_text('#!/bin/sh\nexit 0\n')
    helper.chmod(0o700)
    subprocess.run([
        'cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
        f'-DLOGIN_CHECK_PATH="{helper}"', f'-DSESSION_LIMIT_CHECK_PATH="{helper}"',
        f'-DKIOSK_ADMISSION_LOCK="{root / "run/oh-no-parent-control-kiosk-admission.lock"}"',
        f'-DKIOSK_ADMISSION_DISABLED="{root / "var/lib/oh-no-parent-control/kiosk-confinement-removing"}"',
        f'-DKIOSK_ADMISSION_LOCK_OWNER={os.getuid()}',
        '-o', str(module), str(ROOT / 'tools/pam_oh_no_parent_control.c'), '-lpam',
    ], check=True, capture_output=True, text=True, timeout=30, pass_fds=scratch_descriptors())
    # Historical input keeps the ordinary installed module name. Resolve only
    # that name to the private new binary in libpam's copied configuration.
    original = 'account required pam_oh_no_parent_control.so kiosk\nsession required pam_oh_no_parent_control.so kiosk\n'
    pam = ctypes.CDLL('libpam.so.0')
    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]
    pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(Conversation),
                                    ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
    for name in ('pam_acct_mgmt', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    pam.pam_putenv.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    configuration = directory / 'pam'
    configuration.mkdir()

    def call(migration, user, service):
        local = migration.PAM / service
        vendor = root / 'usr/lib/pam.d' / service
        contents = (local if local.exists() else vendor).read_text()
        (configuration / service).write_text(contents.replace('pam_oh_no_parent_control.so', str(module)))
        handle, conversation = ctypes.c_void_p(), Conversation()
        assert pam.pam_start_confdir(service.encode(), user.encode(), ctypes.byref(conversation),
                                    str(configuration).encode(), ctypes.byref(handle)) == 0
        try:
            assert pam.pam_putenv(handle, b'XDG_SESSION_TYPE=wayland') == 0
            result = pam.pam_acct_mgmt(handle, 0), pam.pam_open_session(handle, 0)
            if result[1] == 0:
                assert pam.pam_close_session(handle, 0) == 0
            return result
        finally:
            assert pam.pam_end(handle, 0) == 0
    return SimpleNamespace(original=original, call=call)


def use_real_account_lifecycle(root):
    """Use the selected owner in the shell machine with private NSS/shadow IO."""
    source = (ROOT / 'packaging/lifecycle_migration.py').read_text()
    source = relocate_system_paths(source, root, prefixes=(
        '/etc/', '/var/', '/run/', '/usr/', '/sys/', '/proc/'))
    source = source.replace("ROOT = Path('/')", 'ROOT = Path(' + repr(str(root)) + ')')
    source = source.replace("Path('/run')", 'Path(' + repr(str(root / 'run')) + ')')
    source = source.replace("Path('/proc')", 'Path(' + repr(str(root / 'proc')) + ')')
    source = source.replace('OWNER = 0', 'OWNER = ' + str(os.getuid()))
    source = source.replace('GROUP = 0', 'GROUP = ' + str(os.getgid()))
    source = source.replace('os.geteuid() != 0', 'os.geteuid() != ' + str(os.getuid()))
    source = source.replace('not stat.S_ISDIR(info.st_mode) or info.st_uid != identity',
                            'not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()')
    boot = root / 'proc/sys/kernel/random/boot_id'
    boot.parent.mkdir(parents=True)
    boot.write_text('11111111-1111-1111-1111-111111111111\n')
    helper = root / 'usr/libexec/oh-no-parent-control-kiosk-lifecycle'
    helper.unlink()
    adapters = '''
import sys
from types import SimpleNamespace
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec
sys.dont_write_bytecode = True
fixture_root = ROOT
with (fixture_root / 'commands').open('a') as stream:
    stream.write('oh-no-parent-control-kiosk-lifecycle ' + ' '.join(sys.argv[1:]) + '\\n')
def fixture_user(name):
    if name != USER or not (fixture_root / 'account-ready').exists():
        raise KeyError(name)
    return SimpleNamespace(pw_name=USER, pw_uid=1006, pw_gid=1006,
                           pw_dir='/home/oh-no-parent-control')
pwd.getpwnam = fixture_user
pwd.getpwuid = lambda identity: fixture_user(USER) if identity == 1006 else (_ for _ in ()).throw(KeyError(identity))
grp.getgrall = lambda: []
def run(arguments):
    path = fixture_root / 'account-expiry'
    if arguments[:2] == ['getent', 'shadow']:
        value = path.read_text().strip()
        return SimpleNamespace(stdout=USER + ':!::::::' + ('' if value == 'unset' else value) + ':\\n')
    if arguments[:2] == ['usermod', '--expiredate']:
        path.write_text('unset\\n' if arguments[2] == '-1' else arguments[2] + '\\n')
        return SimpleNamespace(stdout='')
    raise AssertionError('unexpected native operation: ' + repr(arguments))
if sys.argv[-1] == 'prepare' and os.environ.get('INTERRUPT_AFTER_KIOSK_MARKER') == '1' and not EXPIRY.exists():
    assert OWNERSHIP.read_text() == '1006\\n'
    assert (fixture_root / 'credential-locked').exists()
    sys.exit(71)
loader = SourceFileLoader('distro_pam', str(fixture_root / 'usr/libexec/oh-no-parent-control-distro-pam'))
distro = module_from_spec(spec_from_loader('distro_pam', loader))
sys.modules['distro_pam'] = distro
loader.exec_module(distro)
sys.exit(main())
'''
    helper.write_text('#!' + sys.executable + ' -IB\n' + source.split('\n', 1)[1] + adapters)
    helper.chmod(0o755)


def script_source(phase, distribution='ubuntu'):
    render = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))['render']
    return render(ROOT, distribution, phase)


def rpm_script_source(path):
    # Model RPM's literal-percent decoding for the isolated command machines.
    # test_rpm_packaging checks every generated callback with RPM's actual
    # macro engine, including runtime %{NAME}/%{name} query formats.
    return path.read_text().replace('%%', '%')


def use_real_state_migration(root):
    """Replace the configuration double with the production migration pass.

    Only state paths and the launcher are adapted for this unprivileged machine;
    validation, locking and atomic writes run unchanged under the fixture UID.
    """
    # Match preinst's private state directory; the lightweight command double
    # ordinarily has no need to enforce the production filesystem permissions.
    (root / 'var/lib/oh-no-parent-control').chmod(0o700)
    helper = root / 'usr/libexec/oh-no-parent-control-migrate-state'
    helper.unlink()
    helper.write_text(f'''#!{sys.executable}
import sys
from pathlib import Path
sys.path[:0] = [{str(ROOT)!r}, {str(ROOT / 'broker')!r}]
from oh_no_parent_control.data_migration import MigrationError, migrate_all_state
root = Path({str(root)!r})
state = root / 'var/lib/oh-no-parent-control'
assert (state / 'migration-in-progress').is_file()
assert not (root / 'broker-active').exists()
with (root / 'commands').open('a') as stream:
    stream.write('oh-no-parent-control-migrate-state \\n')
try:
    migrate_all_state(state, product_path=root / 'usr/share/oh-no-parent-control/app.json')
except MigrationError as error:
    sys.stderr.write(str(error) + '\\n')
    raise SystemExit(1)
''')
    helper.chmod(0o755)


class Machine:
    def __init__(self, root, distribution='ubuntu'):
        self.root = root
        self.distribution = distribution
        self.write("etc/os-release", {
            'ubuntu': 'ID=ubuntu\nVERSION_ID="26.04"\n',
            'fedora': 'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n',
        }[distribution])
        for path in ("etc/fapolicyd/rules.d", "run/systemd/system",
                     "var/lib/oh-no-parent-control", "usr/sbin", "var/mail"):
            (root / path).mkdir(parents=True, exist_ok=True)
        # The selected lifecycle finalizer validates every ancestor. Model the
        # root-owned system directory modes explicitly, independent of the
        # developer's group-writable umask used for unrelated private fixtures.
        for path in ('run', 'var', 'var/lib'):
            (root / path).chmod(0o755)
        (root / 'var/lib/oh-no-parent-control').chmod(0o700)
        self.write("etc/pam.d/common-auth", "auth required pam_unix.so\n")
        for name in ("account", "password", "session", "session-noninteractive"):
            self.write("etc/pam.d/common-" + name, "# fixture PAM stack\n")
        self.write("usr/sbin/fagenrules", """#!/bin/sh
set -e
printf '%s\\n' fagenrules >> "$AUDIT_ROOT/commands"
cat "$AUDIT_ROOT"/etc/fapolicyd/rules.d/*.rules > "$AUDIT_ROOT/etc/fapolicyd/compiled.rules"
""")
        (root / "usr/sbin/fagenrules").chmod(0o755)
        self.write("usr/sbin/fapolicyd-cli", """#!/bin/sh
printf '%s\\n' "fapolicyd-cli $*" >> "$AUDIT_ROOT/commands"
if [ "$1" = --update ]; then exit "${TRUST_UPDATE_STATUS:-0}"; fi
""").chmod(0o755)
        self.write("usr/libexec/oh-no-parent-control-uninstall", """#!/bin/sh
printf '%s\\n' "uninstall $*" >> "$AUDIT_ROOT/commands"
case "$1" in
    --remove) exit "${REMOVE_FAILURE:-${UNINSTALL_FAILURE:-0}}" ;;
    --restore) exit "${RESTORE_FAILURE:-${UNINSTALL_FAILURE:-0}}" ;;
esac
exit 99
""").chmod(0o755)
        self.write("usr/libexec/oh-no-parent-control-fedora-pam", """#!/bin/sh
printf '%s\\n' "fedora-pam $*" >> "$AUDIT_ROOT/commands"
case "$1" in
    remove) exit "${PAM_REMOVE_FAILURE:-${PAM_FAILURE:-0}}" ;;
    install) exit "${PAM_INSTALL_FAILURE:-${PAM_FAILURE:-0}}" ;;
esac
exit 99
""").chmod(0o755)
        self.write("test-bin/authselect", """#!/bin/sh
case "$1" in current) printf '%s\\n' local;; esac
""").chmod(0o755)
        self.write('usr/libexec/oh-no-parent-control-kiosk-lifecycle', '''#!/bin/sh
printf '%s\\n' "kiosk-lifecycle $*" >> "$AUDIT_ROOT/commands"
case "$3" in
    visibility-needed) printf 'no\\n' ;;
    commit) exit "${LIFECYCLE_COMMIT_STATUS:-0}" ;;
esac
''').chmod(0o755)
        self.write('usr/libexec/oh-no-parent-control-distro-pam', '''#!/bin/sh
printf '%s\\n' "distro-pam $*" >> "$AUDIT_ROOT/commands"
if [ "$2" = ubuntu ] && [ "$3" = remove ]; then
    choice=
    baseline="$AUDIT_ROOT/var/lib/oh-no-parent-control/malcontent-pam-before-install"
    if [ -f "$baseline" ]; then
        case "$(cat "$baseline")" in enabled) choice=--enable;; disabled) choice=--disable;; *) exit 1;; esac
    fi
    printf '%s\\n' "pam-auth-update --package --remove oh-no-parent-control-session-limits --remove oh-no-parent-control-kiosk-only ${choice:+$choice malcontent}" >> "$AUDIT_ROOT/commands"
    if grep -Eq '^[[:space:]]*[^#[:space:]].*(pam_oh_no_parent_control|/usr/libexec/oh-no-parent-control-)' \
        "$AUDIT_ROOT/etc/pam.d/common-auth" "$AUDIT_ROOT/etc/pam.d/common-account" \
        "$AUDIT_ROOT/etc/pam.d/common-password" "$AUDIT_ROOT/etc/pam.d/common-session" \
        "$AUDIT_ROOT/etc/pam.d/common-session-noninteractive"; then
        echo 'PAM references remain' >&2
        exit 1
    fi
fi
case "$3" in
    remove) exit "${PAM_REMOVE_FAILURE:-${PAM_FAILURE:-0}}" ;;
    install|restore) exit "${PAM_INSTALL_FAILURE:-${PAM_FAILURE:-0}}" ;;
    verify) exit 0 ;;
esac
exit 99
''').chmod(0o755)
        self.write("test-bin/mountpoint", """#!/bin/sh
test -n "$MOUNTED_PATH" && test "$2" = "$MOUNTED_PATH"
""").chmod(0o755)

    def write(self, path, text=""):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def baseline(self, *, active=False, enabled=False, rules=None):
        self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/complete")
        if active:
            self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/active")
        if enabled:
            self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/enabled")
        if rules is not None:
            self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/compiled.rules", rules)
        self.write("etc/fapolicyd/compiled.rules", "product rules\n")
        self.write("etc/fapolicyd/compiled.rules.prev", "old product rules\n")

    def integration(self, name, target, contents="product integration\n"):
        self.write("var/lib/oh-no-parent-control/installed-" + name, contents)
        return self.write(target, contents)

    def kiosk(self):
        self.write("var/lib/oh-no-parent-control/package-created-kiosk-uid", "1006\n").chmod(0o600)
        self.write("account")
        self.write("home/oh-no-parent-control/.cache/residue", "left behind")

    @property
    def gdm_hook(self):
        return 'etc/gdm/PreSession/Default' if self.distribution == 'fedora' else 'etc/gdm3/PreSession/Default'

    @property
    def service_command(self):
        return 'systemctl' if self.distribution == 'fedora' else 'deb-systemd-invoke'

    @property
    def delete_account(self):
        return 'userdel' if self.distribution == 'fedora' else 'deluser'

    def run(self, script, action, *, distribution=None, **env):
        source = script_source(script, distribution or self.distribution)
        return self.run_source(source, action, **env)

    def run_rpm(self, scriptlet, installed_count, **env):
        renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
        scripts = self.root / 'rpm-lifecycle'
        renderer['rpm_scripts'](ROOT, scripts)
        # RPM's preun trap invokes the installed abort-remove callback in a
        # separate shell. Give that shell the same isolated command model.
        if scriptlet == 'preun':
            self.prepare_script(script_source('postinst', 'fedora'),
                                'usr/share/oh-no-parent-control/lifecycle/postinst')
        return self.run_source(rpm_script_source(scripts / ('rpm-' + scriptlet)),
                               str(installed_count), **env)

    def prepare_script(self, source, path='script'):
        # The embedded provenance program is covered with its real filesystem
        # and RPM/DNF adapters in test_fedora_execution_policy. This maintainer
        # machine supplies the same explicit command double as service/account
        # commands; it must never execute a host-root Python scriptlet.
        source = re.sub(
            r"/usr/bin/python3 -B - (capture|flags|restore-stock|cleanup) <<'ONPC_FEDORA_EXECUTION_POLICY'\n.*?\nONPC_FEDORA_EXECUTION_POLICY",
            r'fedora_execution_policy \1', source, flags=re.DOTALL)
        source = re.sub(
            r"/usr/bin/python3 -B - <<'ONPC_NATIVE_PURGE_INTENT'\n.*?\nONPC_NATIVE_PURGE_INTENT",
            'native_purge_phase', source, flags=re.DOTALL)
        # Run the real log deletion/identity/mount guards in the private tree.
        # This unprivileged machine models root ownership with its own UID;
        # no production guard, filesystem action or assertion is omitted.
        source = source.replace(
            '/usr/bin/python3 -B - "$@"', 'ONPC_FIXTURE_PYTHON -B - "$@"')
        source = source.replace(
            "/usr/bin/python3 -I - <<'ONPC_CONFINEMENT_FINISH_REMOVE'",
            "ONPC_FIXTURE_PYTHON -I - <<'ONPC_CONFINEMENT_FINISH_REMOVE'")
        source = source.replace(
            "/usr/bin/python3 -I - <<'ONPC_KIOSK_PRE_UNPACK'",
            "ONPC_FIXTURE_PYTHON -I - <<'ONPC_KIOSK_PRE_UNPACK'")
        source = source.replace(
            '/usr/bin/python3 -I - "$1" "$2"', 'ONPC_FIXTURE_PYTHON -I - "$1" "$2"')
        # Redirect every absolute system prefix, including executable paths.
        source = relocate_system_paths(source, self.root)
        source = source.replace('ONPC_FIXTURE_PYTHON', shlex.quote(sys.executable))
        source = source.replace("_LOG_FILESYSTEM_ROOT = '/'",
                                '_LOG_FILESYSTEM_ROOT = ' + repr(str(self.root)))
        source = source.replace('_LOG_OWNER_UID = 0', '_LOG_OWNER_UID = ' + str(os.getuid()))
        source = source.replace("ROOT = Path('/')", 'ROOT = Path(' + repr(str(self.root)) + ')')
        source = source.replace("Path('/run')", 'Path(' + repr(str(self.root / 'run')) + ')')
        source = source.replace("Path('/proc')", 'Path(' + repr(str(self.root / 'proc')) + ')')
        source = source.replace('OWNER = 0', 'OWNER = ' + str(os.getuid()))
        source = source.replace('GROUP = 0', 'GROUP = ' + str(os.getgid()))
        source = source.replace('pwd.getpwnam(USER)', '(_ for _ in ()).throw(KeyError(USER))')
        source = source.replace('pwd.getpwuid(identity)', '(_ for _ in ()).throw(KeyError(identity))')
        source = source.replace("_CONFIGURATION_FILESYSTEM_ROOT = Path('/')",
                                '_CONFIGURATION_FILESYSTEM_ROOT = Path(' + repr(str(self.root)) + ')')
        source = source.replace('_CONFIGURATION_OWNER_UID = 0',
                                '_CONFIGURATION_OWNER_UID = ' + str(os.getuid()))
        source = source.replace(
            "except Exception:\n    print('oh-no-parent-control: confinement cleanup failed;",
            "except Exception:\n    import traceback\n    traceback.print_exc()\n    print('oh-no-parent-control: confinement cleanup failed;")
        for command in ("deb-systemd-invoke", "invoke-rc.d", "pam-auth-update"):
            source = source.replace(command, command.replace("-", "_").replace(".", "_"))
        mocks = r'''
record() { printf '%s\n' "$*" >> "$AUDIT_ROOT/commands"; }
native_purge_phase() { printf '%s\n' "${RPM_REMOVAL_PHASE:-remove}"; }
fedora_execution_policy() {
    case "$1" in
        restore-stock) printf '%s\n' "${ORIGINAL_STOCK_POLICY:-no}" ;;
        cleanup) rm -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/fedora-execution-policy.json" ;;
        capture|flags) : ;;
        *) return 99 ;;
    esac
}
systemctl() {
    record systemctl "$@"
    case "$1" in
        show)
            case "$*" in
                'show --property=ActiveState --value oh-no-parent-control-execution-policy-ready.service')
                    printf '%s\n' "${READINESS_STATE:-inactive}" ;;
                'show --property=ActiveState --value oh-no-parent-control-broker.service')
                    printf '%s\n' "${BROKER_STOP_STATE:-inactive}" ;;
                *) return 1 ;;
            esac ;;
        stop)
            if [ "$2" = oh-no-parent-control-execution-policy-ready.service ]; then
                return "${READINESS_STOP_STATUS:-0}"
            fi
            if [ "$2" = fapolicyd.service ]; then SERVICE_ACTIVE=0; fi
            if [ "$2" = oh-no-parent-control-broker.service ]; then
                return "${BROKER_STOP_STATUS:-0}"
            fi
            return 0 ;;
        is-active)
            case "$3" in
                user@*) test "${KIOSK_ACTIVE:-0}" = 1 ;;
                oh-no-parent-control-broker.service) test "${BROKER_ACTIVE:-0}" = 1 ;;
                *) test "${SERVICE_ACTIVE:-0}" = 1 ;;
            esac ;;
        is-enabled) test "${SERVICE_ENABLED:-0}" = 1 ;;
        is-failed) test "${BROKER_FAILED:-0}" = 1 ;;
        mask) ln -s /dev/null "$AUDIT_ROOT/run/systemd/system/oh-no-parent-control-broker.service" ;;
        unmask) rm "$AUDIT_ROOT/run/systemd/system/oh-no-parent-control-broker.service" ;;
        *) return 0 ;;
    esac
}
deb_systemd_invoke() {
    record deb-systemd-invoke "$@"
    SERVICE_ACTIVE=0
    if [ "$1 $2" = 'stop oh-no-parent-control-broker.service' ]; then
        return "${BROKER_STOP_STATUS:-0}"
    fi
}
invoke_rc_d() { record invoke-rc.d "$@"; }
pam_auth_update() { record pam-auth-update "$@"; }
busctl() { record busctl "$@"; }
getent() {
    if [ -f "$AUDIT_ROOT/account" ]; then
        printf 'oh-no-parent-control:x:1006:1006::%s/home/oh-no-parent-control:/bin/bash\n' "$AUDIT_ROOT"
    elif [ "${UID_REASSIGNED:-0}" = 1 ] && [ "$2" = 1006 ]; then
        printf 'replacement:x:1006:1006::/somewhere:/bin/bash\n'
    else
        return 2
    fi
}
deluser() { record deluser "$@"; rm "$AUDIT_ROOT/account"; }
userdel() { record userdel "$@"; rm "$AUDIT_ROOT/account"; }
stat() {
    if [ "$2" = '%u:%a' ]; then printf '0:600\n';
    elif [ "$2" = %u ]; then printf '%s\n' "${HOME_UID:-1006}";
    else command stat "$@"; fi
}
install() {
    # Model directory/file installs without chown in this private machine.
    record install "$@"
    install_directory=0
    install_mode=0755
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -o|-g) shift 2 ;;
            -m) install_mode="$2"; shift 2 ;;
            -d) install_directory=1; shift ;;
            *) break ;;
        esac
    done
    if [ "$install_directory" = 1 ]; then
        command install -d -m "$install_mode" "$@"
    else
        if [ "${RELEASE_CAPTURE_FAILURE:-0}" = 1 ] &&
           [ "$1" = "$AUDIT_ROOT/usr/share/oh-no-parent-control/app.json" ]; then
            printf '{"version":' > "$2"
            return 1
        fi
        command install -m "$install_mode" "$@"
    fi
}
'''
        return self.write(path, "#!/bin/sh\n" + mocks + source)

    def run_source(self, source, action, **env):
        target = self.prepare_script(source)
        return subprocess.run(
            ["/bin/sh", str(target), action], capture_output=True, text=True,
            env={**os.environ, "AUDIT_ROOT": str(self.root),
                 "PATH": str(self.root / "test-bin") + os.pathsep + os.environ["PATH"],
                 **env}, timeout=10,
        )

    @property
    def commands(self):
        path = self.root / "commands"
        return path.read_text() if path.exists() else ""


@pytest.fixture
def machine(tmp_path):
    return Machine(tmp_path)


@pytest.fixture
def package_machine(tmp_path, request):
    distribution = getattr(request, 'param', 'ubuntu')
    state = tmp_path / "var/lib/oh-no-parent-control"
    state.mkdir(parents=True)
    (tmp_path / "run/systemd/system").mkdir(parents=True)
    for name in ("migration-in-progress", "package-activation-pending",
                 "previous-package-activation.json"):
        (state / name).touch()

    (state / "package-created-kiosk-uid").write_text("1006\n")
    for name in ("99-oh-no-parent-control-allow.rules", "child-extension.trust"):
        path = tmp_path / "usr/share/oh-no-parent-control" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("product integration\n")
    if distribution == 'fedora':
        name = '00-oh-no-parent-control-canary.rules'
        (tmp_path / 'usr/share/oh-no-parent-control' / name).write_bytes(
            (ROOT / 'data/fapolicyd' / name).read_bytes())
    (tmp_path / "etc/pam.d").mkdir(parents=True)
    stage = runpy.run_path(str(ROOT / 'packaging/stage_distribution.py'))
    stack = stage['pam_stack'](ROOT).replace('ingroup wheel', 'ingroup ' + (
        'wheel' if distribution == 'fedora' else 'sudo'))
    generated = tmp_path / 'generated-pam'
    generated.mkdir()
    files = ('system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth') if distribution == 'fedora' else (
        'common-auth', 'common-account', 'common-password', 'common-session', 'common-session-noninteractive')
    for name in files:
        if distribution == 'fedora':
            contents = stack
        else:
            kind = name.removeprefix('common-').split('-')[0]
            contents = ''.join(line + '\n' for line in stack.splitlines() if line.startswith(kind + ' '))
        (generated / name).write_text(relocate_system_paths(contents, tmp_path))
        # Local-edit cases still begin with complete ordinary vendor files.
        # A test changes its intended rule; missing unrelated files must not
        # become an earlier refusal that hides the behavior under test.
        ordinary = ('auth required pam_unix.so\naccount required pam_unix.so\n'
                    'password required pam_unix.so\nsession required pam_unix.so\n') if distribution == 'fedora' else (
                        f'{kind} required pam_unix.so\n')
        (tmp_path / 'etc/pam.d' / name).write_text(ordinary)

    # Every executable used by postinst is either this stub or a filesystem
    # utility operating on the rewritten paths. PATH contains no host service
    # or account-management commands.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "stub"
    stub.write_text(r'''#!/bin/sh
name=${0##*/}
printf '%s\n' "$name $*" >> "$AUDIT_ROOT/commands"
case "$name" in
    getent)
        printf 'oh-no-parent-control:x:1006:1006::%s/home/oh-no-parent-control:/bin/bash\n' "$AUDIT_ROOT"
        ;;
    stat) printf '%s\n' "${KIOSK_MARKER_METADATA:-0:600}" ;;
    debconf-communicate) printf '%s\n' "${PAM_PROFILES:-0 unix, malcontent}" ;;
    pam-auth-update)
        if [ "${PAM_LOCAL_CHANGES:-0}" != 1 ]; then
            /usr/bin/cp "$AUDIT_ROOT/generated-pam/"* "$AUDIT_ROOT/etc/pam.d/"
        fi
        ;;
    install)
        directory=
        mode=0755
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -d) directory=-d; shift ;;
                -o|-g) shift 2 ;;
                -m) mode="$2"; shift 2 ;;
                *) break ;;
            esac
        done
        exec /usr/bin/install ${directory:+"$directory"} -m "$mode" "$@"
        ;;
    id) printf '1006\n' ;;
    policy-rc.d) exit "${POLICY_STATUS:-0}" ;;
    oh-no-parent-control-migrate-state)
        test -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 94
        test ! -f "$AUDIT_ROOT/broker-active" || exit 95
        exit "${MIGRATION_STATUS:-0}"
        ;;
    oh-no-parent-control-package-activation)
        if [ "$*" = prepare-child-trust-backend ]; then printf '%s\n' "${TRUST_BACKEND_ACTION:-none}"; exit 0; fi
        if [ "$*" = complete-child-trust-backend ]; then exit "${TRUST_COMPLETE_STATUS:-0}"; fi
        if [ "$1" = wait-child-trust ]; then
            if [ "${2:-}" = --refresh ]; then
                "$AUDIT_ROOT/usr/sbin/fapolicyd-cli" --update || exit "$?"
            fi
            exit "${TRUST_READY_STATUS:-0}"
        fi
        printf '%s\n' "$IMPACTS" ;;
    oh-no-parent-control-fedora-execution-policy)
        case "$1" in
            eligible) printf '%s\n' "${ORIGINAL_POLICY_ELIGIBLE:-no}" ;;
            commit) exit "${ORIGINAL_POLICY_COMMIT_STATUS:-0}" ;;
            *) exit 99 ;;
        esac ;;
    fagenrules) exit "${RULE_COMPILE_STATUS:-0}" ;;
    fapolicyd-cli)
        if [ "$*" = '--update' ]; then exit "${TRUST_UPDATE_STATUS:-0}"; fi
        test "$*" = '--reload-rules' || exit 99
        test "${RULE_RELOAD_STATUS:-0}" = 0 || exit "$RULE_RELOAD_STATUS"
        test -f "$AUDIT_ROOT/etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules" || exit 93
        touch "$AUDIT_ROOT/canary-loaded"
        ;;
    notify-reboot-required)
        test "$DPKG_MAINTSCRIPT_PACKAGE" = oh-no-parent-control || exit 91
        test "${NOTIFIER_STATUS:-0}" = 0 || exit "$NOTIFIER_STATUS"
        if [ "${NOTIFIER_DEFER:-0}" != 1 ]; then
            printf '*** System restart required ***\n' > "$AUDIT_ROOT/run/reboot-required"
            printf '%s\n' "$DPKG_MAINTSCRIPT_PACKAGE" >> "$AUDIT_ROOT/run/reboot-required.pkgs"
        fi
        ;;
    systemctl)
        case "$*" in
            'is-active --quiet oh-no-parent-control-broker.service')
                test -f "$AUDIT_ROOT/broker-active"; exit $? ;;
            'stop oh-no-parent-control-broker.service')
                if [ "${BROKER_STOP_REFUSED:-0}" != 1 ]; then rm -f "$AUDIT_ROOT/broker-active"; fi
                exit "${BROKER_STOP_STATUS:-0}"
                ;;
            'show --property=ActiveState --value oh-no-parent-control-broker.service')
                if [ -n "${BROKER_STOP_STATE:-}" ]; then printf '%s\n' "$BROKER_STOP_STATE"
                elif [ -f "$AUDIT_ROOT/broker-active" ]; then printf '%s\n' active
                else printf '%s\n' inactive; fi
                ;;
            'is-active --quiet fapolicyd.service')
                if [ -f "$AUDIT_ROOT/fapolicyd-active" ]; then exit 0; fi
                exit "${FAPOLICYD_ACTIVE_STATUS:-0}" ;;
            'show --property=ActiveState --value user@1006.service')
                test "${KIOSK_QUERY_STATUS:-0}" = 0 || exit "$KIOSK_QUERY_STATUS"
                if [ -f "$AUDIT_ROOT/kiosk-manager-failed" ]; then printf '%s\n' failed
                else printf '%s\n' "${KIOSK_MANAGER_STATE:-inactive}"; fi
                ;;
            'reset-failed user@1006.service')
                test "${KIOSK_RESET_STATUS:-0}" = 0 || exit "$KIOSK_RESET_STATUS"
                rm "$AUDIT_ROOT/kiosk-manager-failed"
                ;;
            'start oh-no-parent-control-execution-policy-ready.service')
                test -f "$AUDIT_ROOT/canary-loaded" || exit 92
                exit "${READINESS_STATUS:-0}"
                ;;
            '--system start oh-no-parent-control-broker.service'|\
            '--system restart oh-no-parent-control-broker.service')
                test ! -e "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 90
                exit "${BROKER_STATUS:-0}"
                ;;
        esac
        ;;
    deb-systemd-invoke)
        # Reproduce the installed helper's behavior for an inactive static unit.
        case "$*" in
            'start fapolicyd.service '*)
                if [ "${FAPOLICYD_STARTS:-0}" = 1 ]; then
                    touch "$AUDIT_ROOT/fapolicyd-active"
                fi
                ;;
            'stop oh-no-parent-control-broker.service')
                if [ "${BROKER_STOP_REFUSED:-0}" != 1 ]; then rm -f "$AUDIT_ROOT/broker-active"; fi
                exit "${BROKER_STOP_STATUS:-0}"
                ;;
            *oh-no-parent-control-broker.service*)
                printf 'inactive static unit skipped\n' >&2
                ;;
        esac
        ;;
    restorecon|chown|chmod|systemd-sysusers|invoke-rc.d|usermod|passwd|setpriv) exit 0 ;;
    oh-no-parent-control-fedora-pam)
        if [ "${PAM_LOCAL_CHANGES:-0}" != 1 ]; then
            /usr/bin/cp "$AUDIT_ROOT/generated-pam/"* "$AUDIT_ROOT/etc/pam.d/"
        fi
        ;;
    oh-no-parent-control-kiosk-lifecycle)
        case "$3" in
            visibility-needed) printf 'no\n'; exit 0 ;;
            commit) exit "${LIFECYCLE_COMMIT_STATUS:-0}" ;;
            *) exit 0 ;;
        esac ;;
    oh-no-parent-control-provision) ;;
    *) exit 99 ;;
esac
''')
    stub.chmod(0o755)
    for name in ("getent", "id", "systemctl", "deb-systemd-invoke", "install",
                 "chown", "chmod", "systemd-sysusers", "invoke-rc.d", "pam-auth-update",
                 "stat", "debconf-communicate", "usermod", "passwd", "setpriv", "restorecon"):
        (bin_dir / name).symlink_to(stub)
    for name in ("rm", "touch", "grep", "cut", "cat", "cmp", "sync"):
        (bin_dir / name).symlink_to(Path("/usr/bin") / name)
    for name in ("migrate-state", "provision", "package-activation", "fedora-pam", "fedora-execution-policy", "kiosk-lifecycle"):
        target = tmp_path / f"usr/libexec/oh-no-parent-control-{name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(stub)
    distro = relocate_system_paths((ROOT / 'packaging/distro_pam.py').read_text(), tmp_path)
    distro = distro.replace('info.st_uid != 0', 'info.st_uid != ' + str(os.getuid()))
    distro = distro.replace('os.geteuid() != 0', 'os.geteuid() != ' + str(os.getuid()))
    helper = tmp_path / 'usr/libexec/oh-no-parent-control-distro-pam'
    # Native command/service behavior stays explicit; production parsing,
    # profile verification, baseline publication and payload checks run real.
    configuration = ("\nENV.update({key: os.environ[key] for key in "
                     "('AUDIT_ROOT', 'PAM_LOCAL_CHANGES', 'PAM_PROFILES', 'CONFIGURE_FAILURE') "
                     "if key in os.environ})\n")
    distro = distro.replace("if __name__ == '__main__':", configuration + "\nif __name__ == '__main__':")
    audit = ("import sys\nwith open(" + repr(str(tmp_path / 'commands')) + ", 'a') as stream:\n"
             "    stream.write('oh-no-parent-control-distro-pam ' + ' '.join(sys.argv[1:]) + '\\n')\n")
    helper.write_text('#!' + sys.executable + ' -IB\n' + audit + distro.split('\n', 1)[1])
    helper.chmod(0o755)
    for target in ('usr/sbin/pam-auth-update', 'usr/bin/debconf-communicate'):
        link = tmp_path / target
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(stub)
    for target, executable in (('usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so', False),
                               ('usr/lib64/security/pam_oh_no_parent_control.so', False),
                               ('usr/libexec/oh-no-parent-control-login-check', True),
                               ('usr/libexec/oh-no-parent-control-session-limit-check', True)):
        path = tmp_path / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('private required payload\n')
        path.chmod(0o755 if executable else 0o644)
    (tmp_path / 'var/lib/oh-no-parent-control').chmod(0o700)
    notice = tmp_path / "usr/libexec/oh-no-parent-control-package-notice"
    notice.write_text(
        (ROOT / "tools/package_notice").read_text().replace("/run/", str(tmp_path) + "/run/")
    )
    notice.chmod(0o755)
    policy = tmp_path / "usr/sbin/policy-rc.d"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.symlink_to(stub)
    for name in ('fagenrules', 'fapolicyd-cli'):
        (tmp_path / 'usr/sbin' / name).symlink_to(stub)
    notifier = tmp_path / "usr/share/update-notifier/notify-reboot-required"
    notifier.parent.mkdir(parents=True)
    notifier.symlink_to(stub)

    source = script_source('postinst', distribution)
    source = relocate_system_paths(source, tmp_path)
    script = tmp_path / "postinst"
    script.write_text(source)

    def run(combine_output=False, **env):
        result = subprocess.run(
            ["/bin/sh", str(script), "configure"],
            env={"PATH": str(bin_dir), "AUDIT_ROOT": str(tmp_path),
                 "IMPACTS": "process-restart", **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if combine_output else subprocess.PIPE,
            text=True, timeout=10,
        )
        if result.returncode != 0:
            assert "PASS:" not in result.stdout
            assert REBOOT_NOTICE not in (result.stderr or result.stdout)
        return result

    return tmp_path, state, run
