"""Installed removal assertions shared by DEB and RPM guarded attempts.

These are engineering checks through package, AccountsService, PAM and logind
APIs. The automatic GDM login is a declared fixture, not customer UI evidence.
The existing outer VM lease owns restoration, including failed transactions.
"""

import ast
from contextlib import contextmanager
import errno
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import runpy
import stat
import sys
import tempfile
import threading
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call
from system_enforcement import DESKTOP_ID, TARGET, observe_launch, provision_native

PRODUCT = 'oh-no-parent-control'
EXTENSION = 'oh-no-parent-control@tech.puffyslippers.com'
LIMITS = 'com.endlessm.ParentalControls.SessionLimits'
DEBIAN_NOTICE = '/etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice'
REMOVAL_NOTICE = '*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***'
RECOVERY_PAM = Path('/etc/pam.d/systemd-user')
GENERATED_POLICY = ('/etc/fapolicyd/rules.d/01-oh-no-parent-control-deny.rules',
                    '/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')


def state_path():
    return guest.PAYLOAD / 'private/removal-state.json'


def save_state(state):
    path = state_path()
    guest.require(not path.is_symlink(), 'removal:state-substituted')
    path.write_text(json.dumps(state))
    path.chmod(0o600)


def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def account_digest(uid, *, include_preferences=True):
    """Witness full retained state, or native policy independently of purge data."""
    state = account_state(uid)
    values = ([state[0].hex() if state[0] is not None else None, *state[1:]]
              if include_preferences else state[1:])
    return hashlib.sha256(json.dumps(
        values, sort_keys=True).encode()).hexdigest()


def preference_digest(uid):
    return guest.sha(Path('/var/lib/oh-no-parent-control/preferences') / f'{uid}.json')


def verify_other_account(state, *, purged=False, category='removal:other-account-changed'):
    uid = state['accounts']['other']
    if purged:
        guest.require(account_digest(uid, include_preferences=False) == state['other_policy'],
                      category)
        path = Path('/var/lib/oh-no-parent-control/preferences') / f'{uid}.json'
        guest.require(not path.exists() and not path.is_symlink(),
                      'purge:other-preferences-remain')
    else:
        guest.require(account_digest(uid) == state['other'], category)


def removal_command():
    # Explicitly retain dependency packages on both distributions.
    if guest.package_path().suffix == '.rpm':
        return ['dnf', 'remove', '--no-autoremove', '-y', PRODUCT]
    return ['apt-get', '-o', 'DPkg::Lock::Timeout=120', 'remove', '-y', PRODUCT]


def package_absent():
    argv = (['rpm', '-qa', '--queryformat', '%{NAME}\n']
            if guest.package_path().suffix == '.rpm' else
            ['dpkg-query', '-W', '-f=${Package}\t${db:Status-Abbrev}\n'])
    rows = guest.run(argv).splitlines()
    if guest.package_path().suffix == '.rpm':
        return PRODUCT not in rows
    for row in rows:
        fields = row.split('\t')
        if fields[0] == PRODUCT:
            # A refused prerm followed by a refused abort-remove can leave
            # configuration pending (iF), with every payload file retained.
            # Only not-installed/config-files states establish absence.
            return len(fields) == 2 and fields[1][1:2] in ('n', 'c')
    return True


def session_for(uid):
    rows = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines()
    guest.require(len(rows) <= 32, 'removal:session-inventory')
    found = []
    for row in rows:
        session = row.split()[0]
        props = dict(line.split('=', 1) for line in guest.run([
            'loginctl', 'show-session', session, '-p', 'User', '-p', 'Class',
            '-p', 'Type', '-p', 'Service', '-p', 'Remote', '-p', 'Scope']).splitlines())
        if props.get('User') == str(uid) and props.get('Class') == 'user':
            guest.require(props.get('Type') in ('wayland', 'x11') and
                          props.get('Service') == 'gdm-autologin' and
                          props.get('Remote') == 'no', 'removal:unexpected-desktop')
            found.append(props)
    guest.require(len(found) <= 1, 'removal:duplicate-desktop')
    return found[0] if found else None


def extension_lists(uid):
    """Read native per-user GSettings without loading erased product modules."""
    account = pwd.getpwuid(uid)
    home = Path(account.pw_dir)
    guest.require(not home.is_symlink() and home.is_dir() and home.stat().st_uid == uid,
                  'removal:unsafe-user-home')
    result = []
    for key in ('enabled-extensions', 'disabled-extensions'):
        raw = guest.run(['runuser', '-u', account.pw_name, '--', 'env', '-i',
                         f'HOME={account.pw_dir}', f'USER={account.pw_name}',
                         f'LOGNAME={account.pw_name}', 'PATH=/usr/bin:/bin', 'LANG=C.UTF-8',
                         'gsettings', 'get', 'org.gnome.shell', key])
        try:
            value = ast.literal_eval(raw.removeprefix('@as '))
        except (SyntaxError, ValueError):
            raise guest.GuestError('removal:extension-list-invalid') from None
        guest.require(isinstance(value, list) and all(isinstance(item, str) for item in value),
                      'removal:extension-list-invalid')
        result.append(value)
    return result


def verify_pam_removed():
    # Active PAM service stacks can be authselect symlinks on Fedora. Backups
    # and comments are inert and may intentionally retain old profile text.
    for path in Path('/etc/pam.d').iterdir():
        if path.name.endswith(('.pam-old', '.pam-new', '.dpkg-old', '.dpkg-dist', '~')):
            continue
        if path.is_file():
            source = path.read_text()
            guest.require('# Oh No Parent Control removal admission barrier' not in source,
                          'removal:pam-barrier-remains')
            for line in source.splitlines():
                if line.strip() and not line.lstrip().startswith('#'):
                    guest.require('pam_oh_no_parent_control.so' not in line and
                                  '/usr/libexec/oh-no-parent-control-' not in line,
                                  'removal:pam-reference-remains')


def desktop_health(uid):
    deadline = time.monotonic() + 90
    while True:
        session = session_for(uid)
        if session is not None:
            break
        guest.require(time.monotonic() < deadline, 'removal:desktop-not-created')
        time.sleep(0.25)
    guest.require(guest.run(['systemctl', 'is-active', session['Scope']]) == 'active',
                  'removal:desktop-scope-inactive')
    # Native Shell owns these interfaces. A loginctl record alone can precede
    # a failed desktop startup, so require a live session-bus result as well.
    command = ['runuser', '-u', pwd.getpwuid(uid).pw_name, '--', 'env',
               f'XDG_RUNTIME_DIR=/run/user/{uid}',
               f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus',
               'gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
               '--object-path', '/org/gnome/ScreenSaver',
               '--method', 'org.gnome.ScreenSaver.GetActive']
    while True:
        reply = guest.commands.run(command, check=False, timeout=10, merge_stderr=False)
        if guest.commands.last_returncode == 0:
            guest.require(reply.strip() in (b'(true,)', b'(false,)'),
                          'removal:desktop-response')
            return
        guest.require(time.monotonic() < deadline, 'removal:desktop-unavailable')
        time.sleep(0.25)


def verify_removed(state, *, purged=False, record=None):
    guest.guard()
    guest.require(package_absent(), 'removal:package-still-installed')
    uid = state['accounts']['child']
    guest.require(account_property(uid, LIMITS, 'LimitType') == 0 and
                  account_property(uid, LIMITS, 'DailyLimit') == 0 and
                  account_property(uid, LIMITS, 'ActiveExtension') == [0, 0] and
                  account_property(uid, 'com.endlessm.ParentalControls.AppFilter',
                                   'AppFilter') == [False, []], 'removal:restrictions-remain')
    if purged:
        for name in ('/var/lib/oh-no-parent-control', '/var/log/oh-no-parent-control'):
            path = Path(name)
            guest.require(not path.exists() and not path.is_symlink(), 'purge:saved-data-remains')
    else:
        guest.require(preference_digest(uid) == state['preferences'], 'removal:preferences-lost')
        guest.require(Path('/var/log/oh-no-parent-control').is_dir(), 'removal:logs-lost')
    verify_other_account(state, purged=purged)
    guest.require(all(EXTENSION not in values for values in extension_lists(uid)),
                  'removal:extension-entry-remains')
    guest.require(extension_lists(state['accounts']['other']) == state['other_extensions'],
                  'removal:other-extension-settings-changed')
    try:
        pwd.getpwnam(state['kiosk_name'])
    except KeyError:
        pass
    else:
        raise guest.GuestError('removal:kiosk-account-remains')
    guest.require(not Path(state['kiosk_home']).exists() and
                  not Path(state['kiosk_home']).is_symlink(), 'removal:kiosk-home-remains')
    for name in state['payload']:
        # Debian's one persistent reboot-notice conffile is intentionally kept
        # until purge. All executable payload and integration files must go.
        if name == DEBIAN_NOTICE and not purged:
            continue
        path = Path(name)
        guest.require(not path.exists() and not path.is_symlink(), 'removal:payload-remains')
    for name in (state['hook'], '/etc/oh-no-parent-control/config.json',
                 '/etc/fapolicyd/trust.d/oh-no-parent-control.trust',
                 '/etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules',
                 '/etc/fapolicyd/rules.d/01-oh-no-parent-control-deny.rules',
                 '/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules',
                 '/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules',
                 '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules',
                 '/var/lib/oh-no-parent-control/package-created-kiosk-uid',
                 '/var/lib/oh-no-parent-control/kiosk-confinement.json',
                 '/var/lib/oh-no-parent-control/kiosk-confinement-removing',
                 '/var/lib/oh-no-parent-control/uninstall-enforcement.json',
                 '/var/lib/oh-no-parent-control/uninstall-broker-mask',
                 '/var/lib/oh-no-parent-control/fapolicyd-before-install',
                 '/var/lib/oh-no-parent-control/child-trust-backend',
                 '/var/lib/oh-no-parent-control/fedora-authselect.json',
                 '/var/lib/oh-no-parent-control/fedora-execution-policy.json',
                 '/var/lib/oh-no-parent-control/installed-fapolicyd-original-policy',
                 '/etc/authselect/custom/oh-no-parent-control',
                 '/run/systemd/system/oh-no-parent-control-broker.service'):
        path = Path(name)
        guest.require(not path.exists() and not path.is_symlink(), 'removal:integration-remains')
    verify_pam_removed()
    guest.require(guest.pam_service_state() == state['pam_services'],
                  'removal:pam-original-not-restored')
    if record is not None:
        record('onpc.removal.pam-restored', json.dumps(state['pam_services'], sort_keys=True))
    if guest.package_path().suffix == '.rpm':
        loaded = guest.run(['semodule', '-l']).splitlines()
        guest.require(not any(row.split()[0] == 'onpc-kiosk' for row in loaded if row.split()),
                      'removal:kiosk-policy-remains')
    else:
        profiles = Path('/sys/kernel/security/apparmor/profiles').read_text().splitlines()
        guest.require(not any(row.startswith('onpc-kiosk-') for row in profiles),
                      'removal:kiosk-policy-remains')
    guest.require(guest.run(['busctl', '--system', 'call', 'org.freedesktop.DBus',
                            '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                            'NameHasOwner', 's', guest.BUS]) == 'b false',
                  'removal:broker-still-owns-bus')
    for role in ('child', 'other'):
        observe_launch(state['accounts'][role], True)
    if guest.package_path().suffix == '.rpm':
        guest.run(['authselect', 'check'])
        guest.require(guest.run(['authselect', 'current', '--raw']) == state['authselect'],
                      'removal:authselect-not-restored')
        guest.require(guest.run(['getenforce']) == 'Enforcing', 'removal:selinux-not-enforcing')


def configure_restrictions(accounts):
    """Make policy, one-time access and shared choices observably nondefault."""
    parent, child = accounts['parent'], accounts['child']
    accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, 60)))
    preferences = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    preferences['apps'] = {DESKTOP_ID: {'state': 'permanent', 'targets': [str(TARGET)],
                                      'patterns': [], 'user_saved_match_rule': False}}
    preferences['request'].update(last_selected_duration='custom', last_custom_minutes=23,
                                  allow_soft_blocked_apps=True, kiosk_muted=False,
                                  child_muted=False)
    accepted(call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences))))
    from system_session_expiry import grant
    grant(child, 600)
    guest.require(EXTENSION in extension_lists(child)[0], 'removal:extension-not-configured')
    observe_launch(child, False)
    observe_launch(accounts['other'], True)


def original_policy_diagnostics(record, stage):
    """Retain native classification inputs through the existing command logs."""
    guest.guard()
    if guest.package_path().suffix != '.rpm':
        return
    guest.require(stage in ('removed', 'reinstalled', 'purged', 'purge-reinstalled'),
                  'removal:diagnostic-stage')
    probes = (
        ('service', ['systemctl', 'show', 'fapolicyd.service', '--property=LoadState',
                     '--property=ActiveState', '--property=UnitFileState']),
        ('reason', ['dnf5', '--quiet', '--cacheonly', '--disable-repo=*', 'repoquery',
                    '--installed', '--queryformat', '%{name}|%{reason}', 'fapolicyd']),
        ('rpm-verify', ['rpm', '-V', 'fapolicyd']),
        ('compiled', ['/usr/sbin/fagenrules', '--check']),
        ('inventory', ['find', '/etc/fapolicyd', '-maxdepth', '3', '-printf',
                       '%y %m %u %g %p\\n']),
        ('provenance', ['cat', '/var/lib/oh-no-parent-control/fedora-execution-policy.json']),
    )
    for name, arguments in probes:
        guest.commands.run(['env', 'LC_ALL=C', *arguments], check=False, timeout=30,
                           merge_stderr=True)
        record(f'onpc.removal.policy.{stage}.{name}.status',
               str(guest.commands.last_returncode))


def purge_path_diagnostics(record, stage):
    """Observe ownership and distro defaults without relaxing purge guards.

    Only fixed paths, metadata and finite owner labels enter the retained XML.
    Never expose group members or arbitrary configuration/account strings.
    """
    guest.guard()
    groups = {'root': 0}
    for name in ('syslog', 'adm'):
        try:
            groups[name] = grp.getgrnam(name).gr_gid
        except (KeyError, OSError):
            pass
    paths = {}
    for name in ('/', '/var', '/var/lib', '/var/log',
                 '/var/lib/oh-no-parent-control', '/var/log/oh-no-parent-control'):
        try:
            info = Path(name).lstat()
            paths[name] = {
                'directory': stat.S_ISDIR(info.st_mode), 'root_owned': info.st_uid == 0,
                'mode': f'{stat.S_IMODE(info.st_mode):04o}',
                'group': next((label for label, gid in groups.items()
                               if info.st_gid == gid), 'other'),
                'device': info.st_dev, 'inode': info.st_ino, 'ctime_ns': info.st_ctime_ns,
            }
        except OSError as error:
            paths[name] = {'errno': error.errno}
    record(f'onpc.removal.purge-paths.{stage}', json.dumps(paths, sort_keys=True))
    for directory in ('/usr/lib/tmpfiles.d', '/etc/tmpfiles.d', '/run/tmpfiles.d'):
        for filename in ('var.conf', '00rsyslog.conf'):
            path = Path(directory) / filename
            value = {}
            try:
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(descriptor, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                            info.st_mode & 0o022 or info.st_nlink != 1 or info.st_size > 65536):
                        value['read'] = 'unsafe-or-oversized'
                    else:
                        raw = stream.read(65537)
                        if len(raw) > 65536:
                            value['read'] = 'oversized'
                        else:
                            value['sha256'] = hashlib.sha256(raw).hexdigest()
                            value['rules'] = []
                            for line in raw.decode('utf-8', errors='replace').splitlines():
                                fields = line.split()
                                if (len(fields) >= 5 and not fields[0].startswith('#') and
                                        fields[1] == '/var/log'):
                                    value['rules'].append({
                                        'action': fields[0] if fields[0] in ('d', 'z', 'Z') else 'other',
                                        'mode': fields[2] if re.fullmatch(r'[0-7]{3,4}', fields[2]) else 'other',
                                        'owner': fields[3] if fields[3] in ('root', 'syslog', '0', '-') else 'other',
                                        'group': fields[4] if fields[4] in ('root', 'syslog', 'adm', '0', '-') else 'other',
                                    })
            except OSError as error:
                value['errno'] = error.errno
            record(f'onpc.removal.purge-default.{stage}.{directory}/{filename}',
                   json.dumps(value, sort_keys=True))


def refuse_foreign_integration(accounts, before, other, category, target, *, record=None):
    """Keep refusal evidence before resolving the edit and retrying configuration."""
    guest.guard()
    info, original = target.lstat(), target.read_bytes()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1,
                  'removal:unsafe-' + category)
    modified = original + b'\n# onpc removal refusal fixture\n'
    write_hook(target, info, original, modified)
    try:
        guest.commands.run(removal_command(), check=False, timeout=1800, merge_stderr=False)
        guest.require(guest.commands.last_returncode != 0 and not package_absent(),
                      'removal:modified-' + category + '-not-refused')
        guest.require(account_digest(accounts['child']) == before and
                      account_digest(accounts['other']) == other, 'removal:refusal-changed-policy')
        guest.require(target.read_bytes() == modified, 'removal:foreign-edit-overwritten')
        # Verify the retained version and every payload digest before any
        # reinstall could conceal erasure or damage from the refused removal.
        guest.verify_package_payload()
    finally:
        write_hook(target, info, modified, original)
    if guest.package_path().suffix == '.deb':
        status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
        guest.require(status in ('install ok installed', 'install ok half-configured'),
                      'removal:unexpected-refusal-package-status')
        if record is not None:
            record('onpc.removal.' + category + '-status-before-recovery', status)
        if status == 'install ok half-configured':
            # Foreign PAM also blocks abort-remove. Once the owned edit is
            # resolved, finish the already-unpacked native configuration.
            # Replacing payload here would create stale live PAM mappings.
            guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
    guest.verify_package_files()
    guest.require(account_digest(accounts['child']) == before and
                  account_digest(accounts['other']) == other, 'removal:retry-changed-policy')
    if record is not None and guest.package_path().suffix == '.deb':
        # Strict verification above independently requires this native status.
        record('onpc.removal.' + category + '-status-after-recovery', 'install ok installed')


def foreign_integration_refusals(record, accounts, other, *, fedora):
    """Exercise the finite hook/PAM refusals and native configuration recovery."""
    guest.guard()
    hook = Path('/etc/gdm/PreSession/Default' if fedora else '/etc/gdm3/PreSession/Default')
    before = account_digest(accounts['child'])
    for category, target in (('hook', hook), ('pam', Path('/etc/pam.d/gdm-password'))):
        refuse_foreign_integration(accounts, before, other, category, target, record=record)
        record('onpc.removal.' + category + '-refusal-retry',
               'foreign-edit-refused; payload-and-policy-preserved')
    return hook


def exercise_live_refusals(record):
    """Engineering-only probe in disposable maintenance; retain the package."""
    guest.guard()
    guest.enable_diagnostics()
    accounts = provision_native()
    other = account_digest(accounts['other'])
    configure_restrictions(accounts)
    foreign_integration_refusals(record, accounts, other,
                                fedora=guest.package_path().suffix == '.rpm')


def mount_inventory():
    """Retain exact kernel identities, including bind source roots and namespace."""
    rows = {}
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields = line.split()
        separator = fields.index('-')
        rows[fields[0]] = (tuple(fields[:separator]), tuple(fields[separator + 1:]))
    return os.readlink('/proc/self/ns/mnt'), rows


def fault_file_identity(path):
    info = path.lstat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and
                  not info.st_mode & 0o022 and info.st_nlink == 1,
                  'rollback:unsafe-fault-file')
    return (info.st_dev, info.st_ino, info.st_uid, info.st_gid,
            info.st_mode, info.st_nlink, path.read_bytes())


def release_pam_fault(path, original, namespace, owned):
    """Never unmount a foreign overlay or a replaced underlying file."""
    current_namespace, rows = mount_inventory()
    matches = {key: value for key, value in rows.items() if value[0][4] == str(path)}
    guest.require(current_namespace == namespace and matches == owned and
                  fault_file_identity(path) == original,
                  'rollback:fault-ownership-changed')
    guest.run(['umount', '--', str(path)], timeout=30)
    current_namespace, rows = mount_inventory()
    guest.require(current_namespace == namespace and
                  not any(row[0][4] == str(path) for row in rows.values()) and
                  fault_file_identity(path) == original,
                  'rollback:fault-release-not-verified')


@contextmanager
def mounted_pam_fault(record):
    """An unchanged read-only self bind makes native atomic replacement fail EBUSY."""
    guest.guard()
    path = RECOVERY_PAM
    original = fault_file_identity(path)
    namespace, before = mount_inventory()
    guest.require(not any(row[0][4] == str(path) for row in before.values()),
                  'rollback:preexisting-fault-mount')
    guest.run(['mount', '--bind', str(path), str(path)], timeout=30)
    current_namespace, rows = mount_inventory()
    owned = {key: row for key, row in rows.items()
             if key not in before and row[0][4] == str(path)}
    # If publication cannot be attributed, preserve it for the VM owner.
    guest.require(current_namespace == namespace and len(owned) == 1 and
                  fault_file_identity(path) == original,
                  'rollback:fault-mount-not-attributable')
    try:
        guest.run(['mount', '-o', 'remount,bind,ro', str(path)], timeout=30)
    finally:
        # Remount changes only options. Pin the new exact kernel row even on
        # command failure; never adopt a replacement mount ID/source/target.
        current_namespace, rows = mount_inventory()
        updated = {key: rows[key] for key in owned if key in rows}
        guest.require(current_namespace == namespace and len(updated) == 1 and
                      all(updated[key][0][:5] == row[0][:5] and
                          updated[key][1] == row[1] for key, row in owned.items()),
                      'rollback:fault-mount-changed')
        owned = updated
        if sys.exc_info()[0] is not None:
            release_pam_fault(path, original, namespace, owned)
    try:
        guest.require(all('ro' in row[0][5].split(',') for row in owned.values()),
                      'rollback:fault-not-readonly')
        record('onpc.rollback.fault', json.dumps({
            'namespace': namespace, 'mounts': owned,
            'device': original[0], 'inode': original[1],
            'sha256': hashlib.sha256(original[-1]).hexdigest()}, sort_keys=True))
        yield
    finally:
        release_pam_fault(path, original, namespace, owned)


def cleanup_transition(uid):
    """Positive native observations only; neither logs nor snapshots prove clearing."""
    values = account_state(uid)[1:]
    if values != (0, 0, [0, 0], [False, []]):
        return None
    extensions = extension_lists(uid)
    if any(EXTENSION in values for values in extensions):
        return None
    if any(os.path.lexists(name) for name in GENERATED_POLICY):
        return None
    snapshot = Path('/var/lib/oh-no-parent-control/uninstall-enforcement.json')
    try:
        info = snapshot.lstat()
        guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                      stat.S_IMODE(info.st_mode) == 0o600, 'rollback:unsafe-snapshot')
        return {'snapshot': json.loads(snapshot.read_text()), 'native': values,
                'extensions': extensions, 'policy_absent': list(GENERATED_POLICY)}
    except FileNotFoundError:
        return None


def observe_aborted_transaction(uid, expected, denial, record):
    """Join the separately owned native command on every watcher exit."""
    transaction = guest.Commands()
    guest.require(guest.commands.directory is not None, 'rollback:diagnostics-unavailable')
    transaction.directory = Path(tempfile.mkdtemp(
        prefix='rollback-', dir=guest.commands.directory.parent))
    result = {}
    def execute():
        try:
            result['output'] = transaction.run(removal_command(), check=False,
                                               timeout=1800, merge_stderr=True)
        except BaseException as error:
            result['error'] = error
    worker = threading.Thread(target=execute, name='onpc-native-removal')
    deadline = time.monotonic() + 1800
    worker.start()
    observed = None
    admission_denied = False
    try:
        while worker.is_alive() and time.monotonic() < deadline:
            admission_denied |= Path('/etc/pam.d/gdm-password').read_bytes() == denial
            observation = cleanup_transition(uid) if observed is None else None
            if observation is not None:
                snapshot = observation['snapshot']
                guest.require(snapshot.get('version') == 1 and
                              expected in snapshot.get('accounts', []),
                              'rollback:snapshot-differs-from-precleanup')
                observed = snapshot
                (transaction.directory / 'observed-snapshot.txt').write_text(json.dumps(observation))
                (transaction.directory / 'observed-snapshot.txt').chmod(0o600)
            if observed is not None and admission_denied:
                break
            time.sleep(0.01)
    finally:
        # Commands owns the spawned pidfd and finite timeout cleanup. No
        # process discovery or inferred descendant signal belongs here.
        worker.join()
    if 'error' in result:
        raise result['error']
    record('onpc.rollback.native-status', str(transaction.last_returncode))
    guest.require(observed is not None, 'rollback:cleared-transition-not-observed')
    guest.require(admission_denied, 'rollback:gdm-denial-transition-not-observed')
    record('onpc.rollback.snapshot', hashlib.sha256(
        json.dumps(observed, sort_keys=True).encode()).hexdigest())
    record('onpc.rollback.gdm-denial', hashlib.sha256(denial).hexdigest())
    witness = transaction.directory / 'observed-gdm-denial.txt'
    witness.write_bytes(denial)
    witness.chmod(0o600)
    record('onpc.rollback.cleared',
           'native-limits-grant-filter-extension-cleared; generated-policy-absent; snapshot-matched')
    return result['output'], transaction.last_returncode


def rollback_record_matches(name, before, after):
    if before == after:
        return True
    # fedora_pam.save atomically republishes this package-owned private record
    # as root. Its group can change from the broker's wheel group to root;
    # neither group has access at 0600. Preserve every authoritative field.
    return (name == '/var/lib/oh-no-parent-control/fedora-authselect.json' and
            before is not None and after is not None and
            before[:2] == after[:2] == (0o600, 0) and
            before[2] == grp.getgrnam('wheel').gr_gid and after[2] == 0 and
            before[3] == after[3])


def aborted_cleanup_rollback_retry(record):
    """One native aborted cleanup, guarded restoration and successful owned retry."""
    guest.guard()
    guest.enable_diagnostics()
    from system_kiosk_admission import probe, verify_gates
    accounts = provision_native()
    parent, child = accounts['parent'], accounts['child']
    defaults = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    guest.require(defaults['parent_control_enabled'] is False and defaults['apps'] == {},
                  'rollback:nonfresh-start')
    other, other_policy = account_digest(accounts['other']), account_digest(
        accounts['other'], include_preferences=False)
    other_extensions = extension_lists(accounts['other'])
    for role in ('child', 'parent', 'other'):
        observe_launch(accounts[role], True)
    verify_gates(record)
    probe('login', 'other', 0, 'rollback.other-before', record)
    configure_restrictions(accounts)
    kiosk = pwd.getpwnam(PRODUCT)
    wait_kiosk_inactive(kiosk)
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    fedora = guest.package_path().suffix == '.rpm'
    state = {'accounts': accounts, 'other': other, 'other_policy': other_policy,
             'other_extensions': other_extensions, 'defaults': defaults,
             'preferences': preference_digest(child), 'boot': boot(),
             'pam_services': json.loads((guest.PAYLOAD / 'before.json').read_text())['pam_services'],
             'hook': '/etc/gdm/PreSession/Default' if fedora else '/etc/gdm3/PreSession/Default',
             'kiosk_name': kiosk.pw_name, 'kiosk_home': kiosk.pw_dir,
             'payload': [item['path'] for item in json.loads(
                 (guest.PAYLOAD / 'installed-files.json').read_text())]}
    if fedora:
        state['authselect'] = original_authselect()
    save_state(state)
    before = admission_removal_state()
    confinement_before = json.loads(Path('/var/lib/oh-no-parent-control/kiosk-confinement.json').read_text())
    gdm = confinement_before['pam']['gdm-password']
    source = gdm['before'] if gdm['before'] is not None else gdm['vendor']
    denial = ('# Oh No Parent Control removal admission barrier\n'
              'account requisite pam_succeed_if.so quiet user != oh-no-parent-control\n'
              'session requisite pam_succeed_if.so quiet user != oh-no-parent-control\n' + source).encode()
    home = Path(kiosk.pw_dir).lstat()
    policy = account_digest(child)
    extensions = extension_lists(child)
    native = account_state(child)[1:]
    expected = dict(zip(('limit_type', 'daily_limit', 'active_extension', 'app_filter'), native))
    expected.update(uid=child, extension_enabled=True)
    generated = {name: Path(name).read_bytes() if os.path.lexists(name) else None
                 for name in GENERATED_POLICY}
    pam = guest.pam_service_state()
    ordinary = {role: (pwd.getpwuid(accounts[role]), account_digest(accounts[role]),
                       extension_lists(accounts[role])) for role in ('parent', 'other')}
    integration = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
    with mounted_pam_fault(record):
        guest.run([integration, 'check-remove'], timeout=30)
        output, status = observe_aborted_transaction(child, expected, denial, record)
        # The self bind fails atomic replacement with EBUSY in both callbacks.
        # Source line numbers are diagnostic context, not part of the fault.
        failure = (rb'kiosk confinement configuration failed reason=os-error errno=%d'
                   rb'(?: source=kiosk-confinement line=[0-9]+)?; preserving ownership records'
                   % errno.EBUSY)
        guest.require(not package_absent() and len(re.findall(failure, output)) >= 2,
                      'rollback:native-callback-not-failed')
        if fedora:
            guest.require(b'preun' in output, 'rollback:rpm-preun-not-observed')
            guest.run(['rpm', '-q', PRODUCT])
        else:
            guest.require(status != 0 and b'package prerm maintainer script subprocess failed' in output and
                          b'package postinst maintainer script subprocess failed' in output,
                          'rollback:deb-callbacks-not-observed')
            guest.require(guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT]) ==
                          'install ok half-configured', 'rollback:unexpected-package-status')
        guest.verify_package_payload()
        guest.require(account_digest(child) == policy and extension_lists(child) == extensions and
                      all((Path(name).read_bytes() if os.path.lexists(name) else None) == value
                          for name, value in generated.items()), 'rollback:enforcement-not-restored')
        verify_other_account(state)
        guest.require(extension_lists(accounts['other']) == other_extensions,
                      'rollback:other-extension-changed')
        current = admission_removal_state()
        changed = {'/var/lib/oh-no-parent-control/kiosk-confinement.json',
                   '/var/lib/oh-no-parent-control/kiosk-confinement-removing',
                   '/var/lib/oh-no-parent-control/uninstall-broker-mask'}
        record('onpc.rollback.changed-records', json.dumps({
            name: {'before': value, 'after': current.get(name)}
            for name, value in before.items() if name not in changed and current.get(name) != value},
            sort_keys=True))
        guest.require(current.keys() == before.keys() and all(
            rollback_record_matches(name, value, current[name])
            for name, value in before.items() if name not in changed),
                      'rollback:foreign-or-ownership-state-changed')
        confinement = json.loads(Path('/var/lib/oh-no-parent-control/kiosk-confinement.json').read_text())
        guest.require({name: value for name, value in confinement.items()
                       if name not in ('removing', 'previous_pam')} == confinement_before,
                      'rollback:confinement-recovery-record-changed')
        guest.require(confinement.get('removing') is True and
                      Path('/var/lib/oh-no-parent-control/kiosk-confinement-removing').read_text() == 'removing\n' and
                      Path('/var/lib/oh-no-parent-control/uninstall-broker-mask').is_file() and
                      os.readlink('/run/systemd/system/oh-no-parent-control-broker.service') == '/dev/null',
                      'rollback:guards-released-before-restoration')
        guest.require(guest.pam_service_state() == pam and pwd.getpwnam(PRODUCT) == kiosk and
                      (Path(kiosk.pw_dir).lstat().st_dev, Path(kiosk.pw_dir).lstat().st_ino,
                       Path(kiosk.pw_dir).lstat().st_uid, Path(kiosk.pw_dir).lstat().st_gid,
                       Path(kiosk.pw_dir).lstat().st_mode) ==
                      (home.st_dev, home.st_ino, home.st_uid, home.st_gid, home.st_mode),
                      'rollback:identity-or-pam-changed')
        verify_loaded_confinement()
        observe_launch(child, False)
        for role in ('parent', 'other'):
            identity, digest, lists = ordinary[role]
            guest.require(pwd.getpwuid(accounts[role]) == identity and
                          account_digest(accounts[role]) == digest and
                          extension_lists(accounts[role]) == lists,
                          'rollback:ordinary-account-changed')
            observe_launch(accounts[role], True)
        probe('login', 'ordinary', 0, 'rollback.ordinary-guarded', record)
        probe('login', 'other', 0, 'rollback.other-guarded', record)
        probe('gdm-password', 'kiosk', 6, 'rollback.kiosk-guarded', record)
        record('onpc.rollback.restored-before-release',
               'exact-enforcement-restored; native-child-denied; ordinary-users-allowed; MAC-enforcing; removing-marker-and-mask-retained')
    if fedora:
        guest.install_package()
    else:
        guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
    guest.verify_package_files()
    guest.require(not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-confinement-removing') and
                  not os.path.lexists('/var/lib/oh-no-parent-control/uninstall-broker-mask') and
                  not os.path.lexists('/run/systemd/system/oh-no-parent-control-broker.service') and
                  not json.loads(Path('/var/lib/oh-no-parent-control/kiosk-confinement.json').read_text()).get('removing') and
                  account_digest(child) == policy, 'rollback:rearm-incomplete')
    verify_loaded_confinement()
    verify_gates(record)
    probe('login', 'other', 0, 'rollback.other-rearmed', record)
    output = guest.commands.run([integration, 'check-remove'], check=False,
                                timeout=30, merge_stderr=True)
    status = guest.commands.last_returncode
    guest.require(status == 0 or (status != 0 and b'legacy-pam-reboot-required' in output),
                  'rollback:unexpected-rearm-preflight-refusal')
    record('onpc.rollback.rearm-preflight',
           'passed' if status == 0 else 'legacy-pam-reboot-required')
    # RPM reinstall replaces the native PAM inode. Cached root login workers
    # must retire naturally at reboot before the same history retries removal.
    # Both platforms keep that reboot and finalization in this guarded attempt.
    state['rollback_rearm'] = {
        'boot': boot(), 'policy': policy, 'extensions': extensions,
        'kiosk_identity': [kiosk.pw_uid, kiosk.pw_gid, kiosk.pw_dir, kiosk.pw_shell],
        'kiosk_home': [home.st_ino, home.st_uid, home.st_gid, home.st_mode],
        'ordinary': {role: {'uid': accounts[role], 'policy': digest, 'extensions': lists,
                            'identity': [identity.pw_name, identity.pw_uid, identity.pw_gid,
                                         identity.pw_dir, identity.pw_shell]}
                     for role, (identity, digest, lists) in ordinary.items()},
    }
    save_state(state)
    record('onpc.rollback.rearmed', 'guards-released-after-restoration; native-rearm-complete')


def rollback_rearmed_rebooted(record):
    """Retire cached native PAM workers, then finalize the same owned retry."""
    guest.guard()
    guest.enable_diagnostics()
    from system_kiosk_admission import probe, verify_gates
    state = json.loads(state_path().read_text())
    rearm = state['rollback_rearm']
    guest.require(boot() != rearm['boot'] and guest.reboot_cleared(),
                  'rollback:rearm-reboot-not-observed')
    guest.installed()
    child, parent = state['accounts']['child'], state['accounts']['parent']
    guest.require(account_digest(child) == rearm['policy'] and
                  extension_lists(child) == rearm['extensions'],
                  'rollback:reboot-changed-restored-enforcement')
    kiosk = pwd.getpwnam(state['kiosk_name'])
    home = Path(kiosk.pw_dir).lstat()
    guest.require([kiosk.pw_uid, kiosk.pw_gid, kiosk.pw_dir, kiosk.pw_shell] ==
                  rearm['kiosk_identity'] and
                  [home.st_ino, home.st_uid, home.st_gid, home.st_mode] == rearm['kiosk_home'],
                  'rollback:reboot-changed-kiosk-identity')
    observe_launch(child, False)
    for role, before in rearm['ordinary'].items():
        identity = pwd.getpwuid(before['uid'])
        guest.require([identity.pw_name, identity.pw_uid, identity.pw_gid,
                       identity.pw_dir, identity.pw_shell] == before['identity'] and
                      account_digest(before['uid']) == before['policy'] and
                      extension_lists(before['uid']) == before['extensions'],
                      'rollback:reboot-changed-ordinary-account')
        observe_launch(before['uid'], True)
    verify_loaded_confinement()
    verify_gates(record)
    probe('login', 'other', 0, 'rollback.other-rebooted', record)
    wait_kiosk_inactive(kiosk)
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
               'check-remove'], timeout=30)
    record('onpc.rollback.rearm-reboot', 'new-boot; restored-enforcement-and-identities-preserved; removal-preflight-passed')
    guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state, record=record)
    probe('login', 'ordinary', 0, 'rollback.ordinary-removed', record)
    probe('login', 'other', 0, 'rollback.other-removed', record)
    observe_launch(parent, True)
    record('onpc.rollback.retry-finalized', 'native-remove-succeeded; owned-account-deleted; exact-original-PAM-restored')


FINALIZATION_VARIANTS = ('denial-publication', 'mac-unload', 'account-finalization')


def removal_denials(saved):
    """Independent expected vendor-only stacks, retaining original callback bytes."""
    prefix = ('# Oh No Parent Control removal admission barrier\n'
              'account requisite pam_succeed_if.so quiet user != oh-no-parent-control\n'
              'session requisite pam_succeed_if.so quiet user != oh-no-parent-control\n')
    return {name: (prefix + (value['before'] if value['before'] is not None
                            else value['vendor'])).encode()
            for name, value in saved['pam'].items()}


def verify_payload_erased(state):
    """A failed postrm can leave dpkg half-installed despite actual file erasure."""
    for name in state['payload']:
        if name == DEBIAN_NOTICE:
            continue
        guest.require(not os.path.lexists(name), 'finalization:payload-not-erased')


def persistent_home_identity(path, info=None):
    """Btrfs device numbers can change across boots; UUID/subvolume IDs persist."""
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate filesystem field')
            result[key] = value
        return result

    try:
        observed = json.loads(guest.run([
            'findmnt', '--json', '--target', str(path), '--output',
            'UUID,FSTYPE,FS-OPTIONS'], timeout=15), object_pairs_hook=unique_fields)
    except (ValueError, TypeError):
        raise guest.GuestError('finalization:home-filesystem-identity') from None
    category = 'finalization:home-filesystem-identity'
    guest.require(type(observed) is dict and set(observed) == {'filesystems'} and
                  type(observed['filesystems']) is list and
                  len(observed['filesystems']) == 1, category)
    filesystem = observed['filesystems'][0]
    guest.require(type(filesystem) is dict and
                  set(filesystem) == {'uuid', 'fstype', 'fs-options'} and
                  type(filesystem['uuid']) is str and re.fullmatch(
                      r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
                      r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', filesystem['uuid']) and
                  type(filesystem['fstype']) is str and
                  re.fullmatch(r'[a-z0-9_+-]+', filesystem['fstype']) and
                  type(filesystem['fs-options']) is str and filesystem['fs-options'], category)
    subvolume = None
    if filesystem['fstype'] == 'btrfs':
        values = [option.partition('=')[2] for option in filesystem['fs-options'].split(',')
                  if option.partition('=')[0] == 'subvolid']
        guest.require(len(values) == 1 and re.fullmatch(r'[0-9]+', values[0]), category)
        subvolume = str(int(values[0]))
    info = path.lstat() if info is None else info
    return [filesystem['fstype'], filesystem['uuid'].lower(), subvolume,
            info.st_ino, info.st_uid, info.st_gid, info.st_mode]


def verify_surviving_identity(state, recovery, record=None, *, home_conflict=False):
    kiosk = pwd.getpwnam(state['kiosk_name'])
    identity = [kiosk.pw_uid, kiosk.pw_gid, kiosk.pw_dir, kiosk.pw_shell]
    # A separately pinned ownership fixture verifies the substituted home while
    # it is active. All ordinary identities and the real kiosk NSS entry still
    # participate; the exact original home is checked again after resolution.
    home = None if home_conflict else Path(kiosk.pw_dir).lstat()
    home_identity = None if home_conflict else persistent_home_identity(Path(kiosk.pw_dir), home)
    if record is not None:
        record('onpc.finalization.identity-comparison', json.dumps({
            'account_fields': dict(zip(('uid', 'gid', 'home', 'shell'),
                (actual == expected for actual, expected in
                 zip(identity, recovery['kiosk_identity'])))),
            'home_fields': dict(zip(('filesystem', 'uuid', 'subvolume', 'inode', 'uid', 'gid', 'mode'),
                (actual == expected for actual, expected in
                 zip(home_identity or (), recovery['kiosk_home'])))),
            'home_conflict': home_conflict,
            'home_device': home.st_dev if home is not None else None,
            'saved_home_device': recovery['home_device'],
        }, sort_keys=True))
    guest.require(identity == recovery['kiosk_identity'] and
                  (home_conflict or home_identity == recovery['kiosk_home']),
                  'finalization:kiosk-identity-changed')
    for role, before in recovery['ordinary'].items():
        account = pwd.getpwuid(before['uid'])
        guest.require([account.pw_name, account.pw_uid, account.pw_gid,
                       account.pw_dir, account.pw_shell] == before['identity'] and
                      account_digest(before['uid']) == before['policy'] and
                      extension_lists(before['uid']) == before['extensions'],
                      'finalization:ordinary-account-changed')
        observe_launch(before['uid'], True)
    verify_other_account(state)
    guest.require(preference_digest(state['accounts']['child']) == state['preferences'],
                  'finalization:preferences-changed')


def verify_durable_interval(state, recovery, saved, record, *, conflict=None):
    """Exercise actual installed account and session callbacks with no product code."""
    from system_kiosk_admission import durable_probe, probe
    verify_payload_erased(state)
    if conflict is None:
        verify_surviving_identity(state, recovery, record)
    else:
        conflict.verify()
        verify_surviving_identity(state, recovery, record,
                                  home_conflict=conflict.variant.startswith('home-'))
    current = json.loads(Path('/var/lib/oh-no-parent-control/kiosk-confinement.json').read_text())
    guest.require(current.get('removing') is True and
                  {key: value for key, value in current.items() if key != 'removing'} == saved and
                  Path('/var/lib/oh-no-parent-control/kiosk-confinement-removing').read_text() == 'removing\n' and
                  Path('/var/lib/oh-no-parent-control/package-created-kiosk-uid').read_text().strip() ==
                  str(conflict.expected_marker_uid if conflict is not None and
                      conflict.expected_marker_uid is not None else recovery['kiosk_identity'][0]),
                  'finalization:recovery-records-changed')
    for service, expected in removal_denials(saved).items():
        target = Path('/etc/pam.d') / service
        guest.require(fault_file_identity(target)[-1] == expected and
                      b'pam_oh_no_parent_control' not in expected,
                      'finalization:durable-denial-not-installed')
        record('onpc.finalization.durable.' + service, hashlib.sha256(expected).hexdigest())
        for role in ('ordinary', 'other'):
            durable_probe(service, role, 'account', 0, service + '.' + role, record)
        for callback in ('account', 'session'):
            durable_probe(service, 'kiosk', callback, 7, service + '.kiosk.' + callback, record)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'finalization.payload-erased.' + role, record)
    if guest.package_path().suffix == '.rpm':
        guest.require(guest.run(['getenforce']) == 'Enforcing', 'finalization:selinux-not-enforcing')
        permissive = guest.run(['/usr/sbin/semanage', 'permissive', '-l'])
        guest.require(not {'xdm_t', 'init_t', 'onpc_kiosk_t'} & set(permissive.split()),
                      'finalization:domain-not-enforcing')
        guest.require(not any(row.split()[0] == 'onpc-kiosk' for row in
                              guest.run(['/usr/sbin/semodule', '-l']).splitlines() if row.split()),
                      'finalization:mac-not-unloaded')
    else:
        guest.require(not any(row.startswith('onpc-kiosk-') for row in
                              Path('/sys/kernel/security/apparmor/profiles').read_text().splitlines()),
                      'finalization:mac-not-unloaded')
    record('onpc.finalization.payload-erased-interval',
           'owned-account-and-recovery-records-retained; native-account-and-session-denied; ordinary-users-allowed; product-MAC-unloaded')


def focused_recovery_start(record, variant, state_key):
    """Shared fresh controls and independent removal oracle for focused histories."""
    guest.guard()
    guest.enable_diagnostics()
    from system_kiosk_admission import durable_probe, verify_gates
    accounts = provision_native()
    parent, child = accounts['parent'], accounts['child']
    defaults = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    guest.require(defaults['parent_control_enabled'] is False and defaults['apps'] == {},
                  'finalization:nonfresh-start')
    other = account_digest(accounts['other'])
    other_policy = account_digest(accounts['other'], include_preferences=False)
    other_extensions = extension_lists(accounts['other'])
    for role in ('child', 'parent', 'other'):
        observe_launch(accounts[role], True)
    verify_gates(record)
    for service in ('gdm-password', 'systemd-user'):
        for role in ('ordinary', 'other'):
            durable_probe(service, role, 'account', 0, service + '.' + role + '.before', record)
    configure_restrictions(accounts)
    kiosk = pwd.getpwnam(PRODUCT)
    wait_kiosk_inactive(kiosk)
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    home = Path(kiosk.pw_dir).lstat()
    fedora = guest.package_path().suffix == '.rpm'
    state = {'accounts': accounts, 'other': other, 'other_policy': other_policy,
             'other_extensions': other_extensions, 'defaults': defaults,
             'preferences': preference_digest(child), 'boot': boot(),
             'pam_services': json.loads((guest.PAYLOAD / 'before.json').read_text())['pam_services'],
             'hook': '/etc/gdm/PreSession/Default' if fedora else '/etc/gdm3/PreSession/Default',
             'kiosk_name': kiosk.pw_name, 'kiosk_home': kiosk.pw_dir,
             'payload': [item['path'] for item in json.loads(
                 (guest.PAYLOAD / 'installed-files.json').read_text())]}
    if fedora:
        state['authselect'] = original_authselect()
    saved = json.loads(Path('/var/lib/oh-no-parent-control/kiosk-confinement.json').read_text())
    before = admission_removal_state()
    generated = {name: Path(name).read_bytes() if os.path.lexists(name) else None
                 for name in GENERATED_POLICY}
    policy = account_digest(child)
    extensions = extension_lists(child)
    recovery = {'variant': variant, 'policy': policy, 'extensions': extensions,
                'kiosk_identity': [kiosk.pw_uid, kiosk.pw_gid, kiosk.pw_dir, kiosk.pw_shell],
                'kiosk_home': persistent_home_identity(Path(kiosk.pw_dir), home),
                'home_device': home.st_dev,
                'ordinary': {}}
    for role in ('parent', 'other'):
        account = pwd.getpwuid(accounts[role])
        recovery['ordinary'][role] = {
            'uid': accounts[role], 'policy': account_digest(accounts[role]),
            'extensions': extension_lists(accounts[role]),
            'identity': [account.pw_name, account.pw_uid, account.pw_gid,
                         account.pw_dir, account.pw_shell]}
    state[state_key] = recovery
    save_state(state)
    return state, recovery, saved, before, generated


def interrupted_finalization_retry(record, variant):
    """One native interruption, protected interval and owned recovery per history."""
    guest.guard()
    guest.require(variant in FINALIZATION_VARIANTS, 'finalization:variant')
    from system_kiosk_admission import probe, verify_gates
    from system_removal_faults import interruption_fault
    state, recovery, saved, before, generated = focused_recovery_start(
        record, variant, 'finalization_retry')
    child = state['accounts']['child']
    policy, extensions = recovery['policy'], recovery['extensions']
    fedora = guest.package_path().suffix == '.rpm'
    expected = dict(zip(('limit_type', 'daily_limit', 'active_extension', 'app_filter'),
                        account_state(child)[1:]))
    expected.update(uid=child, extension_enabled=True)
    with interruption_fault(variant, record) as fault:
        output, status = observe_aborted_transaction(
            child, expected, removal_denials(saved)['gdm-password'], record)
        fault.verify_triggered()
        record('onpc.finalization.native-status', str(status))
        if variant == 'account-finalization':
            guest.require(b'refusing cleanup of a mounted directory' in output,
                          'finalization:account-callback-not-interrupted')
            verify_durable_interval(state, recovery, saved, record)
        else:
            guest.require(not package_absent() and
                          b'kiosk confinement configuration failed' in output,
                          'finalization:preerase-callback-not-interrupted')
            guest.verify_package_payload()
            verify_surviving_identity(state, recovery, record)
            guest.require(account_digest(child) == policy and extension_lists(child) == extensions and
                          all((Path(name).read_bytes() if os.path.lexists(name) else None) == value
                              for name, value in generated.items()),
                          'finalization:enforcement-not-restored')
            current = admission_removal_state()
            mutable = {'/var/lib/oh-no-parent-control/kiosk-confinement.json',
                       '/var/lib/oh-no-parent-control/kiosk-confinement-removing',
                       '/var/lib/oh-no-parent-control/uninstall-broker-mask'}
            guest.require(current.keys() == before.keys() and all(
                rollback_record_matches(name, value, current[name])
                for name, value in before.items() if name not in mutable),
                          'finalization:foreign-or-ownership-state-changed')
            confinement = json.loads(Path('/var/lib/oh-no-parent-control/kiosk-confinement.json').read_text())
            guest.require({name: value for name, value in confinement.items()
                           if name not in ('removing', 'previous_pam')} == saved,
                          'finalization:confinement-recovery-record-changed')
            verify_loaded_confinement()
            observe_launch(child, False)
            for role in ('ordinary', 'other'):
                probe('login', role, 0, 'finalization.restored.' + role, record)
            record('onpc.finalization.restored-before-fault-release',
                   'exact-native-policy-restored; child-denied; ordinary-users-allowed; MAC-enforcing')
    if variant == 'account-finalization' and not fedora:
        # dpkg retains its native postrm and reruns that callback without payload.
        guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
        verify_removed(state, record=record)
        recovery['completed'] = True
    else:
        # RPM has no postun retry entry after erasure. Its supported normal
        # reinstall rearms the surviving owned account; purge chains stay in 4-6.
        if fedora:
            guest.install_package()
        else:
            status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
            guest.require(status in ('install ok installed', 'install ok half-configured'),
                          'finalization:unexpected-rearm-package-status')
            # An unload-only fault allows abort-remove to finish rearming.
            # dpkg rejects --configure for that already configured package.
            if status == 'install ok half-configured':
                guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
        guest.verify_package_files()
        verify_surviving_identity(state, recovery, record)
        guest.require(account_digest(child) == policy and extension_lists(child) == extensions,
                      'finalization:rearm-changed-enforcement')
        verify_loaded_confinement()
        guest.require(not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-confinement-removing') and
                      not os.path.lexists('/var/lib/oh-no-parent-control/uninstall-broker-mask') and
                      not os.path.lexists('/run/systemd/system/oh-no-parent-control-broker.service'),
                      'finalization:rearm-guards-retained')
        verify_gates(record)
        recovery['completed'] = False
    recovery['boot'] = boot()
    save_state(state)
    record('onpc.finalization.owned-recovery', 'native-retry-complete' if recovery['completed']
           else 'native-rearm-complete; reboot-and-removal-pending')


def finalization_retry_rebooted(record, variant):
    """Finish only the same history after a real reboot, with no snapshot splice."""
    recovery_retry_rebooted(record, variant, 'finalization_retry', FINALIZATION_VARIANTS,
                            'finalization')


def recovery_retry_rebooted(record, variant, state_key, variants, label):
    """Shared endpoint for one resolved, identity-bound recovery history."""
    guest.guard()
    guest.require(variant in variants, label + ':variant')
    guest.enable_diagnostics()
    from system_kiosk_admission import probe, verify_gates
    state = json.loads(state_path().read_text())
    recovery = state[state_key]
    guest.require(recovery['variant'] == variant and boot() != recovery['boot'],
                  label + ':retry-identity-or-boot')
    if not recovery['completed']:
        guest.installed()
        verify_surviving_identity(state, recovery, record)
        guest.require(account_digest(state['accounts']['child']) == recovery['policy'] and
                      extension_lists(state['accounts']['child']) == recovery['extensions'],
                      label + ':reboot-changed-enforcement')
        verify_loaded_confinement()
        verify_gates(record)
        observe_launch(state['accounts']['child'], False)
        wait_kiosk_inactive(pwd.getpwnam(PRODUCT))
        guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
                   'check-remove'], timeout=30)
        guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state, record=record)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, label + '.completed.' + role, record)
    observe_launch(state['accounts']['parent'], True)
    record('onpc.' + label + '.retry-finalized',
           'new-boot; native-remove-succeeded; owned-account-and-home-deleted; exact-original-PAM-and-disposition-restored')


def private_recovery_record(path):
    """Private root-owned records may retain the package's administrator group."""
    from system_removal_ownership import witness
    value = witness(path)
    _, _, uid, _, mode, links = value.metadata
    guest.require(stat.S_ISREG(mode) and uid == 0 and
                  stat.S_IMODE(mode) == 0o600 and links == 1,
                  'identity-filesystem:unsafe-recovery-record')
    return value


def observe_rpm_reinstall(state, recovery, generated, record):
    """Witness restored enforcement while durable admission still excludes kiosk."""
    from guest_install_recipe import install
    guest.guard()
    guest.enable_diagnostics()
    transaction = guest.Commands()
    transaction.directory = Path(tempfile.mkdtemp(
        prefix='rpm-reinstall-', dir=guest.commands.directory.parent))
    result = {}

    def execute():
        try:
            def run(arguments, timeout=120):
                return transaction.run(arguments, timeout=timeout,
                                       merge_stderr=True).decode().strip()
            install(run, guest.guard, guest.package_path())
        except BaseException as error:
            result['error'] = error

    worker = threading.Thread(target=execute, name='onpc-rpm-reinstall')
    snapshot = Path('/var/lib/oh-no-parent-control/uninstall-enforcement.json')
    marker = Path('/var/lib/oh-no-parent-control/kiosk-confinement-removing')
    observed = False
    worker.start()
    try:
        while worker.is_alive():
            try:
                guarded = marker.read_bytes() == b'removing\n'
            except FileNotFoundError:
                guarded = False
            if not os.path.lexists(snapshot) and guarded:
                restored = (account_digest(state['accounts']['child']) == recovery['policy'] and
                            extension_lists(state['accounts']['child']) == recovery['extensions'] and
                            all((Path(name).read_bytes() if os.path.lexists(name) else None) == value
                                for name, value in generated.items()))
                if restored:
                    observe_launch(state['accounts']['child'], False)
                # Bracket the complete native read: an endpoint after the
                # barrier was released cannot supply this transition receipt.
                try:
                    guarded = marker.read_bytes() == b'removing\n'
                except FileNotFoundError:
                    guarded = False
                if restored and guarded:
                    observed = True
                    break
            time.sleep(0.01)
    finally:
        # The recipe owns only make install and its Commands timeout/pidfd.
        # Always join it, including failed observations and cancellation.
        worker.join()
    if 'error' in result:
        raise result['error']
    guest.require(observed, 'rpm-posterase:restoration-before-release-not-observed')
    record('onpc.rpm-posterase.restored-before-release',
           'snapshot-consumed; exact-native-policy-extension-and-rules-restored; native-child-execution-denied; durable-admission-marker-retained')


def rpm_posterase_recovery(record):
    """Real failed packaged RPM purge, retained conflict and normal reinstall."""
    guest.guard()
    guest.require(guest.package_path().suffix == '.rpm', 'rpm-posterase:fedora-required')
    from system_kiosk_admission import probe, verify_gates
    from system_removal_identity import identity_filesystem_conflict
    state, recovery, saved, before, generated = focused_recovery_start(
        record, 'rpm-posterase', 'rpm_posterase')
    child = state['accounts']['child']
    recovery['ordinary_native'] = {
        role: account_digest(value['uid'], include_preferences=False)
        for role, value in recovery['ordinary'].items()}
    snapshot_account = dict(zip(('limit_type', 'daily_limit', 'active_extension', 'app_filter'),
                                account_state(child)[1:]))
    snapshot_account.update(uid=child, extension_enabled=True)
    authselect = json.loads(private_recovery_record(Path(
        '/var/lib/oh-no-parent-control/fedora-authselect.json')).contents)
    provenance = private_recovery_record(Path(
        '/var/lib/oh-no-parent-control/fedora-execution-policy.json'))
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
               'check-remove'], timeout=30)
    with identity_filesystem_conflict('home-mount', state['accounts']['other'], record) as conflict:
        output = guest.commands.run(['/usr/bin/oh-no-parent-control-purge', '--yes'],
                                    check=False, timeout=1800, merge_stderr=True)
        record('onpc.rpm-posterase.failed-purge-status', str(guest.commands.last_returncode))
        guest.require(guest.commands.last_returncode != 0 and package_absent() and
                      b'postun' in output and conflict.reason in output and
                      b'saved-state purge outcome=accepted' not in output,
                      'rpm-posterase:native-postun-failure-not-observed')
        verify_durable_interval(state, recovery, saved, record, conflict=conflict)
        snapshot = private_recovery_record(Path(
            '/var/lib/oh-no-parent-control/uninstall-enforcement.json'))
        guest.require(json.loads(snapshot.contents) == {'version': 1, 'accounts': [snapshot_account]},
                      'rpm-posterase:rollback-snapshot-not-retained')
        mask = Path('/run/systemd/system/oh-no-parent-control-broker.service')
        guest.require(fault_file_identity(Path(
            '/var/lib/oh-no-parent-control/uninstall-broker-mask'))[-1] == b'' and
                      stat.S_ISLNK(mask.lstat().st_mode) and mask.lstat().st_uid == 0 and
                      os.readlink(mask) == '/dev/null', 'rpm-posterase:removal-mask-not-retained')
        guest.require(json.loads(private_recovery_record(Path(
            '/var/lib/oh-no-parent-control/fedora-authselect.json')).contents) ==
                      dict(authselect, phase='restored') and private_recovery_record(Path(
            '/var/lib/oh-no-parent-control/fedora-execution-policy.json')) == provenance,
                      'rpm-posterase:recovery-provenance-changed')
        guest.require(Path('/var/log/oh-no-parent-control').is_dir() and
                      not os.path.lexists('/run/oh-no-parent-control-purge-intent.json'),
                      'rpm-posterase:logs-or-intent-not-retained-safely')
        record('onpc.rpm-posterase.retained',
               'RPM-absent; real-postun-refused; payload-erased; foreign-home-and-sentinel-preserved; exact-rollback-authselect-and-execution-records-retained')
        observe_rpm_reinstall(state, recovery, generated, record)
        guest.verify_package_files()
        conflict.verify()
        verify_surviving_identity(state, recovery, record)
        guest.require(account_digest(child) == recovery['policy'] and
                      extension_lists(child) == recovery['extensions'],
                      'rpm-posterase:reinstall-changed-enforcement')
        verify_loaded_confinement()
        verify_gates(record)
        observe_launch(child, False)
        for role in ('ordinary', 'other'):
            probe('login', role, 0, 'rpm-posterase.reinstalled.' + role, record)
        guest.require(all(not os.path.lexists('/var/lib/oh-no-parent-control/' + name)
                          for name in ('kiosk-confinement-removing', 'uninstall-enforcement.json',
                                       'uninstall-broker-mask', 'migration-in-progress')),
                      'rpm-posterase:reinstall-guards-retained')
        conflict.verify()
        record('onpc.rpm-posterase.reinstalled',
               'normal-make-install; exact-enforcement-restored; MAC-enforcing; native-gates-rearmed; foreign-conflict-preserved')
    verify_surviving_identity(state, recovery, record)
    recovery['boot'] = boot()
    save_state(state)
    record('onpc.rpm-posterase.resolved',
           'only-recorded-mount-and-fixture-resolved; reboot-and-repeated-packaged-purge-pending')


def rpm_posterase_reinstalled_rebooted(record):
    """Finish the same RPM recovery with a real reboot and repeated public purge."""
    guest.guard()
    guest.require(guest.package_path().suffix == '.rpm', 'rpm-posterase:fedora-required')
    guest.enable_diagnostics()
    from system_kiosk_admission import probe, verify_gates
    state = json.loads(state_path().read_text())
    recovery = state['rpm_posterase']
    guest.require(recovery['variant'] == 'rpm-posterase' and boot() != recovery['boot'] and
                  guest.reboot_cleared(), 'rpm-posterase:retry-identity-or-boot')
    guest.installed()
    verify_surviving_identity(state, recovery, record)
    guest.require(account_digest(state['accounts']['child']) == recovery['policy'] and
                  extension_lists(state['accounts']['child']) == recovery['extensions'],
                  'rpm-posterase:reboot-changed-enforcement')
    verify_loaded_confinement()
    verify_gates(record)
    observe_launch(state['accounts']['child'], False)
    wait_kiosk_inactive(pwd.getpwnam(PRODUCT))
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
               'check-remove'], timeout=30)
    output = guest.commands.run(['/usr/bin/oh-no-parent-control-purge', '--yes'],
                                timeout=1800, merge_stderr=True)
    verify_removed(state, purged=True, record=record)
    guest.require(b'saved-state purge outcome=accepted' in output and
                  REMOVAL_NOTICE.encode() in output and guest.reboot_requested() and
                  not os.path.lexists('/run/oh-no-parent-control-purge-intent.json'),
                  'rpm-posterase:purge-not-confirmed')
    for role, before in recovery['ordinary'].items():
        account = pwd.getpwuid(before['uid'])
        guest.require([account.pw_name, account.pw_uid, account.pw_gid,
                       account.pw_dir, account.pw_shell] == before['identity'] and
                      account_digest(before['uid'], include_preferences=False) ==
                      recovery['ordinary_native'][role] and
                      extension_lists(before['uid']) == before['extensions'],
                      'rpm-posterase:purge-changed-ordinary-account')
        observe_launch(before['uid'], True)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'rpm-posterase.purged.' + role, record)
    password_login_health(state['accounts']['child'])
    record('onpc.rpm-posterase.completed',
           'new-boot; repeated-packaged-purge-accepted; owned-account-and-home-deleted; exact-original-PAM-and-authselect-restored; ordinary-users-allowed; SELinux-enforcing')


def identity_filesystem_refusal_retry(record, variant):
    """Keep each foreign root/identity, native refusal and owned retry together."""
    guest.guard()
    from system_kiosk_admission import probe, verify_gates
    from system_removal_identity import IDENTITY_FILESYSTEM_VARIANTS, identity_filesystem_conflict
    guest.require(variant in IDENTITY_FILESYSTEM_VARIANTS, 'identity-filesystem:variant')
    state, recovery, saved, before, generated = focused_recovery_start(
        record, variant, 'identity_filesystem_retry')
    child = state['accounts']['child']
    fedora = guest.package_path().suffix == '.rpm'
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
               'check-remove'], timeout=30)
    guards = ('/var/lib/oh-no-parent-control/kiosk-confinement-removing',
              '/var/lib/oh-no-parent-control/uninstall-enforcement.json',
              '/var/lib/oh-no-parent-control/uninstall-broker-mask',
              '/run/systemd/system/oh-no-parent-control-broker.service')
    guest.require(all(not os.path.lexists(name) for name in guards),
                  'identity-filesystem:nonfresh-guards')
    snapshot_account = dict(zip(('limit_type', 'daily_limit', 'active_extension', 'app_filter'),
                                account_state(child)[1:]))
    snapshot_account.update(uid=child, extension_enabled=True)
    authselect_before = (json.loads(Path(
        '/var/lib/oh-no-parent-control/fedora-authselect.json').read_text()) if fedora else None)
    execution_provenance = (private_recovery_record(Path(
        '/var/lib/oh-no-parent-control/fedora-execution-policy.json')) if fedora else None)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'identity-filesystem.before.' + role, record)
    with identity_filesystem_conflict(variant, state['accounts']['other'], record) as conflict:
        output = guest.commands.run(removal_command(), check=False, timeout=1800,
                                    merge_stderr=True)
        status = guest.commands.last_returncode
        record('onpc.identity-filesystem.native-status', str(status))
        guest.require(conflict.reason in output and (fedora or status != 0),
                      'identity-filesystem:native-conflict-not-refused')
        conflict.verify()
        if conflict.preflight:
            guest.require(status != 0 and not package_absent(),
                          'identity-filesystem:preflight-erased-payload')
            guest.verify_package_payload()
            verify_surviving_identity(state, recovery, record)
            guest.require(account_digest(child) == recovery['policy'] and
                          extension_lists(child) == recovery['extensions'] and all(
                              (Path(name).read_bytes() if os.path.lexists(name) else None) == value
                              for name, value in generated.items()),
                          'identity-filesystem:enforcement-changed')
            current = admission_removal_state()
            guest.require(current.keys() == before.keys() and all(
                rollback_record_matches(name, value, current[name])
                for name, value in before.items()), 'identity-filesystem:recovery-records-changed')
            guest.require(all(not os.path.lexists(name) for name in guards),
                          'identity-filesystem:preflight-published-removal-guards')
            verify_loaded_confinement()
            observe_launch(child, False)
            for role in ('ordinary', 'other'):
                probe('login', role, 0, 'identity-filesystem.refused.' + role, record)
            probe('login', 'kiosk', 6, 'identity-filesystem.refused.kiosk', record)
        else:
            # Fedora may report a successful erase despite failed postun. The
            # retained account, exact callback diagnostic and live distribution
            # PAM denials, rather than that exit code, establish safe refusal.
            verify_durable_interval(state, recovery, saved, record, conflict=conflict)
            snapshot_path = Path('/var/lib/oh-no-parent-control/uninstall-enforcement.json')
            snapshot = json.loads(fault_file_identity(snapshot_path)[-1])
            guest.require(stat.S_IMODE(snapshot_path.lstat().st_mode) == 0o600 and
                          snapshot == {'version': 1, 'accounts': [snapshot_account]},
                          'identity-filesystem:rollback-snapshot-not-retained')
            record('onpc.identity-filesystem.rollback-snapshot',
                   hashlib.sha256(snapshot_path.read_bytes()).hexdigest())
            mask = Path('/run/systemd/system/oh-no-parent-control-broker.service')
            guest.require(fault_file_identity(Path(guards[2]))[-1] == b'' and
                          stat.S_ISLNK(mask.lstat().st_mode) and mask.lstat().st_uid == 0 and
                          os.readlink(mask) == '/dev/null',
                          'identity-filesystem:removal-mask-not-retained')
            current = admission_removal_state()
            retained = ('/var/lib/oh-no-parent-control/malcontent-pam-before-install',)
            if variant == 'state-mount':
                retained += tuple('/var/lib/oh-no-parent-control/' + name for name in (
                    'installed-gdm-presession', 'installed-fapolicyd-fallback',
                    'installed-child-extension-trust', 'fapolicyd-before-install',
                    'child-trust-backend'))
            guest.require(all(current.get(name) == value for name, value in before.items()
                              if any(name == root or name.startswith(root + '/') for root in retained)),
                          'identity-filesystem:owned-recovery-records-changed')
            if fedora:
                guest.require(json.loads(private_recovery_record(Path(
                    '/var/lib/oh-no-parent-control/fedora-authselect.json')).contents) ==
                    dict(authselect_before, phase='restored') and private_recovery_record(Path(
                    '/var/lib/oh-no-parent-control/fedora-execution-policy.json')) == execution_provenance,
                    'identity-filesystem:fedora-recovery-provenance-changed')
        conflict.verify()
        record('onpc.identity-filesystem.refused', variant +
               '; exact-conflict-and-foreign-state-preserved; recovery-records-retained; ordinary-users-allowed; kiosk-admission-denied')
    # Restore only the attempt's conflict before invoking any recovery callback.
    verify_surviving_identity(state, recovery, record)
    if not conflict.preflight and not fedora:
        guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
        verify_removed(state, record=record)
        recovery['completed'] = True
    else:
        if fedora and not conflict.preflight:
            guest.install_package()
        elif not fedora:
            status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
            guest.require(status in ('install ok installed', 'install ok half-configured'),
                          'identity-filesystem:unexpected-rearm-package-status')
            if status == 'install ok half-configured':
                guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
        guest.verify_package_files()
        verify_surviving_identity(state, recovery, record)
        guest.require(account_digest(child) == recovery['policy'] and
                      extension_lists(child) == recovery['extensions'],
                      'identity-filesystem:rearm-changed-enforcement')
        verify_loaded_confinement()
        guest.require(all(not os.path.lexists(name) for name in guards),
                      'identity-filesystem:rearm-guards-retained')
        verify_gates(record)
        recovery['completed'] = False
    recovery['boot'] = boot()
    save_state(state)
    record('onpc.identity-filesystem.resolved', variant +
           '; only-recorded-conflict-resolved; ' + ('native-retry-complete' if recovery['completed']
           else 'native-rearm-complete; reboot-and-removal-pending'))


def identity_filesystem_retry_rebooted(record, variant):
    guest.guard()
    from system_removal_identity import IDENTITY_FILESYSTEM_VARIANTS
    guest.require(guest.reboot_cleared(), 'identity-filesystem:reboot-required')
    recovery_retry_rebooted(record, variant, 'identity_filesystem_retry',
                            IDENTITY_FILESYSTEM_VARIANTS, 'identity-filesystem')


def ownership_refusal_retry(record, variant):
    """Preserve one foreign conflict through native refusal, then rearm its owner."""
    guest.guard()
    from system_kiosk_admission import probe, verify_gates
    from system_removal_ownership import OWNERSHIP_VARIANTS, ownership_conflict
    guest.require(variant in OWNERSHIP_VARIANTS, 'ownership:variant')
    state, recovery, saved, before, generated = focused_recovery_start(
        record, variant, 'ownership_retry')
    child = state['accounts']['child']
    integration = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
    guest.run([integration, 'check-remove'], timeout=30)
    targets = {
        'systemd-user-edit': Path('/etc/pam.d/systemd-user'),
        'gdm-password-link': Path('/etc/pam.d/gdm-password'),
        'systemd-user-link': Path('/etc/pam.d/systemd-user'),
        'gdm-hook-link': Path(state['hook']),
    }
    target = targets.get(variant, Path('/var/lib/oh-no-parent-control/kiosk-confinement.json'))
    reasons = {'systemd-user-edit': b'reason=modified-pam-confinement',
               'gdm-hook-link': b'system integration was modified; preserving it and refusing removal',
               'confinement-record-uid': b'reason=changed-kiosk-identity'}
    reason = reasons.get(variant, b'reason=unsafe-confinement-path')
    guards = ('/var/lib/oh-no-parent-control/kiosk-confinement-removing',
              '/var/lib/oh-no-parent-control/uninstall-enforcement.json',
              '/var/lib/oh-no-parent-control/uninstall-broker-mask',
              '/run/systemd/system/oh-no-parent-control-broker.service')
    guest.require(all(not os.path.lexists(name) for name in guards), 'ownership:nonfresh-guards')
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'ownership.before.' + role, record)
    with ownership_conflict(variant, target, state['accounts']['other'], record) as conflict:
        # This is the real package callback, before reversible cleanup. A
        # diagnostic preflight alone cannot establish safe native refusal.
        output = guest.commands.run(removal_command(), check=False, timeout=1800,
                                    merge_stderr=True)
        status = guest.commands.last_returncode
        record('onpc.ownership.native-status', str(status))
        guest.require(status != 0 and not package_absent() and reason in output,
                      'ownership:native-conflict-not-refused')
        conflict.verify()
        guest.verify_package_payload()
        verify_surviving_identity(state, recovery, record)
        guest.require(account_digest(child) == recovery['policy'] and
                      extension_lists(child) == recovery['extensions'] and
                      all((Path(name).read_bytes() if os.path.lexists(name) else None) == value
                          for name, value in generated.items()), 'ownership:enforcement-changed')
        current = admission_removal_state(exclude=(str(target),))
        expected = {name: value for name, value in before.items() if name != str(target)}
        guest.require(current.keys() == expected.keys() and all(
            rollback_record_matches(name, value, current[name])
            for name, value in expected.items()), 'ownership:recovery-records-changed')
        guest.require(all(not os.path.lexists(name) for name in guards),
                      'ownership:preflight-published-removal-guards')
        if not variant.startswith('confinement-record-'):
            guest.require(json.loads(Path('/var/lib/oh-no-parent-control/kiosk-confinement.json').read_text()) == saved,
                          'ownership:confinement-record-changed')
        verify_loaded_confinement()
        observe_launch(child, False)
        for role in ('ordinary', 'other'):
            probe('login', role, 0, 'ownership.refused.' + role, record)
        probe('login', 'kiosk', 6, 'ownership.refused.kiosk', record)
        conflict.verify()
        record('onpc.ownership.refused',
               variant + '; exact-conflict-and-recovery-records-preserved; payload-retained; child-denied; ordinary-users-allowed; MAC-enforcing; no-removal-guards-published')
    if guest.package_path().suffix == '.deb':
        status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
        guest.require(status in ('install ok installed', 'install ok half-configured'),
                      'ownership:unexpected-recovery-package-status')
        if status == 'install ok half-configured':
            guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
    guest.verify_package_files()
    verify_surviving_identity(state, recovery, record)
    guest.require(account_digest(child) == recovery['policy'] and
                  extension_lists(child) == recovery['extensions'] and
                  all(not os.path.lexists(name) for name in guards),
                  'ownership:resolution-changed-protection')
    verify_loaded_confinement()
    verify_gates(record)
    recovery['boot'] = boot()
    save_state(state)
    record('onpc.ownership.resolved', variant + '; only-recorded-conflict-resolved; full-owned-integration-verified; reboot-and-native-retry-pending')


def ownership_retry_rebooted(record, variant):
    """Finalize only this resolved conflict after a real reboot in the same attempt."""
    guest.guard()
    from system_kiosk_admission import probe, verify_gates
    from system_removal_ownership import OWNERSHIP_VARIANTS
    guest.require(variant in OWNERSHIP_VARIANTS, 'ownership:variant')
    guest.enable_diagnostics()
    state = json.loads(state_path().read_text())
    recovery = state['ownership_retry']
    guest.require(recovery['variant'] == variant and boot() != recovery['boot'] and
                  guest.reboot_cleared(), 'ownership:retry-identity-or-boot')
    guest.installed()
    verify_surviving_identity(state, recovery, record)
    child = state['accounts']['child']
    guest.require(account_digest(child) == recovery['policy'] and
                  extension_lists(child) == recovery['extensions'],
                  'ownership:reboot-changed-enforcement')
    verify_loaded_confinement()
    verify_gates(record)
    observe_launch(child, False)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'ownership.rebooted.' + role, record)
    wait_kiosk_inactive(pwd.getpwnam(PRODUCT))
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
               'check-remove'], timeout=30)
    guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state, record=record)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'ownership.removed.' + role, record)
    observe_launch(state['accounts']['parent'], True)
    record('onpc.ownership.retry-finalized', variant +
           '; new-boot; native-remove-succeeded; owned-account-and-home-deleted; exact-original-PAM-and-disposition-restored')


def remove(record):
    guest.guard()
    guest.enable_diagnostics()
    purge_path_diagnostics(record, 'before-removal')
    accounts = provision_native()
    parent, child = accounts['parent'], accounts['child']
    other = account_digest(accounts['other'])
    other_policy = account_digest(accounts['other'], include_preferences=False)
    other_extensions = extension_lists(accounts['other'])
    defaults = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    guest.require(defaults['parent_control_enabled'] is False and defaults['apps'] == {},
                  'removal:nonfresh-start')
    configure_restrictions(accounts)
    verify_active_kiosk_refusal(record, accounts)
    verify_inflight_admission_refusal(record, accounts)
    fedora = guest.package_path().suffix == '.rpm'
    hook = foreign_integration_refusals(record, accounts, other, fedora=fedora)
    config = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())
    kiosk = pwd.getpwuid(config['kiosk_uid'])
    guest.require(kiosk.pw_name == PRODUCT and kiosk.pw_dir == '/home/' + PRODUCT,
                  'removal:kiosk-identity')
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    state = {'accounts': accounts, 'other': other, 'other_policy': other_policy,
             'preferences': preference_digest(child),
             'defaults': defaults,
             'other_extensions': other_extensions,
             'pam_services': json.loads((guest.PAYLOAD / 'before.json').read_text())['pam_services'],
             'boot': boot(), 'hook': str(hook), 'kiosk_name': kiosk.pw_name,
             'kiosk_home': kiosk.pw_dir,
             'payload': [item['path'] for item in json.loads(
                 (guest.PAYLOAD / 'installed-files.json').read_text())]}
    if fedora:
        # The lifecycle ownership record retains the pre-product profile.
        state['authselect'] = original_authselect()
    save_state(state)
    output = guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state, record=record)
    guest.require(REMOVAL_NOTICE.encode() in output, 'removal:reboot-notice-missing')
    guest.require(guest.reboot_requested(), 'removal:reboot-not-requested')
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{child}', 'org.freedesktop.Accounts.User',
               'SetAutomaticLogin', 'b', 'true'])
    guest.require(account_property(child, 'org.freedesktop.Accounts.User', 'AutomaticLogin') is True,
                  'removal:autologin-not-configured')
    record('onpc.removal.erased', 'restrictions-cleared; payload-removed; preferences-retained')


def wait_kiosk_inactive(account):
    """Preserve removal diagnostics while sharing the native probe handoff wait."""
    from system_kiosk_confinement import wait_kiosk_inactive as wait
    wait(account, identity_category='removal:kiosk-identity-changed',
         active_category='removal:kiosk-manager-already-active')


def admission_removal_state(*, exclude=()):
    """Compare owned integration/recovery bytes, including deliberately absent records.

    Native Debian abort-remove may republish identical owned files atomically.
    Their contents, modes and ownership must survive; their inode need not.
    """
    root = Path('/var/lib/oh-no-parent-control')
    paths = [root / name for name in (
        'kiosk-confinement.json', 'kiosk-confinement-removing',
        'package-created-kiosk-uid', 'uninstall-enforcement.json',
        'uninstall-broker-mask', 'installed-gdm-presession',
        'installed-fapolicyd-fallback', 'installed-child-extension-trust',
        'malcontent-pam-before-install', 'fedora-authselect.json',
        'fapolicyd-before-install', 'child-trust-backend')]
    # These are the finite shared stacks touched by pam-auth-update and the
    # Fedora PAM owner, in addition to confinement's two final service gates.
    fedora_stacks = ('system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth')
    paths += [Path('/etc/pam.d') / name for name in (
        'gdm-password', 'systemd-user', 'common-auth', 'common-account',
        'common-password', 'common-session', 'common-session-noninteractive',
        *fedora_stacks)]
    paths += [Path('/etc/authselect') / name for name in (*fedora_stacks, 'authselect.conf')]
    paths.append(Path('/etc/authselect/custom/oh-no-parent-control'))
    pam_links = {Path('/etc/pam.d') / name: name for name in fedora_stacks}
    result = {}
    while paths:
        path = paths.pop()
        if str(path) in exclude:
            continue
        if not os.path.lexists(path):
            result[str(path)] = None
            continue
        info = path.lstat()
        if path in pam_links and stat.S_ISLNK(info.st_mode):
            # Fedora's supported generated stack links are witnessed without
            # following arbitrary links. The fixed effective target is also in
            # paths, so target bytes/metadata/absence participate independently.
            name = pam_links[path]
            target = os.readlink(path)
            guest.require(info.st_uid == 0 and target in (
                '/etc/authselect/' + name, '../authselect/' + name),
                'removal:unsafe-admission-record')
            result[str(path)] = (stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid, target)
            continue
        guest.require(info.st_uid == 0 and not info.st_mode & 0o022 and
                      (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)),
                      'removal:unsafe-admission-record')
        result[str(path)] = (stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid,
                             guest.sha(path) if stat.S_ISREG(info.st_mode) else 'directory')
        if stat.S_ISDIR(info.st_mode):
            paths.extend(path.iterdir())
        guest.require(len(result) + len(paths) <= 128, 'removal:admission-record-bound')
    return result


def verify_loaded_confinement():
    """Check loaded product policy and Fedora's vendor PAM caller domain."""
    guest.guard()
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    try:
        preparation['enforcing'](config)
    except ValueError:
        raise guest.GuestError('removal:confinement-not-enforcing') from None
    if config['backend'] == 'selinux':
        permissive = guest.run(['/usr/sbin/semanage', 'permissive', '-l'], timeout=30)
        guest.require('xdm_t' not in permissive.split(),
                      'removal:vendor-domain-not-enforcing')


def verify_inflight_admission_refusal(record, accounts):
    """Refuse native erase while real root PAM owns a pre-credential admission."""
    guest.guard()
    from system_kiosk_admission import held_account, probe, verify_gates
    from system_kiosk_confinement import process_identity, exited
    account = pwd.getpwnam(PRODUCT)
    wait_kiosk_inactive(account)
    verify_gates(record)
    observe_launch(accounts['other'], True)
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
               'check-remove'], timeout=30)
    before = admission_removal_state()
    policies = {role: account_digest(accounts[role]) for role in ('child', 'other')}
    home = Path(account.pw_dir).lstat()
    lease = Path('/run/oh-no-parent-control-kiosk-admission.lock')
    lease_info = lease.lstat()
    with held_account(record) as pid:
        process = Path('/proc') / str(pid)
        pidfd = os.pidfd_open(pid)
        try:
            identity = process_identity(process)
            guest.require(identity[2] == ('0',) * 4 and not exited(pidfd),
                          'removal:admission-holder-not-root')
            wait_kiosk_inactive(account)
            verify_loaded_confinement()
            # Native removal must fail at the admission lock, before a UID
            # census, payload erasure, reversible cleanup or denial publication.
            output = guest.commands.run(removal_command(), check=False, timeout=120,
                                        merge_stderr=True)
            guest.require(guest.commands.last_returncode != 0 and not package_absent() and
                          b'kiosk-admissions-active' in output,
                          'removal:inflight-admission-not-refused')
            guest.require(not exited(pidfd) and process_identity(process) == identity,
                          'removal:admission-holder-changed')
            verify_loaded_confinement()
            guest.verify_package_files()
            guest.require(admission_removal_state() == before,
                          'removal:inflight-refusal-changed-records')
            current_home, current_lease = Path(account.pw_dir).lstat(), lease.lstat()
            guest.require(pwd.getpwnam(PRODUCT) == account and
                          (current_home.st_dev, current_home.st_ino, current_home.st_uid,
                           current_home.st_gid, current_home.st_mode) ==
                          (home.st_dev, home.st_ino, home.st_uid, home.st_gid, home.st_mode) and
                          (current_lease.st_dev, current_lease.st_ino, current_lease.st_uid,
                           current_lease.st_gid, current_lease.st_mode) ==
                          (lease_info.st_dev, lease_info.st_ino, lease_info.st_uid,
                           lease_info.st_gid, lease_info.st_mode),
                          'removal:inflight-refusal-changed-ownership')
            guest.require(all(account_digest(accounts[role]) == digest
                              for role, digest in policies.items()),
                          'removal:inflight-refusal-changed-policy')
            # Exercise both an allowed ordinary launch and the existing child
            # denial while the same root handle is still alive.
            observe_launch(accounts['other'], True)
            observe_launch(accounts['child'], False)
            probe('login', 'ordinary', 0, 'held-removal.ordinary-after', record)
            guest.require(not exited(pidfd) and process_identity(process) == identity,
                          'removal:admission-holder-changed')
            record('onpc.removal.inflight-admission-refused',
                   'root-holder-live; kiosk-manager-inactive; payload-PAM-authselect-ownership-records-preserved; loaded-confinement-enforcing; enforcement-effective')
        finally:
            os.close(pidfd)
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
               'check-remove'], timeout=30)
    verify_gates(record)
    record('onpc.removal.inflight-admission-drained', 'normal-pam-end; removal-preflight-passed')


def verify_active_kiosk_refusal(record, accounts):
    """Use native removal while one identity-recorded kiosk manager is live."""
    guest.guard()
    from system_kiosk_confinement import census, manager_pid, process_identity, exited, user_command
    account = pwd.getpwnam(PRODUCT)
    unit = f'user@{account.pw_uid}.service'
    wait_kiosk_inactive(account)
    record('onpc.removal.kiosk-inactive-before-owned-start', True)
    protected = [Path('/var/lib/oh-no-parent-control/kiosk-confinement.json'),
                 Path('/etc/pam.d/gdm-password'), Path('/etc/pam.d/systemd-user')]
    originals = {path: path.read_bytes() for path in protected}
    policies = {role: account_digest(accounts[role]) for role in ('child', 'other')}
    marker = Path('/var/lib/oh-no-parent-control/kiosk-confinement-removing')
    guest.require(not os.path.lexists(marker), 'removal:unexpected-removal-marker')
    guest.run(['systemctl', 'start', unit], timeout=75)
    invocation = guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit])
    pid = manager_pid(unit)
    process = Path('/proc') / str(pid)
    pidfd = os.pidfd_open(pid)
    identity = process_identity(process)
    generation_path = process / 'root/usr/share/oh-no-parent-control/confinement/generation'
    generation = generation_path.read_bytes()
    namespace = os.readlink(process / 'ns/mnt')
    try:
        census(required_roles=('manager',))
        guest.require(b'systemd ' in user_command(account, [
            '/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
            '--unit=onpc-removal-positive', '/usr/bin/systemctl', '--version']),
            'removal:kiosk-manager-positive')
        output = guest.commands.run(removal_command(), check=False, timeout=1800,
                                    merge_stderr=True)
        guest.require(guest.commands.last_returncode != 0 and not package_absent() and
                      any(reason in output for reason in
                          (b'kiosk-admissions-active', b'kiosk-processes-active')),
                      'removal:active-kiosk-not-refused')
        guest.verify_package_files()
        guest.require(all(path.read_bytes() == original for path, original in originals.items()) and
                      not os.path.lexists(marker), 'removal:active-refusal-changed-admission')
        guest.require(all(account_digest(accounts[role]) == digest for role, digest in policies.items()),
                      'removal:active-refusal-changed-policy')
        census(required_roles=('manager',))
        record('onpc.removal.active-kiosk-native-removal-refused',
               'package-retained; PAM-and-policy-preserved; manager-confined')
    finally:
        try:
            guest.require(pwd.getpwnam(PRODUCT).pw_uid == account.pw_uid and
                          guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit]) == invocation and
                          manager_pid(unit) == pid and not exited(pidfd) and
                          process_identity(process) == identity and
                          generation_path.read_bytes() == generation and
                          os.readlink(process / 'ns/mnt') == namespace,
                          'removal:kiosk-manager-identity-changed')
            guest.run(['systemctl', 'stop', unit], timeout=75)
        finally:
            os.close(pidfd)
    guest.run(['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'check-remove'], timeout=30)
    record('onpc.removal.active-kiosk-drained', True)


def original_authselect():
    # Read only the product's declared restoration record; validate its schema
    # in the lifecycle helper itself when removal performs the restoration.
    state = json.loads(Path('/var/lib/oh-no-parent-control/fedora-authselect.json').read_text())
    original = state.get('original') if isinstance(state, dict) else None
    guest.require(isinstance(original, list) and bool(original) and
                  all(isinstance(item, str) and item for item in original),
                  'removal:authselect-record-invalid')
    return ' '.join(original)


def write_hook(path, identity, expected, contents):
    """Modify only the unchanged owned inode; never restore over a replacement."""
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    except OSError:
        raise guest.GuestError('removal:hook-identity-changed') from None
    with os.fdopen(descriptor, 'r+b') as stream:
        current = os.fstat(stream.fileno())
        guest.require(stat.S_ISREG(current.st_mode) and current.st_uid == 0 and
                      current.st_nlink == 1 and (current.st_dev, current.st_ino) ==
                      (identity.st_dev, identity.st_ino) and stream.read() == expected,
                      'removal:hook-identity-changed')
        stream.seek(0)
        stream.write(contents)
        stream.truncate()


def removed_rebooted(record):
    guest.guard()
    guest.enable_diagnostics()
    state = json.loads(state_path().read_text())
    guest.require(boot() != state['boot'] and guest.reboot_cleared(), 'removal:reboot-not-observed')
    verify_removed(state, record=record)
    desktop_health(state['accounts']['child'])
    password_login_health(state['accounts']['child'])
    record('onpc.removal.boot-health',
           'GDM-desktop-active; password-login-accepted; native-execution-allowed; integrations-absent')
    state['removed_boot'] = boot()
    save_state(state)
    original_policy_diagnostics(record, 'removed')
    guest.install_package()
    original_policy_diagnostics(record, 'reinstalled')
    guest.require(guest.reboot_requested(), 'removal:reinstall-reboot-not-requested')


def password_login_health(uid):
    guest.guard()
    from system_caller import FixturePassword
    from system_session_expiry import pam_password_status
    password = FixturePassword()
    password.install(uid)
    guest.require(pam_password_status(uid, password) == 0 and
                  pam_password_status(uid, password, account_only=True) == 0,
                  'removal:password-login-unhealthy')


def reinstalled_rebooted(record):
    guest.guard()
    guest.enable_diagnostics()
    state = json.loads(state_path().read_text())
    guest.require(boot() != state['removed_boot'] and guest.reboot_cleared(),
                  'removal:reinstall-reboot-not-observed')
    guest.installed()
    guest.require(preference_digest(state['accounts']['child']) == state['preferences'],
                  'removal:reinstall-preferences-changed')
    verify_other_account(state, category='removal:reinstall-other-account-changed')
    guest.require(account_property(state['accounts']['child'], LIMITS, 'ActiveExtension') == [0, 0],
                  'removal:reinstall-replayed-grant')
    record('onpc.removal.reinstall', 'payload-verified; readiness-passed; preferences-retained; grant-cleared')
    # Exercise the package-delivered action while its payload is installed;
    # the action owns native package removal and its subsequent guarded purge.
    configure_restrictions(state['accounts'])
    state['purged_boot'] = boot()
    save_state(state)
    purge_path_diagnostics(record, 'before-purge')
    output = guest.commands.run(['/usr/bin/oh-no-parent-control-purge', '--yes'],
                                timeout=1800, merge_stderr=True)
    verify_removed(state, purged=True, record=record)
    guest.require(REMOVAL_NOTICE.encode() in output, 'purge:reboot-notice-missing')
    guest.require(b'oh-no-parent-control: saved-state purge outcome=accepted' in output,
                  'purge:completion-not-confirmed')
    guest.require(guest.reboot_requested(), 'purge:reboot-not-requested')
    record('onpc.purge.erased', 'restrictions-cleared; payload-and-saved-data-removed')


def purged_rebooted(record):
    guest.guard()
    guest.enable_diagnostics()
    state = json.loads(state_path().read_text())
    guest.require(boot() != state['purged_boot'] and guest.reboot_cleared(),
                  'purge:reboot-not-observed')
    verify_removed(state, purged=True, record=record)
    desktop_health(state['accounts']['child'])
    password_login_health(state['accounts']['child'])
    state['purge_reinstall_boot'] = boot()
    save_state(state)
    original_policy_diagnostics(record, 'purged')
    guest.install_package()
    original_policy_diagnostics(record, 'purge-reinstalled')
    guest.require(guest.reboot_requested(), 'purge:reinstall-reboot-not-requested')
    record('onpc.purge.boot-health', 'desktop-and-password-login-healthy; native-execution-allowed')


def purge_reinstalled_rebooted(record):
    guest.guard()
    guest.enable_diagnostics()
    state = json.loads(state_path().read_text())
    guest.require(boot() != state['purge_reinstall_boot'] and guest.reboot_cleared(),
                  'purge:reinstall-reboot-not-observed')
    guest.installed()
    accounts = state['accounts']
    preferences = json.loads(accepted(call(accounts['parent'], 'GetPreferences', '(u)',
                                           (accounts['child'],)))[0])
    guest.require(preferences == state['defaults'], 'purge:reinstall-defaults-not-fresh')
    verify_other_account(state, purged=True, category='purge:reinstall-other-account-changed')
    guest.require(account_property(accounts['child'], LIMITS, 'ActiveExtension') == [0, 0],
                  'purge:reinstall-replayed-grant')
    record('onpc.purge.reinstall', 'payload-verified; readiness-passed; fresh-policy-and-request-defaults')


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    guest.require(arguments in (['exercise-live-refusals'], ['exercise-live-rpm-posterase']) or
                  (len(arguments) == 2 and arguments[0] == 'exercise-live-finalization' and
                   arguments[1] in FINALIZATION_VARIANTS), 'removal:diagnostic-arguments')
    def record(name, value):
        print(json.dumps({'property': name, 'value': value}, sort_keys=True), flush=True)
    if arguments == ['exercise-live-refusals']:
        exercise_live_refusals(record)
    elif arguments == ['exercise-live-rpm-posterase']:
        rpm_posterase_recovery(record)
    else:
        interrupted_finalization_retry(record, arguments[1])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
