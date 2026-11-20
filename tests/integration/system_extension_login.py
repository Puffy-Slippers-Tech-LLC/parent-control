"""Real GDM login and retained-lock recovery with automatic repair isolated.

The installed owner removes the monitor override in finally, including worker
failure. Native usage reads preserve existing records while allowing normal
accounting from the real desktop; no usage is seeded, reset or replayed.
"""

import json
from pathlib import Path
import stat
import sys
import time

import system_guest as guest
from system_assertions import accepted, account_property, call, session_limits
from system_extension_monitor import BrokerEvents, UUID, invocation, native_choices, state_digest
from system_extension_parent import recovery_proof
from system_graphical_expiry import child_session, screen_lock_observation, wait_for
from system_session_expiry import identities, installed_manager

HISTORY = guest.PAYLOAD / 'results' / 'extension-login.json'
LIMITS = 'com.endlessm.ParentalControls.SessionLimits'
MONITOR_OVERRIDE = Path('/run/systemd/system') / (guest.BROKER + '.d') / '90-onpc-login-test.conf'
# Run the installed launcher, including its trust checks. Override only the
# monitor factory when the launcher imports the service. Live PAM recovery
# and the test's independent Shell observation both need the child-bus helper.
BROKER_WITHOUT_MONITOR = '''\
import builtins
from dataclasses import replace
import runpy
import sys

def import_for_launcher(name, *args, **kwargs):
    module = builtins.__import__(name, *args, **kwargs)
    if name == 'oh_no_parent_control.service':
        production_dependencies = module.production_dependencies
        module.production_dependencies = lambda bus: replace(
            production_dependencies(bus), extension_monitor_factory=None)
    return module

launcher = '/usr/libexec/oh-no-parent-control-broker'
sys.argv = [launcher]
runpy.run_path(launcher, run_name='__main__', init_globals={
    '__builtins__': dict(vars(builtins), __import__=import_for_launcher)})
'''
OVERRIDE_CONTENT = ('[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I -B -c '
                    + json.dumps(BROKER_WITHOUT_MONITOR) + '\n')


def prepare():
    from system_extension_monitor import prepare as prepare_choices
    prepare_choices()
    child = identities()['child']
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{child}', 'org.freedesktop.Accounts.User',
               'SetAutomaticLogin', 'b', 'false'])
    guest.require(account_property(child, 'org.freedesktop.Accounts.User',
                                   'AutomaticLogin') is False, 'extension-login:autologin-enabled')


def load():
    marker = guest.guard()
    history = json.loads(HISTORY.read_text())
    guest.require(history['run'] == marker['run']
                  and history['boot'] == Path('/proc/sys/kernel/random/boot_id').read_text(),
                  'extension-login:history-identity')
    return history


def save(history):
    HISTORY.write_text(json.dumps(history, sort_keys=True))


def reload_broker():
    guest.run(['systemctl', 'daemon-reload'])
    # An active desktop can request D-Bus activation during a separate stop.
    guest.run(['systemctl', 'restart', guest.BROKER])
    guest.activate_broker(restart=False)


def isolate_monitor(history):
    directory = MONITOR_OVERRIDE.parent
    directory.mkdir(mode=0o755, exist_ok=True)
    status = directory.lstat()
    guest.require(stat.S_ISDIR(status.st_mode) and status.st_uid == status.st_gid == 0
                  and not status.st_mode & 0o022, 'extension-login:unsafe-service-drop-ins')
    with MONITOR_OVERRIDE.open('x') as stream:
        status = MONITOR_OVERRIDE.lstat()
        history['override'] = [status.st_dev, status.st_ino]
        stream.write(OVERRIDE_CONTENT)
    save(history)
    reload_broker()


def restore_monitor(history):
    if 'override' not in history:
        return
    guest.enable_diagnostics()
    status = MONITOR_OVERRIDE.lstat()
    guest.require(stat.S_ISREG(status.st_mode) and status.st_uid == status.st_gid == 0
                  and status.st_nlink == 1 and not status.st_mode & 0o022
                  and [status.st_dev, status.st_ino] == history['override']
                  and MONITOR_OVERRIDE.read_text() == OVERRIDE_CONTENT,
                  'extension-login:monitor-override-replaced')
    MONITOR_OVERRIDE.unlink()
    reload_broker()


def timer():
    from oh_no_parent_control.adapters import TimerUsage
    return TimerUsage(None)


def session(child):
    return child_session(child, service='gdm-password')


def usage(uid):
    return [list(interval) for interval in timer().query_usage(uid)]


def preserved(history, manager, accounts):
    for role, uid in accounts.items():
        guest.require(state_digest(uid) == history['states'][role]
                      and account_property(uid, LIMITS, 'DailySchedule') == history['schedules'][role],
                      'extension-login:policy-or-grant-changed')
        current = native_choices(manager, uid)
        if role == 'child':
            current = [[item for item in current[0] if item != UUID],
                       [item for item in current[1] if item != UUID]]
        guest.require(current == history['choices'][role], 'extension-login:other-choices-changed')
        intervals = usage(uid)
        # QueryUsage may merge old and newly checkpointed intervals. Every
        # pre-existing interval must remain covered, without changing its time.
        guest.require(all(any(start <= old_start and end >= old_end for start, end in intervals)
                          for old_start, old_end in history['usage'][role]),
                      'extension-login:recorded-usage-lost')


def disable(manager, child):
    account, _ = manager._account(child)
    enabled, disabled, _ = native_choices(manager, child)
    selected = [item for item in enabled if item != UUID]
    blocked = [item for item in disabled if item != UUID]
    manager._set_list(account, 'enabled-extensions', selected)
    manager._set_list(account, 'disabled-extensions', blocked + [UUID])
    manager._set_boolean(account, 'disable-user-extensions', True)
    guest.require(native_choices(manager, child) == [selected, blocked + [UUID], True],
                  'extension-login:disable-not-saved')
    if manager._shell_owner(account) is not None:
        wait_for(lambda: manager._runtime_state(account) == (False, False),
                 'extension-login:disable-not-active')


def begin():
    marker = guest.guard()
    guest.enable_diagnostics()
    guest.require(not HISTORY.exists() and not HISTORY.is_symlink(), 'extension-login:history-collision')
    accounts = identities()
    child, parent = accounts['child'], accounts['parent']
    manager = installed_manager()
    account, _ = manager._account(child)
    guest.require(session(child) is None and manager._shell_owner(account) is None,
                  'extension-login:fresh-session-already-present')
    accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, 1440)))
    accepted(call(parent, 'RevokeOneTimeGrant', '(u)', (child,)))
    guest.require(session_limits(child) == (2, 86400, [0, 0]), 'extension-login:not-daily-only')
    history = {'run': marker['run'], 'boot': Path('/proc/sys/kernel/random/boot_id').read_text(),
               'monitor_restored': False, 'proofs': {}, 'phase': 'preparing'}
    with HISTORY.open('x') as stream:
        json.dump(history, stream)
    isolate_monitor(history)
    history['invocation'] = invocation()
    history['startup'] = accepted(call(parent, 'GetStartupTimings'))[0]
    history['states'] = {role: state_digest(uid) for role, uid in accounts.items()}
    history['schedules'] = {role: account_property(uid, LIMITS, 'DailySchedule')
                            for role, uid in accounts.items()}
    history['usage'] = {role: usage(uid) for role, uid in accounts.items()}
    history['choices'] = {role: native_choices(manager, uid) for role, uid in accounts.items()}
    history['choices']['child'] = [[item for item in values if item != UUID]
                                    for values in history['choices']['child'][:2]]
    disable(manager, child)
    history['started'] = time.monotonic()
    history['phase'] = 'login'
    save(history)
    return {'prepared': True}


def recovered(history, manager, accounts, kind):
    child = accounts['child']
    account, _ = manager._account(child)
    guest.require(invocation() == history['invocation'], 'extension-login:broker-replaced')
    events = BrokerEvents(history['startup'])
    proof = wait_for(lambda: recovery_proof(events, history['started'], 'RecoverChildExtension',
                     live=kind == 'unlock', switch_recovery_needed=True),
                     'extension-login:authentication-recovery-missing')
    operations = {row['operation'] for _stamp, row in events.since(history['started'])
                  if row['event'] == 'service.008'
                  and row['fields']['method'] == 'RecoverChildExtension'}
    rows = events.since(history['started'])
    guest.require(sum(row['event'] == 'service.006'
                      and row['fields']['method'] == 'RecoverChildExtension' for _stamp, row in rows) == 1
                  and not any(row['event'] == 'extension-manager.command'
                              and row['fields']['operation'] in {'set', 'reset', 'enable', 'disable'}
                              and row['operation'] not in operations for _stamp, row in rows),
                  'extension-login:automatic-or-repeated-repair')
    current = wait_for(lambda: session(child), 'extension-login:gdm-session-missing')
    if kind == 'login':
        history['session'], history['scope'] = current[0], current[1]['Scope']
    def unlocked():
        current = session(child)
        guest.require(current is not None and current[0] == history['session']
                      and current[1]['Scope'] == history['scope']
                      and guest.run(['systemctl', 'is-active', history['scope']]) == 'active',
                      'extension-login:original-session-replaced')
        return not screen_lock_observation(child, history['session'], manager, account,
                                           service='gdm-password')['screensaver_active']
    wait_for(unlocked, 'extension-login:original-session-not-unlocked')
    wait_for(lambda: manager._runtime_state(account) == (True, True),
             'extension-login:runtime-not-active')
    choices = native_choices(manager, child)
    expected = history['choices']['child']
    guest.require(choices == [expected[0] + [UUID], expected[1], False],
                  'extension-login:activation-choices')
    # The supported fixed-purpose native query reads Shell's dailyLimitTime.
    # Its deadline uses the same guest monotonic clock, in microseconds.
    def native_time_usable():
        from oh_no_parent_control.adapters import TimerUsageError
        try:
            return timer().query_native_deadline(child) > time.monotonic_ns() // 1000
        except TimerUsageError as error:
            if str(error) != 'backend-unavailable':
                raise
            return False  # Shell is active before its native-time endpoint is ready.
    wait_for(native_time_usable, 'extension-login:no-positive-native-daily-time')
    preserved(history, manager, accounts)
    history['proofs'][kind] = {**proof, 'single_authentication': True,
        'configured_and_active': True, 'positive_native_daily_time': True,
        'no_grant': True, 'global_switch_recovered': True, 'state_preserved': True,
        'same_session': kind == 'unlock'}


def command(name):
    if name == 'host-ready':
        return begin()
    if name == 'restore' and not HISTORY.exists():
        guest.require(not HISTORY.is_symlink(), 'extension-login:history-link')
        return {'restored': True}  # Preparation refused before recording an override.
    history = load()
    if name == 'restore':
        if not history['monitor_restored']:
            restore_monitor(history)
            history['monitor_restored'] = True
            save(history)
        return {'restored': True}
    accounts, manager = identities(), installed_manager()
    expected = {'login-complete': 'login', 'unlock-fault': 'logged-in', 'host-complete': 'unlock'}
    guest.require(name in expected and history['phase'] == expected[name], 'extension-login:history-order')
    if name == 'unlock-fault':
        account, _ = manager._account(accounts['child'])
        def locked():
            value = session(accounts['child'])
            guest.require(value is not None and value[0] == history['session']
                          and value[1]['Scope'] == history['scope'],
                          'extension-login:original-session-replaced')
            active = screen_lock_observation(accounts['child'], history['session'], manager, account,
                                             service='gdm-password')['screensaver_active']
            return value if active else None
        current = wait_for(locked, 'extension-login:original-session-not-locked')
        guest.require(current is not None and current[0] == history['session']
                      and current[1]['Scope'] == history['scope'],
                      'extension-login:original-session-not-locked')
        preserved(history, manager, accounts)
        # Keep all usage recorded by the original work before unlock as well.
        wait_for(lambda: usage(accounts['child']), 'extension-login:original-usage-not-recorded')
        history['usage'] = {role: usage(uid) for role, uid in accounts.items()}
        disable(manager, accounts['child'])
        history['started'] = time.monotonic()
        history['phase'] = 'unlock'
    else:
        kind = 'login' if name == 'login-complete' else 'unlock'
        recovered(history, manager, accounts, kind)
        history['phase'] = 'logged-in' if kind == 'login' else 'complete'
    save(history)
    return {'completed': name}


def verify(record):
    history = load()
    guest.require(history['phase'] == 'complete' and history['monitor_restored']
                  and set(history['proofs']) == {'login', 'unlock'}, 'extension-login:history-incomplete')
    for name, proof in history['proofs'].items():
        record('onpc.extension-login.' + name, json.dumps(proof, sort_keys=True))


if __name__ == '__main__':
    guest.guard()
    guest.require(len(sys.argv) == 2 and sys.argv[1] in (
        'prepare', 'host-ready', 'login-complete', 'unlock-fault', 'host-complete', 'restore'),
        'extension-login:arguments')
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        print(json.dumps(command(sys.argv[1]), sort_keys=True))
