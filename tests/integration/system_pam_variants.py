"""Finite native PAM install/configure/reboot/removal histories.

The system runner owns the guest lease and restoration. Scenario mutations stay
inside that history; neither package installation nor native probes have a second
implementation here. Fedora's plain case retains its mandatory native includes.
"""

import json
import os
from pathlib import Path
import pwd

import system_guest as guest
from system_assertions import accepted, call
from system_enforcement import DESKTOP_ID, TARGET, observe_launch, provision_native
from system_first_configure import boot, ordinary_controls, verify_visibility
from system_kiosk_accounts import fingerprint, ordinary_state, owned_bytes, verify_ordinary
from system_kiosk_admission import (PAM_AUTH_ERR, empty_authentication_probe,
                                    verify_gates)
from system_kiosk_confinement import verify_session_composition
import system_removal as removal
from system_removal_faults import identity, parents


VARIANTS = ('plain', 'distro-profile', 'administrator-override', 'pending-vendor')
PAM = Path('/etc/pam.d')
VENDOR = Path('/usr/lib/pam.d')
STATE = Path('/var/lib/oh-no-parent-control')
CGFS = ['session', 'optional', 'pam_cgfs.so', '-c', 'freezer,memory,name=systemd']
STACKS = ('common-session', 'common-session-noninteractive')
COMMENT = (b'\n# onpc PAM environment administrator override\n'
           b'session optional pam_permit.so\n')
CONFIGURED = b'PASS: Oh No! Parent Control package configuration completed successfully.'


def require(condition, reason):
    guest.require(condition, 'pam-variants:' + reason)


def fedora():
    return guest.package_path().suffix == '.rpm'


def state_path():
    return guest.PAYLOAD / 'private/pam-variants-state.json'


def save(state):
    path = state_path()
    parents(path)
    require(not path.is_symlink(), 'state-substituted')
    path.write_text(json.dumps(state, sort_keys=True))
    path.chmod(0o600)


def load(variant):
    require(variant in VARIANTS, 'unknown-variant')
    value = json.loads(identity(state_path())[-1])
    require(value.get('schema') == 1 and value.get('variant') == variant,
            'wrong-history-state')
    return value


def rules(path):
    """Finite native input oracle; no product parser supplies this expectation."""
    # Fedora's supported authselect aliases are resolved for observation only.
    path = path.resolve(strict=True)
    return [line.split('#', 1)[0].split() for line in identity(path)[-1].decode().splitlines()
            if line.split('#', 1)[0].strip()]


def optional_profile():
    """Identify the actual distro-owned profile, rather than guessing its name."""
    paths = guest.run(['dpkg-query', '-L', 'libpam-cgfs']).splitlines()
    candidates = [Path(name) for name in paths
                  if Path(name).parent == Path('/usr/share/pam-configs') and
                  b'pam_cgfs.so' in identity(Path(name))[-1]]
    require(len(candidates) == 1, 'ambiguous-reviewed-cgfs-profile')
    profile = candidates[0]
    require(any(line.removeprefix('Session:').split() == CGFS[1:]
                for line in identity(profile)[-1].decode().splitlines()),
            'wrong-reviewed-cgfs-profile')
    return profile.name


def create_owned(path, contents):
    parents(path)
    require(not os.path.lexists(path), 'mutation-collision')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(contents)
        output.flush()
        os.fsync(output.fileno())
    if fedora():
        guest.run(['restorecon', str(path)])
    require(identity(path)[-1] == contents, 'mutation-not-published')
    return fingerprint(path)


def unlink_owned(path, expected, *, inode=None):
    require(fingerprint(path) == expected, 'mutation-identity-changed')
    # The caller's fingerprint includes exact bytes, owner, mode and xattrs;
    # pin the inode as well across the final check before unlinking.
    observed = identity(path)
    require(inode is None or observed[:2] == inode, 'mutation-inode-changed')
    require(identity(path) == observed, 'mutation-raced')
    path.unlink()


def effective_stack(record, stage, state):
    selected = guest.pam_service_state()
    result = {'services': selected, 'variant': state['variant']}
    if 'plain_profile' in state:
        result['optional_profile'] = state['plain_profile']
    if fedora():
        guest.run(['authselect', 'check'])
        if 'authselect_baseline' in state:
            result['authselect_before_mutation'] = state['authselect_baseline']
        result['authselect'] = guest.run(['authselect', 'current', '--raw'])
        native = {name: rules(PAM / name) for name in ('system-auth', 'password-auth')}
        # Name the actual include layout and prove its mandatory Unix gate.
        for rows in native.values():
            require(any(len(row) >= 3 and row[0] == 'session' and
                        row[2] == 'pam_unix.so' for row in rows), 'missing-native-unix-session')
        if state['variant'] == 'distro-profile':
            for rows in native.values():
                require(any(len(row) >= 3 and row[2] == 'pam_sss.so' for row in rows),
                        'missing-native-sssd-layout')
            service = PAM / 'gdm-password'
            rows = rules(service)
            require(any(len(row) >= 3 and row[0] == 'session' and
                        row[1] in ('include', 'substack') and row[2] == 'password-auth'
                        for row in rows), 'missing-vendor-session-include')
        result['native_stacks'] = native
    else:
        native = {name: rules(PAM / name) for name in STACKS}
        for rows in native.values():
            cgfs = [row for row in rows if 'pam_cgfs.so' in row]
            require(cgfs == ([] if state['variant'] == 'plain' else [CGFS]),
                    'wrong-effective-optional-profile')
        result['native_stacks'] = native
    # Only fixed PAM paths/rules and native profile names enter result properties.
    record('onpc.pam-variants.stack.' + stage, json.dumps(result, sort_keys=True))


def prepare(variant, record):
    require(variant in VARIANTS, 'unknown-variant')
    guest.enable_diagnostics()
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    state = {'schema': 1, 'variant': variant, 'boot': boot()}
    if fedora():
        guest.run(['authselect', 'check'])
        state['authselect_original'] = guest.run(['authselect', 'current', '--raw'])
        if variant == 'distro-profile':
            state['authselect_baseline'] = state['authselect_original']
            state['authselect_baseline_stacks'] = {
                name: rules(PAM / name) for name in ('system-auth', 'password-auth')}
            original = state['authselect_baseline'].split()
            require(bool(original), 'missing-authselect-baseline')
            available = guest.run(['authselect', 'list-features', 'sssd']).split()
            require(set(original[1:]) <= set(available), 'unsupported-sssd-profile-features')
            # Select a shipped profile without editing its distro-owned source
            # or forcing replacement of foreign configuration.
            guest.run(['authselect', 'select', 'sssd', *original[1:]])
            guest.run(['authselect', 'check'])
            state['authselect_original'] = guest.run(['authselect', 'current', '--raw'])
            selected = state['authselect_original'].split()
            require(selected and selected[0] == 'sssd' and set(selected[1:]) == set(original[1:]),
                    'sssd-profile-not-selected')
            for name, before in state['authselect_baseline_stacks'].items():
                def mandatory(rows):
                    return {(row[0], row[2]) for row in rows if len(row) >= 3 and
                            row[1] in ('required', 'requisite') and row[2].endswith('.so')}
                require(mandatory(before) <= mandatory(rules(PAM / name)),
                        'sssd-profile-removed-mandatory-module')
    if not fedora():
        from guest_test_dependencies import verify_pam_compatibility
        verify_pam_compatibility(Path('/'))
        if variant == 'plain':
            state['plain_profile'] = optional_profile()
            state['plain_original'] = {name: rules(PAM / name) for name in STACKS}
            guest.run(['pam-auth-update', '--package', '--disable', state['plain_profile']])
            for name, before in state['plain_original'].items():
                require(rules(PAM / name) == [row for row in before if row != CGFS],
                        'plain-mutation-changed-other-security-rules')
    if variant == 'administrator-override':
        source = VENDOR / 'systemd-user'
        original = identity(source)
        state['vendor'] = fingerprint(source)
        contents = original[-1] + COMMENT
        target = PAM / 'systemd-user'
        # A local package-owned file is never overwritten to manufacture this input.
        state['override'] = create_owned(target, contents)
        state['override_bytes'] = contents.hex()
        require(identity(source) == original, 'vendor-source-overwritten')
    state['pam_original'] = guest.pam_service_state()
    state['gdm_original'] = identity(PAM / 'gdm-password')[-1].hex()
    effective_stack(record, 'prepared', state)
    return state


def policy_state(accounts):
    return {role: removal.account_digest(uid) for role, uid in accounts.items()
            if role in ('child', 'other')}


def verify_policy(state, record, stage):
    require(policy_state(state['accounts']) == state['policy'], 'saved-policy-changed-' + stage)
    require(removal.preference_digest(state['accounts']['child']) == state['preferences'],
            'saved-preferences-changed-' + stage)
    record('onpc.pam-variants.policy.' + stage, 'exact-saved-preferences-limits-app-filter-grants')


def configuration_output():
    """Read the exact last native transaction's private stdout and stderr."""
    diagnostic = guest.commands.directory / f'command-{guest.commands.sequence:04d}.txt'
    return (owned_bytes(diagnostic, private=True) +
            (owned_bytes(diagnostic.with_name(diagnostic.stem + '-stderr.txt'),
                         optional=True, private=True) or b''))


def seed_policy(state):
    accounts = provision_native()
    parent, child = accounts['parent'], accounts['child']
    accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, 60)))
    preferences = json.loads(accepted(call(parent, 'GetPreferences', '(u)', (child,)))[0])
    preferences['apps'] = {DESKTOP_ID: {'state': 'permanent', 'targets': [str(TARGET)],
                                      'patterns': [], 'user_saved_match_rule': False}}
    preferences['request'].update(last_selected_duration='custom', last_custom_minutes=23)
    accepted(call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences))))
    # No temporary grant is created: full preservation includes its zero value.
    observe_launch(child, False)
    observe_launch(accounts['other'], True)
    state.update(accounts=accounts, policy=policy_state(accounts),
                 preferences=removal.preference_digest(child))


def pending_retry(state, record):
    """A pending vendor proposal is opaque input, not an admission failure."""
    target = PAM / ('gdm-password.rpmnew' if fedora() else 'gdm-password.dpkg-dist')
    contents = (bytes.fromhex(state['gdm_original']) +
                b'\n# onpc pending vendor PAM update\nsession optional pam_permit.so\n')
    # gdm-password is a declared local baseline input. systemd-user can instead
    # come directly from the vendor directory: local absence is routing state,
    # and publishing an override must not silently change that selection.
    protected = {PAM / 'gdm-password': identity(PAM / 'gdm-password')}
    for path in (PAM / 'systemd-user', VENDOR / 'systemd-user'):
        protected[path] = identity(path) if os.path.lexists(path) else None
    require(any(protected[path] is not None for path in
                (PAM / 'systemd-user', VENDOR / 'systemd-user')), 'missing-systemd-user-service')
    restoration = STATE / ('fedora-authselect.json' if fedora() else 'malcontent-pam-before-install')
    baseline = fingerprint(restoration)
    owned = create_owned(target, contents)
    inode = identity(target)[:2]
    try:
        guest.install_package()
        # Capture the receipt before any subsequent native command advances the
        # diagnostic sequence. RPM status alone cannot prove post-script success.
        require(CONFIGURED in configuration_output(), 'pending-vendor-configuration-incomplete')
        require(fingerprint(target) == owned and identity(target)[:2] == inode,
                'pending-vendor-overwritten')
        require(all((identity(path) if os.path.lexists(path) else None) == expected
                    for path, expected in protected.items()),
                'pending-vendor-changed-owned-pam')
        require(fingerprint(restoration) == baseline, 'pending-vendor-changed-restoration-record')
        for name in ('migration-in-progress', 'package-activation-pending',
                     'kiosk-configuration-account.json'):
            require(not os.path.lexists(STATE / name), 'pending-vendor-retained-barrier')
        guest.installed(reboot_required=guest.reboot_requested())
        removal.verify_loaded_confinement()
        verify_policy(state, record, 'pending-vendor')
        ordinary_controls(record, 'pending-vendor-configured')
        empty_authentication_probe(0, 'pam-variant.pending-vendor.empty-authentication', record)
        record('onpc.pam-variants.pending-vendor.preserved',
               'native-configuration-completed; candidate-and-services-unchanged; restoration-and-policy-preserved')
    finally:
        unlink_owned(target, owned, inode=inode)
    # This successful transaction leaves no half-configured DEB to configure.
    # Repeat the ordinary public install route after removing only our proposal.
    guest.install_package()
    record('onpc.pam-variants.pending-vendor.retry', 'only-owned-pending-candidate-removed; normal-reinstall')


def verify_administrator_denials(record):
    """Real vendor-stack denials remain authoritative for passwordless kiosk use."""
    path = PAM / 'gdm-password'
    original = identity(path)
    info = path.lstat()
    ordinary_controls(record, 'administrator-denial-before')
    empty_authentication_probe(0, 'pam-variant.administrator-before', record)
    # pam_deny returns PAM_AUTH_ERR for both authentication and account calls.
    for kind, authentication, account in (('auth', PAM_AUTH_ERR, None),
                                         ('account', 0, PAM_AUTH_ERR)):
        # Only this reserved identity is denied; ordinary callers execute the
        # original vendor authentication/account stack without a skip or permit.
        prefix = (f'{kind} [success=1 default=ignore] pam_succeed_if.so quiet user != {removal.PRODUCT}\n'
                  f'{kind} requisite pam_deny.so\n').encode()
        edited = prefix + original[-1]
        require(identity(path) == original, 'administrator-policy-identity-changed')
        removal.write_hook(path, info, original[-1], edited)
        try:
            require(identity(path) == original[:-1] + (edited,), 'administrator-policy-not-published')
            empty_authentication_probe(account, 'pam-variant.administrator-' + kind, record,
                                       expected_authenticate=authentication)
            ordinary_controls(record, 'administrator-' + kind + '-denied')
        finally:
            require(identity(path) == original[:-1] + (edited,),
                    'administrator-policy-identity-changed')
            removal.write_hook(path, info, edited, original[-1])
        require(identity(path) == original, 'administrator-policy-not-restored')
        empty_authentication_probe(0, 'pam-variant.administrator-' + kind + '-retry', record)
    ordinary_controls(record, 'administrator-denial-restored')
    record('onpc.pam-variants.administrator-denials',
           'native-auth-and-account-denied; ordinary-users-allowed; exact-identity-restored; empty-token-retry')


def exercise(record, variant):
    guest.guard()
    guest.enable_diagnostics()
    state = prepare(variant, record)
    guest.before_install()
    state['ordinary'] = ordinary_state()
    ordinary_controls(record, 'pam-variant-baseline')
    save(state)
    guest.install_package()
    guest.installed(reboot_required=True)
    verify_visibility()
    verify_gates(record)
    removal.verify_loaded_confinement()
    verify_ordinary(state['ordinary'])
    effective_stack(record, 'installed', state)
    require(guest.reboot_requested(), 'initial-install-missing-reboot')
    save(state)


def verify_reboot(record, variant):
    guest.guard()
    state = load(variant)
    require(state['boot'] != boot() and guest.reboot_cleared(), 'initial-reboot-not-observed')
    guest.installed()
    verify_ordinary(state['ordinary'])
    ordinary_controls(record, 'pam-variant-first-reboot')
    effective_stack(record, 'first-reboot', state)
    verify_session_composition(record)
    empty_authentication_probe(0, 'pam-variant.first-reboot.empty-authentication', record)
    if variant == 'administrator-override':
        verify_administrator_denials(record)
    seed_policy(state)
    save(state)
    if variant == 'pending-vendor':
        pending_retry(state, record)
    else:
        guest.install_package()
    # Same-byte configuration can legitimately require no further reboot marker.
    # The runner still provides a distinct boot before post-retry enforcement.
    # Ubuntu's frontend hook consumes its temporary notice file; Fedora never
    # creates it. Both native routes emit this receipt only after configuration.
    require(CONFIGURED in configuration_output(), 'repeat-configuration-incomplete')
    record('onpc.pam-variants.configuration-receipt', 'native-transaction-completed')
    for name in ('migration-in-progress', 'package-activation-pending',
                 'kiosk-configuration-account.json'):
        require(not os.path.lexists(STATE / name), 'retry-retained-barrier')
    guest.installed(reboot_required=guest.reboot_requested())
    verify_policy(state, record, 'configured')
    verify_ordinary(state['ordinary'])
    verify_visibility()
    effective_stack(record, 'configured', state)
    state['configured_boot'] = boot()
    save(state)


def remove(record, variant):
    guest.guard()
    state = load(variant)
    require(state['configured_boot'] != boot() and guest.reboot_cleared(),
            'configured-reboot-not-observed')
    guest.installed()
    verify_policy(state, record, 'configured-reboot')
    verify_ordinary(state['ordinary'])
    ordinary_controls(record, 'pam-variant-configured-reboot')
    effective_stack(record, 'configured-reboot', state)
    verify_session_composition(record)
    empty_authentication_probe(0, 'pam-variant.configured-reboot.empty-authentication', record)
    observe_launch(state['accounts']['child'], False)
    observe_launch(state['accounts']['other'], True)
    accounts = state['accounts']
    kiosk = pwd.getpwnam(removal.PRODUCT)
    guest.retain_identity_for_redaction(kiosk.pw_uid)
    removed = {'accounts': accounts,
               'other': removal.account_digest(accounts['other']),
               'other_policy': removal.account_digest(accounts['other'], include_preferences=False),
               'other_extensions': removal.extension_lists(accounts['other']),
               'preferences': state['preferences'], 'pam_services': state['pam_original'],
               'hook': '/etc/gdm/PreSession/Default' if fedora() else '/etc/gdm3/PreSession/Default',
               'kiosk_name': kiosk.pw_name, 'kiosk_home': kiosk.pw_dir,
               'payload': [item['path'] for item in json.loads(
                   (guest.PAYLOAD / 'installed-files.json').read_text())]}
    if fedora():
        require(removal.original_authselect() == state['authselect_original'],
                'authselect-restoration-record-changed')
        removed['authselect'] = state['authselect_original']
    state['removed'] = removed
    state['removal_boot'] = boot()
    save(state)
    output = guest.commands.run(removal.removal_command(), timeout=1800, merge_stderr=True)
    require(removal.REMOVAL_NOTICE.encode() in output and guest.reboot_requested(),
            'removal-missing-reboot-notice')
    removal.verify_removed(removed, record=record)
    verify_override(state, record)


def verify_override(state, record):
    if state['variant'] != 'administrator-override':
        return
    target = PAM / 'systemd-user'
    require(identity(target)[-1] == bytes.fromhex(state['override_bytes']) and
            fingerprint(target) == state['override'], 'administrator-override-not-restored-exactly')
    require(fingerprint(VENDOR / 'systemd-user') == state['vendor'], 'vendor-source-changed')
    record('onpc.pam-variants.override-restored', 'exact-bytes-mode-owner-group-xattrs; vendor-unchanged')


def verify_removed_reboot(record, variant):
    guest.guard()
    state = load(variant)
    require(state['removal_boot'] != boot() and guest.reboot_cleared(), 'removal-reboot-not-observed')
    removal.verify_removed(state['removed'], record=record)
    verify_override(state, record)
    verify_ordinary(state['ordinary'])
    ordinary_controls(record, 'pam-variant-removed-reboot')
    if 'authselect_baseline' in state:
        guest.run(['authselect', 'check'])
        require(guest.run(['authselect', 'current', '--raw']) == state['authselect_original'],
                'sssd-fixture-selection-changed')
        guest.run(['authselect', 'select', *state['authselect_baseline'].split()])
        guest.run(['authselect', 'check'])
        require(guest.run(['authselect', 'current', '--raw']) == state['authselect_baseline'] and
                {name: rules(PAM / name) for name in state['authselect_baseline_stacks']} ==
                state['authselect_baseline_stacks'], 'sssd-baseline-not-restored')
        record('onpc.pam-variants.sssd-input-restored', 'exact-original-selection-and-native-rules')
    if variant == 'administrator-override':
        unlink_owned(PAM / 'systemd-user', state['override'])
    if variant == 'plain' and not fedora():
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        require(optional_profile() == state['plain_profile'], 'plain-profile-source-changed')
        guest.run(['pam-auth-update', '--package', '--enable', state['plain_profile']])
        require({name: rules(PAM / name) for name in STACKS} == state['plain_original'],
                'plain-profile-not-restored')
    record('onpc.pam-variants.complete', variant + '; native-enforcement; policy-preserved; removal-restored')
