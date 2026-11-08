"""Shared transcript formatting and presentation of normalized agent events.

Render once in the detached supervisor, so reconnecting observers see the same
agent transcript. Watch reads the retained transcript independently.
"""

import json
import os
import re
import shlex
import stat
from collections import deque
from pathlib import PurePath

from rich.console import Console
from rich.markdown import CodeBlock, Markdown, Paragraph
from rich.padding import Padding
from rich.syntax import Syntax
from rich.style import Style
from rich.text import Text
from rich.theme import Theme


CONTROL = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))|[\x00-\x08\x0b-\x1f\x7f]')

# Bound both row count and text: a stream need not contain any newlines.
SCROLLBACK_LINES = 2000
SCROLLBACK_CHARACTERS = 256 * 1024

# An invisible OSC tag distinguishes mirrored session lines in mixed launcher
# logs. Remove it before Rich's ANSI decoding, which exposes unknown OSC payloads.
# Dedicated session transcripts retain their original text.
SESSION_LINE = '\033]777;onpc-session\007'
# Simplified activity rows stay on one physical line at every viewport width.
COMPACT_LINE = '\033]777;onpc-compact\007'


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


def compact_text(line, width=None):
    """Decode a shared activity preview and reserve its trailing dots."""
    text = Text.from_ansi(line[len(COMPACT_LINE):])
    if width is not None:
        text.truncate(max(0, width - 3), overflow='crop')
    text.append('.' * (3 if width is None else min(3, width)), style='dim')
    return text


def style_task_counts(text):
    """Apply the shared overview/totals palette, overriding retained ANSI colors."""
    counter = re.match(r'^(?:Total )?Tasks: (\d+|—)/(\d+|—)(?:/(\d+|—))?', text.plain)
    if counter:
        text.stylize('not bold default', counter.start(1), counter.end())
        text.stylize('green', *counter.span(1))
        if counter.group(3) is not None:
            text.stylize('#808080', *counter.span(2))


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


class SessionParagraph(Paragraph):
    """Keep top-level prose as logical lines for the observer to wrap."""

    @classmethod
    def create(cls, markdown, token):
        paragraph = super().create(markdown, token)
        paragraph.markdown = markdown
        return paragraph

    def on_enter(self, context):
        super().on_enter(context)
        self.top_level = len(context.stack) == 1

    def __rich_console__(self, console, options):
        if self.top_level:
            identity = len(self.markdown.paragraphs)
            self.markdown.paragraphs[identity] = self.text.copy()
            self.text.stylize(Style(meta={'session_paragraph': identity}))
        yield from super().__rich_console__(console, options)


class SessionMarkdown(Markdown):
    elements = {**Markdown.elements, 'fence': SessionCodeBlock,
                'code_block': SessionCodeBlock, 'paragraph_open': SessionParagraph}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.paragraphs = {}


class SessionTranscript:
    """Mirror rendered agent output into the current session's bounded log."""

    def __init__(self, stream, run, *, append=False):
        self.stream = stream
        self.path = run / 'session-output.log'
        self.line_start = True
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_NONBLOCK | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            os.close(fd)
            raise ValueError('unsafe session transcript')
        if append:
            os.lseek(fd, 0, os.SEEK_END)
        else:
            os.ftruncate(fd, 0)
        self.log = os.fdopen(fd, 'wb')

    def isatty(self):
        return False

    def write(self, value):
        from detached_launcher import compact_log, MAX_LOG_BYTES
        for part in value.splitlines(keepends=True):
            self.stream.write((SESSION_LINE if self.line_start else '') + part)
            self.line_start = part.endswith('\n')
        self.log.write(value.encode('utf-8'))
        self.log.flush()
        if self.log.tell() > MAX_LOG_BYTES:
            compact_log(self.path, writer_fd=self.log.fileno())

    def flush(self):
        self.stream.flush()
        self.log.flush()

    def close(self):
        self.log.close()


class AgentRenderer:
    def __init__(self, stream, *, width=100, command_log=None, hide_task_completion=False,
                 on_usage=None, on_description=None, on_message=None,
                 full_command_output=False):
        self.width = width
        # Retained presentation must keep its palette even when the supervisor
        # inherits NO_COLOR from a noninteractive caller.
        # Rich needs both dimensions to honor an explicit width with TERM=dumb;
        # a second wrap at its 80-column fallback would lose hanging indentation.
        self.console = Console(file=stream, width=width, height=25, force_terminal=True,
                               color_system='truecolor', no_color=False, style='#24292f',
                               theme=Theme({'markdown.code': '#008000 not bold',
                                            'markdown.link': '#0066ff underline',
                                            'markdown.link_url': '#0066ff underline'}),
                               markup=False, highlight=False)
        self.started = set()
        self.command_streams = {}
        self.command_log = command_log
        self.full_command_output = full_command_output
        self.last_command = None
        self.exploring = False
        self.hide_task_completion = hide_task_completion
        self.task_completion_message = False
        self.on_usage = on_usage
        self.on_description = on_description
        self.on_message = on_message
        self.failure = None

    def message(self, text, title='Agent', style='default'):
        self.block(title, SessionMarkdown(clean(text)), style)

    def preview_message(self, text):
        """Replace observer-only prose without appending unconfirmed log text."""
        if self.on_description is None:
            return
        command, exploring = self.last_command, self.exploring
        try:
            with self.console.capture() as capture:
                if text:
                    self.message(text)
        finally:
            self.last_command, self.exploring = command, exploring
        self.on_description(capture.get(), provisional=True)

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
        paragraphs = getattr(body, 'paragraphs', {})
        emitted = set()
        for index, line in enumerate(lines):
            paragraph = next((segment.style.meta['session_paragraph']
                              for segment in line if segment.style
                              and 'session_paragraph' in segment.style.meta), None)
            if paragraph is not None:
                if paragraph in emitted:
                    continue
                emitted.add(paragraph)
                # Retain explicit Markdown breaks, but defer paragraph wrapping
                # to each observer's actual panel width, including after resize.
                for part_index, part in enumerate(paragraphs[paragraph].split('\n', allow_blank=True)):
                    prefix = '• ' if index == 0 and part_index == 0 and title == 'Agent' else '  '
                    self.console.print(Text.assemble(Text(prefix, style='bright_black'), part),
                                       soft_wrap=True)
                continue
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

    def command_output(self, identity, delta):
        """Append running command output without waiting for item completion."""
        stream = self.command_streams.get(identity)
        if stream is None or not delta:
            return
        stream['length'] += len(delta)
        # Keep incomplete lines bounded; sanitize only after joining chunks so
        # an escape sequence split across notifications cannot leak controls.
        pending = stream['pending'] + delta
        rows = pending.split('\n')
        stream['pending'] = rows.pop()
        if stream.get('dropping') and rows:
            rows.pop(0)
            stream['dropping'] = False
        if len(stream['pending']) > 65536:
            stream['pending'] = ''
            stream['dropping'] = True
        if rows:
            if self.last_command != identity:
                self.command_heading(stream['item'])
            for line in rows:
                self.console.print(Text('    ' + clean(line.replace('\r', '\n')),
                                        style='bright_black'), soft_wrap=True)
            self.console.file.flush()

    def command_result(self, item):
        # Retain full evidence while bounding the visible output preview.
        # App-server commands without captured output may explicitly return null.
        output = item.get('aggregated_output') or ''
        if self.command_log is not None:
            with self.command_log.open('a', encoding='utf-8') as archive:
                archive.write(f'\nCommand {clean(item["id"])}: {clean(item["command"])}\n')
                archive.write(clean(output) + '\n')
                archive.write(f'Exit: {clean(item.get("exit_code"))}\n')
        status = item.get('exit_code')
        if self.last_command != item['id']:
            self.command_heading(item)
        # Expanded output is for command results, not the file contents and
        # search matches used by the agent to explore the checkout.
        if status == 0 and self.exploration(item):
            return
        output = clean(output.replace('\r\n', '\n')
                       .replace('\r', '\n')).rstrip()
        self.exploring = False
        if self.full_command_output:
            streamed = self.command_streams.pop(item['id'], None)
            if streamed is not None and streamed['length']:
                # The final item still owns the archive and outcome. Avoid
                # repeating live output; retain any final unstreamed suffix.
                raw = item.get('aggregated_output') or ''
                output = clean(('' if streamed.get('dropping') else streamed['pending']) +
                               raw[streamed['length']:]).rstrip()
            # Observers choose compact or complete presentation locally. Retain
            # every line without wrapping it to the supervisor's fixed width.
            for index, line in enumerate(output.splitlines()):
                self.console.print(Text('  └ ' if index == 0 else '    ', style='bright_black') +
                                   Text(line, style='bright_black'), soft_wrap=True)
            if status != 0:
                outcome = f'Exit {status}' if status is not None else item.get('status', 'completed')
                self.tree(outcome, style='red')
            return
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

    def event(self, event):
        """Present shared events; adapters alone decode native streams."""
        try:
            self.render(event)
        except (KeyError, TypeError, AttributeError, ValueError):
            # Malformed presentation remains inert and visible.
            self.heading('Agent activity')
            self.details(event.data)

    def details(self, value, indent=0):
        """Present structured activity as labelled text, never a wire dump."""
        if isinstance(value, dict):
            for key, part in value.items():
                label = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(key))
                label = label.replace('_', ' ')
                label = label[:1].upper() + label[1:]
                if isinstance(part, (dict, list)):
                    self.console.print(Text('  ' * (indent + 1) + clean(label) + ':'))
                    self.details(part, indent + 1)
                else:
                    text = 'none' if part is None else str(part)
                    self.console.print(Text('  ' * (indent + 1) + clean(label) + ': ' + clean(text)))
        elif isinstance(value, list):
            for part in value:
                self.details(part, indent)
        else:
            self.console.print(Text('  ' * (indent + 1) + clean(value)))

    def agent_activity(self, item, complete):
        tool = item.get('tool') or item.get('kind') or 'Agent activity'
        action = {
            'wait': 'Wait for agents',
            'spawn_agent': 'Start agent',
            'send_input': 'Send message to agent',
            'send_message': 'Send message to agent',
            'resume_agent': 'Resume agent',
            'close_agent': 'Close agent',
        }.get(tool, str(tool).replace('_', ' ').capitalize())
        status = item.get('status') or ('completed' if complete else 'in progress')
        self.heading('Agent activity')
        self.tree(f'{action} — {str(status).replace("_", " ")}')
        # Omit transport IDs and empty placeholders; retain the actual message,
        # recipients and per-agent outcomes when the provider supplies them.
        for field in ('prompt', 'message'):
            if item.get(field):
                self.message(str(item[field]), 'Agent message')
        details = {key: value for key, value in item.items()
                   if value and key not in ('type', 'id', 'tool', 'kind', 'status',
                                            'sender_thread_id', 'senderThreadId',
                                            'prompt', 'message')}
        if details:
            self.details(details)

    def render(self, event):
        kind, data = event.kind, event.data
        if kind == 'usage':
            if self.on_usage is not None:
                self.on_usage(data['usage'])
        elif kind == 'turn_completed':
            if self.task_completion_message:
                self.task_completion_message = False
                return
            self.heading('Turn complete', 'dim')
        elif kind == 'failure':
            if data.get('terminal', True):
                self.failure = data
            self.heading('Agent error', 'bold red')
            self.code(data.get('diagnostic', data['message']))
        elif kind == 'notice':
            self.message(data['text'], 'Agent notice')
        elif kind == 'command_output':
            self.command_output(data['id'], data['text'])
        elif kind == 'text':
            self.item({'type': 'agent_message', 'text': data['text']}, data['complete'])
        elif kind == 'item':
            self.item(data['item'], data['complete'])
        elif kind == 'diagnostic' and 'text' in data:
            self.last_command = None
            self.exploring = False
            self.console.print(Text(clean(data['text'])))
        else:
            self.heading('Agent activity')
            self.details(data.get('value', data))

    def item(self, item, complete):
        category = item['type']
        if category == 'reasoning':
            return
        if category == 'agent_message':
            if complete:
                text = item['text']
                if self.on_message is not None:
                    text = self.on_message(text)
                    if not text:
                        return
                # The result file still owns orchestration. This only presents
                # the same structured final message in a readable form, without
                # duplicating each launcher's accepted status vocabulary.
                try:
                    result = json.loads(text)
                except ValueError:
                    result = None
                descriptive = result is None
                if (isinstance(result, dict)
                        and isinstance(result.get('status'), str)
                        and isinstance(result.get('summary'), str)):
                    if self.hide_task_completion and result['status'] in ('task_complete', 'blocked'):
                        # The workflow validates success and owns blocked questions.
                        self.task_completion_message = True
                        return
                    title = (result['status'].replace('_', ' ').capitalize()
                             if 'handoff' in result else 'Repair ' + result['status'])
                    style = ('yellow' if result['status'] in (
                        'blocked', 'stalled', 'continue', 'prerequisite_required') else 'green')
                    text = result['summary']
                    descriptive = True
                    if isinstance(result.get('handoff'), str):
                        text += '\n\nNext session prompt:\n\n' + result['handoff']
                else:
                    title, style = 'Agent', 'default'
                if self.on_description is None or not descriptive:
                    self.message(text, title, style)
                else:
                    # Copy only actual agent messages, using the identical
                    # rendered text in the complete and descriptive transcripts.
                    with self.console.capture() as capture:
                        self.message(text, title, style)
                    rendered = capture.get()
                    self.console.file.write(rendered)
                    self.on_description(rendered)
        elif category == 'command_execution':
            identity = item['id']
            if identity not in self.started:
                self.command_heading(item)
                self.started.add(identity)
                if self.full_command_output and not self.exploration(item):
                    self.command_streams[identity] = dict(item=item, length=0, pending='')
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
        elif category in ('sub_agent_activity', 'collab_tool_call'):
            self.agent_activity(item, complete)
        elif category in ('mcp_tool_call', 'web_search'):
            self.heading(('Tool' if category == 'mcp_tool_call' else 'Search') +
                         (' complete' if complete else ' working'))
            if category == 'web_search':
                self.console.print(Text(clean(item['query'])))
            else:
                self.console.print(Text(clean(item['server']) + '.' + clean(item['tool'])))
                for field in ('arguments', 'result', 'error'):
                    if item.get(field) is not None:
                        self.details({field: item[field]})
        else:
            self.heading('Agent activity')
            self.details(item)
