"""Append-only presentation of noninteractive Codex JSONL events.

Render once in the detached supervisor, so reconnecting observers see the same
transcript without a live display, input handling or dependence on a terminal.
"""

import json
import re

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text


CONTROL = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))|[\x00-\x08\x0b-\x1f\x7f]')


def clean(value):
    return CONTROL.sub('', str(value))


class AgentRenderer:
    def __init__(self, stream, *, width=100):
        self.console = Console(file=stream, width=width, force_terminal=True,
                               color_system='standard', markup=False, highlight=False)
        self.pending = b''
        self.started = set()

    def feed(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        for line in lines:
            self.line(line)

    def finish(self):
        if self.pending:
            self.line(self.pending)
            self.pending = b''

    def heading(self, title, style='bold cyan'):
        self.console.print()
        self.console.print(Text('• ' + clean(title), style=style))

    def code(self, value, language='text'):
        self.console.print(Syntax(clean(value), language, theme='ansi_dark',
                                  background_color='default', word_wrap=True))

    def line(self, raw):
        value = raw.decode('utf-8', errors='replace')
        try:
            event = json.loads(value)
        except ValueError:
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
        if category in ('agent_message', 'reasoning'):
            if complete:
                text = item['text']
                # The result file still owns orchestration. This only presents
                # the same structured final message in a readable form.
                try:
                    result = json.loads(text)
                except ValueError:
                    result = None
                if (category == 'agent_message' and isinstance(result, dict)
                        and result.get('status') in ('fixed', 'blocked')
                        and isinstance(result.get('summary'), str)):
                    self.heading('Repair ' + result['status'],
                                 'bold green' if result['status'] == 'fixed' else 'bold yellow')
                    text = result['summary']
                else:
                    self.heading('Agent' if category == 'agent_message' else 'Thinking',
                                 'bold cyan' if category == 'agent_message' else 'dim')
                self.console.print(Markdown(clean(text), code_theme='ansi_dark'))
        elif category == 'command_execution':
            identity = item['id']
            if identity not in self.started:
                self.heading('Command')
                self.code(item['command'], 'bash')
                self.started.add(identity)
            if complete:
                output = item.get('aggregated_output', '')
                if output:
                    self.code(output, 'diff' if output.startswith('diff --git ') else 'text')
                status = item.get('exit_code')
                self.console.print(Text(f'  Exit {status}' if status is not None else
                                        '  ' + clean(item.get('status', 'completed')),
                                        style='green' if status == 0 else 'yellow'))
                self.started.discard(identity)
        elif category == 'file_change':
            if complete:
                self.heading('File changes — ' + item.get('status', 'completed'))
                for change in item['changes']:
                    action = change.get('kind', 'update')
                    self.console.print(Text(f'  {action}  {clean(change["path"])}',
                                            style='red' if action == 'delete' else 'green'))
                    if change.get('diff'):
                        self.code(change['diff'], 'diff')
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
