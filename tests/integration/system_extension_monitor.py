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

    def __init__(self, account, address, *, track_owner=False):
        from gi.repository import Gio, GLib
        from oh_no_parent_control.child_bus import connect_child_bus
        self.Gio, self.GLib = Gio, GLib
        self.events = []
        self.owner_events = []
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
        self.owner_subscription = (self.bus.signal_subscribe(
            'org.freedesktop.DBus', 'org.freedesktop.DBus', 'NameOwnerChanged',
            '/org/freedesktop/DBus', SHELL, Gio.DBusSignalFlags.NONE,
            lambda *_args: None) if track_owner else None)
        try:
            uid = self.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                            'org.freedesktop.DBus', 'GetConnectionUnixUser', '(s)',
                            (self.bus.get_unique_name(),), '(u)')
            guest.require(os.geteuid() == 0 and uid == account.pw_uid,
                          'extension:observer-credentials')
        except BaseException:
            self.close()
            raise

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
            elif (message.get_sender() == 'org.freedesktop.DBus'
                    and message.get_interface() == 'org.freedesktop.DBus'
                    and message.get_member() == 'NameOwnerChanged'
                    and len(values) == 3 and values[0] == SHELL):
                self.owner_events.append((time.monotonic(), values[1], values[2]))
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
        if self.owner_subscription is not None:
            self.bus.signal_unsubscribe(self.owner_subscription)
        self.bus.remove_filter(self.filter)
        if not self.bus.is_closed():
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
    def read(component='broker'):
        from oh_no_parent_control.logs import decode
        guest.require(component in {'broker', 'child'}, 'extension:log-component')
        rows = []
        for path in (Path('/var/log/oh-no-parent-control') / component).glob('*.events*'):
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
                       component=component)
                guest.require(row['component'] == component and type(row['elapsed_ms']) is int
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


def verify_lifecycle(publish):
    """One retained installed history for session, transaction and stop ownership.

    The authentication challenge is genuine, deliberately cancelled, and never
    receives a password. No approval, grant or authentication timeout is replayed.
    """
    import select
    import pwd
    from contextlib import contextmanager
    from system_caller import PersistentCaller, TextAgent
    from system_session_expiry import isolated_broker_for_extension_faults

    marker = guest.guard()
    guest.enable_diagnostics()
    prepared = json.loads(FIXTURE.read_text())
    guest.require(prepared['run'] == marker['run'] and
                  prepared['boot'] != Path('/proc/sys/kernel/random/boot_id').read_text(),
                  'extension:lifecycle-reboot-boundary')
    # One finite budget includes preparation, renewed sessions and cleanup;
    # individual waits may not extend the history indefinitely on a slow guest.
    deadline = time.monotonic() + 900
    accounts = identities()
    child = accounts['child']
    manager = installed_manager()
    from oh_no_parent_control.preferences import PreferenceStore
    account, _ = manager._account(child)
    store = PreferenceStore()
    observers = []

    def record(name, value):
        publish('onpc.extension.lifecycle.' + name, json.dumps(value, sort_keys=True))

    def wait(predicate, category, timeout=90):
        remaining = deadline - time.monotonic()
        guest.require(remaining > 0, 'extension:lifecycle-budget')
        return wait_for(predicate, 'extension:lifecycle-' + category,
                        timeout=min(timeout, remaining))

    def observe():
        from gi.repository import Gio, GLib
        def connect():
            address = manager.session_bus_address(child)
            if address is None:
                return False
            try:
                observer = Shell(account, address, track_owner=True)
            except GLib.Error as error:
                # A normal fresh login can still have the stopped daemon's
                # socket path. The maintained transport reports absence and
                # refused/closed connections as these typed startup outcomes.
                if any(error.matches(Gio.io_error_quark(), code) for code in (
                        Gio.IOErrorEnum.NOT_FOUND, Gio.IOErrorEnum.CLOSED)):
                    return False
                raise
            observers.append(observer)
            return observer
        observer = wait(connect, 'user-bus-not-ready')
        wait(lambda: observer.owner(SHELL), 'shell-unavailable')
        def ready():
            try:
                return observer.info()
            except observer.GLib.Error as error:
                # Shell owns its name before exporting the extension object
                # during normal login. Wait only for this startup boundary;
                # unrelated D-Bus failures remain test failures.
                if observer.Gio.DBusError.get_remote_error(error) in {
                        'org.freedesktop.DBus.Error.UnknownMethod',
                        'org.freedesktop.DBus.Error.UnknownObject'}:
                    return False
                raise
        wait(ready, 'extension-interface-not-ready')
        return observer

    def bus_identity(observer):
        def query(method, signature, values, result):
            return observer.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                                 'org.freedesktop.DBus', method, signature, values, result)
        owner = query('GetNameOwner', '(s)', (SHELL,), '(s)')
        pid = query('GetConnectionUnixProcessID', '(s)', (owner,), '(u)')
        guest.require(query('GetConnectionUnixUser', '(s)', (owner,), '(u)') == child
                      and type(pid) is int and pid > 0, 'extension:lifecycle-shell-credentials')
        process = Path('/proc') / str(pid)
        guest.require(process.stat().st_uid == child
                      and (process / 'comm').read_text().strip() == 'gnome-shell',
                      'extension:lifecycle-shell-process')
        start = (process / 'stat').read_text().rsplit(')', 1)[1].split()[19]
        return query('GetId', '()', (), '(s)'), owner, (pid, start)

    def other_accounts_preserved():
        for role in ('other', 'parent'):
            guest.require(state_digest(accounts[role]) == prepared['other_accounts'][role],
                          'extension:lifecycle-other-account-changed')
        guest.require(native_choices(manager, accounts['other']) == prepared['other_child_choices'],
                      'extension:lifecycle-other-extension-changed')

    def no_report(rows):
        # report_failure's systemd-run (and its already-running check) are the
        # only manager commands outside the three native management tools.
        guest.require(not any(row['event'] == 'extension-manager.command'
                              and row['fields']['tool'] == 'other' for _stamp, row in rows),
                      'extension:lifecycle-unexpected-report-launch')

    def healthy():
        return shell.info().get('state') == 1 and shell.enabled()

    def recovered(since):
        rows = events.since(since)
        return healthy() and attempts(rows) and any(
            row['event'] == 'extension-manager.012' and row['fields']['enabled']
            for _stamp, row in rows)

    def preserved():
        guest.require(state_digest(child) == snapshot, 'extension:lifecycle-policy-changed')
        other_accounts_preserved()
        guest.require(([value for value in manager._list(account, 'enabled-extensions') if value != UUID],
                       [value for value in manager._list(account, 'disabled-extensions') if value != UUID])
                      == choices, 'extension:lifecycle-extension-choices-changed')
        guest.require(UUID in manager._list(account, 'enabled-extensions')
                      and UUID not in manager._list(account, 'disabled-extensions')
                      and manager._runtime_state(account) == (True, True),
                      'extension:lifecycle-durable-runtime-membership')

    def disable():
        manager._run_as(account, 'gnome-extensions', 'disable', '--quiet', UUID)

    @contextmanager
    def transaction():
        with PersistentCaller(child) as caller, TextAgent(caller) as agent:
            requested = time.monotonic()
            caller.send({'kind': 'call', 'method': 'RequestOwnAccess', 'signature': '(uub)',
                         'args': (accounts['parent'], 300, False)})
            other_parent = pwd.getpwnam('onpc-parent-casey').pw_uid
            agent.prompt(accounts['parent'], other_parent)
            # An independent real public operation confirms the transaction
            # lock is held. Its Busy refusal cannot change saved/native policy.
            busy = call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 1440))
            guest.require(busy.get('error') == guest.BUS + '.Error.Busy',
                          'extension:lifecycle-transaction-not-held')
            yield caller, agent, requested

    try:
        wait(lambda: child_session(child), 'initial-session')
        shell = observe()
        accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 1440)))
        wait(healthy, 'initial-enable')
        grant(child, 3600)
        snapshot = state_digest(child)
        choices = ([value for value in manager._list(account, 'enabled-extensions') if value != UUID],
                   [value for value in manager._list(account, 'disabled-extensions') if value != UUID])
        identity = invocation()
        events = BrokerEvents(accepted(call(accounts['parent'], 'GetStartupTimings'))[0])
        began = time.monotonic()

        # Attribute this recovery to the monitor, then log out within GNOME's
        # recovery guard. A normal logout must not become an extension failure.
        started = time.monotonic()
        disable()
        wait(lambda: recovered(started), 'before-logout-not-recovered')
        recovered_at = time.monotonic()
        session, _ = child_session(child)
        previous_bus = bus_identity(shell)
        unit = f'user@{child}.service'
        user_invocation = guest.run(['systemctl', 'show', unit, '--property=InvocationID', '--value'])
        guest.require(re.fullmatch(r'[0-9a-f]{32}', user_invocation)
                      and user_invocation != '0' * 32, 'extension:lifecycle-user-manager-identity')
        guest.require(time.monotonic() - recovered_at < 60, 'extension:lifecycle-logout-too-late')
        logout = json.loads(guest.run(['/usr/bin/python3', '-I', str(guest.PAYLOAD / 'session-control'),
                                      'maintenance-logout', str(child), session], timeout=90))
        guest.require(logout.get('outcome') == 'passed' and child_session(child) is None,
                      'extension:lifecycle-logout-not-observed')
        wait(lambda: any(old == previous_bus[1] and not new
                         for _stamp, old, new in shell.owner_events),
             'shell-owner-loss-not-delivered', timeout=15)
        # GNOME can leave the user manager alive after logout. Stop only the
        # exact fixture instance observed before logout, never a renewed one.
        state = guest.run(['systemctl', 'show', unit, '--property=ActiveState', '--value'])
        if state != 'inactive':
            guest.require(guest.run(['systemctl', 'show', unit,
                          '--property=InvocationID', '--value']) == user_invocation,
                          'extension:lifecycle-user-manager-replaced')
            guest.run(['systemctl', 'stop', unit], timeout=60)
        wait(shell.bus.is_closed, 'old-user-bus-not-closed', timeout=30)
        # A stopped user manager may leave its old Unix socket entry behind.
        # That pathname alone is not a live transport: require the real
        # connection closed and the owned service stopped, then compare the
        # next bus's daemon ID and Shell process below.
        guest.require(guest.run(['systemctl', 'show', unit,
                      '--property=ActiveState', '--value']) == 'inactive',
                      'extension:lifecycle-old-user-manager-still-active')
        # The maintained route refuses any remaining user desktop and starts
        # GDM afresh; prepared autologin supplies a real new child session.
        guest.prepare_activation_greeter()
        renewed, _ = wait(lambda: child_session(child), 'fresh-session')
        guest.require(renewed != session, 'extension:lifecycle-session-not-renewed')
        shell = observe()
        current_bus = bus_identity(shell)
        guest.require(current_bus[0] != previous_bus[0]
                      and current_bus[2] != previous_bus[2] and invocation() == identity,
                      'extension:lifecycle-bus-or-broker-not-retained')
        wait(healthy, 'fresh-session-not-healthy')
        started = time.monotonic()
        disable()
        wait(lambda: recovered(started), 'fresh-monitor-not-reattached')
        preserved()
        no_report(events.since(began))
        record('session-replacement', {'normal_logout_after_recovery': True,
               'fresh_session': True, 'new_bus_id': True, 'new_shell_process': True,
               'shell_owner_loss_delivered': True, 'same_broker': True,
               'monitor_recovered_in_fresh_session': True, 'error_reports': 0})

        with transaction() as (caller, agent, requested):
            started = time.monotonic()
            cpu_before = int(guest.run(['systemctl', 'show', guest.BROKER,
                                       '--property=CPUUsageNSec', '--value']))
            disable()
            held_until = time.monotonic() + 4
            while time.monotonic() < held_until:
                guest.require(not healthy() and not attempts(events.since(started)),
                              'extension:lifecycle-recovered-during-transaction')
                guest.require(not select.select([caller.child.stdout], [], [], 0)[0],
                              'extension:lifecycle-authentication-ended-early')
                time.sleep(0.25)
            cpu_after = int(guest.run(['systemctl', 'show', guest.BROKER,
                                      '--property=CPUUsageNSec', '--value']))
            guest.require(0 <= cpu_after - cpu_before < 2_000_000_000,
                          'extension:lifecycle-busy-loop')
            agent.close()  # Cancel this one real challenge; never submit/replay approval.
            result = accepted(caller.receive())
            guest.require(result[1] in ('denied', 'cancelled') and result[2] == 0,
                          'extension:lifecycle-authentication-not-cancelled')
        wait(lambda: recovered(started), 'transaction-release-not-recovered')
        preserved()
        guest.require(sum(row['event'] == 'core.026'
                          for _stamp, row in events.since(requested)) == 1,
                      'extension:lifecycle-authentication-replayed')
        record('transaction', {'held_across_early_retries': True, 'cancelled_without_password': True,
               'cpu_seconds': round((cpu_after - cpu_before) / 1e9, 3),
               'recovered_after_release': True, 'policy_and_grants_preserved': True})

        # A real pending recovery exists while authentication owns the lock.
        # Keep activation masked until the old invocation has fully exited.
        with transaction() as (caller, agent, _requested):
            pending = time.monotonic()
            disable()
            wait(lambda: not healthy(), 'shutdown-fault-not-visible')
            time.sleep(1)
            guest.require(not attempts(events.since(pending)),
                          'extension:lifecycle-shutdown-recovery-not-pending')
            with isolated_broker_for_extension_faults():
                agent.close()
                stopped = time.monotonic()
                guest.require(guest.run(['systemctl', 'show', guest.BROKER,
                              '--property=MainPID', '--value']) == '0',
                              'extension:lifecycle-old-broker-not-exited')
                guest.require('error' in caller.receive(),
                              'extension:lifecycle-stopped-request-completed')
                guest.require(not healthy(), 'extension:lifecycle-stopped-worker-activated')
                # Saved-off is an engineering fixture while the real service
                # is isolated; no human authentication or grant is fabricated.
                preferences = store.load(child)
                store.save(child, {**preferences, 'parent_control_enabled': False})
                stopped_snapshot = state_digest(child)
                quiet_until = time.monotonic() + 3
                while time.monotonic() < quiet_until:
                    guest.require(not healthy(), 'extension:lifecycle-late-stopped-activation')
                    time.sleep(0.25)
                guest.require(not commands(events.since(stopped)),
                              'extension:lifecycle-late-stopped-command')
        guest.require(invocation() != identity, 'extension:lifecycle-broker-not-restarted')
        restarted_events = BrokerEvents(accepted(call(accounts['parent'], 'GetStartupTimings'))[0])
        off = time.monotonic()
        quiet_until = off + 35  # Covers the monitor's maximum existing retry delay.
        while time.monotonic() < quiet_until:
            guest.require(not healthy() and state_digest(child) == stopped_snapshot,
                          'extension:lifecycle-off-state-lost')
            time.sleep(0.5)
        guest.require(not attempts(restarted_events.since(restarted_events.origin)),
                      'extension:lifecycle-restarted-off-worker-activated')
        no_report(events.since(began))
        no_report(restarted_events.since(restarted_events.origin))
        other_accounts_preserved()
        record('broker-replacement', {'pending_recovery_before_stop': True,
               'old_worker_settled': True, 'new_invocation': True, 'saved_off_preserved': True,
               'late_enable_attempts': 0, 'error_reports': 0})
    finally:
        for observer in reversed(observers):
            observer.close()


# Same-user UI adapter for the launch-owned, non-unique Child error reporter.
# Mutations are explicit one-shot operations; polling invokes only 'read'.
REPORT_UI = '''
import json, sys, types
sys.path.insert(0, '/usr/lib/oh-no-parent-control')
support = types.ModuleType('application_ui_support')
sys.modules[support.__name__] = support
exec(sys.argv[1], support.__dict__)
from application_ui_support import process_application_ui, UIClientError
pid, operation = int(sys.argv[2]), sys.argv[3]
try:
    ui = process_application_ui(pid, frontend='child-request')
    with_ui = lambda identity: ui.getElementById(identity)
    dialog = with_ui('feedback-dialog')
    if not dialog.metadata['visible']:
        raise UIClientError('Unavailable')
    if operation == 'edit':
        with_ui('feedback-editor-input').setText(sys.argv[4])
    elif operation == 'close':
        with_ui('feedback-close').activate()
        print(json.dumps({'closed': True}))
        sys.exit(0)
    elif operation != 'read':
        raise ValueError('operation')
    document = with_ui('feedback-editor-document').getValue()
    client = dialog.client
    surfaces = client.listSurfaces()
    print(json.dumps({'ready': True, 'pid': client.pid, 'owner': client.owner,
          'path': client.object_path, 'document': document,
          'reports': sum(s['id'] == 'feedback-dialog' and s['visible'] for s in surfaces),
          'success': any(s['id'] == 'feedback-success-dialog' and s['visible'] for s in surfaces)}))
except UIClientError as error:
    if operation != 'read' or error.code != 'Unavailable':
        raise
    print(json.dumps({'ready': False}))
'''


def verify_failure_reporting(publish):
    """One native ERROR, deferred report/draft, then conservative bus-loss hold.

    The sole native payload fault is restored before renewing the Shell module
    cache. Whole-bus loss uses the runner-created user manager, never a PID kill.
    The outer installed-system owner restores autologin and the VM fixture.
    """
    from contextlib import contextmanager
    from system_session_expiry import isolated_broker_for_extension_faults

    marker = guest.guard()
    guest.enable_diagnostics()
    prepared = json.loads(FIXTURE.read_text())
    guest.require(prepared['run'] == marker['run'] and
                  prepared['boot'] != Path('/proc/sys/kernel/random/boot_id').read_text(),
                  'extension:failure-reboot-boundary')
    deadline = time.monotonic() + 1050
    accounts = identities()
    child = accounts['child']
    manager = installed_manager()
    from oh_no_parent_control.preferences import PreferenceStore
    account, _ = manager._account(child)
    store = PreferenceStore()
    observers = []
    reporter = 'oh-no-parent-control-extension-error.service'
    user_unit = f'user@{child}.service'
    # The verified input tree is root-private. Hand the shared public adapter's
    # source to the child process without exposing the rest of that tree.
    ui_support = Path(__file__).with_name('application_ui_support.py').read_text()

    def record(name, value):
        publish('onpc.extension.failure.' + name, json.dumps(value, sort_keys=True))

    def wait(predicate, category, timeout=90):
        remaining = deadline - time.monotonic()
        guest.require(remaining > 0, 'extension:failure-budget')
        return wait_for(predicate, 'extension:failure-' + category,
                        timeout=min(timeout, remaining))

    def user(*arguments):
        return manager._run_command(account, ('systemctl', '--user', *arguments),
                                    require_live=True).stdout.strip()

    def user_identity():
        value = guest.run(['systemctl', 'show', user_unit, '--property=InvocationID', '--value'])
        guest.require(re.fullmatch(r'[0-9a-f]{32}', value) and value != '0' * 32,
                      'extension:failure-user-manager-identity')
        return value

    def observe():
        wait(lambda: child_session(child), 'child-session')
        wait(lambda: manager._shell_is_available(account), 'shell-unavailable')
        observer = Shell(account, manager.session_bus_address(child), track_owner=True)
        observers.append(observer)
        def ready():
            try:
                return observer.info()
            except observer.GLib.Error as error:
                if observer.Gio.DBusError.get_remote_error(error) in {
                        'org.freedesktop.DBus.Error.UnknownMethod',
                        'org.freedesktop.DBus.Error.UnknownObject'}:
                    return False
                raise
        wait(ready, 'extension-interface')
        return observer

    def automatic_login(enabled):
        guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                   f'/org/freedesktop/Accounts/User{child}', 'org.freedesktop.Accounts.User',
                   'SetAutomaticLogin', 'b', str(enabled).lower()])
        guest.require(account_property(child, 'org.freedesktop.Accounts.User',
                                       'AutomaticLogin') is enabled,
                      'extension:failure-autologin-readback')

    def logout():
        session, _ = child_session(child)
        result = json.loads(guest.run(['/usr/bin/python3', '-I', str(Path(__file__).with_name('session-control')),
                                     'maintenance-logout', str(child), session], timeout=90))
        guest.require(result.get('outcome') == 'passed' and child_session(child) is None,
                      'extension:failure-logout-not-observed')

    def report_state():
        # A fixed transient service is the product's singleton ownership
        # boundary. No window title or process-name census supplies identity.
        def absent():
            return not user('list-units', '--all', '--plain', '--no-legend', reporter)
        missing = {'ActiveState': 'inactive', 'MainPID': '0', 'InvocationID': ''}
        if absent():
            return missing
        raw = user('show', reporter, '--property=ActiveState,MainPID,InvocationID')
        values = dict(line.split('=', 1) for line in raw.splitlines())
        guest.require(set(values) == {'ActiveState', 'MainPID', 'InvocationID'}
                      and values['MainPID'].isdigit(), 'extension:failure-report-service-state')
        return values

    def report(operation='read', value=''):
        state = report_state()
        if state['ActiveState'] != 'active' or state['MainPID'] == '0':
            guest.require(operation == 'read', 'extension:failure-report-not-active')
            return False
        pid = int(state['MainPID'])
        process = Path('/proc') / str(pid)
        guest.require(process.stat().st_uid == child, 'extension:failure-report-wrong-user')
        started = (process / 'stat').read_text().rsplit(')', 1)[1].split()[19]
        result = json.loads(manager._run_command(account, ('/usr/bin/python3', '-B', '-c',
            REPORT_UI, ui_support, str(pid), operation, value),
            require_live=True, timeout=30).stdout)
        if operation != 'close':
            guest.require(report_state() == state and process.stat().st_uid == child
                          and (process / 'stat').read_text().rsplit(')', 1)[1].split()[19] == started,
                          'extension:failure-report-replaced')
        return result if result.get('ready') or operation == 'close' else False

    @contextmanager
    def unavailable_display():
        identity = user_identity()
        values = dict(line.split('=', 1) for line in user('show-environment').splitlines()
                      if '=' in line)
        saved = {key: values[key] for key in ('DISPLAY', 'WAYLAND_DISPLAY') if key in values}
        guest.require(any(saved.values()), 'extension:failure-no-original-display')
        user('unset-environment', 'DISPLAY', 'WAYLAND_DISPLAY')
        try:
            yield
        finally:
            guest.require(user_identity() == identity, 'extension:failure-display-manager-replaced')
            current = dict(line.split('=', 1) for line in user('show-environment').splitlines()
                           if '=' in line)
            guest.require(not {'DISPLAY', 'WAYLAND_DISPLAY'}.intersection(current),
                          'extension:failure-display-environment-changed')
            user('set-environment', *(key + '=' + value for key, value in saved.items()))
            restored = dict(line.split('=', 1) for line in user('show-environment').splitlines()
                            if '=' in line)
            guest.require({key: restored[key] for key in ('DISPLAY', 'WAYLAND_DISPLAY')
                           if key in restored} == saved, 'extension:failure-display-not-restored')

    @contextmanager
    def native_error():
        path = manager.installation / 'extension.js'
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
        identity = os.fstat(fd)
        guest.require(stat.S_ISREG(identity.st_mode) and identity.st_uid == identity.st_gid == 0
                      and identity.st_nlink == 1 and identity.st_size < 262144,
                      'extension:failure-payload-owner')
        original = os.read(fd, identity.st_size + 1)
        fault = b'export default class Extension { enable() { throw new Error("onpc-owned-native-fault"); } disable() {} }\n'
        def write(value):
            os.lseek(fd, 0, os.SEEK_SET)
            guest.require(os.write(fd, value) == len(value), 'extension:failure-payload-short-write')
            os.ftruncate(fd, len(value))
            os.fsync(fd)
        try:
            write(fault)
            record('owned-fault', {'device': identity.st_dev, 'inode': identity.st_ino,
                                  'original_sha256': hashlib.sha256(original).hexdigest()})
            yield
        finally:
            try:
                current = path.lstat()
                guest.require((current.st_dev, current.st_ino, current.st_uid, current.st_gid,
                               current.st_mode, current.st_nlink) ==
                              (identity.st_dev, identity.st_ino, identity.st_uid, identity.st_gid,
                               identity.st_mode, identity.st_nlink)
                              and path.read_bytes() == fault, 'extension:failure-payload-replaced')
                write(original)
                os.utime(fd, ns=(identity.st_atime_ns, identity.st_mtime_ns))
                guest.require(path.read_bytes() == original, 'extension:failure-payload-not-restored')
                record('owned-restoration', {'exact_payload_restored': True})
            finally:
                os.close(fd)

    def healthy():
        return shell.info().get('state') == 1 and shell.enabled()

    def no_enable(events, since):
        guest.require(not attempts(events.since(since)), 'extension:failure-automatic-enable')

    def preserved():
        guest.require(state_digest(child) == snapshot, 'extension:failure-child-policy-changed')
        for role in ('other', 'parent'):
            guest.require(state_digest(accounts[role]) == prepared['other_accounts'][role],
                          'extension:failure-other-account-changed')
        guest.require(native_choices(manager, accounts['other']) == prepared['other_child_choices'],
                      'extension:failure-other-child-extension-changed')

    child_events_before = {(row['segment'], row['sequence']) for row in BrokerEvents.read('child')}

    def no_submission():
        rows = [row for row in BrokerEvents.read('child')
                if (row['segment'], row['sequence']) not in child_events_before]
        guest.require(not any(row['event'].startswith('feedback-transport.')
                              or row['event'] == 'feedback.002' for row in rows),
                      'extension:failure-report-sent-without-send')

    try:
        shell = observe()
        guest.require(not store.load(child)['parent_control_enabled'] and
                      shell.info().get('state') == 6 and shell.info().get('enabled') is False,
                      'extension:failure-initial-not-never-loaded')
        accepted(call(accounts['parent'], 'GetPreferences', '(u)', (child,)))
        identity = invocation()
        events = BrokerEvents(accepted(call(accounts['parent'], 'GetStartupTimings'))[0])
        grant(child, 3600)
        with native_error():
            with unavailable_display():
                preferences = store.load(child)
                store.save(child, {**preferences, 'parent_control_enabled': True})
                snapshot = state_digest(child)
                interface = 'org.freedesktop.Accounts.User'
                language = account_property(child, interface, 'Language')
                try:
                    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                        f'/org/freedesktop/Accounts/User{child}', interface, 'SetLanguage', 's',
                        'en_US.UTF-8' if language != 'en_US.UTF-8' else 'zh_CN.UTF-8'])
                finally:
                    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                        f'/org/freedesktop/Accounts/User{child}', interface, 'SetLanguage', 's', language])
                wait(lambda: shell.info().get('state') == 3 and shell.call(SHELL, PATH, INTERFACE,
                     'GetExtensionErrors', '(s)', (UUID,), '(as)'), 'native-error-not-observed')
                failed_at = time.monotonic()
                time.sleep(4)
                guest.require(invocation() == identity and report_state()['MainPID'] == '0',
                              'extension:failure-report-not-deferred')
                no_enable(events, failed_at)
            first = wait(report, 'deferred-report-not-visible')
            guest.require(first['reports'] == 1 and not first['success'],
                          'extension:failure-report-count-or-submission')
            draft = 'Owned extension failure draft; keep this text.'
            report('edit', draft)
            edited = wait(lambda: (value if draft in json.dumps(value['document']) else False)
                          if (value := report()) else False, 'edited-draft-not-visible')
            for _ in range(2):
                manager._run_as(account, 'gnome-extensions', 'disable', '--quiet', UUID)
                manager._run_as(account, 'gnome-extensions', 'enable', '--quiet', UUID)
            wait(lambda: shell.info().get('state') == 3, 'repeated-native-error')
            time.sleep(3)
            guest.require(report() == edited, 'extension:failure-repeat-overwrote-draft')
            with isolated_broker_for_extension_faults():
                guest.require(report() == edited, 'extension:failure-stopped-broker-lost-draft')
            guest.require(invocation() != identity, 'extension:failure-broker-not-restarted')
            events = BrokerEvents(accepted(call(accounts['parent'], 'GetStartupTimings'))[0])
            restarted = time.monotonic()
            time.sleep(5)
            guest.require(report() == edited and shell.info().get('state') == 3,
                          'extension:failure-restarted-broker-overwrote-draft')
            no_enable(events, restarted)
            preserved()
            no_submission()
            report('close')
            wait(lambda: report_state()['MainPID'] == '0', 'report-close-not-finished')
            record('native-error-report', {'actual_gnome_error': True, 'broker_available': True,
                   'deferred_until_display_returned': True, 'one_report': True,
                   'edited_draft_survived_repeated_error_and_restart': True, 'send_selected': False})

        # The original source is back, but GNOME caches imports for a Shell
        # lifetime. Renew the session before the explicit parent recovery.
        logout()
        guest.prepare_activation_greeter()
        shell = observe()
        accepted(call(accounts['parent'], 'RecoverChildExtension', '(u)', (child,)))
        wait(healthy, 'parent-recovery')
        began = time.monotonic()
        manager._run_as(account, 'gnome-extensions', 'disable', '--quiet', UUID)
        wait(lambda: healthy() and attempts(events.since(began)), 'monitor-not-rearmed')
        recovered_at = time.monotonic()
        bus_id = shell.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                            'org.freedesktop.DBus', 'GetId', '()', (), '(s)')
        owner = user_identity()
        automatic_login(False)
        guest.require(user_identity() == owner and child_session(child) is not None,
                      'extension:failure-crash-fixture-replaced')
        guest.require(time.monotonic() - recovered_at < 60, 'extension:failure-crash-too-late')
        crash_at = time.monotonic()
        guest.run(['systemctl', 'stop', user_unit], timeout=60)
        wait(shell.bus.is_closed, 'whole-bus-loss-not-delivered', timeout=30)
        lost_at = time.monotonic()
        guest.require(lost_at - recovered_at < 60, 'extension:failure-bus-loss-outside-crash-window')
        wait(lambda: child_session(child) is None, 'crashed-session-retained')
        guest.require(guest.run(['systemctl', 'show', user_unit, '--property=ActiveState',
                                '--value']) == 'inactive', 'extension:failure-user-manager-not-stopped')
        # The stopped manager may leave its old socket pathname. A separate
        # public session avoids treating that stale socket as a live transport.
        manager._run_as(account, 'dbus-run-session', '--', 'gsettings', 'set',
                        'org.gnome.shell', 'disable-user-extensions', 'true')
        guest.require(manager._run_as(account, 'dbus-run-session', '--', 'gsettings', 'get',
                      'org.gnome.shell', 'disable-user-extensions').stdout.strip() == 'true',
                      'extension:failure-offline-global-disable-not-saved')
        automatic_login(True)
        guest.prepare_activation_greeter()
        shell = observe()
        guest.require(shell.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                      'org.freedesktop.DBus', 'GetId', '()', (), '(s)') != bus_id,
                      'extension:failure-bus-not-renewed')
        held = time.monotonic()
        until = held + 35
        while time.monotonic() < until:
            guest.require(not shell.enabled() and shell.info().get('state') != 1,
                          'extension:failure-crash-hold-lost')
            time.sleep(.5)
        no_enable(events, crash_at)
        guest.require(not any(row['event'] == 'extension-manager.command'
                              and row['fields']['tool'] == 'other'
                              for _stamp, row in events.since(crash_at)),
                      'extension:failure-bus-loss-report-attempt')
        guest.require(report_state()['MainPID'] == '0', 'extension:failure-bus-loss-reported')
        no_submission()
        accepted(call(accounts['parent'], 'RecoverChildExtension', '(u)', (child,)))
        wait(healthy, 'crash-explicit-parent-recovery')
        began = time.monotonic()
        manager._run_as(account, 'gnome-extensions', 'disable', '--quiet', UUID)
        wait(lambda: healthy() and attempts(events.since(began)), 'crash-monitor-not-rearmed')
        preserved()
        quiet = time.monotonic()
        logout()
        time.sleep(3)
        guest.require(not any(row['event'] == 'extension-manager.command'
                              and row['fields']['tool'] == 'other'
                              for _stamp, row in events.since(quiet)),
                      'extension:failure-ordinary-logout-reported')
        no_submission()
        record('crash-window', {'whole_bus_loss_after_recovery_seconds': round(crash_at - recovered_at, 3),
               'bus_close_observed_after_recovery_seconds': round(lost_at - recovered_at, 3),
               'old_bus_closed': True, 'new_bus': True, 'replacement_globally_disabled': True,
               'hold_seconds': 35, 'automatic_enable_commands': 0,
               'explicit_parent_recovered': True, 'monitor_rearmed': True,
               'bus_loss_and_ordinary_logout_quiet': True, 'send_events': 0,
               'extension_crash_attribution': False})
    finally:
        for observer in reversed(observers):
            observer.close()


if __name__ == '__main__':
    guest.require(sys.argv[1:] == ['prepare'], 'extension:arguments')
    prepare()
