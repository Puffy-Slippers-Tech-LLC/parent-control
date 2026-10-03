"""Bounded observation and owner-scoped cancellation of detached launchers."""

import fcntl
import codecs
import io
import json
import os
from pathlib import Path
import re
import stat

from test_storage import directory

TAIL_BYTES = 128 * 1024


def open_private(path):
    # Do not create locks, mark results delivered, or follow replaced paths.
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('watch-output: symlink')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_nlink != 1):
        os.close(fd)
        raise ValueError('watch-output: unsafe file')
    return os.fdopen(fd, 'rb')


def read_json(path, limit=65536):
    with open_private(path) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('watch-output: oversized metadata')
    return json.loads(data)


def snapshot(path, *, steps=False):
    try:
        value = read_json(path)
    except FileNotFoundError:
        return []
    def lines(items):
        return isinstance(items, list) and all(isinstance(item, str) for item in items)
    valid = (isinstance(value, list) and all(
        isinstance(step, dict) and isinstance(step.get('key'), str)
        and lines(step.get('lines')) and step['lines']
        and lines(step.get('replaces', [])) for step in value)) if steps else lines(value)
    if not valid:
        raise ValueError('watch-output: invalid progress')
    return value


def active_run(base, *, workflow=False):
    name = read_json(base / 'current.json', 4096)['run']
    if not isinstance(name, str) or not re.fullmatch('[0-9a-f]{32}', name):
        raise ValueError('watch-output: invalid run')
    run = base / name
    info = run.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077):
        raise ValueError('watch-output: unsafe run')
    with open_private((base if workflow else run) / 'owner') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return run
        fcntl.flock(owner, fcntl.LOCK_UN)
    return None


class Output:
    def __init__(self, root=None, *, terminal_size=None):
        self.root = root or Path(__file__).resolve().parents[1]
        self.terminal_size = terminal_size
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.run = None
        self.label = ''
        self.identity = None
        self.offset = 0
        self.display = None
        self.line_start = True

    def progress(self, active, data=b''):
        from launcher_progress import repair_progress
        from launcher_render import LauncherDisplay, clean
        if self.display is None:
            # The embedded terminal supplies its own dimensions and needs the
            # same in-place dashboard as an attached launcher, not log snapshots.
            self.display = LauncherDisplay(io.StringIO(), terminal_size=self.terminal_size)
        if self.terminal_size is not None and data:
            self.display.write(self.decoder.decode(data))
        try:
            steps = snapshot(self.run / 'controller.json', steps=True)
            if self.label == 'fix-tests':
                steps = repair_progress(self.run, steps,
                    child_steps=snapshot(self.run / 'test-controller.json', steps=True))
            details = snapshot(self.run / 'frame.json') if active else []
            if steps:
                details = [line for line in details if not clean(line).startswith('Overall - ')]
            self.display.update(steps, details)
        except (OSError, ValueError, KeyError, TypeError):
            # A rejected progress publication must not swallow fresh log bytes.
            self.display.draw()
        stream = self.display.stream
        data = stream.getvalue().encode('utf-8')
        stream.seek(0)
        stream.truncate()
        return data

    def scroll(self, rows):
        if self.display is not None:
            self.display.offsets['bottom'] = max(0, self.display.offsets['bottom'] + rows)

    def cancel(self):
        """Request the displayed owner's cooperative Ctrl+C shutdown."""
        run, _label = self.discover()
        if run is None or run != self.run:
            return False
        try:
            (run / 'cancel').touch(mode=0o600)
        except OSError:
            return False
        return True

    def discover(self):
        for kind, label in (('fix-tests', 'fix-tests'), ('fix-tests-host', 'fix-tests'), ('sessions-host', 'run-tests'),
                            ('sessions', 'run-tests')):
            try:
                base = directory(kind, root=self.root, create=False)
                run = active_run(base, workflow=kind in ('fix-tests', 'fix-tests-host'))
                if run is not None:
                    return run, label
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return None, ''

    def poll(self):
        run, label = self.discover()
        active = run is not None
        # Drain the final bytes after owner exit and keep the last transcript.
        if run is None:
            run, label = self.run, self.label
        reset, data = False, b''
        if run is not None:
            try:
                with open_private(run / 'output') as stream:
                    info = os.fstat(stream.fileno())
                    identity = (run, info.st_dev, info.st_ino)
                    reset = identity != self.identity or info.st_size < self.offset
                    if reset:
                        self.display = None
                        self.decoder.reset()
                        self.line_start = True
                        self.offset = max(0, info.st_size - TAIL_BYTES)
                        stream.seek(self.offset)
                        if self.offset:
                            stream.readline(TAIL_BYTES)
                            self.offset = stream.tell()
                    stream.seek(self.offset)
                    data = stream.read(TAIL_BYTES)
                    self.offset = stream.tell()
                    self.identity, self.run, self.label = identity, run, label
            except (OSError, ValueError):
                pass
        if data:
            self.line_start = data.endswith(b'\n')
        if self.terminal_size is not None and self.run == run and run is not None:
            data = self.progress(active, data)
        elif self.run == run and run is not None and self.line_start:
            # Never insert dashboard text into a partial UTF-8/ANSI/log line.
            data += self.progress(active)
        return label, active, reset, data


def terminal(identity, description):
    """VS Code Light+ palette, responsive terminal reflow, vertical scroll only."""
    import gi
    gi.require_version('Vte', '3.91')
    from gi.repository import Gdk, Gtk, Pango, Vte
    from common.oh_no_parent_control_ui.gtk_automation import set_automation_id

    view = Vte.Terminal(hexpand=True, vexpand=True)
    set_automation_id(view, identity)
    view.set_input_enabled(False)
    view.set_focusable(True)
    view.set_allow_hyperlink(False)
    view.set_audible_bell(False)
    view.set_bold_is_bright(True)
    view.set_scrollback_lines(10000)
    view.set_scroll_on_output(False)
    view.set_font(Pango.FontDescription('Monospace 10'))
    def color(value):
        rgba = Gdk.RGBA()
        rgba.parse(value)
        return rgba
    view.set_colors(color('#26374e'), color('#ffffff'), list(map(color, (
        '#000000', '#cd3131', '#008000', '#866951',
        '#0451a5', '#bc05bc', '#0598bc', '#555555',
        '#666666', '#cd3131', '#14ce14', '#b5ba00',
        '#0451a5', '#bc05bc', '#0598bc', '#77808b'))))
    view.set_color_highlight(color('#add6ff'))
    view.set_color_highlight_foreground(color('#26374e'))
    view.update_property([Gtk.AccessibleProperty.LABEL], [description])
    scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True,
        hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
    set_automation_id(scroll, identity + '-scroll')
    scroll.set_margin_start(18)
    scroll.set_child(view)
    return view, scroll


class TerminalWriter:
    def __init__(self, view):
        from tests.integration.watch_activity import TerminalControls
        self.view = view
        self.controls = TerminalControls()
        self.last_cr = False

    def feed(self, data, *, reset=False):
        if reset:
            self.view.reset(True, True)
            self.controls.__init__()
            self.last_cr = False
        data = self.controls.feed(data)
        if not data:
            return
        # Pipes lack the PTY's LF->CRLF conversion. Honor split CRLF pairs.
        prefix = b'\r' if self.last_cr else b''
        self.last_cr = data.endswith(b'\r')
        converted = re.sub(rb'(?<!\r)\n', b'\r\n', prefix + data)
        self.view.feed(converted[len(prefix):])
