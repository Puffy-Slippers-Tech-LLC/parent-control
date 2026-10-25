"""Installed removal assertions shared by DEB and RPM guarded attempts.

These are engineering checks through package, AccountsService, PAM and logind
APIs. The automatic GDM login is a declared fixture, not customer UI evidence.
The existing outer VM lease owns restoration, including failed transactions.
"""

import ast
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
from system_enforcement import native_paths, observe_launch, provision_native

PRODUCT = 'oh-no-parent-control'
EXTENSION = 'oh-no-parent-control@tech.puffyslippers.com'
LIMITS = 'com.endlessm.ParentalControls.SessionLimits'
DEBIAN_NOTICE = '/etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice'
REMOVAL_NOTICE = '*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***'
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
                 '/var/lib/oh-no-parent-control/kiosk-configuration-account.json',
                 '/var/lib/oh-no-parent-control/legacy-kiosk-policy.json',
                 '/var/lib/oh-no-parent-control/legacy-kiosk-policy',
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
        try:
            observe_launch(state['accounts'][role], True,
                           variant=state.get('native_variant', 'command'))
        except guest.GuestError:
            removed_launch_failure_diagnostics()
            raise
    if guest.package_path().suffix == '.rpm':
        guest.run(['authselect', 'check'])
        guest.require(guest.run(['authselect', 'current', '--raw']) == state['authselect'],
                      'removal:authselect-not-restored')
        guest.require(guest.run(['getenforce']) == 'Enforcing', 'removal:selinux-not-enforcing')


def removed_launch_failure_diagnostics():
    """Capture policy/reload evidence only after the unchanged launch check fails."""
    previous_returncode = guest.commands.last_returncode
    probes = (
        ('compiled', ['cat', '/etc/fapolicyd/compiled.rules']),
        ('rules', ['fapolicyd-cli', '--list']),
        ('journal', ['journalctl', '--boot', '--unit=fapolicyd.service',
                     '--lines=80', '--no-pager', '--output=short-monotonic']),
    )
    try:
        for name, arguments in probes:
            try:
                # Reuse private command artifacts and never replace the failure.
                guest.commands.run(arguments, check=False, timeout=10, merge_stderr=True)
                outcome = 'collected' if guest.commands.last_returncode == 0 else 'failed'
            except Exception:
                outcome = 'unavailable'
            print(f'onpc-system: stage=removed-launch-{name} outcome={outcome}', flush=True)
    finally:
        guest.commands.last_returncode = previous_returncode


def configure_restrictions(accounts, *, variant='command'):
    """Make policy, one-time access and shared choices observably nondefault."""
    parent, child = accounts['parent'], accounts['child']
    accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, 60)))
    preferences = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    target, _, desktop_id = native_paths(variant)
    preferences['apps'] = {desktop_id: {'state': 'permanent', 'targets': [str(target)],
                                       'patterns': [], 'user_saved_match_rule': False}}
    preferences['request'].update(last_selected_duration='custom', last_custom_minutes=23,
                                  allow_soft_blocked_apps=True, kiosk_muted=False,
                                  child_muted=False)
    accepted(call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences))))
    from system_session_expiry import grant
    grant(child, 600)
    guest.require(EXTENSION in extension_lists(child)[0], 'removal:extension-not-configured')
    observe_launch(child, False, variant=variant)
    observe_launch(accounts['other'], True, variant=variant)


def restriction_failure_diagnostics():
    """Identify preserved native policy without changing the failed launch."""
    previous_returncode = guest.commands.last_returncode
    probes = (
        ('rules', ['fapolicyd-cli', '--list']),
        ('provenance', ['cat',
                        '/var/lib/oh-no-parent-control/fedora-execution-policy.json']),
        ('reason', ['dnf5', '--quiet', '--cacheonly', '--disable-repo=*', 'repoquery',
                    '--installed', '--queryformat', '%{name}|%{reason}', 'fapolicyd']),
    )
    try:
        for name, arguments in probes:
            try:
                # Output stays in the attempt's existing private command logs.
                # Diagnostic failure must never replace the original assertion.
                guest.commands.run(arguments, check=False, timeout=10, merge_stderr=True)
                outcome = 'collected' if guest.commands.last_returncode == 0 else 'failed'
            except Exception:
                outcome = 'unavailable'
            print(f'onpc-system: stage=removal-restriction-{name} outcome={outcome}',
                  flush=True)
    finally:
        guest.commands.last_returncode = previous_returncode


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


def refuse_foreign_integration(accounts, before, other, category, target, *, record=None,
                               reason=None):
    """Keep refusal evidence before resolving the edit and retrying configuration."""
    guest.guard()
    info, original = target.lstat(), target.read_bytes()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1,
                  'removal:unsafe-' + category)
    modified = original + b'\n# onpc removal refusal fixture\n'
    if category == 'pam' and target.name == 'fedora-authselect.json':
        document = json.loads(original)
        guest.require(isinstance(document.get('original'), list) and document['original'],
                      'removal:unsafe-original-pam-selection')
        document['original'] = []
        modified = (json.dumps(document, sort_keys=True) + '\n').encode()
    write_hook(target, info, original, modified)
    try:
        output = guest.commands.run(removal_command(), check=False, timeout=1800, merge_stderr=True)
        guest.require(guest.commands.last_returncode != 0 and not package_absent() and
                      (reason is None or reason in output),
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
    elif category == 'pam':
        guest.install_package()
    guest.verify_package_files()
    guest.require(account_digest(accounts['child']) == before and
                  account_digest(accounts['other']) == other, 'removal:retry-changed-policy')
    if record is not None and guest.package_path().suffix == '.deb':
        # Strict verification above independently requires this native status.
        record('onpc.removal.' + category + '-status-after-recovery', 'install ok installed')


def foreign_integration_refusals(record, accounts, other, *, fedora):
    """Keep historic hook/PAM labels bound to current owned integrations."""
    guest.guard()
    from system_removal_ownership import ownership_targets, ownership_reason
    distribution = 'fedora' if fedora else 'ubuntu'
    targets = ownership_targets(distribution)
    hook = targets['gdm-hook-link']
    before = account_digest(accounts['child'])
    for category, variant in (('hook', 'gdm-hook-link'), ('pam', 'systemd-user-edit')):
        target = targets[variant]
        refuse_foreign_integration(accounts, before, other, category, target, record=record,
                                  reason=ownership_reason(variant, distribution))
        record('onpc.removal.' + category + '-refusal-retry',
               'foreign-edit-refused; payload-and-policy-preserved')
    return hook


def exercise_live_refusals(record):
    """Engineering-only probe in disposable maintenance; retain the package."""
    guest.guard()
    guest.enable_diagnostics()
    variant = 'trusted-hard' if guest.package_path().suffix == '.rpm' else 'command'
    accounts = provision_native(variant)
    other = account_digest(accounts['other'])
    configure_restrictions(accounts, variant=variant)
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


def current_expiry():
    """Read the vendor shadow account barrier without requiring erased code."""
    fields = guest.run(['getent', 'shadow', PRODUCT],
                       diagnostic_stdout=lambda _: b'kiosk-expiry-read\n').split(':')
    guest.require(len(fields) == 9 and fields[0] == PRODUCT and
                  (not fields[7] or re.fullmatch(r'[0-9]+', fields[7])), 'removal:invalid-kiosk-expiry')
    return int(fields[7]) if fields[7] else None


def expiry_status(service):
    """Vendor account policy owns expiry; Ubuntu's common-account maps to 7."""
    guest.require(service in ('gdm-password', 'systemd-user'), 'removal:expiry-service')
    suffix = guest.package_path().suffix
    guest.require(suffix in ('.deb', '.rpm'), 'removal:package-format')
    return 7 if suffix == '.deb' else 13


def removal_recovery_state():
    """Fresh installations own an identity/expiry journal, never legacy PAM."""
    uid = pwd.getpwnam(PRODUCT).pw_uid
    guest.require(all(not os.path.lexists('/var/lib/oh-no-parent-control/' + name)
                      for name in ('kiosk-confinement.json', 'kiosk-confinement-removing',
                                   'kiosk-configuration-account.json', 'legacy-kiosk-policy.json',
                                   'legacy-kiosk-policy')),
                  'removal:nonfresh-lifecycle-records')
    marker = private_recovery_record(Path('/var/lib/oh-no-parent-control/package-created-kiosk-uid'))
    guest.require(marker.contents == (str(uid) + '\n').encode(), 'removal:changed-kiosk-identity')
    pam = {}
    for name, service in guest.pam_service_state().items():
        # A missing local override selects the vendor service. Retain its
        # actual path so the later exact-byte check reads the same authority.
        directory = '/etc/pam.d' if service['source'] == 'local' else '/usr/lib/pam.d'
        path = Path(directory) / name
        pam[str(path)] = fault_file_identity(path)[2:]
    return {'uid': uid, 'expires': current_expiry(), 'pam': pam}


def verify_quarantine(saved, *, marker_uid=None):
    value = private_recovery_record(Path('/var/lib/oh-no-parent-control/kiosk-configuration-account.json'))
    try:
        expiry = json.loads(value.contents)
    except (ValueError, UnicodeError):
        raise guest.GuestError('finalization:quarantine-record-changed') from None
    guest.require(isinstance(expiry, dict) and type(expiry.get('version')) is int and
                  type(expiry.get('uid')) is int and
                  (expiry.get('expires') is None or type(expiry.get('expires')) is int) and
                  expiry == {'version': 1, 'uid': saved['uid'],
                  'expires': saved['expires'], 'phase': 'quarantined'} and current_expiry() == 1,
                  'finalization:quarantine-record-changed')
    guest.require(private_recovery_record(Path(
        '/var/lib/oh-no-parent-control/package-created-kiosk-uid')).contents ==
                  (str(saved['uid'] if marker_uid is None else marker_uid) + '\n').encode() and
                  all(not os.path.lexists('/var/lib/oh-no-parent-control/' + name)
                      for name in ('kiosk-confinement.json', 'kiosk-confinement-removing')),
                  'finalization:recovery-records-changed')


def quarantine_active(recovery):
    """Bracket observations with the same independently checked native barrier."""
    try:
        verify_quarantine({'uid': recovery['kiosk_identity'][0],
                           'expires': recovery['expires']})
    except (FileNotFoundError, guest.GuestError):
        return False
    return True


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
    admission_denied = denial is None
    try:
        while worker.is_alive() and time.monotonic() < deadline:
            if denial is not None:
                try:
                    verify_quarantine(denial)
                    admission_denied = True
                except (FileNotFoundError, guest.GuestError):
                    pass
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
    guest.require(admission_denied, 'rollback:account-quarantine-transition-not-observed')
    record('onpc.rollback.snapshot', hashlib.sha256(
        json.dumps(observed, sort_keys=True).encode()).hexdigest())
    if denial is not None:
        record('onpc.rollback.account-quarantine', str(denial['uid']))
    record('onpc.rollback.cleared',
           'native-limits-grant-filter-extension-cleared; generated-policy-absent; snapshot-matched')
    return result['output'], transaction.last_returncode


def rollback_record_matches(name, before, after, *, broker_started=False):
    if before == after:
        return True
    if name == '/var/lib/oh-no-parent-control/fedora-authselect.json':
        admin_group = 'wheel'
    elif (name in ('/var/lib/oh-no-parent-control/installed-fapolicyd-fallback',
                  '/var/lib/oh-no-parent-control/installed-child-extension-trust') and
          guest.package_path().suffix == '.deb'):
        admin_group = 'sudo'
    else:
        return False
    # Broker startup can chgrp its StateDirectory tree to sudo/wheel;
    # postinst install_integration and fedora_pam.save republish private copies
    # as root:root. Fedora reinstall starts the broker again, so that recovery
    # comparison can observe root -> wheel too. Refusal comparisons stay
    # one-way. Neither group has access at 0600; bytes and root owner stay exact.
    if (before is None or after is None or
            before[:2] != (0o600, 0) or after[:2] != (0o600, 0) or
            before[3] != after[3]):
        return False
    admin_gid = grp.getgrnam(admin_group).gr_gid
    groups = (before[2], after[2])
    return groups == (admin_gid, 0) or (
        broker_started and name == '/var/lib/oh-no-parent-control/fedora-authselect.json' and
        groups == (0, admin_gid))


def aborted_cleanup_rollback_retry(record):
    """One native aborted cleanup, guarded restoration and successful owned retry."""
    guest.guard()
    guest.enable_diagnostics()
    from system_kiosk_admission import probe, verify_gates
    # Existing Fedora policy denies the untrusted mechanical control even
    # before product restrictions. Use the prepared, verified trusted witness
    # so this history measures product rollback while preserving native policy.
    variant = 'trusted-hard' if guest.package_path().suffix == '.rpm' else 'command'
    accounts = provision_native(variant)
    parent, child = accounts['parent'], accounts['child']
    defaults = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    guest.require(defaults['parent_control_enabled'] is False and defaults['apps'] == {},
                  'rollback:nonfresh-start')
    other, other_policy = account_digest(accounts['other']), account_digest(
        accounts['other'], include_preferences=False)
    other_extensions = extension_lists(accounts['other'])
    try:
        for role in ('child', 'parent', 'other'):
            observe_launch(accounts[role], True, variant=variant)
    except guest.GuestError:
        # Preserve the unrestricted-launch assertion. Capture native rules and
        # their provenance before any rollback policy or fault is configured.
        if guest.package_path().suffix == '.rpm':
            restriction_failure_diagnostics()
        raise
    verify_gates(record)
    probe('login', 'other', 0, 'rollback.other-before', record)
    configure_restrictions(accounts, variant=variant)
    kiosk = pwd.getpwnam(PRODUCT)
    wait_kiosk_inactive(kiosk)
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    fedora = guest.package_path().suffix == '.rpm'
    state = {'accounts': accounts, 'other': other, 'other_policy': other_policy,
             'native_variant': variant,
             'other_extensions': other_extensions, 'defaults': defaults,
             'preferences': preference_digest(child), 'boot': boot(),
             'pam_services': json.loads((guest.PAYLOAD / 'before.json').read_text())['pam_services'],
             'hook': '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules',
             'kiosk_name': kiosk.pw_name, 'kiosk_home': kiosk.pw_dir,
             'payload': [item['path'] for item in json.loads(
                 (guest.PAYLOAD / 'installed-files.json').read_text())]}
    if fedora:
        state['authselect'] = original_authselect()
    save_state(state)
    before = admission_removal_state()
    saved = removal_recovery_state()
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
    from system_removal_faults import interruption_fault
    check_remove_preflight()
    with interruption_fault('pam-restoration', record) as fault:
        output, status = observe_aborted_transaction(child, expected, saved, record)
        fault.verify_triggered()
        guest.require(not package_absent() and b'onpc-removal-fault:' in output,
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
        guest.require(account_digest(child) == policy and extension_lists(child) == extensions and
                      all((Path(name).read_bytes() if os.path.lexists(name) else None) == value
                          for name, value in generated.items()), 'rollback:enforcement-not-restored')
        verify_other_account(state)
        guest.require(extension_lists(accounts['other']) == other_extensions,
                      'rollback:other-extension-changed')
        current = admission_removal_state()
        changed = {'/var/lib/oh-no-parent-control/kiosk-confinement.json',
                   '/var/lib/oh-no-parent-control/kiosk-confinement-removing',
                   '/var/lib/oh-no-parent-control/kiosk-configuration-account.json',
                   '/var/lib/oh-no-parent-control/uninstall-broker-mask'}
        record('onpc.rollback.changed-records', json.dumps({
            name: {'before': value, 'after': current.get(name)}
            for name, value in before.items() if name not in changed and current.get(name) != value},
            sort_keys=True))
        guest.require(current.keys() == before.keys() and all(
            rollback_record_matches(name, value, current[name])
            for name, value in before.items() if name not in changed),
                      'rollback:foreign-or-ownership-state-changed')
        verify_quarantine(saved)
        guest.require(Path('/var/lib/oh-no-parent-control/uninstall-broker-mask').is_file() and
                      os.readlink('/run/systemd/system/oh-no-parent-control-broker.service') == '/dev/null',
                      'rollback:guards-released-before-restoration')
        guest.require(guest.pam_service_state() == pam and pwd.getpwnam(PRODUCT) == kiosk and
                      (Path(kiosk.pw_dir).lstat().st_dev, Path(kiosk.pw_dir).lstat().st_ino,
                       Path(kiosk.pw_dir).lstat().st_uid, Path(kiosk.pw_dir).lstat().st_gid,
                       Path(kiosk.pw_dir).lstat().st_mode) ==
                      (home.st_dev, home.st_ino, home.st_uid, home.st_gid, home.st_mode),
                      'rollback:identity-or-pam-changed')
        verify_loaded_confinement()
        observe_launch(child, False, variant=variant)
        for role in ('parent', 'other'):
            identity, digest, lists = ordinary[role]
            guest.require(pwd.getpwuid(accounts[role]) == identity and
                          account_digest(accounts[role]) == digest and
                          extension_lists(accounts[role]) == lists,
                          'rollback:ordinary-account-changed')
            observe_launch(accounts[role], True, variant=variant)
        probe('login', 'ordinary', 0, 'rollback.ordinary-guarded', record)
        probe('login', 'other', 0, 'rollback.other-guarded', record)
        probe('gdm-password', 'kiosk', expiry_status('gdm-password'), 'rollback.kiosk-guarded', record)
        record('onpc.rollback.restored-before-release',
               'exact-enforcement-restored; native-child-denied; ordinary-users-allowed; native-expiry-quarantine-and-mask-retained')
    # The fault overlays a packaged helper. Verify the complete payload only
    # after its owned unmount restores that helper, before reconfiguration or
    # reinstall can repair any damage from the aborted removal.
    guest.verify_package_payload()
    if fedora:
        guest.install_package()
    else:
        guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
    guest.verify_package_files()
    guest.require(not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-confinement-removing') and
                  not os.path.lexists('/var/lib/oh-no-parent-control/uninstall-broker-mask') and
                  not os.path.lexists('/run/systemd/system/oh-no-parent-control-broker.service') and
                  not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-configuration-account.json') and
                  current_expiry() == saved['expires'] and
                  account_digest(child) == policy, 'rollback:rearm-incomplete')
    verify_loaded_confinement()
    verify_gates(record)
    probe('login', 'other', 0, 'rollback.other-rearmed', record)
    check_remove_preflight()
    record('onpc.rollback.rearm-preflight', 'passed')
    # RPM reinstall replaces the native PAM inode. Cached root login workers
    # must retire naturally at reboot before the same history retries removal.
    # Both platforms keep that reboot and finalization in this guarded attempt.
    state['rollback_rearm'] = {
        'boot': boot(), 'policy': policy, 'extensions': extensions,
        'expires': saved['expires'],
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
    variant = state.get('native_variant', 'command')
    rearm = state['rollback_rearm']
    guest.require(boot() != rearm['boot'] and guest.reboot_cleared(),
                  'rollback:rearm-reboot-not-observed')
    guest.installed()
    child, parent = state['accounts']['child'], state['accounts']['parent']
    guest.require(current_expiry() == rearm['expires'] and
                  account_digest(child) == rearm['policy'] and
                  extension_lists(child) == rearm['extensions'],
                  'rollback:reboot-changed-restored-enforcement')
    kiosk = pwd.getpwnam(state['kiosk_name'])
    home = Path(kiosk.pw_dir).lstat()
    guest.require([kiosk.pw_uid, kiosk.pw_gid, kiosk.pw_dir, kiosk.pw_shell] ==
                  rearm['kiosk_identity'] and
                  [home.st_ino, home.st_uid, home.st_gid, home.st_mode] == rearm['kiosk_home'],
                  'rollback:reboot-changed-kiosk-identity')
    observe_launch(child, False, variant=variant)
    for role, before in rearm['ordinary'].items():
        identity = pwd.getpwuid(before['uid'])
        guest.require([identity.pw_name, identity.pw_uid, identity.pw_gid,
                       identity.pw_dir, identity.pw_shell] == before['identity'] and
                      account_digest(before['uid']) == before['policy'] and
                      extension_lists(before['uid']) == before['extensions'],
                      'rollback:reboot-changed-ordinary-account')
        observe_launch(before['uid'], True, variant=variant)
    verify_loaded_confinement()
    verify_gates(record)
    probe('login', 'other', 0, 'rollback.other-rebooted', record)
    wait_kiosk_inactive(kiosk)
    check_remove_preflight()
    record('onpc.rollback.rearm-reboot', 'new-boot; restored-enforcement-and-identities-preserved; removal-preflight-passed')
    guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state, record=record)
    probe('login', 'ordinary', 0, 'rollback.ordinary-removed', record)
    probe('login', 'other', 0, 'rollback.other-removed', record)
    observe_launch(parent, True, variant=variant)
    record('onpc.rollback.retry-finalized', 'native-remove-succeeded; owned-account-deleted; exact-original-PAM-restored')


FINALIZATION_VARIANTS = ('denial-publication', 'account-finalization')


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
        observe_launch(before['uid'], True, variant=state.get('native_variant', 'command'))
    verify_other_account(state)
    guest.require(preference_digest(state['accounts']['child']) == state['preferences'],
                  'finalization:preferences-changed')


def verify_durable_interval(state, recovery, saved, record, *, conflict=None):
    """Exercise vendor account expiry after payload erasure, with ordinary positives."""
    from system_kiosk_admission import durable_probe, probe
    verify_payload_erased(state)
    if conflict is None:
        verify_surviving_identity(state, recovery, record)
    else:
        conflict.verify()
        verify_surviving_identity(state, recovery, record,
                                  home_conflict=conflict.variant.startswith('home-'))
    verify_quarantine(saved, marker_uid=(conflict.expected_marker_uid
                      if conflict is not None else None))
    verify_pam_removed()
    guest.require(guest.pam_service_state() == state['pam_services'],
                  'finalization:original-pam-not-restored')
    for name, expected in saved['pam'].items():
        target = Path(name)
        service = target.name
        guest.require(fault_file_identity(target)[2:] == expected,
                      'finalization:vendor-service-changed')
        record('onpc.finalization.durable.' + service, hashlib.sha256(expected[-1]).hexdigest())
        for role in ('ordinary', 'other'):
            durable_probe(service, role, 'account', 0, service + '.' + role, record)
        # The selected baseline uses the vendor account-expiry barrier. Calling
        # open_session alone bypasses account policy and supplies no admission
        # result; the retired private session-only veto has no current binding.
        durable_probe(service, 'kiosk', 'account', expiry_status(service),
                      service + '.kiosk.account', record)
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
           'owned-account-and-expiry-record-retained; vendor-account-expiry-denied; exact-vendor-PAM-retained; ordinary-users-allowed; legacy-MAC-absent')


def focused_recovery_start(record, variant, state_key, *, native_variant='command'):
    """Shared fresh controls and independent removal oracle for focused histories."""
    guest.guard()
    guest.enable_diagnostics()
    from system_kiosk_admission import durable_probe, verify_gates
    if native_variant == 'command' and guest.package_path().suffix == '.rpm':
        native_variant = 'trusted-hard'
    accounts = provision_native(native_variant)
    parent, child = accounts['parent'], accounts['child']
    defaults = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    guest.require(defaults['parent_control_enabled'] is False and defaults['apps'] == {},
                  'finalization:nonfresh-start')
    other = account_digest(accounts['other'])
    other_policy = account_digest(accounts['other'], include_preferences=False)
    other_extensions = extension_lists(accounts['other'])
    try:
        for role in ('child', 'parent', 'other'):
            observe_launch(accounts[role], True, variant=native_variant)
    except guest.GuestError:
        # Capture the preserved native rules and their provenance before this
        # history writes policy or installs a removal fault. Keep the failed
        # launch and its assertion unchanged.
        if guest.package_path().suffix == '.rpm':
            restriction_failure_diagnostics()
        raise
    verify_gates(record)
    for service in ('gdm-password', 'systemd-user'):
        for role in ('ordinary', 'other'):
            durable_probe(service, role, 'account', 0, service + '.' + role + '.before', record)
    configure_restrictions(accounts, variant=native_variant)
    kiosk = pwd.getpwnam(PRODUCT)
    wait_kiosk_inactive(kiosk)
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    home = Path(kiosk.pw_dir).lstat()
    fedora = guest.package_path().suffix == '.rpm'
    state = {'accounts': accounts, 'other': other, 'other_policy': other_policy,
             'native_variant': native_variant,
             'other_extensions': other_extensions, 'defaults': defaults,
             'preferences': preference_digest(child), 'boot': boot(),
             'pam_services': json.loads((guest.PAYLOAD / 'before.json').read_text())['pam_services'],
             'hook': '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules',
             'kiosk_name': kiosk.pw_name, 'kiosk_home': kiosk.pw_dir,
             'payload': [item['path'] for item in json.loads(
                 (guest.PAYLOAD / 'installed-files.json').read_text())]}
    if fedora:
        state['authselect'] = original_authselect()
    saved = removal_recovery_state()
    before = admission_removal_state()
    generated = {name: Path(name).read_bytes() if os.path.lexists(name) else None
                 for name in GENERATED_POLICY}
    policy = account_digest(child)
    extensions = extension_lists(child)
    recovery = {'variant': variant, 'policy': policy, 'extensions': extensions,
                'expires': saved['expires'],
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
    # Preserved Fedora policy denies the untrusted mechanical fixture even
    # without product restrictions. Verify the prepared trusted witness instead,
    # and keep that same executable through restriction, rollback and removal.
    native_variant = 'trusted-hard' if guest.package_path().suffix == '.rpm' else 'command'
    state, recovery, saved, before, generated = focused_recovery_start(
        record, variant, 'finalization_retry', native_variant=native_variant)
    child = state['accounts']['child']
    policy, extensions = recovery['policy'], recovery['extensions']
    fedora = guest.package_path().suffix == '.rpm'
    expected = dict(zip(('limit_type', 'daily_limit', 'active_extension', 'app_filter'),
                        account_state(child)[1:]))
    expected.update(uid=child, extension_enabled=True)
    with interruption_fault(variant, record) as fault:
        output, status = observe_aborted_transaction(
            child, expected, None, record)
        fault.verify_triggered()
        record('onpc.finalization.native-status', str(status))
        if variant == 'account-finalization':
            guest.require(b'onpc-removal-fault:' in output,
                          'finalization:account-callback-not-interrupted')
            verify_durable_interval(state, recovery, saved, record)
        else:
            # The lifecycle helper captures usermod's stderr. The exact fault
            # invocation is verified above through its owned witness; the
            # package transaction reports the helper's CalledProcessError.
            failure = (b"kiosk-lifecycle: Command '['usermod', '--expiredate', '1', "
                       b"'oh-no-parent-control']' returned non-zero exit status 79.")
            guest.require(status != 0 and not package_absent() and failure in output,
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
                       '/var/lib/oh-no-parent-control/kiosk-configuration-account.json',
                       '/var/lib/oh-no-parent-control/uninstall-broker-mask'}
            guest.require(current.keys() == before.keys() and all(
                rollback_record_matches(name, value, current[name])
                for name, value in before.items() if name not in mutable),
                          'finalization:foreign-or-ownership-state-changed')
            guest.require(current_expiry() == saved['expires'],
                          'finalization:original-expiry-not-restored')
            verify_loaded_confinement()
            observe_launch(child, False, variant=native_variant)
            for role in ('ordinary', 'other'):
                probe('login', role, 0, 'finalization.restored.' + role, record)
            record('onpc.finalization.restored-before-fault-release',
                   'exact-native-policy-restored; child-denied; ordinary-users-allowed; native-distro-PAM-ready')
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
            # A failed quarantine write allows abort-remove to finish rearming.
            # dpkg rejects --configure for that already configured package.
            if status == 'install ok half-configured':
                guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
        guest.verify_package_files()
        verify_surviving_identity(state, recovery, record)
        guest.require(account_digest(child) == policy and extension_lists(child) == extensions,
                      'finalization:rearm-changed-enforcement')
        verify_loaded_confinement()
        guest.require(not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-confinement-removing') and
                      not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-configuration-account.json') and
                      current_expiry() == saved['expires'] and
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
        guest.require(current_expiry() == recovery['expires'] and
                      account_digest(state['accounts']['child']) == recovery['policy'] and
                      extension_lists(state['accounts']['child']) == recovery['extensions'],
                      label + ':reboot-changed-enforcement')
        verify_loaded_confinement()
        verify_gates(record)
        observe_launch(state['accounts']['child'], False,
                       variant=state.get('native_variant', 'command'))
        wait_kiosk_inactive(pwd.getpwnam(PRODUCT))
        check_remove_preflight()
        guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state, record=record)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, label + '.completed.' + role, record)
    observe_launch(state['accounts']['parent'], True,
                   variant=state.get('native_variant', 'command'))
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
    observed = False
    worker.start()
    try:
        while worker.is_alive():
            guarded = quarantine_active(recovery)
            if not os.path.lexists(snapshot) and guarded:
                restored = (account_digest(state['accounts']['child']) == recovery['policy'] and
                            extension_lists(state['accounts']['child']) == recovery['extensions'] and
                            all((Path(name).read_bytes() if os.path.lexists(name) else None) == value
                                for name, value in generated.items()))
                if restored:
                    observe_launch(state['accounts']['child'], False,
                                   variant=state.get('native_variant', 'command'))
                # Bracket the complete native read: an endpoint after the
                # barrier was released cannot supply this transition receipt.
                guarded = quarantine_active(recovery)
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
           'snapshot-consumed; exact-native-policy-extension-and-rules-restored; native-child-execution-denied; native-expiry-quarantine-retained')


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
    check_remove_preflight()
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
        guest.require(current_expiry() == recovery['expires'] and
                      account_digest(child) == recovery['policy'] and
                      extension_lists(child) == recovery['extensions'],
                      'rpm-posterase:reinstall-changed-enforcement')
        verify_loaded_confinement()
        verify_gates(record)
        observe_launch(child, False, variant=state.get('native_variant', 'command'))
        for role in ('ordinary', 'other'):
            probe('login', role, 0, 'rpm-posterase.reinstalled.' + role, record)
        guest.require(all(not os.path.lexists('/var/lib/oh-no-parent-control/' + name)
                          for name in ('kiosk-confinement-removing', 'kiosk-configuration-account.json',
                                       'uninstall-enforcement.json',
                                       'uninstall-broker-mask', 'migration-in-progress')),
                      'rpm-posterase:reinstall-guards-retained')
        conflict.verify()
        record('onpc.rpm-posterase.reinstalled',
               'normal-make-install; exact-enforcement-restored; native-distro-PAM-ready; native-gates-rearmed; foreign-conflict-preserved')
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
    guest.require(current_expiry() == recovery['expires'] and
                  account_digest(state['accounts']['child']) == recovery['policy'] and
                  extension_lists(state['accounts']['child']) == recovery['extensions'],
                  'rpm-posterase:reboot-changed-enforcement')
    verify_loaded_confinement()
    verify_gates(record)
    observe_launch(state['accounts']['child'], False, variant=state.get('native_variant', 'command'))
    wait_kiosk_inactive(pwd.getpwnam(PRODUCT))
    check_remove_preflight()
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
        observe_launch(before['uid'], True, variant=state.get('native_variant', 'command'))
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
    check_remove_preflight()
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
        conflict_before = admission_removal_state()
        output = guest.commands.run(removal_command(), check=False, timeout=1800,
                                    merge_stderr=True)
        status = guest.commands.last_returncode
        record('onpc.identity-filesystem.native-status', str(status))
        if variant in ('state-owner', 'state-link'):
            # Snapshot refusal reports catalogued fields and cause provenance;
            # exception messages are excluded by the diagnostics contract.
            refused = (
                b'onpc.uninstall uninstall snapshot outcome=failed error_type=UninstallCleanupError'
                in output.splitlines() and re.search(
                    rb'^onpc.runtime Failure provenance depth=1 link=cause '
                    rb'error_type=UninstallCleanupError source=uninstall line=[1-9][0-9]* '
                    rb'os_error=none exit_code=256;', output, re.MULTILINE) is not None)
        else:
            refused = conflict.reason in output
        guest.require(refused and (fedora or status != 0),
                      'identity-filesystem:native-conflict-not-refused')
        conflict.verify()
        if conflict.preflight:
            guest.require(status != 0 and not package_absent(),
                          'identity-filesystem:preflight-erased-payload')
            guest.verify_package_payload()
            verify_surviving_identity(state, recovery, record,
                                      home_conflict=variant.startswith('home-'))
            guest.require(account_digest(child) == recovery['policy'] and
                          extension_lists(child) == recovery['extensions'] and all(
                              (Path(name).read_bytes() if os.path.lexists(name) else None) == value
                              for name, value in generated.items()),
                          'identity-filesystem:enforcement-changed')
            current = admission_removal_state()
            mutable = {'/var/lib/oh-no-parent-control/uninstall-broker-mask'}
            guest.require(current.keys() == conflict_before.keys() and all(
                rollback_record_matches(name, value, current[name])
                for name, value in conflict_before.items() if name not in mutable),
                          'identity-filesystem:recovery-records-changed')
            guest.require(Path(guards[2]).is_file() and os.readlink(guards[3]) == '/dev/null' and
                          not os.path.lexists(guards[0]) and not os.path.lexists(guards[1]) and
                          not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-configuration-account.json'),
                          'identity-filesystem:refusal-guards-not-retained')
            verify_loaded_confinement()
            observe_launch(child, False, variant=state.get('native_variant', 'command'))
            for role in ('ordinary', 'other'):
                probe('login', role, 0, 'identity-filesystem.refused.' + role, record)
            probe('login', 'kiosk', 6, 'identity-filesystem.refused.kiosk', record)
        else:
            # Fedora may report a successful erase despite failed postun. The
            # retained account, exact callback diagnostic and vendor account
            # expiry, rather than that exit code, establish safe refusal.
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
        if fedora:
            guest.install_package()
        elif not fedora:
            status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
            guest.require(status in ('install ok installed', 'install ok half-configured'),
                          'identity-filesystem:unexpected-rearm-package-status')
            if status == 'install ok half-configured':
                guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
        guest.verify_package_files()
        verify_surviving_identity(state, recovery, record)
        guest.require(current_expiry() == recovery['expires'] and
                      account_digest(child) == recovery['policy'] and
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
    from system_kiosk_admission import PAM_AUTH_ERR, PAM_PERM_DENIED, probe, verify_gates
    from system_removal_ownership import (OWNERSHIP_VARIANTS, ownership_conflict,
                                         ownership_targets, ownership_reason)
    guest.require(variant in OWNERSHIP_VARIANTS, 'ownership:variant')
    state, recovery, saved, before, generated = focused_recovery_start(
        record, variant, 'ownership_retry')
    child = state['accounts']['child']
    check_remove_preflight()
    distribution = 'fedora' if guest.package_path().suffix == '.rpm' else 'ubuntu'
    target = ownership_targets(distribution)[variant]
    reason = ownership_reason(variant, distribution)
    prepared = variant.startswith('confinement-record-')
    early = variant in ('systemd-user-link', 'gdm-hook-link')
    if prepared:
        # Use the genuine package owner to create its UID-bound journal. The
        # fixture changes that existing authority, never fabricates provenance.
        guest.run(['/usr/libexec/oh-no-parent-control-kiosk-lifecycle',
                   '--distribution', distribution, 'prepare'], timeout=60)
        verify_quarantine(saved)
        before = admission_removal_state()
    record('onpc.ownership.target', variant + '; ' + str(target))
    guards = ('/var/lib/oh-no-parent-control/kiosk-confinement-removing',
              '/var/lib/oh-no-parent-control/uninstall-enforcement.json',
              '/var/lib/oh-no-parent-control/uninstall-broker-mask',
              '/run/systemd/system/oh-no-parent-control-broker.service')
    guest.require(all(not os.path.lexists(name) for name in guards), 'ownership:nonfresh-guards')
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'ownership.before.' + role, record)
    with ownership_conflict(variant, target, state['accounts']['other'], record) as conflict:
        # The native callback owns refusal and any reversible cleanup/rollback.
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
        mutable = {str(target)}
        if not early:
            mutable.add('/var/lib/oh-no-parent-control/uninstall-broker-mask')
            if not prepared:
                mutable.add('/var/lib/oh-no-parent-control/kiosk-configuration-account.json')
        current = admission_removal_state(exclude=tuple(mutable))
        expected = {name: value for name, value in before.items() if name not in mutable}
        guest.require(current.keys() == expected.keys() and all(
            rollback_record_matches(name, value, current[name])
            for name, value in expected.items()), 'ownership:recovery-records-changed')
        if early:
            guest.require(all(not os.path.lexists(name) for name in guards),
                          'ownership:preflight-published-removal-guards')
        else:
            guest.require(Path(guards[2]).is_file() and os.readlink(guards[3]) == '/dev/null',
                          'ownership:rollback-mask-not-retained')
            if not prepared:
                verify_quarantine(saved)
        verify_loaded_confinement()
        observe_launch(child, False, variant=state.get('native_variant', 'command'))
        for role in ('ordinary', 'other'):
            probe('login', role, 0, 'ownership.refused.' + role, record)
        kiosk_denial = PAM_PERM_DENIED
        if distribution == 'ubuntu' and not early:
            # Ubuntu's primary common-account stack maps expired accounts to
            # PAM_AUTH_ERR before the additional kiosk-only module can run.
            # Prove the retained native quarantine, then require its exact
            # denial rather than accepting an arbitrary failed account check.
            guest.require(current_expiry() == 1, 'ownership:quarantine-not-retained')
            kiosk_denial = PAM_AUTH_ERR
        probe('login', 'kiosk', kiosk_denial, 'ownership.refused.kiosk', record)
        conflict.verify()
        record('onpc.ownership.refused',
               variant + '; exact-conflict-and-recovery-records-preserved; payload-retained; child-denied; ordinary-users-allowed; native-PAM-retained; ' +
               ('no-removal-guards-published' if early else 'owned-rollback-mask-retained'))
    if prepared:
        guest.run(['/usr/libexec/oh-no-parent-control-distro-pam',
                   '--distribution', distribution, 'verify'], timeout=60)
        guest.run(['/usr/libexec/oh-no-parent-control-kiosk-lifecycle',
                   '--distribution', distribution, 'rollback'], timeout=60)
    if guest.package_path().suffix == '.deb':
        status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
        guest.require(status in ('install ok installed', 'install ok half-configured'),
                      'ownership:unexpected-recovery-package-status')
        if status == 'install ok half-configured':
            guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
    elif not early:
        guest.install_package()
    guest.verify_package_files()
    verify_surviving_identity(state, recovery, record)
    guest.require(account_digest(child) == recovery['policy'] and
                  extension_lists(child) == recovery['extensions'] and
                  not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-configuration-account.json') and
                  current_expiry() == saved['expires'] and
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
    guest.require(current_expiry() == recovery['expires'] and
                  account_digest(child) == recovery['policy'] and
                  extension_lists(child) == recovery['extensions'],
                  'ownership:reboot-changed-enforcement')
    verify_loaded_confinement()
    verify_gates(record)
    observe_launch(child, False, variant=state.get('native_variant', 'command'))
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'ownership.rebooted.' + role, record)
    wait_kiosk_inactive(pwd.getpwnam(PRODUCT))
    check_remove_preflight()
    guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state, record=record)
    for role in ('ordinary', 'other'):
        probe('login', role, 0, 'ownership.removed.' + role, record)
    observe_launch(state['accounts']['parent'], True, variant=state.get('native_variant', 'command'))
    record('onpc.ownership.retry-finalized', variant +
           '; new-boot; native-remove-succeeded; owned-account-and-home-deleted; exact-original-PAM-and-disposition-restored')


def remove(record):
    guest.guard()
    guest.enable_diagnostics()
    purge_path_diagnostics(record, 'before-removal')
    # Removal must clear product restrictions while preserving native policy.
    # Fedora may already deny untrusted files, so use the baseline's trusted
    # witness rather than treating that independent denial as product policy.
    variant = 'trusted-hard' if guest.package_path().suffix == '.rpm' else 'command'
    accounts = provision_native(variant)
    parent, child = accounts['parent'], accounts['child']
    other = account_digest(accounts['other'])
    other_policy = account_digest(accounts['other'], include_preferences=False)
    other_extensions = extension_lists(accounts['other'])
    defaults = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    guest.require(defaults['parent_control_enabled'] is False and defaults['apps'] == {},
                  'removal:nonfresh-start')
    try:
        for role in ('child', 'other'):
            observe_launch(accounts[role], True, variant=variant)
        configure_restrictions(accounts, variant=variant)
    except guest.GuestError:
        if guest.package_path().suffix == '.rpm':
            restriction_failure_diagnostics()
        raise
    verify_active_kiosk_refusal(record, accounts)
    verify_inflight_admission_refusal(record, accounts, variant=variant)
    fedora = guest.package_path().suffix == '.rpm'
    hook = foreign_integration_refusals(record, accounts, other, fedora=fedora)
    config = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())
    kiosk = pwd.getpwuid(config['kiosk_uid'])
    guest.require(kiosk.pw_name == PRODUCT and kiosk.pw_dir == '/home/' + PRODUCT,
                  'removal:kiosk-identity')
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    state = {'accounts': accounts, 'other': other, 'other_policy': other_policy,
             'native_variant': variant,
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
        'kiosk-configuration-account.json',
        'legacy-kiosk-policy.json', 'legacy-kiosk-policy',
        'package-created-kiosk-uid', 'uninstall-enforcement.json',
        'uninstall-broker-mask', 'installed-gdm-presession',
        'installed-fapolicyd-fallback', 'installed-child-extension-trust',
        'malcontent-pam-before-install', 'fedora-authselect.json',
        'fedora-execution-policy.json', 'installed-fapolicyd-original-policy',
        'fapolicyd-before-install', 'child-trust-backend')]
    # These are the finite shared stacks touched by pam-auth-update and the
    # Fedora PAM owner, plus the vendor GDM/user-manager service files.
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
    """Check selected native/distro PAM readiness, without a private MAC graph.

    The historical callable name remains for the lifecycle-history consumers;
    successful readiness is not installed session or administrator-policy proof.
    """
    guest.guard()
    suffix = guest.package_path().suffix
    guest.require(suffix in ('.deb', '.rpm'), 'removal:package-format')
    integration = runpy.run_path('/usr/lib/oh-no-parent-control/lifecycle/distro_pam.py')
    try:
        integration['runtime_ready']('fedora' if suffix == '.rpm' else 'ubuntu')
    except ValueError:
        raise guest.GuestError('removal:kiosk-pam-not-ready') from None


def check_remove_preflight():
    """Read the installed lifecycle's owned idle boundary without quarantine.

    prepare-remove is a mutating package operation, not a replacement for the
    retired check-remove command. Reuse the actual lifecycle readers and its
    exclusive lease while making no expiry, PAM or recovery-state publication.
    """
    guest.guard()
    lifecycle = runpy.run_path('/usr/lib/oh-no-parent-control/lifecycle/lifecycle_migration.py')
    with lifecycle['barriers']():
        identity = lifecycle['uid']()
        lifecycle['account'](identity)
        expiry = lifecycle['expiry_record'](identity)
        if expiry is not None:
            lifecycle['quarantined'](identity)
        saved = lifecycle['state']()
        lifecycle['marker']()
        if saved is None:
            guest.require(lifecycle['read'](lifecycle['DISABLED'], private=True, optional=True) is None,
                          'removal:unowned-legacy-removal-marker')
        if saved is not None:
            guest.require(saved.get('kiosk_uid', identity) == identity,
                          'removal:changed-kiosk-identity')
            lifecycle['verify_pam'](saved)
            lifecycle['policy_material'](saved)
        lifecycle['idle'](saved, identity)


def verify_inflight_admission_refusal(record, accounts, *, variant='command'):
    """Refuse native erase while real root PAM owns a pre-credential admission."""
    guest.guard()
    from system_kiosk_admission import held_account, probe, verify_gates
    from system_kiosk_confinement import process_identity, exited
    account = pwd.getpwnam(PRODUCT)
    wait_kiosk_inactive(account)
    verify_gates(record)
    observe_launch(accounts['other'], True, variant=variant)
    check_remove_preflight()
    before = admission_removal_state()
    expiry_before = current_expiry()
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
            # The lifecycle must refuse its admission lock before kiosk
            # quarantine, PAM removal, account deletion or payload erasure.
            # Native abort-remove owns restoration of earlier reversible work.
            output = guest.commands.run(removal_command(), check=False, timeout=120,
                                        merge_stderr=True)
            guest.require(guest.commands.last_returncode != 0 and not package_absent() and
                          b'kiosk-lifecycle: [Errno 11] Resource temporarily unavailable' in output,
                          'removal:inflight-admission-not-refused')
            guest.require(not exited(pidfd) and process_identity(process) == identity,
                          'removal:admission-holder-changed')
            verify_loaded_confinement()
            guest.verify_package_payload()
            current = admission_removal_state()
            mask_record = '/var/lib/oh-no-parent-control/uninstall-broker-mask'
            guest.require(before[mask_record] is None and current.keys() == before.keys() and all(
                rollback_record_matches(name, value, current[name])
                for name, value in before.items() if name != mask_record),
                          'removal:inflight-refusal-changed-records')
            mask = Path('/run/systemd/system/oh-no-parent-control-broker.service')
            guest.require(fault_file_identity(Path(mask_record))[-1] == b'' and
                          stat.S_ISLNK(mask.lstat().st_mode) and mask.lstat().st_uid == 0 and
                          os.readlink(mask) == '/dev/null' and
                          current_expiry() == expiry_before and
                          not os.path.lexists('/var/lib/oh-no-parent-control/kiosk-configuration-account.json'),
                          'removal:inflight-refusal-guards-not-retained')
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
            observe_launch(accounts['other'], True, variant=variant)
            observe_launch(accounts['child'], False, variant=variant)
            probe('login', 'ordinary', 0, 'held-removal.ordinary-after', record)
            guest.require(not exited(pidfd) and process_identity(process) == identity,
                          'removal:admission-holder-changed')
            record('onpc.removal.inflight-admission-refused',
                   'root-holder-live; kiosk-manager-inactive; payload-PAM-and-enforcement-restored; exact-recovery-records-preserved; native-expiry-unchanged; own-broker-mask-retained')
        finally:
            os.close(pidfd)
    check_remove_preflight()
    record('onpc.removal.inflight-admission-drained', 'normal-pam-end; removal-preflight-passed')
    fedora = guest.package_path().suffix == '.rpm'
    if not fedora:
        status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
        guest.require(status == 'install ok half-configured',
                      'removal:inflight-unexpected-recovery-package-status')
        guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
    else:
        guest.install_package()
    guest.verify_package_files()
    current = admission_removal_state()
    # Keep the exact comparison below; expose only changed fields and safe
    # metadata so recovery-record drift can be diagnosed without record bytes.
    changes = {}
    for name in sorted(current.keys() | before.keys()):
        if name not in before or name not in current:
            changes[name] = {'fields': ['path-added' if name in current else 'path-removed']}
            continue
        old, new = before[name], current[name]
        if rollback_record_matches(name, old, new, broker_started=fedora):
            continue
        change = {'fields': ['presence'] if old is None or new is None else
                  [field for field, left, right in zip(
                      ('mode', 'owner', 'group', 'content'), old, new) if left != right]}
        for label, value in (('before', old), ('after', new)):
            change[label] = None if value is None else {
                'mode': f'{value[0]:04o}', 'root_owner': value[1] == 0,
                'root_group': value[2] == 0}
        changes[name] = change
    record('onpc.removal.inflight-recovery-record-changes', json.dumps(changes, sort_keys=True))
    guest.require(current.keys() == before.keys() and all(
        rollback_record_matches(name, value, current[name], broker_started=fedora)
        for name, value in before.items()) and
                  current_expiry() == expiry_before and
                  not os.path.lexists('/run/systemd/system/oh-no-parent-control-broker.service') and
                  all(account_digest(accounts[role]) == digest for role, digest in policies.items()),
                  'removal:inflight-recovery-changed-state')
    verify_loaded_confinement()
    verify_gates(record)
    record('onpc.removal.inflight-admission-restored',
           'native-configuration-complete; exact-PAM-ownership-and-enforcement-restored; owned-mask-released')


def verify_active_kiosk_refusal(record, accounts):
    """Use native removal while one identity-recorded kiosk manager is live."""
    guest.guard()
    from system_kiosk_confinement import manager_pid, process_identity, exited, user_command
    account = pwd.getpwnam(PRODUCT)
    unit = f'user@{account.pw_uid}.service'
    wait_kiosk_inactive(account)
    record('onpc.removal.kiosk-inactive-before-owned-start', True)
    originals = admission_removal_state()
    expiry_before = current_expiry()
    policies = {role: account_digest(accounts[role]) for role in ('child', 'other')}
    marker = Path('/var/lib/oh-no-parent-control/kiosk-configuration-account.json')
    guest.require(not os.path.lexists(marker), 'removal:unexpected-removal-marker')
    guest.run(['systemctl', 'start', unit], timeout=75)
    invocation = guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit])
    pid = manager_pid(unit)
    process = Path('/proc') / str(pid)
    pidfd = os.pidfd_open(pid)
    identity = process_identity(process)
    try:
        guest.require(not exited(pidfd) and identity[2] == (str(account.pw_uid),) * 4,
                      'removal:kiosk-manager-identity-changed')
        guest.require(b'systemd ' in user_command(account, [
            '/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
            '--unit=onpc-removal-positive', '/usr/bin/systemctl', '--version']),
            'removal:kiosk-manager-positive')
        output = guest.commands.run(removal_command(), check=False, timeout=1800,
                                    merge_stderr=True)
        guest.require(guest.commands.last_returncode != 0 and not package_absent() and
                      b'log out of the kiosk session before removal' in output,
                      'removal:active-kiosk-not-refused')
        # The live manager also holds native PAM's admission lease, so Debian
        # abort-remove cannot finish its exclusive rollback yet. Verify every
        # retained payload digest now; require full configuration after drain.
        guest.verify_package_payload()
        current = admission_removal_state()
        guest.require(current.keys() == originals.keys() and all(
            rollback_record_matches(name, value, current[name]) for name, value in originals.items()) and
                      not os.path.lexists(marker), 'removal:active-refusal-changed-admission')
        guest.require(all(account_digest(accounts[role]) == digest for role, digest in policies.items()),
                      'removal:active-refusal-changed-policy')
        guest.require(not exited(pidfd) and process_identity(process) == identity,
                      'removal:kiosk-manager-identity-changed')
        record('onpc.removal.active-kiosk-native-removal-refused',
               'package-retained; PAM-and-policy-preserved; owned-manager-live')
    finally:
        try:
            guest.require(pwd.getpwnam(PRODUCT).pw_uid == account.pw_uid and
                          guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit]) == invocation and
                          manager_pid(unit) == pid and not exited(pidfd) and
                          process_identity(process) == identity,
                          'removal:kiosk-manager-identity-changed')
            guest.run(['systemctl', 'stop', unit], timeout=75)
        finally:
            os.close(pidfd)
    check_remove_preflight()
    record('onpc.removal.active-kiosk-drained', True)
    if guest.package_path().suffix == '.deb':
        status = guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT])
        guest.require(status in ('install ok installed', 'install ok half-configured'),
                      'removal:active-unexpected-recovery-package-status')
        record('onpc.removal.active-kiosk-status-before-recovery', status)
        if status == 'install ok half-configured':
            # Finish the already-unpacked package after releasing only this
            # fixture's manager. Do not reinstall over live PAM mappings.
            guest.run(['dpkg', '--configure', PRODUCT], timeout=1800)
    guest.verify_package_files()
    current = admission_removal_state()
    # Retain which record/field changed without exposing its contents or
    # account values. The combined assertion otherwise reports no difference.
    changes = {}
    for name in sorted(current.keys() | originals.keys()):
        if name not in originals or name not in current:
            changes[name] = ['path-added' if name in current else 'path-removed']
            continue
        before, after = originals[name], current[name]
        if rollback_record_matches(name, before, after):
            continue
        changes[name] = (['presence'] if before is None or after is None else
                         [field for field, old, new in zip(
                             ('mode', 'owner', 'group', 'content'), before, after) if old != new])
    record('onpc.removal.active-kiosk-recovery-record-changes', json.dumps(changes, sort_keys=True))
    guest.require(current.keys() == originals.keys() and all(
        rollback_record_matches(name, value, current[name]) for name, value in originals.items()) and
                  current_expiry() == expiry_before and
                  all(account_digest(accounts[role]) == digest for role, digest in policies.items()),
                  'removal:active-recovery-changed-state')
    verify_loaded_confinement()
    record('onpc.removal.active-kiosk-restored',
           'native-configuration-complete; exact-PAM-ownership-and-policy-preserved; original-expiry-restored')


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
    configure_restrictions(state['accounts'], variant=state.get('native_variant', 'command'))
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
