"""Installed Parent recovery, attributed to its real broker operations.

The runner supplies an active Parent desktop and retains the child's native
session. Its normal restored-VM lifetime owns policy/settings cleanup. No
monitor-only repair is accepted as a successful Parent recovery.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call, session_limits
from system_extension_monitor import (
    BrokerEvents, DISABLED_CHOICE, ENABLED_CHOICE, Shell, UUID,
    invocation, native_choices, state_digest,
)
from system_graphical_expiry import child_session, wait_for
from system_session_expiry import (
    grant, identities, installed_manager, isolated_broker_for_extension_faults,
)


@contextmanager
def isolated_monitor_bus():
    """Deny the child-only bus helper, retaining root's installed broker path.

    Stop the old broker first so no connected monitor survives the dependency
    fault. The caller creates its independent Shell observer before entering.
    Restore only the exact installed file and injected permission state.
    """
    from oh_no_parent_control.child_bus import HELPER_PATH
    helper = Path(HELPER_PATH)
    original = helper.lstat()
    guest.require(stat.S_ISREG(original.st_mode) and original.st_uid == original.st_gid == 0
                  and original.st_nlink == 1 and original.st_mode & 0o044 == 0o044
                  and not original.st_mode & 0o022, 'extension-parent:unsafe-bus-helper')
    digest = hashlib.sha256(helper.read_bytes()).digest()
    mode = stat.S_IMODE(original.st_mode)
    injected = mode & ~0o044

    def owned(expected_mode):
        current = helper.lstat()
        guest.require(stat.S_ISREG(current.st_mode) and current.st_uid == current.st_gid == 0
                      and current.st_nlink == 1
                      and (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino)
                      and stat.S_IMODE(current.st_mode) == expected_mode
                      and hashlib.sha256(helper.read_bytes()).digest() == digest,
                      'extension-parent:bus-helper-replaced')

    changed = False
    try:
        with isolated_broker_for_extension_faults():
            owned(mode)
            os.chmod(helper, injected, follow_symlinks=False)
            changed = True
            owned(injected)
        yield
    finally:
        if changed:
            owned(injected)
            os.chmod(helper, mode, follow_symlinks=False)
            owned(mode)


# Run as the administrator on that administrator's real session bus. The
# installed facade owns discovery, same-user authorization and input guards.
# Subsequent calls bind the original owner, path and PID across observations.
PARENT_UI = '''
import json, sys
sys.path.insert(0, '/usr/lib/oh-no-parent-control')
from common.oh_no_parent_control_ui.application_ui_client import UIClient, UIClientError
operation, binding, value = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])
try:
    ui = UIClient('parent', **({'owner': binding['owner'],
        'object_path': binding['path']} if binding else {}))
    if binding and ui.pid != binding['pid']:
        raise UIClientError('OwnerChanged')
    if operation == 'select':
        ui.setValue('parent-child-selector', str(value))
        print(json.dumps({'submitted': True}))
        sys.exit(0)
    elif operation == 'enable':
        if ui.getValue('parent-child-selector') != str(value):
            raise UIClientError('Denied')
        ui.setValue('parent-screen-limit-toggle', True)
        print(json.dumps({'submitted': True}))
        sys.exit(0)
    elif operation == 'close':
        ui.getSurfaceById('parent-window').close()
        print(json.dumps({'closed': True}))
        sys.exit(0)
    elif operation != 'read':
        raise ValueError('operation')
    toggle = ui.getElementById('parent-screen-limit-toggle').snapshot()
    print(json.dumps({'ready': bool(toggle['visible'] and toggle['enabled']),
        'binding': {'owner': ui.owner, 'path': ui.object_path, 'pid': ui.pid},
        'child': ui.getValue('parent-child-selector'),
        'enabled': ui.getValue('parent-screen-limit-toggle'),
        'daily': ui.getValue('parent-daily-limit-selector')}))
except UIClientError as error:
    if operation != 'read' or error.code != 'Unavailable':
        raise
    print(json.dumps({'ready': False}))
'''


def recovery_proof(events, started, method, *, live):
    """Require the frontend operation itself to mutate and verify activation."""
    unique = {}
    for _stamp, row in events.since(started):
        sequence = row['sequence']
        guest.require(sequence not in unique or unique[sequence] == row,
                      'extension-parent:conflicting-log-record')
        unique[sequence] = row
    rows = list(unique.values())
    successes = [row for row in rows if row['event'] == 'service.008'
                 and row['fields']['method'] == method]
    if not successes:
        return None
    guest.require(len(successes) == 1, 'extension-parent:ambiguous-action')
    completed = successes[0]
    owned = [row for row in rows if row['operation'] == completed['operation']
             and row['sequence'] < completed['sequence']]
    contexts = [row for row in owned if row['event'] == 'extension-manager.activation-context']
    guest.require(len(contexts) == 1 and contexts[0]['fields']['shell_available'] is live
                  and contexts[0]['fields']['recover_global_switch'] is True
                  and contexts[0]['fields']['switch_recovery_needed'] is (method == 'SetParentControl'),
                  'extension-parent:wrong-activation-context')
    mutations = [row for row in owned if row['event'] == 'extension-manager.command'
                 and row['fields']['operation'] in {'set', 'reset', 'enable', 'disable'}]
    guest.require(mutations, 'extension-parent:monitor-only-repair')
    if live:
        guest.require(any(row['event'] == 'extension-manager.runtime-verification'
                          and row['fields'] == {'expected': True, 'configured': True,
                                                'active': True} for row in owned),
                      'extension-parent:live-activation-unverified')
    else:
        guest.require(any(row['event'] == 'extension-manager.setting-verification'
                          and row['fields']['stage'] == 'offline'
                          and row['fields']['matches'] for row in owned),
                      'extension-parent:offline-activation-unverified')
    if method == 'SetParentControl':
        guest.require(any(row['event'] == 'core.parent-control-stage'
                          and row['fields'] == {'stage': 'commit', 'outcome': 'accepted'}
                          for row in owned), 'extension-parent:enable-not-committed')
    return {'method': method, 'activation_mutations': len(mutations),
            'live_shell': live, 'frontend_owned_recovery': True}


def verify(publish):
    guest.guard()
    guest.enable_diagnostics()
    accounts = identities()
    manager = installed_manager()
    child = accounts['child']
    session, _ = wait_for(lambda: child_session(child), 'extension-parent:child-session')
    child_account, _ = manager._account(child)
    shell = Shell(child_account, manager.session_bus_address(child))
    try:
        # Saved-off autologin need not start the D-Bus-activated broker. Start
        # it through a read before the shared isolation helper pins its owner.
        accepted(call(accounts['parent'], 'GetPreferences', '(u)', (child,)))
        with isolated_monitor_bus():
            verify_actions(publish, accounts, manager, shell, session)
    finally:
        shell.close()


def verify_actions(publish, accounts, manager, shell, session):
    deadline = time.monotonic() + 600
    parent, _ = manager._account(accounts['parent'])
    child = accounts['child']
    binding = None

    def wait(predicate, name):
        return wait_for(predicate, 'extension-parent:' + name,
                        timeout=max(0, deadline - time.monotonic()))

    def ui(operation='read', value=None):
        result = manager._run_command(parent, ('/usr/bin/python3', '-B', '-c', PARENT_UI,
            operation, json.dumps(binding), json.dumps(value)), require_live=True, timeout=30)
        return json.loads(result.stdout)

    def loaded(uid, enabled):
        value = ui()
        return value if (value['ready'] and value['child'] == str(uid)
                         and value['enabled'] is enabled) else False

    def healthy():
        info = shell.info()
        return info.get('state') == 1 and info.get('enabled') is True and shell.enabled()

    def choices(uid):
        enabled, disabled, global_switch = native_choices(manager, uid)
        return [[item for item in enabled if item != UUID],
                [item for item in disabled if item != UUID], global_switch]

    def disabled(uid, *, global_switch=False):
        account, _ = manager._account(uid)
        enabled, blocked, _ = native_choices(manager, uid)
        manager._set_list(account, 'enabled-extensions', [item for item in enabled if item != UUID])
        manager._set_list(account, 'disabled-extensions',
                          [item for item in blocked if item != UUID] + [UUID])
        manager._set_boolean(account, 'disable-user-extensions', global_switch)
        current = native_choices(manager, uid)
        guest.require(UUID not in current[0] and UUID in current[1]
                      and current[2] is global_switch, 'extension-parent:fault-not-observed')

    def configured(uid):
        current = native_choices(manager, uid)
        return UUID in current[0] and UUID not in current[1] and current[2] is False

    def preserved(expected, extension_choices):
        guest.require(all(state_digest(uid) == value for uid, value in expected.items()),
                      'extension-parent:policy-time-or-grant-changed')
        guest.require(all(choices(uid) == value for uid, value in extension_choices.items()),
                      'extension-parent:other-extension-choices-changed')
        guest.require(all(account_property(uid,
                          'com.endlessm.ParentalControls.SessionLimits', 'DailySchedule') == value
                          for uid, value in schedules.items()),
                      'extension-parent:daily-schedule-changed')
        guest.require(not any(row['event'] == 'extension-manager.command'
                              and row['fields']['operation'] in {'set', 'reset', 'enable', 'disable'}
                              and row['operation'] not in action_operations
                              for _stamp, row in events.since(actions_started)),
                      'extension-parent:automatic-repair-during-isolation')
        current = child_session(child)
        guest.require(current is not None and current[0] == session,
                      'extension-parent:child-session-replaced')

    def record(name, value):
        publish('onpc.extension-parent.' + name, json.dumps(value, sort_keys=True))

    try:
        # Engineering fixture only. Real selection and enable actions below
        # exclusively use Parent's public controls.
        accepted(call(accounts['parent'], 'SetOwnLanguage', '(s)', ('en',)))
        notes_json, = accepted(call(accounts['parent'], 'GetOwnWhatsNew'))
        notes = json.loads(notes_json)
        if any(record['auto_show'] for record in notes['records']):
            accepted(call(accounts['parent'], 'AcknowledgeOwnWhatsNew', '(s)',
                          (notes['product_version'],)))
        for uid in (child, accounts['other']):
            accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (uid, True, 30)))
            grant(uid, 7200)
            account, _ = manager._account(uid)
            enabled, blocked, _ = native_choices(manager, uid)
            guest.require(DISABLED_CHOICE not in enabled and ENABLED_CHOICE not in blocked
                          and enabled.count(ENABLED_CHOICE) <= 1
                          and blocked.count(DISABLED_CHOICE) <= 1,
                          'extension-parent:choice-fixture-collision')
            if ENABLED_CHOICE not in enabled:
                manager._set_list(account, 'enabled-extensions', enabled + [ENABLED_CHOICE])
            if DISABLED_CHOICE not in blocked:
                manager._set_list(account, 'disabled-extensions', blocked + [DISABLED_CHOICE])
        expected = {uid: state_digest(uid) for uid in accounts.values()}
        extension_choices = {uid: choices(uid) for uid in accounts.values()}
        schedules = {uid: account_property(uid,
                      'com.endlessm.ParentalControls.SessionLimits', 'DailySchedule')
                      for uid in accounts.values()}
        identity = invocation()
        events = BrokerEvents(accepted(call(accounts['parent'], 'GetStartupTimings'))[0])
        action_operations = set()
        actions_started = time.monotonic()
        # Parent selects the first returned eligible child at initial load.
        users, = accepted(call(accounts['parent'], 'ListManagedUsers'))
        initial = users[0][0]
        guest.require(initial in (child, accounts['other']), 'extension-parent:unexpected-initial-child')
        second = accounts['other'] if initial == child else child
        disabled(initial)
        started = time.monotonic()
        # The coordinator supplies the shared PARENT01 command operation. It
        # launches once on the active parent desktop and never retries input.
        guest.run(['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'accessible_ui.py'),
                   'parent-command-launch', ''], timeout=120)
        first = wait(lambda: loaded(initial, True), 'initial-selection-not-loaded')
        binding = first['binding']
        proof = wait(lambda: recovery_proof(events, started, 'RecoverChildExtension',
                     live=initial == child), 'initial-recovery-not-observed')
        action_operations.update(row['operation'] for _stamp, row in events.since(started)
                                 if row['event'] == 'service.008'
                                 and row['fields']['method'] == 'RecoverChildExtension')
        wait(lambda: configured(initial), 'initial-not-configured')
        if initial == child:
            wait(healthy, 'initial-not-active')
        preserved(expected, extension_choices)
        record('initial-selection', proof)

        disabled(second)
        started = time.monotonic()
        ui('select', second)
        wait(lambda: loaded(second, True), 'changed-selection-not-loaded')
        proof = wait(lambda: recovery_proof(events, started, 'RecoverChildExtension',
                     live=second == child), 'changed-recovery-not-observed')
        action_operations.update(row['operation'] for _stamp, row in events.since(started)
                                 if row['event'] == 'service.008'
                                 and row['fields']['method'] == 'RecoverChildExtension')
        wait(lambda: configured(second), 'changed-not-configured')
        wait(healthy, 'retained-child-not-active')
        preserved(expected, extension_choices)
        record('changed-selection', proof)

        # Move away before engineering the saved-off fixture, then select it
        # in the same Parent process. Retain a genuinely stale nonzero grant.
        second = child
        ui('select', accounts['other'])
        wait(lambda: loaded(accounts['other'], True), 'return-not-loaded')
        accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (second, False, 30)))
        # This engineering disable is outside the measured action history.
        actions_started = time.monotonic()
        # The timestamp, rather than an incidental wait, makes this grant stale.
        guest.run(['busctl', '--system', 'set-property', 'org.freedesktop.Accounts',
                   f'/org/freedesktop/Accounts/User{second}',
                   'com.endlessm.ParentalControls.SessionLimits', 'ActiveExtension',
                   '(tu)', '1', '1'])
        disabled(second, global_switch=True)
        saved_off_choices = native_choices(manager, second)
        expected[second] = state_digest(second)
        extension_choices[second][2] = True
        started = time.monotonic()
        ui('select', second)
        wait(lambda: loaded(second, False), 'saved-off-not-loaded')
        guest.require(native_choices(manager, second) == saved_off_choices
                      and not healthy(), 'extension-parent:saved-off-selection-enabled')
        preserved(expected, extension_choices)
        guest.require(not any(row['event'] == 'service.006'
                              and row['fields']['method'] == 'RecoverChildExtension'
                              for _stamp, row in events.since(started)),
                      'extension-parent:saved-off-selection-recovered')
        record('saved-off-selection', {'disabled_preserved': True, 'recovery_calls': 0})
        before = account_state(second)
        from oh_no_parent_control.preferences import PreferenceStore
        before_preferences = PreferenceStore().load(second)
        started = time.monotonic()
        ui('enable', second)
        wait(lambda: loaded(second, True), 'first-enable-not-loaded')
        proof = wait(lambda: recovery_proof(events, started, 'SetParentControl',
                     live=second == child), 'first-enable-recovery-not-observed')
        action_operations.update(row['operation'] for _stamp, row in events.since(started)
                                 if row['event'] == 'service.008'
                                 and row['fields']['method'] == 'SetParentControl')
        wait(lambda: configured(second), 'first-enable-not-configured')
        if second == child:
            wait(healthy, 'first-enable-not-active')
        saved = PreferenceStore().load(second)
        guest.require(saved == {**before_preferences, 'parent_control_enabled': True}
                      and session_limits(second) == (2, 1800, [0, 0])
                      and account_state(second)[-1] == before[-1],
                      'extension-parent:first-enable-time-or-policy')
        expected.pop(second)
        extension_choices[second][2] = False
        preserved(expected, extension_choices)
        guest.require(invocation() == identity, 'extension-parent:broker-replaced')
        record('first-enable', {**proof, 'daily_limit_seconds': 1800,
                               'stale_grant_cleared': True, 'app_policy_preserved': True})
    finally:
        if binding is not None:
            ui('close')
