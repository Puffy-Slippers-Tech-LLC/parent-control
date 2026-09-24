"""Shared launcher panes and presentation of noninteractive Codex JSONL events.

Render once in the detached supervisor, so reconnecting observers see the same
agent transcript. Only the observer owns the terminal and its two-pane display.
"""

import json
import os
import re
import shlex
import shutil
import signal
import select
import sys
import termios
from collections import deque
from pathlib import PurePath

from rich.console import Console
from rich.markdown import CodeBlock, Markdown
from rich.padding import Padding
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme


CONTROL = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))|[\x00-\x08\x0b-\x1f\x7f]')
HANGING_PREFIX = re.compile(r'^(?: *[•└│✓○] | {2,})')

# Bound both row count and text: a stream need not contain any newlines.
SCROLLBACK_LINES = 2000
SCROLLBACK_CHARACTERS = 256 * 1024


def retained_tail(lines):
    """Keep the newest text within the observer's in-memory history budget."""
    retained = deque()
    remaining = SCROLLBACK_CHARACTERS
    for line in reversed(lines):
        if len(retained) == SCROLLBACK_LINES or remaining == 0:
            break
        retained.appendleft(line[-remaining:])
        remaining -= len(retained[0])
    return retained


def clean(value):
    return CONTROL.sub('', str(value))


class LauncherDisplay:
    """Two panes owned by the observer, never by its streaming children.

    Native terminal selection and context menus own the mouse by default.
    Press m to enable pane scrolling and show the draggable scrollbar.
    The lower pane starts focused. Absolute positioning isolates redraws.
    """

    def __init__(self, stream, *, log_path=None):
        self.stream = stream
        self.log_path = log_path
        self.unsaved = deque()
        self.tty = stream.isatty() and os.environ.get('TERM') != 'dumb'
        self.console = Console(file=stream, force_terminal=True, markup=False,
                               highlight=False, color_system='truecolor', no_color=False)
        self.transcript = deque(maxlen=SCROLLBACK_LINES)
        self.pending = ''
        self.steps = []
        self.details = []
        self.size = None
        self.screen = False
        self.previous = None
        self.signal_handlers = {}
        self.focus = 'bottom'
        self.offsets = {'top': 0, 'bottom': 0}
        self.row_cache = {}
        self.top_height = 0
        self.step_history = {}
        self.input_fd = None
        self.input_attributes = None
        self.input_pending = b''
        self.scrollbar = None
        self.scrollbar_grab = None
        self.mouse_capture = False

    def __enter__(self):
        if self.tty:
            # Ctrl+C already has launcher-specific guarded cancellation. Only
            # replace default termination actions, which bypass finally blocks.
            for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGQUIT):
                previous = signal.getsignal(sig)
                if previous == signal.SIG_DFL:
                    self.signal_handlers[sig] = previous
                    signal.signal(sig, self.terminate)
            try:
                fd = sys.stdin.fileno()
                if (os.isatty(fd) and os.fstat(fd).st_rdev == os.fstat(self.stream.fileno()).st_rdev
                        and os.tcgetpgrp(fd) == os.getpgrp()):
                    attributes = termios.tcgetattr(fd)
                    interactive = attributes[:]
                    interactive[6] = attributes[6][:]
                    interactive[3] &= ~(termios.ICANON | termios.ECHO | termios.ECHONL)
                    interactive[6][termios.VMIN] = 1
                    interactive[6][termios.VTIME] = 0
                    self.input_fd, self.input_attributes = fd, attributes
                    termios.tcsetattr(fd, termios.TCSANOW, interactive)
            except (OSError, ValueError, termios.error):
                self.restore_terminal()
        return self

    def terminate(self, signum, frame):
        raise SystemExit(128 + signum)

    def __exit__(self, *_):
        try:
            self.close()
        finally:
            for sig, previous in self.signal_handlers.items():
                signal.signal(sig, previous)
            self.signal_handlers.clear()

    def write(self, value, *, final=False, saved=True):
        if not self.tty:
            self.stream.write(value)
            self.stream.flush()
            return
        if not saved:
            self.unsaved.append(value)
            self.unsaved = retained_tail(self.unsaved)
        lines = (self.pending + value).split('\n')
        if self.offsets['bottom'] and self.size:
            width = max(1, self.size.columns - 1)
            incoming = lines[:-1] + ([lines[-1]] if lines[-1] else [])
            previous = [self.pending] if self.pending else []
            self.offsets['bottom'] += (len(self.wrapped(incoming, width))
                                       - len(self.wrapped(previous, width)))
        self.pending = lines.pop()
        self.transcript.extend(lines)
        if final and self.pending:
            self.transcript.append(self.pending)
            self.pending = ''
        retained = retained_tail([*self.transcript, *([self.pending] if self.pending else [])])
        if self.pending:
            self.pending = retained.pop()
        self.transcript = deque(retained, maxlen=SCROLLBACK_LINES)
        self.draw()

    def update(self, steps, details):
        if not self.tty:
            for step in steps:
                if step not in self.steps:
                    self.stream.write('\n'.join(step['lines']) + '\n')
            if details != self.details and details:
                self.stream.write('\n'.join(details) + '\n')
            self.stream.flush()
        for step in steps:
            self.step_history[step['key']] = list(retained_tail(step['lines']))
        history_size = sum(len(line) for lines in self.step_history.values() for line in lines)
        history_lines = sum(map(len, self.step_history.values()))
        while (len(self.step_history) > SCROLLBACK_LINES or history_lines > SCROLLBACK_LINES
               or history_size > SCROLLBACK_CHARACTERS):
            oldest = self.step_history[next(iter(self.step_history))]
            history_size -= sum(map(len, oldest))
            history_lines -= len(oldest)
            del self.step_history[next(iter(self.step_history))]
        self.steps, self.details = steps, details
        self.draw()

    def poll_input(self):
        if self.input_fd is not None and select.select([self.input_fd], [], [], 0)[0]:
            self.handle_input(os.read(self.input_fd, 4096))

    def handle_input(self, data):
        """Decode navigation keys and SGR reports, including fragmented reads."""
        self.input_pending += data
        while self.input_pending:
            keys = (b'\x1b[A', b'\x1b[B', b'\x1b[5~', b'\x1b[6~',
                    b'\x1b[F', b'\x1bOF', b'\x1b[4~', b'\x1b[8~', b'\t', b'm')
            key = next((key for key in keys if self.input_pending.startswith(key)), None)
            if key is not None:
                self.input_pending = self.input_pending[len(key):]
                if key == b'm':
                    self.mouse_capture = not self.mouse_capture
                    self.scrollbar_grab = None
                    self.set_mouse_mode()
                    self.draw()
                elif key == b'\t':
                    self.focus = 'top' if self.focus == 'bottom' else 'bottom'
                else:
                    page = (self.top_height if self.focus == 'top' else
                            self.size.lines - self.top_height - 1) if self.size else 1
                    delta = {b'\x1b[A': 1, b'\x1b[B': -1,
                             b'\x1b[5~': max(1, page), b'\x1b[6~': -max(1, page)}
                    self.offsets[self.focus] = max(0, self.offsets[self.focus] + delta[key]) if key in delta else 0
                    self.draw()
                continue
            if any(key.startswith(self.input_pending) for key in keys):
                break
            match = re.match(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', self.input_pending)
            if match:
                button, column, row = map(int, match.groups()[:3])
                self.input_pending = self.input_pending[match.end():]
                if not self.mouse_capture:
                    # Reports already queued before releasing the mouse must
                    # not scroll or start a drag in native selection mode.
                    continue
                if match[4] == b'm':
                    self.scrollbar_grab = None
                elif (button & ~28) == 32:
                    if self.scrollbar_grab is not None and self.scrollbar:
                        first, start, thumb, travel, limit = self.scrollbar
                        position = min(travel, max(0, row - first - self.scrollbar_grab))
                        if travel:
                            self.offsets['bottom'] = round(limit * (travel - position) / travel)
                            self.draw()
                elif match[4] == b'M':
                    if (button & ~28) == 0 and self.size and column == self.size.columns:
                        self.scrollbar_grab = None
                        if self.scrollbar and self.top_height + 1 < row <= self.size.lines:
                            first, start, thumb, travel, limit = self.scrollbar
                            position = row - first
                            self.focus = 'bottom'
                            if start <= position < start + thumb:
                                self.scrollbar_grab = position - start
                                continue
                            height = self.size.lines - self.top_height - 1
                            if limit:
                                self.offsets['bottom'] = round(limit * (height - 1 - position) / max(1, height - 1))
                                self.draw()
                    elif (button & ~28) == 0 and self.size and 1 <= column < self.size.columns:
                        self.scrollbar_grab = None
                        if 1 <= row <= self.top_height:
                            self.focus = 'top'
                        elif self.top_height + 1 < row <= self.size.lines:
                            self.focus = 'bottom'
                    elif (button & ~28) in (64, 65):
                        delta = 3 if (button & 1) == 0 else -3
                        self.offsets[self.focus] = max(0, self.offsets[self.focus] + delta)
                        self.draw()
            elif re.fullmatch(rb'\x1b(?:\[(?:<(?:\d*(?:;\d*(?:;\d*)?)?)?)?)?',
                              self.input_pending) and len(self.input_pending) < 64:
                break
            else:
                self.input_pending = self.input_pending[1:]

    def scroll_rows(self, pane, lines, width, height):
        # Quiet observer polls should not repeatedly reflow the scrollback.
        lines = retained_tail(lines)
        key = (width, tuple(lines))
        cached = self.row_cache.get(pane)
        if cached is None or cached[0] != key:
            rows = deque(maxlen=SCROLLBACK_LINES)
            # Reflow from the newest end and stop once the visible history is
            # full; narrow terminals must not multiply the retained row count.
            for line in reversed(lines):
                wrapped = self.wrapped([line], width)
                rows.extendleft(reversed(wrapped[-(SCROLLBACK_LINES - len(rows)):]))
                if len(rows) == SCROLLBACK_LINES:
                    break
            cached = self.row_cache[pane] = (key, list(rows))
        rows = cached[1]
        limit = max(0, len(rows) - height) if height else 0
        self.offsets[pane] = min(self.offsets[pane], limit)
        end = len(rows) - self.offsets[pane]
        return rows[max(0, end - height):end] if height else []

    def wrapped(self, lines, width):
        rows = []
        for line in lines:
            text = Text.from_ansi(line)
            if self.is_rule(text):
                rows.append(Text('─' * width, style='dim'))
            else:
                prefix = HANGING_PREFIX.match(text.plain)
                if prefix is None or text.cell_len <= width:
                    rows.extend(text.wrap(self.console, width, overflow='fold'))
                    continue
                # The retained transcript was formatted for a wider terminal.
                # Reflow each physical row under its original content column.
                text.rstrip()
                indent = min(len(prefix[0]), width - 1)
                body = text[len(prefix[0]):]
                for index, part in enumerate(body.wrap(self.console, max(1, width - indent),
                                                       overflow='fold')):
                    leader = text[:indent] if index == 0 else Text(' ' * indent)
                    rows.append(leader + part)
        return rows

    @staticmethod
    def is_rule(text):
        return bool(text.plain) and set(text.plain) == {'─'}

    def draw(self):
        if not self.tty:
            return
        try:
            size = os.get_terminal_size(self.stream.fileno())
        except (OSError, ValueError):
            size = shutil.get_terminal_size()
        width, height = max(1, size.columns - 1), max(1, size.lines)
        recent = self.steps[-2:]
        steps = []
        previous_lines = []
        for step in recent:
            lines = step['lines']
            shared = 0
            for previous, current in zip(previous_lines, lines):
                if previous != current:
                    break
                shared += 1
            steps.append(self.wrapped(lines[shared:], width))
            previous_lines = lines
        # Reflow the entire newest step before spending space on its predecessor.
        # Keep even extremely small terminals on the alternate screen: falling
        # back to ordinary output would permanently leak panes into scrollback.
        while len(steps) > 1 and sum(map(len, steps)) + 3 > height:
            # Once the predecessor is hidden, restore the newest step's context.
            steps = [self.wrapped(recent[-1]['lines'], width)]
        top = [row for step in steps for row in step]
        if len(top) + 3 > height:
            top = top[:max(0, height - 2)]
        self.top_height = len(top)
        if self.offsets['top']:
            history = [line for lines in self.step_history.values() for line in lines]
            scrolled_top = self.scroll_rows('top', history, width, self.top_height)
            if self.offsets['top']:
                top = scrolled_top
        available = height - len(top) - 1
        # The lower pane keeps the detailed test dashboard and the newest log
        # rows. Agent sessions have no dashboard, so use the whole lower pane.
        from regression import Dashboard
        details = Dashboard.fit_height(self.details, available) if self.details and available > 0 else []
        detail_rows = []
        for line in details:
            row = Text.from_ansi(line)
            row.truncate(width, overflow='ellipsis')
            detail_rows.append(row)
        room = available - len(detail_rows)
        log_rows = []
        for line in reversed([*self.transcript, *([self.pending] if self.pending else [])]):
            if len(log_rows) >= room:
                break
            log_rows = self.wrapped([line], width)[-(room - len(log_rows)):] + log_rows
        body = log_rows + detail_rows
        retained = [*self.transcript, *([self.pending] if self.pending else []), *self.details]
        scrolled_body = self.scroll_rows('bottom', retained, width, available)
        if self.offsets['bottom']:
            body = scrolled_body
        body += [Text('')] * (available - len(body))
        divider = Text('─' * width, style='dim')
        if self.input_fd is not None:
            divider = Text(' m: select text ' if self.mouse_capture else ' m: scroll ',
                           style='dim')
            divider.truncate(width, overflow='crop')
            divider.append('─' * max(0, width - divider.cell_len))
        rows = top + [divider] + body
        total = len(self.row_cache['bottom'][1])
        self.scrollbar = None
        if self.mouse_capture and available > 0 and total > available:
            thumb = max(1, min(available - 1, round(available * available / total)))
            travel = available - thumb
            start = round(travel * (total - available - self.offsets['bottom']) / (total - available))
            self.scrollbar = (len(top) + 2, start, thumb, travel, total - available)
            for index in range(available):
                row_index = len(top) + 1 + index
                row = rows[row_index].copy()
                row.pad_right(max(0, width - row.cell_len))
                rows[row_index] = row + Text(
                    '█' if start <= index < start + thumb else '░', style='dim')
        # Compare physical rows so quiet workers do not repaint either pane.
        encoded = []
        for row in rows:
            with self.console.capture() as capture:
                self.console.print(row, width=size.columns, end='', soft_wrap=True)
            encoded.append(capture.get())
        if not self.screen:
            self.screen = True
            self.stream.write('\033[?1049h\033[H\033[2J\033[?25l')
            if self.input_fd is not None:
                self.set_mouse_mode()
            self.previous = None
        if size != self.size:
            self.stream.write('\033[H\033[2J')
            self.previous = None
        for index, row in enumerate(encoded):
            if self.previous is None or index >= len(self.previous) or row != self.previous[index]:
                self.stream.write(f'\033[{index + 1};1H\033[2K' + row)
        self.stream.flush()
        self.previous, self.size = encoded, size

    def set_mouse_mode(self):
        if self.input_fd is not None:
            # Mouse reporting consumes selection and right clicks before the
            # host terminal can apply its own menu/preferences (including VS Code).
            self.stream.write('\033[?1000l\033[?1002l\033[?1003l\033[?1006l')
            if self.mouse_capture:
                self.stream.write('\033[?1002h\033[?1006h')
            self.stream.flush()

    def restore_terminal(self):
        self.scrollbar_grab = None
        self.mouse_capture = False
        if self.input_fd is not None:
            try:
                self.stream.write('\033[?1002l\033[?1006l')
                self.stream.flush()
            finally:
                termios.tcsetattr(self.input_fd, termios.TCSAFLUSH, self.input_attributes)
                self.input_fd = None
                self.input_attributes = None
        if self.screen:
            self.stream.write('\033[?25h\033[?1049l')
            self.stream.flush()
            self.screen = False
            self.previous = None

    def close(self):
        replay = self.screen
        self.restore_terminal()
        if not replay:
            return
        # Alternate-screen rows vanish when the terminal restores the shell.
        # Append the retained log to ordinary scrollback after restoring modes;
        # the live pane's bounded deque may have lost most of a long session.
        try:
            width = os.get_terminal_size(self.stream.fileno()).columns
        except (OSError, ValueError):
            width = shutil.get_terminal_size().columns

        def replay_line(line):
            text = Text.from_ansi(line)
            if self.is_rule(text):
                text = Text('─' * max(1, width - 1), style='dim')
            self.console.print(text, soft_wrap=True)

        self.stream.write('\n')
        for step in self.steps:
            for line in step['lines']:
                replay_line(line)
        try:
            source = self.log_path.open('rb') if self.log_path is not None else None
        except OSError:
            source = None
        if source is None:
            for line in [*self.transcript, *([self.pending] if self.pending else [])]:
                replay_line(line)
        else:
            with source:
                # A detached worker can still be appending: replay only the
                # snapshot present at exit, without waiting for that worker.
                remaining = os.fstat(source.fileno()).st_size
                while remaining:
                    line = source.readline(remaining)
                    if not line:
                        break
                    remaining -= len(line)
                    replay_line(line.decode('utf-8', errors='replace').rstrip('\n'))
            for value in self.unsaved:
                replay_line(value.rstrip('\n'))
        self.stream.flush()


class SessionCodeBlock(CodeBlock):
    def __rich_console__(self, console, options):
        code = str(self.text).rstrip()
        syntax = Syntax(code, self.lexer_name, theme='ansi_light',
                        background_color='default', word_wrap=True)
        if self.lexer_name in ('bash', 'sh', 'shell'):
            text = syntax.highlight(code)
            text.rstrip()
            for match in re.finditer(r'(?m)^\s*(?:\$ )?([^\s#]+)', code):
                text.stylize('#0066ff', *match.span(1))
            for match in re.finditer(r'(?<!\S)--[\w-]+', code):
                text.stylize('#ff0000', *match.span())
            yield text
        else:
            yield syntax


class SessionMarkdown(Markdown):
    elements = {**Markdown.elements, 'fence': SessionCodeBlock,
                'code_block': SessionCodeBlock}


class TranscriptWriter:
    """Fit retained rows to an observer without losing their hanging indent."""

    def __init__(self, stream):
        self.stream = stream
        self.pending = ''
        self.console = Console(file=stream, force_terminal=True,
                               color_system='truecolor', no_color=False, style='#24292f',
                               markup=False, highlight=False)

    def write(self, value, *, final=False):
        if not self.stream.isatty():
            self.stream.write(value)
            return
        lines = (self.pending + value).split('\n')
        self.pending = lines.pop()
        for line in lines:
            self.line(line)
        if final and self.pending:
            self.line(self.pending, end='')
            self.pending = ''

    def line(self, value, *, end='\n'):
        try:
            width = os.get_terminal_size(self.stream.fileno()).columns
        except (OSError, ValueError):
            width = shutil.get_terminal_size().columns
        width = max(1, width)
        text = Text.from_ansi(value)
        prefix = HANGING_PREFIX.match(text.plain)
        if prefix is None or text.cell_len <= width:
            self.stream.write(value + end)
            return
        # Rich pads retained Markdown rows to the recording width. Those spaces
        # must not become extra physical rows in a narrower observer.
        text.rstrip()
        indent = min(len(prefix[0]), width - 1)
        body = text[len(prefix[0]):]
        rows = body.wrap(self.console, max(1, width - indent))
        for index, row in enumerate(rows):
            leader = text[:indent] if index == 0 else Text(' ' * indent)
            self.console.print(leader + row, width=width,
                               end=end if index == len(rows) - 1 else '\n')


class AgentRenderer:
    def __init__(self, stream, *, width=100, command_log=None, hide_task_completion=False):
        self.width = width
        # Retained presentation must keep its palette even when the supervisor
        # inherits NO_COLOR from a noninteractive caller.
        self.console = Console(file=stream, width=width, force_terminal=True,
                               color_system='truecolor', no_color=False, style='#24292f',
                               theme=Theme({'markdown.code': '#008000 not bold',
                                            'markdown.link': '#0066ff underline',
                                            'markdown.link_url': '#0066ff underline'}),
                               markup=False, highlight=False)
        self.pending = b''
        self.started = set()
        self.command_log = command_log
        self.last_command = None
        self.exploring = False
        self.hide_task_completion = hide_task_completion
        self.task_completion_message = False

    def message(self, text, title='Agent', style='default'):
        self.block(title, SessionMarkdown(clean(text)), style)

    def feed(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        for line in lines:
            self.line(line)

    def finish(self):
        if self.pending:
            self.line(self.pending)
            self.pending = b''

    def heading(self, title, style='bold'):
        self.last_command = None
        self.exploring = False
        self.console.print()
        self.console.print(Text('• ', style='bright_black') + Text(clean(title), style=style))

    def code(self, value, language='text'):
        self.last_command = None
        self.exploring = False
        self.console.print(Syntax(clean(value), language, theme='ansi_light',
                                  background_color='default', word_wrap=True))

    def diff(self, value, path):
        lexer = Syntax.guess_lexer(path, code=clean(value))
        old = new = None
        for line in clean(value).splitlines():
            hunk = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if hunk:
                old, new = map(int, hunk.groups())
                self.console.print(Text(line, style='bright_black'))
                continue
            marker = line[:1]
            if marker not in ('+', '-', ' ') or line.startswith(('+++', '---')):
                self.console.print(Text(line, style='bright_black'))
                continue
            number = old if marker == '-' else new
            prefix = f'{number:>4} {marker} ' if number is not None else marker
            background = '#ffebe9' if marker == '-' else '#dafbe1' if marker == '+' else None
            source = Syntax(line[1:], lexer, theme='friendly', background_color='default').highlight(line[1:])
            source.rstrip()
            for index, part in enumerate(source.wrap(self.console, max(1, self.width - len(prefix)))):
                row = Text(prefix if index == 0 else ' ' * len(prefix), style='#24292f') + part
                row.pad_right(max(0, self.width - row.cell_len))
                if background:
                    row.stylize('on ' + background)
                self.console.print(row)
            if old is not None and marker != '+':
                old += 1
            if new is not None and marker != '-':
                new += 1

    def block(self, title, body, style='default'):
        self.last_command = None
        self.exploring = False
        self.console.print()
        lines = self.console.render_lines(Padding(body, (0, 0)),
                                         self.console.options.update(width=self.width - 2))
        if title != 'Agent':
            self.console.print(Text('• ' + clean(title), style=style))
        for index, line in enumerate(lines):
            self.console.print(Text(('• ' if index == 0 and title == 'Agent' else '  '), style='bright_black'),
                               Text.assemble(*(Text(segment.text, style=segment.style)
                                               for segment in line)), sep='')

    def tree(self, value, style='bright_black', branch=True):
        value = value if isinstance(value, Text) else Text(clean(value), style=style)
        lines = value.wrap(self.console, max(1, self.width - 4))
        for index, line in enumerate(lines):
            self.console.print(Text('  └ ' if index == 0 and branch else '    ', style='bright_black'),
                               line, sep='')

    def command_display(self, item):
        command = clean(item['command'])
        try:
            args = shlex.split(command)
            if (len(args) == 3 and args[0] in ('/bin/bash', '/bin/sh', 'bash', 'sh')
                    and args[1] in ('-lc', '-c')):
                command = args[2]
        except ValueError:
            pass
        return command

    def exploration(self, item):
        command = self.command_display(item)
        try:
            tokens = list(shlex.shlex(command, posix=True, punctuation_chars=True))
            args = shlex.split(command)
        except ValueError:
            return None
        if not args or any(token in (';', '|', '||', '&&', '&', '>', '<', '(', ')')
                           for token in tokens) or any(char in command for char in ('$', '`', '\n')):
            return None
        if args[0] == 'cat' and len(args) > 1 and all(not arg.startswith('-') for arg in args[1:]):
            return 'Read', ', '.join(PurePath(arg).name for arg in args[1:])
        if args[0] == 'sed' and len(args) >= 4 and args[1] == '-n' and re.fullmatch(r'\d+(,\d+)?p', args[2]):
            return 'Read', ', '.join(PurePath(arg).name for arg in args[3:])
        if args[0] == 'rg':
            operands = []
            skip = False
            for arg in args[1:]:
                if skip:
                    skip = False
                elif arg in ('-g', '--glob', '-t', '--type', '-A', '-B', '-C', '--max-count'):
                    skip = True
                elif not arg.startswith('-'):
                    operands.append(arg)
            if operands:
                detail = Text(operands[0])
                if len(operands) > 1:
                    detail.append(' in ', style='bright_black')
                    detail.append(', '.join(PurePath(arg).name for arg in operands[1:]))
                return 'Search', detail
        return None

    def command_heading(self, item):
        exploration = self.exploration(item)
        if exploration:
            grouped = self.exploring
            if not grouped:
                self.heading('Explored')
            action, detail = exploration
            self.tree(Text.assemble((action, '#0066ff'), ' ', detail), branch=not grouped)
            self.exploring = True
            self.last_command = item['id']
            return
        command = self.command_display(item)
        self.exploring = False
        body = Text('Ran ')
        body.stylize('bold', 0, 3)
        code = Text(command)
        match = re.match(r'\S+', command)
        if match:
            code.stylize('bright_blue', match.start(), match.end())
        for match in re.finditer(r"'[^']*'|\"[^\"]*\"", command):
            code.stylize('green', match.start(), match.end())
        body.append_text(code)
        lines = body.wrap(self.console, max(1, self.width - 2))
        self.console.print()
        for index, line in enumerate(lines):
            status = item.get('exit_code')
            style = 'green' if status == 0 else 'red' if status is not None else 'bright_black'
            self.console.print(Text('• ' if index == 0 else '│ ', style=style if index == 0 else 'bright_black') + line)
        self.last_command = item['id']

    def command_result(self, item):
        # Retain full evidence while bounding the visible output preview.
        if self.command_log is not None:
            with self.command_log.open('a', encoding='utf-8') as archive:
                archive.write(f'\nCommand {clean(item["id"])}: {clean(item["command"])}\n')
                archive.write(clean(item.get('aggregated_output', '')) + '\n')
                archive.write(f'Exit: {clean(item.get("exit_code"))}\n')
        status = item.get('exit_code')
        if self.last_command != item['id']:
            self.command_heading(item)
        if status == 0 and self.exploration(item):
            return
        output = clean(item.get('aggregated_output', '').replace('\r\n', '\n')
                       .replace('\r', '\n')).rstrip()
        self.exploring = False
        lines = [row for line in output.splitlines()
                 for row in Text(line).wrap(self.console, max(1, self.width - 4))]
        for index, line in enumerate(lines[:3]):
            self.console.print(Text('  └ ' if index == 0 else '    ', style='bright_black') +
                               Text(line.plain, style='bright_black'))
        if len(lines) > 3:
            location = ' (agent-commands.log)' if self.command_log is not None else ''
            self.console.print(Text(f'    +{len(lines) - 3} lines{location}', style='dim'))
        if status != 0:
            outcome = f'Exit {status}' if status is not None else item.get('status', 'completed')
            self.tree(outcome, style='red')

    def line(self, raw):
        value = raw.decode('utf-8', errors='replace')
        try:
            event = json.loads(value)
        except ValueError:
            self.last_command = None
            self.exploring = False
            self.console.print(Text(clean(value)))
            return
        # Unknown or malformed events remain visible, never control execution.
        try:
            self.event(event)
        except (KeyError, TypeError, AttributeError, ValueError):
            self.code(value, 'json')

    def event(self, event):
        kind = event['type']
        if kind in ('thread.started', 'turn.started'):
            return
        if kind == 'turn.completed':
            if self.task_completion_message:
                self.task_completion_message = False
                return
            self.heading('Turn complete', 'dim')
            return
        if kind in ('error', 'turn.failed'):
            self.heading('Agent error', 'bold red')
            self.code(event.get('message', event.get('error', event)))
            return
        if kind not in ('item.started', 'item.updated', 'item.completed'):
            self.code(json.dumps(event, ensure_ascii=False), 'json')
            return
        item = event['item']
        category = item['type']
        complete = kind == 'item.completed'
        if category == 'reasoning':
            return
        if category == 'agent_message':
            if complete:
                text = item['text']
                # The result file still owns orchestration. This only presents
                # the same structured final message in a readable form.
                try:
                    result = json.loads(text)
                except ValueError:
                    result = None
                if (isinstance(result, dict)
                        and result.get('status') in ('fixed', 'blocked', 'ready_for_vm', 'task_complete')
                        and isinstance(result.get('summary'), str)):
                    if self.hide_task_completion and result['status'] == 'task_complete':
                        # The workflow reports success only after validation and staging.
                        self.task_completion_message = True
                        return
                    title = (result['status'].replace('_', ' ').capitalize()
                             if 'handoff' in result else 'Repair ' + result['status'])
                    style = 'yellow' if result['status'] == 'blocked' else 'green'
                    text = result['summary']
                    if isinstance(result.get('handoff'), str):
                        text += '\n\nNext session prompt:\n\n' + result['handoff']
                else:
                    title, style = 'Agent', 'default'
                self.message(text, title, style)
        elif category == 'command_execution':
            identity = item['id']
            if identity not in self.started:
                self.command_heading(item)
                self.started.add(identity)
            if complete:
                self.command_result(item)
                self.started.discard(identity)
        elif category == 'file_change':
            if complete:
                self.heading('File changes — ' + item.get('status', 'completed'))
                for change in item['changes']:
                    action = change.get('kind', 'update')
                    self.console.print(Text(f'  {action}  {clean(change["path"])}',
                                            style='red' if action == 'delete' else 'green'))
                    if change.get('diff'):
                        self.diff(change['diff'], change['path'])
        elif category == 'todo_list':
            self.heading('Plan')
            for task in item['items']:
                self.console.print(Text(('  ✓ ' if task['completed'] else '  ○ ') +
                                        clean(task['text'])))
        elif category in ('mcp_tool_call', 'web_search'):
            self.heading(('Tool' if category == 'mcp_tool_call' else 'Search') +
                         (' complete' if complete else ' working'))
            if category == 'web_search':
                self.console.print(Text(clean(item['query'])))
            else:
                self.console.print(Text(clean(item['server']) + '.' + clean(item['tool'])))
                for field in ('arguments', 'result', 'error'):
                    if item.get(field) is not None:
                        self.code(json.dumps(item[field], ensure_ascii=False, indent=2), 'json')
        else:
            self.code(json.dumps(event, ensure_ascii=False), 'json')
