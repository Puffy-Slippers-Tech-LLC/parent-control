"""Finite ScreenSaver reply/availability faults in system-282's owned history.

The public lock setting gates GNOME's competing automatic action. Reply faults
restore it before forwarding; an outage holds it until declared recovery.
The synchronous user_command owns the proxy until restoration.
"""

import json
import os
from pathlib import Path
import sys
import time


def proxy(directory, status):
    from gi.repository import Gio, GLib

    name = 'org.gnome.ScreenSaver'
    path = '/org/gnome/ScreenSaver'
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def owner(bus_name):
        return connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'GetNameOwner', GLib.Variant('(s)', (bus_name,)),
            GLib.VariantType.new('(s)'), Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]

    native = owner('org.gnome.Shell.ScreenShield')
    assert native == owner('org.gnome.Shell')
    original = owner(name)
    began = time.monotonic()
    loop = GLib.MainLoop()
    mode, serial, held, forwarded = None, 0, None, False
    rejected = 0
    settings = Gio.Settings.new('org.gnome.desktop.lockdown')
    key = 'disable-lock-screen'
    assert settings.is_writable(key) and not settings.get_boolean(key)
    native_paused = False

    def record(event, **fields):
        data = json.dumps(dict(event=event, serial=serial, monotonic=time.monotonic(),
                               **fields)).encode() + b'\n'
        assert os.fstat(status).st_size + len(data) < 16384
        assert os.write(status, data) == len(data)

    def native_action(paused):
        nonlocal native_paused
        assert settings.get_boolean(key) == native_paused
        if paused:
            # Publish ownership before changing the public setting, so the
            # enclosing command can restore it even after a proxy failure.
            record('native-action-pausing', mode=mode)
        assert settings.set_boolean(key, paused)
        Gio.Settings.sync()
        native_paused = paused
        assert settings.get_boolean(key) == paused
        record('native-action-paused' if paused else 'native-action-restored', mode=mode)

    def method(bus, sender, object_path, interface, member, parameters, invocation):
        nonlocal held, forwarded, rejected, mode
        retry = False
        assert owner('org.gnome.Shell.ScreenShield') == native
        if member == 'Lock' and sender == native:
            record('requested', mode=mode)
        if member == 'Lock' and mode in ('transient', 'renewal', 'outage') and sender == native:
            if mode in ('renewal', 'outage') or rejected == 0:
                rejected += 1
                record('unavailable', mode=mode)
                invocation.return_dbus_error('org.freedesktop.DBus.Error.Failed',
                                             'Temporary lock unavailability')
                return
            # Only the real retry restores availability and the competing
            # native action. A service restart cannot supply a false pass.
            record('retried', mode=mode)
            native_action(False)
            mode = None
            retry = True
        hold = member == 'Lock' and mode in ('delayed', 'missing') and sender == native
        if hold:
            assert held is None and native_paused
            held, forwarded = invocation, False
            record('captured', mode=mode, sender=sender)
            # The native dispatcher calls ScreenShield directly and can win
            # expiry before the product issues its D-Bus call. Gate that action
            # with a supported setting, then restore real locking before this
            # actual request is forwarded. No deadline or product code changes.
            native_action(False)

        def completed(bus, result):
            nonlocal forwarded
            try:
                value = bus.call_finish(result)
                if retry:
                    record('retry-native-complete')
                if hold:
                    forwarded = True
                    record('native-complete', mode=mode)
                else:
                    invocation.return_value(value)
            except GLib.Error as error:
                invocation.return_gerror(error)
                record('native-error')

        connection.call(native, path, name, member, parameters, None,
                        Gio.DBusCallFlags.NONE, 10000, None, completed)

    def guarded_method(*arguments):
        try:
            method(*arguments)
        except BaseException:
            os._exit(1)

    info = Gio.DBusNodeInfo.new_for_xml('''<node><interface name="org.gnome.ScreenSaver">
      <method name="Lock"/><method name="GetActive"><arg type="b" direction="out"/></method>
      <method name="SetActive"><arg type="b" direction="in"/></method>
      <method name="GetActiveTime"><arg type="u" direction="out"/></method>
      <signal name="ActiveChanged"><arg type="b"/></signal><signal name="WakeUpScreen"/>
    </interface></node>''')
    registration = connection.register_object(path, info.interfaces[0], guarded_method, None, None)
    subscription = connection.signal_subscribe(native, name, None, path, None,
        Gio.DBusSignalFlags.NONE,
        lambda bus, sender, object_path, interface, signal, value:
            bus.emit_signal(None, path, name, signal, value))
    result = connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
        'org.freedesktop.DBus', 'RequestName', GLib.Variant('(su)', (name, 2 | 4)),
        GLib.VariantType.new('(u)'), Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    assert result == 1 and owner(name) == connection.get_unique_name()
    record('ready', native=native, original=original, proxy=connection.get_unique_name())
    print('onpc-lock-service-ready', flush=True)

    def control():
        nonlocal serial, mode, held, forwarded, rejected
        assert time.monotonic() < began + 1800
        assert owner(name) == connection.get_unique_name()
        assert owner('org.gnome.Shell.ScreenShield') == native
        try:
            descriptor = os.open('control.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        except FileNotFoundError:
            return GLib.SOURCE_CONTINUE
        with os.fdopen(descriptor) as stream:
            value = json.load(stream)
        if value['serial'] == serial:
            return GLib.SOURCE_CONTINUE
        assert value['serial'] == serial + 1
        serial = value['serial']
        action = value['action']
        if action in ('delayed', 'missing', 'transient', 'renewal', 'outage'):
            assert held is None
            mode = action
            rejected = 0
            native_action(True)
        elif action == 'available':
            assert mode in ('renewal', 'outage') and rejected > 0
            native_action(False)
            mode = None
        elif action == 'release':
            assert mode == 'delayed' and held is not None and forwarded
            held.return_value(GLib.Variant('()', ()))
            held, mode = None, None
        elif action == 'finish':
            loop.quit()
        else:
            raise AssertionError('lock-reply:control')
        record(action)
        return GLib.SOURCE_CONTINUE

    # Exceptions in a GLib callback must stop the owned process, not strand it.
    def tick():
        try:
            return control()
        except BaseException:
            os._exit(1)

    GLib.timeout_add(100, tick)
    try:
        loop.run()
    finally:
        if native_paused:
            native_action(False)
        assert owner(name) == connection.get_unique_name()
        connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'ReleaseName', GLib.Variant('(s)', (name,)),
            None, Gio.DBusCallFlags.NONE, 5000, None)
        connection.signal_unsubscribe(subscription)
        connection.unregister_object(registration)
        connection.close_sync(None)


def records():
    from system_graphical_expiry import FIXTURE
    path = FIXTURE / 'lock-reply' / 'status.jsonl'
    raw = path.read_bytes()
    assert len(raw) < 16384
    return [json.loads(line) for line in raw.splitlines(keepends=True) if line.endswith(b'\n')]


def control(action):
    from system_graphical_expiry import FIXTURE, wait_for
    directory = FIXTURE / 'lock-reply'
    path = directory / 'control.json'
    serial = json.loads(path.read_text())['serial'] + 1 if path.exists() else 1
    pending = directory / 'control.pending'
    with pending.open('x') as stream:
        os.fchmod(stream.fileno(), 0o644)
        json.dump(dict(serial=serial, action=action), stream)
    pending.replace(path)
    wait_for(lambda: any(row['event'] == action and row['serial'] == serial for row in records()),
             'expiry:lock-reply-control', timeout=15)


def serve():
    import system_guest as guest
    from system_graphical_expiry import FIXTURE, identities
    from system_kiosk_confinement import user_command
    import pwd

    guest.guard()
    child = pwd.getpwuid(identities()['child'])
    setting = ['/usr/bin/gsettings', 'get', 'org.gnome.desktop.lockdown', 'disable-lock-screen']
    guest.require(user_command(child, setting).strip() == b'false',
                  'expiry:lock-reply-initial-lock-setting')
    user_command(child, ['/usr/bin/gdbus', 'call', '--session', '--dest',
        'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver',
        '--method', 'org.gnome.ScreenSaver.GetActive'])
    directory = FIXTURE / 'lock-reply'
    directory.mkdir(mode=0o755)
    # The enclosing fixture remains root-private. Only this inherited directory
    # fd lets the child read the root-written controls, even under umask 077.
    directory.chmod(0o755)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    status_fd = os.open(directory / 'status.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        def output(data, stream):
            if stream == 'stdout':
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
        user_command(child, ['/usr/bin/python3', '-I', '-c', Path(__file__).read_text(),
                             'proxy', str(directory_fd), str(status_fd)],
                     timeout=1830, pass_fds=(directory_fd, status_fd), on_output=output)
    finally:
        os.close(directory_fd)
        os.close(status_fd)
        lock_setting = user_command(child, setting).strip()
        guest.require(lock_setting in (b'true', b'false'), 'expiry:lock-reply-lock-setting')
        if lock_setting == b'true':
            gate = [row for row in records() if row['event'] in (
                'native-action-pausing', 'native-action-paused', 'native-action-restored')]
            guest.require(gate and gate[-1]['event'] != 'native-action-restored',
                          'expiry:lock-reply-unowned-lock-setting')
            user_command(child, ['/usr/bin/gsettings', 'set', 'org.gnome.desktop.lockdown',
                                 'disable-lock-screen', 'false'])
        guest.require(user_command(child, setting).strip() == b'false',
                      'expiry:lock-reply-lock-setting-not-restored')
        # Name loss terminates GNOME's original facade. Reactivate normally;
        # never signal or adopt a replacement process or require its old PID.
        user_command(child, ['/usr/bin/gdbus', 'call', '--session', '--dest',
            'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver',
            '--method', 'org.gnome.ScreenSaver.GetActive'])
        observed = json.loads(user_command(child, ['/usr/bin/busctl', '--user', '--json=short',
            'call', 'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
            'GetNameOwner', 's', 'org.gnome.Shell.ScreenShield']).decode())['data'][0]
        ready = next(row for row in records() if row['event'] == 'ready')
        guest.require(observed == ready['native'], 'expiry:lock-reply-native-owner-changed')
        with (directory / 'restored').open('x') as stream:
            stream.write('normal-facade-active; same-native-owner\n')
    print('onpc-lock-service-restored', flush=True)


def history(command, value, path, accounts):
    import system_guest as guest
    from system_graphical_expiry import LIMITS, account_property, grant, wait_for, installed_manager
    from system_extension_monitor import BrokerEvents

    child = accounts['child']
    # Load the installed package through its existing scoped loader before
    # reusing the structured-event decoder in a fresh command process.
    installed_manager()
    if command == 'reply-missing-wait':
        guest.require(value['grants'] == 3 and not value.get('reply_timeout_observed'),
                      'expiry:lock-reply-timeout-order')
        wait_for(lambda: any(row['event'] == 'child.lock-failed'
                            and row not in value['lock_log_before']
                            for row in BrokerEvents.read('child')),
                 'expiry:lock-reply-timeout-not-observed', timeout=40)
        value['reply_timeout_observed'] = True
        path.write_text(json.dumps(value))
        return {'completed': True}
    sequence = ('reply-delayed-arm', 'reply-delayed-recovery',
                'reply-missing-arm', 'reply-missing-recovery', 'reply-complete')
    index = value['grants']
    guest.require(index < len(sequence) and command == sequence[index], 'expiry:lock-reply-order')
    if command.endswith('-arm'):
        mode = 'delayed' if index == 0 else 'missing'
        value['lock_log_before'] = [row for row in BrokerEvents.read('child')
                                    if row['event'] in ('child.locked', 'child.lock-failed')]
        control(mode)
        value['reply_expiry'] = grant(child, 180)
        value['reply_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        result = {'remaining_seconds': value['reply_expiry'] - time.time()}
    elif command.endswith('-recovery'):
        mode = 'delayed' if index == 1 else 'missing'
        rows = records()
        captured = [row for row in rows if row['event'] == 'captured' and row['mode'] == mode]
        completed = [row for row in rows if row['event'] == 'native-complete' and row['mode'] == mode]
        paused = [row for row in rows if row['event'] == 'native-action-paused' and row['mode'] == mode]
        restored = [row for row in rows if row['event'] == 'native-action-restored' and row['mode'] == mode]
        guest.require(len(captured) == 1, 'expiry:lock-reply-request-not-captured')
        guest.require(len(completed) == 1, 'expiry:lock-reply-native-call-not-completed')
        guest.require(not any(row['event'] == 'native-error' for row in rows),
                      'expiry:lock-reply-native-call-failed')
        guest.require(captured[0]['monotonic'] <= completed[0]['monotonic'],
                      'expiry:lock-reply-native-completion-before-request')
        guest.require(len(paused) == len(restored) == 1
                      and paused[0]['monotonic'] <= captured[0]['monotonic']
                      <= restored[0]['monotonic'] <= completed[0]['monotonic'],
                      'expiry:lock-reply-native-action-order')
        guest.require(time.time() >= value['reply_expiry'],
                      'expiry:lock-reply-original-expiry-not-reached')
        guest.require(account_property(child, LIMITS, 'ActiveExtension') == value['reply_grant'],
                      'expiry:lock-reply-original-grant-changed')
        def new_events():
            before = value['lock_log_before']
            return [row for row in BrokerEvents.read('child')
                    if row['event'] in ('child.locked', 'child.lock-failed') and row not in before]
        if mode == 'delayed':
            guest.require(not new_events(), 'expiry:lock-reply-completed-before-release')
            control('release')
            wait_for(lambda: any(row['event'] == 'child.locked' for row in new_events()),
                     'expiry:lock-reply-ack-not-observed', timeout=15)
        else:
            guest.require(value.get('reply_timeout_observed') is True
                          and any(row['event'] == 'child.lock-failed' for row in new_events()),
                          'expiry:lock-reply-timeout-not-observed')
        value.setdefault('reply_histories', []).append(mode)
        deadline = grant(child, 1200)
        result = {'remaining_seconds': deadline - time.time()}
    else:
        guest.require(value.get('reply_histories') == ['delayed', 'missing'],
                      'expiry:lock-reply-history-incomplete')
        value['complete'] = True
        result = {'completed': True}
    value['grants'] += 1
    path.write_text(json.dumps(value))
    return result


def retry_history(command, value, path, accounts):
    """One real transient failure and one renewal cancelling stale retries."""
    import system_guest as guest
    from system_graphical_expiry import LIMITS, account_property, grant, wait_for, installed_manager

    child = accounts['child']
    installed_manager()
    sequence = ('retry-renew-arm', 'retry-renew', 'retry-renew-available', 'retry-renew-check',
                'retry-arm', 'retry-recovery', 'retry-complete')
    index = value['grants']
    guest.require(index < len(sequence) and command == sequence[index], 'expiry:lock-retry-order')
    if command in ('retry-renew-arm', 'retry-arm'):
        control('renewal' if index == 0 else 'transient')
        value['retry_expiry'] = grant(child, 180)
        value['retry_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        result = {'remaining_seconds': value['retry_expiry'] - time.time()}
    elif command == 'retry-renew':
        wait_for(lambda: any(row['event'] == 'unavailable' and row['mode'] == 'renewal'
                             for row in records()), 'expiry:lock-retry-renewal-fault', timeout=210)
        grant(child, 1200)
        result = {'completed': True}
    elif command == 'retry-renew-available':
        # The controller has independently read the child's renewed allowance
        # through the public UI API. Product logs are best-effort diagnostics.
        control('available')
        value['renew_available_at'] = time.monotonic()
        value['renew_request_count'] = len([row for row in records() if row['event'] == 'requested'])
        result = {'completed': True}
    elif command == 'retry-renew-check':
        guest.require(time.time() > value['retry_expiry'] + 15
                      and time.monotonic() > value['renew_available_at'] + 15,
                      'expiry:lock-retry-renewal-window-not-crossed')
        guest.require(len([row for row in records() if row['event'] == 'requested'])
                      == value['renew_request_count'], 'expiry:lock-retry-stale-request')
        value['renewal_cancelled_retry'] = True
        result = {'completed': True}
    elif command == 'retry-recovery':
        rows = records()
        faults = [row for row in rows if row['event'] == 'unavailable' and row.get('mode') == 'transient']
        retries = [row for row in rows if row['event'] == 'retried']
        completions = [row for row in rows if row['event'] == 'retry-native-complete']
        guest.require(len(faults) == len(retries) == 1
                      and len(completions) == 1
                      and faults[0]['monotonic'] < retries[0]['monotonic']
                      <= completions[0]['monotonic']
                      and not any(row['event'] == 'native-error' for row in rows),
                      'expiry:lock-retry-real-boundary-not-retried')
        guest.require(account_property(child, LIMITS, 'ActiveExtension') == value['retry_grant']
                      and time.time() >= value['retry_expiry'], 'expiry:lock-retry-original-grant')
        value['transient_recovered'] = True
        result = {'remaining_seconds': grant(child, 1200) - time.time()}
    else:
        guest.require(value.get('renewal_cancelled_retry') and value.get('transient_recovered'),
                      'expiry:lock-retry-incomplete')
        value['complete'] = True
        result = {'completed': True}
    value['grants'] += 1
    path.write_text(json.dumps(value))
    return result


def outage_history(command, value, path, accounts):
    """Characterize unavailable locking, without accepting absent protection."""
    import system_guest as guest
    from system_graphical_expiry import LIMITS, account_property, grant
    from system_assertions import accepted, call

    child = accounts['child']
    sequence = ('outage-arm', 'outage-revoke', 'outage-restore',
                'outage-recovery', 'outage-complete')
    index = value['grants']
    guest.require(index < len(sequence) and command == sequence[index], 'expiry:lock-outage-order')
    if command == 'outage-arm':
        control('outage')
        value['outage_expiry'] = grant(child, 180)
        value['outage_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        result = {'remaining_seconds': value['outage_expiry'] - time.time()}
    elif command in ('outage-revoke', 'outage-restore'):
        rows = records()
        paused = [row for row in rows if row['event'] == 'native-action-paused'
                  and row['mode'] == 'outage']
        refused = [row for row in rows if row['event'] == 'unavailable'
                   and row['mode'] == 'outage']
        guest.require(len(paused) == 1 and refused
                      and paused[0]['monotonic'] <= refused[0]['monotonic']
                      and not any(row['event'] in ('available', 'native-action-restored') for row in rows)
                      and time.time() >= value['outage_expiry'] + 15,
                      'expiry:lock-outage-not-spanning-expiry')
        guest.require(account_property(child, LIMITS, 'DailyLimit') == 0,
                      'expiry:lock-outage-policy-changed')
        if command == 'outage-revoke':
            guest.require(account_property(child, LIMITS, 'ActiveExtension') == value['outage_grant'],
                          'expiry:lock-outage-original-grant-changed')
            value['outage_revoked_at'] = time.monotonic()
            accepted(call(accounts['parent'], 'RevokeOneTimeGrant', '(u)', (child,)))
            guest.require(account_property(child, LIMITS, 'ActiveExtension')[1] == 0,
                          'expiry:lock-outage-revoke-not-observed')
            result = {'completed': True}
        else:
            guest.require(time.monotonic() >= value['outage_revoked_at'] + 15
                          and account_property(child, LIMITS, 'ActiveExtension')[1] == 0,
                          'expiry:lock-outage-not-spanning-revocation')
            # The host has independently submitted/read original work after
            # each exhausted boundary. Record that unsupported result explicitly;
            # restoring availability can never turn it into a protection pass.
            value['outage_protection'] = 'unsupported-input-remained-usable'
            value['outage_recovery_expiry'] = grant(child, 1200)
            control('available')
            result = {'remaining_seconds': value['outage_recovery_expiry'] - time.time()}
    elif command == 'outage-recovery':
        guest.require(value.get('outage_protection') == 'unsupported-input-remained-usable',
                      'expiry:lock-outage-characterization-missing')
        result = {'remaining_seconds': value['outage_recovery_expiry'] - time.time()}
    else:
        guest.require(value.get('outage_protection') == 'unsupported-input-remained-usable'
                      and any(row['event'] == 'available' for row in records()),
                      'expiry:lock-outage-incomplete')
        value['complete'] = True
        result = {'completed': True}
    value['grants'] += 1
    path.write_text(json.dumps(value))
    return result


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'proxy':
        proxy(int(sys.argv[2]), int(sys.argv[3]))
    else:
        import system_guest as guest
        guest.guard()
        guest.require(len(sys.argv) == 2 and sys.argv[1] in ('serve', 'finish'),
                      'expiry:lock-reply-arguments')
        if sys.argv[1] == 'serve':
            serve()
        else:
            control('finish')
