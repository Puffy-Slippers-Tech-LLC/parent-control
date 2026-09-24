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
from collections import deque
from pathlib import PurePath

from rich.console import Console
from rich.markdown import CodeBlock, Markdown
from rich.padding import Padding
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme


CONTROL = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))|[\x00-\x08\x0b-\x1f\x7f]')


def clean(value):
    return CONTROL.sub('', str(value))


class LauncherDisplay:
    """Two panes owned by the observer, never by its streaming children.

    A VT terminal cannot scroll two independent panes. Its upper pane therefore
    shows the latest two controller steps. Pipes retain accumulating output.
    Absolute cursor positioning confines every redraw to its own pane.
    """

    def __init__(self, stream):
        self.stream = stream
        self.tty = stream.isatty() and os.environ.get('TERM') != 'dumb'
        self.console = Console(file=stream, force_terminal=True, markup=False,
                               highlight=False, color_system='truecolor', no_color=False)
        self.transcript = deque(maxlen=2000)
        self.pending = ''
        self.steps = []
        self.details = []
        self.size = None
        self.screen = False
        self.previous = None
        self.signal_handlers = {}

    def __enter__(self):
        if self.tty:
            # Ctrl+C already has launcher-specific guarded cancellation. Only
            # replace default termination actions, which bypass finally blocks.
            for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGQUIT):
                previous = signal.getsignal(sig)
                if previous == signal.SIG_DFL:
                    self.signal_handlers[sig] = previous
                    signal.signal(sig, self.terminate)
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

    def write(self, value, *, final=False):
        if not self.tty:
            self.stream.write(value)
            self.stream.flush()
            return
        lines = (self.pending + value).split('\n')
        self.pending = lines.pop()
        self.transcript.extend(lines)
        if final and self.pending:
            self.transcript.append(self.pending)
            self.pending = ''
        self.draw()

    def update(self, steps, details):
        if not self.tty:
            for step in steps:
                if step not in self.steps:
                    self.stream.write('\n'.join(step['lines']) + '\n')
            if details != self.details and details:
                self.stream.write('\n'.join(details) + '\n')
            self.stream.flush()
        self.steps, self.details = steps, details
        self.draw()

    def wrapped(self, lines, width):
        return [row for line in lines for row in
                Text.from_ansi(line).wrap(self.console, width, overflow='fold')]

    def draw(self):
        if not self.tty:
            return
        try:
            size = os.get_terminal_size(self.stream.fileno())
        except (OSError, ValueError):
            size = shutil.get_terminal_size()
        width, height = max(1, size.columns - 1), max(1, size.lines)
        steps = [self.wrapped(step['lines'], width) for step in self.steps[-2:]]
        # Reflow the entire newest step before spending space on its predecessor.
        # Keep even extremely small terminals on the alternate screen: falling
        # back to ordinary output would permanently leak panes into scrollback.
        while len(steps) > 1 and sum(map(len, steps)) + 3 > height:
            steps.pop(0)
        top = [row for step in steps for row in step]
        if len(top) + 3 > height:
            top = top[:max(0, height - 2)]
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
        body += [Text('')] * (available - len(body))
        rows = top + [Text('─' * width, style='dim')] + body
        # Compare physical rows so quiet workers do not repaint either pane.
        encoded = []
        for row in rows:
            with self.console.capture() as capture:
                self.console.print(row, width=width, end='', soft_wrap=True)
            encoded.append(capture.get())
        if not self.screen:
            self.screen = True
            self.stream.write('\033[?1049h\033[H\033[2J\033[?25l')
            self.previous = None
        if size != self.size:
            self.stream.write('\033[H\033[2J')
            self.previous = None
        for index, row in enumerate(encoded):
            if self.previous is None or index >= len(self.previous) or row != self.previous[index]:
                self.stream.write(f'\033[{index + 1};1H\033[2K' + row)
        self.stream.flush()
        self.previous, self.size = encoded, size

    def restore_terminal(self):
        if self.screen:
            self.stream.write('\033[?25h\033[?1049l')
            self.stream.flush()
            self.screen = False
            self.previous = None

    def close(self):
        self.restore_terminal()


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
        prefix = re.match(r'^(?: *[•└│✓○] | {2,})', text.plain)
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
