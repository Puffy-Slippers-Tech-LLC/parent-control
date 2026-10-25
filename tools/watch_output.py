"""Bounded observation and owner-scoped cancellation of detached launchers."""

import fcntl
import codecs
import copy
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


class JsonReader:
    """Reuse unchanged publications, rechecking path and file safety each poll."""

    def __init__(self):
        self.cache = {}

    def read(self, path, limit=65536):
        with open_private(path) as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino, info.st_size,
                        info.st_mtime_ns, info.st_ctime_ns, limit)
            cached = self.cache.get(path)
            if cached is not None and cached[0] == identity:
                # repair_progress modifies nested lines for its display only.
                return copy.deepcopy(cached[1])
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('watch-output: oversized metadata')
        value = json.loads(data)
        if len(self.cache) >= 8:
            self.cache.clear()
        self.cache[path] = identity, value
        return copy.deepcopy(value)


def snapshot(path, *, steps=False, reader=None):
    try:
        value = reader.read(path) if reader is not None else read_json(path)
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


def active_run(base, *, workflow=False, reader=None):
    name = (reader.read(base / 'current.json', 4096) if reader is not None
            else read_json(base / 'current.json', 4096))['run']
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
        self.reader = JsonReader()

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
            steps = snapshot(self.run / 'controller.json', steps=True, reader=self.reader)
            if self.label == 'fix-tests':
                steps = repair_progress(self.run, steps,
                    child_steps=snapshot(self.run / 'test-controller.json', steps=True, reader=self.reader))
            details = snapshot(self.run / 'frame.json', reader=self.reader) if active else []
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

    def scroll_state(self):
        """Top row, total rows and visible rows of the embedded dashboard log."""
        display = self.display
        if display is None or display.size is None or 'bottom' not in display.row_cache:
            return 0, 0, 0
        total = len(display.row_cache['bottom'][1])
        visible = max(0, display.size.lines - display.top_height - 1)
        return max(0, total - visible - display.offsets['bottom']), total, visible

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

    def completion_status(self):
        """Describe the displayed run's recorded outcome after its owner exits."""
        if self.run is None:
            return 'incomplete'
        try:
            workflow = self.label == 'fix-tests'
            result = self.reader.read(self.run / ('result.json' if workflow else 'result'), 4096)
            if workflow and not isinstance(result, dict):
                return 'incomplete'
            status = result.get('status') if workflow else result
            if type(status) is not int:
                return 'incomplete'
            if status == 0 and workflow and (self.run / 'limited').exists():
                return 'task limit reached'
            return {0: 'finished', 130: 'stopped'}.get(status, 'failed')
        except (OSError, ValueError, KeyError, TypeError):
            return 'incomplete'

    def discover(self):
        for kind, label in (('fix-tests', 'fix-tests'), ('fix-tests-host', 'fix-tests'), ('sessions-host', 'run-tests'),
                            ('sessions', 'run-tests')):
            try:
                base = directory(kind, root=self.root, create=False)
                run = active_run(base, workflow=kind in ('fix-tests', 'fix-tests-host'), reader=self.reader)
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


class SessionOutput:
    """Follow the displayed workflow's session, with owner-checked input routing."""

    def __init__(self, output, terminal_size):
        self.output = output
        self.terminal_size = terminal_size
        self.run = self.owner = self.identity = None
        self.offset = 0
        self.panel = None
        self.reader = JsonReader()
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')

    def discover(self):
        owner, _ = self.output.discover()
        owners = [owner] if owner is not None else []
        # Plan-based tools have independent namespaces and need no test runner.
        for kind in ('fix-tests', 'fix-tests-host', 'write-e2e', 'sync-whatsnew', 'plans'):
            try:
                base = directory(kind, root=self.output.root, create=False)
                bases = sorted(base.iterdir()) if kind == 'plans' else [base]
                for item in bases:
                    try:
                        run = active_run(item, workflow=True, reader=self.reader)
                        if run is not None:
                            owners.append(run)
                    except (OSError, ValueError, KeyError, TypeError):
                        continue
            except (OSError, ValueError):
                continue
        sessions = []
        for owner in dict.fromkeys(owners):
            # Repair admission permits one writer; select its newest session.
            candidates = [owner, *sorted(owner.glob('pipeline-*'))]
            for run in candidates:
                try:
                    value = self.reader.read(run / 'session-view.json')
                    if (not isinstance(value, dict) or not isinstance(value.get('session'), str)
                            or not isinstance(value.get('started_at'), (int, float))
                            or type(value.get('interactive')) is not bool
                            or value.get('status') != 'running'):
                        continue
                    sessions.append((value['started_at'], owner, run, value))
                except (OSError, ValueError, TypeError):
                    continue
        if sessions:
            _started, owner, run, value = max(sessions, key=lambda item: item[0])
            return owner, run, value, 'session-output.log'
        return None, None, {}, None

    def current(self):
        owner, run, state, _source = self.discover()
        return owner == self.owner and run == self.run and state.get('session') == self.identity

    def send(self, text):
        from launcher_chat import send_input
        from launcher_question import submit
        if not self.current():
            raise ValueError('Session changed; review the current session before sending.')
        if self.panel.question:
            question = self.panel.question.question
            options = question['options']
            choice = int(text.strip()) - 1 if text.strip() in ('1', '2', '3') else len(options)
            submit(self.run, question['id'], min(choice, len(options)), text)
        elif self.panel.input_mode == 'chat':
            send_input(self.run, 'message', text,
                       expected_session=self.panel.chat_state.get('session'))
        else:
            raise ValueError('This session accepts input when a developer decision is pending.')

    def feed(self, data):
        from launcher_chat import send_input
        if self.panel is None or not self.current():
            return
        if data in (b'\x03', b'\x1b') and not self.panel.editor.paste:
            if self.panel.input_mode == 'chat':
                try:
                    send_input(self.run, 'interrupt', cancel_waiting=data == b'\x03',
                               expected_session=self.panel.chat_state.get('session'))
                except (OSError, ValueError) as error:
                    self.panel.editor.error = str(error)
        elif data in (b'\x1b[5~', b'\x1b[6~'):
            self.scroll(self.panel.output_height * (1 if data == b'\x1b[5~' else -1))
        elif self.panel.input_mode == 'chat':
            self.panel.editor.feed(data)
        elif self.panel.question:
            self.panel.question.feed(data)

    def scroll(self, rows):
        if self.panel:
            self.panel.offsets['bottom'] = max(0, self.panel.offsets['bottom'] + rows)

    def poll(self):
        from launcher_session import SessionPanel
        from launcher_question import QuestionInput, submit
        owner, run, state, source = self.discover()
        if run is None:
            self.owner = self.run = self.identity = self.panel = None
            self.offset = 0
            self.decoder.reset()
            return False, False, b''
        reset = (run, state['session']) != (self.run, self.identity)
        if reset:
            self.owner, self.run, self.identity = owner, run, state['session']
            self.panel = SessionPanel(io.StringIO(), send=self.send, terminal_size=self.terminal_size)
            self.offset = 0
            self.decoder.reset()
        panel = self.panel
        panel.input_mode = 'chat' if state['interactive'] else 'question'
        panel.chat_state = state
        try:
            chat = self.reader.read(run / 'chat-state.json')
            if state['interactive'] and isinstance(chat, dict):
                panel.chat_state = chat
            elif state['interactive']:
                panel.chat_state = dict(session=None, status='starting')
        except (OSError, ValueError):
            if state['interactive']:
                panel.chat_state = dict(session=None, status='starting')
        # Workflow transitions can publish only mailbox/lifecycle fields.
        # Keep the supervisor's display metadata without reusing its input identity.
        for name in ('model', 'effort'):
            if name not in panel.chat_state and name in state:
                panel.chat_state[name] = state[name]
        try:
            question = self.reader.read(run / 'question.json')
            if question.get('answer') is not None:
                question = None
        except (OSError, ValueError):
            question = None
        previous = panel.question.question['id'] if panel.question else None
        if (question['id'] if question else None) != previous:
            panel.question = QuestionInput(question, lambda identity, choice, text:
                submit(run, identity, choice, text) if self.current() else False) if question else None
        panel.details = ([question['question'],
            *[f'{index + 1}. {option}' for index, option in enumerate(question['options'])],
            'Type a number or your own instructions below.'] if question else [])
        try:
            with open_private(run / source) as stream:
                size = os.fstat(stream.fileno()).st_size
                if size < self.offset:
                    self.offset = 0
                    panel.transcript.clear()
                    panel.pending = ''
                    self.decoder.reset()
                start = max(self.offset, size - TAIL_BYTES)
                stream.seek(start)
                if start > self.offset:
                    stream.readline(TAIL_BYTES)
                data = stream.read(min(TAIL_BYTES, max(0, size - stream.tell())))
                self.offset = stream.tell()
            panel.write(self.decoder.decode(data))
        except (OSError, ValueError):
            pass
        panel.draw()
        data = panel.stream.getvalue().encode('utf-8')
        panel.stream.seek(0)
        panel.stream.truncate()
        return True, reset, data


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
