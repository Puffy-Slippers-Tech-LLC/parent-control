"""Installed removal assertions shared by DEB and RPM guarded attempts.

These are engineering checks through package, AccountsService, PAM and logind
APIs. The automatic GDM login is a declared fixture, not customer UI evidence.
The existing outer VM lease owns restoration, including failed transactions.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
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


def account_digest(uid):
    state = account_state(uid)
    return hashlib.sha256(json.dumps(
        [state[0].hex() if state[0] is not None else None, *state[1:]],
        sort_keys=True).encode()).hexdigest()


def preference_digest(uid):
    return guest.sha(Path('/var/lib/oh-no-parent-control/preferences') / f'{uid}.json')


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
    return not any(row.split('\t')[0] == PRODUCT and
                   len(row.split('\t')) == 2 and row.split('\t')[1][1:2] == 'i'
                   for row in rows)


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
            for line in path.read_text().splitlines():
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


def verify_removed(state, *, purged=False):
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
    guest.require(account_digest(state['accounts']['other']) == state['other'],
                  'removal:other-account-changed')
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
                 '/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules',
                 '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules',
                 '/var/lib/oh-no-parent-control/package-created-kiosk-uid',
                 '/var/lib/oh-no-parent-control/uninstall-enforcement.json',
                 '/var/lib/oh-no-parent-control/uninstall-broker-mask',
                 '/var/lib/oh-no-parent-control/fapolicyd-before-install',
                 '/var/lib/oh-no-parent-control/child-trust-backend',
                 '/var/lib/oh-no-parent-control/fedora-authselect.json',
                 '/etc/authselect/custom/oh-no-parent-control',
                 '/run/systemd/system/oh-no-parent-control-broker.service'):
        path = Path(name)
        guest.require(not path.exists() and not path.is_symlink(), 'removal:integration-remains')
    verify_pam_removed()
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


def remove(record):
    guest.guard()
    guest.enable_diagnostics()
    accounts = provision_native()
    parent, child = accounts['parent'], accounts['child']
    other = account_digest(accounts['other'])
    other_extensions = extension_lists(accounts['other'])
    defaults = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    guest.require(defaults['parent_control_enabled'] is False and defaults['apps'] == {},
                  'removal:nonfresh-start')
    configure_restrictions(accounts)
    fedora = guest.package_path().suffix == '.rpm'
    hook = Path('/etc/gdm/PreSession/Default' if fedora else '/etc/gdm3/PreSession/Default')
    info, original = hook.lstat(), hook.read_bytes()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1,
                  'removal:unsafe-hook')
    before = account_digest(child)
    modified = original + b'\n# onpc removal refusal fixture\n'
    write_hook(hook, info, original, modified)
    try:
        guest.commands.run(removal_command(), check=False, timeout=1800, merge_stderr=False)
        guest.require(guest.commands.last_returncode != 0 and not package_absent(),
                      'removal:modified-hook-not-refused')
        guest.require(account_digest(child) == before and
                      account_digest(accounts['other']) == other, 'removal:refusal-changed-policy')
        guest.verify_package_files()
    finally:
        write_hook(hook, info, modified, original)
    record('onpc.removal.refusal-retry', 'modified-hook-refused; payload-and-policy-preserved')
    config = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())
    kiosk = pwd.getpwuid(config['kiosk_uid'])
    guest.require(kiosk.pw_name == PRODUCT and kiosk.pw_dir == '/home/' + PRODUCT,
                  'removal:kiosk-identity')
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    state = {'accounts': accounts, 'other': other, 'preferences': preference_digest(child),
             'defaults': defaults,
             'other_extensions': other_extensions,
             'boot': boot(), 'hook': str(hook), 'kiosk_name': kiosk.pw_name,
             'kiosk_home': kiosk.pw_dir,
             'payload': [item['path'] for item in json.loads(
                 (guest.PAYLOAD / 'installed-files.json').read_text())]}
    if fedora:
        # The lifecycle ownership record retains the pre-product profile.
        state['authselect'] = original_authselect()
    save_state(state)
    output = guest.commands.run(removal_command(), timeout=1800, merge_stderr=True)
    verify_removed(state)
    guest.require(REMOVAL_NOTICE.encode() in output, 'removal:reboot-notice-missing')
    if not fedora:
        guest.require(guest.reboot_requested(), 'removal:reboot-not-requested')
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{child}', 'org.freedesktop.Accounts.User',
               'SetAutomaticLogin', 'b', 'true'])
    guest.require(account_property(child, 'org.freedesktop.Accounts.User', 'AutomaticLogin') is True,
                  'removal:autologin-not-configured')
    record('onpc.removal.erased', 'restrictions-cleared; payload-removed; preferences-retained')


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
    verify_removed(state)
    desktop_health(state['accounts']['child'])
    password_login_health(state['accounts']['child'])
    record('onpc.removal.boot-health',
           'GDM-desktop-active; password-login-accepted; native-execution-allowed; integrations-absent')
    state['removed_boot'] = boot()
    save_state(state)
    guest.install_package()
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
    guest.require(account_digest(state['accounts']['other']) == state['other'],
                  'removal:reinstall-other-account-changed')
    guest.require(account_property(state['accounts']['child'], LIMITS, 'ActiveExtension') == [0, 0],
                  'removal:reinstall-replayed-grant')
    record('onpc.removal.reinstall', 'payload-verified; readiness-passed; preferences-retained; grant-cleared')
    # Exercise the package-delivered action while its payload is installed;
    # the action owns native package removal and its subsequent guarded purge.
    configure_restrictions(state['accounts'])
    state['purged_boot'] = boot()
    save_state(state)
    output = guest.commands.run(['/usr/bin/oh-no-parent-control-purge', '--yes'],
                                timeout=1800, merge_stderr=True)
    verify_removed(state, purged=True)
    guest.require(REMOVAL_NOTICE.encode() in output, 'purge:reboot-notice-missing')
    record('onpc.purge.erased', 'restrictions-cleared; payload-and-saved-data-removed')


def purged_rebooted(record):
    guest.guard()
    guest.enable_diagnostics()
    state = json.loads(state_path().read_text())
    guest.require(boot() != state['purged_boot'] and guest.reboot_cleared(),
                  'purge:reboot-not-observed')
    verify_removed(state, purged=True)
    desktop_health(state['accounts']['child'])
    password_login_health(state['accounts']['child'])
    state['purge_reinstall_boot'] = boot()
    save_state(state)
    guest.install_package()
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
    guest.require(account_digest(accounts['other']) == state['other'],
                  'purge:reinstall-other-account-changed')
    guest.require(account_property(accounts['child'], LIMITS, 'ActiveExtension') == [0, 0],
                  'purge:reinstall-replayed-grant')
    record('onpc.purge.reinstall', 'payload-verified; readiness-passed; fresh-policy-and-request-defaults')
