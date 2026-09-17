"""Private QEMU display listener; serves copies, never exposes a VM connection."""

import argparse
import array
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from e2e_watch_protocol import Frames, layout, progress_packet, require

# Supported QEMU org.qemu.Display1.Listener API, copied image path only.
# Deliberately do not advertise Unix.Map/DMABUF (synchronous/GPU acknowledgements).
XML = '''<node><interface name="org.qemu.Display1.Listener">
<method name="Scanout"><arg type="u" direction="in"/><arg type="u" direction="in"/>
<arg type="u" direction="in"/><arg type="u" direction="in"/><arg type="ay" direction="in"/></method>
<method name="Update"><arg type="i" direction="in"/><arg type="i" direction="in"/>
<arg type="i" direction="in"/><arg type="i" direction="in"/>
<arg type="u" direction="in"/><arg type="u" direction="in"/><arg type="ay" direction="in"/></method>
<method name="Disable"/>
<method name="MouseSet"><arg type="i" direction="in"/><arg type="i" direction="in"/>
<arg type="i" direction="in"/></method>
<method name="CursorDefine"><arg type="i" direction="in"/><arg type="i" direction="in"/>
<arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="ay" direction="in"/></method>
<property name="Interfaces" type="as" access="read"/>
</interface></node>'''


class Display:
    def __init__(self, frames):
        self.frames = frames
        self.pixels = bytearray()
        self.cursor = b''
        self.meta = {}
        self.dirty = False

    def update(self, method, values, data=b''):
        if method == 'Scanout':
            width, height, stride, format_ = values
            require(len(data) == layout(*values), 'scanout-size')
            self.meta.update(width=width, height=height, stride=stride, format=format_, state='live')
            self.pixels = bytearray(data)
        elif method == 'Update':
            x, y, width, height, stride, format_ = values
            require(len(data) == layout(width, height, stride, format_), 'update-size')
            # During early VGA startup QEMU can send damage before its first
            # full Scanout. Keep Waiting until dimensions/full pixels arrive.
            if self.meta.get('state') != 'live':
                return
            require(x >= 0 and y >= 0 and x + width <= 2048 and y + height <= 2048, 'update-bounds')
            if (format_ != self.meta['format'] or x + width > self.meta['width']
                    or y + height > self.meta['height']):
                # A mode switch may discard queued full-frame messages in
                # QEMU. Never apply new-mode damage to old-mode geometry.
                self.update('Disable', [])
                return
            for row in range(height):
                offset = (y + row) * self.meta['stride'] + x * 4
                self.pixels[offset:offset + width * 4] = data[row * stride:row * stride + width * 4]
        elif method == 'Disable':
            self.meta.update(state='waiting', width=0, height=0, cursor_on=False)
            self.pixels = bytearray()
        elif method == 'MouseSet':
            self.meta.update(cursor_x=values[0], cursor_y=values[1], cursor_on=bool(values[2]))
        elif method == 'CursorDefine':
            width, height, hot_x, hot_y = values
            require(0 < width <= 256 and 0 < height <= 256
                    and 0 <= hot_x < width and 0 <= hot_y < height
                    and len(data) == width * height * 4, 'cursor-bounds')
            self.meta.update(cursor_width=width, cursor_height=height, hot_x=hot_x, hot_y=hot_y)
            self.cursor = data
        else:
            require(False, 'unknown-display-method')
        self.dirty = True

    def publish(self):
        if self.dirty:
            self.frames.publish(self.pixels, self.cursor, **self.meta)
            self.dirty = False
            return True
        return False


def receive_progress(control, frames):
    """Controller-only metadata; no viewer or guest command channel."""
    packet, _, flags, _ = control.recvmsg(3501)
    if not packet:
        return False
    require(not flags & socket.MSG_TRUNC, 'progress-size')
    value = json.loads(packet)
    require(progress_packet(value) == packet, 'progress-packet')
    frames.publish(progress=value)
    return True


def export_listener(connection, display, failed):
    from gi.repository import Gio, GLib
    def method(_connection, _sender, _path, _interface, name, parameters, invocation):
        try:
            n = parameters.n_children()
            payload = name in ('Scanout', 'Update', 'CursorDefine')
            values = [parameters.get_child_value(i).unpack() for i in range(n - int(payload))]
            data = parameters.get_child_value(n - 1).get_data_as_bytes().get_data() if payload else b''
            display.update(name, values, data)
            invocation.return_value(GLib.Variant('()', ()))
        except Exception as error:
            category = (str(error) if isinstance(error, ValueError) and str(error).startswith('watch:')
                        else type(error).__name__)
            print('watch-collector: invalid-update ' + name + ' ' + category, flush=True)
            invocation.return_dbus_error('org.onpc.Watch.InvalidFrame', 'Invalid display update')
            failed()
    return connection.register_object_with_closures2('/org/qemu/Display1/Listener',
        Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], method,
        lambda *_: GLib.Variant('as', []), None)


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    for name in ('control', 'display', 'listener', 'remote', 'server', 'uid'):
        parser.add_argument('--' + name, required=True, type=int)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0 and args.uid > 0, 'collector-context')
    control = socket.socket(fileno=args.control)
    control.settimeout(5)
    # The parent pins our process identity before authorizing any attachment.
    if control.recv(16) != b'start':
        return
    os.nice(5)
    import gi
    from gi.repository import Gio, GLib
    control.setblocking(False)
    server = socket.socket(fileno=args.server)
    server.setblocking(False)
    frames = Frames(args.run)
    display = Display(frames)
    loop = GLib.MainLoop()
    connections = []
    counts = {'frames': 0, 'viewers': 0}
    last_beat = 0

    def tick():
        nonlocal last_beat
        try:
            try:
                if not receive_progress(control, frames):
                    loop.quit()
                    return False
            except BlockingIOError:
                pass
            for _ in range(4):
                try:
                    peer, _ = server.accept()
                except BlockingIOError:
                    break
                try:
                    with peer:
                        peer.setblocking(False)
                        uid = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                        if uid != args.uid:
                            continue
                        peer.sendmsg([b'ONPC-WATCH-1'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                      array.array('i', [frames.read_fd]))])
                        counts['viewers'] += 1
                except OSError:
                    # An arbitrary viewer disconnect/full buffer is local to it.
                    continue
            counts['frames'] += int(display.publish())
            if time.monotonic() - last_beat > .5:
                # Refresh liveness even on a perfectly still screen.
                if not display.dirty:
                    frames.publish()
                control.send(b'beat')
                last_beat = time.monotonic()
        except (OSError, ValueError) as error:
            category = (str(error) if isinstance(error, ValueError) and str(error).startswith('watch:')
                        else type(error).__name__)
            print('watch-collector: transport-failed ' + category, flush=True)
            loop.quit()
            return False
        return True

    def connected(_source, result):
        try:
            listener = Gio.DBusConnection.new_finish(result)
            connections.append(listener)
            listener.set_exit_on_close(False)
            export_listener(listener, display, loop.quit)
            listener.connect('closed', lambda *_: loop.quit())
            listener.start_message_processing()
        except Exception as error:
            print('watch-collector: listener-failed ' + type(error).__name__, flush=True)
            loop.quit()

    def registered(connection, result):
        try:
            connection.call_with_unix_fd_list_finish(result)
            # QEMU has completed registration before automation starts input.
            control.send(b'ready')
        except Exception as error:
            print('watch-collector: registration-failed ' + type(error).__name__, flush=True)
            loop.quit()

    try:
        transport = Gio.Socket.new_from_fd(args.display).connection_factory_create_connection()
        connection = Gio.DBusConnection.new_sync(transport, None,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT, None, None)
        connection.set_exit_on_close(False)
        connections.append(connection)
        connection.connect('closed', lambda *_: loop.quit())
        # Exact graphical console exported by the unchanged first video head.
        result = connection.call_sync(None, '/org/qemu/Display1/VM',
            'org.freedesktop.DBus.Properties', 'Get',
            GLib.Variant('(ss)', ('org.qemu.Display1.VM', 'ConsoleIDs')), None,
            Gio.DBusCallFlags.NONE, 3000, None)
        console_ids = result.unpack()[0]
        require(0 in console_ids, 'primary-console-missing')
        transport = Gio.Socket.new_from_fd(args.listener).connection_factory_create_connection()
        Gio.DBusConnection.new(transport, None,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.DELAY_MESSAGE_PROCESSING,
            None, None, connected)
        fds = Gio.UnixFDList.new()
        index = fds.append(args.remote)
        connection.call_with_unix_fd_list(None, '/org/qemu/Display1/Console_0',
            'org.qemu.Display1.Console', 'RegisterListener', GLib.Variant('(h)', (index,)),
            None, Gio.DBusCallFlags.NONE, 3000, fds, None, registered)
        os.close(args.remote)
        GLib.timeout_add(33, tick)
        loop.run()
    finally:
        frames.close()
        for connection in connections:
            connection.close(None, None)
        server.close()
        control.close()
        print('watch-collector: frames={frames} viewers={viewers}'.format(**counts), flush=True)


if __name__ == '__main__':
    main()
