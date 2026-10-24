"""Embeddable launcher transcript and prompt, independent of dashboard layout."""

import time

from rich.cells import get_character_cell_size
from rich.text import Text

from launcher_chat import ChatEditor
from launcher_render import LauncherDisplay


def clock_duration(seconds):
    """Elapsed whole minutes, shared by launcher clocks and task-field ages."""
    hours, minutes = divmod(max(0, int(seconds // 60)), 60)
    return f'{hours}h {minutes}m' if hours else f'{minutes}m'


def working_duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f'{clock_duration(minutes * 60)} {seconds}s' if minutes else f'{seconds}s'


class SessionPanel(LauncherDisplay):
    """Render into a host's viewport or occupy a dedicated embedded terminal.

    The host supplies session state, transcript and its authorized send callback.
    Layout returns rows and caret geometry without claiming terminal ownership.
    """

    def __init__(self, stream, *, send, **kwargs):
        super().__init__(stream, **kwargs)
        self.editor = ChatEditor(send)
        self.chat_state = {}
        self.input_mode = 'chat'
        self.output_height = 0
        self.cursor = None

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

    def layout(self, width, height, logs, *, scroll=None, output_width=None,
               input_mode='chat', question=None, working=''):
        """Return the same transcript/composer at any size and screen location."""
        boxed = width >= 5
        show_hint = height >= 4
        chrome_height = 1 + int(boxed) + int(show_hint)
        editor_width = max(1, width - 4) if boxed else width
        editor_rows, caret_row, caret_column = self.editor_rows(editor_width)
        capacity = max(0, height - chrome_height)
        room = min(len(editor_rows), max(1, capacity - 1) if capacity else 0)
        editor_start = max(0, caret_row - room + 1)
        editor_rows = editor_rows[editor_start:editor_start + room]
        if input_mode != 'chat':
            editor_rows = self.wrapped(question.lines(width), width) if question else []
            editor_rows = editor_rows[-max(1, height // 2):]
            chrome_height = 0
        self.output_height = max(0, height - len(editor_rows) - chrome_height)
        rows = (scroll or self.scroll_rows)('bottom', logs,
            output_width or width, self.output_height)
        rows += [Text('')] * (self.output_height - len(rows))
        self.cursor = None
        self.chat_bounds = None
        self.chat_top = self.output_height + 1
        self.editor_height = len(editor_rows)
        if input_mode == 'chat':
            hint = Text(self.editor.error or ' '.join(filter(None, (
                self.chat_state.get('model'), self.chat_state.get('effort')))),
                style='red' if self.editor.error else 'dim')
            hint.truncate(width, overflow='crop')
            label = ' Chat ' + (f'· {working} ' if working else '')
            border = Text('╭' + label[:max(0, width - 2)].ljust(max(0, width - 2), '─') + '╮', style='dim')
            border.truncate(width, overflow='crop')
            bottom = []
            if boxed:
                bordered = []
                for row in editor_rows:
                    row = row.copy()
                    row.pad_right(max(0, editor_width - row.cell_len))
                    bordered.append(Text('│ ', style='dim') + row + Text(' │', style='dim'))
                editor_rows = bordered
                bottom = [Text('╰' + '─' * (width - 2) + '╯', style='dim')]
            for row in [border, *editor_rows, *bottom]:
                row.stylize('#333333 on #f4f4f4')
            rows += [border, *editor_rows, *bottom, *([hint] if show_hint else [])]
            if editor_rows and width >= 3:
                self.cursor = (min(height, self.chat_top + 1 + caret_row - editor_start),
                               min(width, 1 + (2 if boxed else 0) + caret_column))
                self.chat_bounds = (3 if boxed else 1, width - 2 if boxed else width,
                                    self.chat_top + 1, min(height, self.chat_top + len(editor_rows)))
        else:
            rows += editor_rows
        return rows[:height]

    def working(self):
        started = self.chat_state.get('turn_started_at', self.chat_state.get('started_at'))
        if self.chat_state.get('status') == 'running' and started is not None:
            return f'Working ({working_duration(time.time() - started)})'
        return ''

    def draw(self):
        if not self.tty:
            return
        size = self.terminal_size()
        width, height = max(1, size.columns - 1), max(1, size.lines)
        logs = [*self.transcript, *([self.pending] if self.pending else []), *self.details]
        rows = self.layout(width, height, logs, input_mode=self.input_mode,
                           question=self.question, working=self.working())
        if not self.screen or size != self.size:
            self.stream.write('\033[H\033[2J')
            self.previous = None
            self.screen = True
        for index, row in enumerate(rows):
            if self.previous is None or index >= len(self.previous) or row != self.previous[index]:
                with self.console.capture() as capture:
                    self.console.print(row, width=size.columns, end='', soft_wrap=True)
                self.stream.write(f'\033[{index + 1};1H\033[2K' + capture.get())
        self.previous, self.size = rows, size
        self.stream.write(f'\033[{self.cursor[0]};{self.cursor[1]}H\033[3 q\033[?25h'
                          if self.cursor else '\033[?25l')
        self.stream.flush()
