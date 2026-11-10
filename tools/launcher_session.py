"""Bounded transcript projection for ONPC: Watch."""

import io
import json
import re
import time
from collections import deque

from rich.console import Console
from rich.text import Text

from launcher_render import COMPACT_LINE, SCROLLBACK_CHARACTERS, clean, retained_tail


def clock_duration(seconds):
    """Elapsed whole minutes, shared by launcher clocks and task-field ages."""
    hours, minutes = divmod(max(0, int(seconds // 60)), 60)
    return f'{hours}h {minutes}m' if hours else f'{minutes}m'


def working_duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f'{clock_duration(minutes * 60)} {seconds}s' if minutes else f'{seconds}s'


class SessionPanel:
    """Retain session text for the Watch webview without terminal ownership."""

    def __init__(self, *, hide_tool_results=False):
        self.console = Console(file=io.StringIO(), force_terminal=True, markup=False,
                               highlight=False, color_system='truecolor', no_color=False)
        self.hide_tool_results = hide_tool_results
        self.transcript = deque()
        self.pending = ''
        self.details = []
        self.question = None
        self.chat_state = {}
        self.input_mode = 'chat'
        self.simplified = True
        self.text_output = None
        self.streaming_lines = []
        self.text_identity = None
        self.simplified_cache = None
        self.webview_cache = {}
        self.webview_text = {}
        self.result_pending = ''
        self.result_activity = 'orphan'
        self.result_detail_pending = False

    def write(self, value):
        if self.hide_tool_results:
            lines = (self.result_pending + value).split('\n')
            self.result_pending = lines.pop()[:SCROLLBACK_CHARACTERS]
            lines = self.visible_lines(lines, incremental=True)
        else:
            lines = (self.pending + value).split('\n')
            self.pending = lines.pop()[:SCROLLBACK_CHARACTERS]
        self.transcript = retained_tail([*self.transcript, *lines])

    def visible_lines(self, logs, *, incremental=False):
        """Watch keeps activity names without displaying captured tool results."""
        if not self.hide_tool_results:
            return logs
        rows = []
        # The bounded transcript (or a reconnect's byte tail) can start in
        # the middle of a result, after its heading has been discarded. Do not
        # expose that orphaned body as prose; resume at the next known block.
        activity = self.result_activity if incremental else 'orphan'
        detail_pending = self.result_detail_pending if incremental else False
        for line in logs:
            text = self.line_text(line)
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
        if incremental:
            self.result_activity = activity
            self.result_detail_pending = detail_pending
        return rows

    def line_text(self, line):
        # These values are read only; callers copy before changing their style.
        text = self.webview_text.get(line)
        return Text.from_ansi(line) if text is None else text

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
            text = self.line_text(line)
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
        stream = record.get('stream', [])
        if not isinstance(stream, list) or any(not isinstance(line, str) for line in stream):
            return
        self.streaming_lines = list(retained_tail(stream))
        lines = list(retained_tail([*record.get('lines', []),
                                   *(['', preview] if preview is not None else [])]))
        identity = record.get('session')
        self.text_output, self.text_identity = lines, identity

    def model_label(self):
        # Retained records are provenance, never a reason to read live config
        # or infer a provider from a native model name.
        return ' '.join(filter(None, (self.chat_state.get('model'), self.chat_state.get('effort'))))

    def webview(self, *, simplified=None):
        """Expose the shared transcript/composer to a native webview host."""
        simplified = self.simplified if simplified is None else simplified
        source = (*self.transcript, *([self.pending] if self.pending else []))
        signature = source, self.hide_tool_results
        cached = self.webview_cache.get(simplified)
        if cached is None or cached[0] != signature:
            # A streamed update changes the tail, not the whole transcript.
            # Retain decoded rows only within the existing history budget.
            self.webview_text = {line: self.line_text(line) for line in source}
            logs = self.visible_lines(source)
            if simplified:
                logs = self.simplified_lines(logs) if logs else None
            self.webview_cache[simplified] = signature, logs
        logs = self.webview_cache[simplified][1]
        if logs is None:
            logs = self.text_output or []
        return dict(lines=[*logs, *self.details, *self.streaming_lines], working=self.working(),
                    model=self.model_label(),
                    simplified=simplified)

    def working(self):
        started = self.chat_state.get('turn_started_at', self.chat_state.get('started_at'))
        if self.chat_state.get('status') == 'running' and started is not None:
            return f'Working ({working_duration(time.time() - started)})'
        return ''
