"""Finite native GNOME monitor history in the runner's restored guest.

The initial saved-policy write is engineering preparation: it deliberately
avoids the public enable action, whose own activation would obscure attribution.
All measured recovery belongs to one real installed broker invocation. The
outer installed-system owner restores the autologin and policy fixture.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call
from system_graphical_expiry import child_session, wait_for
from system_session_expiry import grant, identities, installed_manager

UUID = 'oh-no-parent-control@tech.puffyslippers.com'
SHELL = 'org.gnome.Shell'
INTERFACE = 'org.gnome.Shell.Extensions'
PATH = '/org/gnome/Shell'
FIXTURE = guest.PAYLOAD / 'results' / 'extension-prepared.json'
ENABLED_CHOICE = 'onpc-monitor-enabled-fixture@example.invalid'
DISABLED_CHOICE = 'onpc-monitor-disabled-fixture@example.invalid'


def state_digest(uid):
    values = account_state(uid)
    encoded = json.dumps([value.hex() if isinstance(value, bytes) else value
                          for value in values], sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def native_choices(manager, uid):
    account, _ = manager._account(uid)
    return [manager._list(account, 'enabled-extensions'),
            manager._list(account, 'disabled-extensions'),
            manager._boolean(account, 'disable-user-extensions')]


def prepare():
    marker = guest.guard()
    accounts = identities()
    manager = installed_manager()
    child, _ = manager._account(accounts['child'])
    guest.require(not manager._shell_is_available(child), 'extension:prepare-live-shell')
    guest.require(not FIXTURE.exists() and not FIXTURE.is_symlink(),
                  'extension:prepare-collision')
    others = {role: state_digest(accounts[role]) for role in ('other', 'parent')}
    other_choices = native_choices(manager, accounts['other'])
    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)',
                  (accounts['child'], False, 1440)))
    manager._set_boolean(child, 'disable-user-extensions', False)
    enabled = manager._list(child, 'enabled-extensions')
    disabled = manager._list(child, 'disabled-extensions')
    guest.require(not {ENABLED_CHOICE, DISABLED_CHOICE}.intersection(enabled + disabled),
                  'extension:choice-fixture-collision')
    # Harmless absent-payload choices make exact list preservation meaningful
    # even on Fedora's otherwise empty extension inventory.
    manager._set_list(child, 'enabled-extensions',
                      [item for item in enabled if item != UUID] + [ENABLED_CHOICE])
    manager._set_list(child, 'disabled-extensions',
                      [item for item in disabled if item != UUID] + [UUID, DISABLED_CHOICE])
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{accounts["child"]}',
               'org.freedesktop.Accounts.User', 'SetAutomaticLogin', 'b', 'true'])
    guest.require(account_property(accounts['child'], 'org.freedesktop.Accounts.User',
                                   'AutomaticLogin') is True, 'extension:autologin-readback')
    FIXTURE.parent.mkdir(mode=0o700, exist_ok=True)
    with FIXTURE.open('x') as stream:
        json.dump({'run': marker['run'],
                   'boot': Path('/proc/sys/kernel/random/boot_id').read_text(),
                   'other_accounts': others, 'other_child_choices': other_choices}, stream)


class Shell:
    """Root's real connection to the child's public bus; no Shell Eval."""

    def __init__(self, account, address):
        from gi.repository import Gio, GLib
        from oh_no_parent_control.child_bus import connect_child_bus
        self.Gio, self.GLib = Gio, GLib
        self.events = []
        context = GLib.MainContext.new()
        replies = []
        context.push_thread_default()
        attempt = None
        def dispatch_until(predicate, category, timeout):
            deadline = time.monotonic() + timeout
            while not predicate():
                context.iteration(False)
                guest.require(time.monotonic() < deadline, category)
                time.sleep(0.005)
        try:
            attempt = connect_child_bus(account, address, context,
                lambda connection, error: replies.append((connection, error)))
            dispatch_until(lambda: replies, 'extension:observer-connect-timeout', 5)
            self.bus, error = replies[0]
            if error is not None:
                raise error
        finally:
            try:
                if not replies and attempt is not None:
                    attempt.cancel()
                if attempt is not None:
                    dispatch_until(lambda: not attempt.pending, 'extension:observer-connect-cleanup', 2)
            finally:
                context.pop_thread_default()
        self.bus.set_exit_on_close(False)
        self.filter = self.bus.add_filter(self.observe, None)
        self.subscription = self.bus.signal_subscribe(
            SHELL, INTERFACE, 'ExtensionStateChanged', PATH, UUID,
            Gio.DBusSignalFlags.NONE, lambda *_args: None)
        self.properties = self.bus.signal_subscribe(
            SHELL, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', PATH, INTERFACE,
            Gio.DBusSignalFlags.NONE, lambda *_args: None)
        uid = self.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                        'org.freedesktop.DBus', 'GetConnectionUnixUser', '(s)',
                        (self.bus.get_unique_name(),), '(u)')
        guest.require(os.geteuid() == 0 and uid == account.pw_uid,
                      'extension:observer-credentials')

    def observe(self, _bus, message, incoming, _data):
        # Gio's receive thread timestamps notification arrival independently of
        # subprocess completion, pytest polling and host SSH transport.
        if incoming and message.get_message_type() == self.Gio.DBusMessageType.SIGNAL:
            values = message.get_body().unpack()
            if (message.get_interface() == INTERFACE
                    and message.get_member() == 'ExtensionStateChanged'
                    and len(values) == 2 and values[0] == UUID and isinstance(values[1], dict)):
                self.events.append((time.monotonic(), values[1].get('state')))
            elif (message.get_interface() == 'org.freedesktop.DBus.Properties'
                    and message.get_member() == 'PropertiesChanged'
                    and len(values) == 3 and values[0] == INTERFACE
                    and values[1].get('UserExtensionsEnabled') is False):
                self.events.append((time.monotonic(), 0))
        return message

    def call(self, destination, path, interface, method, signature, values, result):
        return self.bus.call_sync(destination, path, interface, method,
            self.GLib.Variant(signature, values), self.GLib.VariantType.new(result),
            self.Gio.DBusCallFlags.NO_AUTO_START, 2000, None).unpack()[0]

    def info(self):
        return self.call(SHELL, PATH, INTERFACE, 'GetExtensionInfo', '(s)', (UUID,), '(a{sv})')

    def enabled(self):
        return self.call(SHELL, PATH, 'org.freedesktop.DBus.Properties', 'Get',
                         '(ss)', (INTERFACE, 'UserExtensionsEnabled'), '(v)')

    def owner(self, name):
        return self.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                         'org.freedesktop.DBus', 'NameHasOwner', '(s)', (name,), '(b)')

    def close(self):
        self.bus.signal_unsubscribe(self.subscription)
        self.bus.signal_unsubscribe(self.properties)
        self.bus.remove_filter(self.filter)
        self.bus.close_sync(None)


def invocation():
    guest.require(guest.run(['systemctl', 'is-active', guest.BROKER]) == 'active',
                  'extension:broker-inactive')
    value = guest.run(['systemctl', 'show', guest.BROKER, '--property=InvocationID', '--value'])
    guest.require(re.fullmatch(r'[0-9a-f]{32}', value) and value != '0' * 32,
                  'extension:broker-invocation')
    return value


class BrokerEvents:
    """Read the real broker's bounded structured log, using its native clock."""

    def __init__(self, startup):
        rows = self.read()
        ready = [row for row in rows if row['event'] == 'service.ready']
        guest.require(ready, 'extension:broker-readiness-log-missing')
        latest = max(ready, key=lambda row: row['timestamp'])
        self.segment = latest['segment']
        # The public startup witness and service.ready describe the same
        # registration boundary. File elapsed_ms is monotonic within a segment.
        self.origin = startup['register_finished_ns'] / 1e9 - latest['elapsed_ms'] / 1000

    @staticmethod
    def read():
        from oh_no_parent_control.logs import decode
        rows = []
        for path in Path('/var/log/oh-no-parent-control/broker').glob('*.events*'):
            try:
                info = path.lstat()
                guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                              info.st_nlink == 1 and info.st_size <= 262144,
                              'extension:unsafe-broker-log')
                raw = path.read_text()
            except FileNotFoundError:
                continue  # A bounded product rotation may rename a listed file.
            for line in raw.splitlines(keepends=True):
                if not line.endswith('\n'):
                    continue  # Never interpret an in-flight append as a record.
                row = json.loads(line)
                decode(json.dumps({key: row[key] for key in ('v', 'event', 'operation', 'fields')}),
                       component='broker')
                guest.require(row['component'] == 'broker' and type(row['elapsed_ms']) is int
                              and row['elapsed_ms'] >= 0, 'extension:invalid-broker-log')
                rows.append(row)
        guest.require(len(rows) < 10000, 'extension:broker-log-bound')
        return rows

    def since(self, started):
        rows = self.read()
        return sorted([(self.origin + row['elapsed_ms'] / 1000, row)
                       for row in rows if row['segment'] == self.segment
                       and self.origin + row['elapsed_ms'] / 1000 >= started],
                      key=lambda item: item[1]['sequence'])


def commands(rows):
    return [(stamp, row) for stamp, row in rows if row['event'] == 'extension-manager.command']


def attempts(rows):
    return [stamp for stamp, row in commands(rows)
            if row['fields'] == {'tool': 'gnome-extensions', 'operation': 'enable',
                                 'key': 'none', 'transport': 'live-session'}]


def failed_verification(rows):
    return any((row['event'] == 'extension-manager.runtime-verification'
                and row['fields']['expected'] is True
                and (not row['fields']['configured'] or not row['fields']['active']))
               or (row['event'] == 'extension-manager.setting-verification'
                   and row['fields']['stage'] == 'live' and not row['fields']['matches'])
               for _stamp, row in rows)


# Run as the real child. A changed handler races actual enablement, rather than
# returning a fabricated Shell reply or modifying installed product code.
INTERFERENCE = '''
import sys
from gi.repository import Gio, GLib
uuid, name, owner = sys.argv[1:]
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
    'org.freedesktop.DBus', 'RequestName', GLib.Variant('(su)', (name, 4)),
    GLib.VariantType.new('(u)'), Gio.DBusCallFlags.NONE, 2000, None)
settings = Gio.Settings.new('org.gnome.shell')
def disable(*unused):
    enabled = settings.get_strv('enabled-extensions')
    if uuid in enabled:
        settings.set_strv('enabled-extensions', [item for item in enabled if item != uuid])
    disabled = settings.get_strv('disabled-extensions')
    if uuid not in disabled:
        settings.set_strv('disabled-extensions', disabled + [uuid])
    Gio.Settings.sync()
settings.connect('changed::enabled-extensions', disable)
settings.connect('changed::disabled-extensions', disable)
loop = GLib.MainLoop()
bus.signal_subscribe(owner, 'org.onpc.ExtensionInterference', 'Stop',
    '/org/onpc/ExtensionInterference', None, Gio.DBusSignalFlags.NONE,
    lambda *unused: loop.quit())
GLib.timeout_add_seconds(45, lambda: (loop.quit(), False)[1])
disable()
loop.run()
'''


def interfere(manager, account, shell, events, run, record):
    name = 'org.onpc.ExtensionInterference.r' + run
    errors = []
    def worker():
        try:
            manager._run_command(account, ('/usr/bin/python3', '-B', '-c',
                INTERFERENCE, UUID, name, shell.bus.get_unique_name()),
                require_live=True, timeout=55)
        except Exception:
            errors.append(True)
    started = time.monotonic()
    thread = threading.Thread(target=worker, name='extension-interference')
    thread.start()
    try:
        wait_for(lambda: shell.owner(name), 'extension:interference-not-ready', timeout=10)
        wait_for(lambda: failed_verification(events.since(started)),
                 'extension:interference-did-not-fail-verification', timeout=35)
    finally:
        # This public signal is consumed only by our bounded child fixture.
        # No process discovery or inferred PID signalling is involved.
        stopped = time.monotonic()
        shell.bus.emit_signal(None, '/org/onpc/ExtensionInterference',
                              'org.onpc.ExtensionInterference', 'Stop', None)
        shell.bus.flush_sync(None)
        thread.join(timeout=60)
        rows = events.since(started)
        record('interference', {'failed_verification': failed_verification(rows),
               'attempts': len(attempts(rows)), 'finished': not thread.is_alive(),
               'child_command_succeeded': not errors})
    guest.require(not thread.is_alive() and not errors, 'extension:interference-cleanup')
    guest.require(1 <= len(attempts(rows)) <= 12, 'extension:interference-attempt-bound')
    return stopped


def verify(publish):
    marker = guest.guard()
    guest.enable_diagnostics()
    prepared = json.loads(FIXTURE.read_text())
    guest.require(prepared['run'] == marker['run'] and
                  prepared['boot'] != Path('/proc/sys/kernel/random/boot_id').read_text(),
                  'extension:reboot-boundary')
    observations = []
    def record(name, value):
        observations.append((name, value))
        pending = FIXTURE.parent / 'extension-observations.pending'
        pending.write_text(json.dumps(observations, sort_keys=True))
        pending.replace(FIXTURE.parent / 'extension-observations.json')
        publish('onpc.extension.' + name, json.dumps(value, sort_keys=True))
    accounts = identities()
    child = accounts['child']
    session, _props = wait_for(lambda: child_session(child), 'extension:child-session')
    manager = installed_manager()
    account, _ = manager._account(child)
    wait_for(lambda: manager._shell_is_available(account), 'extension:shell-unavailable')
    from oh_no_parent_control.preferences import PreferenceStore
    store = PreferenceStore()
    guest.require(not store.load(child)['parent_control_enabled'], 'extension:setup-not-saved-off')
    # The broker is D-Bus activated. A read starts it while controls are still
    # off and witnesses completed startup without enabling the extension.
    accepted(call(accounts['parent'], 'GetPreferences', '(u)', (child,)))
    identity = invocation()
    startup, = accepted(call(accounts['parent'], 'GetStartupTimings'))
    broker_events = BrokerEvents(startup)
    shell = Shell(account, manager.session_bus_address(child))
    shell_owner = shell.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                            'org.freedesktop.DBus', 'GetNameOwner', '(s)', (SHELL,), '(s)')

    def same_shell():
        return shell.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                          'org.freedesktop.DBus', 'GetNameOwner', '(s)', (SHELL,), '(s)') == shell_owner

    began = time.monotonic()
    try:
        # No public enable action or restart occurs after this point. The real
        # broker has already completed its saved-off startup reconciliation.
        preferences = store.load(child)
        info = shell.info()
        record('initial', {'state': info.get('state'), 'enabled': info.get('enabled'),
                          'saved_off': not preferences['parent_control_enabled']})
        guest.require(not preferences['parent_control_enabled'] and
                      info.get('state') == 6 and info.get('enabled') is False and shell.enabled(),
                      'extension:initial-not-never-loaded')
        enabled = manager._list(account, 'enabled-extensions')
        disabled = manager._list(account, 'disabled-extensions')
        choices = ([item for item in enabled if item != UUID],
                   [item for item in disabled if item != UUID])
        guest.require(ENABLED_CHOICE in choices[0] and DISABLED_CHOICE in choices[1],
                      'extension:choice-fixture-missing')
        record('other-choices', {'enabled_count': len(choices[0]),
                                'disabled_count': len(choices[1]),
                                'absent_payload_fixture_choices': 2})
        # A real positive grant makes preservation non-vacuous. No approval or
        # explicit activation is performed by this engineering policy setup.
        grant(child, 1800)
        native_before = account_state(child)[1:]
        snapshot = None

        def stable():
            return shell.info().get('state') == 1 and shell.enabled()

        def completed_recovery(since):
            rows = broker_events.since(since)
            return (stable() and attempts(rows) and any(
                row['event'] == 'extension-manager.012' and row['fields']['enabled']
                for _stamp, row in rows))

        def preserved():
            guest.require(state_digest(child) == snapshot, 'extension:child-policy-changed')
            guest.require(native_choices(manager, accounts['other']) == prepared['other_child_choices'],
                          'extension:other-child-extension-changed')
            for role in ('other', 'parent'):
                guest.require(state_digest(accounts[role]) == prepared['other_accounts'][role],
                              'extension:other-account-changed')
            guest.require(([item for item in manager._list(account, 'enabled-extensions') if item != UUID],
                           [item for item in manager._list(account, 'disabled-extensions') if item != UUID])
                          == choices, 'extension:other-extension-choices-changed')
            guest.require(UUID in manager._list(account, 'enabled-extensions') and
                          UUID not in manager._list(account, 'disabled-extensions') and
                          manager._runtime_state(account) == (True, True),
                          'extension:durable-runtime-membership')
            guest.require(invocation() == identity and same_shell() and child_session(child)[0] == session,
                          'extension:broker-or-session-replaced')
            assisted = {'RecoverChildExtension', 'SetParentControl', 'RequestAccess', 'RequestOwnAccess'}
            guest.require(not any(row['event'] == 'service.006' and row['fields']['method'] in assisted
                                  for _stamp, row in broker_events.since(began)),
                          'extension:explicit-recovery-assisted-monitor')

        def recovery(label, mutate, *, initialized=False):
            started = time.monotonic()
            index = len(shell.events)
            mutate()
            submitted = time.monotonic()
            wait_for(lambda: completed_recovery(started),
                     'extension:' + label + '-not-recovered', timeout=90)
            finished = time.monotonic()
            events = shell.events[index:]
            disabled_at = (started if initialized else
                           next((stamp for stamp, state in events if state in (0, 2, 6)), None))
            active_at = max((stamp for stamp, state in events
                             if state == 1 and disabled_at is not None and stamp >= disabled_at), default=None)
            rows = broker_events.since(started)
            record(label, {'native_signal_seconds': (round(active_at - disabled_at, 3)
                    if active_at is not None and not initialized else None),
                'saved_policy_to_active_seconds': (round(active_at - started, 3)
                    if active_at is not None and initialized else None),
                'submission_seconds': round(submitted - started, 3),
                'observation_seconds': round(finished - submitted, 3),
                'native_enable_attempts': len(attempts(rows))})
            guest.require(disabled_at is not None and active_at is not None,
                          'extension:native-transition-missing')
            guest.require(attempts(rows), 'extension:no-root-live-enable')
            preserved()
            return rows

        def global_disable():
            manager._run_as(account, 'gsettings', 'set', 'org.gnome.shell',
                            'disable-user-extensions', 'true')

        def initialize_policy():
            nonlocal snapshot
            store.save(child, {**preferences, 'parent_control_enabled': True})
            guest.require(account_state(child)[1:] == native_before, 'extension:initial-native-policy-changed')
            snapshot = state_digest(child)
            # A genuine AccountsService notification wakes account discovery
            # without enabling the extension. Restore the exact desktop-language
            # metadata; product preferences and the running session locale stay
            # unchanged. Later checks exercise GNOME's own disable signals.
            if not stable():
                interface = 'org.freedesktop.Accounts.User'
                language = account_property(child, interface, 'Language')
                alternate = ('en_US.UTF-8' if language in ('zh_CN.UTF-8', 'zh_CN.utf8')
                             else 'zh_CN.UTF-8')
                def set_language(value):
                    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                        f'/org/freedesktop/Accounts/User{child}', interface, 'SetLanguage', 's', value])
                try:
                    set_language(alternate)
                finally:
                    set_language(language)
                guest.require(account_property(child, interface, 'Language') == language,
                              'extension:desktop-language-not-restored')

        recovery('initialized-recovery', initialize_policy, initialized=True)
        stopped = interfere(manager, account, shell, broker_events, marker['run'], record)
        wait_for(lambda: completed_recovery(stopped),
                 'extension:interference-not-recovered', timeout=90)
        preserved()
        recovery('global-recovery', global_disable)
        cycles = []
        for number in range(8):
            rows = recovery('individual-' + str(number + 1), lambda:
                manager._run_as(account, 'gnome-extensions', 'disable', '--quiet', UUID))
            cycles.append(attempts(rows)[0])
        intervals = [round(right - left, 3) for left, right in zip(cycles, cycles[1:])]
        record('backoff', {'native_attempt_intervals_seconds': intervals,
                          'disablements': 8, 'cap_seconds': 30})
        # Native daemon command timestamps exclude all host SSH delay. Five
        # seconds cover bounded command/notification work around the 30s wait.
        guest.require(all(29 <= value <= 35 for value in intervals[-2:]),
                      'extension:backoff-not-capped-at-thirty')
        time.sleep(2)
        quiet = time.monotonic()
        deadline = quiet + 65
        while time.monotonic() < deadline:
            guest.require(stable(), 'extension:quiet-not-healthy')
            time.sleep(0.25)
        idle = commands(broker_events.since(quiet))
        record('quiet', {'healthy_seconds': round(time.monotonic() - quiet, 3),
                         'broker_management_commands': len(idle)})
        guest.require(not idle, 'extension:idle-management-commands')
        rows = recovery('cooldown-reset', lambda:
            manager._run_as(account, 'gnome-extensions', 'disable', '--quiet', UUID))
        # The native signal measurement, not pytest/SSH latency, distinguishes
        # a reset cooldown from the previously observed thirty-second delay.
        latest = observations[-1][1]
        guest.require(latest['native_signal_seconds'] < 10, 'extension:quiet-did-not-reset')
        accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, False, 1440)))
        off = time.monotonic()
        global_disable()
        time.sleep(35)
        guest.require(not store.load(child)['parent_control_enabled'] and
                      shell.info().get('state') != 1 and not shell.enabled() and
                      not attempts(broker_events.since(off)), 'extension:parent-off-lost')
        for role in ('other', 'parent'):
            guest.require(state_digest(accounts[role]) == prepared['other_accounts'][role],
                          'extension:other-account-changed')
        guest.require(native_choices(manager, accounts['other']) == prepared['other_child_choices'],
                      'extension:other-child-extension-changed')
        guest.require(invocation() == identity and same_shell() and child_session(child)[0] == session,
                      'extension:broker-or-session-replaced')
        record('parent-off', {'saved_off': True, 'native_enable_attempts': 0,
                              'other_accounts_preserved': True})
    finally:
        try:
            record('broker', {'same_invocation': invocation() == identity,
                              'same_shell_owner': same_shell(),
                              'live_enable_attempts': len(attempts(broker_events.since(began))),
                              'root_observer_uid': 0,
                              'selinux_enforcing': (guest.run(['getenforce']) == 'Enforcing'
                                                    if guest.package_path().suffix == '.rpm'
                                                    else None)})
        finally:
            shell.close()


if __name__ == '__main__':
    guest.require(sys.argv[1:] == ['prepare'], 'extension:arguments')
    prepare()
