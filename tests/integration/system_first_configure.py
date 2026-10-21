"""One product-free configure interruption/retry/reboot history.

Faults refuse exact current integration and service-account commands through
the shared owned mount fixture. Product scripts, PAM configuration
and policy bytes remain the package's own; fixture evidence stays private.
"""

from contextlib import contextmanager
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import runpy
import shlex
import shutil
import stat
import tempfile

import system_guest as guest
from system_kiosk_admission import (durable_probe, empty_authentication_probe,
                                   probe, routing, verify_gates)
from system_kiosk_accounts import ordinary_state, verify_fresh_restart, verify_ordinary
from system_removal import persistent_home_identity, verify_loaded_confinement
from system_removal_faults import Fault, identity, mounted_fault, parents


PRODUCT = 'oh-no-parent-control'
PAM_ACCT_EXPIRED = 13
WITNESS = b'onpc-first-configure:exact-native-command-refused\n'
PAM_DEFERRED = b'onpc-first-configure:default-profile-activation-deferred\n'
COMPLETE = Path('/run/oh-no-parent-control-package-configuration-complete')
SHARED_PAM = b'pam_oh_no_parent_control.so'
QUARANTINE = Path('/var/lib/oh-no-parent-control/kiosk-configuration-account.json')


def require(condition, reason):
    guest.require(condition, 'first-configure:' + reason)


def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def state_path():
    return guest.PAYLOAD / 'results/first-configure-state.json'


def verify_compatibility_profile(record, stage):
    """Bind optional PAM compatibility to the actual installed history."""
    if guest.package_path().suffix != '.deb':
        return
    from guest_test_dependencies import verify_pam_compatibility
    result = verify_pam_compatibility(Path('/'))
    record('onpc.first-configure.pam-compatibility.' + stage, json.dumps(result, sort_keys=True))


def wrapper_source(original, witness, arguments):
    """Refuse exactly one invocation before its native side effects."""
    require(bool(arguments), 'empty-native-invocation')
    quote = shlex.quote
    comparisons = ' && '.join(
        f'[ "${index}" = {quote(value)} ]' for index, value in enumerate(arguments, 1))
    delegated = f'{quote(str(original))} "$@"'
    return ('#!/bin/sh\nset -eu\n'
            f'if [ "$#" -eq {len(arguments)} ] && {comparisons}; then\n'
            + '    (set -C; umask 077; '
            + f'printf %s {quote(WITNESS.decode())} > {quote(str(witness))})\n'
            + '    exit 79\nfi\n'
            + f'exec {delegated}\n')


def deferred_pam_source(original, witness):
    """Keep dependency profile updates real, deferring only these defaults."""
    return ('#!/bin/sh\nset -eu\n'
            'if [ "$#" -eq 1 ] && [ "$1" = --package ]; then\n'
            f'    (umask 077; printf %s {shlex.quote(PAM_DEFERRED.decode())} >> {shlex.quote(str(witness))})\n'
            f'    exec {shlex.quote(str(original))} --package '
            '--disable oh-no-parent-control-kiosk-only '
            '--disable oh-no-parent-control-session-limits\n'
            'fi\n'
            f'exec {shlex.quote(str(original))} "$@"\n')


class ConfigureFault(Fault):
    def verify_triggered(self):
        self.verify_artifacts()
        require(identity(self.path) == self.wrapper, 'native-wrapper-changed')
        observed = identity(self.witness)
        expected = (1 <= len(observed[-1].splitlines()) <= 32 and
                    observed[-1] == PAM_DEFERRED * len(observed[-1].splitlines())
                    if self.variant == 'early-pam' else observed[-1] == WITNESS)
        require(stat.S_IMODE(observed[4]) == 0o600 and expected,
                'exact-native-invocation-not-observed')


def fault_command(stage):
    """Select published paths from the verified package format, never VM names."""
    require(stage in ('visibility', 'pam-ready', 'early-pam'), 'unknown-fault-stage')
    fedora = guest.package_path().suffix == '.rpm'
    if stage == 'early-pam':
        require(not fedora, 'unexpected-default-pam-tool')
        return Path('/usr/sbin/pam-auth-update'), (), ['--package'], False
    if stage == 'visibility':
        # This is the first integration publication after account provisioning
        # in postinst. Match its full command, not an unused historical GDM
        # directory. The tool exists in the product-free baseline even when
        # fapolicyd's target directory is created by this installation.
        return Path('/usr/bin/install'), (), [
            '-o', 'root', '-g', 'root', '-m', '0644',
            '/usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules',
            '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules'], False
    # Both distributions reach this exact dependency-account command after
    # real distro PAM activation and before lifecycle commit/release. Refuse
    # it before side effects; native expiry must still quarantine the kiosk.
    return Path('/usr/bin/systemd-sysusers'), (), [
        'malcontent-timer-extension-agent.conf', 'malcontent-timerd.conf',
        'malcontent-webd.conf'], False


@contextmanager
def configure_fault(stage, record):
    guest.guard()
    tool, aliases, arguments, after = fault_command(stage)
    expected = identity(tool)
    private = guest.PAYLOAD / 'private'
    info = private.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and
            stat.S_IMODE(info.st_mode) == 0o700, 'unsafe-private-root')
    parents(private)
    # Child of the controller's retained allocation; no independent scratch root.
    fixture = Path(tempfile.mkdtemp(prefix='first-configure-' + stage + '-', dir=private))
    original, wrapper, witness = (fixture / name for name in ('original', 'wrapper', 'triggered.txt'))
    shutil.copy2(tool, original, follow_symlinks=False)
    require(identity(tool) == expected and original.read_bytes() == expected[-1],
            'native-tool-changed-during-copy')
    wrapper.write_text(deferred_pam_source(original, witness) if stage == 'early-pam' else
                       wrapper_source(original, witness, arguments))
    shutil.copystat(tool, wrapper, follow_symlinks=False)
    for name in os.listxattr(tool):
        require(os.getxattr(tool, name) == os.getxattr(original, name) == os.getxattr(wrapper, name),
                'native-tool-xattr-not-preserved')
    wrapper_identity = identity(wrapper)
    fault = ConfigureFault(stage, tool, expected, witness=witness, wrapper=wrapper_identity,
        artifacts=((original, identity(original)), (wrapper, wrapper_identity)), aliases=aliases)
    record('onpc.first-configure.fault.' + stage, json.dumps({
        'tool': str(tool), 'arguments': arguments, 'after_native_success': after,
        'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'wrapper_sha256': hashlib.sha256(wrapper.read_bytes()).hexdigest()}, sort_keys=True))
    with mounted_fault(fault, wrapper, record):
        yield fault
    record('onpc.first-configure.fault-cleanup.' + stage, 'exact-native-inode-restored')


@contextmanager
def deferred_default_pam(record):
    # Ubuntu dependencies can configure after unpacking our Default: yes
    # profiles. Deliberately exercise the missing-shared-gate interval through
    # public --disable flags. The product's later explicit --enable is intact.
    if guest.package_path().suffix == '.rpm':
        yield
        return
    with configure_fault('early-pam', record) as fault:
        yield
        fault.verify_triggered()


def ordinary_controls(record, stage):
    """Prove the same native account boundary works before kiosk negatives."""
    for service in ('gdm-password', 'login', 'sshd'):
        for role in ('ordinary', 'other'):
            probe(service, role, 0, 'first-configure.' + stage + '.' + service + '.' + role, record)
    for role in ('ordinary', 'other'):
        durable_probe('systemd-user', role, 'account', 0,
                      'first-configure.' + stage + '.systemd-user.' + role, record)


def verify_quarantine(record, stage):
    """Expiry must deny native account admission even with an empty password."""
    guest.guard()
    ordinary_controls(record, stage)
    account = pwd.getpwnam(PRODUCT)
    saved = identity(QUARANTINE)
    state = json.loads(saved[-1])
    require(stat.S_IMODE(saved[4]) == 0o600 and state == {
        'version': 1, 'uid': account.pw_uid, 'expires': None, 'phase': 'quarantined'},
        'quarantine-record-not-retained')
    # Capture only the expiry field through the installed reader. Shadow
    # credentials never enter the command recorder or the result properties.
    lifecycle = runpy.run_path('/usr/lib/oh-no-parent-control/lifecycle/lifecycle_migration.py')
    require(lifecycle['current_expiry']() == 1, 'native-expiry-not-retained')
    record('onpc.first-configure.native-expiry.' + stage,
           'day=1; exact-private-uid-record-retained')
    expected = quarantine_statuses(stage)
    if passwordless():
        empty_authentication_probe(expected['gdm-password'],
                                   'first-configure.' + stage + '.empty-authentication', record)
    for service in ('gdm-password', 'login', 'sshd'):
        probe(service, 'kiosk', expected[service],
              'first-configure.' + stage + '.' + service + '.expired', record)
    durable_probe('systemd-user', 'kiosk', 'account', expected['systemd-user'],
                  'first-configure.' + stage + '.systemd-user.expired', record)
    unit = f'user@{account.pw_uid}.service'
    require(guest.run(['systemctl', 'show', '--property=MainPID', '--value', unit]) == '0',
            'preexisting-kiosk-manager')
    guest.commands.run(['systemctl', 'start', unit], timeout=75,
                       check=False, merge_stderr=True)
    status = guest.commands.last_returncode
    require(type(status) is int and status != 0 and
            guest.run(['systemctl', 'show', '--property=MainPID', '--value', unit]) == '0',
            'expired-kiosk-manager-started')
    record('onpc.first-configure.manager-denied.' + stage, status)
    if guest.package_path().suffix == '.rpm':
        require(guest.run(['getenforce']) == 'Enforcing', 'selinux-not-enforcing')
        permissive = guest.run(['/usr/sbin/semanage', 'permissive', '-l'])
        require(not {'xdm_t', 'init_t'} &
                set(permissive.split()), 'selinux-domain-permissive')


def quarantine_statuses(stage):
    require(stage in ('visibility', 'owned-passwordless', 'pam-ready'),
            'unknown-quarantine-stage')
    services = ('gdm-password', 'login', 'sshd', 'systemd-user')
    if guest.package_path().suffix == '.deb':
        # Ubuntu's common-account maps pam_unix expiry to its requisite
        # pam_deny (PAM_AUTH_ERR). Native empty-token authentication succeeds
        # separately; this is an account-stage denial, not a password failure.
        return dict.fromkeys(services, 7)
    # Fedora's selected shared gate permits dedicated GDM routing and the user
    # manager, leaving vendor expiry authoritative. It refuses login/sshd at
    # its service boundary once activated, before their vendor expiry checks.
    result = dict.fromkeys(services, PAM_ACCT_EXPIRED)
    if stage == 'pam-ready':
        result.update(dict.fromkeys(('login', 'sshd'), 6))
    return result


def account_identity():
    account = pwd.getpwnam(PRODUCT)
    marker = Path('/var/lib/oh-no-parent-control/package-created-kiosk-uid')
    original = identity(marker)
    require(stat.S_IMODE(original[4]) == 0o600 and
            original[-1] == (str(account.pw_uid) + '\n').encode(), 'kiosk-marker-identity')
    home = Path(account.pw_dir)
    require(not home.is_symlink() and home.is_dir(), 'kiosk-home-identity')
    cache = Path('/var/lib/AccountsService/users') / PRODUCT
    info = cache.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
            'kiosk-cache-identity')
    return {
        'account': [account.pw_name, account.pw_uid, account.pw_gid, account.pw_gecos,
                    account.pw_dir, account.pw_shell],
        'marker': [original[1], original[2], original[3], original[4], original[5],
                   hashlib.sha256(original[-1]).hexdigest()],
        'home': persistent_home_identity(home),
        'cache_metadata': [info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode),
                           {name: os.getxattr(cache, name).hex() for name in os.listxattr(cache)}],
        'cache_sha256': hashlib.sha256(cache.read_bytes()).hexdigest(),
    }


def verify_account_identity(expected, stage, record):
    actual = account_identity()
    if stage == 'after-reboot':
        def cache_fingerprint(saved):
            uid, gid, mode, attributes = saved['cache_metadata']
            return {'uid': uid, 'gid': gid, 'mode': mode, 'xattrs': attributes,
                    'sha256': saved['cache_sha256']}
        # Reuse the reviewed AccountsService startup oracle: only its native
        # 0644/0600 -> 0600 transition is allowed, with exact bytes and metadata.
        verify_fresh_restart(cache_fingerprint(expected), cache_fingerprint(actual))
        expected = {**expected, 'cache_metadata': [*expected['cache_metadata'][:2],
                                                 0o600, expected['cache_metadata'][3]]}
        record('onpc.first-configure.cache-mode.after-reboot',
               'native-AccountsService-private-mode; exact-bytes-owner-group-xattrs')
    if (stage in ('after-retry', 'after-reboot') and expected['marker'][2] == 0 and
            actual['marker'][2] != 0):
        # systemd applies the broker's StateDirectory ownership at its first
        # startup. The marker stays the same root-owned private inode/bytes;
        # admit only this exact native administrative-group transition.
        group = 'wheel' if guest.package_path().suffix == '.rpm' else 'sudo'
        group_id = grp.getgrnam(group).gr_gid
        require(guest.run(['systemctl', 'show', '--property=Group', '--value',
                           'oh-no-parent-control-broker.service']) == group,
                'unexpected-broker-state-group')
        directory = QUARANTINE.parent.lstat()
        require(stat.S_ISDIR(directory.st_mode) and directory.st_uid == 0 and
                directory.st_gid == group_id and stat.S_IMODE(directory.st_mode) == 0o700 and
                actual['marker'][2] == group_id, 'unexpected-marker-group-transition')
        expected = {**expected, 'marker': [*expected['marker'][:2], group_id,
                                          *expected['marker'][3:]]}
        record('onpc.first-configure.marker-group.' + stage,
               'native-broker-StateDirectory; root-private; exact-admin-group')
    changed = [key for key in expected if actual[key] != expected[key]]
    record('onpc.first-configure.identity.' + stage, json.dumps({
        'changed': changed, 'expected': expected, 'actual': actual}, sort_keys=True))
    if changed:
        # The fresh fixed product account contains no personal user data.
        (guest.PAYLOAD / 'results/first-configure-cache-after.txt').write_bytes(
            (Path('/var/lib/AccountsService/users') / PRODUCT).read_bytes())
    require(not changed, 'owned-identity-changed-' + stage)


def retry_configuration():
    """Finish an unpacked DEB; RPM retries use the public reinstall route."""
    if guest.package_path().suffix == '.rpm':
        guest.install_package()
        return
    # As in the maintained removal-recovery histories, dpkg owns retrying
    # an already-unpacked postinst. APT --reinstall cannot process its
    # half-configured same-version state. Verify retained payload first;
    # installation/replacement remains exclusively through make install.
    guest.guard()
    guest.verify_package_payload()
    require(guest.run(['dpkg-query', '-W', '-f=${Status}', PRODUCT]) ==
            'install ok half-configured', 'unexpected-retry-package-status')
    guest.run(['dpkg', '--configure', PRODUCT], timeout=2400)


def interrupted_install(fault, record, stage):
    """RPM can report transaction success after a failed post scriptlet."""
    try:
        (guest.install_package if stage == 'visibility' else retry_configuration)()
    except guest.CommandError:
        pass
    status = guest.commands.last_returncode
    record('onpc.first-configure.transaction-status.' + stage, status)
    fault.verify_triggered()
    require(not COMPLETE.exists(), 'interrupted-configuration-marked-complete')
    # The witness, rather than a generic package failure, proves our boundary.
    guest.verify_package_payload()


def passwordless():
    fields = guest.run(['passwd', '--status', PRODUCT]).split()
    require(len(fields) >= 2 and fields[0] == PRODUCT and fields[1] in ('P', 'L', 'NP'),
            'password-status')
    return fields[1] == 'NP'


def verify_visibility():
    account = pwd.getpwnam(PRODUCT)
    require(routing(account.pw_uid) == ('oh-no-parent-control', 'wayland'),
            'dedicated-routing-not-published')
    require(guest.run(['busctl', '--system', 'get-property', 'org.freedesktop.Accounts',
        f'/org/freedesktop/Accounts/User{account.pw_uid}', 'org.freedesktop.Accounts.User',
        'SystemAccount']) == 'b false', 'kiosk-visibility-not-published')


def exercise(record):
    guest.guard()
    (guest.PAYLOAD / 'results').mkdir(mode=0o700, exist_ok=True)
    guest.enable_diagnostics()
    verify_compatibility_profile(record, 'before-install')
    guest.before_install()
    ordinary = ordinary_state()
    ordinary_controls(record, 'baseline')
    with deferred_default_pam(record), configure_fault('visibility', record) as fault:
        interrupted_install(fault, record, 'visibility')
        verify_visibility()
        require(not Path('/var/lib/oh-no-parent-control/installed-gdm-presession').exists(),
                'obsolete-gdm-integration-was-published')
        require(not Path('/var/lib/oh-no-parent-control/installed-fapolicyd-fallback').exists(),
                'refused-integration-was-published')
        require(not Path('/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules').exists(),
                'refused-integration-target-was-published')
        # The original vulnerable interval must be reached before activation of
        # the product's shared account gate, rather than accidentally testing it.
        for name in ('common-account', 'system-auth'):
            path = Path('/etc/pam.d') / name
            if path.exists():
                require(SHARED_PAM not in path.read_bytes(), 'shared-pam-enabled-before-first-fault')
        verify_quarantine(record, 'visibility')
        verify_ordinary(ordinary)
        saved = account_identity()
        (guest.PAYLOAD / 'results/first-configure-cache-before.txt').write_bytes(
            (Path('/var/lib/AccountsService/users') / PRODUCT).read_bytes())
    # Deliberately model an older owned passwordless identity. Native expiry
    # remains active before and after this credential mutation and every retry.
    verify_account_identity(saved, 'before-passwordless-fixture', record)
    guest.run(['passwd', '--delete', PRODUCT])
    require(passwordless(), 'passwordless-retry-fixture-not-established')
    verify_quarantine(record, 'owned-passwordless')
    with configure_fault('pam-ready', record) as fault:
        interrupted_install(fault, record, 'pam-ready')
        verify_visibility()
        verify_account_identity(saved, 'during-retry', record)
        require(passwordless(), 'owned-passwordless-retry-changed-password')
        verify_loaded_confinement()
        verify_quarantine(record, 'pam-ready')
        verify_ordinary(ordinary)
    manager = f'user@{pwd.getpwnam(PRODUCT).pw_uid}.service'
    require(guest.run(['systemctl', 'show', '--property=ActiveState', '--value', manager]) ==
            'failed', 'denied-manager-failure-not-retained')
    require(manager in guest.run(['systemctl', 'list-units', '--plain', '--no-legend',
                                 'user@*.service']).split(),
            'denied-manager-not-in-trigger-enumeration')
    retry_configuration()
    require(guest.run(['systemctl', 'show', '--property=ActiveState', '--value', manager]) ==
            'inactive', 'configured-manager-failure-not-cleared')
    require(manager not in guest.run(['systemctl', 'list-units', '--plain', '--no-legend',
                                     'user@*.service']).split(),
            'configured-manager-still-in-trigger-enumeration')
    # Exercise the native trigger's glob expansion/reload path, restricted to
    # the kiosk unit. An exact literal would load the inactive unit again;
    # this glob matches the same name while excluding inactive units.
    guest.run(['systemctl', 'reload', manager.removesuffix('e') + '[e]'])
    record('onpc.first-configure.manager-recovery',
           'owned-failed-unit-reset; trigger-enumeration-excludes; wildcard-reload-succeeded')
    verify_compatibility_profile(record, 'after-retry')
    verify_account_identity(saved, 'after-retry', record)
    require(passwordless(), 'final-password-not-empty')
    verify_visibility()
    guest.installed(reboot_required=True)
    verify_loaded_confinement()
    verify_gates(record)
    empty_authentication_probe(0, 'first-configure.final.empty-authentication', record)
    require(guest.reboot_requested(), 'retry-did-not-request-reboot')
    verify_ordinary(ordinary)
    state_path().write_text(json.dumps({'schema': 1, 'boot': boot(), 'identity': saved,
                                      'ordinary': ordinary}, sort_keys=True))
    record('onpc.first-configure.retry', 'two-exact-interruptions; native-expiry-denied; owned-passwordless-retry; integration-complete')


def verify_reboot(record):
    guest.guard()
    guest.enable_diagnostics()
    verify_compatibility_profile(record, 'after-reboot')
    saved = json.loads(state_path().read_text())
    require(saved.get('schema') == 1 and saved['boot'] != boot(), 'normal-reboot-not-observed')
    verify_account_identity(saved['identity'], 'after-reboot', record)
    verify_ordinary(saved['ordinary'])
    guest.installed()
    require(guest.reboot_cleared(), 'reboot-marker-retained')
    verify_visibility()
    ordinary_controls(record, 'rebooted')
    verify_gates(record)
    empty_authentication_probe(0, 'first-configure.rebooted.empty-authentication', record)
    verify_loaded_confinement()
    from system_kiosk_confinement import verify_session_composition
    from system_kiosk_scope import verify as verify_ordinary_scope
    verify_session_composition(record)
    verify_ordinary_scope(record)
    verify_ordinary(saved['ordinary'])
    verify_loaded_confinement()
    guest.guard()
    record('onpc.first-configure.reboot', 'new-boot; same-owned-identity; selected-pam-ready; dedicated-routing; ordinary-controls')
