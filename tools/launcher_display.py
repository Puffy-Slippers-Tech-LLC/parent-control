"""Shared resizable task overview/totals and execution/input/status panes."""

import json
import os
import re
import shutil
import sys
import termios
import time

from rich.cells import get_character_cell_size
from rich.text import Text

from launcher_chat import ChatEditor, read_state, send_input
from launcher_render import LauncherDisplay, clean


def clock_duration(seconds):
    """Elapsed whole minutes, shared by the session and terminal-launch clocks."""
    hours, minutes = divmod(max(0, int(seconds // 60)), 60)
    return f'{hours}h {minutes}m' if hours else f'{minutes}m'


class TaskDisplay(LauncherDisplay):
    def __init__(self, stream, *, run, input_mode='chat', totals=None, **kwargs):
        super().__init__(stream, **kwargs)
        self.launched_at = time.monotonic()
        self.run = run
        self.input_mode = input_mode
        self.ratio = .75
        self.top_ratio = self.ratio
        self.dragging = None
        self.totals = totals
        self.task_totals = None
        self.pointer = False
        self.focus = 'chat' if input_mode == 'chat' else 'bottom'
        self.offsets['info'] = 0
        self.offsets['summary'] = 0
        self.chat_state = {}
        self.task_info = {}
        self.editor = ChatEditor(self.submit)
        self.divider_column = 0
        self.top_divider_column = 0
        self.chat_top = 0
        self.output_height = 0
        self.summary_bottom = 0
        self.cancel_button = None
        self.escape_since = None
        self.mouse_pending = b''

    def __enter__(self):
        super().__enter__()
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
        return self

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
        path = self.run / 'task-info.json'
        self.task_info = json.loads(path.read_text()) if path.exists() else {}
        if self.totals is not None:
            try:
                self.task_totals = self.totals()
            except (OSError, ValueError):
                # A partially rewritten queue must not detach the observer or
                # replace the last valid totals with misleading zeroes.
                pass

    def output_width(self):
        return max(1, self.divider_column - 1)

    def update_question(self, question, send):
        if self.input_mode != 'chat':
            return super().update_question(question, send)
        # Keep mouse reporting and the always-editable composer while blocked.
        from launcher_question import QuestionInput
        identity = self.question.question['id'] if self.question else None
        if (question['id'] if question else None) != identity:
            self.question = QuestionInput(question, send) if question else None
            self.draw()

    def set_mouse_mode(self):
        if self.input_mode != 'chat':
            return super().set_mouse_mode()
        if self.input_fd is not None:
            self.stream.write('\033[?1000l\033[?1002l\033[?1003h\033[?1006h')
            self.stream.flush()

    def set_pointer(self, resize):
        if resize != self.pointer:
            self.pointer = resize
            self.stream.write('\033]22;' + ('ew-resize' if resize else '') + '\033\\')
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
                match = re.match(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', self.mouse_pending)
                if match:
                    self.mouse_pending = self.mouse_pending[match.end():]
                    if self.mouse_capture:
                        self.mouse(*map(int, match.groups()[:3]), match[4] == b'm')
                elif (b'\x1b[<'.startswith(self.mouse_pending) or
                      self.mouse_pending.startswith(b'\x1b[<') and len(self.mouse_pending) < 64):
                    break
                else:
                    split = self.mouse_pending.find(b'\x1b[<', 1)
                    value = self.mouse_pending if split < 0 else self.mouse_pending[:split]
                    self.mouse_pending = b'' if split < 0 else self.mouse_pending[split:]
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
            key = next((key for key in navigation if self.input_pending.startswith(key)), None)
            if key:
                self.input_pending = self.input_pending[len(key):]
                self.offsets['bottom'] = max(0, self.offsets['bottom'] +
                    (max(1, self.output_height) if key == navigation[0] else
                     -max(1, self.output_height)))
                continue
            if any(key.startswith(self.input_pending) for key in navigation):
                break
            byte = self.input_pending[:1]
            self.input_pending = self.input_pending[1:]
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
        over = ('top' if column == self.top_divider_column and 1 <= row <= self.top_height else
                'bottom' if column == self.divider_column and row > self.top_height + 1 else None)
        self.set_pointer(bool(over or self.dragging))
        if released:
            self.dragging = None
            self.set_pointer(bool(over))
            self.draw()
            return
        if base == 0 and over:
            self.dragging = over
            self.draw()
        elif base == 32 and self.dragging and self.size:
            ratio = min(.9, max(.1, (column - 1) / max(1, self.size.columns - 2)))
            if self.dragging == 'top':
                self.top_ratio = ratio
            else:
                self.ratio = ratio
            self.draw()
        elif base == 0:
            if row <= self.top_height:
                if column < self.top_divider_column:
                    self.focus = 'top'
                return
            if self.bottom_button == (column, row):
                self.offsets['bottom'] = 0
                self.draw()
            elif (self.cancel_button and row == self.cancel_button[1]
                  and self.cancel_button[0] <= column < self.divider_column):
                send_input(self.run, 'interrupt')
            self.focus = ('bottom' if self.input_mode != 'chat' or
                          column < self.divider_column and row < self.chat_top else 'chat')
        elif base in (64, 65):
            if row <= self.top_height and column >= self.top_divider_column:
                return
            if self.input_mode == 'chat' and column < self.divider_column and row >= self.chat_top:
                return
            pane = ('top' if row <= self.top_height else 'bottom' if column < self.divider_column else
                    'summary' if row <= self.summary_bottom else 'info')
            delta = 3 if base == 64 else -3
            self.offsets[pane] = max(0, self.offsets[pane] + (-delta if pane in ('summary', 'info') else delta))
            self.draw()

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
        if (current and current['key'] == self.chat_state.get('progress_key')
                and started is not None and len(summary_lines) > 1
                and clean(summary_lines[-1]).startswith((f'Session [{session}]:', f'Session {session}:'))):
            ended = self.chat_state.get('finished_at', time.time())
            summary_lines[-1] += '; ' + clock_duration(ended - started)
        total_duration = clock_duration(time.monotonic() - self.launched_at)
        state = (size, self.ratio, self.top_ratio, self.dragging, self.task_totals,
                 tuple(summary_lines), total_duration,
                 tuple((s['key'], tuple(s['lines']), bool(s.get('replaces')),
                 bool(s.get('pinned'))) for s in self.steps), tuple(self.details),
                 tuple(self.transcript), self.pending, tuple(self.offsets.items()),
                 self.editor.text, self.editor.cursor, self.editor.error,
                 json.dumps(self.task_info, sort_keys=True), json.dumps(self.chat_state, sort_keys=True),
                 (self.question.question['id'], self.question.selected, self.question.text)
                 if self.question else None, self.focus, self.mouse_capture)
        if self.screen and state == self.draw_state:
            return
        width, height = max(1, size.columns - 1), max(1, size.lines)
        top_left_width = max(1, min(width - 2, round((width - 1) * self.top_ratio))) if width >= 3 else 1
        top_right_width = max(1, width - top_left_width - 1)
        self.top_divider_column = top_left_width + 1
        totals = Text('Total Tasks: ')
        completed, unfinished, total = self.task_totals or ('—', '—', '—')
        totals.append(str(completed), style='green')
        totals.append('/')
        totals.append(str(unfinished), style='blue')
        totals.append('/')
        totals.append(str(total))
        totals.append('\nTotal Duration: ' + total_duration)
        total_rows = totals.wrap(self.console, top_right_width, overflow='fold')[:max(0, height - 4)]
        pinned = [line for s in self.steps if s.get('pinned') for line in s['lines']]
        # Only completed/suspended history stays above the lower split.
        history = [line for s in self.steps if not s.get('pinned') and
                   (s.get('replaces') or (s is not current and len(s['lines']) == 1)) for line in s['lines']]
        if self.input_mode != 'chat':
            history = [s['lines'][0] for s in self.steps if not s.get('pinned') and s['lines']]
        top = self.wrapped(pinned, top_left_width)[:max(0, height - 3)]
        room = min(max(0, height // 4 - len(top)), max(0, height - len(top) - 4))
        top += self.scroll_rows('top', history, top_left_width, room)
        top += [Text('')] * max(0, len(total_rows) - len(top))
        for index, row in enumerate(top):
            row.pad_right(max(0, top_left_width - row.cell_len))
            top[index] = row + Text('│', style='#0098ff' if self.dragging == 'top' else 'dim')
            if index < len(total_rows):
                top[index] += total_rows[index]
        self.top_height = len(top)
        available = max(0, height - len(top) - 1)
        left_width = max(1, min(width - 2, round((width - 1) * self.ratio))) if width >= 3 else 1
        right_width = max(1, width - left_width - 1)
        boxed = left_width >= 5
        separator = [Text('─' * right_width, style='dim')] if available >= 5 else []
        show_hint = available >= 4
        # Reserve the bottom composer independently of session-output scrolling.
        # Very short terminals give up the hint first.
        chrome_height = 1 + int(boxed) + int(show_hint)
        self.divider_column = left_width + 1

        summary = self.wrapped(summary_lines, right_width)
        summary_height = min(len(summary), max(0, available // 2),
                             max(0, available - len(separator) - 1))
        summary = self.from_top('summary', summary_lines, right_width, summary_height)
        self.summary_bottom = len(top) + 1 + summary_height
        task_info = self.task_info if self.task_info.get('task_id') == self.chat_state.get('task_id') else {}
        explanation = task_info.get('explanation', 'Preparing the task explanation…'
                                    if self.input_mode == 'chat' else 'Execution details appear on the left.')
        session = self.chat_state.get('task_session', self.chat_state.get('session'))
        status = ('Running session 1.' if session == 1 and self.chat_state.get('status') == 'running' else
                  task_info.get('status', f'Running session {session}. Reviewing the previous attempt.'
                                if session else 'Starting…'))
        if self.chat_state.get('status') == 'waiting':
            status = 'Interrupted. Waiting for your instructions. Ctrl+C again exits.'
        elif self.chat_state.get('status') == 'interrupting':
            status = 'Interrupting the current work…'
        elif self.chat_state.get('status') == 'cleaning':
            status = 'Finishing cleanup before accepting more instructions…'
        elif self.chat_state.get('status') == 'blocked':
            status = 'Waiting for your answer below.'
        elif self.chat_state.get('status') == 'finished':
            status = 'Session finished. Preparing the next step.'
        info_lines = [explanation, '', status]
        if self.question:
            info_lines += ['', self.question.question.get('explanation', ''),
                           self.question.question['question'],
                           *[f'{i + 1}. {option}' for i, option in enumerate(self.question.question['options'])],
                           'Type a number or your own instructions below.']

        if self.input_mode != 'chat':
            info_lines = [explanation, '', task_info.get('status', current['lines'][-1] if current else 'Starting…')]
            if self.question:
                info_lines += ['', self.question.question.get('explanation', '')]

        editor_width = max(1, left_width - 4) if boxed else left_width
        editor_rows, caret_row, caret_column = self.editor_rows(editor_width)
        # Grow and shrink with content; a long draft scrolls around its caret
        # rather than escaping the terminal; leave room for output when possible.
        editor_capacity = max(0, available - chrome_height)
        editor_room = min(len(editor_rows), max(1, editor_capacity - 1) if editor_capacity else 0)
        start = max(0, caret_row - editor_room + 1)
        editor_rows = editor_rows[start:start + editor_room]
        if self.input_mode != 'chat':
            editor_rows = self.wrapped(self.question.lines(left_width), left_width) if self.question else []
            editor_rows = editor_rows[-max(1, available // 2):]
            chrome_height = 0
        self.output_height = max(0, available - len(editor_rows) - chrome_height)
        logs = [*self.transcript, *([self.pending] if self.pending else []), *self.details]
        left = self.scroll_rows('bottom', logs, left_width, self.output_height)
        left += [Text('')] * (self.output_height - len(left))
        remaining = max(0, available - summary_height - len(separator))
        info = self.from_top('info', info_lines, right_width, remaining)
        info += [Text('')] * (remaining - len(info))
        hint = Text('Enter: send · Shift+Enter: newline', style='dim')
        hint.truncate(left_width, overflow='crop')
        if self.editor.error:
            hint = Text(self.editor.error, style='red')
            hint.truncate(left_width, overflow='crop')
        label = ' Chat [Cancel] '
        cancel = Text('╭' + label[:max(0, left_width - 2)].ljust(max(0, left_width - 2), '─') + '╮', style='dim')
        cancel.truncate(left_width, overflow='crop')
        bottom = []
        if boxed and self.input_mode == 'chat':
            bordered = []
            for row in editor_rows:
                row = row.copy()
                row.pad_right(max(0, editor_width - row.cell_len))
                bordered.append(Text('│ ', style='dim') + row + Text(' │', style='dim'))
            editor_rows = bordered
            bottom = [Text('╰' + '─' * (left_width - 2) + '╯', style='dim')]
        left += ([cancel] + editor_rows + bottom + ([hint] if show_hint else [])
                 if self.input_mode == 'chat' else editor_rows)
        left = left[:available]
        right = summary + separator + info
        right = right[:available]
        right += [Text('')] * (available - len(right))
        self.chat_top = len(top) + 1 + self.output_height + 1
        self.cancel_button = ((9, self.chat_top) if self.input_mode == 'chat'
                              and left_width >= 14 and available else None)
        self.bottom_button = ((left_width, self.chat_top - 1)
                              if self.output_height > 0 and left_width > 1 else None)
        divider = Text('─' * width, style='dim')
        if self.input_mode != 'chat' and self.input_fd is not None:
            divider = Text(' m: select text ' if self.mouse_capture else ' m: scroll ', style='dim')
            divider.truncate(width, overflow='crop')
            divider.append('─' * max(0, width - divider.cell_len))
        rows = top + [divider]
        for index in range(available):
            row = left[index].copy()
            if self.bottom_button and index == self.output_height - 1:
                row.truncate(left_width - 1, overflow='crop')
                row.pad_right(max(0, left_width - 1 - row.cell_len))
                row += Text('↓', style='bold reverse')
            row.truncate(left_width, overflow='crop')
            row.pad_right(max(0, left_width - row.cell_len))
            rows.append(row + Text('│', style='#0098ff' if self.dragging == 'bottom' else 'dim') + right[index])
        if width < 3:
            # Preserve terminal ownership without emitting over-wide rows.
            rows = [Text('')] * height
            self.cancel_button = None
            self.bottom_button = None
        for row in rows:
            row.truncate(width, overflow='crop')
        self.paint(rows, size)
        if self.input_mode == 'chat' and self.focus == 'chat' and editor_rows and width >= 3:
            cursor_row = min(height, self.chat_top + 1 + caret_row - start)
            cursor_column = min(left_width, 1 + (2 if boxed else 0) + caret_column)
            # DECSCUSR: use the standard blinking I-beam for text editing.
            self.stream.write(f'\033[{cursor_row};{cursor_column}H\033[5 q\033[?25h')
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
        rows = self.wrapped(lines, width)
        offset = self.offsets[pane] = min(self.offsets[pane], max(0, len(rows) - height))
        return rows[offset:offset + height]

    def paint(self, rows, size):
        if not self.screen:
            self.screen = True
            self.stream.write('\033[?1049h\033[H\033[2J\033[?25l')
            self.set_mouse_mode()
            self.previous = None
        if size != self.size:
            self.stream.write('\033[H\033[2J')
            self.previous = None
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
