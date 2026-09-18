"""Manually opened GTK window displaying only local read-only frame copies."""

import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess
import time

from e2e_watch_protocol import BASE, progress_packet, read_frame, receive_frames, require

WAITING = 'Waiting for an E2E VM. You can leave this window open.'
TITLE = 'E2E VM — View only'
APPLICATION_ID = 'org.onpc.E2EWatch'


def duration_text(seconds):
    minutes = max(0, int(seconds) // 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m' if hours else f'{minutes}m'


def progress_text(meta, *, now_ns=None):
    progress = meta.get('progress') or {}
    if not progress:
        return TITLE, '', ''
    suffix = ''
    now = time.monotonic_ns() if now_ns is None else now_ns
    if 'started_ns' in progress:
        current = duration_text((now - progress['case_started_ns']) / 1e9)
        total = duration_text((now - progress['started_ns']) / 1e9)
        suffix = f' - ({current}/{total})'
    operation = progress['operation']
    started = progress.get('operation_started_ns')
    if operation.startswith('Preparing VM:'):
        started = progress.get('case_started_ns', started)
    if operation and started is not None:
        minutes, seconds = divmod(max(0, (now - started) // 1_000_000_000), 60)
        elapsed = f'{minutes}m {seconds}s' if minutes else f'{seconds}s'
        operation += f' - ({elapsed})'
    return (f"[{progress['current']}/{progress['total']}] [{progress['case_id']}]: {progress['title']}" + suffix,
            progress['step'], operation)


class Feed:
    """Reconnect to subsequent attempts without any dependency on window life."""

    def __init__(self):
        self.memory = None
        self.sequence = 0
        self.next_connect = 0
        self.last_frame = time.monotonic()
        self.next_activity = 0
        self.activity_value = None

    def activity(self):
        """Authenticated output-only snapshots, independent of QEMU frames."""
        now = time.monotonic()
        if now < self.next_activity:
            return self.activity_value
        self.next_activity = now + .25
        directory = BASE / str(os.getuid())
        try:
            for path in (BASE, directory, directory / 'activity.json'):
                info = path.lstat()
                require(info.st_uid == 0 and not info.st_mode & 0o022
                        and not stat.S_ISLNK(info.st_mode), 'registry-owner')
            path = directory / 'activity.json'
            require(path.stat().st_size < 128, 'activity-registry-size')
            run = json.loads(path.read_text())['run']
            require(type(run) is str and re.fullmatch('[0-9a-f]{32}', run), 'run-identity')
            with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
                peer.settimeout(.05)
                peer.connect(str(directory / (run + '.sock')))
                require(struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET,
                    socket.SO_PEERCRED, 12))[1] == 0, 'server-owner')
                packet, _, flags, _ = peer.recvmsg(100000)
                require(not flags & socket.MSG_TRUNC, 'activity-size')
                value = json.loads(packet)
                require(set(value) in ({'run', 'sequence', 'text'}, {'run', 'sequence', 'text', 'offset'})
                        and value['run'] == run
                        and type(value['sequence']) is int and value['sequence'] >= 0
                        and type(value.get('offset', 0)) is int and value.get('offset', 0) >= 0
                        and type(value['text']) is str and len(value['text']) <= 8000,
                        'activity-fields')
            self.activity_value = value
        except (OSError, ValueError, KeyError, TypeError):
            self.activity_value = None
        return self.activity_value

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

    def progress(self):
        """Read only the root-owned, bounded, fresh invocation heartbeat."""
        directory = BASE / str(os.getuid())
        try:
            for path in (BASE, directory):
                info = path.lstat()
                require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                        and not info.st_mode & 0o022 and path.resolve() == path, 'registry-owner')
            fd = os.open(directory / 'progress.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and info.st_uid == 0
                        and not info.st_mode & 0o022 and info.st_size <= 4096, 'progress-owner')
                value = json.loads(stream.read(4097))
            age = time.monotonic_ns() - value['updated_ns']
            require(0 <= age < 3_000_000_000, 'progress-expired')
            return json.loads(progress_packet(value['progress']))
        except (OSError, ValueError, KeyError, TypeError):
            return None

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
    try:
        gi.require_version('Vte', '3.91')
    except ValueError as error:
        raise RuntimeError('watch-e2e needs GTK 4 VTE; run ./setup.sh --test-tools-only') from error
    from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Pango, Vte

    # A terminal launched by an editor can pass its desktop/startup identity
    # down to us. Give this separate window its own shell association.
    for name in ('GIO_LAUNCHED_DESKTOP_FILE', 'GIO_LAUNCHED_DESKTOP_FILE_PID',
                 'DESKTOP_STARTUP_ID', 'XDG_ACTIVATION_TOKEN'):
        os.environ.pop(name, None)
    GLib.set_prgname(APPLICATION_ID)
    GLib.set_application_name(TITLE)

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
            super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.feed = feed if feed is not None else Feed()
            self.window = None
            self.metadata = {}

        def do_activate(self):
            if self.window is not None:
                return
            self.window = Gtk.ApplicationWindow(application=self, title=TITLE)
            self.window.set_icon_name(APPLICATION_ID)
            header = Gtk.HeaderBar(decoration_layout=':minimize,maximize,close')
            header.pack_start(Gtk.Image(
                icon_name=APPLICATION_ID, pixel_size=32, valign=Gtk.Align.CENTER))
            self.window.set_titlebar(header)
            self.window.set_default_size(1050, 820)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.screen = Screen()
            self.step = Gtk.Label(xalign=0, yalign=0, wrap=True,
                                  wrap_mode=Pango.WrapMode.WORD_CHAR,
                                  ellipsize=Pango.EllipsizeMode.END, lines=3)
            # Reserve exactly three font lines, including for short/empty steps.
            metrics = self.step.get_pango_context().get_metrics(None, None)
            line_height = (metrics.get_ascent() + metrics.get_descent()) / Pango.SCALE
            self.step.set_size_request(-1, int(line_height * 3 + .999))
            self.step.set_margin_start(8)
            self.step.set_margin_end(8)
            self.step.set_margin_top(8)
            self.status = Gtk.Label(label=WAITING, xalign=0,
                                    ellipsize=Pango.EllipsizeMode.END, single_line_mode=True)
            self.status.set_margin_start(8)
            self.status.set_margin_end(8)
            self.status.set_margin_top(8)
            self.status.set_margin_bottom(8)
            box.append(self.step)
            pane = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
            pane.set_start_child(self.screen)
            pane.set_resize_start_child(True)
            pane.set_shrink_start_child(True)
            self.terminal = Vte.Terminal()
            self.terminal.set_input_enabled(False)
            self.terminal.set_allow_hyperlink(False)
            self.terminal.set_audible_bell(False)
            self.terminal.set_bold_is_bright(True)
            self.terminal.set_scrollback_lines(2000)
            self.terminal.set_scroll_on_output(True)
            self.terminal.set_font(Pango.FontDescription('Ubuntu Mono 12'))
            def color(value):
                rgba = Gdk.RGBA()
                rgba.parse(value)
                return rgba
            self.terminal.set_colors(color('#eeeeec'), color('#300a24'), list(map(color, (
                '#2e3436', '#cc0000', '#4e9a06', '#c4a000',
                '#3465a4', '#75507b', '#06989a', '#d3d7cf',
                '#555753', '#ef2929', '#8ae234', '#fce94f',
                '#729fcf', '#ad7fa8', '#34e2e2', '#eeeeec'))))
            self.terminal.add_css_class('vm-terminal')
            terminal_style = Gtk.CssProvider()
            terminal_style.load_from_data(b'''
                .vm-terminal { padding: 8px 10px; }
            ''')
            Gtk.StyleContext.add_provider_for_display(self.window.get_display(),
                terminal_style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.terminal.update_property([Gtk.AccessibleProperty.LABEL], ['VM command input and output'])
            scroll = Gtk.ScrolledWindow(min_content_height=150)
            scroll.set_child(self.terminal)
            pane.set_end_child(scroll)
            pane.set_position(540)
            box.append(pane)
            self.activity_identity = None
            self.activity_end = 0
            box.append(self.status)
            self.window.set_child(box)
            self.window.present()  # Only the user's initial launch presents it.
            self.timer = GLib.timeout_add(33, self.tick)

        def tick(self):
            activity = self.feed.activity()
            if activity is not None:
                identity = (activity['run'], activity['sequence'])
                if identity != self.activity_identity:
                    offset = activity.get('offset', 0)
                    end = offset + len(activity['text'])
                    if (self.activity_identity is None or self.activity_identity[0] != activity['run']
                            or not offset <= self.activity_end <= end
                            or 'offset' not in activity):
                        self.terminal.reset(True, True)
                        self.activity_end = offset
                    text = activity['text'][self.activity_end - offset:]
                    # SSH pipes carry LF; a terminal normally receives CRLF
                    # from its PTY. Preserve existing CR/erase/cursor sequences.
                    self.terminal.feed(re.sub(r'(?<!\r)\n', '\r\n', text).encode('utf-8'))
                    self.activity_identity = identity
                    self.activity_end = end
            frame = self.feed.poll()
            if frame == 'waiting':
                self.screen.clear()
                self.metadata = {}
            elif frame is not None:
                self.metadata = frame[1]
                if frame[1]['state'] == 'live':
                    self.screen.update(frame)
                else:
                    self.screen.clear()
            progress = self.feed.progress()
            meta = dict(self.metadata)
            if progress:
                meta['progress'] = progress
            title, step, operation = progress_text(meta)
            self.window.set_title(title)
            self.step.set_label(step)
            self.status.set_label(operation or ('VM commands · View only' if activity else
                ('Live · View only' if meta.get('state') == 'live' else WAITING)))
            return True

        def do_shutdown(self):
            if hasattr(self, 'timer'):
                GLib.source_remove(self.timer)
            self.feed.close()
            Gtk.Application.do_shutdown(self)

    return Viewer()


def desktop_launch_command():
    """Start through the user manager, without an editor's Snap process label.

    A scope would retain the caller as parent and inherit its AppArmor label.
    A user service starts from the desktop user manager instead. Forward only
    the desktop connection variables, not the editor's Snap/loader environment.
    """
    command = ['/usr/bin/systemd-run', '--user', '--quiet', '--collect',
               '--wait', '--pipe', '--service-type=exec']
    for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY',
                 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'):
        if name in os.environ:
            command.append('--setenv=' + name + '=' + os.environ[name])
    return command + ['--', str(Path(__file__).resolve().with_name('watch-e2e')),
                      '--desktop-session']


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Watch E2E output. Close this window whenever you want.')
    parser.add_argument('--desktop-session', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    require(os.getuid() != 0, 'launch-as-your-desktop-user')
    # Mutter derives Snap identity from this kernel label, not environment
    # variables or GTK's application ID. Do not modify the security profile.
    try:
        snap_parent = Path('/proc/self/attr/current').read_text().startswith('snap.')
    except FileNotFoundError:
        snap_parent = False
    if snap_parent:
        require(not args.desktop_session, 'desktop-session-still-has-snap-identity')
        return subprocess.run(desktop_launch_command(), check=False).returncode
    return application().run(['watch-e2e'])
