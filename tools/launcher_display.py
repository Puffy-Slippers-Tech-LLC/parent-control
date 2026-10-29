"""Shared resizable task overview/totals and execution/input/status panes."""

import base64
import json
import os
import re
import shutil
import sys
import termios
import time

from rich.cells import get_character_cell_size
from rich.text import Text

from launcher_chat import TASK_STATUSES, read_state, send_input, task_info as read_task_info
from launcher_render import LauncherDisplay, clean, retained_tail, style_task_counts
from launcher_session import SessionPanel, clock_duration, working_duration


def error_status_lines(task_info, key, clock):
    """Shared Last Error/Status fields and observer fallback clock."""
    error = clean(task_info.get('last_error', '')).strip()
    has_error = bool(error and error != '-')
    status = task_info.get('status')
    if not has_error:
        status = 'Running'
    elif status not in TASK_STATUSES or status == 'Running':
        status = TASK_STATUSES[0]
    key = (*key, status)
    if clock is None or clock[0] != key:
        clock = (key, time.time())
    status_age = clock_duration(time.time() - task_info.get('status_at', clock[1]))
    last_error = Text('Last Error: ')
    last_error.stylize('bold', 0, len('Last Error:'))
    if has_error:
        last_error.append(error, style='red')
        error_at = task_info.get('last_error_at')
        if error_at is not None:
            last_error.append(f' ({clock_duration(time.time() - error_at)} ago)')
    else:
        last_error.append('-')
    status_line = Text('Status: ')
    status_line.stylize('bold', 0, len('Status:'))
    colors = dict(zip(TASK_STATUSES, ('#0098ff', '#0098ff', 'yellow', 'green', '#0098ff')))
    status_line.append(status, style=colors[status])
    status_line.append(f' ({status_age} ago)', style='#0098ff')
    return [last_error, Text(''), status_line], clock


class Divider:
    """A proportional split shared by the outer frames."""

    def __init__(self, ratio):
        self.ratio = ratio

    def width(self, width):
        return max(1, min(width - 2, round((width - 1) * self.ratio))) if width >= 3 else 1

    def move(self, column, width):
        self.ratio = min(.9, max(.1, (column - 1) / max(1, width - 1)))

    @staticmethod
    def line(dragging):
        return Text('│', style='#0098ff' if dragging else 'dim')


def owner_clock(run):
    try:
        record = json.loads((run.parent / 'current.json').read_text())
        return record if record.get('run') == run.name else {}
    except FileNotFoundError:
        return {}


class PanelSelection:
    """A stable screen snapshot, clipped to the panel where a drag began."""

    def __init__(self, rows, bounds, column, row):
        self.rows = [line.copy() for line in rows]
        self.bounds = bounds
        self.anchor = self.end = (row, column)
        self.active = True

    def move(self, column, row):
        left, right, top, bottom = self.bounds
        self.end = (min(bottom, max(top, row)), min(right, max(left, column)))

    @staticmethod
    def character_span(text, left, right):
        # Mouse columns count terminal cells, not Unicode code points. Include
        # whole wide characters and their trailing combining marks.
        position = 1
        start = end = None
        for index, char in enumerate(text):
            cells = get_character_cell_size(char)
            if cells and position <= right and position + cells > left:
                if start is None:
                    start = index
                end = index + 1
            elif not cells and end == index:
                end = index + 1
            position += cells
        return (start, end) if start is not None else (0, 0)

    def spans(self):
        if self.anchor == self.end:
            return
        first, last = sorted((self.anchor, self.end))
        left, right, _, _ = self.bounds
        for row in range(first[0], last[0] + 1):
            start, end = self.character_span(self.rows[row - 1].plain,
                first[1] if row == first[0] else left,
                last[1] if row == last[0] else right)
            yield row - 1, start, end

    def text(self):
        return clean('\n'.join(self.rows[row].plain[start:end].rstrip()
                              for row, start, end in self.spans()))

    def highlighted(self):
        rows = [line.copy() for line in self.rows]
        for row, start, end in self.spans():
            rows[row].stylize('reverse', start, end)
        return rows


class TaskDisplay(LauncherDisplay):
    def __init__(self, stream, *, run, input_mode='chat', totals=None, overview_current=False,
                 cancel_on_ctrl_c=False, execution_tabs=False, **kwargs):
        super().__init__(stream, **kwargs)
        self.observed_monotonic = time.monotonic()
        self.owner_clock = owner_clock(run)
        self.run = run
        self.input_mode = input_mode
        self.overview_current = overview_current
        self.cancel_on_ctrl_c = cancel_on_ctrl_c
        self.divider = Divider(.75)
        self.execution_tabs = execution_tabs
        self.execution_tab = 'active'
        self.execution_width = 0
        self.execution_first = 0
        self.execution_controls = []
        self.execution_tab_bounds = []
        self.execution_selection = []
        self.execution_grab = None
        self.execution_session = None
        self.execution_cursor = None
        self.dragging = None
        self.totals = totals
        self.task_totals = None
        self.runtime_tasks = None
        self.completed_before = None
        self.pointer = ''
        self.focus = 'chat' if input_mode == 'chat' else 'bottom'
        self.offsets['info'] = 0
        self.offsets['summary'] = 0
        self.offsets['session'] = 0
        self.description = {}
        self.top_scrollbar = None
        self.top_scrollbar_grab = None
        self.top_bottom_button = None
        self.chat_state = {}
        self.task_info = {}
        self.status_clock = None
        self.session_panel = SessionPanel(stream, send=self.submit)
        self.editor = self.session_panel.editor
        self.divider_column = 0
        self.top_divider_column = 0
        self.chat_top = 0
        self.chat_bounds = None
        self.simplified_bounds = None
        self.output_height = 0
        self.summary_bottom = 0
        self.escape_since = None
        self.mouse_pending = b''
        self.mouse_capture = True
        self.selection = None
        self.selection_panels = []
        self.visible_rows = []
        self.recap_printed = False
        self.reloading = False

    def __enter__(self):
        super().__enter__()
        self.enable_chat_input()
        return self

    def enable_chat_input(self):
        try:
            if self.input_fd is not None and self.input_mode == 'chat':
                # Deliver Ctrl+C to the conversation instead of the observer's
                # process signal handler. Restore the original flags on every exit.
                attributes = termios.tcgetattr(self.input_fd)
                # Keep Enter (CR) distinct from Ctrl+J (LF), including inside
                # modified-key sequences sent by the terminal.
                attributes[0] &= ~(termios.ICRNL | termios.INLCR | termios.IGNCR)
                attributes[3] &= ~termios.ISIG
                termios.tcsetattr(self.input_fd, termios.TCSANOW, attributes)
                # Request Shift+Enter reporting from xterm-compatible and
                # Kitty-protocol terminals; unsupported requests are ignored.
                self.stream.write('\033[?2004h\033[>4;2m\033[>1u')
                self.stream.flush()
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def attach(self, run, *, input_mode):
        """Keep the startup screen while adopting the published backend identity."""
        self.run = run
        self.execution_session = None
        self.log_path = run / 'output'
        self.owner_clock = owner_clock(run)
        self.input_mode = input_mode
        self.focus = 'chat' if input_mode == 'chat' else 'bottom'
        self.steps = []
        self.step_history.clear()
        self.enable_chat_input()
        self.set_mouse_mode()

    def submit(self, text):
        if self.execution_tabs and self.execution_session and self.execution_session.active:
            self.execution_session.send(text)
        elif self.question is not None:
            options = self.question.question['options']
            choice = int(text.strip()) - 1 if text.strip() in ('1', '2', '3') else len(options)
            if choice >= len(options):
                choice = len(options)
            self.question.send(self.question.question['id'], choice, text if choice == len(options) else '')
        else:
            send_input(self.run, 'message', text)

    def refresh_chat(self):
        if (self.execution_tabs or self.input_mode == 'chat') and self.tty:
            from watch_output import SessionOutput
            if self.execution_session is None:
                self.execution_session = SessionOutput(None, lambda: self.size or shutil.get_terminal_size(),
                    owner_run=self.run, embedded=True)
            session = self.execution_session
            if self.execution_tabs and session.panel:
                session.panel.offsets['bottom'] = self.offsets['session']
            _, reset, _ = session.poll()
            if self.execution_tabs and session.panel:
                self.offsets['session'] = session.panel.offsets['bottom']
                session.panel.editor = self.editor
            if reset:
                self.offsets['session'] = 0
        self.chat_state = read_state(self.run)
        self.task_info = read_task_info(self.run, self.chat_state.get('task_id'))
        self.refresh_description()
        if self.totals is not None:
            try:
                from launcher_runtime import task_counters
                runtime, totals, baseline = task_counters(
                    self.run, self.totals(), completed_before=self.completed_before)
                self.runtime_tasks, self.task_totals, self.completed_before = runtime, totals, baseline
                if self.tty:
                    self.steps = self.counter_steps(self.steps)
            except (OSError, ValueError):
                # A partially rewritten queue must not detach the observer or
                # replace the last valid totals with misleading zeroes.
                pass

    def update(self, steps, details):
        super().update(self.counter_steps(steps), details)

    def counter_steps(self, steps):
        if self.runtime_tasks is not None:
            return [self.runtime_tasks, *(step for step in steps if step['key'] != 'runtime-tasks')]
        return steps

    def refresh_description(self):
        try:
            value = json.loads((self.run / 'descriptive-output.json').read_text())
            if (not isinstance(value, dict) or not isinstance(value.get('session'), str)
                    or not isinstance(value.get('lines'), list)
                    or any(not isinstance(line, str) for line in value['lines'])):
                return
            value['lines'] = list(retained_tail(value['lines']))
        except FileNotFoundError:
            value = {}
        except (OSError, ValueError):
            return
        self.description = value

    def output_width(self):
        if self.execution_tabs:
            return max(1, self.execution_width - int(self.mouse_capture))
        return max(1, self.divider_column - 1 - int(self.mouse_capture))

    def execution_source(self):
        if self.execution_tab == 'active':
            return 'session' if self.execution_session and self.execution_session.active else 'launcher'
        return self.execution_tab

    def execution_layout(self, width, height, logs, first):
        """Compose tabbed output from the shared pane controls."""
        self.execution_width, self.execution_first = width, first
        content_left = 1
        content_width = max(1, width)
        self.execution_controls = []
        self.execution_selection = []
        self.execution_tab_bounds = []
        self.execution_cursor = None
        self.chat_bounds = None
        self.simplified_bounds = None
        if width < 3:
            self.output_height = 0
            self.chat_top = first + height
            return [Text(' ' * width) for _ in range(height)]
        session = self.execution_session
        active = bool(session and session.active)
        source = self.execution_source()
        tabs = Text()
        for name, label in (('active', 'Active (Session)' if active else 'Active (Launcher)'),
                            ('session', 'Session'), ('launcher', 'Launcher')):
            start = tabs.cell_len + content_left
            tabs.append(' ' + label + ' ', style='bold reverse' if name == self.execution_tab else 'dim')
            self.execution_tab_bounds.append((name, start, min(width, content_left + tabs.cell_len - 1)))
        tabs.truncate(content_width, overflow='crop')
        tabs.pad_right(max(0, content_width - tabs.cell_len))
        body_height = max(0, height - 1)
        panel = session.panel if source == 'session' and active else None
        pane = 'session' if source == 'session' else 'bottom'
        if panel is None:
            body = self.scroll_rows(pane, ['No active session'] if source == 'session' else logs,
                max(1, content_width - int(self.mouse_capture)), body_height)
            output_height = body_height
        else:
            logs = [*panel.transcript, *([panel.pending] if panel.pending else []), *panel.details]
            body = panel.layout(content_width, body_height, logs,
                scroll=lambda _pane, lines, columns, rows: self.scroll_rows(pane, lines, columns, rows),
                output_width=max(1, content_width - int(self.mouse_capture)),
                input_mode='chat' if session.input_enabled else 'none',
                question=panel.question, working=panel.working(),
                session_logs=[*panel.transcript, *([panel.pending] if panel.pending else [])])
            output_height = panel.output_height
            # Keep the shared transcript's append/scroll anchoring at this viewport width.
            panel.size = os.terminal_size((content_width + int(not self.mouse_capture), body_height))
            panel.offsets['bottom'] = self.offsets['session']
        self.output_height = output_height
        self.chat_top = first + 1 + output_height
        self.chat_bounds = None
        if panel and panel.chat_bounds:
            left_edge, right_edge, top, bottom_edge = panel.chat_bounds
            self.chat_bounds = (left_edge + content_left - 1, right_edge + content_left - 1,
                                top + first, bottom_edge + first)
        if panel and panel.simplified_bounds:
            left_edge, right_edge, footer = panel.simplified_bounds
            self.simplified_bounds = (left_edge, right_edge, footer + first)
        if panel and panel.cursor:
            row, column = panel.cursor
            self.execution_cursor = (row + first, column + content_left - 1)
        body += [Text('')] * (body_height - len(body))
        scrollbar, bottom = self.scrollbar_controls(pane, content_width, output_height, first + 1)
        self.execution_controls.append((pane, scrollbar, bottom, width))
        for index, row in enumerate(body):
            body[index] = self.scrollbar_row(row, content_width, first + 1 + index, scrollbar, bottom)
        self.execution_selection.append((content_left, max(content_left, width - int(self.mouse_capture)),
                                         first + 1, first + output_height))
        return [tabs, *body] if height else []

    def overview_lines(self, step):
        """Normalize retained completions from older, still-running backends."""
        if not step.get('replaces') or not step['lines']:
            return step['lines']
        text = Text.from_ansi(step['lines'][0])
        if not re.match(r'^(?:✓ )?Task [\w.-]+:', text.plain):
            return step['lines']
        suffix = re.search(r'\s+[—–-]\s+complete\.?$', text.plain, re.IGNORECASE)
        if suffix:
            text = text[:suffix.start()]
        duration = re.search(r'\s+\((?:sessions=\d+,\s*duration=)?(\d+(?:h \d+m|m)|duration unavailable)\)$',
                             text.plain)
        elapsed = duration[1] if duration else 'duration unavailable'
        if duration:
            text = text[:duration.start()]
        if not text.plain.startswith('✓ '):
            text = Text('✓ ') + text
        text.append(f' ({elapsed})')
        text.stylize('green')
        with self.console.capture() as capture:
            self.console.print(text, end='', soft_wrap=True)
        return [capture.get()]

    def overview(self):
        """Full top-left content, independent of viewport size and scrolling."""
        pinned = [line for s in self.steps if s.get('pinned') for line in s['lines']]
        current = next((s for s in reversed(self.steps)
                        if not s.get('pinned') and not s.get('replaces')), None)
        history = [line for s in self.steps if not s.get('pinned') and
                   (s.get('replaces') or (s is not current and len(s['lines']) == 1))
                   for line in self.overview_lines(s)]
        if self.input_mode != 'chat' or self.overview_current:
            history = [self.overview_lines(s)[0] for s in self.steps
                       if not s.get('pinned') and s['lines']]
        return pinned, history

    def close(self):
        if self.reloading:
            self.restore_terminal()
            return
        super().close()
        if self.recap_printed:
            return
        self.recap_printed = True
        pinned, history = self.overview()
        lines = pinned + history
        # The saved transcript is replayed first. Leave the complete overview
        # and exit timing last, even when the live pane was scrolled/clipped.
        self.stream.write('\n')
        for line in lines:
            if self.tty:
                text = Text.from_ansi(line)
                self.style_task_label(text)
                self.console.print(text, soft_wrap=True)
            else:
                self.stream.write(clean(line) + '\n')
        origin = self.owner_clock.get('started_monotonic', self.observed_monotonic)
        for label, value in (('Ended:', time.strftime('%I:%M')),
                             ('Duration:', clock_duration(time.monotonic() - origin))):
            if self.tty:
                text = Text(f'{label} {value}')
                text.stylize('bold', 0, len(label))
                self.console.print(text, soft_wrap=True)
            else:
                self.stream.write(f'{label} {value}\n')
        try:
            result = json.loads((self.run / 'result.json').read_text())
            checkpoint = json.loads((self.run / 'checkpoint.json').read_text())
            queue_complete = (result.get('status') == 0
                              and checkpoint.get('reason') == 'queue complete')
        except (OSError, ValueError, AttributeError):
            queue_complete = False
        if queue_complete:
            message = 'QUEUE COMPLETE'
            border = '=' * len(message)
            if self.tty:
                self.console.print(Text(border, style='green'), soft_wrap=True)
                self.console.print(Text(message, style='bold green'), soft_wrap=True)
                self.console.print(Text(border, style='green'), soft_wrap=True)
            else:
                self.stream.write(f'{border}\n{message}\n{border}\n')
        self.stream.flush()

    def reload_ready(self):
        """Defer replacement while input or an edited answer is unfinished."""
        editor, question = self.editor, self.question
        editing = (editor.text or editor.pending or editor.paste or editor.decoder.getstate()[0]
                   or self.input_pending or self.mouse_pending or self.dragging or self.selection
                   or self.scrollbar_grab is not None or self.top_scrollbar_grab is not None
                   or self.execution_grab is not None
                   or self.escape_since is not None)
        answering = question and (question.text or question.buffer or question.pasting
                    or question.decoder.getstate()[0] or question.selected != 0)
        return not (editing or answering)

    def update_question(self, question, send):
        if self.input_mode != 'chat':
            # A decision must not silently disable wheel/scrollbar controls.
            capture = self.mouse_capture
            super().update_question(question, send)
            if self.mouse_capture != capture:
                self.mouse_capture = capture
                self.set_mouse_mode()
                self.draw()
            return
        # Keep the mouse preference and always-editable composer while blocked.
        from launcher_question import QuestionInput
        identity = self.question.question['id'] if self.question else None
        if (question['id'] if question else None) != identity:
            self.question = QuestionInput(question, send) if question else None
            self.draw()

    def set_mouse_mode(self):
        # Wheel events belong to the panes by default. F2 releases the mouse
        # for native terminal selection and context menus in every display.
        super().set_mouse_mode()
        self.selection = None
        self.scrollbar_grab = None
        self.top_scrollbar_grab = None
        self.execution_grab = None
        if not self.mouse_capture:
            self.dragging = None
            self.set_pointer('')
        elif self.input_fd is not None and self.input_mode == 'chat':
            self.stream.write('\033[?1002l\033[?1003h\033[?1006h')
            self.stream.flush()

    def set_pointer(self, shape):
        if shape != self.pointer:
            self.pointer = shape
            self.stream.write('\033]22;' + shape + '\033\\')
            self.stream.flush()

    def poll_input(self):
        super().poll_input()
        # Escape also prefixes navigation, mouse and modified-key sequences.
        # Allow fragmented reads to complete before treating it as a shortcut.
        if self.escape_since is not None and time.monotonic() - self.escape_since >= .1:
            self.input_pending = b''
            self.escape_since = None
            self.focus = 'chat'
            send_input(self.run, 'interrupt', cancel_waiting=False)
            self.draw()

    def handle_input(self, data):
        if self.input_mode != 'chat':
            self.mouse_pending += data
            while self.mouse_pending:
                if self.question and self.question.pasting:
                    self.question.feed(self.mouse_pending[:1])
                    self.mouse_pending = self.mouse_pending[1:]
                    continue
                toggles = (b'\x1bOQ', b'\x1b[12~')
                keys = toggles + (b'\x1b[5~', b'\x1b[6~', b'\x1b[200~', b'\x1b[201~')
                key = next((key for key in keys if self.mouse_pending.startswith(key)), None)
                if key:
                    self.selection = None
                    self.mouse_pending = self.mouse_pending[len(key):]
                    if key in toggles:
                        self.mouse_capture = not self.mouse_capture
                        self.set_mouse_mode()
                    else:
                        super().handle_input(key)
                    continue
                if any(key.startswith(self.mouse_pending) for key in keys):
                    break
                match = re.match(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', self.mouse_pending)
                if match:
                    self.mouse_pending = self.mouse_pending[match.end():]
                    if self.mouse_capture:
                        self.mouse(*map(int, match.groups()[:3]), match[4] == b'm')
                elif (b'\x1b[<'.startswith(self.mouse_pending) or
                      self.mouse_pending.startswith(b'\x1b[<') and len(self.mouse_pending) < 64):
                    break
                else:
                    split = self.mouse_pending.find(b'\x1b', 1)
                    value = self.mouse_pending if split < 0 else self.mouse_pending[:split]
                    self.mouse_pending = b'' if split < 0 else self.mouse_pending[split:]
                    self.selection = None
                    super().handle_input(value)
            self.draw()
            return
        self.input_pending += data
        while self.input_pending:
            if self.editor.paste:
                self.editor.feed(self.input_pending[:1])
                self.input_pending = self.input_pending[1:]
                continue
            match = re.match(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', self.input_pending)
            if match:
                self.input_pending = self.input_pending[match.end():]
                button, column, row = map(int, match.groups()[:3])
                if self.mouse_capture:
                    self.mouse(button, column, row, match[4] == b'm')
                continue
            if self.input_pending.startswith(b'\x1b[<'):
                if len(self.input_pending) < 64:
                    break
                self.input_pending = b''
                continue
            if b'\x1b[<'.startswith(self.input_pending):
                break
            navigation = (b'\x1b[5~', b'\x1b[6~')
            mouse_keys = (b'\x1bOQ', b'\x1b[12~')  # F2: xterm and VT forms.
            interrupt_keys = (b'\x03', b'\x1b[99;5u', b'\x1b[27;5;99~')
            tab_keys = (b'\x1b1', b'\x1b2', b'\x1b3') if self.execution_tabs else ()
            keys = navigation + mouse_keys + interrupt_keys + tab_keys
            key = next((key for key in keys if self.input_pending.startswith(key)), None)
            if key:
                self.selection = None
                self.input_pending = self.input_pending[len(key):]
                if key in tab_keys:
                    self.execution_tab = ('active', 'session', 'launcher')[tab_keys.index(key)]
                    self.focus = 'session' if self.execution_source() == 'session' else 'bottom'
                elif key in interrupt_keys:
                    self.focus = 'chat'
                    if self.cancel_on_ctrl_c:
                        # Repair cancellation belongs to the workflow owner,
                        # including while its agent lives in a child pipeline.
                        (self.run / 'cancel').touch(mode=0o600)
                    else:
                        send_input(self.run, 'interrupt')
                elif key in mouse_keys:
                    self.mouse_capture = not self.mouse_capture
                    self.set_mouse_mode()
                else:
                    pane = self.focus if self.focus in ('top', 'session') else 'bottom'
                    if self.execution_tabs and self.focus in ('bottom', 'session', 'chat'):
                        pane = 'session' if self.execution_source() == 'session' else 'bottom'
                    height = {'top': self.top_height,
                              'session': self.output_height, 'bottom': self.output_height}[pane]
                    self.offsets[pane] = max(0, self.offsets[pane] +
                        (max(1, height) if key == navigation[0] else -max(1, height)))
                continue
            if any(key.startswith(self.input_pending) for key in keys):
                break
            byte = self.input_pending[:1]
            self.input_pending = self.input_pending[1:]
            self.selection = None
            if self.execution_tabs and not self.chat_bounds:
                continue
            # All typing goes to the visible composer even while output is focused.
            self.focus = 'chat'
            self.editor.feed(byte)
        if self.input_pending == b'\x1b' and not self.editor.paste:
            if self.escape_since is None:
                self.escape_since = time.monotonic()
        else:
            self.escape_since = None
        self.draw()

    def mouse(self, button, column, row, released):
        base = button & ~28
        if base == 0 and not released and self.simplified_bounds:
            left, right, footer = self.simplified_bounds
            if left <= column <= right and row == footer:
                panel = (self.execution_session.panel if self.execution_tabs and self.execution_session
                         else self.session_panel)
                if panel and panel.simplified_bounds:
                    panel.toggle_at(column, panel.simplified_bounds[2])
                    pane = 'session' if self.execution_tabs else 'bottom'
                    self.offsets[pane] = 0
                    self.selection = None
                    self.draw()
                    return
        if self.selection and self.selection.active and (released or base == 32):
            self.selection.move(column, row)
            if released:
                self.selection.active = False
                text = self.selection.text()
                if text:
                    # OSC 52 writes only the explicit selection, never queries
                    # clipboard contents. Terminals may disable this operation.
                    encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
                    self.stream.write('\033]52;c;' + encoded + '\033\\')
                    self.stream.flush()
            self.draw()
            return
        if self.execution_tabs and self.execution_mouse(base, column, row, released):
            return
        over = ('top' if column == self.top_divider_column and 1 <= row <= self.top_height else
                'bottom' if column == self.divider_column and row > self.top_height + 1 else None)
        if released:
            self.dragging = None
            self.scrollbar_grab = None
            self.top_scrollbar_grab = None
        shape = ''
        if over or self.dragging:
            shape = 'ew-resize'
        elif (self.simplified_bounds and self.simplified_bounds[0] <= column <= self.simplified_bounds[1]
              and row == self.simplified_bounds[2]):
            shape = 'pointer'
        elif self.chat_bounds:
            left, right, top, bottom = self.chat_bounds
            if left <= column <= right and top <= row <= bottom:
                shape = 'text'
        self.set_pointer(shape)
        if released:
            self.draw()
            return
        if base == 0:
            self.selection = None
            self.dragging = None
            self.scrollbar_grab = None
            self.top_scrollbar_grab = None
        for pane, scrollbar, bottom_button, grab_name in (
                ('top', self.top_scrollbar, self.top_bottom_button, 'top_scrollbar_grab'),
                ('bottom', self.scrollbar, self.bottom_button, 'scrollbar_grab')):
            if self.scrollbar_mouse(pane, scrollbar, bottom_button, grab_name, base, column, row):
                return
        if base == 0 and over:
            self.dragging = over
            self.draw()
        elif base == 32 and self.dragging and self.size:
            self.divider.move(column, self.size.columns - 1)
            self.draw()
        elif base == 0:
            for bounds in self.selection_panels:
                left, right, top, bottom = bounds
                if left <= column <= right and top <= row <= bottom:
                    self.selection = PanelSelection(self.visible_rows, bounds, column, row)
                    break
            if row <= self.top_height:
                if column < self.top_divider_column:
                    self.focus = 'top'
                return
            if column > self.divider_column:
                self.focus = 'info'
                return
            self.focus = ('bottom' if self.input_mode != 'chat' or
                          column < self.divider_column and row < self.chat_top else 'chat')
        elif base in (64, 65):
            self.selection = None
            if row <= self.top_height and column >= self.top_divider_column:
                return
            if self.input_mode == 'chat' and column < self.divider_column and row >= self.chat_top:
                return
            pane = ('top' if row <= self.top_height else 'bottom' if column < self.divider_column else
                    'summary' if row <= self.summary_bottom else 'info')
            delta = 3 if base == 64 else -3
            self.offsets[pane] = max(0, self.offsets[pane] + (-delta if pane in ('summary', 'info') else delta))
            self.draw()

    def scrollbar_controls(self, pane, width, height, first):
        """Shared left-panel geometry, with a pinned return-to-bottom button."""
        bottom_button = ((width, first + height - 1)
                         if self.mouse_capture and height > 0 and width > 1 else None)
        track_height = height - bool(bottom_button)
        total = len(self.row_cache[pane][1])
        scrollbar = None
        if self.mouse_capture and width > 1 and track_height > 0 and total > height:
            thumb = max(1, min(track_height, round(track_height * height / total)))
            travel = track_height - thumb
            limit = total - height
            start = round(travel * (limit - self.offsets[pane]) / limit)
            scrollbar = (first, start, thumb, travel, limit)
        return scrollbar, bottom_button

    @staticmethod
    def scrollbar_row(row, width, screen_row, scrollbar, bottom_button):
        """Paint either left panel's scrollbar and button with identical styling."""
        row = row.copy()
        marker, style = '', 'dim'
        if scrollbar and scrollbar[0] <= screen_row < scrollbar[0] + scrollbar[2] + scrollbar[3]:
            first, start, thumb, _, _ = scrollbar
            marker = '█' if start <= screen_row - first < start + thumb else '░'
        if bottom_button and screen_row == bottom_button[1]:
            marker, style = '↓', 'bold reverse'
        content_width = width - bool(marker)
        row.truncate(content_width, overflow='crop')
        row.pad_right(max(0, content_width - row.cell_len))
        if marker:
            row += Text(marker, style=style)
        return row

    def execution_mouse(self, base, column, row, released):
        """Route nested pane controls before the enclosing frame handles its own."""
        inside = (self.execution_first <= row and 1 <= column < self.divider_column)
        if not (inside or self.execution_grab is not None):
            return False
        if self.dragging:
            return False
        if released:
            self.execution_grab = None
            self.set_pointer('')
            self.draw()
            return True
        if base == 0:
            self.execution_grab = None
            if row == self.execution_first:
                for name, left, right in self.execution_tab_bounds:
                    if left <= column <= right:
                        self.selection = None
                        self.execution_tab = name
                        self.focus = 'session' if self.execution_source() == 'session' else 'bottom'
                        self.draw()
                        return True
        for pane, scrollbar, bottom, edge in self.execution_controls:
            if self.scrollbar_mouse(pane, scrollbar, bottom, 'execution_grab',
                    base, column, row, edge=edge,
                    allow_drag=self.focus == pane):
                return True
        pane = 'session' if self.execution_source() == 'session' else 'bottom'
        self.set_pointer('pointer' if self.simplified_bounds
                         and self.simplified_bounds[0] <= column <= self.simplified_bounds[1]
                         and row == self.simplified_bounds[2] else
                         'text' if self.chat_bounds and self.chat_bounds[0] <= column <= self.chat_bounds[1]
                         and self.chat_bounds[2] <= row <= self.chat_bounds[3] else '')
        if base in (64, 65):
            if row >= self.chat_top:
                return True
            self.selection = None
            self.offsets[pane] = max(0, self.offsets[pane] + (3 if base == 64 else -3))
            self.draw()
        elif base == 0:
            self.focus = pane
            self.selection = None
            for bounds in self.selection_panels:
                left, right, top, bottom = bounds
                if left <= column <= right and top <= row <= bottom:
                    self.selection = PanelSelection(self.visible_rows, bounds, column, row)
                    break
        return True

    def scrollbar_mouse(self, pane, scrollbar, bottom_button, grab_name, base, column, row,
                        *, edge=None, allow_drag=True):
        """Handle button clicks, track clicks and captured thumb drags for either pane."""
        if base == 0 and bottom_button == (column, row):
            self.offsets[pane] = 0
            self.focus = pane
        elif base == 32 and allow_drag and getattr(self, grab_name) is not None and scrollbar:
            first, _, _, travel, limit = scrollbar
            position = min(travel, max(0, row - first - getattr(self, grab_name)))
            if travel:
                self.offsets[pane] = round(limit * (travel - position) / travel)
        elif (base == 0 and scrollbar and column == (edge if edge is not None else self.divider_column - 1)
              and scrollbar[0] <= row < scrollbar[0] + scrollbar[2] + scrollbar[3]):
            first, start, thumb, travel, limit = scrollbar
            position = row - first
            self.focus = pane
            if start <= position < start + thumb:
                setattr(self, grab_name, position - start)
            else:
                self.offsets[pane] = round(limit *
                    (thumb + travel - 1 - position) / max(1, thumb + travel - 1))
        else:
            return False
        self.draw()
        return True

    def draw(self):
        if not self.tty:
            return
        try:
            size = self.terminal_size() if self.terminal_size else os.get_terminal_size(self.stream.fileno())
        except (OSError, ValueError):
            size = shutil.get_terminal_size()
        current = next((s for s in reversed(self.steps) if not s.get('pinned') and not s.get('replaces')), None)
        summary_lines = list(current['lines']) if current else ['Waiting for task…']
        started = self.chat_state.get('started_at')
        # The clock belongs to the owner session, so reconnecting observers use
        # the same origin and a new task never inherits the previous clock.
        session = self.chat_state.get('task_session', self.chat_state.get('session'))
        owns_session = (current and current['key'] == self.chat_state.get('progress_key')
                and started is not None and len(summary_lines) > 1
                and clean(summary_lines[-1]).startswith((f'Session [{session}]:', f'Session {session}:')))
        working = ''
        if owns_session:
            ended = self.chat_state.get('finished_at', time.time())
            summary_lines[-1] = (summary_lines[-1].split(':', 1)[0] + ': '
                                 + clock_duration(ended - started))
            if self.input_mode == 'chat' and self.chat_state.get('status') == 'running':
                turn_started = self.chat_state.get('turn_started_at', started)
                working = f'Working ({working_duration(time.time() - turn_started)})'
        origin = self.owner_clock.get('started_monotonic')
        total_duration = clock_duration(time.monotonic() - origin) if origin is not None else '—'
        task_info = (self.task_info if self.task_info.get('task_id') == self.chat_state.get('task_id')
                     and (not current or self.chat_state.get('progress_key') in (None, current['key'])) else {})
        info_lines, self.status_clock = error_status_lines(task_info,
            (current['key'] if current else None, self.chat_state.get('task_id')), self.status_clock)
        session_panel = self.execution_session.panel if self.execution_session else None
        session_state = (self.execution_session.active, self.execution_session.identity,
                         tuple(session_panel.transcript), session_panel.pending,
                         json.dumps(session_panel.chat_state, sort_keys=True),
                         tuple(session_panel.details), session_panel.simplified,
                         tuple(session_panel.text_output or [])) if session_panel else None
        state = (size, self.divider.ratio, self.execution_tab,
                 session_state, self.session_panel.simplified, self.dragging, self.task_totals,
                 tuple(summary_lines), total_duration, working, tuple(line.plain for line in info_lines),
                 tuple((s['key'], tuple(s['lines']), bool(s.get('replaces')),
                 bool(s.get('pinned'))) for s in self.steps), tuple(self.details),
                 tuple(self.transcript), self.pending, tuple(self.offsets.items()),
                 json.dumps(self.description, sort_keys=True),
                 self.editor.text, self.editor.cursor, self.editor.error,
                 json.dumps(self.task_info, sort_keys=True), json.dumps(self.chat_state, sort_keys=True),
                 (self.question.question['id'], self.question.selected, self.question.text)
                 if self.question else None, self.focus, self.mouse_capture,
                 (self.selection.anchor, self.selection.end, self.selection.active)
                 if self.selection else None)
        if self.screen and state == self.draw_state:
            return
        width, height = max(1, size.columns - 1), max(1, size.lines)
        left_width = self.divider.width(width)
        right_width = max(1, width - left_width - 1)
        self.top_divider_column = self.divider_column = left_width + 1
        completed, unfinished, total = self.task_totals or ('—', '—', '—')
        totals = Text(f'Total Tasks: {completed}/{unfinished}/{total}')
        style_task_counts(totals)
        totals.append('\nTotal Duration: ' + total_duration)
        top_capacity = min(5, max(0, height - 4))
        total_rows = totals.wrap(self.console, right_width, overflow='fold')[:top_capacity]
        pinned, history = self.overview()
        # Keep runtime counters in retained output/exit recaps, outside the live
        # overview. All remaining rows share its bottom-following viewport.
        overview = [line for line in pinned + history
                    if not re.match(r'^Tasks: ', clean(line))]
        top = self.scroll_rows('top', overview, max(1, left_width - int(self.mouse_capture)), top_capacity)
        top += [Text('')] * max(0, len(total_rows) - len(top))
        self.top_scrollbar, self.top_bottom_button = self.scrollbar_controls(
            'top', left_width, len(top), 1)
        for index, row in enumerate(top):
            row = self.scrollbar_row(row, left_width, index + 1,
                                     self.top_scrollbar, self.top_bottom_button)
            # Keep pane base styles scoped to their own text, not the full row.
            top[index] = Text.assemble(row, self.divider.line(self.dragging in ('top', 'bottom')))
            if index < len(total_rows):
                top[index] += total_rows[index]
        self.top_height = len(top)
        available = max(0, height - len(top) - 1)
        separator = [Text('─' * right_width, style='dim')] if available >= 5 else []
        summary = self.wrapped(summary_lines, right_width, task_labels=True)
        summary_height = min(len(summary), max(0, available // 2),
                             max(0, available - len(separator) - 1))
        summary = self.from_top('summary', summary_lines, right_width, summary_height)
        self.summary_bottom = len(top) + 1 + summary_height
        lifecycle = {
            'waiting': 'Interrupted. Waiting for your instructions. Ctrl+C again exits.',
            'interrupting': 'Interrupting the current work…',
            'cleaning': 'Finishing cleanup before accepting more instructions…',
            'blocked': 'Waiting for your answer below.',
            'finished': 'Session finished. Preparing the next step.',
        }.get(self.chat_state.get('status'))
        if lifecycle:
            info_lines[0:0] = [lifecycle, '']
        if self.question:
            notices = ['', self.question.question.get('explanation', '')]
            if self.input_mode == 'chat':
                notices += [self.question.question['question'],
                               *[f'{i + 1}. {option}' for i, option in enumerate(self.question.question['options'])],
                               'Type a number or your own instructions below.']
            info_lines[0:0] = notices

        logs = [*self.transcript, *([self.pending] if self.pending else []), *self.details]
        if not self.execution_tabs and self.details and clean(self.details[0]).startswith('VM pipelines | concurrency '):
            # The live pipeline frame replaces earlier command output. Keep
            # the transcript for saved logs and replay after the frame closes.
            logs = self.details
        self.session_panel.chat_state = self.chat_state
        self.scroll_transcript = (self.execution_tabs or self.input_mode != 'chat'
                                  or not self.session_panel.simplified)
        if self.input_mode == 'chat' and not self.execution_tabs:
            self.session_panel.offsets['bottom'] = self.offsets['bottom']
            description = (self.description if not current or
                self.description.get('progress_key') in (None, current['key']) else {})
            self.session_panel.update_text_output(description)
            self.offsets['bottom'] = self.session_panel.offsets['bottom']
        if self.execution_tabs:
            left = self.execution_layout(left_width, available,
                [*self.transcript, *([self.pending] if self.pending else [])],
                len(top) + 2)
        else:
            left = self.session_panel.layout(left_width, available, logs, scroll=self.scroll_rows,
                output_width=self.output_width(), input_mode=self.input_mode,
                question=self.question, working=working,
                session_logs=[*session_panel.transcript,
                              *([session_panel.pending] if session_panel.pending else [])]
                             if session_panel else [])
            self.output_height = self.session_panel.output_height
        remaining = max(0, available - summary_height - len(separator))
        info_height = min(len(self.wrapped(info_lines, right_width)), remaining)
        info = self.from_top('info', info_lines, right_width, info_height)
        info += [Text('')] * (info_height - len(info))
        right = summary + separator + info
        right = right[:available]
        right += [Text('')] * (available - len(right))
        if not self.execution_tabs:
            self.chat_top = len(top) + 1 + self.output_height + 1
            self.chat_bounds = self.session_panel.chat_bounds
            self.simplified_bounds = self.session_panel.simplified_bounds
            if self.simplified_bounds:
                left_edge, right_edge, footer = self.simplified_bounds
                self.simplified_bounds = (left_edge, right_edge, footer + len(top) + 1)
            if self.chat_bounds:
                left_edge, right_edge, first, last = self.chat_bounds
                self.chat_bounds = (left_edge, right_edge, first + len(top) + 1, last + len(top) + 1)
            self.scrollbar, self.bottom_button = self.scrollbar_controls(
                'bottom', left_width, self.output_height, len(top) + 2)
        divider = Text('─' * width, style='dim')
        if self.input_fd is not None:
            key = 'F2' if self.input_mode == 'chat' else 'F2/m'
            action = 'native selection' if self.mouse_capture else 'scroll/resize'
            hint = 'Drag: select/copy panel · ' if self.mouse_capture else ''
            divider = Text(f' {hint}{key}: {action} ', style='dim')
            divider.truncate(width, overflow='crop')
            divider.append('─' * max(0, width - divider.cell_len))
        rows = top + [divider]
        for index in range(available):
            row = (left[index] if self.execution_tabs else
                   self.scrollbar_row(left[index], left_width, len(top) + 2 + index,
                                      self.scrollbar, self.bottom_button))
            rows.append(Text.assemble(row, self.divider.line(self.dragging in ('top', 'bottom')),
                                      right[index]))
        if width < 3:
            # Preserve terminal ownership without emitting over-wide rows.
            rows = [Text('')] * height
            self.bottom_button = None
            self.scrollbar = None
            self.top_bottom_button = None
            self.top_scrollbar = None
            self.simplified_bounds = None
        for row in rows:
            row.truncate(width, overflow='crop')
        self.selection_panels = [
            (1, max(1, left_width - int(self.mouse_capture)), 1, self.top_height),
            (left_width + 2, width, 1, self.top_height),
            (1, self.output_width(), self.top_height + 2,
             self.top_height + 1 + self.output_height),
            (left_width + 2, width, self.top_height + 2, height),
        ] if width >= 3 else []
        if self.execution_tabs and width >= 3:
            self.selection_panels[2:3] = self.execution_selection
        if self.chat_bounds:
            self.selection_panels.append(self.chat_bounds)
        elif self.input_mode != 'chat' and self.session_panel.editor_height and width >= 3:
            self.selection_panels.append((1, left_width, self.chat_top, height))
        self.paint(rows, size)
        cursor = self.execution_cursor if self.execution_tabs else self.session_panel.cursor
        if cursor and width >= 3:
            cursor_row, cursor_column = cursor
            cursor_row = min(height, cursor_row if self.execution_tabs else cursor_row + len(top) + 1)
            # Typing always edits chat, even while another pane is focused.
            # DECSCUSR: use the standard blinking underline cursor.
            self.stream.write(f'\033[{cursor_row};{cursor_column}H\033[3 q\033[?25h')
        else:
            self.stream.write('\033[?25l')
        self.stream.flush()
        self.draw_state = state

    def from_top(self, pane, lines, width, height):
        rows = self.wrapped(lines, width, task_labels=pane == 'summary')
        offset = self.offsets[pane] = min(self.offsets[pane], max(0, len(rows) - height))
        return rows[offset:offset + height]

    def paint(self, rows, size):
        if not self.screen:
            self.screen = True
            # Keep the shell and its scrollback outside the launcher. Output
            # scrolling belongs to the panes, never to the terminal viewport.
            self.stream.write('\033[?1049h\033[H\033[2J\033[?25l')
            self.set_mouse_mode()
            self.previous = None
        if size != self.size:
            self.selection = None
            self.stream.write('\033[H\033[2J')
            self.previous = None
        if self.selection:
            if self.selection.active or rows == self.selection.rows:
                rows = self.selection.highlighted()
            else:
                self.selection = None
        self.visible_rows = self.selection.rows if self.selection else [row.copy() for row in rows]
        for index, row in enumerate(rows):
            if (self.previous is None or index >= len(self.previous)
                    or row != self.previous[index] or row.style != self.previous[index].style):
                with self.console.capture() as capture:
                    self.console.print(row, width=size.columns, end='', soft_wrap=True)
                self.stream.write(f'\033[{index + 1};1H\033[2K' + capture.get())
        self.previous, self.size = rows, size

    def restore_terminal(self):
        try:
            if self.screen or self.input_fd is not None:
                self.stream.write('\033[?1003l\033]22;\033\\\033[0 q')
            if self.input_fd is not None:
                self.stream.write('\033[<u\033[>4;0m')
        finally:
            super().restore_terminal()
