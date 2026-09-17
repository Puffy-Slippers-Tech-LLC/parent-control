"""Selected categories use the aggregate's execution, evidence and dashboard."""

import runpy
import time

from regression import CATEGORY_NAMES, Category, Run
from regression_inputs import identity as source_identity


def e2e_case_ids(root, args):
    """Resolve the same host-safe selection before build or VM preparation."""
    runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
    plan = runner['preflight'](args, root=root, allow_missing_artifacts=True)
    return tuple(case['case_id'] for case in plan['cases'])


class SelectedRun(Run):
    def __init__(self, root, report, control, selections):
        includes_vm = any(kind in ('system', 'e2e', 'integration') for kind, _ in selections)
        super().__init__(root, report, control, host_only=not includes_vm,
                         scope='selected categories only', continue_on_errors=True)
        self.selections = [(kind, args[1:] if args[:1] == ['--unattended'] else args)
                           for kind, args in selections]
        self.report.write('\nSelected categories: ' + ', '.join(kind for kind, _ in selections) + '\n')
        self.categories.clear()
        for kind, args in self.selections:
            name = CATEGORY_NAMES[kind]
            if kind in ('fixtures', 'artifacts') and args and args[0] != 'build':
                name = ('Package reproducibility' if args[0] == 'compare' else
                        'Package verification' if kind == 'artifacts' else 'Test fixture verification')
            events = self.events(kind, args)
            item = Category(name, None if events else 1,
                            host=kind not in ('system', 'e2e', 'integration'))
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

    def run(self):
        self.inputs = source_identity(self.root)
        self.report.write('\nSource inputs SHA-256: ' + self.inputs + '\n')
        # Keep arbitrary selections serial: their fixtures have not necessarily
        # been qualified for overlap. The branch records the actual launches.
        host_elapsed = 0.0
        for item, (kind, args) in zip(self.categories, self.selections):
            if self.control.stopped.is_set():
                break
            if item.host:
                if self.dashboard.host_started is None:
                    self.dashboard.host_started = time.monotonic()
                self.dashboard.host_elapsed = None
                item.branch = 1
                item.launch_order = self.sequence + 1
                started = time.monotonic()
            try:
                # Preserve each category's own fail-fast options. The dashboard
                # must not turn an ordinary assertion into aggregate cancellation.
                status, _ = self.execute(item, self.command(kind, *args), events=self.events(kind, args))
                if status or item.state != 'Passed':
                    break
            finally:
                if item.host:
                    host_elapsed += time.monotonic() - started
                    self.dashboard.host_elapsed = host_elapsed
