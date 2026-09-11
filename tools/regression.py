"""Run established suites, with a quiet dashboard and durable streaming report."""

from dataclasses import dataclass, asdict
import codecs
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

from regression_events import PREFIX
from regression_process import Control
import test_launcher as host


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


class Dashboard:
    def __init__(self, categories, stream=None):
        self.categories = categories
        self.stream = stream or sys.stdout
        self.lines = 0
        self.last = 0.0

    def draw(self, *, force=False):
        if not force and time.monotonic() - self.last < 0.2:
            return
        self.last = time.monotonic()
        lines = []
        for item in self.categories:
            total = '?' if item.total is None else str(item.total)
            percent = '?' if item.total is None else str(int(100 * item.done / max(item.total, 1)))
            label = {'Passed': '✓', 'Failed': '✗', 'Interrupted': '✗',
                     'Blocked': '✗'}.get(item.state, item.state)
            color = {'Passed': '32', 'Failed': '31', 'Interrupted': '31',
                     'Blocked': '31', 'Running': '97;1', 'Pending': '90'}[item.state]
            lines.append(f'\033[{color}m[{label}] {item.name} - {percent}% '
                         f'({item.done} / {total})\033[0m')
        done = sum(item.done for item in self.categories)
        known = all(item.total is not None for item in self.categories)
        total = sum(item.total or 0 for item in self.categories)
        percent = str(int(100 * done / max(total, 1))) if known else '?'
        color = '31' if any(c.state in ('Failed', 'Interrupted', 'Blocked') for c in self.categories) else (
            '32' if all(c.state == 'Passed' for c in self.categories) else '97;1')
        lines.append(f'\033[{color}mOverall - {percent}% ({done} / {total if known else "?"})\033[0m')
        prefix = f'\033[{self.lines}F' if self.lines and self.stream.isatty() else ''
        self.stream.write(prefix + '\n'.join('\033[2K' + line for line in lines) + '\n')
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


class Run:
    def __init__(self, root, report, control):
        self.root, self.report, self.control = root, report, control
        self.categories = [Category('Discovery and prerequisites', 1)]
        self.dashboard = Dashboard(self.categories)
        self.artifacts = []

    def command(self, category, *args):
        if category == 'ui':
            return [str(self.root / 'tools/run-ui-tests'), '--unattended', *args]
        return [str(self.root / 'tools/run-tests'), category, '--unattended', *args]

    def execute(self, item, command, *, collect=False, events=False, units=None):
        if self.control.stopped.is_set():
            item.state = 'Interrupted'
            return 130, ''
        item.state = 'Running'
        self.report.write('\n## ' + item.name + (' — collection' if collect else '') + '\n\n<pre>\n')
        self.dashboard.draw(force=True)
        pending = b''
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        captured = []
        finished = set()

        def output(data):
            nonlocal pending
            # Persist every received byte before parsing or repainting. Split
            # lines are retained too, even if Ctrl+C arrives mid-traceback.
            self.report.write(html.escape(decoder.decode(data)))
            pending += data
            while b'\n' in pending:
                raw, pending = pending.split(b'\n', 1)
                line = raw.decode('utf-8', errors='replace')
                if collect or line.startswith('run-tests: output='):
                    captured.append(line)
                if events and line.startswith(PREFIX):
                    event = json.loads(line[len(PREFIX):])
                    if event['kind'] == 'collection':
                        if item.total is not None and item.total != event['total']:
                            raise ValueError('test inventory changed after collection')
                        item.total = event['total']
                    elif event['kind'] == 'finished' and not collect:
                        finished.add(event['nodeid'])
                        item.done = len(finished)
                    elif event['kind'] == 'failure':
                        item.failures += 1
                    self.report.snapshot(self.categories)
                    self.dashboard.draw()
        status = self.control.run(command, cwd=self.root, env=host.environment(self.root),
                                  output=output, cooperative=True)
        self.report.write(html.escape(decoder.decode(b'', final=True)))
        self.report.write('\n</pre>\n\nExit status: ' + str(status) + '\n')
        if collect:
            item.state = 'Pending' if status == 0 else 'Failed'
        else:
            if not events and not self.control.stopped.is_set():
                item.done = min(item.total or 1, item.done + units) if units is not None else item.total or 1
            item.state = ('Interrupted' if self.control.stopped.is_set() else
                          'Failed' if status or item.failures else
                          'Passed' if item.done == item.total else 'Running' if units else 'Failed')
        self.report.snapshot(self.categories)
        self.dashboard.draw(force=True)
        return status, '\n'.join(captured)

    def run(self):
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

        status, _ = self.execute(safety, self.command('unit', *selections[0][1], '-q'), events=True)
        if status or safety.state != 'Passed':
            raise ValueError('cleanup safety prerequisites failed; protected suites refused')
        for (_, kind, args), item in zip(suites, suite_items):
            self.execute(item, self.command(kind, *args, '-q'), events=True)
            if self.control.stopped.is_set():
                return
        for (_, kind), item in zip(fixed, fixed_items):
            self.execute(item, self.command(kind))
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
            graphical.failures += int(status != 0)
            if status:
                # Never start another VM attempt after an unproven cleanup.
                break
        graphical.state = ('Interrupted' if self.control.stopped.is_set() else
                           'Passed' if graphical.done == graphical.total and not graphical.failures else 'Failed')


def main(root=None):
    root = root or Path(__file__).resolve().parents[1]
    report = None
    run = None
    status = 1
    with Control().installed() as control:
        try:
            report = Report(root)
            run = Run(root, report, control)
            run.run()
            status = 0 if all(item.state == 'Passed' for item in run.categories) else 1
        except (Exception, KeyboardInterrupt) as error:
            if report is not None:
                report.write('\nRunner failure: ' + html.escape(str(error)) + '\n')
            if run is not None:
                for item in run.categories:
                    if item.state == 'Running':
                        item.state = 'Failed'
        finally:
            if control.stopped.is_set():
                status = 130
            if run is not None:
                for item in run.categories:
                    if item.state in ('Running', 'Pending'):
                        item.state = 'Interrupted' if status == 130 else 'Blocked'
                report.snapshot(run.categories)
                report.write('\n## Final result\n\n' + ('Passed' if status == 0 else
                             'Interrupted; owned child cleanup finished' if status == 130 else 'Failed') + '\n')
                run.dashboard.draw(force=True)
            elif report is None:
                print('\033[31m[✗] Report initialization - 0% (0 / 1)\033[0m')
            if report is not None:
                report.stream.close()
    return status
