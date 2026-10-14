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
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call
from system_enforcement import DESKTOP_ID, TARGET, observe_launch, provision_native

PRODUCT = 'oh-no-parent-control'
EXTENSION = 'oh-no-parent-control@tech.puffyslippers.com'
LIMITS = 'com.endlessm.ParentalControls.SessionLimits'
DEBIAN_NOTICE = '/etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice'
REMOVAL_NOTICE = '*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***'


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


def admission_removal_state():
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
    guest.require(arguments == ['exercise-live-refusals'], 'removal:diagnostic-arguments')
    exercise_live_refusals(lambda name, value: print(
        json.dumps({'property': name, 'value': value}, sort_keys=True), flush=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
