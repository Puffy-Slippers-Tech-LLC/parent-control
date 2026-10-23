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

from launcher_chat import ChatEditor, TASK_STATUSES, read_state, send_input, task_info as read_task_info
from launcher_render import LauncherDisplay, clean, retained_tail, style_task_counts


def clock_duration(seconds):
    """Elapsed whole minutes, shared by launcher clocks and task-field ages."""
    hours, minutes = divmod(max(0, int(seconds // 60)), 60)
    return f'{hours}h {minutes}m' if hours else f'{minutes}m'


def working_duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f'{clock_duration(minutes * 60)} {seconds}s' if minutes else f'{seconds}s'


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
    def __init__(self, stream, *, run, input_mode='chat', totals=None, **kwargs):
        super().__init__(stream, **kwargs)
        self.observed_monotonic = time.monotonic()
        self.owner_clock = owner_clock(run)
        self.run = run
        self.input_mode = input_mode
        self.ratio = .75
        self.dragging = None
        self.totals = totals
        self.task_totals = None
        self.runtime_tasks = None
        self.completed_before = None
        self.pointer = ''
        self.focus = 'chat' if input_mode == 'chat' else 'bottom'
        self.offsets['info'] = 0
        self.offsets['summary'] = 0
        self.offsets['description'] = 0
        self.description = {}
        self.description_top = 0
        self.description_height = 0
        self.description_scrollbar = None
        self.description_grab = None
        self.top_scrollbar = None
        self.top_scrollbar_grab = None
        self.top_bottom_button = None
        self.chat_state = {}
        self.task_info = {}
        self.status_clock = None
        self.editor = ChatEditor(self.submit)
        self.divider_column = 0
        self.top_divider_column = 0
        self.chat_top = 0
        self.chat_bounds = None
        self.output_height = 0
        self.summary_bottom = 0
        self.escape_since = None
        self.mouse_pending = b''
        self.mouse_capture = True
        self.selection = None
        self.selection_panels = []
        self.visible_rows = []
        self.recap_printed = False

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
        self.log_path = run / 'output'
        self.owner_clock = owner_clock(run)
        self.input_mode = input_mode
        self.focus = 'chat' if input_mode == 'chat' else 'bottom'
        self.steps = []
        self.step_history.clear()
        self.enable_chat_input()
        self.set_mouse_mode()

    def submit(self, text):
        if self.question is not None:
            options = self.question.question['options']
            choice = int(text.strip()) - 1 if text.strip() in ('1', '2', '3') else len(options)
            if choice >= len(options):
                choice = len(options)
            self.question.send(self.question.question['id'], choice, text if choice == len(options) else '')
        else:
            send_input(self.run, 'message', text)

    def refresh_chat(self):
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
        if value.get('session') != self.description.get('session'):
            self.offsets['description'] = 0
            self.description_grab = None
        elif self.offsets['description'] and self.size and value != self.description:
            width = max(1, self.size.columns - self.divider_column - 1 - int(self.mouse_capture))
            self.offsets['description'] += max(0,
                len(self.wrapped(value.get('lines', []), width)) -
                len(self.wrapped(self.description.get('lines', []), width)))
        self.description = value

    def output_width(self):
        return max(1, self.divider_column - 1 - int(self.mouse_capture))

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
        if self.input_mode != 'chat':
            history = [self.overview_lines(s)[0] for s in self.steps
                       if not s.get('pinned') and s['lines']]
        return pinned, history

    def close(self):
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
        self.description_grab = None
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
            keys = navigation + mouse_keys
            key = next((key for key in keys if self.input_pending.startswith(key)), None)
            if key:
                self.selection = None
                self.input_pending = self.input_pending[len(key):]
                if key in mouse_keys:
                    self.mouse_capture = not self.mouse_capture
                    self.set_mouse_mode()
                else:
                    pane = self.focus if self.focus in ('top', 'description') else 'bottom'
                    height = {'top': self.top_height, 'description': self.description_height,
                              'bottom': self.output_height}[pane]
                    self.offsets[pane] = max(0, self.offsets[pane] +
                        (max(1, height) if key == navigation[0] else -max(1, height)))
                continue
            if any(key.startswith(self.input_pending) for key in keys):
                break
            byte = self.input_pending[:1]
            self.input_pending = self.input_pending[1:]
            self.selection = None
            if byte == b'\x03' and not self.editor.paste:
                self.focus = 'chat'
                send_input(self.run, 'interrupt')
            else:
                # All typing goes to the composer even while output is focused.
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
        over = ('top' if column == self.top_divider_column and 1 <= row <= self.top_height else
                'bottom' if column == self.divider_column and row > self.top_height + 1 else None)
        if released:
            self.dragging = None
            self.scrollbar_grab = None
            self.top_scrollbar_grab = None
            self.description_grab = None
        shape = ''
        if over or self.dragging:
            shape = 'ew-resize'
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
            self.description_grab = None
        for pane, scrollbar, bottom_button, grab_name in (
                ('top', self.top_scrollbar, self.top_bottom_button, 'top_scrollbar_grab'),
                ('bottom', self.scrollbar, self.bottom_button, 'scrollbar_grab')):
            if self.scrollbar_mouse(pane, scrollbar, bottom_button, grab_name, base, column, row):
                return
        if base == 32 and self.description_grab is not None and self.description_scrollbar:
            first, start, thumb, travel, limit = self.description_scrollbar
            position = min(travel, max(0, row - first - self.description_grab))
            if travel:
                self.offsets['description'] = round(limit * (travel - position) / travel)
            self.draw()
            return
        if (base == 0 and self.description_scrollbar and self.size
                and column == self.size.columns - 1
                and self.description_top <= row < self.description_top + self.description_height):
            first, start, thumb, travel, limit = self.description_scrollbar
            position = row - first
            self.focus = 'description'
            if start <= position < start + thumb:
                self.description_grab = position - start
            else:
                self.offsets['description'] = round(limit *
                    (thumb + travel - 1 - position) / max(1, thumb + travel - 1))
            self.draw()
            return
        if base == 0 and over:
            self.dragging = over
            self.draw()
        elif base == 32 and self.dragging and self.size:
            self.ratio = min(.9, max(.1, (column - 1) / max(1, self.size.columns - 2)))
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
            if column > self.divider_column and row >= self.description_top and self.description_height:
                self.focus = 'description'
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
                    'summary' if row <= self.summary_bottom else
                    'description' if row >= self.description_top and self.description_height
                    and self.description.get('lines') else 'info')
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

    def scrollbar_mouse(self, pane, scrollbar, bottom_button, grab_name, base, column, row):
        """Handle button clicks, track clicks and captured thumb drags for either pane."""
        if base == 0 and bottom_button == (column, row):
            self.offsets[pane] = 0
            self.focus = pane
        elif base == 32 and getattr(self, grab_name) is not None and scrollbar:
            first, _, _, travel, limit = scrollbar
            position = min(travel, max(0, row - first - getattr(self, grab_name)))
            if travel:
                self.offsets[pane] = round(limit * (travel - position) / travel)
        elif (base == 0 and scrollbar and column == self.divider_column - 1
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
        error_summary = clean(task_info.get('last_error', '')).strip()
        has_error = bool(error_summary and error_summary != '-')
        error_at = task_info.get('last_error_at') if has_error else None
        error_age = clock_duration(time.time() - error_at) if error_at is not None else None
        status = task_info.get('status')
        if not has_error:
            status = 'Running'
        elif status not in TASK_STATUSES or status == 'Running':
            status = TASK_STATUSES[0]
        status_key = (current['key'] if current else None, self.chat_state.get('task_id'), status)
        if self.status_clock is None or self.status_clock[0] != status_key:
            # Older backends and non-agent workflows have no retained status
            # timestamp. Measure from observation rather than inventing an age.
            self.status_clock = (status_key, time.time())
        status_at = task_info.get('status_at', self.status_clock[1])
        status_age = clock_duration(time.time() - status_at)
        state = (size, self.ratio, self.dragging, self.task_totals,
                 tuple(summary_lines), total_duration, working, error_age, status_age,
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
        left_width = max(1, min(width - 2, round((width - 1) * self.ratio))) if width >= 3 else 1
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
        top = self.scroll_rows('top', overview, self.output_width(), top_capacity)
        top += [Text('')] * max(0, len(total_rows) - len(top))
        self.top_scrollbar, self.top_bottom_button = self.scrollbar_controls(
            'top', left_width, len(top), 1)
        for index, row in enumerate(top):
            row = self.scrollbar_row(row, left_width, index + 1,
                                     self.top_scrollbar, self.top_bottom_button)
            top[index] = row + Text('│', style='#0098ff' if self.dragging else 'dim')
            if index < len(total_rows):
                top[index] += total_rows[index]
        self.top_height = len(top)
        available = max(0, height - len(top) - 1)
        boxed = left_width >= 5
        separator = [Text('─' * right_width, style='dim')] if available >= 5 else []
        show_hint = available >= 4
        # Reserve the bottom composer independently of session-output scrolling.
        # Very short terminals give up the hint first.
        chrome_height = 1 + int(boxed) + int(show_hint)
        summary = self.wrapped(summary_lines, right_width, task_labels=True)
        summary_height = min(len(summary), max(0, available // 2),
                             max(0, available - len(separator) - 1))
        summary = self.from_top('summary', summary_lines, right_width, summary_height)
        self.summary_bottom = len(top) + 1 + summary_height
        explanation = task_info.get('explanation', 'Preparing the task explanation…'
                                    if self.input_mode == 'chat' else 'Execution details appear on the left.')
        last_error = Text('Last Error: ')
        last_error.stylize('bold', 0, len('Last Error:'))
        if has_error:
            last_error.append(error_summary, style='red')
            if error_age is not None:
                last_error.append(f' ({error_age} ago)')
        else:
            last_error.append('-')
        # Only labels are bold; values keep their own normal/red styling.
        status_line = Text('Status: ')
        status_line.stylize('bold', 0, len('Status:'))
        colors = dict(zip(TASK_STATUSES, ('#0098ff', '#0098ff', 'yellow', 'green', '#0098ff')))
        status_line.append(status, style=colors[status])
        status_line.append(f' ({status_age} ago)', style='#0098ff')
        info_lines = [Text('Explanation:', style='bold'), Text(clean(explanation)),
                      Text('─'), last_error, Text(''), status_line]
        lifecycle = {
            'waiting': 'Interrupted. Waiting for your instructions. Ctrl+C again exits.',
            'interrupting': 'Interrupting the current work…',
            'cleaning': 'Finishing cleanup before accepting more instructions…',
            'blocked': 'Waiting for your answer below.',
            'finished': 'Session finished. Preparing the next step.',
        }.get(self.chat_state.get('status'))
        if lifecycle:
            info_lines[2:2] = ['', lifecycle]
        if self.question:
            notices = ['', self.question.question.get('explanation', '')]
            if self.input_mode == 'chat':
                notices += [self.question.question['question'],
                               *[f'{i + 1}. {option}' for i, option in enumerate(self.question.question['options'])],
                               'Type a number or your own instructions below.']
            info_lines[2:2] = notices

        editor_width = max(1, left_width - 4) if boxed else left_width
        editor_rows, caret_row, caret_column = self.editor_rows(editor_width)
        # Grow and shrink with content; a long draft scrolls around its caret
        # rather than escaping the terminal; leave room for output when possible.
        editor_capacity = max(0, available - chrome_height)
        editor_room = min(len(editor_rows), max(1, editor_capacity - 1) if editor_capacity else 0)
        editor_start = max(0, caret_row - editor_room + 1)
        editor_rows = editor_rows[editor_start:editor_start + editor_room]
        if self.input_mode != 'chat':
            editor_rows = self.wrapped(self.question.lines(left_width), left_width) if self.question else []
            editor_rows = editor_rows[-max(1, available // 2):]
            chrome_height = 0
        self.output_height = max(0, available - len(editor_rows) - chrome_height)
        logs = [*self.transcript, *([self.pending] if self.pending else []), *self.details]
        left = self.scroll_rows('bottom', logs, self.output_width(), self.output_height)
        left += [Text('')] * (self.output_height - len(left))
        remaining = max(0, available - summary_height - len(separator))
        description_lines = (self.description.get('lines', [])
                             if not current or self.description.get('progress_key') in (None, current['key']) else [])
        reserve = min(4, remaining) if description_lines else min(1, remaining)
        info_height = min(len(self.wrapped(info_lines, right_width)), max(0, remaining - reserve))
        info = self.from_top('info', info_lines, right_width, info_height)
        info += [Text('')] * (info_height - len(info))
        if remaining > info_height:
            info.append(Text('─' * right_width, style='dim'))
        self.description_top = len(top) + 2 + summary_height + len(separator) + len(info)
        self.description_height = max(0, remaining - len(info))
        description_width = max(1, right_width - int(self.mouse_capture))
        description_rows = self.scroll_rows('description', description_lines,
                                            description_width, self.description_height)
        description_rows += [Text('')] * (self.description_height - len(description_rows))
        self.description_scrollbar = None
        total_description = len(self.row_cache['description'][1])
        if self.mouse_capture and right_width > 1 and self.description_height > 0 and total_description > self.description_height:
            thumb = max(1, round(self.description_height * self.description_height / total_description))
            travel = self.description_height - thumb
            limit = total_description - self.description_height
            start = round(travel * (limit - self.offsets['description']) / limit)
            self.description_scrollbar = (self.description_top, start, thumb, travel, limit)
            for index, row in enumerate(description_rows):
                row = row.copy()
                row.pad_right(max(0, description_width - row.cell_len))
                description_rows[index] = row + Text('█' if start <= index < start + thumb else '░', style='dim')
        info += description_rows
        hint = Text(' '.join(filter(None, (self.chat_state.get('model'),
                                          self.chat_state.get('effort')))), style='dim')
        hint.truncate(left_width, overflow='crop')
        if self.editor.error:
            hint = Text(self.editor.error, style='red')
            hint.truncate(left_width, overflow='crop')
        label = ' Chat ' + (f'· {working} ' if working else '')
        border = Text('╭' + label[:max(0, left_width - 2)].ljust(max(0, left_width - 2), '─') + '╮', style='dim')
        border.truncate(left_width, overflow='crop')
        bottom = []
        if boxed and self.input_mode == 'chat':
            bordered = []
            for row in editor_rows:
                row = row.copy()
                row.pad_right(max(0, editor_width - row.cell_len))
                bordered.append(Text('│ ', style='dim') + row + Text(' │', style='dim'))
            editor_rows = bordered
            bottom = [Text('╰' + '─' * (left_width - 2) + '╯', style='dim')]
        if self.input_mode == 'chat':
            # Shade the full composer, including padding, without carrying its
            # background into the adjacent status pane or the model/effort line.
            for row in [border, *editor_rows, *bottom]:
                row.stylize('#333333 on #f4f4f4')
        left += ([border] + editor_rows + bottom + ([hint] if show_hint else [])
                 if self.input_mode == 'chat' else editor_rows)
        left = left[:available]
        right = summary + separator + info
        right = right[:available]
        right += [Text('')] * (available - len(right))
        self.chat_top = len(top) + 1 + self.output_height + 1
        self.chat_bounds = ((3 if boxed else 1, left_width - 2 if boxed else left_width,
                             self.chat_top + 1, min(height, self.chat_top + len(editor_rows)))
                            if self.input_mode == 'chat' and editor_rows and width >= 3 else None)
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
            row = self.scrollbar_row(left[index], left_width, len(top) + 2 + index,
                                     self.scrollbar, self.bottom_button)
            rows.append(row + Text('│', style='#0098ff' if self.dragging else 'dim') + right[index])
        if width < 3:
            # Preserve terminal ownership without emitting over-wide rows.
            rows = [Text('')] * height
            self.bottom_button = None
            self.scrollbar = None
            self.top_bottom_button = None
            self.top_scrollbar = None
            self.description_scrollbar = None
        for row in rows:
            row.truncate(width, overflow='crop')
        self.selection_panels = [
            (1, self.output_width(), 1, self.top_height),
            (left_width + 2, width, 1, self.top_height),
            (1, self.output_width(), self.top_height + 2,
             self.top_height + 1 + self.output_height),
            (left_width + 2, width, self.top_height + 2, self.description_top - 2),
            (left_width + 2, width - int(self.mouse_capture), self.description_top,
             self.description_top + self.description_height - 1),
        ] if width >= 3 else []
        if self.chat_bounds:
            self.selection_panels.append(self.chat_bounds)
        elif self.input_mode != 'chat' and editor_rows and width >= 3:
            self.selection_panels.append((1, left_width, self.chat_top, height))
        self.paint(rows, size)
        if self.input_mode == 'chat' and editor_rows and width >= 3:
            cursor_row = min(height, self.chat_top + 1 + caret_row - editor_start)
            cursor_column = min(left_width, 1 + (2 if boxed else 0) + caret_column)
            # Typing always edits chat, even while another pane is focused.
            # DECSCUSR: use the standard blinking underline cursor.
            self.stream.write(f'\033[{cursor_row};{cursor_column}H\033[3 q\033[?25h')
        else:
            self.stream.write('\033[?25l')
        self.stream.flush()
        self.draw_state = state

    def editor_rows(self, width):
        rows = []
        caret_row = caret_column = 0
        row = Text('', style='default not dim')
        for index, char in enumerate(self.editor.text + '\0'):
            cells = get_character_cell_size(char)
            if row.cell_len + cells > width or (index == self.editor.cursor and row.cell_len == width):
                rows.append(row)
                row = Text('', style='default not dim')
            if index == self.editor.cursor:
                caret_row, caret_column = len(rows), row.cell_len
            if char in ('\n', '\0'):
                rows.append(row)
                row = Text('', style='default not dim')
            else:
                row.append(char)
        return rows, caret_row, caret_column

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
