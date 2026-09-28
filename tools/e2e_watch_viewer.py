"""Manually opened GTK window displaying only local read-only frame copies."""

import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import time

from e2e_watch_protocol import BASE, progress_packet, read_frame, receive_frames, require

WAITING = 'Waiting for VM activity. You can leave this window open.'
TITLE = 'VM — View only'
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


def activity_text(activity, progress=None, *, now_ns=None):
    """Current shared intent wins over older case metadata, with its own timer."""
    if not activity or not activity.get('operation') or activity.get('operation_active') is False:
        return ''
    started = activity['operation_started_ns']
    # Explicit scopes survive nested progress updates, including restoration
    # of an older parent. Generic command labels defer to newer worker prose.
    if (activity.get('operation_priority', 1) < 2
            and (progress or {}).get('operation_started_ns', 0) > started):
        return ''
    now = time.monotonic_ns() if now_ns is None else now_ns
    minutes, seconds = divmod(max(0, (now - started) // 1_000_000_000), 60)
    elapsed = f'{minutes}m {seconds}s' if minutes else f'{seconds}s'
    return activity['operation'] + f' - ({elapsed})'


class Feed:
    """Reconnect to subsequent attempts without any dependency on window life."""

    def __init__(self):
        self.memory = None
        self.sequence = 0
        self.next_connect = 0
        self.last_frame = time.monotonic()
        self.next_activity = 0
        self.activity_value = None
        self.activity_offsets = {}
        self.activity_buffer = ''
        self.activity_offset = 0
        self.activity_sequence = 0

    def activity(self):
        """Authenticated output-only snapshots, independent of QEMU frames."""
        now = time.monotonic()
        if now < self.next_activity:
            return self.activity_value
        self.next_activity = now + .25
        directory = BASE / str(os.getuid())
        values = []
        # Include the old single registry for already-running controllers during
        # a checkout update. All new publishers use independent registrations.
        try:
            paths = sorted(directory.glob('activity-*.json'))
            paths.append(directory / 'activity.json')
            for path in paths:
                value = self.activity_packet(directory, path)
                if value is not None:
                    values.append(value)
                    if len(values) == 128:
                        break
                # A crashed producer can leave a registry behind. Only live,
                # authenticated replies count toward the retained bound.
        except (OSError, ValueError):
            values = []
        if not values:
            self.activity_value = None
            return None
        offsets = {}
        for value in sorted(values, key=lambda item: item.get('operation_started_ns', 0)):
            offset = value.get('offset', 0)
            end = offset + len(value['text'])
            previous = self.activity_offsets.get(value['run'], offset)
            if not offset <= previous <= end:
                previous = offset
            addition = value['text'][previous - offset:]
            if addition:
                combined = self.activity_buffer + addition
                self.activity_offset += max(0, len(combined) - 8000)
                self.activity_buffer = combined[-8000:]
                self.activity_sequence += 1
            offsets[value['run']] = end
        # A transient publisher timeout must not replay its entire retained
        # transcript when it answers again. Bound history across ended callers.
        self.activity_offsets.update(offsets)
        while len(self.activity_offsets) > 128:
            self.activity_offsets.pop(next(iter(self.activity_offsets)))
        latest = max(values, key=lambda value: (value.get('operation_active', False),
                                               value.get('operation_priority', 1),
                                               value.get('operation_started_ns', 0)))
        self.activity_value = dict(run='0' * 32, sequence=self.activity_sequence,
            text=self.activity_buffer, offset=self.activity_offset,
            operation=latest.get('operation', ''),
            operation_active=latest.get('operation_active', False),
            operation_priority=latest.get('operation_priority', 1),
            operation_started_ns=latest.get('operation_started_ns', 0))
        return self.activity_value

    def activity_packet(self, directory, path):
        """Authenticate every producer independently; viewers never send input."""
        try:
            for entry in (BASE, directory, path):
                info = entry.lstat()
                require(info.st_uid == 0 and not info.st_mode & 0o022
                        and not stat.S_ISLNK(info.st_mode), 'registry-owner')
            require(stat.S_ISREG(info.st_mode) and info.st_size < 128, 'activity-registry-size')
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
                require(set(value) in ({'run', 'sequence', 'text'}, {'run', 'sequence', 'text', 'offset'},
                                      {'run', 'sequence', 'text', 'offset', 'operation', 'operation_started_ns',
                                       'operation_active', 'operation_priority'},
                                      {'run', 'sequence', 'text', 'offset', 'operation', 'operation_started_ns',
                                       'operation_active'})
                        and value['run'] == run
                        and type(value['sequence']) is int and value['sequence'] >= 0
                        and type(value.get('offset', 0)) is int and value.get('offset', 0) >= 0
                        and type(value['text']) is str and len(value['text']) <= 8000,
                        'activity-fields')
                require(type(value.get('operation', '')) is str and len(value.get('operation', '')) <= 384
                        and type(value.get('operation_active', False)) is bool
                        and type(value.get('operation_priority', 1)) is int
                        and 0 <= value.get('operation_priority', 1) <= 2
                        and type(value.get('operation_started_ns', 0)) is int
                        and 0 <= value.get('operation_started_ns', 0) <= time.monotonic_ns(),
                        'activity-operation')
            return value
        except (OSError, ValueError, KeyError, TypeError):
            return None

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

    def poll(self, *, pixels=True):
        now = time.monotonic()
        try:
            if self.memory is None:
                if now < self.next_connect:
                    return None
                self.next_connect = now + 1
                self.connect()
            frame = read_frame(self.memory, self.sequence if pixels == getattr(self, '_pixels', True) else 0,
                               pixels=pixels)
            self._pixels = pixels
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


def panel(feed=None):
    # Importing transport helpers never connects to the host desktop.
    from common.oh_no_parent_control_ui.gtk_automation import set_automation_id
    from watch_output import terminal, TerminalWriter
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    gi.require_version('Graphene', '1.0')
    from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

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

    class Panel(Gtk.Box):
        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
            self.feed = feed if feed is not None else Feed()
            self.metadata = {}
            self.active = False
            self.heading = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
            set_automation_id(self.heading, 'e2e-watch-heading')
            self.screen = Screen()
            set_automation_id(self.screen, 'e2e-watch-display')
            self.screen.update_property([Gtk.AccessibleProperty.LABEL], ['VM display'])
            self.step = Gtk.Label(xalign=0, yalign=0, wrap=True,
                                  wrap_mode=Pango.WrapMode.WORD_CHAR,
                                  ellipsize=Pango.EllipsizeMode.END, lines=3)
            set_automation_id(self.step, 'e2e-watch-progress')
            metrics = self.step.get_pango_context().get_metrics(None, None)
            line_height = (metrics.get_ascent() + metrics.get_descent()) / Pango.SCALE
            self.step.set_size_request(-1, int(line_height * 3 + .999))
            self.status = Gtk.Label(label=WAITING, xalign=0,
                                    ellipsize=Pango.EllipsizeMode.END, single_line_mode=True)
            set_automation_id(self.status, 'e2e-watch-status')
            for widget in (self.heading, self.step, self.status):
                widget.set_margin_start(8)
                widget.set_margin_end(8)
                widget.set_margin_top(4)
                widget.set_margin_bottom(4)
            self.append(self.heading)
            self.append(self.step)
            pane = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
            set_automation_id(pane, 'e2e-watch-split')
            pane.set_start_child(self.screen)
            pane.set_resize_start_child(True)
            pane.set_shrink_start_child(True)
            self.terminal, scroll = terminal('e2e-watch-output', 'VM command input and output')
            self.writer = TerminalWriter(self.terminal)
            pane.set_end_child(scroll)
            pane.set_resize_end_child(False)
            pane.set_shrink_end_child(True)
            pane.set_position(400)
            self.append(pane)
            self.append(self.status)
            self.activity_identity = None
            self.activity_end = 0

        def tick(self, *, render=True):
            frame = self.feed.poll(pixels=render)
            if frame == 'waiting':
                self.metadata = {}
            elif frame is not None:
                self.metadata = frame[1]
            progress = self.feed.progress()
            self.active = bool(self.metadata or progress)
            if not render:
                return
            activity = self.feed.activity()
            self.active = self.active or bool(activity and activity.get('operation_active'))
            if activity is not None:
                identity = (activity['run'], activity['sequence'])
                if identity != self.activity_identity:
                    offset = activity.get('offset', 0)
                    end = offset + len(activity['text'])
                    reset = (self.activity_identity is None or self.activity_identity[0] != activity['run']
                             or not offset <= self.activity_end <= end or 'offset' not in activity)
                    if reset:
                        self.activity_end = offset
                    text = activity['text'][self.activity_end - offset:]
                    self.writer.feed(text.encode('utf-8'), reset=reset)
                    self.activity_identity = identity
                    self.activity_end = end
            if not self.metadata or self.metadata.get('state') != 'live':
                self.screen.clear()
            elif frame is not None:
                self.screen.update(frame)
            meta = dict(self.metadata)
            if progress:
                meta['progress'] = progress
            title, step, operation = progress_text(meta)
            self.heading.set_label(title)
            self.step.set_label(step)
            self.status.set_label(activity_text(activity, meta.get('progress')) or operation or
                ('VM running · Waiting for the next operation' if meta.get('state') == 'live' else WAITING))

        def close(self):
            self.feed.close()

    return Panel()
