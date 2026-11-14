"""Request/response adapter for watch feeds and shared launcher sessions.

Feeds remain view only, without a listening port, VM lease or saved screenshots.
Session chat uses the launcher's existing owner-checked mailbox.
The extension requests at most one snapshot at a time over its private stdio.
"""

import argparse
import base64
import hashlib
import json
import re
import shlex
from pathlib import Path
import struct
import sys
import time
from urllib.parse import unquote, urlsplit
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e2e_watch_viewer import AsyncFeed, Feed, activity_text, progress_text, WAITING, CONNECTED
from ui_watch_transport import Feeds, label
from watch_checkouts import Discovery, checkout, identity
from watch_model import ResourceUsage, VMMemory, viewer_entries
from watch_output import Output, SessionOutput, JsonReader, active_launchers, watch_closed, TAIL_BYTES
from tests.integration.watch_activity import TerminalControls


def inline_video(stream):
    """Transfer the published WebM unchanged, bounded by the bridge limit."""
    limit = 64 * 1024 * 1024
    if stream.seek(0, 2) > limit:
        raise ValueError('Recording exceeds the inline transfer limit; open it on the source host.')
    stream.seek(0)
    data = stream.read(limit + 1)
    if not data:
        raise ValueError('Recording is empty.')
    if len(data) > limit:
        raise ValueError('Recording exceeds the inline transfer limit; open it on the source host.')
    return dict(kind='video', data=base64.b64encode(data).decode('ascii'))


def recording_artifact(uri, anchor, host):
    """Read only a current publication in this host's remote operation store."""
    parsed = urlsplit(uri)
    path = Path(unquote(parsed.path))
    base = Path(anchor) / 'output/test-runs/host/remote'
    if (parsed.scheme != 'onpc-recording' or parsed.netloc != host
            or parsed.query or parsed.fragment or not path.is_absolute()
            or '..' in path.parts or not path.is_relative_to(base)):
        raise ValueError('Invalid recording URI or storage host.')
    parts = path.relative_to(base).parts
    if (len(parts) != 5 or re.fullmatch('[0-9a-f]{64}', parts[0]) is None
            or parts[1:4] != ('output', 'test-runs', 'recordings') or path.suffix != '.webm'):
        raise ValueError('Recording outside this host\'s managed remote storage.')
    from recording_storage import Store
    with Store(root=path.parents[3], create=False).open_published(path) as stream:
        return inline_video(stream)


def remote_recording_artifact(uri):
    """Use current source for one read, preserving the remote host's checkout."""
    from host_dispatch import tool_host
    from vm_selection import vm_config
    root = Path(__file__).resolve().parents[1]
    document = vm_config.read_document(root / 'config/environment.json', validate_agent=False)
    host = vm_config.host_registry(document).get(urlsplit(uri).netloc)
    if host is None or host.name == tool_host(root, document).name:
        raise ValueError('Recording host is not a remote registered host.')
    from regression_process import Control
    from remote_sources import RemoteVM
    import test_launcher
    environment = test_launcher.environment(root)
    for variable in ('ONPC_TEST_VM', 'ONPC_VM_CHECKOUT', 'ONPC_VM_RECORDING_CONTROL',
                     'ONPC_TEST_FAMILY_WORK', 'ONPC_TEST_VM_WORKER', 'ONPC_TEST_VM_BATCH'):
        environment.pop(variable, None)
    data = bytearray()
    def received(block):
        if len(data) + len(block) > 96 * 1024 * 1024:
            raise ValueError('Recording response exceeds transfer limit.')
        data.extend(block)
    with Control().installed() as control:
        status = RemoteVM(root, host=host).run(control,
            ['/usr/bin/python3', '-B', str(root / 'tools/watch_webview.py'),
             '--root', str(root), '--recording', uri], env=environment,
            output=received, stderr_output=lambda block: None, timeout=60)
    if status:
        raise ValueError(f'Recording read failed on {host.name} (status {status}).')
    return json.loads(data)


def status_spans(lines, *, failures=0, category_failures=None, error_log=None,
                 session_waiting=False, launcher=False, branches=()):
    """Keep status colors and emphasis without sending HTML or terminal controls."""
    from rich.text import Text
    from rich.console import Console
    from rich.style import Style
    from document_checks import references
    from launcher_render import BLUE, COMPACT_LINE, SESSION_LINE, clean, compact_text
    console = Console()
    git_names = re.compile(r'(?<![\w/.-])(?:' + '|'.join([
        *(re.escape(name) for name in sorted(branches, key=len, reverse=True)),
        r'[0-9a-fA-F]{64}', r'[0-9a-fA-F]{7,40}',
    ]) + r')(?![\w/-]|\.[\w/-])') if launcher else None
    rows = []
    waiting_heading = False
    for line in lines:
        compact = not launcher and isinstance(line, str) and line.startswith(COMPACT_LINE)
        text = line.copy() if isinstance(line, Text) else (
            compact_text(line) if compact else Text.from_ansi(
                line if launcher else line.replace(SESSION_LINE, '')))
        if not compact and '](' in text.plain:
            # Transcript rows include presentation indentation. Parse the prose
            # without treating that indentation as a Markdown code block.
            prose = text.plain.lstrip(' ')
            indent = len(text.plain) - len(prose)
            linked = Text()
            position = 0
            for reference in references(prose):
                try:
                    uri = urlsplit(reference.destination)
                except ValueError:
                    continue
                if (reference.kind != 'inline' or uri.scheme not in ('file', 'onpc-recording')
                        or (uri.scheme == 'file' and uri.netloc)
                        or uri.query or uri.fragment or not uri.path.startswith('/')
                        or not unquote(uri.path).endswith('.webm')):
                    continue
                start, end = indent + reference.start, indent + reference.end
                linked.append_text(text[position:start])
                label = text[indent + reference.label_start:indent + reference.label_end]
                label.stylize(Style(color=BLUE, underline=True, link=reference.destination))
                linked.append_text(label)
                position = end
            linked.append_text(text[position:])
            text = linked
        if launcher:
            # Resolve branch names from Git and recognize Git object
            # IDs independently of the wording of an agent's closing summary.
            for match in git_names.finditer(text.plain):
                text.stylize('green', *match.span())
            # Preserve launcher emphasis as text spans in the webview, too.
            spans = []
            for segment in text.render(console):
                style = segment.style
                color = style.color if style else None
                # Match the Status session blue for launcher command emphasis,
                # including retained output using ANSI bright blue.
                if color and color.type.name == 'STANDARD' and color.number == 12:
                    color = Style(color=BLUE).color
                themed = color and (color.type.name == 'DEFAULT' or
                                   (color.type.name == 'STANDARD' and color.number in (0, 7, 15)))
                spans.append(dict(text=clean(segment.text), bold=bool(style and style.bold),
                                  link=style.link if style else None,
                                  color=color.get_truecolor().hex if color and not themed else None))
            rows.append(spans)
            continue
        summary_label = re.match(r'^(Total Tasks:|Total Duration:|Ended:)', text.plain)
        if summary_label:
            text.stylize('bold', 0, summary_label.end())
        family_progress = re.fullmatch(r'\S+ \| (?:system|e2e): \((\d+)/\d+\)', text.plain)
        if family_progress:
            text.stylize('green', *family_progress.span(1))
        heading = re.fullmatch(r'VM: (.+) \(([^()]*)\)', text.plain)
        if heading:
            text = text[4:]
            text.stylize('bold', 0, len(heading[1]))
            if session_waiting and heading[2] == 'Waiting for input':
                text = text[:len(heading[1])] + Text(' (')
                text.append('Waiting for session intervention',
                            style=Style(color='red', meta={'waiting': True}))
                text.append(')')
                waiting_heading = True
        match = re.search(r'Waiting for input', text.plain)
        if match:
            text.stylize('red', match.start(), match.end())
        if session_waiting and re.fullmatch(r'Paused\s*[—-]\s*waiting for your answer', text.plain.strip()):
            if waiting_heading:
                continue
            text = Text()
            text.append('Paused - waiting for your answer',
                        style=Style(color='red', meta={'waiting': True}))
        if error_log and 'Overall - ' in text.plain:
            match = re.search(r'\((\d+)/(\d+)\)', text.plain)
            if match:
                category = re.search(r'Category: (\S+)', text.plain)
                failed = ((category_failures or {}).get(category[1], 0)
                          if category and category[1] != 'all' else failures)
                counts = Text(str(max(0, int(match[1]) - failed)), style='green')
                counts.append('/')
                counts.append(str(failed), style=f'red underline link {error_log}')
                counts.append('/' + match[2])
                text = text[:match.start() + 1] + counts + text[match.end() - 1:]
        summary = re.fullmatch(r'(?:Round \d+: )?(Category: .+?) \| (Overall - .+)', text.plain)
        display_lines = ([Text('• ') + text[summary.start(index):summary.end(index)]
                          for index in (1, 2)] if summary else [text])
        for display_line in display_lines:
            spans = []
            for segment in display_line.render(console):
                style = segment.style
                color = style.color if style else None
                # Neutral terminal foregrounds must follow VS Code's light/dark theme.
                themed = color and (color.type.name == 'DEFAULT' or
                                   (color.type.name == 'STANDARD' and color.number in (0, 7, 15)))
                spans.append(dict(text=clean(segment.text), bold=bool(style and style.bold),
                                  compact=compact,
                                  waiting=bool(style and style.meta.get('waiting')),
                                  link=style.link if style else None,
                                  color=color.get_truecolor().hex if color and not themed else None))
            rows.append(spans)
    return rows


def png(pixels, width, height, stride, *, rgba=False, red_first=False):
    """Encode already-validated frame bytes without GTK or extra dependencies."""
    channels = 4 if rgba else 3
    rows = bytearray()
    for y in range(height):
        source = pixels[y * stride:y * stride + width * 4]
        row = bytearray(width * channels)
        row[0::channels] = source[0 if red_first else 2::4]
        row[1::channels] = source[1::4]
        row[2::channels] = source[2 if red_first else 0::4]
        if rgba:
            row[3::channels] = source[3::4]
        rows.append(0)  # PNG filter: None
        rows.extend(row)

    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))

    encoded = (b'\x89PNG\r\n\x1a\n' +
               chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6 if rgba else 2, 0, 0, 0)) +
               chunk(b'IDAT', zlib.compress(rows, 1)) + chunk(b'IEND', b''))
    return 'data:image/png;base64,' + base64.b64encode(encoded).decode('ascii')


def launcher_arguments(record, kind, *, branch, execution_plan=False):
    """Share the displayed action's arguments with its actual invocation."""
    if kind == 'resume' and not execution_plan and 'requested_argv' not in record:
        return ['--branch', branch, '--resume']
    argv = (record.get('stop_argv', record['argv']) if kind in ('stop', 'cancel-stop')
            else record['argv'] if kind == 'add-session'
            else record.get('requested_argv', record['argv']))
    # Replace lifecycle switches; never replay a destructive reset.
    tokens = iter(argv)
    argv = []
    for arg in tokens:
        if arg == '--':
            argv.extend((arg, *tokens))
            break
        if arg == '--add-session':
            next(tokens, None)
        elif not arg.startswith('--add-session=') and arg not in ('--stop', '--cancel-stop', '--resume', '--reload', '--reset'):
            argv.append(arg)
    if kind in ('stop', 'cancel-stop', 'add-session') or 'requested_argv' not in record:
        argv = ['--branch', branch, *argv]
    if kind == 'add-session':
        return ['--add-session', '5', *argv]
    return argv if kind == 'resume' and execution_plan else [f'--{kind}', *argv]


class Viewer:
    def __init__(self, root):
        self.root = root
        self.discovery = Discovery(root)
        self.branches = ()
        self.roots = {root: root.name}
        self.ui = {}
        self.vms = {}
        self.configured = {}
        self.images = {}
        self.outputs = {}
        self.launcher_reader = JsonReader()
        self.status_cache = {}
        self.span_cache = {}
        self.sent_runs = {}
        self.launcher_logs = {}
        self.launcher_controls = {}
        self.sessions = {}
        self.resources = ResourceUsage()
        self.vm_memory = {}
        self.artifact_links = set()
        self.case_links = set()
        self.run_times = None
        self.run_times_scope = None
        self.run_times_at = 0
        self.timing_records = {}

    def cached_spans(self, root, kind, lines, *, branches=()):
        """Reuse unchanged rows when a streaming update changes the text tail."""
        key = root, kind
        previous = self.span_cache.get(key, {})
        current, rows = {}, []
        for line in lines:
            if isinstance(line, str):
                line_key = line, branches
                spans = current.get(line_key, previous.get(line_key))
                if spans is None:
                    spans = status_spans([line], launcher=kind == 'launcher', branches=branches)
                current[line_key] = spans
            else:
                # Rich Text is mutable; never cache it by object identity.
                spans = status_spans([line])
            rows.extend(spans)
        # Drop rows that left this body's bounded transcript.
        self.span_cache[key] = current
        return rows

    def launcher_command(self, action):
        """Resolve only a displayed, unchanged run into its public invocation."""
        from watch_output import read_json, active_run
        try:
            output = self.outputs.get(Path(action['root']))
            if output is None or output.run is None or str(output.run) != action['run']:
                raise ValueError('Launcher changed; refresh before trying again.')
            run = active_run(output.run.parent, workflow=output.run.parent.name not in (
                'sessions', 'sessions-host') and not output.run.parent.name.startswith('vm-'),
                include_idle=True)
            if run != output.run:
                raise ValueError('Launcher changed; refresh before trying again.')
            if action['kind'] == 'close':
                if (watch_closed(run) or any(candidate == run for candidate, _name in
                                             active_launchers(output.root, JsonReader()))):
                    raise ValueError('Launcher is running or already closed; refresh before trying again.')
                record = read_json(run.parent / 'current.json', 4096)
                return dict(ok=True, root=str(output.root), run=str(run),
                            launcher=record.get('launcher', 'launcher'), argv=[])
            if action['kind'] == 'kill' and not any(
                    candidate == run for candidate, _name in active_launchers(output.root, JsonReader())):
                raise ValueError('Launcher is no longer active; refresh before trying again.')
            record = read_json(run.parent / 'current.json')
            allowance_key = None
            if action['kind'] == 'add-session':
                from launcher_runtime import SessionAllowance
                allowance_key = SessionAllowance(run).read().get('key')
                if (not any(candidate == run for candidate, _name in active_launchers(output.root, JsonReader()))
                        or allowance_key is None):
                    raise ValueError('No active session allowance; refresh before trying again.')
            name, argv = record.get('launcher'), record.get('requested_argv', record.get('argv'))
            if action['kind'] in ('stop', 'cancel-stop'):
                argv = record.get('stop_argv', argv)
            if (not isinstance(name, str) or not re.fullmatch(r'[\w.-]{1,100}', name)
                    or not isinstance(argv, list) or any(not isinstance(arg, str) or '\0' in arg for arg in argv)):
                raise ValueError('Restart this launcher normally to publish its command parameters.')
            command = output.root / 'tools' / name
            if command.is_symlink() or not command.is_file():
                raise ValueError('Public launcher is unavailable.')
            return dict(ok=True, root=str(output.root), run=str(run), launcher=name,
                        allowance_key=allowance_key,
                        argv=([] if action['kind'] == 'kill' else
                              launcher_arguments(record, action['kind'], branch=self.roots[output.root],
                                                 execution_plan=output.execution_plan)))
        except (OSError, ValueError, KeyError, TypeError) as error:
            return dict(ok=False, error=str(error))

    def delete_run_times(self, tokens):
        from vm_run_times import delete
        try:
            if not tokens or any(token not in self.timing_records for token in tokens):
                raise ValueError('Run times are no longer published; refresh before deleting.')
            for token in dict.fromkeys(tokens):
                root, record = self.timing_records[token]
                if root not in self.roots:
                    raise ValueError('Checkout is no longer available.')
                delete(root, record)
            return dict(ok=True)
        except (OSError, ValueError, KeyError, TypeError) as error:
            return dict(ok=False, error=str(error))
        finally:
            self.run_times = None
            self.timing_records.clear()

    def artifact(self, request):
        """Serve only artifacts published by this reader, never arbitrary paths."""
        from watch_output import open_private
        uri = request['uri']
        try:
            parsed = urlsplit(uri)
            remote_recording = parsed.scheme == 'onpc-recording'
            if uri not in self.artifact_links and not remote_recording:
                raise ValueError('Artifact is no longer published by this reader.')
            if ((parsed.scheme not in ('', 'file') and not remote_recording)
                    or (parsed.netloc and not remote_recording) or parsed.query or parsed.fragment):
                raise ValueError('Invalid artifact URI.')
            path = Path(unquote(parsed.path))
            if not path.is_absolute() or '..' in path.parts:
                raise ValueError('Invalid artifact path.')
            if remote_recording:
                from host_dispatch import tool_host
                for root in self.roots:
                    if parsed.netloc == tool_host(root).name and path.is_relative_to(root):
                        return recording_artifact(uri, root, parsed.netloc)
                return remote_recording_artifact(uri)
            if uri in self.case_links:
                if not any(path.resolve().is_relative_to(root.resolve() / 'tests') for root in self.roots):
                    raise ValueError('Case file outside checkout tests.')
                if request['inline']:
                    if path.stat().st_size > 2 * 1024 * 1024:
                        raise ValueError('Case file exceeds inline limit.')
                    return dict(kind='text', text=path.read_text())
                return dict(kind='file', uri=path.as_uri(), media_type='text/plain')
            video = path.suffix == '.webm' and any(
                path.parent == root / 'output/test-runs/recordings' for root in self.roots)
            error_log = any(output.repair and output.run is not None
                            and path == output.run.parent / 'errors.md'
                            for output in self.outputs.values())
            if not video and not error_log:
                raise ValueError('Unsupported artifact.')
            with open_private(path) as stream:
                if not request['inline']:
                    return dict(kind='file', uri=path.as_uri(),
                                media_type='video/webm' if video else 'text/markdown')
                if video:
                    return inline_video(stream)
                limit = 2 * 1024 * 1024
                data = stream.read(limit + 1)
                if len(data) > limit:
                    raise ValueError('Artifact exceeds the inline transfer limit; open it on the source host.')
            return dict(kind='text', text=data.decode('utf-8', errors='replace'))
        except (OSError, ValueError) as error:
            return dict(error=str(error))

    def run_status(self, session_root=None, session_roots=()):
        from launcher_render import clean
        from launcher_display import launcher_status_color, launcher_status_line
        branches = self.discovery.poll_branches()
        if branches is not None:
            self.branches = branches
        session_roots = set(session_roots)
        if session_root:
            session_roots.add(session_root)
        sections = []
        workflow_roots = {run: root for root in self.roots
                          for run, _name in active_launchers(root, self.launcher_reader,
                              include_idle=True, workflows_only=True)}
        workflow_bases = {run.parent: run for run in workflow_roots}

        def supervisor(run):
            if run is None:
                return None
            try:
                record = self.launcher_reader.read(run.parent / 'current.json', 4096)
                observer = Path(record['observer'])
                if record['run'] == run.name:
                    if observer.name.startswith('pipeline-'):
                        observer = observer.parent
                    if re.fullmatch('[0-9a-f]{32}', observer.name):
                        # A newer parent run can precede its replacement child.
                        return workflow_bases.get(observer.parent)
            except (OSError, ValueError, KeyError, TypeError):
                pass
            return None

        def observe(root, run):
            owner = supervisor(run)
            if owner is not None:
                root, run = workflow_roots[owner], owner
            if run.parent not in self.outputs:
                self.outputs[run.parent] = Output(root, launcher_base=run.parent)

        for checkout_root in self.roots:
            # Child runners can be dispatched into another worktree. Their
            # progress already appears in the controlling workflow's section.
            candidates = list(active_launchers(checkout_root, self.launcher_reader, include_idle=True))
            for run, _name in candidates:
                observe(checkout_root, run)
        # Discovery may learn a child's checkout before its parent's checkout.
        for output in tuple(self.outputs.values()):
            if output.run is not None:
                observe(output.root, output.run)
        for root, output in self.outputs.items():
            branch = self.roots[output.root]
            label, active, reset, data = output.poll()
            if reset or root not in self.launcher_logs:
                self.launcher_logs[root] = ''
                self.launcher_controls[root] = TerminalControls()
            if data:
                text = output.decoder.decode(self.launcher_controls[root].feed(data))
                self.launcher_logs[root] = (self.launcher_logs[root] + text)[-TAIL_BYTES:]
            if root not in self.sessions:
                self.sessions[root] = SessionOutput(output)
            session = self.sessions[root]
            session.poll()
            # Session discovery can observe a newly admitted owner after the
            # output poll. Do not publish the previous outcome beside live work.
            active = active or session.active
            closed = (output.run is not None and not active and not session.active
                      and watch_closed(output.run))
            if supervisor(output.run) is not None:
                continue
            status = '' if active else output.completion_status()
            if active and output.run is not None:
                try:
                    requested = self.launcher_reader.read(output.run / 'reload.json', 4096)
                    try:
                        accepted = self.launcher_reader.read(output.run / 'reload-accepted.json', 4096)
                    except FileNotFoundError:
                        accepted = None
                    if isinstance(requested, str) and requested != accepted:
                        status = 'Reload Requested'
                except (OSError, ValueError, TypeError):
                    pass
            if active and output.run is not None and any(
                    (output.run / marker).exists() for marker in ('stop', 'cancel')):
                status = 'Stop Requested'
                record = self.launcher_reader.read(output.run.parent / 'current.json', 4096)
                if (not record.get('cancel_stop') or any(
                        (output.run / marker).exists() for marker in ('stopping', 'cancel'))):
                    status = 'Stopping'
            lines = []
            error_lines = []
            failures, error_log = 0, None
            category_failures = {}
            repair_lines = []
            pending_repairs = []
            summary = []
            status_index = 0
            steps = []
            status_available = True
            phase = ''
            if output.run is not None:
                try:
                    steps, details = output.status(active)
                    repair_progress = output.repair_progress()
                    pending_repairs = repair_progress['items']
                    if pending_repairs:
                        blocked = repair_progress['blocked']
                        repair_lines = [f'Unresolved failures: {repair_progress["total"]}',
                            ('New test admission paused; waiting for admitted attempts and cleanup before repair.'
                             if blocked else 'Failures queued; independent tests may continue.')]
                        if repair_progress['total'] > len(pending_repairs):
                            repair_lines.append(f'Showing the latest {len(pending_repairs)} failures.')
                        for ticket in pending_repairs:
                            repair_lines.extend([
                                f'{ticket["vm"] or "Host"} | {ticket["category"]} | {ticket["case"] or "preparation"}',
                                f'Impact: {ticket["impact"]} — {ticket["reason"]}'])
                    if active and not status and output.repair:
                        try:
                            repair_state = output.reader.read(output.run / 'checkpoint.json', 2 * 1024 * 1024)
                        except (OSError, ValueError):
                            repair_state = {}
                        phase = next((clean(line).removeprefix('Status: ')
                                      for step in reversed(steps) for line in reversed(step['lines'])
                                      if clean(line).startswith('Status: ')), '')
                        if repair_state.get('pending') is not None:
                            status = 'Committing Fix'
                        elif phase in ('Rechecking failed case', 'Verifying repair', 'Collecting diagnostic evidence'):
                            status = 'Verifying'
                        elif phase == 'Checking failure impact' and session.active:
                            status = 'Checking Impact'
                        elif phase.startswith(('fixing errors', 'Repairing failed case',
                                               'validating retained response')) or session.active:
                            status = 'Repairing'
                        elif pending_repairs:
                            status = 'Repair Pending'
                        elif phase == 'Checking failure impact':
                            status = 'Checking Impact'
                    if active and not status and output.closing_task(steps, session_inactive=not session.active):
                        status = 'Closing Task'
                    summary = output.task_summary(active)
                    lines = [*summary, *(['─'] if summary else [])]
                    lines.extend(line for step in steps
                             if not (output.repair and step['key'] == 'pipelines')
                             for line in step['lines'] if not clean(line).startswith('Status: '))
                    status_index = len(summary) if summary else len(lines)
                    if output.repair:
                        details = [line for line in details
                                   if not clean(line).startswith(('VM pipelines | concurrency ',
                                                                  'Repair queue: '))]
                        while details and not clean(details[0]).strip():
                            details.pop(0)
                    if details:
                        if lines:
                            lines.append('─')
                        lines.extend(details)
                    if repair_lines:
                        lines.extend(['─', *repair_lines])
                except (OSError, ValueError, KeyError, TypeError):
                    lines = ['Run status unavailable']
                    error_lines = ['Error status unavailable']
                    status_available = False
                if output.repair:
                    try:
                        state = output.reader.read(output.run / 'checkpoint.json', 2 * 1024 * 1024)
                        targets = {tuple(item['failure']) for item in state.get('failed_cases', [])}
                        failures = len(targets)
                        for category, _case, _vm in targets:
                            category_failures[category] = category_failures.get(category, 0) + 1
                        error_log = (output.run.parent / 'errors.md').as_uri()
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
            session_run = session.run if session.active else None
            session_number = None
            session_allowance = None
            # Retain the attempt number through verification, but mark the
            # transcript inactive when its agent and pending questions finish.
            session_inactive = not session.active
            if output.execution_plan:
                try:
                    state = output.reader.read(output.run / 'checkpoint.json', limit=2 * 1024 * 1024)
                    number = state.get('task_sessions')
                    if state.get('phase') != 'complete' and type(number) is int and number > 0:
                        session_number = number
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            elif output.repair and session.run is not None:
                # The case remains unfinished during verification and between
                # agent attempts. Only accepted repair close-out removes it.
                try:
                    failure = session.state.get('repair_failure')
                    number = session.state.get('task_session')
                    if isinstance(failure, list) and type(number) is int and number > 0:
                        state = session.reader.read(session.run / 'checkpoint.json', limit=2 * 1024 * 1024)
                        repair = state.get('repairs', {}).get(json.dumps(failure))
                        if repair is not None:
                            number -= repair.get('session_start', 0)
                            if number > 0:
                                session_number = number
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            try:
                allowance = output.reader.read(output.run / 'session-allowance.json')
                if (allowance.get('key') is not None
                        and type(allowance.get('used')) is int and type(allowance.get('limit')) is int):
                    session_number, session_allowance = allowance['used'], allowance['limit']
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                pass
            if (output.repair and session.active and session.owner == output.run
                    and session_number is not None and session.state.get('status') == 'running'
                    and len(session.state['repair_failure']) == 3
                    and all(isinstance(part, str) for part in session.state['repair_failure'])):
                from regression import duration_text
                category, case, vm = session.state['repair_failure']
                started = session.state.get('started_at')
                if category == 'system' and case.startswith('check_') and isinstance(started, (int, float)):
                    elapsed = duration_text(time.time() - started)
                    current_vm = ''
                    for index, line in enumerate(lines):
                        plain = clean(line).strip()
                        heading = re.fullmatch(r'VM: (.+) \([^()]*\)', plain)
                        if heading:
                            current_vm = heading[1]
                        if current_vm == vm and re.match(
                                r'^\[[^]]+\] Check: ' + re.escape(case) + r' - ', plain):
                            lines[index] = line + f' | Session {session_number}: {elapsed}'
            question = session.panel.question if session.panel and session.panel.question else None
            waiting = bool(session.active and (question or session.panel.chat_state.get('status') in ('waiting', 'blocked')))
            deadline = question.get('deadline') if question else None
            if waiting and not any(re.fullmatch(r'Paused\s*[—-]\s*waiting for your answer',
                                               clean(line).strip())
                                   for line in lines):
                lines.append('Paused - waiting for your answer')
            # A new question replaces the old clock, even within the same session.
            prompt_id = question.get('id') if question else None
            status_value = status or ('Running' if active else output.completion_status() or 'Idle')
            status_color = launcher_status_color(status_value)
            status_detail = status_value
            if status_value == 'Repair Pending':
                status_detail = ('Repair pending — waiting for active tests and VM cleanup'
                                 if blocked else
                                 'Repair pending — waiting for independent tests to finish')
            elif status_value == 'Checking Impact':
                status_detail = 'Checking whether the failure affects other tests'
            elif status_value == 'Verifying':
                status_detail = {
                    'Rechecking failed case': 'Rechecking the failed case before repair',
                    'Collecting diagnostic evidence': 'Collecting diagnostic evidence',
                }.get(phase, 'Verifying the repaired case')
            elif status_value == 'Committing Fix':
                status_detail = 'Committing and propagating the verified fix'
            elif waiting:
                status_detail = 'Waiting for your answer'
            content_status = launcher_status_line(status_detail, status_color)
            if status_available and output.run is not None:
                try:
                    error_lines = output.error_status(steps, pending_repairs=pending_repairs,
                        prefer_pending=status_value in ('Repair Pending', 'Checking Impact'),
                        status_override=(None if session.active and not waiting
                                         and status_value in ('Running', 'Repairing') else status_detail),
                        status_color=status_color)
                    content_status = error_lines[-1]
                except (OSError, ValueError, KeyError, TypeError):
                    error_lines = ['Error status unavailable']
            if status_available:
                # The summary remains fixed above the scrolling test history.
                lines.insert(status_index, content_status)
            signature = lines, failures, category_failures, error_log, session_run, waiting, deadline, prompt_id
            if self.status_cache.get(root, (None,))[0] != signature:
                self.status_cache[root] = signature, status_spans(lines, failures=failures,
                    category_failures=category_failures, error_log=error_log,
                    session_waiting=waiting)
            session_view = None
            if str(root) in session_roots and (session.panel or repair_lines):
                session_view = (session.panel.webview() if session.panel else
                                dict(lines=[], model='', simplified=True))
                transcript = session_view.pop('lines')
                if repair_lines:
                    transcript = [*repair_lines,
                        'Agent session active.' if session.active else
                        'No agent session active; repair remains queued.',
                        '', *transcript]
                session_view['rows'] = self.cached_spans(root, 'session', transcript)
                session_view['input_enabled'] = session.input_enabled
            sections.append(dict(id=str(root), checkout=str(output.root), label=f'[{branch}]' +
                (f' {label}' + (f' ({status})' if status else '') if label else ''),
                active=active or session.active, closed=closed, status=status, rows=self.status_cache[root][1],
                status_color=status_color,
                run=str(output.run) if output.run is not None else None,
                launcher_output=self.launcher_logs[root],
                launcher_rows=self.cached_spans(root, 'launcher', self.launcher_logs[root].split('\n'),
                                                branches=self.branches),
                error_rows=self.cached_spans(root, 'error', error_lines),
                session=session.identity,
                session_active=session.active,
                session_number=session_number, session_inactive=session_inactive,
                session_allowance=session_allowance,
                session_waiting=waiting, session_deadline=deadline, session_question=prompt_id,
                session_view=session_view))
            sections[-1]['launcher_close'] = bool(output.run is not None and not active and not session.active)
            try:
                record = self.launcher_reader.read(output.run.parent / 'current.json') if output.run else {}
                sections[-1]['launcher_controls'] = record.get('run') == output.run.name and isinstance(record.get('argv'), list)
                name, argv = record.get('launcher'), record.get('requested_argv', record.get('argv'))
                if (sections[-1]['launcher_controls'] and isinstance(name, str)
                        and isinstance(argv, list) and all(isinstance(arg, str) for arg in argv)):
                    sections[-1]['launcher_command'] = shlex.join([f'tools/{name}',
                        *([] if 'requested_argv' in record else ['--branch', branch]), *argv])
                    kind = 'cancel-stop' if status == 'Stop Requested' else 'stop' if active or session.active else 'resume'
                    sections[-1]['launcher_action_command'] = shlex.join([f'tools/{name}',
                        *launcher_arguments(record, kind, branch=branch, execution_plan=output.execution_plan)])
                    sections[-1]['launcher_reload_command'] = shlex.join([f'tools/{name}',
                        *launcher_arguments(record, 'reload', branch=branch, execution_plan=output.execution_plan)])
                    sections[-1]['launcher_kill'] = active
                    if active and session_allowance is not None and status not in ('Stopping', 'Stop Requested'):
                        sections[-1]['launcher_add_session_command'] = shlex.join([f'tools/{name}',
                            *launcher_arguments(record, 'add-session', branch=branch, execution_plan=output.execution_plan)])
            except (OSError, ValueError, AttributeError, TypeError):
                sections[-1]['launcher_controls'] = False
        # VM selections have independent publications, but finished results
        # occupy one tile per launcher and branch. Use start time, not directory
        # mtime: a late-finishing older run must not replace a newer invocation.
        retained = [section for section in sections if section['run'] or section['session']]
        latest = {}
        identities = {}
        for section in retained:
            output = self.outputs[Path(section['id'])]
            try:
                record = self.launcher_reader.read(output.run.parent / 'current.json', 4096)
                if record.get('run') != output.run.name:
                    continue
                name = record.get('launcher') or output.label
                started = record.get('started_at')
                if not isinstance(started, (int, float)):
                    started = output.run.stat().st_mtime
                key = self.roots[output.root], name
                rank = started, section['id']
                identities[section['id']] = key, rank
                latest[key] = max(latest.get(key, rank), rank)
            except (OSError, ValueError, AttributeError, TypeError):
                continue
        return [section for section in retained if not section.pop('closed') and (section['active']
                or section['id'] not in identities
                or identities[section['id']][1] == latest[identities[section['id']][0]])]

    def close(self):
        self.discovery.close()
        for feeds in self.ui.values():
            feeds.close()
        for feed, _meta in self.vms.values():
            feed.close()

    def screen(self, entry, frame, visible, *, updates=False):
        if not visible or frame == 'waiting' or (frame is not None and frame[1]['state'] != 'live'):
            self.images.pop(entry, None)
            return {'screen': None}
        if frame is None or not frame[2]:
            return {}
        _sequence, meta, pixels, cursor = frame
        signature = (meta['width'], meta['height'], meta['stride'], meta['format'],
                     zlib.crc32(pixels), zlib.crc32(cursor),
                     *(meta[key] for key in ('cursor_on', 'cursor_x', 'cursor_y', 'hot_x', 'hot_y',
                                            'cursor_width', 'cursor_height')))
        previous = self.images.get(entry)
        if previous is not None and previous[0] == signature:
            return {}
        # Cursor movement must not re-encode an unchanged full-size desktop.
        encoded = (previous[1] if previous is not None and previous[0][:5] == signature[:5]
                   else png(pixels, meta['width'], meta['height'], meta['stride'],
                            red_first=meta['format'] in (0x20030888, 0x20038888)))
        self.images[entry] = signature, encoded
        image = dict(width=meta['width'], height=meta['height'])
        if not updates or previous is None or previous[0][:5] != signature[:5]:
            image['image'] = encoded
        if cursor and meta['cursor_on']:
            image['cursor'] = dict(image=png(cursor, meta['cursor_width'], meta['cursor_height'],
                meta['cursor_width'] * 4, rgba=True), x=meta['cursor_x'] - meta['hot_x'],
                y=meta['cursor_y'] - meta['hot_y'], width=meta['cursor_width'], height=meta['cursor_height'])
        return {'screen': image}

    def snapshot(self, request):
        # A partial first inventory would remove retained panels after reconnect.
        # Leave time within the bridge's ten-second request deadline for rendering.
        if not self.discovery.ready.wait(timeout=5):
            raise TimeoutError('watch: initial checkout discovery timed out')
        result = None
        action = request.get('session_action')
        if action:
            try:
                session = self.sessions.get(Path(action['root']))
                if (session is None or session.panel is None
                        or session.identity != action['session']):
                    raise ValueError('Session changed; review the current session before sending.')
                question = session.panel.question
                if (action['kind'] != 'simplified' and action['question'] !=
                        (question['id'] if question else '')):
                    raise ValueError('Question changed; review the current session before sending.')
                if action['kind'] == 'simplified':
                    # This changes only the observer's presentation, including
                    # the retained transcript after its launcher has exited.
                    session.panel.simplified = not session.panel.simplified
                elif not session.current():
                    raise ValueError('Session changed; review the current session before sending.')
                elif action['kind'] == 'send':
                    if not session.input_enabled:
                        raise ValueError('This session is not accepting input.')
                    session.send(action['text'])
                elif action['kind'] == 'extend':
                    session.extend_deadline(action['text'])
                result = dict(id=action['id'], ok=True)
            except (OSError, ValueError) as error:
                result = dict(id=action['id'], ok=False, error=str(error))
        if request.get('reset'):
            self.images.clear()
        self.roots.update(self.discovery.poll() or {})
        changed = self.discovery.poll_vms()
        if changed is not None:
            self.configured = changed
        for root in self.roots:
            if root not in self.ui:
                self.ui[root] = Feeds(root=root)
        wanted = [(root, name) for root, configured in self.configured.items() for name in configured]
        for entry in tuple(self.vms):
            if entry not in wanted:
                self.vms.pop(entry)[0].close()
                self.vm_memory.pop(entry, None)
        for entry in wanted:
            if entry not in self.vms:
                self.vms[entry] = [AsyncFeed(Feed(entry[1], root=entry[0])), {}]

        scope = request.get('scope', 'all')
        if scope not in ('all', *(str(root) for root in self.roots)):
            scope = 'all'
        selected = request.get('selected', 'all')
        entries, ids, frames_by_entry = {}, {}, {}

        def entry_id(root, key):
            # A global VM tab keeps its identity as its controller moves worktrees.
            return key if key.startswith('vm-') else identity(root) + '-' + key

        def visible(root, key):
            return scope in ('all', str(root)) and selected in ('all', entry_id(root, key))

        for root, feeds in self.ui.items():
            prefix = identity(root) + '-ui-'
            ui_selected = selected[len(prefix):] if selected.startswith(prefix) else None
            pixels = scope in ('all', str(root)) and (selected == 'all' or ui_selected is not None)
            frames = feeds.poll(pixels=pixels, selected=ui_selected)
            for run, frame in sorted(frames.items(), key=lambda item: label(item[1][1].get('branch', ''))):
                key, meta = 'ui-' + run, frame[1]
                entry = str(root), key
                view = dict(kind='ui', heading=label(meta.get('test', '')) or 'Preparing UI worker',
                    step='', status=f"{label(meta.get('phase', ''), 32)} · " +
                    ('Live' if meta['state'] == 'live' else label(meta.get('detail', 'Waiting for frames'))) +
                    ' · View only', activity='')
                frames_by_entry[entry] = frame
                entries[entry] = view, 'UI - ' + label(meta.get('branch', ''), 120), True, True

        for (root, name), state in self.vms.items():
            feed, meta = state
            key = 'vm-' + name.encode('ascii').hex()
            entry = str(root), key
            frame = feed.poll(pixels=visible(root, key))
            if frame == 'waiting':
                meta = state[1] = {}
            elif frame is not None:
                meta = state[1] = frame[1]
            progress, activity = feed.progress(), feed.activity()
            active = bool(meta or progress or (activity and activity.get('operation_active')))
            locked = bool(progress or (activity and activity.get('operation_active')) or
                          (meta and meta.get('lease_locked', True)))
            title, step, operation = progress_text(dict(meta, **({'progress': progress} if progress else {})))
            case = progress or meta.get('progress')
            if case:
                title = f"[{case['case_id']}] {case['title']}"
            view = dict(kind='vm', heading=title, step=step,
                memory=self.vm_memory.setdefault((root, name), VMMemory()).chart(meta),
                status=activity_text(activity, progress or meta.get('progress')) or operation or
                    ('VM running · Waiting for the next operation' if meta.get('state') == 'live' else
                     CONNECTED if meta.get('lease_locked') else WAITING),
                activity=(activity or {}).get('text', ''))
            view['status'] = re.sub(r' - (\([^()]+\))$', r' \1',
                                   re.sub(r'\bsnapshot "([^"]+)"', r'snapshot \1', view['status']))
            frames_by_entry[entry] = frame
            entries[entry] = view, name, active, locked
            ids[entry] = self.configured[root][name].id

        scoped = viewer_entries(entries, scope=scope, vm_ids=ids,
                                current_vms={'vm-' + name.encode('ascii').hex()
                                             for name in self.configured.get(self.root, {})})
        valid_ids = {entry_id(Path(root), key) for root, key in scoped}
        if selected not in valid_ids and selected != 'run-time':
            selected = 'all'
        runs = self.run_status(request.get('session_root'), request.get('session_roots', ()))
        # Follow the displayed terminal sections, including changes on refresh.
        # Checkouts without a displayed run follow in discovery order.
        ordered_roots = dict.fromkeys([section['checkout'] for section in runs] +
                                     [str(root) for root in self.roots])
        root_order = {root: index for index, root in enumerate(ordered_roots)}
        values, shown = [], set()
        for (root, key), (view, name, active, locked) in sorted(
                scoped.items(), key=lambda item: root_order[item[0][0]]):
            identifier = entry_id(Path(root), key)
            entry = root, key
            render = active if selected == 'all' else selected == identifier
            if render:
                shown.add(entry)
            view.update(self.screen(entry, frames_by_entry[entry], render,
                                    updates=request.get('updates', False)))
            values.append(dict(view, id=identifier, source=identity(Path(root)),
                label=f'[{self.roots[Path(root)]}] {name}', active=active, locked=locked))
        self.images = {entry: value for entry, value in self.images.items() if entry in shown}
        self.artifact_links = {part['link'] for run in runs
            for row in [*run['rows'], *run['error_rows'], *run['launcher_rows'],
                        *((run.get('session_view') or {}).get('rows', []))]
            for part in row if part.get('link')}
        run_times = []
        self.case_links = set()
        if selected == 'run-time':
            from vm_run_times import load
            selection = tuple(root for root in self.roots if scope in ('all', str(root)))
            now = time.monotonic()
            if self.run_times is None or selection != self.run_times_scope or now - self.run_times_at >= 60:
                self.run_times = []
                self.timing_records.clear()
                for root in selection:
                    for row in load(root):
                        token = hashlib.sha256(json.dumps([str(root), row['category'], row['id'],
                            row['vm'], row['completed_at']]).encode()).hexdigest()
                        self.timing_records[token] = root, dict(row)
                        self.run_times.append(dict(row, delete_token=token))
                self.run_times_scope, self.run_times_at = selection, now
            run_times = self.run_times
            for row in run_times:
                self.case_links.add(row['case_link'])
                self.artifact_links.update(link for link in (row['case_link'], row['recording']) if link)
        else:
            self.run_times = None
            self.run_times_scope = None
            self.timing_records.clear()
        response = dict(protocol=1, capabilities=dict(sessions=True, session_roots=True, updates=True,
                    artifacts=True, delete_run_times=True),
                    scope=scope, selected=selected, entries=values,
                    run_times=run_times,
                    runs=runs, session_result=result,
                    checkouts=[dict(id=str(root), label=branch) for root, branch in self.roots.items()],
                    resources=self.resources.text(), resource_sample=self.resources.last,
                    resource_charts=self.resources.charts)
        # Keep full state internally for input/artifact guards. Only the wire
        # representation omits unchanged bodies, and only after negotiation.
        previous_runs = self.sent_runs if not request.get('reset') else {}
        self.sent_runs = {run['id']: run for run in runs}
        if request.get('updates'):
            response['updates'] = True
            response['runs'] = []
            for run in runs:
                previous = previous_runs.get(run['id'])
                update = dict(run)
                if previous and (previous['run'], previous['session']) == (run['run'], run['session']):
                    for field in ('rows', 'error_rows', 'launcher_output', 'launcher_rows'):
                        if run.get(field) == previous.get(field):
                            update.pop(field, None)
                    if run['session_view'] and previous['session_view'] and (
                            run['session_view']['rows'] == previous['session_view']['rows']):
                        update['session_view'] = {key: value for key, value in run['session_view'].items()
                                                  if key != 'rows'}
                response['runs'].append(update)
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--snapshot', action='store_true', help='Print one read-only snapshot and exit')
    parser.add_argument('--recording', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.recording:
        from vm_selection import vm_config
        origin = vm_config.remote_origin()
        if origin is None or args.snapshot:
            raise ValueError('Recording read requires transferred controller source.')
        try:
            result = recording_artifact(args.recording, origin['storage_root'], origin['host'])
        except (OSError, ValueError) as error:
            result = dict(error=str(error))
        print(json.dumps(result, separators=(',', ':')), flush=True)
        return
    viewer = Viewer(checkout(args.root))
    try:
        if args.snapshot:
            print(json.dumps(viewer.snapshot({})), flush=True)
            return
        while line := sys.stdin.buffer.readline(512 * 1024 + 1):
            if len(line) > 512 * 1024:
                raise ValueError('watch: request too large')
            request = json.loads(line)
            if type(request) is not dict or request.get('protocol', 1) != 1:
                raise ValueError('watch: incompatible bridge protocol')
            if 'delete_run_times' in request:
                tokens = request['delete_run_times']
                if (set(request) - {'protocol', 'delete_run_times'} or type(tokens) is not list
                        or not 0 < len(tokens) <= 4096 or any(type(token) is not str
                            or not re.fullmatch(r'[a-f0-9]{64}', token) for token in tokens)):
                    raise ValueError('watch: invalid timing deletion request')
                print(json.dumps(dict(protocol=1, delete_result=viewer.delete_run_times(tokens))), flush=True)
                continue
            if 'launcher_action' in request:
                action = request['launcher_action']
                if (set(request) - {'protocol', 'launcher_action'} or type(action) is not dict
                        or set(action) != {'root', 'run', 'kind'}
                        or any(type(value) is not str for value in action.values())
                        or action['kind'] not in ('stop', 'cancel-stop', 'resume', 'reload', 'kill', 'add-session', 'close')):
                    raise ValueError('watch: invalid launcher action')
                print(json.dumps(dict(protocol=1, launcher_result=viewer.launcher_command(action))), flush=True)
                continue
            if 'artifact' in request:
                artifact = request['artifact']
                if (set(request) - {'protocol', 'artifact'} or type(artifact) is not dict
                        or set(artifact) != {'uri', 'inline'} or type(artifact['uri']) is not str
                        or len(artifact['uri']) > 8192 or type(artifact['inline']) is not bool):
                    raise ValueError('watch: invalid artifact request')
                print(json.dumps(dict(protocol=1, artifact_result=viewer.artifact(artifact)),
                                 separators=(',', ':')), flush=True)
                continue
            if (set(request) - {'protocol', 'scope', 'selected', 'reset', 'updates', 'session_root', 'session_roots', 'session_action'} or
                    any(type(request.get(key, 'all')) is not str for key in ('scope', 'selected')) or
                    type(request.get('session_root', '')) is not str or
                    type(request.get('session_roots', [])) is not list or
                    any(type(root) is not str or not 0 < len(root) <= 4096
                        for root in request.get('session_roots', [])) or
                    type(request.get('reset', False)) is not bool or
                    type(request.get('updates', False)) is not bool):
                raise ValueError('watch: invalid request')
            action = request.get('session_action')
            if action is not None and (type(action) is not dict
                    or set(action) != {'root', 'session', 'question', 'kind', 'text', 'id'}
                    or any(type(value) is not str for value in action.values())
                    or not 0 < len(action['id']) <= 128
                    or action['kind'] not in ('send', 'simplified', 'extend')
                    or len(action['text'].encode('utf-8')) > 65536):
                raise ValueError('watch: invalid session action')
            print(json.dumps(viewer.snapshot(request), separators=(',', ':')), flush=True)
    except BrokenPipeError:
        pass
    finally:
        viewer.close()


if __name__ == '__main__':
    main()
