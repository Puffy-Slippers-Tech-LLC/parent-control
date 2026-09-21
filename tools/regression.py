"""Run established suites, with a quiet dashboard and durable streaming report."""

from dataclasses import dataclass, asdict
import codecs
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

from regression_events import PREFIX
from regression_process import Control
import test_launcher as host
from regression_schedule import Job, run_jobs
from regression_inputs import identity as source_identity
from regression_resources import Admission, HOST_WORKERS, PRESSURE_RECOVERY_SECONDS, vm_demand
from regression_ui import buckets as ui_buckets
from regression_unit import buckets as unit_buckets
from regression_cleanup import buckets as cleanup_buckets


CATEGORY_NAMES = {
    'unit': 'Unit and contracts', 'component': 'Private D-Bus components',
    'ui': 'UI inventory', 'fixture-runtime': 'Fixture runtime',
    'source': 'Source and traceability', 'static': 'Static checks',
    'child-node': 'Child Node', 'child-gjs': 'Child GJS',
    'backend': 'Backend prerequisites', 'publish': 'Publishing tests',
    'system': 'Installed-system tests', 'e2e': 'Ready E2E scenarios',
    'traceability': 'Traceability', 'coverage': 'Python coverage',
    'check': 'Make check', 'component-all': 'Component checks',
    'fixtures': 'Test fixtures', 'artifacts': 'Package build A',
    'integration': 'Integration checks', 'fast': 'Fast tests',
}


def authorization():
    from dev_privileges import check
    check('/usr/local/libexec/onpc-test-runner')
    installed = Path('/usr/local/libexec/onpc-test-runner').read_text()
    if any(option not in installed for option in ('--unattended', '--skip-backing-verification',
                                                  '--retention-run=')):
        raise ValueError('installed dispatcher needs ./setup.sh --test-tools-only')


@dataclass
class Category:
    name: str
    total: int | None = None
    done: int = 0
    state: str = 'Pending'
    failures: int = 0
    elapsed: float = 0.0
    started: float | None = None
    waiting: float = 0.0
    wait_reason: str = ''
    host: bool = False
    branch: int | None = None
    launch_order: int = 0
    nodeids: tuple[str, ...] | None = None
    phase: str = 'host'
    retry_category: str | None = None

    def duration(self, now):
        seconds = self.elapsed + (now - self.started if self.started is not None else 0)
        return f'{seconds:.0f}s' if seconds < 60 else f'{seconds / 60:.1f}m'

    def stop_timer(self):
        if self.started is not None:
            self.elapsed += time.monotonic() - self.started
            self.started = None


class Dashboard:
    ANSI = re.compile(r'\x1b\[[?0-9;]*[A-Za-z]')

    def __init__(self, categories, stream=None):
        self.categories = categories
        self.stream = stream or sys.stdout
        self.lines = 0
        self.terminal_size = None
        self.alternate_screen = False
        self.finished = False
        self.last = 0.0
        self.started = time.monotonic()
        self.host_started = None
        self.host_elapsed = None
        self.cleanup_started = None
        self.cleanup_elapsed = None
        self.control = None
        self.cleanup_finished = False

    @staticmethod
    def counts(done, failures, total):
        passed = max(0, done - failures)
        counts = f'\033[0m(\033[32m{passed}\033[0m/'
        if failures:
            counts += f'\033[31m{failures}\033[0m/'
        return counts + f'{total})'

    def category(self, item, now):
        total = '?' if item.total is None else str(item.total)
        routine = (f'{HOST_WORKERS} host categories already running', 'waiting for required host jobs')
        reason = '' if item.wait_reason in routine else item.wait_reason
        if item.state == 'Pending':
            if item.wait_reason:
                suffix = ': ' + reason if reason else ''
                return f'\033[33m[Waiting] {item.name}{suffix} ({total})\033[0m'
            return f'\033[90m[Pending] {item.name} ({total})\033[0m'
        percent = '?' if item.total is None else str(int(100 * item.done / max(item.total, 1)))
        label = {'Passed': '✓', 'Failed': '✗', 'Interrupted': '✗',
                 'Blocked': '✗'}.get(item.state, item.state)
        if item.state == 'Passed':
            return (f'\033[32m[{label}] {item.name} - {percent}% '
                    f'({item.done}/{total}) - {item.duration(now)}'
                    + (f' ({reason})' if reason else '') + '\033[0m')
        color = {'Passed': '32', 'Failed': '31', 'Interrupted': '31',
                 'Blocked': '31', 'Running': '97;1', 'Pending': '90'}[item.state]
        return (f'\033[{color}m[{label}] {item.name} - {percent}% '
                + self.counts(item.done, item.failures, total)
                + f' - {item.duration(now)}'
                + (f' ({reason})' if reason else '') + '\033[0m')

    def branches(self, items, now, phase='host'):
        lines = []
        phase_elapsed = getattr(self, phase + '_elapsed')
        phase_started = getattr(self, phase + '_started')
        for branch in range(1, HOST_WORKERS + 1):
            assigned = sorted((item for item in items if item.branch == branch),
                              key=lambda item: item.launch_order)
            if not assigned:
                continue
            if lines:
                lines.append('│')
            active = any(item.state == 'Running' for item in assigned)
            state = 'running' if active else 'idle' if phase_elapsed is None else 'finished'
            style = {'running': '\033[1m', 'idle': '\033[90m',
                     'finished': ('\033[32m' if all(item.state == 'Passed' for item in assigned)
                                  else '\033[1;31m')}[state]
            elapsed = sum(item.elapsed + (now - item.started if item.started is not None else 0)
                          for item in assigned)
            lines.append(f'{style}├─ Host branch {branch} — {state} - {elapsed / 60:.1f}m\033[0m')
            for index, item in enumerate(assigned):
                connector = '└─ ' if index == len(assigned) - 1 else '├─ '
                lines.append('│  ' + connector + self.category(item, now))
        unassigned = [item for item in items if item.branch is None]
        if unassigned:
            lines.append('│')
            lines.append('│  Unassigned host work — waiting for a branch and headroom')
            lines.extend('│    ' + self.category(item, now) for item in unassigned)
        if phase_elapsed is None:
            state = 'waiting for cleanup prerequisites' if phase == 'cleanup' else 'waiting for host work'
        else:
            state = 'passed' if all(item.state == 'Passed' for item in items) else 'incomplete or failed'
        elapsed = phase_elapsed
        if phase_started is not None:
            elapsed = (now - self.started if elapsed is None else
                       phase_started - self.started + elapsed)
        timing = '' if elapsed is None else f' — {(elapsed / 60):.1f}m wall time'
        lines.append('│')
        join = 'Join cleanup prerequisites' if phase == 'cleanup' else 'Join host branches'
        summary = f'└─ {join} — {state}{timing}'
        lines.append(f'\033[32m{summary}\033[0m' if state == 'passed' else summary)
        return lines

    def render(self, now):
        lines = []
        hosts = [item for item in self.categories if item.host]
        rendered = set()
        for item in self.categories:
            if item.host:
                if item.phase not in rendered:
                    rendered.add(item.phase)
                    if lines:
                        lines.append('│')
                    phase_items = [other for other in hosts if other.phase == item.phase]
                    if item.phase == 'cleanup':
                        heading = 'Cleanup safety prerequisites'
                        if self.cleanup_elapsed is not None and all(
                                other.state == 'Passed' for other in phase_items):
                            heading = f'\033[32m{heading}\033[0m'
                        lines.append(heading)
                    lines.extend(self.branches(phase_items, now, item.phase))
            else:
                lines.append(('│  ' if hosts else '') + self.category(item, now))
        done = sum(item.done for item in self.categories)
        known = all(item.total is not None for item in self.categories)
        total = sum(item.total or 0 for item in self.categories)
        percent = str(int(100 * done / max(total, 1))) if known else '?'
        color = '31' if any(c.state in ('Failed', 'Interrupted', 'Blocked') for c in self.categories) else (
            '32' if all(c.state == 'Passed' for c in self.categories) else '97;1')
        failures = sum(item.failures for item in self.categories)
        lines.append('')
        if color == '32':
            lines.append(f'\033[32mOverall - {percent}% ({done}/{total})'
                         f' - {(now - self.started) / 60:.1f}m\033[0m')
        else:
            lines.append(f'\033[{color}mOverall - {percent}% '
                         + self.counts(done, failures, total if known else '?')
                         + f' - {(now - self.started) / 60:.1f}m\033[0m')
        if self.control is not None and (self.control.interrupted or
                                        self.control.stopped.is_set()):
            notice = ('Tests interrupted. Shutdown finished; see cleanup results above.'
                      if self.cleanup_finished else
                      'Tests interrupted. Shutting down safely; please wait for cleanup to finish.')
            lines.append('\033[31;1m' + notice + '\033[0m')
        return lines

    @classmethod
    def fit(cls, line, width):
        """Keep each terminal row on one physical line, ignoring ANSI colors."""
        if len(cls.ANSI.sub('', line)) <= width:
            return line
        parts, remaining = [], max(0, width - 1)
        for part in re.split(r'(\x1b\[[0-9;]*[A-Za-z])', line):
            if cls.ANSI.fullmatch(part):
                parts.append(part)
            elif len(part) <= remaining:
                parts.append(part)
                remaining -= len(part)
            else:
                parts.append(part[:remaining])
                break
        return ''.join(parts) + '…\033[0m'

    @classmethod
    def fit_height(cls, lines, height):
        """Keep live rows reachable by cursor-up, with urgent status visible."""
        if len(lines) <= height:
            return lines

        def priority(index):
            plain = cls.ANSI.sub('', lines[index])
            if plain.startswith(('Overall - ', 'Running category [', 'Tests interrupted.')):
                return 0
            if '[Running]' in plain or '[Waiting]' in plain or '[✗]' in plain:
                return 1
            if plain.startswith(('├─ Host branch ', '└─ Join ')):
                return 2
            if plain in ('', '│'):
                return 4
            return 3

        # Preserve the tree's order after choosing which rows fit. The complete
        # category inventory remains in the report and non-terminal output.
        count = max(1, height - 1)
        selected = sorted(sorted(range(len(lines)), key=priority)[:count])
        visible = [lines[index] for index in selected]
        if height > 1:
            visible.insert(0, f'… {len(lines) - count} rows hidden; full details in run report')
        return visible

    def draw(self, *, force=False):
        if self.finished:
            return
        now = time.monotonic()
        if not force and now - self.last < 1:
            return
        self.last = now
        lines = self.render(now)
        if hasattr(self.stream, 'frame'):
            self.stream.frame(lines)
            return
        self.draw_lines(lines)

    def draw_lines(self, lines):
        """Render a local or reconnected frame using this terminal's size."""
        if hasattr(self.stream, 'frame'):
            self.stream.frame(lines)
            return
        tty = self.stream.isatty()
        prefix = f'\033[{self.lines}F' if self.lines and tty else ''
        ending = '\n'
        if tty:
            # Query the terminal we actually draw into. shutil prefers LINES
            # and COLUMNS from the environment, which can outlive a resize and
            # let frames scroll beyond the reach of the next cursor-up.
            try:
                size = os.get_terminal_size(self.stream.fileno())
            except (OSError, ValueError):
                size = shutil.get_terminal_size()
            width = max(1, size.columns - 1)
            # Reserve a row for the trailing newline: cursor-up cannot reach
            # rows that have already scrolled out of the terminal viewport.
            lines = self.fit_height(lines, max(1, size.lines - 1))
            lines = [self.fit(line, width) for line in lines]
            if self.terminal_size is not None and size != self.terminal_size:
                # Resizing can reflow old rows, invalidating our cursor offset.
                prefix = '\033[H\033[2J'
            self.terminal_size = size
            if size.lines <= 1:
                prefix = '\r\033[2K'
                ending = ''
            if not self.alternate_screen:
                # Keep live frames out of scrollback, including rows pushed
                # beyond the viewport by terminal resize/reflow.
                self.alternate_screen = True
                prefix = '\033[?1049h\033[H\033[2J' + prefix
        self.stream.write(prefix + '\n'.join('\033[2K' + line for line in lines)
                          + ending + ('\033[J' if tty else ''))
        self.stream.flush()
        self.lines = len(lines)

    def restore_terminal(self):
        if self.alternate_screen:
            self.stream.write('\033[?1049l')
            self.stream.flush()
            self.alternate_screen = False
            self.lines = 0
            self.terminal_size = None

    def finish(self):
        """Leave one complete summary in the normal terminal history."""
        self.restore_terminal()
        if not self.finished:
            self.finished = True
            self.stream.write('\n'.join(self.render(time.monotonic())) + '\n')
            self.stream.flush()


class Report:
    def __init__(self, root):
        parent = root / 'docs/TestAutomation/Evidence/test-all-runs'
        for path in (parent, *parent.parents):
            if path.is_symlink():
                raise ValueError('report path contains a symlink')
        parent.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
        self.directory = parent / name
        self.directory.mkdir(mode=0o700)
        from test_retention import retain
        retain(self.directory)
        self.stream = (self.directory / 'report.md').open('x', encoding='utf-8')
        os.chmod(self.directory / 'report.md', 0o600)
        self.dirty = set()
        self.last_sync = time.monotonic()
        self.last_snapshot = -float('inf')
        self.pending_categories = None
        self.write('# Established regression run\n\nStarted: ' + name +
                   '\n\nLive output follows. A missing final result means an incomplete run.\n'
                   'Counts are pytest cases, registered VM executions/E2E variants, and '
                   'one check per non-pytest command. Pending roadmap cases are excluded.\n')

    def write(self, value):
        self.stream.write(value)
        self.stream.flush()
        self.dirty.add(Path(self.stream.name))

    def snapshot(self, categories, *, force=True):
        now = time.monotonic()
        if not force and now - self.last_snapshot < 1:
            self.pending_categories = categories
            return
        path = self.directory / 'progress.json'
        temporary = self.directory / 'progress.tmp'
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump([asdict(item) for item in categories], stream, indent=2)
            stream.flush()
        os.replace(temporary, path)
        self.dirty.add(path)
        self.last_snapshot = now
        self.pending_categories = None

    def resources(self, sample):
        path = self.directory / 'resources.jsonl'
        with path.open('a', encoding='utf-8') as stream:
            os.chmod(path, 0o600)
            stream.write(json.dumps(sample, sort_keys=True) + '\n')
            stream.flush()
        self.dirty.add(path)

    def schedule(self, event):
        with (self.directory / 'schedule.jsonl').open('a', encoding='utf-8') as stream:
            os.chmod(stream.name, 0o600)
            stream.write(json.dumps({'monotonic': time.monotonic(), **event}, sort_keys=True) + '\n')
            stream.flush()
        self.dirty.add(self.directory / 'schedule.jsonl')

    def checkpoint(self, *, force=False):
        # Keep output immediately readable, but do not turn thousands of test
        # events into synchronous disk barriers that close our own I/O gate.
        if self.pending_categories is not None:
            self.snapshot(self.pending_categories, force=force)
        now = time.monotonic()
        if not force and now - self.last_sync < 5:
            return
        for path in sorted(self.dirty):
            with path.open('rb') as stream:
                os.fsync(stream.fileno())
        if self.dirty:
            descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        self.dirty.clear()
        self.last_sync = time.monotonic()

    def close(self):
        try:
            self.checkpoint(force=True)
        finally:
            self.stream.close()


class Execution:
    """A single category's decoder, durable output and result, coordinator-only."""

    def __init__(self, run, item, *, collect=False, events=False, units=None,
                 defer_failure_stop=False):
        self.run, self.item = run, item
        self.collect, self.events, self.units = collect, events, units
        self.defer_failure_stop = defer_failure_stop
        self.pending = b''
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.captured, self.finished, self.failed = [], set(), set()
        self.inventory_seen = False
        self.fixture_failed = False
        run.sequence += 1
        filename = f'category-{run.sequence:03d}.log'
        self.raw = (run.report.directory / filename).open('xb')
        os.chmod(self.raw.name, 0o600)
        try:
            item.state = 'Running'
            item.started = time.monotonic()
            run.report.snapshot(run.categories)
            run.report.write('\n## ' + item.name + (' — collection' if collect else '')
                             + (f' — host branch {item.branch}' if item.branch is not None else '')
                             + '\n\nRaw output: [' + filename + '](' + filename + ')\n')
            run.dashboard.draw(force=True)
        except BaseException:
            self.close()
            raise

    def line(self, raw):
        line = raw.decode('utf-8', errors='replace')
        if self.collect or line.startswith('run-tests: output='):
            self.captured.append(line)
        if self.events and line.startswith(PREFIX):
            event = json.loads(line[len(PREFIX):])
            item = self.item
            if event['kind'] == 'collection':
                if self.inventory_seen:
                    raise ValueError('duplicate test inventory event')
                self.inventory_seen = True
                if item.total is not None and item.total != event['total']:
                    raise ValueError('test inventory changed after collection')
                item.total = event['total']
                if 'nodeids' in event:
                    ids = tuple(event['nodeids'])
                    if len(ids) != item.total or len(set(ids)) != len(ids):
                        raise ValueError('invalid test inventory IDs')
                    if item.nodeids is not None and set(ids) != set(item.nodeids):
                        raise ValueError('test inventory IDs changed after collection')
                    item.nodeids = ids
                elif item.nodeids is not None:
                    raise ValueError('missing test inventory IDs')
            elif event['kind'] == 'finished' and not self.collect:
                if event['nodeid'] in self.finished:
                    raise ValueError('duplicate test completion')
                if item.nodeids is not None and event['nodeid'] not in item.nodeids:
                    raise ValueError('uncollected test completion')
                self.finished.add(event['nodeid'])
                item.done = len(self.finished)
            elif event['kind'] == 'failure':
                self.failed.add(event['nodeid'])
                item.failures = len(self.failed)
                if event.get('when') in ('setup', 'teardown'):
                    self.fixture_failed = True
                    from test_retention import preserve_for_recovery
                    preserve_for_recovery()
            self.run.report.snapshot(self.run.categories, force=event['kind'] == 'failure')
            if event['kind'] == 'failure':
                self.run.report.checkpoint(force=True)
                if not self.run.continue_on_errors and not self.defer_failure_stop:
                    self.run.control.stop()
            self.run.dashboard.draw()
            if self.fixture_failed and not self.defer_failure_stop:
                # Refuse new branches as soon as the durable event arrives.
                # Waiting for pytest to exit permits unrelated work to start
                # while a fixture has already lost storage or cleanup safety.
                self.run.control.stop()

    def output(self, data):
        # Each fragment has a category label. UTF-8 and partial lines remain
        # independent even when several children stream their failures together.
        self.raw.write(data)
        self.raw.flush()
        self.run.report.dirty.add(Path(self.raw.name))
        self.run.report.write('\n<p><b>' + html.escape(self.item.name) + '</b></p>\n<pre>'
                              + html.escape(self.decoder.decode(data)) + '</pre>\n')
        self.pending += data
        while b'\n' in self.pending:
            raw, self.pending = self.pending.split(b'\n', 1)
            self.line(raw)

    def finish(self, status):
        item, run = self.item, self.run
        try:
            if self.pending:
                self.line(self.pending)
                self.pending = b''
            tail = self.decoder.decode(b'', final=True)
            run.report.write('\n' + html.escape(tail) + '\n' + item.name +
                             ' — Exit status: ' + str(status) + '\n')
            if self.collect:
                item.state = 'Pending' if status == 0 else 'Failed'
            else:
                if item.nodeids is not None and not self.inventory_seen and not run.control.stopped.is_set():
                    raise ValueError('missing test execution inventory')
                if not self.events and not run.control.stopped.is_set():
                    before = item.done
                    item.done = (min(item.total or 1, item.done + self.units)
                                 if self.units is not None else item.total or 1)
                    if status:
                        item.failures += item.done - before
                item.state = ('Failed' if self.fixture_failed or item.failures else
                              'Interrupted' if run.control.stopped.is_set() else
                              'Failed' if status or item.failures else
                              'Passed' if item.done == item.total else
                              'Running' if self.units else 'Failed')
            item.stop_timer()
            run.report.snapshot(run.categories)
            run.dashboard.draw(force=True)
            if self.fixture_failed:
                raise ValueError('test fixture setup or cleanup failed; further host work refused')
            if not self.collect and self.events and status not in (0, 1) and not run.control.stopped.is_set():
                from test_retention import preserve_for_recovery
                preserve_for_recovery()
                raise ValueError('test infrastructure failed; further host work refused')
            if item.state == 'Failed' and not run.continue_on_errors:
                run.report.checkpoint(force=True)
                run.control.stop()
            return status, '\n'.join(self.captured)
        finally:
            self.close()

    def close(self):
        self.item.stop_timer()
        if not self.raw.closed:
            try:
                self.run.report.checkpoint(force=True)
            finally:
                self.raw.close()


class Run:
    def __init__(self, root, report, control, *, verify_backing_bytes=True, host_only=False,
                 host_builds=False, serial_builds=False, continue_on_errors=False, scope=None,
                 phases=None):
        self.root, self.report, self.control = root, report, control
        self.continue_on_errors = continue_on_errors
        self.verify_backing_bytes = verify_backing_bytes
        self.phases = phases if phases is not None else (
            ('host',) if host_only or host_builds else ('host', 'system', 'e2e'))
        self.serial_builds = serial_builds
        self.includes_vm = any(kind in self.phases for kind in ('system', 'e2e'))
        self.verification_mode = ('not applicable; host-only run' if not self.includes_vm else
                                  'full' if verify_backing_bytes else 'metadata-only; backing bytes not verified')
        self.report.write('\nScope: ' + (scope or ('complete regression' if
                          self.phases == ('host', 'system', 'e2e') else ' + '.join(self.phases))) + '\n')
        if scope is None:
            self.report.write('\nBuild scheduling: ' + ('after host join (serial comparison)' if serial_builds else
                              'qualified host companions') + '\n')
        self.report.write('\nVM backing verification: ' + self.verification_mode + '\n')
        self.categories = [Category('Discovery and prerequisites', 1)]
        self.dashboard = Dashboard(self.categories)
        self.dashboard.control = control
        self.artifacts = {}
        self.sequence = 0
        self.inputs = None
        self.admission = Admission(observe=self.observe_resources)

    def observe_resources(self, sample):
        self.report.resources({**sample, 'running_categories': [item.name for item in self.categories
                                                             if item.state == 'Running']})

    def command(self, category, *args):
        if category == 'ui':
            return [str(self.root / 'tools/run-ui-tests'), '--unattended', *args]
        if category in ('system', 'e2e') and '--list' not in args and not self.verify_backing_bytes:
            args = (*args, '--skip-backing-verification')
        return [str(self.root / 'tools/run-tests'), category, '--unattended', *args]

    def execute(self, item, command, *, collect=False, events=False, units=None):
        if self.control.stopped.is_set():
            item.state = 'Interrupted'
            return 130, ''
        item.retry_category = ('ui' if Path(command[0]).name == 'run-ui-tests' else
                               command[1] if Path(command[0]).name == 'run-tests' else None)
        if not collect and len(command) > 1 and command[1] in ('publish', 'artifacts', 'system', 'e2e'):
            self.wait_for_resources(item, command[1])
            if self.control.stopped.is_set():
                item.state = 'Interrupted'
                return 130, ''
        # VM controllers own failure handling, collection and the final suite
        # audit. Report their events immediately without cancelling that cleanup.
        # finish() still stops subsequent work after the controller exits.
        execution = Execution(self, item, collect=collect, events=events, units=units,
                              defer_failure_stop=len(command) > 1 and command[1] in ('system', 'e2e'))

        def tick():
            # Serial builders and VM controllers also need observations during
            # execution, not just the sample that admitted their launch. Report
            # writes remain on the coordinator and retain normal cancellation.
            self.admission.update()
            self.report.checkpoint()
            self.dashboard.draw()

        try:
            status = self.control.run(command, cwd=self.root, env=host.environment(self.root),
                                      output=execution.output, cooperative=True,
                                      tick=tick)
            return execution.finish(status)
        finally:
            execution.close()

    def wait_for_resources(self, item, kind):
        if kind in ('system', 'e2e'):
            self.admission.demands[kind] = vm_demand(self.root)
        started = time.monotonic()
        previous = None
        while not self.control.stopped.is_set() and not self.admission.allows(kind, []):
            item.wait_reason = self.admission.reason
            if item.wait_reason != previous:
                self.report.write('\nScheduler: ' + item.wait_reason + '\n')
                self.report.snapshot(self.categories)
                previous = item.wait_reason
            self.report.checkpoint()
            self.dashboard.draw()
            self.control.stopped.wait(2)
        item.waiting += time.monotonic() - started
        item.wait_reason = ''

    def host_jobs(self, jobs, *, phase='host'):
        queued = time.monotonic()
        before = sum(job.item.elapsed for job in jobs)
        setattr(self.dashboard, phase + '_started', queued)
        setattr(self.dashboard, phase + '_elapsed', None)
        for job in jobs:
            job.item.host = True
            job.item.phase = phase

        def begin(job):
            # Bucket builders retain the public category explicitly. Resource
            # kinds and future command-name prefixes do not define ownership.
            # Do not evaluate deferred commands again just to label evidence.
            job.item.retry_category = job.item.retry_category or job.kind
            occupied = {other.item.branch for other in jobs if other.item.state == 'Running'}
            job.item.branch = next(branch for branch in range(1, HOST_WORKERS + 1)
                                   if branch not in occupied)
            job.item.launch_order = self.sequence + 1
            job.item.waiting += time.monotonic() - queued
            job.item.wait_reason = ''
            self.report.schedule({'event': 'start', 'job': job.key or job.item.name,
                                  'phase': phase,
                                  'kind': job.kind, 'branch': job.item.branch,
                                  'companions': [other.kind for other in jobs
                                                 if other.item.state == 'Running'],
                                  'estimate_seconds': job.estimate,
                                  'requires': job.requires})
            return Execution(self, job.item, events=job.events)

        def command(argv, output):
            return self.control.run(argv, cwd=self.root, env=host.environment(self.root),
                                    output=output, cooperative=True)

        def waiting(job, reason):
            job.item.wait_reason = reason
            self.report.schedule({'event': 'waiting', 'job': job.key or job.item.name, 'reason': reason})
            self.report.write('\nScheduler: ' + job.item.name + ': ' + reason + '\n')
            self.report.snapshot(self.categories)
            self.dashboard.draw(force=True)

        def blocked(job, reason):
            job.item.state, job.item.wait_reason = 'Blocked', reason
            job.item.waiting = time.monotonic() - queued
            self.report.schedule({'event': 'blocked', 'job': job.key or job.item.name,
                                  'reason': reason, 'requires': job.requires})
            self.report.snapshot(self.categories)

        def tick():
            self.report.checkpoint()
            self.dashboard.draw()

        try:
            if phase == 'cleanup' and len(jobs) > 1 and hasattr(self.admission, 'overlap_ready'):
                # Sample CPU/memory headroom before the first bucket adds load.
                # Give hysteresis one recovery window plus a sample. This is bounded;
                # missing metrics and persistent pressure retain normal fallback.
                deadline = queued + PRESSURE_RECOVERY_SECONDS + 2
                while (not self.control.stopped.is_set() and time.monotonic() < deadline
                       and not self.admission.overlap_ready()):
                    for job in jobs:
                        if not job.item.wait_reason:
                            waiting(job, 'warming up cleanup parallel admission')
                    tick()
                    self.control.stopped.wait(.1)
            maximum = run_jobs(jobs, control=self.control, begin=begin, run_command=command,
                               admission=self.admission, waiting=waiting,
                               tick=tick, complete=self.complete_host, blocked=blocked)
        finally:
            setattr(self.dashboard, phase + '_elapsed', time.monotonic() - queued)
            self.dashboard.draw(force=True)
        elapsed = time.monotonic() - queued
        executed = sum(job.item.elapsed for job in jobs) - before
        self.report.write(f'\n{phase.capitalize()} scheduling: wall={elapsed:.3f}s '
                          f'category-execution={executed:.3f}s maximum-active={maximum}\n')

    def complete_host(self, job, result):
        status, output = result
        if job.key in ('build-a', 'build-b') and status == 0:
            matches = re.findall(r'^run-tests: output=(/tmp/onpc-test-artifacts-[A-Za-z0-9_-]+)$', output, re.M)
            if (len(matches) != 1 or job.key in self.artifacts
                    or matches[0] in self.artifacts.values()):
                job.item.state = 'Failed'
                job.item.failures = max(1, job.item.failures)
                self.report.snapshot(self.categories)
                raise ValueError('package build output invalid; package-bearing suites refused')
            self.artifacts[job.key] = matches[0]
        self.report.schedule({'event': 'finish', 'job': job.key or job.item.name,
                              'phase': job.item.phase,
                              'kind': job.kind, 'state': job.item.state,
                              'elapsed_seconds': job.item.elapsed, 'waiting_seconds': job.item.waiting})

    def build_jobs(self, publishing, builds):
        # Estimates come from retained complete runs; they only order work.
        # Deferred comparison arguments are resolved on the coordinator after
        # both successful builders have supplied distinct artifact directories.
        return [*([Job('publish', publishing, self.command('publish'), estimate=360, key='publish')]
                  if publishing is not None else []),
                Job('artifacts', builds[0], self.command('artifacts', 'build'),
                    estimate=7, key='build-a'),
                Job('artifacts', builds[1], self.command('artifacts', 'build'),
                    estimate=7, key='build-b'),
                Job('artifacts', builds[2], lambda: self.command('artifacts', 'compare',
                    self.artifacts['build-a'], self.artifacts['build-b']),
                    estimate=1, key='compare', requires=('build-a', 'build-b'))]

    def pytest_jobs(self, kind, inventory, args, *, exact=False):
        """Share module isolation and scheduling across host and selected runs."""
        buckets = {'ui': ui_buckets, 'unit': unit_buckets}[kind](inventory.nodeids)
        items = [Category(bucket.name, len(bucket.nodeids), nodeids=bucket.nodeids,
                          retry_category=kind)
                 for bucket in buckets]
        position = self.categories.index(inventory)
        self.categories[position:position + 1] = items
        return [Job(bucket.kind, item,
                    self.command(kind, *args, *(bucket.nodeids if exact else bucket.paths)),
                    events=True, estimate=bucket.estimate)
                for bucket, item in zip(buckets, items, strict=True)]

    def run(self):
        from test_commands import suite_inventory
        inventory = suite_inventory(('host',))
        self.inputs = source_identity(self.root)
        self.report.write('\nInitial source inputs SHA-256 (informational): ' + self.inputs + '\n')
        if 'host' not in self.phases:
            return self.run_vm_only()
        discovery = self.categories[0]
        pytest_kinds = ('unit', 'component', 'ui', 'fixture-runtime')
        suites = [(CATEGORY_NAMES[kind], kind, inventory[kind]['args']) for kind in pytest_kinds]
        suite_items = [Category(name) for name, _, _ in suites]
        fixed = [(CATEGORY_NAMES.get(kind, inventory[kind]['description']), kind) for kind in inventory
                 if kind not in (*pytest_kinds, 'artifacts', 'publish')]
        fixed.append((CATEGORY_NAMES['publish'], 'publish'))
        fixed_items = [Category(name, 1) for name, _ in fixed]
        builds = [Category(name, 1) for name in ('Package build A', 'Package build B',
                                               'Package reproducibility')]
        system = Category(CATEGORY_NAMES['system']) if 'system' in self.phases else None
        graphical = Category(CATEGORY_NAMES['e2e']) if 'e2e' in self.phases else None
        safety = Category('Cleanup safety prerequisites')
        self.categories.extend([safety, *suite_items, *fixed_items[:-1]])
        self.categories.extend([fixed_items[-1], *builds])
        self.categories.extend(item for item in (system, graphical) if item is not None)
        discovery.state = 'Running'
        discovery.started = time.monotonic()
        self.dashboard.draw(force=True)

        # Collection uses the same launchers/selections as execution. No
        # manually maintained case counts or roadmap completion documents.
        selections = [('unit', ['tests/unit/test_*cleanup_safety.py',
                                'tests/unit/test_graphical_lease.py'], safety)]
        selections.extend((kind, args, item) for (_, kind, args), item in zip(suites, suite_items))
        for kind, args, item in selections:
            if self.control.stopped.is_set():
                return
            status, _ = self.execute(item, self.command(kind, *args, '--collect-only', '-q'),
                                     collect=True, events=True)
            if status or not item.total:
                if self.control.stopped.is_set():
                    return
                raise ValueError('pytest collection failed or collected no tests')
        unit_jobs = self.pytest_jobs('unit', suite_items[0], ['-q', '--durations=0'])
        ui_jobs = self.pytest_jobs('ui', suite_items[2], [*inventory['ui']['args'], '-q', '--durations=0'])
        if self.includes_vm:
            ready = self.discover_vm(system, graphical)
            if self.control.stopped.is_set():
                return
            authorization()
        discovery.done, discovery.state = 1, 'Passed'
        discovery.stop_timer()

        self.cleanup_jobs(safety)
        if self.control.stopped.is_set():
            return
        estimates = {'component': 20, 'fixture-runtime': 12}
        jobs = [Job(kind, item, self.command(kind, *args, '-q'), events=True,
                    estimate=estimates[kind]) for (_, kind, args), item in zip(suites, suite_items)
                if kind not in ('unit', 'ui')]
        jobs.extend(unit_jobs)
        jobs.extend(ui_jobs)
        jobs.extend(Job(kind, item, self.command(kind, *inventory[kind]['args']), estimate=1)
                    for (_, kind), item in zip(fixed, fixed_items) if kind != 'publish')
        package_jobs = self.build_jobs(fixed_items[-1], builds)
        if not self.serial_builds:
            jobs.extend(package_jobs)
        self.host_jobs(jobs)
        if self.control.stopped.is_set():
            return
        if self.serial_builds:
            outcomes = {}
            for job in package_jobs:
                if not all(outcomes.get(key) for key in job.requires):
                    job.item.state = 'Blocked'
                    job.item.wait_reason = 'required host job failed'
                    self.report.snapshot(self.categories)
                    continue
                self.report.schedule({'event': 'start', 'job': job.key, 'kind': job.kind,
                                      'branch': None, 'companions': [], 'requires': job.requires,
                                      'estimate_seconds': job.estimate})
                result = self.execute(job.item, job.command() if callable(job.command) else job.command)
                if self.control.stopped.is_set():
                    return
                self.complete_host(job, result)
                outcomes[job.key] = job.item.state == 'Passed'
        if not self.includes_vm:
            return
        if any(job.item.state != 'Passed' for job in package_jobs):
            for item in (system, graphical):
                if item is not None:
                    item.state, item.wait_reason = 'Blocked', 'package qualification failed'
            self.report.snapshot(self.categories)
            return
        self.vm_tests(system, graphical, ready)

    def run_vm_only(self):
        """Build one required input; keep all selected VM work sequential."""
        discovery = self.categories[0]
        build = Category('Package input build', 1)
        system = Category(CATEGORY_NAMES['system']) if 'system' in self.phases else None
        graphical = Category(CATEGORY_NAMES['e2e']) if 'e2e' in self.phases else None
        self.categories.extend([build, *(item for item in (system, graphical) if item is not None)])
        discovery.state, discovery.started = 'Running', time.monotonic()
        ready = self.discover_vm(system, graphical)
        if self.control.stopped.is_set():
            return
        if system is None and not ready:
            # Successful collection is not customer coverage. No executable
            # consumer needs package inputs or privileged VM prerequisites.
            self.categories.remove(build)
            discovery.done, discovery.state = 1, 'Passed'
            discovery.stop_timer()
            self.vm_tests(system, graphical, ready)
            return
        authorization()
        discovery.done, discovery.state = 1, 'Passed'
        discovery.stop_timer()
        self.host_jobs([Job('artifacts', build, self.command('artifacts', 'build'), key='build-a')])
        if self.control.stopped.is_set() or build.state != 'Passed':
            return
        self.vm_tests(system, graphical, ready)

    def cleanup_jobs(self, safety):
        buckets = cleanup_buckets(safety.nodeids)
        items = [Category(bucket.name, len(bucket.nodeids), nodeids=bucket.nodeids,
                          host=True, phase='cleanup', retry_category='unit') for bucket in buckets]
        position = self.categories.index(safety)
        self.categories[position:position + 1] = items
        jobs = [Job(bucket.kind, item, self.command('unit', *bucket.paths, '-q', '--durations=0'),
                    events=True, estimate=bucket.estimate)
                for bucket, item in zip(buckets, items, strict=True)]
        self.host_jobs(jobs, phase='cleanup')
        if self.control.stopped.is_set():
            return
        if any(item.state != 'Passed' for item in items):
            raise ValueError('cleanup safety prerequisites failed; protected suites refused')
        # The scheduler has joined every worker; Execution validated each exact
        # inventory, completion and exit. Persist before reuse.
        self.report.snapshot(self.categories)
        self.report.checkpoint(force=True)
        import test_activity
        test_activity.record_cleanup(self.inputs)
        self.report.write('\nHost cleanup prerequisites: passed; owned host workers reuse '
                          'this gate for the current activity.\n')

    def discover_vm(self, system, graphical):
        if system is not None:
            status, listing = self.execute(system, self.command('system', '--list'), collect=True)
            if self.control.stopped.is_set():
                return []
            match = re.search(r'expected-executions: (\d+)', listing)
            if status or match is None:
                raise ValueError('installed-system inventory failed')
            system.total = int(match[1])
        if graphical is None:
            return []
        status, listing = self.execute(graphical, self.command('e2e', '--list', '--ready'), collect=True)
        if self.control.stopped.is_set():
            return []
        if status:
            raise ValueError('E2E inventory failed')
        inventory = json.loads(listing[listing.index('{'):])
        ready = [case['case_id'] for case in inventory['cases']]
        graphical.total = len(ready)
        graphical.nodeids = tuple(ready)
        self.report.write('\nReady E2E variants: ' + ', '.join(ready) + '\n'
                          'Pending variants excluded: ' + str(len(inventory['excluded_pending_cases'])) + '\n')
        return ready

    def vm_tests(self, system, graphical, ready):
        if system is not None:
            status, _ = self.execute(system, self.command('system', '--artifacts', self.artifacts['build-a']), events=True)
            if self.control.stopped.is_set():
                return
            if status:
                raise ValueError('installed-system attempt failed; subsequent VM attempts refused')
        if graphical is not None and ready:
            # One dispatcher invocation keeps prerequisite checks and the VM
            # lease at suite scope. The controller reports each case and stops
            # on case/transition failure; its final status includes suite cleanup.
            self.execute(graphical, self.command('e2e', '--artifacts', self.artifacts['build-a'],
                                                 '--ready'), events=True)
        elif graphical is not None:
            graphical.state = 'Interrupted' if self.control.stopped.is_set() else 'Failed'
            if graphical.state == 'Failed':
                graphical.wait_reason = 'no ready E2E variants'
                self.report.write('\nE2E execution refused: no ready E2E variants; '
                                  'no customer scenarios executed. See '
                                  '`tests/e2e/scenarios.json` pending_reason fields '
                                  'for implementation and qualification blockers.\n')


def recover_initial_checks(root, state):
    """Accept only a dead owner stopped before the protected-suite gate passed."""
    import test_activity
    import test_retention
    if not test_activity.descriptors() or len(state['paths']) != 1:
        return False
    record = state['paths'][0]
    report = Path(record['path'])
    if report.parent != root / 'docs/TestAutomation/Evidence/test-all-runs':
        return False
    try:
        # Verify the registered identity without removing anything. Missing or
        # unreadable progress is uncertainty, not permission to restart suites.
        test_retention.remove(record, validate_only=True)
        progress = json.loads((report / 'progress.json').read_text())
        # A dead parallel coordinator cannot prove that all worker cleanups
        # finished. Keep that journal for explicit recovery, never infer safety
        # from partial bucket successes or an absent schedule file.
        if any(item.get('phase') == 'cleanup' for item in progress):
            return False
        by_name = {item['name']: item for item in progress}
        if len(by_name) != len(progress):
            return False
        if by_name['Discovery and prerequisites']['state'] != 'Passed':
            return False
        if by_name['Cleanup safety prerequisites']['state'] != 'Running':
            return False
        for name, item in by_name.items():
            if name in ('Discovery and prerequisites', 'Cleanup safety prerequisites'):
                continue
            if (item['state'] != 'Pending' or item['done'] != 0
                    or item['failures'] != 0 or item['started'] is not None):
                return False
        if len(by_name) < 3 or (report / 'schedule.jsonl').exists():
            return False
    except (OSError, ValueError, KeyError, TypeError):
        return False
    print('Recovering interrupted initial checks; preserving the previous journal '
          'and all registered evidence.', flush=True)
    return True


def main(root=None, *, verify_backing_bytes=True, host_only=False, host_builds=False, serial_builds=False,
         continue_on_errors=False, selections=None, phases=None, stop_on_error=False):
    import test_retention
    import test_activity
    root = root or Path(__file__).resolve().parents[1]
    # Keep repeated interrupts cooperative through storage rotation/finalization,
    # including after the inner command controller has restored its handlers.
    with Control().installed() as storage_control:
        with test_retention.Store(test_activity.retention_path(root)).session(
                recover=lambda state: recover_initial_checks(root, state)):
            if storage_control.stopped.is_set():
                return 130
            status = retained_main(root, verify_backing_bytes=verify_backing_bytes,
                                   host_only=host_only, host_builds=host_builds,
                                   serial_builds=serial_builds, continue_on_errors=continue_on_errors,
                                   selections=selections, phases=phases, stop_on_error=stop_on_error)
        return 130 if storage_control.stopped.is_set() else status


def retained_main(root=None, *, verify_backing_bytes=True, host_only=False, host_builds=False, serial_builds=False,
                  continue_on_errors=False, selections=None, phases=None, stop_on_error=False):
    root = root or Path(__file__).resolve().parents[1]
    report = None
    run = None
    status = 1
    failed = False
    with Control().installed() as control:
        try:
            report = Report(root)
            if selections is None:
                run = Run(root, report, control, verify_backing_bytes=verify_backing_bytes, host_only=host_only,
                          host_builds=host_builds, serial_builds=serial_builds,
                          continue_on_errors=continue_on_errors, phases=phases)
            else:
                from regression_selection import SelectedRun
                run = SelectedRun(root, report, control, selections, stop_on_error=stop_on_error)
            run.run()
            status = 0 if all(item.state == 'Passed' for item in run.categories) else 1
        except (Exception, KeyboardInterrupt) as error:
            failed = not isinstance(error, KeyboardInterrupt)
            if report is None and failed:
                print(f'Report initialization failed: {type(error).__name__}: {error}',
                      file=sys.stderr)
            if report is not None:
                try:
                    report.write('\nRunner failure: ' + html.escape(str(error)) + '\n')
                except OSError:
                    if run is not None:
                        run.dashboard.restore_terminal()
                    print('Regression evidence storage failed; owned cleanup has finished.', file=sys.stderr)
            if run is not None:
                for item in run.categories:
                    if item.state == 'Running':
                        item.state = 'Failed'
        finally:
            if control.stopped.is_set() and not failed:
                status = 130
            try:
                if run is not None:
                    run.dashboard.cleanup_finished = True
                    for item in run.categories:
                        item.stop_timer()
                        if item.state in ('Running', 'Pending'):
                            item.state = 'Interrupted' if status == 130 else 'Blocked'
                    report.snapshot(run.categories)
                    report.write('\n## Final result\n\n' + ('Passed' if status == 0 else
                                 'Interrupted; owned child cleanup finished' if status == 130 else 'Failed') + '\n')
                    report.write('\nVM backing verification: ' + run.verification_mode + '\n')
                    summary = '\n'.join(run.dashboard.render(time.monotonic()))
                    report.write('\n<pre>' + html.escape(Dashboard.ANSI.sub('', summary)) + '</pre>\n')
                elif report is None:
                    print('\033[31m[✗] Report initialization - 0% (0/1)\033[0m')
            except OSError:
                status = 1
                if run is not None:
                    run.dashboard.restore_terminal()
                print('Regression final evidence could not be saved; result is failed.', file=sys.stderr)
            finally:
                if run is not None:
                    run.dashboard.finish()
                if report is not None:
                    try:
                        report.close()
                    except OSError:
                        status = 1
                        print('Regression final evidence could not be synced; result is failed.', file=sys.stderr)
    if report is not None:
        print(f'Report: {report.directory / "report.md"}', flush=True)
    if report is not None and (status == 1 or (run is not None and any(
            item.failures or item.state == 'Failed' for item in run.categories))):
        print('\nCopy this prompt into a new Codex session:\n')
        prompt = (f'In {root.resolve()}, investigate and fix the failures in '
              f'{(report.directory / "report.md").resolve()}. '
              'Read the adjacent progress.json for category results and follow '
              'any detailed evidence paths in the report. Fix the root causes, '
              'On a behavior mismatch, report expected versus actual behavior, never assume app behavior is expected and test expectation is wrong. '
              'Obtain developer confirmation before accepting the change or altering expectations unless that exact behavior change '
              'is already authorized. Never weaken, skip or delete a check to match the app. '
              'ONLY rerun the relevant checks, do NOT run more tests than necessary to validate the fixes, and report anything still unresolved. '
              'If the run was manually interrupted, ignore the interruption, and just fix the recorded failures. ')
        print(prompt)
        retries = list(dict.fromkeys(item.retry_category for item in run.categories
                                     if (item.failures or item.state == 'Failed')
                                     and item.retry_category)) if run is not None else []
        handoff = report.directory / 'failure.json'
        handoff.write_text(json.dumps({'prompt': prompt, 'categories': retries}, indent=2))
        print(f'Failure handoff: {handoff.resolve()}', flush=True)
    return status
