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
from watch_output import Output, SessionOutput, JsonReader, active_launchers, TAIL_BYTES
from tests.integration.watch_activity import TerminalControls


def status_spans(lines, *, failures=0, category_failures=None, error_log=None,
                 session_waiting=False):
    """Keep status colors and emphasis without sending HTML or terminal controls."""
    from rich.text import Text
    from rich.console import Console
    from rich.style import Style
    from document_checks import references
    from launcher_render import COMPACT_LINE, SESSION_LINE, clean, compact_text
    console = Console()
    rows = []
    waiting_heading = False
    for line in lines:
        compact = isinstance(line, str) and line.startswith(COMPACT_LINE)
        text = line.copy() if isinstance(line, Text) else (
            compact_text(line) if compact else Text.from_ansi(line.replace(SESSION_LINE, '')))
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
                if (reference.kind != 'inline' or uri.scheme != 'file' or uri.netloc
                        or uri.query or uri.fragment or not uri.path.startswith('/')
                        or not unquote(uri.path).endswith('.webm')):
                    continue
                start, end = indent + reference.start, indent + reference.end
                linked.append_text(text[position:start])
                label = text[indent + reference.label_start:indent + reference.label_end]
                label.stylize(Style(color='#0066ff', underline=True, link=reference.destination))
                linked.append_text(label)
                position = end
            linked.append_text(text[position:])
            text = linked
        summary_label = re.match(r'^(Total Tasks:|Total Duration:|Ended:)', text.plain)
        if summary_label:
            text.stylize('bold', 0, summary_label.end())
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


class Viewer:
    def __init__(self, root):
        self.root = root
        self.discovery = Discovery(root)
        self.roots = {root: root.name}
        self.ui = {}
        self.vms = {}
        self.configured = {}
        self.images = {}
        self.outputs = {}
        self.launcher_reader = JsonReader()
        self.status_cache = {}
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
            if uri not in self.artifact_links:
                raise ValueError('Artifact is no longer published by this reader.')
            parsed = urlsplit(uri)
            if parsed.scheme not in ('', 'file') or parsed.netloc or parsed.query or parsed.fragment:
                raise ValueError('Invalid artifact URI.')
            path = Path(unquote(parsed.path))
            if not path.is_absolute() or '..' in path.parts:
                raise ValueError('Invalid artifact path.')
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
                limit = 64 * 1024 * 1024 if video else 2 * 1024 * 1024
                data = stream.read(limit + 1)
                if len(data) > limit:
                    raise ValueError('Artifact exceeds the inline transfer limit; open it on the source host.')
            return (dict(kind='video', data=base64.b64encode(data).decode('ascii')) if video else
                    dict(kind='text', text=data.decode('utf-8', errors='replace')))
        except (OSError, ValueError) as error:
            return dict(error=str(error))

    def run_status(self, session_root=None):
        from launcher_render import clean
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
                self.outputs[run.parent] = Output(root, show_log=False, launcher_base=run.parent)

        for checkout_root in self.roots:
            # Child runners can be dispatched into another worktree. Their
            # progress already appears in the controlling workflow's section.
            live = list(active_launchers(checkout_root, self.launcher_reader))
            candidates = live
            if not live and not any(output.root == checkout_root for output in self.outputs.values()):
                retained = []
                for run, name in active_launchers(checkout_root, self.launcher_reader, include_idle=True):
                    try:
                        retained.append((run.stat().st_mtime_ns, run, name))
                    except OSError:
                        continue
                if retained:
                    _modified, run, name = max(retained)
                    candidates = [(run, name)]
            for run, _name in candidates:
                observe(checkout_root, run)
        # Discovery may learn a child's checkout before its parent's checkout.
        for output in tuple(self.outputs.values()):
            if output.run is not None:
                observe(output.root, output.run)
        for root, output in self.outputs.items():
            branch = self.roots[output.root]
            label, active, reset, data = output.poll(progress=False)
            if reset or root not in self.launcher_logs:
                self.launcher_logs[root] = ''
                self.launcher_controls[root] = TerminalControls()
            if data:
                text = output.decoder.decode(self.launcher_controls[root].feed(data))
                self.launcher_logs[root] = (self.launcher_logs[root] + text)[-TAIL_BYTES:]
            if root not in self.sessions:
                self.sessions[root] = SessionOutput(output, None, embedded=True)
            session = self.sessions[root]
            session.poll()
            if supervisor(output.run) is not None:
                continue
            status = '' if active else output.completion_status()
            if active and output.run is not None and any(
                    (output.run / marker).exists() for marker in ('stop', 'cancel')):
                status = 'Stop Requested'
            lines = []
            error_lines = []
            failures, error_log = 0, None
            category_failures = {}
            if output.run is not None:
                try:
                    steps, details = output.status(active)
                    error_lines = output.error_status(steps)
                    summary = output.task_summary(active)
                    lines = [*summary, *(['─'] if summary else [])]
                    lines.extend(line for step in steps
                             if not (output.repair and step['key'] == 'pipelines')
                             for line in step['lines'])
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
                except (OSError, ValueError, KeyError, TypeError):
                    lines = ['Run status unavailable']
                    error_lines = ['Error status unavailable']
                if output.repair:
                    try:
                        state = output.reader.read(output.run / 'checkpoint.json')
                        targets = {tuple(item['failure']) for item in state.get('failed_cases', [])}
                        failures = len(targets)
                        for category, _case, _vm in targets:
                            category_failures[category] = category_failures.get(category, 0) + 1
                        error_log = (output.run.parent / 'errors.md').as_uri()
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
            session_run = session.run if session.active else None
            session_number = None
            session_inactive = not session.active
            if output.execution_plan:
                try:
                    state = output.reader.read(output.run / 'checkpoint.json', limit=2 * 1024 * 1024)
                    number = state.get('task_sessions')
                    if state.get('phase') != 'complete' and type(number) is int and number > 0:
                        session_number = number
                    session_inactive = session_number is None
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
                        session_inactive = session_number is None
                except (OSError, ValueError, KeyError, TypeError):
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
            question = session.panel.question.question if session.panel and session.panel.question else None
            waiting = bool(session.active and (question or session.panel.chat_state.get('status') in ('waiting', 'blocked')))
            deadline = question.get('deadline') if question else None
            if waiting and not any(re.fullmatch(r'Paused\s*[—-]\s*waiting for your answer',
                                               clean(line).strip())
                                   for line in lines):
                lines.append('Paused - waiting for your answer')
            # A new question replaces the old clock, even within the same session.
            prompt_id = question.get('id') if question else None
            signature = lines, failures, category_failures, error_log, session_run, waiting, deadline, prompt_id
            if self.status_cache.get(root, (None,))[0] != signature:
                self.status_cache[root] = signature, status_spans(lines, failures=failures,
                    category_failures=category_failures, error_log=error_log,
                    session_waiting=waiting)
            session_view = None
            if str(root) == session_root and session.panel:
                session_view = session.panel.webview()
                session_view['rows'] = status_spans(session_view.pop('lines'))
                session_view['input_enabled'] = session.input_enabled
            sections.append(dict(id=str(root), checkout=str(output.root), label=f'[{branch}]' +
                (f' {label}' + (f' ({status})' if status else '') if label else ''),
                active=active or session.active, status=status, rows=self.status_cache[root][1],
                run=str(output.run) if output.run is not None else None,
                launcher_output=self.launcher_logs[root],
                error_rows=status_spans(error_lines),
                session=session.identity,
                session_active=session.active,
                session_number=session_number, session_inactive=session_inactive,
                session_waiting=waiting, session_deadline=deadline, session_question=prompt_id,
                session_view=session_view))
        # Exiting one launcher must not remove its tabs while another checkout
        # is still active. Retain observed runs for this reader's lifetime.
        retained = [section for section in sections if section['run'] or section['session']]
        return retained

    def close(self):
        self.discovery.close()
        for feeds in self.ui.values():
            feeds.close()
        for feed, _meta in self.vms.values():
            feed.close()

    def screen(self, entry, frame, visible):
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
        if self.images.get(entry) == signature:
            return {}
        self.images[entry] = signature
        image = dict(width=meta['width'], height=meta['height'],
            image=png(pixels, meta['width'], meta['height'], meta['stride'],
                      red_first=meta['format'] in (0x20030888, 0x20038888)))
        if cursor and meta['cursor_on']:
            image['cursor'] = dict(image=png(cursor, meta['cursor_width'], meta['cursor_height'],
                meta['cursor_width'] * 4, rgba=True), x=meta['cursor_x'] - meta['hot_x'],
                y=meta['cursor_y'] - meta['hot_y'], width=meta['cursor_width'], height=meta['cursor_height'])
        return {'screen': image}

    def snapshot(self, request):
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
                        (question.question['id'] if question else '')):
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
        runs = self.run_status(request.get('session_root'))
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
            view.update(self.screen(entry, frames_by_entry[entry], render))
            values.append(dict(view, id=identifier, source=identity(Path(root)),
                label=f'[{self.roots[Path(root)]}] {name}', active=active, locked=locked))
        self.images = {entry: value for entry, value in self.images.items() if entry in shown}
        self.artifact_links = {part['link'] for run in runs
            for row in [*run['rows'], *run['error_rows'],
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
        return dict(protocol=1, capabilities=dict(sessions=True, artifacts=True, delete_run_times=True),
                    scope=scope, selected=selected, entries=values,
                    run_times=run_times,
                    runs=runs, session_result=result,
                    checkouts=[dict(id=str(root), label=branch) for root, branch in self.roots.items()],
                    resources=self.resources.text(), resource_sample=self.resources.last,
                    resource_charts=self.resources.charts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--snapshot', action='store_true', help='Print one read-only snapshot and exit')
    args = parser.parse_args()
    viewer = Viewer(checkout(args.root))
    try:
        if args.snapshot:
            viewer.discovery.thread.join(timeout=1.1)
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
            if 'artifact' in request:
                artifact = request['artifact']
                if (set(request) - {'protocol', 'artifact'} or type(artifact) is not dict
                        or set(artifact) != {'uri', 'inline'} or type(artifact['uri']) is not str
                        or len(artifact['uri']) > 8192 or type(artifact['inline']) is not bool):
                    raise ValueError('watch: invalid artifact request')
                print(json.dumps(dict(protocol=1, artifact_result=viewer.artifact(artifact)),
                                 separators=(',', ':')), flush=True)
                continue
            if (set(request) - {'protocol', 'scope', 'selected', 'reset', 'session_root', 'session_action'} or
                    any(type(request.get(key, 'all')) is not str for key in ('scope', 'selected')) or
                    type(request.get('session_root', '')) is not str or
                    type(request.get('reset', False)) is not bool):
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
