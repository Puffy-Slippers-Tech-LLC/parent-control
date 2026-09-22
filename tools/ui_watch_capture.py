"""Fixture-owned Mutter monitor capture. No remote-desktop or input interface.

Like the development preview, this is bounded to Mutter 50's ScreenCast API.
The spectator receives only copied frames; this process alone has the private
test bus. Capture failure is diagnostic and never controls pytest.
"""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from ui_watch_transport import Publication, registry, label

CAST = 'org.gnome.Mutter.ScreenCast'
DISPLAY = 'org.gnome.Mutter.DisplayConfig'


class Capture:
    def __init__(self, publication):
        import gi
        gi.require_version('Gst', '1.0')
        gi.require_version('GstApp', '1.0')
        gi.require_version('GstVideo', '1.0')
        from gi.repository import Gio, GLib, Gst, GstVideo
        self.Gio, self.GLib, self.Gst, self.GstVideo = Gio, GLib, Gst, GstVideo
        self.publication = publication
        self.connection = self.cast = self.subscription = self.monitor_subscription = None
        self.pipeline = None
        self.sink = None
        self.started = time.monotonic()
        self.retries = 0
        self.retry_at = 0
        self.stage = 'stream'
        self.generation = 0
        self.display_serial = None
        self.next_display_check = 0
        try:
            runtime = Path(os.environ['XDG_RUNTIME_DIR'])
            if (runtime.parent.parent != Path('/tmp')
                    or not runtime.parent.name.startswith('dogtail-hermetic-')
                    or runtime.resolve() != runtime or runtime.stat().st_uid != os.getuid()
                    or os.environ['PIPEWIRE_RUNTIME_DIR'] != str(runtime)):
                raise ValueError('Capture requires a private test runtime')
            self.runtime = runtime
            version = subprocess.run(['mutter', '--version'], check=True,
                                     capture_output=True, text=True, timeout=3).stdout
            if not version.strip().startswith('mutter 50.'):
                raise ValueError('UI capture requires Mutter 50.x')
            Gst.init(None)
            for factory in ('pipewiresrc', 'videoconvert', 'videoscale', 'appsink'):
                if not Gst.ElementFactory.find(factory):
                    raise RuntimeError(f'Missing GStreamer element: {factory}')
            self.begin()
        except BaseException:
            self.close()
            raise

    def call(self, service, path, interface, method, signature=None, values=()):
        return self.connection.call_sync(
            service, path, interface, method,
            self.GLib.Variant(signature, values) if signature else None, None,
            self.Gio.DBusCallFlags.NO_AUTO_START, 3000, None).unpack()

    def begin(self):
        self.connection = self.Gio.DBusConnection.new_for_address_sync(
            os.environ['DBUS_SESSION_BUS_ADDRESS'],
            self.Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | self.Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.monitor_subscription = self.connection.signal_subscribe(
            DISPLAY, DISPLAY, 'MonitorsChanged', '/org/gnome/Mutter/DisplayConfig', None,
            self.Gio.DBusSignalFlags.NONE, self.monitors_changed)
        serial, monitors, logical, _ = self.call(
            DISPLAY, '/org/gnome/Mutter/DisplayConfig', DISPLAY, 'GetCurrentState')
        if len(monitors) != 1 or len(logical) != 1:
            raise ValueError('Expected the existing single test monitor')
        self.display_serial = serial
        self.next_display_check = time.monotonic() + .25
        self.cast, = self.call(CAST, '/org/gnome/Mutter/ScreenCast', CAST,
                              'CreateSession', '(a{sv})', ({},))
        stream, = self.call(CAST, self.cast, CAST + '.Session', 'RecordMonitor',
                           '(sa{sv})', (monitors[0][0][0], {
                               'cursor-mode': self.GLib.Variant('u', 1)}))
        self.subscription = self.connection.signal_subscribe(
            CAST, CAST + '.Stream', 'PipeWireStreamAdded', stream, None,
            self.Gio.DBusSignalFlags.NONE, self.stream_added)
        self.call(CAST, self.cast, CAST + '.Session', 'Start')
        self.generation += 1
        print(f'UI capture stream started: generation={self.generation}', flush=True)

    def stream_added(self, _connection, _sender, _path, _interface, _signal, parameters):
        try:
            node, = parameters.unpack()
            objects = json.loads(subprocess.run(
                ['pw-dump'], check=True, capture_output=True, text=True, timeout=3).stdout)
            serial = int(next(item['info']['props']['object.serial'] for item in objects
                              if item['id'] == node and item['type'] == 'PipeWire:Interface:Node'))
            self.pipeline = self.Gst.parse_launch(
                f'pipewiresrc target-object={serial} on-disconnect=error ! '
                'videoconvert ! videoscale ! '
                'video/x-raw,format=BGRx,width=[1,2048],height=[1,2048],pixel-aspect-ratio=1/1 ! '
                'appsink name=frames sync=false max-buffers=1 drop=true enable-last-sample=false')
            self.sink = self.pipeline.get_by_name('frames')
            if self.pipeline.set_state(self.Gst.State.PLAYING) == self.Gst.StateChangeReturn.FAILURE:
                raise RuntimeError('Capture pipeline could not start')
            self.stage = 'frames'
        except Exception as error:
            self.recover(error)

    def monitors_changed(self, _connection, *_args):
        # Mutter can replace the monitor's PipeWire buffers without posting a
        # GStreamer error. The callback's PyGObject connection wrapper need not
        # be identical to self.connection, and the display-state serial need
        # not change when the same scale is reapplied. This subscription belongs
        # to the active connection and close() removes it, so recover directly.
        if self.stage not in ('retry', 'failed'):
            self.recover(RuntimeError('Monitor configuration changed'))

    def display_changed(self, now):
        if self.stage in ('retry', 'failed') or now < self.next_display_check:
            return False
        self.next_display_check = now + .25
        serial, monitors, logical, _ = self.call(
            DISPLAY, '/org/gnome/Mutter/DisplayConfig', DISPLAY, 'GetCurrentState')
        if len(monitors) != 1 or len(logical) != 1:
            raise ValueError('Expected the existing single test monitor')
        if serial == self.display_serial:
            return False
        self.recover(RuntimeError('Monitor configuration changed'))
        return True

    def recover(self, error):
        # A display-scale change can remove every PipeWire buffer. Recreate
        # only our capture session, retaining the publication and branch ID.
        now = time.monotonic()
        if self.stage == 'live':
            self.started = now
            self.retries = 0
        if self.retries >= 3 or now - self.started > 15:
            self.fail(error)
            return
        print(f'UI capture reconnecting: {type(error).__name__}: {error}', flush=True)
        self.retries += 1
        self.retry_at = now + .5
        self.stage = 'retry'
        self.publication.frames.publish(state='waiting', width=0, height=0, captured_ns=0,
                                        detail='Reconnecting capture')
        self.close()

    def fail(self, error):
        print(f'UI capture unavailable: {type(error).__name__}: {error}', flush=True)
        self.close()
        self.stage = 'failed'
        self.publication.frames.publish(state='unavailable', detail='Capture unavailable; see capture.log')

    def tick(self):
        try:
            if self.stage == 'failed':
                return
            if self.stage == 'retry':
                if time.monotonic() < self.retry_at:
                    return
                self.stage = 'stream'
                self.begin()
            if self.display_changed(time.monotonic()):
                return
            if self.pipeline is not None:
                error = self.pipeline.get_bus().pop_filtered(self.Gst.MessageType.ERROR)
                if error is not None:
                    raise RuntimeError(str(error.parse_error()[0]))
                sample = self.sink.emit('try-pull-sample', 0)
                if sample is not None:
                    info = self.GstVideo.VideoInfo.new_from_caps(sample.get_caps())
                    buffer = sample.get_buffer()
                    count = info.stride[0] * info.height
                    self.publication.frames.publish(
                        buffer.extract_dup(0, count), state='live', width=info.width,
                        height=info.height, stride=info.stride[0], format=0x20020888,
                        captured_ns=time.monotonic_ns(), capture_generation=self.generation)
                    if self.stage != 'live':
                        print(f'UI capture live: generation={self.generation}', flush=True)
                    self.stage = 'live'
            if self.stage != 'live' and time.monotonic() - self.started > 15:
                raise RuntimeError('No monitor frames arrived within 15 seconds')
        except Exception as error:
            self.recover(error)

    def close(self):
        if self.pipeline is not None:
            # Buffer removal can flush downstream concurrently with shutdown.
            # Unblock streaming before NULL starts taking element state locks;
            # otherwise pipewiresrc teardown can deadlock the collector loop.
            print('UI capture teardown: flushing pipeline', flush=True)
            self.pipeline.send_event(self.Gst.Event.new_flush_start())
            print('UI capture teardown: stopping pipeline', flush=True)
            self.pipeline.set_state(self.Gst.State.NULL)
            print('UI capture teardown: pipeline stopped', flush=True)
            self.pipeline = self.sink = None
        if self.connection is not None:
            if self.subscription is not None:
                self.connection.signal_unsubscribe(self.subscription)
                self.subscription = None
            if self.monitor_subscription is not None:
                self.connection.signal_unsubscribe(self.monitor_subscription)
                self.monitor_subscription = None
            if self.cast is not None:
                try:
                    self.call(CAST, self.cast, CAST + '.Session', 'Stop')
                except self.GLib.Error:
                    pass
                self.cast = None
            self.connection.close_sync(None)
            self.connection = None


def main():
    import gi
    gi.require_version('GLibUnix', '2.0')
    from gi.repository import GLib, GLibUnix
    control = socket.socket(fileno=int(sys.argv[1]))
    control.setblocking(False)
    loop = GLib.MainLoop()
    publication = capture = None
    try:
        publication = Publication(registry(create=True))
        publication.frames.publish(worker=os.getppid(), test='', phase='setup', detail='Starting capture',
                                   branch=label(os.environ.get('ONPC_UI_WATCH_BRANCH', 'UI tests'), 120))
        try:
            capture = Capture(publication)
        except Exception as error:
            print(f'UI capture unavailable: {type(error).__name__}: {error}', flush=True)
            publication.frames.publish(state='unavailable', detail='Capture unavailable; see capture.log')

        def tick():
            # The fixture owns this channel. Viewers never receive it.
            for _ in range(32):
                try:
                    packet = control.recv(8192)
                except BlockingIOError:
                    break
                if not packet:
                    loop.quit()
                    return GLib.SOURCE_REMOVE
                value = json.loads(packet)
                if (set(value) == {'test', 'phase'}
                        and all(isinstance(text, str) for text in value.values())):
                    publication.frames.publish(**value)
            publication.serve()
            if capture is not None:
                capture.tick()
            publication.frames.publish()  # Heartbeat also covers a static screen.
            return GLib.SOURCE_CONTINUE

        for sig in (signal.SIGTERM, signal.SIGINT):
            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
        def serve(*_args):
            publication.serve()
            return GLib.SOURCE_CONTINUE
        GLib.io_add_watch(publication.server.fileno(), GLib.IOCondition.IN, serve)
        GLib.timeout_add(100, tick)
        loop.run()
    finally:
        control.close()
        try:
            if capture is not None:
                capture.close()
        finally:
            if publication is not None:
                publication.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
