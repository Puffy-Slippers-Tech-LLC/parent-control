"""One guarded, real earlier-package policy history; no package installation here.

The runner calls prepare after the old package's boot, verify_updated after
native update, and verify_reboot after the candidate's required reboot.
Checkpoints belong to the runner's existing attempt-private payload allocation.
"""

import json
import os
from pathlib import Path
import pwd
import stat
import time

import system_guest as guest
from system_assertions import accepted, account_property, session_limits
from system_caller import FixturePassword, PersistentCaller, TextAgent
from system_enforcement import call, native_paths, observe_launch, provision_native, record_rules
from system_removal import account_digest, extension_lists, persistent_home_identity

LIMITS = 'com.endlessm.ParentalControls.SessionLimits'
FILTER = 'com.endlessm.ParentalControls.AppFilter'
GRANT_SECONDS = 43200
DAILY_MINUTES = 37
PREFERENCES = Path('/var/lib/oh-no-parent-control/preferences')


def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def state_path():
    return guest.PAYLOAD / 'private/previous-upgrade-state.json'


def binding(marker):
    return {key: marker[key] for key in (
        'run', 'package_sha256', 'baseline_sha256', 'selected_inputs_sha256')}


def save_state(state):
    """Exclusive checkpoint creation never adopts or overwrites prior evidence."""
    path = state_path()
    parent = path.parent.lstat()
    guest.require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == parent.st_gid == 0
                  and stat.S_IMODE(parent.st_mode) == 0o700,
                  'previous-upgrade:private-directory')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(state, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def load_state(marker):
    parent = state_path().parent.lstat()
    guest.require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == parent.st_gid == 0
                  and stat.S_IMODE(parent.st_mode) == 0o700,
                  'previous-upgrade:private-directory')
    fd = os.open(state_path(), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        guest.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                      and info.st_uid == info.st_gid == 0
                      and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 65536,
                      'previous-upgrade:checkpoint-metadata')
        state = json.load(stream)
    guest.require(state.get('schema') == 1 and state.get('binding') == binding(marker),
                  'previous-upgrade:checkpoint-attempt')
    return state


def identity(uid):
    account = pwd.getpwuid(uid)
    home = Path(account.pw_dir)
    guest.require(home.is_dir() and not home.is_symlink(),
                  'previous-upgrade:account-home')
    # Raw names/home paths stay only in this private checkpoint, never properties.
    return {'account': [account.pw_name, uid, account.pw_gid,
                        account.pw_dir, account.pw_shell],
            'home': persistent_home_identity(home)}


def policy_projection(preferences):
    """Compare owned choices across compatible additions to normalized schemas."""
    result = {key: preferences[key] for key in (
        'parent_control_enabled', 'daily_time_limit_minutes', 'apps')}
    result['request'] = {key: preferences['request'][key] for key in (
        'last_selected_duration', 'last_custom_minutes', 'allow_soft_blocked_apps',
        'last_selected_approver_uid', 'kiosk_muted', 'child_muted')}
    return result


def native_state(uid):
    return {'limits': list(session_limits(uid)),
            'filter': account_property(uid, FILTER, 'AppFilter'),
            'extensions': extension_lists(uid)}


def saved_preferences(uid):
    raw = json.loads((PREFERENCES / f'{uid}.json').read_text())
    # v1.2 uses schema 3; v1.3 already uses 4. The current writer requires
    # schema 4, with the preserved/default personal language after migration.
    guest.require(raw.get('version') == 4 and raw.get('personal', {}).get('language') == '',
                  'previous-upgrade:preference-migration')
    return policy_projection(raw)


def verify_grant(expected, observed, now):
    # Screen-Time.md: fixed requests cross midnight, and downtime consumes time.
    guest.require(observed == expected and len(expected) == 2
                  and expected[0] > 0 and expected[1] >= GRANT_SECONDS
                  and expected[0] <= now < sum(expected),
                  'previous-upgrade:grant-expired-or-replaced')
    return sum(expected) - now


def upgraded_identity(role, expected):
    if role != 'kiosk':
        return expected
    guest.require(expected['account'][-1] == '/bin/bash',
                  'previous-upgrade:prior-kiosk-shell')
    # The pinned releases' package-owned kiosk used bash. Current provisioning
    # deliberately installs nologin; every other account/home field stays exact.
    return {**expected, 'account': [*expected['account'][:-1], '/usr/sbin/nologin']}


def verify_preserved(state, record=None):
    child = state['accounts']['child']
    for role, expected in state['identities'].items():
        expected = upgraded_identity(role, expected)
        observed = identity(state['accounts'][role])
        if record is not None:
            record('onpc.previous-upgrade.identity.' + role, json.dumps({
                key: observed.get(key) == expected.get(key) for key in expected}, sort_keys=True))
        guest.require(observed == expected,
                      'previous-upgrade:identity-changed')
    guest.require(account_digest(state['accounts']['other']) == state['other'],
                  'previous-upgrade:other-account-changed')
    guest.require(saved_preferences(child) == state['policy'],
                  'previous-upgrade:saved-policy-changed')
    observed = native_state(child)
    guest.require(observed == state['native'], 'previous-upgrade:native-policy-changed')
    remaining = verify_grant(state['native']['limits'][2], observed['limits'][2], time.time())
    guest.require(remaining <= state['remaining'], 'previous-upgrade:grant-replenished')
    return remaining


def witness_enforcement(accounts, record, stage):
    for variant, allowed in (('trusted-hard', False), ('trusted-soft', True)):
        record_rules('previous-upgrade-' + stage, accounts['child'], not allowed,
                     record, variant=variant)
        observe_launch(accounts['child'], allowed, variant=variant)
        observe_launch(accounts['other'], True, variant=variant)
    record(f'onpc.previous-upgrade.{stage}.native',
           'hard-denied; approved-soft-allowed; unrelated-account-allowed')


def prepare(record):
    marker = guest.guard()
    guest.wait_for_boot()
    previous = guest.PAYLOAD / ('previous-package' + guest.package_path().suffix)
    installed = json.loads((guest.PAYLOAD / 'results/previous-install.json').read_text())
    guest.require(boot() != installed['boot'] and guest.reboot_cleared(),
                  'previous-upgrade:old-package-not-booted')
    guest.require(guest.sha(previous) == installed['previous_package_sha256'],
                  'previous-upgrade:old-package-digest')
    guest.verify_package_files(previous, category='previous-package')
    old = guest.package_identity(previous, installed=True)
    guest.require(old != guest.package_identity(guest.package_path()),
                  'previous-upgrade:requires-earlier-package')
    guest.require(not os.path.lexists(guest.KIOSK_CONFINEMENT_STATE),
                  'previous-upgrade:expected-prelease-package')
    record('onpc.previous-upgrade.packages', json.dumps({
        'previous_version': old,
        'candidate_version': guest.package_identity(guest.package_path()),
        'previous_sha256': guest.sha(previous),
        'candidate_sha256': marker['package_sha256'],
        'boundary': 'prelease-package-without-confinement-record-to-admission-protocol-1',
    }, sort_keys=True))
    accounts = provision_native('trusted-hard')
    guest.require(provision_native('trusted-soft') == accounts,
                  'previous-upgrade:fixture-identities')
    parent, child, other = (accounts[role] for role in ('parent', 'child', 'other'))
    before_other = account_digest(other)
    preferences = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    guest.require(not preferences['parent_control_enabled'] and not preferences['apps'],
                  'previous-upgrade:requires-clean-policy')
    call(parent, 'SetParentControl', '(ubu)', (child, True, DAILY_MINUTES))
    preferences = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    preferences['apps'] = {}
    for variant, app_state in (('trusted-hard', 'permanent'), ('trusted-soft', 'conditional')):
        target, _, desktop = native_paths(variant)
        preferences['apps'][desktop] = {'state': app_state, 'targets': [str(target)],
                                       'patterns': [], 'user_saved_match_rule': False}
    call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences)))
    call(child, 'UpdateRequestPreferences', '(usdbu)', (child, 'custom', 23.0, True, parent))
    # Witness strict soft denial before approval so a missing soft rule cannot pass.
    record_rules('previous-upgrade-strict', child, True, record, variant='trusted-soft')
    observe_launch(child, False, variant='trusted-soft')
    password = FixturePassword()
    password.install(parent)
    other_parent = pwd.getpwnam('onpc-parent-casey').pw_uid
    with PersistentCaller(child) as caller, TextAgent(caller) as agent:
        caller.send({'kind': 'call', 'method': 'RequestOwnAccess',
                     'signature': '(uub)', 'args': (parent, GRANT_SECONDS, True)})
        agent.prompt(parent, other_parent)
        agent.authenticate(password)
        result = accepted(caller.receive())
        guest.require(result[1] == 'approved', 'previous-upgrade:request-not-approved')
    saved = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    policy = policy_projection(saved)
    expected_schema = 4 if guest.package_path().suffix == '.rpm' else 3
    guest.require(saved['version'] == expected_schema, 'previous-upgrade:prior-preference-schema')
    guest.require(policy['parent_control_enabled'] is True
                  and policy['daily_time_limit_minutes'] == DAILY_MINUTES
                  and policy['apps'] == preferences['apps']
                  and policy['request']['last_selected_duration'] == 'custom'
                  and policy['request']['last_custom_minutes'] == 23.0
                  and policy['request']['allow_soft_blocked_apps'] is True
                  and policy['request']['last_selected_approver_uid'] == parent,
                  'previous-upgrade:policy-setup-readback')
    native = native_state(child)
    guest.require(native['limits'][:2] == [2, DAILY_MINUTES * 60],
                  'previous-upgrade:daily-limit-not-applied')
    remaining = verify_grant(native['limits'][2], native['limits'][2], time.time())
    guest.require(account_digest(other) == before_other, 'previous-upgrade:setup-other-changed')
    kiosk = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())['kiosk_uid']
    accounts['kiosk'] = kiosk
    guest.require(identity(kiosk)['account'][-1] == '/bin/bash',
                  'previous-upgrade:prior-kiosk-shell')
    state = {'schema': 1, 'binding': binding(marker), 'boot': boot(), 'old_version': old,
             'accounts': accounts, 'identities': {role: identity(uid) for role, uid in accounts.items()},
             'other': before_other, 'policy': policy, 'native': native, 'remaining': remaining}
    witness_enforcement(accounts, record, 'previous')
    save_state(state)
    record('onpc.previous-upgrade.grant', json.dumps({
        'daily_minutes': DAILY_MINUTES, 'additional_seconds': GRANT_SECONDS,
        'issued_at': native['limits'][2][0], 'duration_seconds': native['limits'][2][1],
        'expiry': sum(native['limits'][2]), 'remaining_after_approval': remaining,
    }, sort_keys=True))
    record('onpc.previous-upgrade.preference-schemas', json.dumps({
        'previous': expected_schema, 'candidate': 4}, sort_keys=True))
    record('onpc.previous-upgrade.prepared',
           'old-package-booted; public-policy-saved; polkit-approved; active-fixed-grant')


def verify_updated(record):
    marker = guest.guard()
    state = load_state(marker)
    guest.require(boot() == state['boot'] and guest.reboot_requested(),
                  'previous-upgrade:update-boot-boundary')
    guest.verify_package_files()
    guest.require(guest.package_identity(guest.package_path(), installed=True) != state['old_version'],
                  'previous-upgrade:package-version-unchanged')
    rules = guest.execution_rule_state()
    guest.verify_reboot_gate()
    retirement = guest.verify_upgrade_admission_receipt(boot())
    guest.require(retirement == 'legacy-integration-retired-current-pam-verified',
                  'previous-upgrade:integration-transition-not-observed')
    guest.require(guest.execution_rule_state() == rules,
                  'previous-upgrade:diagnostics-changed-rules')
    remaining = verify_preserved(state, record)
    record('onpc.previous-upgrade.remaining.updated', remaining)
    record('onpc.previous-upgrade.updated',
           'diagnostics-only; policy-and-identity-preserved; grant-expiry-unchanged')
    record('onpc.previous-upgrade.admission', retirement)


def verify_reboot(record):
    marker = guest.guard()
    state = load_state(marker)
    guest.require(boot() != state['boot'] and guest.reboot_cleared(),
                  'previous-upgrade:candidate-reboot-not-observed')
    guest.installed()
    remaining = verify_preserved(state, record)
    guest.require(remaining < state['remaining'], 'previous-upgrade:grant-did-not-decrease')
    record('onpc.previous-upgrade.remaining.rebooted', remaining)
    accounts = state['accounts']
    parent, child = accounts['parent'], accounts['child']
    policy = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    guest.require(policy_projection(policy) == state['policy'],
                  'previous-upgrade:public-policy-changed')
    call(child, 'PrepareOwnSession')
    before = time.time()
    status = call(parent, 'GetTimeStatus', '(uu)', (child, 0))
    after = time.time()
    expiry = sum(state['native']['limits'][2])
    guest.require(len(status) == 4 and all(type(value) is int and value >= 0 for value in status)
                  and status[0] <= DAILY_MINUTES * 60 and status[2] == 0
                  and max(0, int(expiry - after) - 1) <= status[1] <= int(expiry - before) + 1
                  and status[3] == max(status[0], status[1]),
                  'previous-upgrade:public-time-status')
    verify_preserved(state)
    witness_enforcement(accounts, record, 'rebooted')
    record('onpc.previous-upgrade.rebooted',
           'public-broker-operational; policy-and-identity-preserved; wall-clock-grant-decreased')
