"""Selected categories use the aggregate's execution, evidence and dashboard."""

import runpy
import time

from regression import CATEGORY_NAMES, Category, Run
from regression_inputs import identity as source_identity
from regression_ui import selected_options, serial_options
from test_launcher import pytest_command
from test_commands import CATEGORIES


CLEANUP_SELECTION = '__cleanup_prerequisites__'


def e2e_case_ids(root, args):
    """Resolve the same host-safe selection before build or VM preparation."""
    runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
    plan = runner['preflight'](args, root=root, allow_missing_artifacts=True)
    return tuple(case['case_id'] for case in plan['cases'])


class SelectedRun(Run):
    def __init__(self, root, report, control, selections, *, stop_on_error=False):
        includes_vm = any(kind in ('system', 'e2e', 'integration') for kind, _ in selections)
        super().__init__(root, report, control, host_only=not includes_vm,
                         scope='selected categories only', continue_on_errors=not stop_on_error)
        self.selections = [(kind, args[1:] if args[:1] == ['--unattended'] else args)
                           for kind, args in selections]
        self.report.write('\nSelected categories: ' + ', '.join(kind for kind, _ in selections) + '\n')
        self.categories.clear()
        for kind, args in self.selections:
            name = ('Cleanup safety prerequisites' if kind == CLEANUP_SELECTION else
                    CATEGORY_NAMES.get(kind, CATEGORIES[kind].description))
            if kind in ('fixtures', 'artifacts') and args and args[0] != 'build':
                name = ('Package reproducibility' if args[0] == 'compare' else
                        'Package verification' if kind == 'artifacts' else 'Test fixture verification')
            events = self.events(kind, args)
            item = Category(name, None if events or kind == CLEANUP_SELECTION else 1,
                            host=kind not in ('system', 'e2e', 'integration'),
                            phase='cleanup' if kind == CLEANUP_SELECTION else 'host')
            if kind == 'e2e' and events:
                item.nodeids = e2e_case_ids(root, args)
                item.total = len(item.nodeids)
            self.categories.append(item)
        if includes_vm:
            self.verification_mode = ('selected command options; backing bytes verified by default')

    @staticmethod
    def events(kind, args):
        if kind == 'e2e':
            return not any(arg.startswith('--qualify-') for arg in args)
        return kind in ('unit', 'component', 'ui', 'fixture-runtime', 'coverage', 'system') and (
            '--collect-only' not in args)

    def run_cleanup(self, safety):
        """Collect and run the one shared cleanup gate through its four buckets."""
        status, _ = self.execute(safety, self.command(
            'unit', 'tests/unit/test_*cleanup_safety.py',
            'tests/unit/test_graphical_lease.py', '--collect-only', '-q'),
            collect=True, events=True)
        if self.control.stopped.is_set():
            return 130
        if status or not safety.total:
            raise ValueError('cleanup prerequisite collection failed or collected no tests')
        self.cleanup_jobs(safety)
        return 130 if self.control.stopped.is_set() else 0

    def run_pytest(self, kind, inventory, args):
        if kind == 'ui':
            args, options = selected_options(self.root, args)
        else:
            command = pytest_command(self.root, args, kind)
            options = command[command.index('no:cacheprovider') + 1:command.index('--')]
        if serial_options(options):
            self.report.write(f'\n{kind.upper()} selection: serial execution preserves the requested failure limit.\n')
            inventory.branch = 1
            inventory.launch_order = self.sequence + 1
            status, _ = self.execute(inventory, self.command(kind, *args), events=True)
            return status or int(inventory.state != 'Passed')

        status, _ = self.execute(inventory, self.command(kind, *args, '--collect-only'),
                                 collect=True, events=True)
        if self.control.stopped.is_set():
            return 130
        if status or not inventory.total:
            raise ValueError(f'{kind.upper()} collection failed or collected no tests')
        # The common builder validates the inventory before protected work.
        # Exact IDs retain partial files, parametrization, -k, -m and ignores.
        jobs = self.pytest_jobs(kind, inventory, options, exact=True)
        # Unit selections keep their exact scope and existing prerequisite
        # policy. Only UI adds the mandatory host-integrated cleanup gate.
        if kind == 'ui':
            safety = Category('Cleanup safety prerequisites', phase='cleanup')
            self.categories.insert(self.categories.index(jobs[0].item), safety)
            status = self.run_cleanup(safety)
            if status:
                return status
        if self.control.stopped.is_set():
            return 130
        self.host_jobs(jobs)
        return int(any(job.item.state != 'Passed' for job in jobs))

    def run(self):
        self.inputs = source_identity(self.root)
        self.report.write('\nInitial source inputs SHA-256 (informational): ' + self.inputs + '\n')
        # Categories stay ordered; unit/UI use the same buckets as host.
        # Keep a stable work list while collected inventories expand into jobs.
        host_elapsed = 0.0
        for item, (kind, args) in list(zip(self.categories, self.selections, strict=True)):
            if self.control.stopped.is_set():
                break
            if item.host:
                if self.dashboard.host_started is None:
                    self.dashboard.host_started = time.monotonic()
                host_started = self.dashboard.host_started
                self.dashboard.host_elapsed = None
                item.branch = None if kind in ('unit', 'ui') else 1
                item.launch_order = self.sequence + 1
                started = time.monotonic()
            try:
                # Preserve each category's own fail-fast options. The dashboard
                # must not turn an ordinary assertion into aggregate cancellation.
                if kind == 'artifacts' and not args:
                    # Match all's complete artifact coverage, including comparison.
                    builds = [Category(name, 1) for name in
                              ('Package build A', 'Package build B', 'Package reproducibility')]
                    index = self.categories.index(item)
                    self.categories[index:index + 1] = builds
                    self.host_jobs(self.build_jobs(None, builds))
                    status = int(any(build.state != 'Passed' for build in builds))
                elif kind in ('unit', 'ui'):
                    status = self.run_pytest(kind, item, args)
                elif kind == CLEANUP_SELECTION:
                    status = self.run_cleanup(item)
                else:
                    status, _ = self.execute(item, self.command(kind, *args), events=self.events(kind, args))
                    status = status or int(item.state != 'Passed')
                if status:
                    break
            finally:
                if item.host:
                    host_elapsed += time.monotonic() - started
                    self.dashboard.host_started = host_started
                    self.dashboard.host_elapsed = host_elapsed
