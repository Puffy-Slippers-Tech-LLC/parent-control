"""Embeddable launcher transcript and prompt, independent of dashboard layout."""

import json
import re
import time

from rich.cells import get_character_cell_size
from rich.text import Text

from launcher_chat import ChatEditor
from launcher_render import COMPACT_LINE, LauncherDisplay, clean, retained_tail


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

    def __init__(self, stream, *, send, embedded=False, hide_tool_results=False, **kwargs):
        super().__init__(stream, **kwargs)
        self.embedded = embedded
        self.hide_tool_results = hide_tool_results
        # Embedded hosts consume the retained transcript instead of terminal
        # bytes. Keep collecting it even when their backing stream is not a TTY.
        self.tty = self.tty or embedded
        self.editor = ChatEditor(send)
        self.chat_state = {}
        self.input_mode = 'chat'
        self.output_height = 0
        self.cursor = None
        self.simplified = True
        self.simplified_bounds = None
        self.text_output = None
        self.text_identity = None
        self.text_width = 1
        self.simplified_cache = None

    def visible_lines(self, logs):
        """Watch keeps activity names without displaying captured tool results."""
        if not self.hide_tool_results:
            return logs
        rows = []
        activity = None
        detail_pending = False
        for line in logs:
            text = Text.from_ansi(line)
            plain = text.plain
            if plain.startswith('• '):
                if activity is not None and rows and clean(rows[-1]).strip():
                    rows.append('')
                activity = None
                if text.get_style_at_offset(self.console, 2).bold:
                    if plain.startswith('• Ran '):
                        activity = 'command'
                    elif plain == '• Explored':
                        activity = 'exploration'
                    elif re.fullmatch(r'• (?:Tool|Search) (?:working|complete)', plain):
                        activity = 'tool'
                detail_pending = activity == 'tool'
            elif activity is not None:
                if not plain.strip():
                    continue
                if activity == 'command' and plain.startswith('│ '):
                    pass  # Wrapped command name.
                elif activity == 'exploration' and re.match(r'^  (?:└ |  )(?:Read|Search) ', plain):
                    pass
                elif detail_pending:
                    detail_pending = False  # Tool name or search query.
                else:
                    continue
            rows.append(line)
        return rows

    def simplified_lines(self, logs):
        """Project retained full output locally, so observer reloads apply now."""
        source = tuple(logs)
        if self.simplified_cache is not None and source == self.simplified_cache[0]:
            return self.simplified_cache[1]
        rows = []
        activity = None
        heading = None
        prose = False
        detail_pending = False
        unknown = False
        command_output = None

        def new_block(line):
            while rows and not clean(rows[-1]).strip():
                rows.pop()
            rows.extend(['', line])

        def preview(text):
            nonlocal activity
            with self.console.capture() as capture:
                self.console.print(text, end='', soft_wrap=True)
            line = COMPACT_LINE + capture.get()
            if activity is None:
                new_block(line)
                activity = len(rows) - 1
            else:
                rows[activity] = line

        for line in source:
            text = Text.from_ansi(line)
            plain = text.plain
            # Older supervisors emitted unknown items (including sleep) as
            # bare JSON. Recognize them even after prose when reloading logs.
            item = None
            if plain.startswith('{'):
                try:
                    item = json.loads(plain)
                except ValueError:
                    pass
            if (isinstance(item, dict) and isinstance(item.get('type'), str)
                    and isinstance(item.get('id'), str)):
                heading = None
                prose = detail_pending = False
                unknown = True
                preview(Text('• ', style='bright_black') + text)
                continue
            if plain.startswith('• '):
                command_output = None
                if plain == '• Turn complete':
                    continue
                nontext = re.match(r'^• (?:Ran |Explored$|(?:Tool|Search) (?:working|complete)$|'
                                   r'File changes —|Plan$|Agent error$|Agent activity$)', plain)
                if nontext and text.get_style_at_offset(self.console, 2).bold:
                    heading = text
                    prose = unknown = False
                    detail_pending = not plain.startswith(('• Ran ', '• Explored'))
                    preview(text)
                else:
                    activity = None
                    prose, unknown = True, False
                    new_block(line)
            elif prose:
                rows.append(line)
            elif heading is not None and heading.plain == '• Explored' and re.match(
                    r'^  (?:└ |  )(?:Read|Search) ', plain):
                command_output = heading + Text(' ') + text[4:]
                preview(command_output)
            elif heading is not None and (heading.plain.startswith('• Ran ')
                    or heading.plain == '• Explored') and plain.strip():
                if command_output is None:
                    command_output = heading.copy()
                start = 4 if plain.startswith(('  └ ', '    ')) else 0
                command_output += Text(' ') + text[start:]
                # A preview is one clipped row, not another full transcript.
                command_output.truncate(4096, overflow='ellipsis')
                preview(command_output)
            elif detail_pending and plain.strip():
                start = 4 if plain.startswith('  └ ') else len(plain) - len(plain.lstrip())
                preview(heading + Text(' ') + text[start:])
                detail_pending = False
            elif heading is None and plain and not plain[0].isspace() and not plain.startswith('│ '):
                if not unknown:
                    preview(Text('• ', style='bright_black') + text)
                heading = None
                unknown = True
        result = list(retained_tail(rows))
        self.simplified_cache = (source, result)
        return result

    def update_text_output(self, record):
        """Follow prose and the current inline activity from the shared renderer."""
        if not isinstance(record, dict) or (record and (
                not isinstance(record.get('session'), str)
                or not isinstance(record.get('lines'), list)
                or any(not isinstance(line, str) for line in record['lines']))):
            return
        preview = record.get('preview')
        if preview is not None and not isinstance(preview, str):
            return
        lines = list(retained_tail([*record.get('lines', []),
                                   *(['', preview] if preview is not None else [])]))
        identity = record.get('session')
        if identity != self.text_identity:
            self.offsets['bottom'] = 0
        elif self.simplified and self.offsets['bottom'] and lines != self.text_output:
            self.offsets['bottom'] += max(0,
                len(self.wrapped(lines, self.text_width)) -
                len(self.wrapped(self.text_output or [], self.text_width)))
        self.text_output, self.text_identity = lines, identity
        self.scroll_transcript = not self.simplified

    def toggle_at(self, column, row):
        if self.simplified_bounds is None:
            return False
        left, right, footer = self.simplified_bounds
        if row != footer or not left <= column <= right:
            return False
        self.simplified = not self.simplified
        self.scroll_transcript = not self.simplified or self.text_output is None
        self.offsets['bottom'] = 0
        return True

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
               input_mode='chat', question=None, working='', session_logs=None):
        """Return the same transcript/composer at any size and screen location."""
        if self.hide_tool_results:
            source = logs if session_logs is None else session_logs
            logs = self.visible_lines(source)
            if session_logs is not None:
                session_logs = logs
                logs = [*logs, *self.details]
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
        self.text_width = output_width or width
        if self.simplified and self.text_output is not None:
            # Retain the shared renderer's bullets, blank message separators
            # and hanging indentation, including when the viewport reflows.
            source = logs if session_logs is None else session_logs
            logs = [*(self.simplified_lines(source) if source else self.text_output), *self.details]
        rows = (scroll or self.scroll_rows)('bottom', logs,
            output_width or width, self.output_height)
        rows += [Text('')] * (self.output_height - len(rows))
        self.cursor = None
        self.chat_bounds = None
        self.chat_top = self.output_height + 1
        self.editor_height = len(editor_rows)
        self.simplified_bounds = None
        if input_mode == 'chat':
            hint = Text(self.editor.error or ' '.join(filter(None, (
                self.chat_state.get('model'), self.chat_state.get('effort')))),
                style='red' if self.editor.error else 'dim')
            toggle = Text('Simplified ', style='#808080')
            state_label = '[on]' if self.simplified else '[off]'
            toggle.append(state_label, style='#0066ff underline')
            if show_hint and width >= len('Simplified [off]'):
                hint.truncate(max(0, width - toggle.cell_len - 1), overflow='crop')
                hint.pad_right(width - toggle.cell_len - hint.cell_len)
                self.simplified_bounds = (width - len(state_label) + 1, width, height)
                hint += toggle
            else:
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

    def webview(self):
        """Expose the shared transcript/composer to a native webview host."""
        logs = [*self.transcript, *([self.pending] if self.pending else [])]
        logs = self.visible_lines(logs)
        if self.simplified:
            logs = self.simplified_lines(logs) if logs else self.text_output or []
        return dict(lines=[*logs, *self.details], working=self.working(),
                    model=' '.join(filter(None, (self.chat_state.get('model'),
                                                self.chat_state.get('effort')))),
                    simplified=self.simplified)

    def working(self):
        started = self.chat_state.get('turn_started_at', self.chat_state.get('started_at'))
        if self.chat_state.get('status') == 'running' and started is not None:
            return f'Working ({working_duration(time.time() - started)})'
        return ''

    def draw(self):
        if not self.tty or self.embedded:
            return
        size = self.terminal_size()
        width, height = max(1, size.columns - 1), max(1, size.lines)
        logs = [*self.transcript, *([self.pending] if self.pending else []), *self.details]
        rows = self.layout(width, height, logs, input_mode=self.input_mode,
                           question=self.question, working=self.working(),
                           session_logs=[*self.transcript, *([self.pending] if self.pending else [])])
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
