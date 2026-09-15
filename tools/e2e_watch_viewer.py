"""Manually opened GTK window displaying only local read-only frame copies."""

import json
import os
import re
import socket
import stat
import time

from e2e_watch_protocol import BASE, read_frame, receive_frames, require


class Feed:
    """Reconnect to subsequent attempts without any dependency on window life."""

    def __init__(self):
        self.memory = None
        self.sequence = 0
        self.next_connect = 0
        self.last_frame = time.monotonic()

    def connect(self):
        directory = BASE / str(os.getuid())
        for path in (BASE, directory, directory / 'current.json'):
            info = path.lstat()
            require(info.st_uid == 0 and not info.st_mode & 0o022
                    and not stat.S_ISLNK(info.st_mode), 'registry-owner')
        run = json.loads((directory / 'current.json').read_text())['run']
        require(isinstance(run, str) and re.fullmatch('[0-9a-f]{32}', run), 'run-identity')
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
            peer.settimeout(.2)
            peer.connect(str(directory / (run + '.sock')))
            self.memory = receive_frames(peer)
        self.sequence = 0
        self.last_frame = time.monotonic()

    def close(self):
        if self.memory is not None:
            self.memory.close()
            self.memory = None

    def poll(self):
        now = time.monotonic()
        try:
            if self.memory is None:
                if now < self.next_connect:
                    return None
                self.next_connect = now + 1
                self.connect()
            frame = read_frame(self.memory, self.sequence)
            if frame is None:
                # A killed/stopped writer can leave an odd seqlock indefinitely.
                if now - self.last_frame > 3:
                    self.close()
                    return 'waiting'
                return None
            sequence, meta, *_ = frame
            if meta['state'] == 'stopped' or time.monotonic_ns() - meta['updated_ns'] > 3_000_000_000:
                self.close()
                return 'waiting'
            self.last_frame = now
            self.sequence = sequence
            return frame
        except (OSError, ValueError, KeyError, TypeError):
            self.close()
            return 'waiting'


def application(feed=None):
    # Importing transport helpers for tests does not connect to the host desktop.
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    gi.require_version('Graphene', '1.0')
    from gi.repository import Gdk, Gio, GLib, Graphene, Gtk

    class Screen(Gtk.Widget):
        def __init__(self):
            super().__init__(hexpand=True, vexpand=True)
            self.texture = self.cursor = None
            self.meta = {}
            self.set_overflow(Gtk.Overflow.HIDDEN)
            self.set_focusable(False)

        def do_measure(self, orientation, _for_size):
            return 100, (1024 if orientation == Gtk.Orientation.HORIZONTAL else 768), -1, -1

        def update(self, frame):
            _, self.meta, pixels, cursor = frame
            m = self.meta
            formats = {0x20020888: Gdk.MemoryFormat.B8G8R8X8,
                       0x20028888: Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                       0x20030888: Gdk.MemoryFormat.R8G8B8X8,
                       0x20038888: Gdk.MemoryFormat.R8G8B8A8_PREMULTIPLIED}
            self.texture = Gdk.MemoryTexture.new(m['width'], m['height'], formats[m['format']],
                                                 GLib.Bytes.new(pixels), m['stride'])
            self.cursor = (Gdk.MemoryTexture.new(m['cursor_width'], m['cursor_height'],
                Gdk.MemoryFormat.B8G8R8A8, GLib.Bytes.new(cursor), m['cursor_width'] * 4)
                if cursor and m['cursor_on'] else None)
            self.queue_draw()

        def clear(self):
            self.texture = self.cursor = None
            self.queue_draw()

        def do_snapshot(self, snapshot):
            if self.texture is None:
                return
            m = self.meta
            scale = min(self.get_width() / m['width'], self.get_height() / m['height'])
            left = (self.get_width() - m['width'] * scale) / 2
            top = (self.get_height() - m['height'] * scale) / 2
            rect = Graphene.Rect().init(left, top, m['width'] * scale, m['height'] * scale)
            snapshot.push_clip(rect)
            snapshot.append_texture(self.texture, rect)
            if self.cursor is not None:
                rect = Graphene.Rect().init(left + (m['cursor_x'] - m['hot_x']) * scale,
                    top + (m['cursor_y'] - m['hot_y']) * scale,
                    m['cursor_width'] * scale, m['cursor_height'] * scale)
                snapshot.append_texture(self.cursor, rect)
            snapshot.pop()

    class Viewer(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='org.onpc.E2EWatch', flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.feed = feed if feed is not None else Feed()
            self.window = None

        def do_activate(self):
            if self.window is not None:
                return
            self.window = Gtk.ApplicationWindow(application=self, title='E2E VM — View only')
            self.window.set_default_size(1050, 820)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.screen = Screen()
            self.status = Gtk.Label(label='Waiting for an E2E VM. You can leave this window open.')
            self.status.set_margin_top(8)
            self.status.set_margin_bottom(8)
            box.append(self.screen)
            box.append(self.status)
            self.window.set_child(box)
            self.window.present()  # Only the user's initial launch presents it.
            self.timer = GLib.timeout_add(33, self.tick)

        def tick(self):
            frame = self.feed.poll()
            if frame is None:
                return True
            if frame == 'waiting' or frame[1]['state'] != 'live':
                self.screen.clear()
                self.status.set_label('Waiting for an E2E VM. You can leave this window open.')
            else:
                self.screen.update(frame)
                self.status.set_label('Live · View only · Keyboard and mouse stay on your host')
            return True

        def do_shutdown(self):
            if hasattr(self, 'timer'):
                GLib.source_remove(self.timer)
            self.feed.close()
            Gtk.Application.do_shutdown(self)

    return Viewer()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Watch E2E output. Close this window whenever you want.')
    parser.parse_args()
    require(os.getuid() != 0, 'launch-as-your-desktop-user')
    return application().run(['watch-e2e'])
