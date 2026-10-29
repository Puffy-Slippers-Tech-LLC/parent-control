"""Request/response adapter for watch feeds and shared launcher sessions.

Feeds remain view only, without a listening port, VM lease or saved screenshots.
Session chat uses the launcher's existing owner-checked mailbox.
The extension requests at most one snapshot at a time over its private stdio.
"""

import argparse
import base64
import json
import re
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e2e_watch_viewer import AsyncFeed, Feed, activity_text, progress_text, WAITING, CONNECTED
from ui_watch_transport import Feeds, label
from watch_checkouts import Discovery, checkout, identity
from watch_model import ResourceUsage, viewer_entries
from watch_output import Output, SessionOutput


def status_spans(lines, *, failures=0, category_failures=None, error_log=None,
                 session_waiting=False):
    """Keep status colors and emphasis without sending HTML or terminal controls."""
    from rich.text import Text
    from rich.console import Console
    from rich.style import Style
    from launcher_render import SESSION_LINE, clean
    console = Console()
    rows = []
    for line in lines:
        text = Text.from_ansi(line.replace(SESSION_LINE, ''))
        match = re.search(r'Waiting for input', text.plain)
        if match:
            text.stylize('red', match.start(), match.end())
        if session_waiting and re.fullmatch(r'Paused\s*[—-]\s*waiting for your answer', text.plain.strip()):
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
        spans = []
        for segment in text.render(console):
            style = segment.style
            color = style.color if style else None
            # Neutral terminal foregrounds must follow VS Code's light/dark theme.
            themed = color and (color.type.name == 'DEFAULT' or
                               (color.type.name == 'STANDARD' and color.number in (0, 7, 15)))
            spans.append(dict(text=clean(segment.text), bold=bool(style and style.bold),
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
        self.last_output = root
        self.status_cache = {}
        self.sessions = {}
        self.resources = ResourceUsage()

    def run_status(self, session_root=None):
        sections = []
        for root, branch in self.roots.items():
            if root not in self.outputs:
                self.outputs[root] = Output(root, show_log=False)
            output = self.outputs[root]
            label, active, _reset, _data = output.poll(progress=False)
            if root not in self.sessions:
                self.sessions[root] = SessionOutput(output, None, embedded=True)
            session = self.sessions[root]
            session.poll()
            if active:
                self.last_output = root
            status = '' if active else output.completion_status()
            lines = []
            failures, error_log = 0, None
            category_failures = {}
            if output.run is not None:
                try:
                    steps, details = output.status(active)
                    lines = [line for step in steps for line in step['lines']]
                    if details:
                        lines += ['─', *details]
                except (OSError, ValueError, KeyError, TypeError):
                    lines = ['Run status unavailable']
                if label == 'fix-tests':
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
            question = session.panel.question.question if session.panel and session.panel.question else None
            waiting = bool(session.active and (question or session.panel.chat_state.get('status') in ('waiting', 'blocked')))
            deadline = question.get('deadline') if question else None
            if waiting and not any(re.fullmatch(r'Paused\s*[—-]\s*waiting for your answer',
                                               re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line).strip())
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
            sections.append(dict(id=str(root), label=f'[{branch}]' +
                (f' {label}' + (f' ({status})' if status else '') if label else ''),
                active=active or session.active, status=status, rows=self.status_cache[root][1],
                session=session.identity if session.active else None,
                session_waiting=waiting, session_deadline=deadline, session_question=prompt_id,
                session_view=session_view))
        active = [section for section in sections if section['active']]
        return active or [section for section in sections if section['id'] == str(self.last_output)]

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
                if (session is None
                        or session.identity != action['session'] or not session.current()):
                    raise ValueError('Session changed; review the current session before sending.')
                if action['kind'] == 'send':
                    if not session.input_enabled:
                        raise ValueError('This session is not accepting input.')
                    session.send(action['text'])
                elif action['kind'] == 'simplified':
                    session.panel.simplified = not session.panel.simplified
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
            view = dict(kind='vm', heading=title, step=step,
                status=activity_text(activity, progress or meta.get('progress')) or operation or
                    ('VM running · Waiting for the next operation' if meta.get('state') == 'live' else
                     CONNECTED if meta.get('lease_locked') else WAITING),
                activity=(activity or {}).get('text', ''))
            frames_by_entry[entry] = frame
            entries[entry] = view, name, active, locked
            ids[entry] = self.configured[root][name].id

        scoped = viewer_entries(entries, scope=scope, vm_ids=ids,
                                current_vms={'vm-' + name.encode('ascii').hex()
                                             for name in self.configured.get(self.root, {})})
        valid_ids = {entry_id(Path(root), key) for root, key in scoped}
        if selected not in valid_ids:
            selected = 'all'
        values, shown = [], set()
        for (root, key), (view, name, active, locked) in scoped.items():
            identifier = entry_id(Path(root), key)
            entry = root, key
            render = active if selected == 'all' else selected == identifier
            if render:
                shown.add(entry)
            view.update(self.screen(entry, frames_by_entry[entry], render))
            values.append(dict(view, id=identifier, source=identity(Path(root)),
                label=f'[{self.roots[Path(root)]}] {name}', active=active, locked=locked))
        self.images = {entry: value for entry, value in self.images.items() if entry in shown}
        return dict(scope=scope, selected=selected, entries=values,
                    runs=self.run_status(request.get('session_root')), session_result=result,
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
            if (type(request) is not dict or set(request) - {'scope', 'selected', 'reset', 'session_root', 'session_action'} or
                    any(type(request.get(key, 'all')) is not str for key in ('scope', 'selected')) or
                    type(request.get('session_root', '')) is not str or
                    type(request.get('reset', False)) is not bool):
                raise ValueError('watch: invalid request')
            action = request.get('session_action')
            if action is not None and (type(action) is not dict
                    or set(action) != {'root', 'session', 'kind', 'text', 'id'}
                    or any(type(value) is not str for value in action.values())
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
