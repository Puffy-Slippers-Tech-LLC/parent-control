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
from regression_resources import Admission, vm_demand


def authorization():
    from dev_privileges import check
    check('/usr/local/libexec/onpc-test-runner')
    if '--unattended' not in Path('/usr/local/libexec/onpc-test-runner').read_text():
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

    def duration(self, now):
        seconds = self.elapsed + (now - self.started if self.started is not None else 0)
        return f'{seconds:.0f}s' if seconds < 60 else f'{seconds / 60:.1f}m'

    def stop_timer(self):
        if self.started is not None:
            self.elapsed += time.monotonic() - self.started
            self.started = None


class Dashboard:
    ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

    def __init__(self, categories, stream=None):
        self.categories = categories
        self.stream = stream or sys.stdout
        self.lines = 0
        self.last = 0.0
        self.started = time.monotonic()
        self.host_started = None
        self.host_elapsed = None

    @staticmethod
    def counts(done, failures, total):
        passed = max(0, done - failures)
        counts = f'\033[0m(\033[32m{passed}\033[0m/'
        if failures:
            counts += f'\033[31m{failures}\033[0m/'
        return counts + f'{total})'

    def category(self, item, now):
        total = '?' if item.total is None else str(item.total)
        percent = '?' if item.total is None else str(int(100 * item.done / max(item.total, 1)))
        label = {'Passed': '✓', 'Failed': '✗', 'Interrupted': '✗',
                 'Blocked': '✗'}.get(item.state, item.state)
        color = {'Passed': '32', 'Failed': '31', 'Interrupted': '31',
                 'Blocked': '31', 'Running': '97;1', 'Pending': '90'}[item.state]
        return (f'\033[{color}m[{label}] {item.name} - {percent}% '
                + self.counts(item.done, item.failures, total)
                + f' - {item.duration(now)}'
                + (f' ({item.wait_reason})' if item.wait_reason else '') + '\033[0m')

    def branches(self, items, now):
        lines = []
        for branch in (1, 2):
            assigned = sorted((item for item in items if item.branch == branch),
                              key=lambda item: item.launch_order)
            active = any(item.state == 'Running' for item in assigned)
            state = 'running' if active else 'idle' if self.host_elapsed is None else 'finished'
            lines.append(f'├─ Host branch {branch} — {state}; one category at a time')
            if not assigned:
                lines.append('│  └─ No categories assigned')
            for index, item in enumerate(assigned):
                connector = '└─ ' if index == len(assigned) - 1 else '├─ '
                lines.append('│  ' + connector + self.category(item, now))
        unassigned = [item for item in items if item.branch is None]
        if unassigned:
            lines.append('│  Unassigned host work — waiting for a branch and headroom')
            lines.extend('│    ' + self.category(item, now) for item in unassigned)
        if self.host_elapsed is None:
            state = 'waiting for host work'
        else:
            state = 'passed' if all(item.state == 'Passed' for item in items) else 'incomplete or failed'
        elapsed = self.host_elapsed
        if elapsed is None and self.host_started is not None:
            elapsed = now - self.host_started
        timing = '' if elapsed is None else f' — {(elapsed / 60):.1f}m wall time'
        lines.append(f'└─ Join host branches — {state}{timing}')
        return lines

    def render(self, now):
        lines = []
        hosts = [item for item in self.categories if item.host]
        for item in self.categories:
            if item.host:
                if item is hosts[0]:
                    lines.extend(self.branches(hosts, now))
            else:
                lines.append(('│  ' if hosts else '') + self.category(item, now))
        done = sum(item.done for item in self.categories)
        known = all(item.total is not None for item in self.categories)
        total = sum(item.total or 0 for item in self.categories)
        percent = str(int(100 * done / max(total, 1))) if known else '?'
        color = '31' if any(c.state in ('Failed', 'Interrupted', 'Blocked') for c in self.categories) else (
            '32' if all(c.state == 'Passed' for c in self.categories) else '97;1')
        failures = sum(item.failures for item in self.categories)
        lines.append(f'\033[{color}mOverall - {percent}% '
                     + self.counts(done, failures, total if known else '?')
                     + f' - {(now - self.started) / 60:.1f}m\033[0m')
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

    def draw(self, *, force=False):
        now = time.monotonic()
        if not force and now - self.last < 1:
            return
        self.last = now
        lines = self.render(now)
        tty = self.stream.isatty()
        prefix = f'\033[{self.lines}F' if self.lines and tty else ''
        if tty:
            width = max(1, shutil.get_terminal_size().columns - 1)
            lines = [self.fit(line, width) for line in lines]
        self.stream.write(prefix + '\n'.join('\033[2K' + line for line in lines)
                          + '\n' + ('\033[J' if tty else ''))
        self.stream.flush()
        self.lines = len(lines)


class Report:
    def __init__(self, root):
        parent = root / 'docs/TestAutomation/Evidence/test-all-runs'
        for path in (parent, *parent.parents):
            if path.is_symlink():
                raise ValueError('report path contains a symlink')
        parent.mkdir(exist_ok=True)
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
        self.directory = parent / name
        self.directory.mkdir(mode=0o700)
        self.stream = (self.directory / 'report.md').open('x', encoding='utf-8')
        os.chmod(self.directory / 'report.md', 0o600)
        self.write('# Established regression run\n\nStarted: ' + name +
                   '\n\nLive output follows. A missing final result means an incomplete run.\n'
                   'Counts are pytest cases, registered VM executions/E2E variants, and '
                   'one check per non-pytest command. Pending roadmap cases are excluded.\n')

    def write(self, value):
        self.stream.write(value)
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def snapshot(self, categories):
        path = self.directory / 'progress.json'
        temporary = self.directory / 'progress.tmp'
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump([asdict(item) for item in categories], stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def resources(self, sample):
        path = self.directory / 'resources.jsonl'
        with path.open('a', encoding='utf-8') as stream:
            os.chmod(path, 0o600)
            stream.write(json.dumps(sample, sort_keys=True) + '\n')
            stream.flush()
            os.fsync(stream.fileno())


class Execution:
    """A single category's decoder, durable output and result, coordinator-only."""

    def __init__(self, run, item, *, collect=False, events=False, units=None):
        self.run, self.item = run, item
        self.collect, self.events, self.units = collect, events, units
        self.pending = b''
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.captured, self.finished, self.failed = [], set(), set()
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
                if item.total is not None and item.total != event['total']:
                    raise ValueError('test inventory changed after collection')
                item.total = event['total']
            elif event['kind'] == 'finished' and not self.collect:
                if event['nodeid'] in self.finished:
                    raise ValueError('duplicate test completion')
                self.finished.add(event['nodeid'])
                item.done = len(self.finished)
            elif event['kind'] == 'failure':
                self.failed.add(event['nodeid'])
                item.failures = len(self.failed)
            self.run.report.snapshot(self.run.categories)
            self.run.dashboard.draw()

    def output(self, data):
        # Each fragment has a category label. UTF-8 and partial lines remain
        # independent even when two children stream their failures together.
        self.raw.write(data)
        self.raw.flush()
        os.fsync(self.raw.fileno())
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
                if not self.events and not run.control.stopped.is_set():
                    before = item.done
                    item.done = (min(item.total or 1, item.done + self.units)
                                 if self.units is not None else item.total or 1)
                    if status:
                        item.failures += item.done - before
                item.state = ('Interrupted' if run.control.stopped.is_set() else
                              'Failed' if status or item.failures else
                              'Passed' if item.done == item.total else
                              'Running' if self.units else 'Failed')
            item.stop_timer()
            run.report.snapshot(run.categories)
            run.dashboard.draw(force=True)
            run.check_inputs()
            return status, '\n'.join(self.captured)
        finally:
            self.close()

    def close(self):
        self.item.stop_timer()
        self.raw.close()


class Run:
    def __init__(self, root, report, control):
        self.root, self.report, self.control = root, report, control
        self.categories = [Category('Discovery and prerequisites', 1)]
        self.dashboard = Dashboard(self.categories)
        self.artifacts = []
        self.sequence = 0
        self.inputs = None
        self.admission = Admission(observe=self.report.resources)

    def check_inputs(self):
        if self.inputs is not None and source_identity(self.root) != self.inputs:
            raise ValueError('source inputs changed during regression run; results cannot be combined')

    def command(self, category, *args):
        if category == 'ui':
            return [str(self.root / 'tools/run-ui-tests'), '--unattended', *args]
        return [str(self.root / 'tools/run-tests'), category, '--unattended', *args]

    def execute(self, item, command, *, collect=False, events=False, units=None):
        if self.control.stopped.is_set():
            item.state = 'Interrupted'
            return 130, ''
        self.check_inputs()
        if not collect and len(command) > 1 and command[1] in ('publish', 'artifacts', 'system', 'e2e'):
            self.wait_for_resources(item, command[1])
            if self.control.stopped.is_set():
                item.state = 'Interrupted'
                return 130, ''
        execution = Execution(self, item, collect=collect, events=events, units=units)
        try:
            status = self.control.run(command, cwd=self.root, env=host.environment(self.root),
                                      output=execution.output, cooperative=True,
                                      tick=self.dashboard.draw)
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
            self.dashboard.draw()
            self.control.stopped.wait(2)
        item.waiting += time.monotonic() - started
        item.wait_reason = ''

    def host_jobs(self, jobs):
        queued = time.monotonic()
        before = sum(job.item.elapsed for job in jobs)
        self.dashboard.host_started = queued
        for job in jobs:
            job.item.host = True

        def begin(job):
            self.check_inputs()
            occupied = {other.item.branch for other in jobs if other.item.state == 'Running'}
            job.item.branch = next(branch for branch in (1, 2) if branch not in occupied)
            job.item.launch_order = self.sequence + 1
            job.item.waiting += time.monotonic() - queued
            job.item.wait_reason = ''
            return Execution(self, job.item, events=job.events)

        def command(argv, output):
            return self.control.run(argv, cwd=self.root, env=host.environment(self.root),
                                    output=output, cooperative=True)

        def waiting(reason):
            for job in jobs:
                if job.item.state == 'Pending':
                    job.item.wait_reason = reason
            self.report.write('\nScheduler: ' + reason + '\n')
            self.report.snapshot(self.categories)
            self.dashboard.draw(force=True)

        try:
            maximum = run_jobs(jobs, control=self.control, begin=begin, run_command=command,
                               admission=self.admission, waiting=waiting,
                               tick=self.dashboard.draw)
        finally:
            self.dashboard.host_elapsed = time.monotonic() - queued
            self.dashboard.draw(force=True)
        elapsed = time.monotonic() - queued
        executed = sum(job.item.elapsed for job in jobs) - before
        self.report.write(f'\nHost scheduling: wall={elapsed:.3f}s '
                          f'category-execution={executed:.3f}s maximum-active={maximum}\n')

    def run(self):
        self.inputs = source_identity(self.root)
        self.report.write('\nSource inputs SHA-256: ' + self.inputs + '\n')
        discovery = self.categories[0]
        suites = [('Unit and contracts', 'unit', []),
                  ('Private D-Bus components', 'component', []),
                  ('UI and nested Shell', 'ui', ['--timeout', '1800s']),
                  ('Fixture runtime', 'fixture-runtime', [])]
        suite_items = [Category(name) for name, _, _ in suites]
        fixed = [('Source and traceability', 'source'), ('Static checks', 'static'),
                 ('Child Node', 'child-node'), ('Child GJS', 'child-gjs'),
                 ('Backend prerequisites', 'backend'), ('Publishing tests', 'publish')]
        fixed_items = [Category(name, 1) for name, _ in fixed]
        builds = Category('Package builds and reproducibility', 3)
        system = Category('Installed-system tests')
        graphical = Category('Ready E2E scenarios')
        safety = Category('Cleanup safety prerequisites')
        self.categories.extend([safety, *suite_items, *fixed_items, builds, system, graphical])
        discovery.state = 'Running'
        discovery.started = time.monotonic()
        self.dashboard.draw(force=True)

        # Collection uses the same launchers/selections as execution. No
        # manually maintained case counts or roadmap completion documents.
        selections = [('unit', ['tests/unit/test_*cleanup_safety.py',
                                'tests/unit/test_graphical_lease.py'], safety)]
        selections.extend((kind, args, item) for (_, kind, args), item in zip(suites, suite_items))
        for kind, args, item in selections:
            status, _ = self.execute(item, self.command(kind, *args, '--collect-only', '-q'),
                                     collect=True, events=True)
            if status or not item.total:
                raise ValueError('pytest collection failed or collected no tests')
        status, listing = self.execute(system, self.command('system', '--list'), collect=True)
        match = re.search(r'expected-executions: (\d+)', listing)
        if status or match is None:
            raise ValueError('installed-system inventory failed')
        system.total = int(match[1])
        status, listing = self.execute(graphical, self.command('e2e', '--list'), collect=True)
        if status:
            raise ValueError('E2E inventory failed')
        inventory = json.loads(listing[listing.index('{'):])
        ready = [case['case_id'] for case in inventory['cases'] if case['status'] == 'ready']
        graphical.total = len(ready)
        self.report.write('\nReady E2E variants: ' + ', '.join(ready) + '\n'
                          'Pending variants excluded: ' + str(len(inventory['pending_cases'])) + '\n')
        authorization()
        discovery.done, discovery.state = 1, 'Passed'
        discovery.stop_timer()

        status, _ = self.execute(safety, self.command('unit', *selections[0][1], '-q'), events=True)
        if status or safety.state != 'Passed':
            raise ValueError('cleanup safety prerequisites failed; protected suites refused')
        estimates = {'ui': 840, 'unit': 150, 'component': 20, 'fixture-runtime': 12}
        jobs = [Job(kind, item, self.command(kind, *args, '-q'), events=True,
                    estimate=estimates[kind]) for (_, kind, args), item in zip(suites, suite_items)]
        jobs.extend(Job(kind, item, self.command(kind), estimate=1)
                    for (_, kind), item in zip(fixed, fixed_items) if kind != 'publish')
        self.host_jobs(jobs)
        if self.control.stopped.is_set():
            return
        # The costly builder is deliberately outside the qualified host overlap.
        # It already uses two internal jobs and competes with UI for disk/memory.
        self.execute(fixed_items[-1], self.command('publish'))
        if self.control.stopped.is_set():
            return
        for index in range(2):
            status, output = self.execute(builds, self.command('artifacts', 'build'), units=1)
            match = re.search(r'^run-tests: output=(/tmp/onpc-test-artifacts-[A-Za-z0-9_-]+)$', output, re.M)
            if status or match is None:
                builds.state = 'Failed'
                raise ValueError('package build failed; package-bearing suites refused')
            self.artifacts.append(match[1])
        status, _ = self.execute(builds, self.command('artifacts', 'compare', *self.artifacts), units=1)
        if status:
            raise ValueError('reproducibility failed; package-bearing suites refused')
        status, _ = self.execute(system, self.command('system', '--artifacts', self.artifacts[0]), events=True)
        if status:
            raise ValueError('installed-system attempt failed; subsequent VM attempts refused')
        if self.control.stopped.is_set():
            return
        for case in ready:
            status, _ = self.execute(graphical, self.command('e2e', '--artifacts', self.artifacts[0],
                                                           '--scenario', case), units=1)
            if status:
                # Never start another VM attempt after an unproven cleanup.
                break
        graphical.state = ('Interrupted' if self.control.stopped.is_set() else
                           'Passed' if graphical.done == graphical.total and not graphical.failures else 'Failed')
        self.check_inputs()


def main(root=None):
    root = root or Path(__file__).resolve().parents[1]
    report = None
    run = None
    status = 1
    failed = False
    with Control().installed() as control:
        try:
            report = Report(root)
            run = Run(root, report, control)
            run.run()
            status = 0 if all(item.state == 'Passed' for item in run.categories) else 1
        except (Exception, KeyboardInterrupt) as error:
            failed = not isinstance(error, KeyboardInterrupt)
            if report is not None:
                try:
                    report.write('\nRunner failure: ' + html.escape(str(error)) + '\n')
                except OSError:
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
                    for item in run.categories:
                        item.stop_timer()
                        if item.state in ('Running', 'Pending'):
                            item.state = 'Interrupted' if status == 130 else 'Blocked'
                    report.snapshot(run.categories)
                    report.write('\n## Final result\n\n' + ('Passed' if status == 0 else
                                 'Interrupted; owned child cleanup finished' if status == 130 else 'Failed') + '\n')
                    summary = '\n'.join(run.dashboard.render(time.monotonic()))
                    report.write('\n<pre>' + html.escape(Dashboard.ANSI.sub('', summary)) + '</pre>\n')
                    run.dashboard.draw(force=True)
                elif report is None:
                    print('\033[31m[✗] Report initialization - 0% (0/1)\033[0m')
            except OSError:
                status = 1
                print('Regression final evidence could not be saved; result is failed.', file=sys.stderr)
            finally:
                if report is not None:
                    report.stream.close()
    if report is not None and (status == 1 or (run is not None and any(
            item.failures or item.state == 'Failed' for item in run.categories))):
        print('\nCopy this prompt into a new Codex session:\n')
        print(f'In {root.resolve()}, investigate and fix the failures in '
              f'{(report.directory / "report.md").resolve()}. '
              'Read the adjacent progress.json for category results and follow '
              'any detailed evidence paths in the report. Fix the root causes, '
              'rerun the relevant checks, and report anything still unresolved.')
    return status
