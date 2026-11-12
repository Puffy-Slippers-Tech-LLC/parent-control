"""Bounded observation and owner-scoped cancellation of detached launchers."""

import fcntl
import codecs
import copy
import json
import os
from pathlib import Path
import re
import stat
import time

from test_storage import directory

TAIL_BYTES = 128 * 1024


def open_private(path):
    # Do not create locks, mark results delivered, or follow replaced paths.
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('watch-output: symlink')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_nlink != 1):
        os.close(fd)
        raise ValueError('watch-output: unsafe file')
    return os.fdopen(fd, 'rb')


def read_json(path, limit=65536):
    with open_private(path) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('watch-output: oversized metadata')
    return json.loads(data)


class JsonReader:
    """Reuse unchanged publications, rechecking path and file safety each poll."""

    def __init__(self):
        self.cache = {}
        self.cache_bytes = 0

    def read(self, path, limit=65536):
        with open_private(path) as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino, info.st_size,
                        info.st_mtime_ns, info.st_ctime_ns, limit)
            cached = self.cache.get(path)
            if cached is not None and cached[0] == identity:
                # Touch the entry without dropping every other hot publication.
                self.cache[path] = self.cache.pop(path)
                # repair_progress modifies nested lines for its display only.
                return copy.deepcopy(cached[1])
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('watch-output: oversized metadata')
        value = json.loads(data)
        previous = self.cache.pop(path, None)
        if previous is not None:
            self.cache_bytes -= previous[2]
        self.cache[path] = identity, value, len(data)
        self.cache_bytes += len(data)
        while len(self.cache) > 64 or self.cache_bytes > 4 * 1024 * 1024:
            self.cache_bytes -= self.cache.pop(next(iter(self.cache)))[2]
        return copy.deepcopy(value)


def snapshot(path, *, steps=False, reader=None):
    try:
        value = reader.read(path) if reader is not None else read_json(path)
    except FileNotFoundError:
        return []
    def lines(items):
        return isinstance(items, list) and all(isinstance(item, str) for item in items)
    valid = (isinstance(value, list) and all(
        isinstance(step, dict) and isinstance(step.get('key'), str)
        and lines(step.get('lines')) and step['lines']
        and lines(step.get('replaces', [])) for step in value)) if steps else lines(value)
    if not valid:
        raise ValueError('watch-output: invalid progress')
    return value


def active_run(base, *, workflow=False, reader=None, include_idle=False):
    name = (reader.read(base / 'current.json', 4096) if reader is not None
            else read_json(base / 'current.json', 4096))['run']
    if not isinstance(name, str) or not re.fullmatch('[0-9a-f]{32}', name):
        raise ValueError('watch-output: invalid run')
    run = base / name
    info = run.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077):
        raise ValueError('watch-output: unsafe run')
    with open_private((base if workflow else run) / 'owner') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return run
        fcntl.flock(owner, fcntl.LOCK_UN)
    return run if include_idle else None


def active_launchers(root, reader, *, include_idle=False, workflows_only=False):
    """Discover live publications, optionally including retained idle runs."""
    for kind in ('fix-tests', 'fix-tests-host', 'write-e2e', 'sync-whatsnew',
                 'plans', 'sessions-host', 'sessions'):
        if workflows_only and kind in ('sessions-host', 'sessions'):
            continue
        try:
            base = directory(kind, root=root, create=False)
            bases = sorted(base.iterdir()) if kind == 'plans' else [base]
            if kind == 'sessions':
                # Explicit VM selections publish in independent session scopes,
                # including while their owners wait for a host-wide VM checkout.
                bases.extend(sorted(base.glob('vm-*')))
            for item in bases:
                try:
                    run = active_run(item, workflow=kind not in ('sessions-host', 'sessions'),
                                     reader=reader, include_idle=include_idle)
                    if run is not None:
                        record = reader.read(item / 'current.json', 4096)
                        if record.get('run') != run.name:
                            continue
                        name = record.get('launcher', 'launcher')
                        if not isinstance(name, str) or not re.fullmatch(r'[\w.-]{1,100}', name):
                            raise ValueError('watch-output: invalid launcher name')
                        yield run, name
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        except (OSError, ValueError):
            continue


def cancel_run(root, run):
    """Cancel an exact live publication; never adopt a replacement run."""
    if not any(candidate == run for candidate, _name in active_launchers(root, JsonReader())):
        raise ValueError('Launcher changed; refresh before trying again.')
    output = Output(root, launcher_base=run.parent)
    output.run = run
    if not output.cancel():
        raise ValueError('Launcher changed or cancellation could not be requested.')


def watch_closed(run):
    """A durable, run-specific dismissal, independent of execution checkpoints."""
    try:
        with open_private(run / 'watch-closed'):
            return True
    except FileNotFoundError:
        return False


def close_finished_run(root, run):
    """Dismiss only an unchanged idle publication while holding its owner lock."""
    if not any(candidate == run for candidate, _name in
               active_launchers(root, JsonReader(), include_idle=True)):
        raise ValueError('Launcher changed; refresh before trying again.')
    workflow = run.parent.name not in ('sessions', 'sessions-host') and not run.parent.name.startswith('vm-')
    with open_private((run.parent if workflow else run) / 'owner') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Launcher is running; it cannot be closed.') from error
        if read_json(run.parent / 'current.json', 4096)['run'] != run.name:
            raise ValueError('Launcher changed; refresh before trying again.')
        # Pin the private run directory and never follow a replacement marker.
        fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('watch-output: unsafe run')
            if watch_closed(run):
                return
            marker = os.open('watch-closed', os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
            with os.fdopen(marker, 'wb') as stream:
                os.fsync(stream.fileno())
            os.fsync(fd)
        finally:
            os.close(fd)


class Output:
    def __init__(self, root=None, *, launcher_base=None):
        self.root = root or Path(__file__).resolve().parents[1]
        self.launcher_base = launcher_base
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.run = None
        self.label = ''
        self.identity = None
        self.offset = 0
        self.reader = JsonReader()
        self.error_clock = None
        self.summary_run = None
        self.task_totals = None
        self.completed_before = None
        self.summary_ended = None
        self.summary_clock = {}

    def task_summary(self, active):
        """Use every execution plan's accepted counters and shared rendering."""
        from launcher_display import task_summary_lines
        from launcher_runtime import task_counters
        from launcher_session import clock_duration
        from launcher_view import observed_plan_totals
        if self.run is None or not self.execution_plan:
            return []
        if self.summary_run != self.run:
            self.summary_run = self.run
            self.task_totals = self.completed_before = self.summary_ended = None
            self.summary_clock = {}
        try:
            _, totals, baseline = task_counters(self.run,
                observed_plan_totals(self.root, self.run, self.reader),
                completed_before=self.completed_before)
            self.task_totals, self.completed_before = totals, baseline
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Retain valid totals while editable plan metadata is incomplete.
        if not active and self.summary_ended is None:
            self.summary_ended = time.monotonic()
        try:
            record = self.reader.read(self.run.parent / 'current.json', 4096)
            if record.get('run') == self.run.name:
                self.summary_clock = record
        except (OSError, ValueError, KeyError, TypeError):
            pass
        origin = self.summary_clock.get('started_monotonic')
        duration = (clock_duration((self.summary_ended if self.summary_ended is not None
                                   else time.monotonic()) - origin)
                    if origin is not None else '—')
        lines = task_summary_lines(self.task_totals, duration)
        if not active and self.completion_status() == 'finished':
            try:
                with open_private(self.run / 'result.json') as stream:
                    ended = os.fstat(stream.fileno()).st_mtime
                lines.append('Ended: ' + time.strftime('%H:%M', time.localtime(ended)))
            except (OSError, ValueError):
                pass
        return lines

    @property
    def execution_plan(self):
        return self.run is not None and (self.run.parent.name == 'write-e2e'
                                        or self.run.parent.parent.name == 'plans'
                                        or (self.run / 'plan-view.json').exists())

    @property
    def repair(self):
        return self.run is not None and self.run.parent.name in ('fix-tests', 'fix-tests-host')

    def error_status(self, steps):
        """Read the same task-local fields as the shared launcher right pane."""
        from launcher_display import error_status_lines
        current = next((step for step in reversed(steps)
                        if not step.get('pinned') and not step.get('replaces')), None)
        def metadata(name):
            try:
                return self.reader.read(self.run / name)
            except FileNotFoundError:
                return {}
        state = metadata('chat-state.json') if self.run else {}
        info = metadata('task-info.json') if self.run else {}
        task = state.get('task_id')
        if info.get('task_id') != task:
            info = info.get('previous_tasks', {}).get(task, {})
        if current and state.get('progress_key') not in (None, current['key']):
            info = {}
        lines, self.error_clock = error_status_lines(info,
            (self.run, current['key'] if current else None, task), self.error_clock)
        return lines

    def status(self, active):
        """Read shared launcher status publications for the editor viewer."""
        from launcher_progress import repair_progress
        from launcher_render import clean
        steps = snapshot(self.run / 'controller.json', steps=True, reader=self.reader)
        if self.execution_plan:
            from launcher_progress import plan_status
            steps = plan_status(self.run, steps, reader=self.reader, active=active)
        if self.repair:
            steps = repair_progress(self.run, steps,
                child_steps=snapshot(self.run / 'test-controller.json', steps=True, reader=self.reader))
        details = snapshot(self.run / 'frame.json', reader=self.reader)
        if self.repair and not details:
            details = snapshot(self.run / 'test-frame.json', reader=self.reader)
        if steps:
            details = [line for line in details if not clean(line).startswith('Overall - ')]
        if details and clean(details[0]).startswith('VM queue | concurrency '):
            spaced = []
            seen_vm = False
            for line in details[1:]:
                if clean(line).startswith('VM: '):
                    # Removing Overall can leave its blank row beside the
                    # queue's separator. Keep one blank between VM sections.
                    while spaced and not clean(spaced[-1]).strip():
                        spaced.pop()
                    if seen_vm:
                        spaced.append('')
                    seen_vm = True
                spaced.append(line)
            details = spaced
        if not active and self.completion_status() == 'stopped':
            details = [line for line in details
                       if not clean(line).startswith('Tests interrupted.')]
            details.append('\033[31mLauncher has stopped.\033[0m')
        return steps, details

    def closing_task(self, steps, *, session_inactive):
        """Include final synchronization before the next task is selected."""
        if not self.execution_plan:
            return False
        from launcher_progress import progress_keys
        try:
            state = self.reader.read(self.run / 'checkpoint.json', limit=2 * 1024 * 1024)
            accepted = state.get('git_reconciliation', {}).get('accepted_result', {})
            accepted_completion = (accepted.get('status') == 'task_complete'
                                   and accepted.get('task_id') == state.get('task_id'))
            # A completed task can publish its recap and clear its commit intent
            # before the final boundary pull. Include that wait even though its
            # active row has already been replaced by the green recap.
            if 'upstream_pull' in state and (state.get('pending_completion')
                    or state.get('commit_intent') or accepted_completion
                    or state.get('phase') == 'complete'):
                return True
            keys = progress_keys(state)
            if not any(not step.get('replaces') and step['key'] in keys for step in steps):
                return False
            if state.get('pending_completion') or state.get('phase') == 'complete':
                return True
            # Reconciliation retains the accepted result outside
            # pending_completion, including while waiting for the Git lock.
            if accepted_completion:
                return True
            # The Session tab can become inactive before the controller saves
            # pending_completion, while it validates the finished task response.
            if session_inactive and state.get('in_flight'):
                result = self.reader.read(self.run / 'agent-result.json', limit=2 * 1024 * 1024)
                return (result.get('status') == 'task_complete'
                        and result.get('task_id') == state.get('task_id'))
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return False

    def cancel(self):
        """Request the displayed owner's cooperative Ctrl+C shutdown."""
        run, _label = self.discover()
        if run is None or run != self.run:
            return False
        try:
            (run / 'cancel').touch(mode=0o600)
        except OSError:
            return False
        return True

    def completion_status(self):
        """Describe the displayed run's recorded outcome after its owner exits."""
        if self.run is None:
            return 'incomplete'
        try:
            try:
                result = self.reader.read(self.run / 'result.json', 4096)
                workflow = True
            except FileNotFoundError:
                result = self.reader.read(self.run / 'result', 4096)
                workflow = False
            if workflow and not isinstance(result, dict):
                return 'incomplete'
            status = result.get('status') if workflow else result
            if type(status) is not int:
                return 'incomplete'
            if status == 0 and workflow and (self.run / 'stop').exists():
                return 'stopped'
            if status == 0 and workflow and (self.run / 'limited').exists():
                return 'task limit reached'
            if status == 0 and self.execution_plan:
                from launcher_view import observed_plan_totals
                totals = observed_plan_totals(self.root, self.run, self.reader)
                if totals is None or totals[1]:
                    return 'incomplete'
            return {0: 'finished', 130: 'stopped'}.get(status, 'failed')
        except (OSError, ValueError, KeyError, TypeError):
            return 'incomplete'

    def discover(self):
        return next(((run, name) for run, name in active_launchers(self.root, self.reader)
                     if self.launcher_base is None or run.parent == self.launcher_base), (None, ''))

    def poll(self):
        run, label = self.discover()
        active = run is not None
        if run is None and self.launcher_base is not None:
            # A scoped publication may be replaced and finish between polls.
            # Follow its current result instead of pinning the previous run.
            run, label = next(((candidate, name) for candidate, name in
                              active_launchers(self.root, self.reader, include_idle=True)
                              if candidate.parent == self.launcher_base), (None, ''))
        # Drain the final bytes after owner exit and keep the last transcript.
        if run is None:
            run, label = self.run, self.label
            if run is None:
                # Reconnect can happen after owner exit. Reuse the latest safe
                # current publication without treating it as live authority.
                latest = -1
                for candidate, name in active_launchers(self.root, self.reader, include_idle=True):
                    if self.launcher_base is not None and candidate.parent != self.launcher_base:
                        continue
                    try:
                        modified = candidate.lstat().st_mtime_ns
                    except OSError:
                        continue
                    if modified > latest:
                        run, label, latest = candidate, name, modified
        reset, data = False, b''
        if run is not None:
            try:
                with open_private(run / 'output') as stream:
                    info = os.fstat(stream.fileno())
                    identity = (run, info.st_dev, info.st_ino)
                    reset = identity != self.identity or info.st_size < self.offset
                    if reset:
                        self.decoder.reset()
                        self.offset = max(0, info.st_size - TAIL_BYTES)
                        stream.seek(self.offset)
                        if self.offset:
                            stream.readline(TAIL_BYTES)
                            self.offset = stream.tell()
                    stream.seek(self.offset)
                    data = stream.read(TAIL_BYTES)
                    self.offset = stream.tell()
                    self.identity, self.run, self.label = identity, run, label
            except (OSError, ValueError):
                pass
        return label, active, reset, data



class SessionOutput:
    """Follow the displayed workflow's session, with owner-checked input routing."""

    def __init__(self, output, *, owner_run=None):
        self.output = output
        self.owner_run = owner_run
        self.run = self.owner = self.identity = None
        self.offset = 0
        self.panel = None
        self.state = {}
        self.active = False
        self.input_enabled = False
        self.reader = JsonReader()
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')

    def discover(self):
        if self.owner_run is not None:
            try:
                owner = active_run(self.owner_run.parent, workflow=True, reader=self.reader)
            except (OSError, ValueError, KeyError, TypeError):
                owner = None
            owners = [owner] if owner == self.owner_run else []
            return self.discover_sessions(owners)
        owners = [run for run, _name in active_launchers(self.output.root, self.reader)
                  if self.output.launcher_base is None or run.parent == self.output.launcher_base]
        if not owners and self.run is None and self.output.run is not None:
            # Restore a retained transcript read-only after Watch reconnects.
            _, run, state, source = self.discover_sessions([self.output.run])
            return None, run, dict(state, status='finished'), source
        return self.discover_sessions(owners)

    def discover_sessions(self, owners):
        sessions = []
        for owner in dict.fromkeys(owners):
            # Repair admission permits one writer; select its newest session.
            candidates = [owner, *sorted(owner.glob('pipeline-*'))]
            for run in candidates:
                try:
                    value = self.reader.read(run / 'session-view.json')
                    if (not isinstance(value, dict) or not isinstance(value.get('session'), str)
                            or not isinstance(value.get('started_at'), (int, float))
                            or type(value.get('interactive')) is not bool
                            or value.get('status') not in ('running', 'finished')):
                        continue
                    sessions.append((value['status'] == 'running', value['started_at'], owner, run, value))
                except (OSError, ValueError, TypeError):
                    continue
        if sessions:
            _active, _started, owner, run, value = max(sessions, key=lambda item: item[:2])
            return owner, run, value, 'session-output.log'
        # Retain the last displayed transcript after launcher exit, without
        # retaining authority to send input to that owner.
        if self.run is not None:
            return None, self.run, dict(self.state, status='finished'), 'session-output.log'
        return None, None, {}, None

    def current(self):
        owner, run, state, _source = self.discover()
        if (owner is None or owner != self.owner or run != self.run
                or state.get('session') != self.identity):
            return False
        if state['status'] == 'running':
            return True
        try:
            question = self.reader.read(run / 'question.json')
            return (self.panel.question is not None and question.get('answer') is None
                    and not question.get('expired')
                    and question.get('id') == self.panel.question['id'])
        except (OSError, ValueError, TypeError, AttributeError):
            return False

    def send(self, text):
        from launcher_chat import send_input
        from launcher_question import submit
        if not self.current():
            raise ValueError('Session changed; review the current session before sending.')
        if self.panel.question:
            question = self.panel.question
            options = question['options']
            choice = int(text.strip()) - 1 if text.strip() in ('1', '2', '3') else len(options)
            submit(self.run, question['id'], min(choice, len(options)), text)
        elif self.panel.input_mode == 'chat':
            send_input(self.run, 'message', text,
                       expected_session=self.panel.chat_state.get('session'))
        else:
            raise ValueError('This session accepts input when a developer decision is pending.')

    def extend_deadline(self, identity):
        from launcher_question import extend_deadline
        if not self.current():
            raise ValueError('Session changed; review the current session before adding time.')
        extend_deadline(self.run, identity)

    def poll(self):
        from launcher_session import SessionPanel
        owner, run, state, source = self.discover()
        if run is None:
            self.owner = self.run = self.identity = self.panel = None
            self.offset = 0
            self.decoder.reset()
            self.active = self.input_enabled = False
            return False, False
        reset = (run, state['session']) != (self.run, self.identity)
        if reset:
            self.owner, self.run, self.identity = owner, run, state['session']
            simplified = self.panel.simplified if self.panel else True
            self.panel = SessionPanel(hide_tool_results=True)
            self.panel.simplified = simplified
            self.panel.update_text_output({})
            self.offset = 0
            self.decoder.reset()
        panel = self.panel
        self.owner = owner
        self.state = state
        panel.chat_state = state
        try:
            chat = self.reader.read(run / 'chat-state.json')
            if state['status'] == 'running' and state['interactive'] and isinstance(chat, dict):
                panel.chat_state = chat
            elif state['status'] == 'running' and state['interactive']:
                panel.chat_state = dict(session=None, status='starting')
        except (OSError, ValueError):
            if state['status'] == 'running' and state['interactive']:
                panel.chat_state = dict(session=None, status='starting')
        # Workflow transitions can publish only mailbox/lifecycle fields.
        # Keep the supervisor's display metadata without reusing its input identity.
        for name in ('agent', 'model', 'effort', 'logical_tier'):
            if name not in panel.chat_state and name in state:
                panel.chat_state[name] = state[name]
        try:
            question = self.reader.read(run / 'question.json')
            if owner is None or question.get('answer') is not None or question.get('expired'):
                question = None
        except (OSError, ValueError):
            question = None
        self.active = owner is not None and (state['status'] == 'running' or question is not None)
        self.input_enabled = self.active and (state['interactive'] or question is not None)
        panel.input_mode = 'chat' if self.active and state['interactive'] and question is None else 'question'
        panel.question = question
        # The launcher writes the full question and choices to session-output.log.
        # Keep question state for input routing without appending a second prompt.
        try:
            with open_private(run / source) as stream:
                size = os.fstat(stream.fileno()).st_size
                if size < self.offset:
                    self.offset = 0
                    # Log compaction is not a new session. Keep the bounded
                    # visible history while resuming from the retained log.
                    if not panel.hide_tool_results:
                        panel.transcript.clear()
                    panel.pending = ''
                    panel.result_pending = ''
                    panel.result_activity = 'orphan'
                    panel.result_detail_pending = False
                    self.decoder.reset()
                # Drain in bounded chunks without skipping messages between
                # polls when a tool writes more than one chunk at once.
                stream.seek(self.offset)
                data = stream.read(min(TAIL_BYTES, max(0, size - stream.tell())))
                self.offset = stream.tell()
            panel.write(self.decoder.decode(data))
        except (OSError, ValueError):
            pass
        try:
            # Read provisional text after the log, so completing a message
            # cannot leave an older preview beside its authoritative text.
            # JSON escaping can expand the bounded prose beyond its text budget.
            description = self.reader.read(run / 'descriptive-output.json', limit=2 * 1024 * 1024)
        except FileNotFoundError:
            description = {}
        except (OSError, ValueError):
            description = None
        if description is not None:
            panel.update_text_output(description)
        if owner is None or panel.chat_state.get('status') != 'running':
            panel.streaming_lines = []
        return True, reset


def terminal(identity, description):
    """VS Code Light+ palette, responsive terminal reflow, vertical scroll only."""
    import gi
    gi.require_version('Vte', '3.91')
    from gi.repository import Gdk, Gtk, Pango, Vte
    from common.oh_no_parent_control_ui.gtk_automation import set_automation_id

    view = Vte.Terminal(hexpand=True, vexpand=True)
    set_automation_id(view, identity)
    view.set_input_enabled(False)
    view.set_focusable(True)
    view.set_allow_hyperlink(False)
    view.set_audible_bell(False)
    view.set_bold_is_bright(True)
    view.set_scrollback_lines(10000)
    view.set_scroll_on_output(False)
    view.set_font(Pango.FontDescription('Monospace 10'))
    def color(value):
        rgba = Gdk.RGBA()
        rgba.parse(value)
        return rgba
    view.set_colors(color('#26374e'), color('#ffffff'), list(map(color, (
        '#000000', '#cd3131', '#008000', '#866951',
        '#0451a5', '#bc05bc', '#0598bc', '#555555',
        '#666666', '#cd3131', '#14ce14', '#b5ba00',
        '#0451a5', '#bc05bc', '#0598bc', '#77808b'))))
    view.set_color_highlight(color('#add6ff'))
    view.set_color_highlight_foreground(color('#26374e'))
    view.update_property([Gtk.AccessibleProperty.LABEL], [description])
    scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True,
        hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
    set_automation_id(scroll, identity + '-scroll')
    scroll.set_margin_start(18)
    scroll.set_child(view)
    return view, scroll


class TerminalWriter:
    def __init__(self, view, *, mouse_tracking=True):
        from tests.integration.watch_activity import TerminalControls
        self.view = view
        self.controls = TerminalControls()
        self.last_cr = False
        self.mouse_tracking = mouse_tracking

    @staticmethod
    def without_mouse_tracking(match):
        # A transcript has no mouse consumer. Preserve display modes in mixed
        # DECSET/DECRST sequences while keeping native selection and scrolling.
        modes = [mode for mode in match[1].split(b';')
                 if int(mode) not in (9, 1000, 1001, 1002, 1003, 1005, 1006, 1007, 1015, 1016)]
        return b'\x1b[?' + b';'.join(modes) + match[2] if modes else b''

    def feed(self, data, *, reset=False):
        if reset:
            self.view.reset(True, True)
            self.controls.__init__()
            self.last_cr = False
        data = self.controls.feed(data)
        if not self.mouse_tracking:
            data = re.sub(rb'\x1b\[\?([0-9]+(?:;[0-9]+)*)([hl])',
                          self.without_mouse_tracking, data)
        if not data:
            return
        # Pipes lack the PTY's LF->CRLF conversion. Honor split CRLF pairs.
        prefix = b'\r' if self.last_cr else b''
        self.last_cr = data.endswith(b'\r')
        converted = re.sub(rb'(?<!\r)\n', b'\r\n', prefix + data)
        self.view.feed(converted[len(prefix):])
