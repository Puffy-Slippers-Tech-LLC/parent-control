"""Write-e2e's resizable output, task information and conversation panes."""

import json
import os
import re
import shutil
import sys
import termios

from rich.cells import get_character_cell_size
from rich.text import Text

from launcher_chat import ChatEditor, read_state, send_input
from launcher_render import LauncherDisplay


class WriteE2EDisplay(LauncherDisplay):
    def __init__(self, stream, *, run, **kwargs):
        super().__init__(stream, **kwargs)
        self.run = run
        self.ratio = .75
        self.dragging = False
        self.pointer = False
        self.focus = 'chat'
        self.offsets['info'] = 0
        self.offsets['summary'] = 0
        self.chat_state = {}
        self.task_info = {}
        self.editor = ChatEditor(self.submit)
        self.divider_column = 0
        self.chat_top = 0
        self.summary_bottom = 0
        self.cancel_button = None

    def __enter__(self):
        super().__enter__()
        try:
            if self.input_fd is not None:
                # Deliver Ctrl+C to the conversation instead of the observer's
                # process signal handler. Restore the original flags on every exit.
                attributes = termios.tcgetattr(self.input_fd)
                attributes[3] &= ~termios.ISIG
                termios.tcsetattr(self.input_fd, termios.TCSANOW, attributes)
                self.stream.write('\033[?2004h')
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

    def output_width(self):
        return max(1, self.divider_column - 1)

    def update_question(self, question, send):
        # Keep mouse reporting and the always-editable composer while blocked.
        from launcher_question import QuestionInput
        identity = self.question.question['id'] if self.question else None
        if (question['id'] if question else None) != identity:
            self.question = QuestionInput(question, send) if question else None
            self.draw()

    def set_mouse_mode(self):
        if self.input_fd is not None:
            self.stream.write('\033[?1000l\033[?1002l\033[?1003h\033[?1006h')
            self.stream.flush()

    def set_pointer(self, resize):
        if resize != self.pointer:
            self.pointer = resize
            self.stream.write('\033]22;' + ('ew-resize' if resize else '') + '\033\\')
            self.stream.flush()

    def handle_input(self, data):
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
                    (max(1, self.size.lines - self.top_height - 1) if key == navigation[0] else
                     -max(1, self.size.lines - self.top_height - 1)))
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
        self.draw()

    def mouse(self, button, column, row, released):
        base = button & ~28
        over = column == self.divider_column and row > self.top_height + 1
        self.set_pointer(over or self.dragging)
        if released:
            self.dragging = False
            self.set_pointer(over)
            return
        if base == 0 and over:
            self.dragging = True
        elif base == 32 and self.dragging and self.size:
            self.ratio = min(.9, max(.1, (column - 1) / max(1, self.size.columns - 2)))
            self.draw()
        elif base == 0:
            if self.bottom_button == (column, row):
                self.offsets['bottom'] = 0
                self.draw()
            elif self.cancel_button and row == self.cancel_button[1] and column >= self.cancel_button[0]:
                send_input(self.run, 'interrupt')
            self.focus = 'bottom' if column < self.divider_column else 'chat'
        elif base in (64, 65):
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
        state = (size, self.ratio, tuple((s['key'], tuple(s['lines']), bool(s.get('replaces')),
                 bool(s.get('pinned'))) for s in self.steps), tuple(self.details),
                 tuple(self.transcript), self.pending, tuple(self.offsets.items()),
                 self.editor.text, self.editor.cursor, self.editor.error,
                 json.dumps(self.task_info, sort_keys=True), json.dumps(self.chat_state, sort_keys=True),
                 self.question.question['id'] if self.question else None, self.focus)
        if self.screen and state == self.draw_state:
            return
        width, height = max(1, size.columns - 1), max(1, size.lines)
        pinned = [line for s in self.steps if s.get('pinned') for line in s['lines']]
        current = next((s for s in reversed(self.steps) if not s.get('pinned') and not s.get('replaces')), None)
        # Only completed/suspended history stays above the lower split.
        history = [line for s in self.steps if not s.get('pinned') and
                   (s.get('replaces') or (s is not current and len(s['lines']) == 1)) for line in s['lines']]
        top = self.wrapped(pinned, width)[:max(0, height - 3)]
        room = min(max(0, height // 4 - len(top)), max(0, height - len(top) - 4))
        top += self.scroll_rows('top', history, width, room)
        self.top_height = len(top)
        available = max(0, height - len(top) - 1)
        left_width = max(1, min(width - 2, round((width - 1) * self.ratio))) if width >= 3 else 1
        right_width = max(1, width - left_width - 1)
        self.divider_column = left_width + 1
        logs = [*self.transcript, *([self.pending] if self.pending else []), *self.details]
        left = self.scroll_rows('bottom', logs, left_width, available)
        left += [Text('')] * (available - len(left))

        summary = self.wrapped(current['lines'] if current else ['Waiting for task…'], right_width)
        summary_height = min(len(summary), max(0, available // 2))
        summary_lines = current['lines'] if current else ['Waiting for task…']
        summary = self.from_top('summary', summary_lines, right_width, summary_height)
        self.summary_bottom = len(top) + 1 + summary_height
        task_info = self.task_info if self.task_info.get('task_id') == self.chat_state.get('task_id') else {}
        explanation = task_info.get('explanation', 'Preparing the task explanation…')
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

        boxed = right_width >= 5
        editor_width = max(1, right_width - 4) if boxed else right_width
        editor_rows, caret_row, caret_column = self.editor_rows(editor_width)
        # Grow and shrink with content; a long draft scrolls around its caret
        # rather than covering the task summary or escaping the terminal.
        editor_room = min(len(editor_rows), max(1, available - summary_height - 4))
        start = max(0, caret_row - editor_room + 1)
        editor_rows = editor_rows[start:start + editor_room]
        remaining = max(0, available - summary_height - len(editor_rows) - 3)
        info = self.from_top('info', info_lines, right_width, remaining)
        info += [Text('')] * (remaining - len(info))
        hint = Text('Enter: send · Alt+Enter/Ctrl+J: newline', style='dim')
        hint.truncate(right_width, overflow='crop')
        if self.editor.error:
            hint = Text(self.editor.error, style='red')
            hint.truncate(right_width, overflow='crop')
        label = ' Chat [Cancel] '
        cancel = Text('╭' + label[:max(0, right_width - 2)].ljust(max(0, right_width - 2), '─') + '╮', style='dim')
        cancel.truncate(right_width, overflow='crop')
        if boxed:
            bordered = []
            for row in editor_rows:
                row = row.copy()
                row.pad_right(max(0, editor_width - row.cell_len))
                bordered.append(Text('│ ', style='dim') + row + Text(' │', style='dim'))
            editor_rows = bordered
            hint.truncate(max(1, right_width - 2), overflow='crop')
            hint = Text('╰', style='dim') + hint + Text('╯', style='dim')
        right = summary + [Text('─' * right_width, style='dim')] + info + [cancel] + editor_rows + [hint]
        right = right[:available]
        right += [Text('')] * (available - len(right))
        self.chat_top = len(top) + 1 + summary_height + 1 + remaining + 1
        self.cancel_button = (self.divider_column + 8, self.chat_top)
        self.bottom_button = (left_width, height) if available > 0 and left_width > 1 else None
        rows = top + [Text('─' * width, style='dim')]
        for index in range(available):
            row = left[index].copy()
            if self.bottom_button and index == available - 1:
                row.truncate(left_width - 1, overflow='crop')
                row.pad_right(max(0, left_width - 1 - row.cell_len))
                row += Text('↓', style='bold reverse')
            row.truncate(left_width, overflow='crop')
            row.pad_right(max(0, left_width - row.cell_len))
            rows.append(row + Text('│', style='dim') + right[index])
        if width < 3:
            # Preserve terminal ownership without emitting over-wide rows.
            rows = [Text('')] * height
            self.cancel_button = None
            self.bottom_button = None
        for row in rows:
            row.truncate(width, overflow='crop')
        self.paint(rows, size)
        if self.focus == 'chat' and available > 3:
            cursor_row = min(height, self.chat_top + 1 + caret_row - start)
            cursor_column = min(width, self.divider_column + 1 + (2 if boxed else 0) + caret_column)
            self.stream.write(f'\033[{cursor_row};{cursor_column}H\033[?25h')
        else:
            self.stream.write('\033[?25l')
        self.stream.flush()
        self.draw_state = state

    def editor_rows(self, width):
        rows = []
        caret_row = caret_column = 0
        row = Text('')
        for index, char in enumerate(self.editor.text + '\0'):
            cells = get_character_cell_size(char)
            if row.cell_len + cells > width or (index == self.editor.cursor and row.cell_len == width):
                rows.append(row)
                row = Text('')
            if index == self.editor.cursor:
                caret_row, caret_column = len(rows), row.cell_len
            if char in ('\n', '\0'):
                rows.append(row)
                row = Text('')
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
                self.stream.write('\033[?1003l\033]22;\033\\')
        finally:
            super().restore_terminal()
