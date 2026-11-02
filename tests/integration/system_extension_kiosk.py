"""One installed kiosk approval with operation-owned native recovery.

Reuse the extension area's retained child desktop. The existing identity-guarded
monitor isolation prevents authentication time from racing automatic recovery;
root's real Shell observer and the installed activation path remain available.
The outer restored-VM lifetime owns policy and extension-choice fixtures.
"""

import json
from pathlib import Path
import pwd
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call
from system_caller import FixturePassword, PersistentCaller, TextAgent
from system_extension_monitor import (
    BrokerEvents, DISABLED_CHOICE, ENABLED_CHOICE, Shell, UUID,
    invocation, native_choices, state_digest,
)
from system_extension_parent import isolated_monitor_bus
from system_graphical_expiry import child_session, wait_for
from system_session_expiry import LIMITS, grant, identities, installed_manager


def verify(record):
    guest.guard()
    guest.enable_diagnostics()
    accounts = identities()
    child, parent = accounts['child'], accounts['parent']
    other_parent = pwd.getpwnam('onpc-parent-casey').pw_uid
    kiosk = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())['kiosk_uid']
    manager = installed_manager()
    session, props = wait_for(lambda: child_session(child), 'extension-kiosk:child-session')
    account, _ = manager._account(child)
    shell = Shell(account, manager.session_bus_address(child))
    password = FixturePassword()
    seconds = 600

    def healthy():
        info = shell.info()
        return info.get('state') == 1 and info.get('enabled') is True and shell.enabled()

    def retained():
        current = child_session(child)
        guest.require(current is not None and current[0] == session
                      and current[1]['Scope'] == props['Scope']
                      and guest.run(['systemctl', 'is-active', props['Scope']]) == 'active',
                      'extension-kiosk:child-session-replaced')

    try:
        password.install(parent)
        # Start through a read before the shared isolation helper pins the
        # broker. Fixture controls and headroom grants are outside the measured
        # single approval; no natural-expiry or authentication matrix is replayed.
        accepted(call(parent, 'GetPreferences', '(u)', (child,)))
        with isolated_monitor_bus():
            accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, 0)))
            grant(child, 1200)
            accepted(call(parent, 'SetParentControl', '(ubu)', (accounts['other'], True, 30)))
            grant(accounts['other'], 7200)
            enabled, disabled, _ = native_choices(manager, child)
            guest.require(DISABLED_CHOICE not in enabled and ENABLED_CHOICE not in disabled
                          and enabled.count(ENABLED_CHOICE) <= 1
                          and disabled.count(DISABLED_CHOICE) <= 1,
                          'extension-kiosk:choice-fixture-collision')
            selected = [item for item in enabled if item != UUID]
            excluded = [item for item in disabled if item != UUID]
            if ENABLED_CHOICE not in selected:
                selected.append(ENABLED_CHOICE)
            if DISABLED_CHOICE not in excluded:
                excluded.append(DISABLED_CHOICE)
            manager._set_list(account, 'enabled-extensions', selected)
            manager._set_list(account, 'disabled-extensions', excluded + [UUID])
            manager._set_boolean(account, 'disable-user-extensions', True)
            wait_for(lambda: not healthy(), 'extension-kiosk:disable-not-observed')
            guest.require(native_choices(manager, child) == [selected, excluded + [UUID], True],
                          'extension-kiosk:disabled-choices-not-observed')

            before = account_state(child)
            schedules = {uid: account_property(uid, LIMITS, 'DailySchedule')
                         for uid in accounts.values()}
            others = {uid: state_digest(uid) for uid in (accounts['other'], parent)}
            other_choices = {uid: native_choices(manager, uid) for uid in others}
            identity = invocation()
            events = BrokerEvents(accepted(call(parent, 'GetStartupTimings'))[0])
            with PersistentCaller(kiosk) as caller, TextAgent(caller) as agent:
                started = time.monotonic()
                started_epoch = int(time.time())
                caller.send({'kind': 'call', 'method': 'RequestAccess',
                             'signature': '(uuub)', 'args': (child, parent, seconds, False)})
                agent.prompt(parent, other_parent)
                agent.authenticate(password)
                request, outcome = accepted(caller.receive())
                guest.require(outcome == 'approved', 'extension-kiosk:request-not-approved')
            extension = account_property(child, LIMITS, 'ActiveExtension')
            guest.require(started_epoch <= extension[0] <= int(time.time())
                          and extension[1] == max(0, sum(before[3]) - extension[0]) + seconds,
                          'extension-kiosk:incorrect-single-grant')
            wait_for(healthy, 'extension-kiosk:native-activation-not-observed')

            def rows():
                unique = {}
                for _stamp, row in events.since(started):
                    key = row['sequence']
                    guest.require(key not in unique or unique[key] == row,
                                  'extension-kiosk:conflicting-log-record')
                    unique[key] = row
                return list(unique.values())

            # The asynchronous RequestAccess worker owns service.013 and its
            # activation. service.006 belongs to the separate ingress operation.
            def completed():
                return [row for row in rows() if row['event'] == 'service.013']

            completions = wait_for(completed, 'extension-kiosk:completion-not-observed')
            guest.require(len(completions) == 1, 'extension-kiosk:multiple-approvals')
            completion = completions[0]
            operation = completion['operation']
            owned = [row for row in rows() if row['operation'] == operation
                     and row['sequence'] < completion['sequence']]

            def one(event):
                matches = [row for row in owned if row['event'] == event]
                guest.require(len(matches) == 1, 'extension-kiosk:event-count:' + event)
                return matches[0]

            guest.require(sum(row['event'] == 'service.006'
                              and row['fields']['method'] == 'RequestAccess'
                              for row in rows()) == 1
                          and one('core.026')['fields'] == {
                              'request': request, 'duration_seconds': seconds,
                              'allow_soft': False, 'kind': 'kiosk'}
                          and one('core.grant-calculation')['fields'] == {
                              'request': request, 'daily': 0,
                              'grant': max(0, sum(before[3]) - extension[0]),
                              'additional': seconds, 'calculated': extension[1]}
                          and one('core.038')['fields']['request'] == request
                          and one('core.032')['fields']['request'] == request,
                          'extension-kiosk:approval-transaction-mismatch')
            context = one('extension-manager.activation-context')
            verifications = [row for row in owned
                             if row['event'] == 'extension-manager.runtime-verification']
            guest.require(context['fields']['shell_available'] is True
                          and context['fields']['recover_global_switch'] is True
                          and context['fields']['switch_recovery_needed'] is True
                          and verifications
                          and all(row['fields'] == {
                              'expected': True, 'configured': True, 'active': True}
                              and one('core.038')['sequence'] < context['sequence']
                              < row['sequence'] < one('core.032')['sequence']
                              for row in verifications),
                          'extension-kiosk:approval-activation-not-verified')
            mutations = [row for row in rows() if row['event'] == 'extension-manager.command'
                         and row['fields']['operation'] in {'set', 'reset', 'enable', 'disable'}]
            guest.require(mutations and all(row['operation'] == operation for row in mutations),
                          'extension-kiosk:monitor-only-repair')

            # Explicit idempotent recovery must retain the exact committed grant,
            # rather than replaying the authenticated additional interval.
            accepted(call(parent, 'RecoverChildExtension', '(u)', (child,)))
            after = account_state(child)
            guest.require(after[:3] == before[:3] and after[4:] == before[4:]
                          and after[3] == extension
                          and native_choices(manager, child) == [selected + [UUID], excluded, False]
                          and healthy(), 'extension-kiosk:recovery-replayed-or-changed-policy')
            guest.require(all(state_digest(uid) == value for uid, value in others.items())
                          and all(native_choices(manager, uid) == value
                                  for uid, value in other_choices.items())
                          and all(account_property(uid, LIMITS, 'DailySchedule') == value
                                  for uid, value in schedules.items())
                          and invocation() == identity,
                          'extension-kiosk:unrelated-state-or-broker-changed')
            guest.require(sum(row['event'] == 'core.038' for row in rows()) == 1
                          and sum(row['event'] == 'core.032' for row in rows()) == 1,
                          'extension-kiosk:grant-replayed')
            retained()
            record('onpc.extension-kiosk.recovery', json.dumps({
                'method': 'RequestAccess', 'polkit_authenticated': True,
                'approval_owned_activation': True, 'configured_and_active': True,
                'global_switch_recovered': True, 'exact_choices_preserved': True,
                'additional_seconds': seconds, 'grant_transactions': 1,
                'idempotent_recovery': True, 'same_child_session': True,
                'unrelated_state_preserved': True,
            }, sort_keys=True))
        guest.require(account_property(child, LIMITS, 'ActiveExtension') == extension,
                      'extension-kiosk:grant-changed-after-isolation')
        retained()
    finally:
        shell.close()
