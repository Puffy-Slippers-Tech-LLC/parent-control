"""Finite installed engineering fault injection, separate from public acceptance.

The parent process runs the installed production broker and adapters. Its one
owned child observes public native estimates and lock signals as Riley. No
product state or synthetic grant from this probe earns customer credit.
"""
from contextlib import contextmanager, redirect_stdout
import json
import logging
import os
from pathlib import Path
import pwd
import select
import subprocess
import sys
import time

diagnostic = {}
OBSERVATION_SECONDS = 300


@contextmanager
def hold_service_transaction(child, parent):
    from system_assertions import accepted, call
    from system_caller import PersistentCaller, TextAgent
    from system_guest import BUS

    other_parent = pwd.getpwnam(control.ACCOUNTS['second-parent']).pw_uid
    # A qualified, unanswered challenge holds the real service's policy lock.
    # The service can still answer deadline queries from the live extension.
    with PersistentCaller(child) as caller, TextAgent(caller) as agent:
        caller.send({'kind': 'call', 'method': 'RequestOwnAccess', 'signature': '(uub)',
                     'args': (parent, 300, False),
                     'timeout_ms': (OBSERVATION_SECONDS + 60) * 1000})
        try:
            agent.prompt(parent, other_parent)
            busy = call(child, 'GetOwnSessionAllowsSoftApps')
            control.require(busy.get('error') == BUS + '.Error.Busy',
                            'engineering-service-transaction-not-held')
            yield
            readable, _, _ = select.select([caller.child.stdout], [], [], 0)
            control.require(not readable and not caller.pending,
                            'engineering-service-transaction-ended-early')
        finally:
            agent.close()
            reply = accepted(caller.receive(timeout=15))
            control.require(reply[1] in ('denied', 'cancelled') and reply[2] == 0,
                            'engineering-service-request-not-cancelled')


def observer(deadline):
    import json
    import os
    from pathlib import Path
    import sys
    import time
    import gi
    from gi.repository import Gio, GLib

    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    loop = GLib.MainLoop()
    count = 0
    failed = False
    last_call = None
    timer = 'org.freedesktop.MalcontentTimer1'
    timer_path = '/org/freedesktop/MalcontentTimer1'
    estimate_interface = timer + '.Child'
    estimate_busy = estimate_interface + '.Error.Busy'
    estimate_args = GLib.Variant('(s)', ('login-session',))
    pending = 0
    acknowledgement = None
    last_periodic_estimate = None

    def remaining_ms():
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining < 1:
            raise TimeoutError('disable-observer:deadline')
        return remaining

    def call(bus, name, path, interface, method, arguments=None, *,
             flags=Gio.DBusCallFlags.NO_AUTO_START):
        nonlocal last_call
        last_call = interface + '.' + method
        return bus.call_sync(name, path, interface, method, arguments, None, flags,
                             remaining_ms(), None).unpack()

    def emit(event, **value):
        nonlocal count
        count += 1
        if count > 4096:
            raise RuntimeError('disable-observer:bound')
        print(json.dumps(dict(event=event, monotonic_ns=time.monotonic_ns(), **value)), flush=True)

    def identity():
        owner = call(system, 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                     'org.freedesktop.DBus', 'GetNameOwner', GLib.Variant('(s)', (timer,)))[0]
        pid = call(system, 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                   'org.freedesktop.DBus', 'GetConnectionUnixProcessID', GLib.Variant('(s)', (owner,)))[0]
        birth = (Path('/proc') / str(pid) / 'stat').read_text().rpartition(') ')[2].split()[19]
        return [owner, pid, birth]

    def fail(error):
        nonlocal failed
        failed = True
        emit('failure', category=type(error).__name__, operation=last_call,
             remote_error=(Gio.DBusError.get_remote_error(error)
                           if isinstance(error, GLib.Error) else None),
             domain=getattr(error, 'domain', None), code=getattr(error, 'code', None))
        loop.quit()

    # Activate through the actual child's public estimate operation before pinning.
    try:
        call(system, timer, timer_path, estimate_interface, 'GetEstimatedTimes',
             estimate_args, flags=Gio.DBusCallFlags.NONE)
    except GLib.Error as error:
        if Gio.DBusError.get_remote_error(error) != estimate_busy:
            raise
    pinned = identity()

    def acknowledge():
        nonlocal acknowledgement
        if pending or acknowledgement is None:
            return False
        label, acknowledgement = acknowledgement, None
        try:
            if label == 'ready':
                emit('ready', timer_identity=pinned, uid=os.geteuid())
            elif label == 'finish':
                emit('finished')
                loop.quit()
            else:
                emit('boundary', label=label)
        except Exception as error:
            fail(error)
        return False

    def acknowledge_after_reads(label):
        nonlocal acknowledgement
        acknowledgement = label
        # Let queued notifications run before releasing the held state.
        GLib.idle_add(acknowledge)

    def sample(label, *, required=True, after=None):
        nonlocal pending
        pending += 1
        began = time.monotonic_ns()
        delay_ms = 100

        def request():
            try:
                system.call(timer, timer_path, estimate_interface, 'GetEstimatedTimes',
                            estimate_args, None, Gio.DBusCallFlags.NO_AUTO_START,
                            remaining_ms(), None, complete, None)
            except Exception as error:
                fail(error)
            return False

        def complete(bus, result, _data):
            nonlocal pending, last_call, last_periodic_estimate, delay_ms
            try:
                last_call = estimate_interface + '.GetEstimatedTimes'
                observed = estimate = None
                try:
                    observed, estimates = bus.call_finish(result).unpack()
                except GLib.Error as error:
                    if Gio.DBusError.get_remote_error(error) != estimate_busy:
                        raise
                    if required:
                        if delay_ms == 100:
                            emit('estimate-busy', label=label, remote_error=estimate_busy)
                        GLib.timeout_add(min(delay_ms, remaining_ms()), request)
                        delay_ms = min(2 * delay_ms, 1000)
                        return
                    emit('estimate-gap', label=label, remote_error=estimate_busy)
                    last_periodic_estimate = None
                else:
                    if set(estimates) not in (set(), {''}):
                        raise RuntimeError('disable-observer:unexpected-estimate-map')
                    estimate = estimates.get('')
                completed = time.monotonic_ns()
                locked = call(session, 'org.gnome.ScreenSaver', '/org/gnome/ScreenSaver',
                              'org.gnome.ScreenSaver', 'GetActive')[0]
                timer_identity = identity()
                # The native boolean means "limit reached". An empty estimate
                # map represents unrestricted time.
                if (timer_identity != pinned or locked or estimate is not None
                        and (estimate[0] or estimate[2] <= observed)):
                    raise RuntimeError('disable-observer:lock-exhaustion-or-timer-replaced')
                if observed is not None and (required or (estimate,) != last_periodic_estimate):
                    emit('sample', label=label, timer_identity=timer_identity,
                         estimate=list(estimate) if estimate is not None else None,
                         estimate_observed=observed, screensaver_active=locked,
                         read_bounds_ns=[began, completed] if required else None)
                    if not required:
                        last_periodic_estimate = (estimate,)
                pending -= 1
                if after is not None:
                    after()
                if pending == 0 and acknowledgement is not None:
                    GLib.idle_add(acknowledge)
            except Exception as error:
                fail(error)

        request()

    def event(bus, sender, path, interface, signal, parameters, *_unused):
        try:
            if signal == 'ActiveChanged':
                active, = parameters.unpack()
                emit('lock', active=active)
                if active:
                    raise RuntimeError('disable-observer:native-lock')
            elif signal == 'NameOwnerChanged':
                _name, old, new = parameters.unpack()
                emit('timer-owner', old=old, new=new)
                if old != new:
                    raise RuntimeError('disable-observer:timer-replaced')
            else:
                # The public signal deliberately has no payload. Keep its
                # delivery time and query through the actual child identity.
                if parameters.unpack() != ():
                    raise RuntimeError('disable-observer:unexpected-signal-payload')
                emit('estimate-event')
                sample('estimated-times-changed')
        except Exception as error:
            fail(error)

    subscriptions = [
        (session, session.signal_subscribe('org.gnome.ScreenSaver', 'org.gnome.ScreenSaver',
            'ActiveChanged', '/org/gnome/ScreenSaver', None, Gio.DBusSignalFlags.NONE, event)),
        (system, system.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus',
            'NameOwnerChanged', '/org/freedesktop/DBus', timer, Gio.DBusSignalFlags.NONE, event)),
        (system, system.signal_subscribe(timer, timer + '.Child', 'EstimatedTimesChanged',
            timer_path, None, Gio.DBusSignalFlags.NONE, event)),
    ]

    def tick():
        if pending == 0 and acknowledgement is None:
            sample('periodic', required=False)
        return True

    def command(_fd, condition):
        try:
            if condition & GLib.IO_HUP:
                raise RuntimeError('disable-observer:controller-lost')
            label = sys.stdin.readline().strip()
            if label not in ('disable', 'rollback-live-grant', 'rollback-unrestricted',
                             'post-termination-unrestricted', 'preparation-readback-refusal',
                             'restored', 'native-write', 'finish'):
                raise RuntimeError('disable-observer:marker')
            if label == 'native-write':
                # Engineering fault seams deliberately hold every intermediate
                # native state while its async estimate/lock pipeline runs.
                def settled():
                    sample('native-write-window-end', after=lambda: acknowledge_after_reads(label))
                    return False
                sample(label, after=lambda: GLib.timeout_add(1000, settled))
            else:
                sample(label, after=lambda: acknowledge_after_reads(label))
            return label != 'finish'
        except Exception as error:
            fail(error)
            return False

    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_IN | GLib.IO_HUP, command)
    GLib.timeout_add(100, tick)
    def expire():
        fail(TimeoutError('disable-observer:deadline'))
        return False
    GLib.timeout_add(remaining_ms(), expire)
    acknowledge_after_reads('ready')
    sample('ready')
    try:
        if not failed:
            loop.run()
    finally:
        for bus, subscription in subscriptions:
            bus.signal_unsubscribe(subscription)
    if failed:
        raise RuntimeError('disable-observer:failed')


def qualify():
    control.require(os.geteuid() == 0, 'engineering-root-required')
    account = pwd.getpwnam(control.ACCOUNTS['child'])
    administrator = pwd.getpwnam(control.ACCOUNTS['parent'])
    current = control.sessions()
    sessions = [(name, props) for name, props in current.items()
                if props['User'] == str(account.pw_uid) and control.local_graphical(props)]
    control.require(len(sessions) == 1 and sessions[0][1]['Active'] == 'yes'
                    and sessions[0][1]['LockedHint'] == 'no', 'engineering-unlocked-child-required')
    with hold_service_transaction(account.pw_uid, administrator.pw_uid):
        return exercise_transitions(account, administrator)


def exercise_transitions(account, administrator):
    sys.path[:0] = ['/usr/lib/oh-no-parent-control', '/usr/lib/oh-no-parent-control/broker']
    from gi.repository import Gio
    from oh_no_parent_control.core import Broker, BackendFailure, blocked_targets
    from oh_no_parent_control.service import production_dependencies
    from common.oh_no_parent_control_ui.diagnostic_events import record_payload
    dependencies = production_dependencies(Gio.bus_get_sync(Gio.BusType.SYSTEM, None))

    # This standalone broker has no service event-file writer. Retain its
    # validated activation evidence in the existing private failure response,
    # rather than looking for these events in the separate running service.
    extension_events = diagnostic['extension_events'] = []
    diagnostic['extension_events_omitted'] = 0

    class ActivationEvidence(logging.Handler):
        def emit(self, record):
            try:
                value = json.loads(record_payload(record))
                if value['event'] in ('extension-manager.001', 'extension-manager.003',
                                      'extension-manager.command'):
                    return
                extension_events.append(dict(value, monotonic_ns=time.monotonic_ns()))
                while (len(extension_events) > 160
                       or len(json.dumps(extension_events).encode()) > 65536):
                    extension_events.pop(0)
                    diagnostic['extension_events_omitted'] += 1
            except Exception:
                # Diagnostics must not change the original failure or cleanup.
                pass

    extension_logger = logging.getLogger('onpc.extension-manager')
    extension_logger.addHandler(ActivationEvidence())
    extension_logger.setLevel(logging.INFO)
    set_live = dependencies.extensions._set_live

    def observe_live(account, enabled, **options):
        try:
            return set_live(account, enabled, **options)
        except Exception:
            if enabled:
                # Reuse the bounded, read-only settings observer for enable
                # failures too, before rollback conceals the disagreement.
                # A later match never converts this original failure to a pass.
                dependencies.extensions._observe_disable_settings(account)
            raise

    dependencies.extensions._set_live = observe_live
    native = dependencies.accounts
    uid = account.pw_uid
    fields = ('limit_type', 'daily_limit', 'daily_schedule', 'extension', 'filter')

    def snapshot():
        return {name: getattr(native, 'get_' + name)(uid) for name in fields}

    original = snapshot()
    diagnostic['original_native_state'] = original
    preferences = dependencies.preferences.load(uid)
    control.require(original['limit_type'] == 2 and original['daily_limit'] == 0
        and original['extension'][0] + original['extension'][1] > int(time.time()) + 120
        and preferences['parent_control_enabled'] is True, 'engineering-live-grant-required')

    # Correlate the observer's monotonic samples with the validated product
    # events' UTC timestamps, without extra native reads or settling delays.
    diagnostic['clock'] = {'monotonic_ns': time.monotonic_ns(), 'realtime_ns': time.time_ns()}
    native_writes = diagnostic['native_writes'] = []

    def write_started(name):
        record = {'method': name, 'started_monotonic_ns': time.monotonic_ns()}
        native_writes.append(record)
        del native_writes[:-128]
        return record

    class FaultAccounts:
        def __init__(self):
            self.fault = None
            self.fired = False
            self.calls = []
            self.failure_index = None

        def __getattr__(self, name):
            target = getattr(native, name)
            if not name.startswith(('set_', 'get_')):
                return target

            def call(*arguments, **options):
                self.calls.append(name)
                write = write_started(name) if name.startswith('set_') else None
                if self.fault == name + '_after_write' and not self.fired:
                    target(*arguments, **options)
                    if write is not None:
                        write['returned_monotonic_ns'] = time.monotonic_ns()
                    boundary('native-write')
                    self.fired = True
                    self.failure_index = len(self.calls) - 1
                    raise RuntimeError('injected-native-boundary-failure')
                if self.fault == name and not self.fired:
                    self.fired = True
                    self.failure_index = len(self.calls) - 1
                    raise RuntimeError('injected-native-boundary-failure')
                result = target(*arguments, **options)
                if write is not None:
                    write['returned_monotonic_ns'] = time.monotonic_ns()
                    boundary('native-write')
                return result
            return call

    accounts = FaultAccounts()
    broker = Broker(dependencies.config_loader, dependencies.authorizer, accounts,
        dependencies.preferences, dependencies.extensions, dependencies.timer_usage,
        dependencies.application_catalog, dependencies.running_apps)

    def restore(state):
        broker._restore(uid, state['limit_type'], state['daily_limit'], state['filter'],
                        state['extension'], state['daily_schedule'], None)

    events = []
    diagnostic['events'] = events
    deadline = time.monotonic() + OBSERVATION_SECONDS
    process = subprocess.Popen(['/usr/bin/python3', '-I', '-c', probe_source, 'observe', str(deadline)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        bufsize=1, user=account.pw_uid, group=account.pw_gid, extra_groups=(),
        env=control.environment(account))
    pending = b''

    def receive(expected, label=None):
        nonlocal pending
        while True:
            while b'\n' not in pending:
                remaining = deadline - time.monotonic()
                control.require(remaining > 0 and select.select([process.stdout], [], [], remaining)[0],
                                'engineering-observer-deadline')
                chunk = os.read(process.stdout.fileno(), 65536)
                control.require(bool(chunk), 'engineering-observer-exited')
                pending += chunk
                control.require(len(pending) < 512 * 1024, 'engineering-observer-output-bound')
            line, pending = pending.split(b'\n', 1)
            event = json.loads(line)
            events.append(event)
            if event.get('read_bounds_ns') is not None:
                # A delayed reply cannot stand for a state that another
                # controlled write may already have replaced.
                began, completed = event['read_bounds_ns']
                for write in native_writes:
                    if began <= write['started_monotonic_ns'] <= completed:
                        diagnostic.setdefault('required_estimate_gap', {'sample': event, 'write': write})
                        break
            control.require(event['event'] != 'failure' and len(events) <= 4096,
                            'engineering-observer-failed')
            if event['event'] == expected and (label is None or event.get('label') == label):
                return event

    def boundary(label):
        diagnostic['boundary'] = label
        process.stdin.write(label + '\n')
        process.stdin.flush()
        receive('boundary', label)

    def expect_failure(action, fault):
        accounts.fault, accounts.fired, accounts.calls = fault, False, []
        accounts.failure_index = None
        try:
            action()
        except BackendFailure:
            control.require(accounts.fired, 'engineering-wrong-failure')
        else:
            raise RuntimeError('engineering:missing-failure')
        finally:
            accounts.fault = None

    checks = []
    def state_is(expected, label):
        actual = snapshot()
        diagnostic['state_comparison'] = {'check': label, 'expected': expected, 'actual': actual}
        return actual == expected

    try:
        receive('ready')
        control.require('required_estimate_gap' not in diagnostic, 'engineering-estimate-crossed-write')
        broker.set_parent_control(administrator.pw_uid, uid, False, 0)
        disabled = snapshot()
        diagnostic['disabled_native_state'] = disabled
        control.require(disabled['limit_type'] == 0 and disabled['daily_limit'] == 0
            and disabled['extension'] == (0, 0)
            and disabled['filter'] == (False, blocked_targets(preferences, False))
            and disabled['daily_schedule'] == original['daily_schedule'], 'engineering-disable-result')
        boundary('disable')
        checks.append('disable')
        restore(original)
        dependencies.preferences.save(uid, preferences)
        dependencies.extensions.set_enabled(uid, True)
        expect_failure(lambda: broker.set_parent_control(administrator.pw_uid, uid, False, 0), 'set_filter')
        control.require(state_is(original, 'rollback-live-grant') and dependencies.preferences.load(uid) == preferences,
                        'engineering-live-grant-rollback')
        boundary('rollback-live-grant')
        checks.append('rollback-live-grant')

        broker.set_parent_control(administrator.pw_uid, uid, False, 0)
        unrestricted = snapshot()
        expect_failure(lambda: broker._apply(uid, preferences, original['filter'],
            original['extension'], 'engineering', admit=lambda: True), 'set_extension_after_write')
        control.require(state_is(unrestricted, 'rollback-unrestricted'), 'engineering-unrestricted-rollback')
        boundary('rollback-unrestricted')
        checks.append('rollback-unrestricted')

        restore(original)
        broker._restore_after_termination(uid, unrestricted['limit_type'], unrestricted['daily_limit'],
            unrestricted['filter'], unrestricted['extension'], unrestricted['daily_schedule'], 'engineering')
        control.require(state_is(unrestricted, 'post-termination-unrestricted'), 'engineering-post-termination-rollback')
        boundary('post-termination-unrestricted')
        checks.append('post-termination-unrestricted')

        restore(original)
        dependencies.preferences.save(uid, preferences)
        dependencies.extensions.set_enabled(uid, True)
        # Fail the bridge's independent schedule read after the initial snapshot.
        # Arm at its write so the initial state read remains genuine.
        schedule_set = native.set_daily_schedule
        def arm_after_write(*arguments):
            write = write_started('set_daily_schedule')
            schedule_set(*arguments)
            write['returned_monotonic_ns'] = time.monotonic_ns()
            boundary('native-write')
            accounts.fault = 'get_daily_schedule'
        accounts.set_daily_schedule = arm_after_write
        try:
            expect_failure(lambda: broker.set_parent_control(administrator.pw_uid, uid, False, 0),
                           'bridge-readback-armed')
        finally:
            del accounts.set_daily_schedule
        committed_before_failure = accounts.calls[:accounts.failure_index]
        control.require(state_is(original, 'preparation-readback-refusal') and not any(name in committed_before_failure for name in (
            'set_limit_type', 'set_daily_limit', 'set_extension', 'set_filter')),
                        'engineering-preparation-refusal-effects')
        boundary('preparation-readback-refusal')
        checks.append('preparation-readback-refusal')
    finally:
        primary = sys.exc_info()[1]
        if primary is not None:
            diagnostic['primary_failure'] = {'category': type(primary).__name__,
                                              'boundary': diagnostic.get('boundary')}
        accounts.fault = None
        observer_finished = False
        try:
            if primary is not None:
                # A failed observer must not prevent cleanup of real native
                # state. The original failure still prevents acceptance.
                broker._accounts = native
            restore(original)
            dependencies.preferences.save(uid, preferences)
            dependencies.extensions.set_enabled(uid, preferences['parent_control_enabled'])
            restored = state_is(original, 'final-restoration') and dependencies.preferences.load(uid) == preferences
        finally:
            try:
                try:
                    if process.poll() is None:
                        boundary('restored')
                        process.stdin.write('finish\n')
                        process.stdin.flush()
                        receive('finished')
                        observer_finished = True
                finally:
                    stdout, stderr = process.communicate(timeout=10)
                    tail = pending + stdout.encode()
                    for line in tail.splitlines():
                        events.append(json.loads(line))
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=5)
                raise RuntimeError('engineering:observer-cleanup-deadline')
            control.require(observer_finished and process.returncode == 0 and not stderr
                            and not any(event['event'] == 'failure' for event in events),
                            'engineering-observer-result')
        control.require(restored, 'engineering-original-state-not-restored')
    control.require('required_estimate_gap' not in diagnostic, 'engineering-estimate-crossed-write')
    return {'engineering_only': True, 'checks': checks, 'events': events,
            'original_native_state': original, 'original_state_restored': restored,
            'observer_joined': True, 'native_write_observation_ms': 1000,
            'estimate_signals_have_no_payload': True}


if sys.argv[1:2] == ['observe']:
    observer(float(sys.argv[2]))
else:
    try:
        sys.path.insert(0, '/var/tmp/onpc-system-input')
        with redirect_stdout(sys.stderr):
            result = qualify()
        print(json.dumps(result, sort_keys=True))
    except BaseException:
        print(json.dumps({'engineering_failure': diagnostic}, sort_keys=True), file=sys.stderr, flush=True)
        raise
