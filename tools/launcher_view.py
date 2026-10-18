"""Presentation strategies: workflows supply data, the shared display owns UI."""

from dataclasses import dataclass
from pathlib import Path

from launcher_runtime import task_progress


def unchanged(run, steps, child_steps):
    return steps


def e2e_progress(run, steps, child_steps):
    from write_e2e import task_progress as progress
    return progress(run, steps, remaining=lambda: e2e_totals()[1])


def repair_progress(run, steps, child_steps):
    from launcher_progress import repair_progress as overlay
    return task_progress(run, overlay(run, steps, child_steps=child_steps))


def plan_progress(run, steps, child_steps, *, remaining=None):
    return task_progress(run, steps, remaining=remaining)


def plan_totals(root, path):
    """Read the whole active queue, independent of run limits and pointer edits."""
    from execution_plan import Plan, queue_state
    plan = Plan.load(root, path)
    _, tasks = queue_state(plan.root, plan.path, plan.queue, validate_pointer=False)
    completed = sum(tasks.values())
    return completed, len(tasks) - completed, len(tasks)


def e2e_totals():
    from write_e2e import PLAN
    return plan_totals(Path(__file__).resolve().parent.parent, PLAN)


def whatsnew_totals(root=None):
    """Count complete languages across all records of the latest release."""
    from tools import whats_new_catalogs as catalogs
    root = root if root is not None else Path(__file__).resolve().parent.parent
    release = catalogs.latest(root)
    try:
        remaining = len(catalogs.pending(root, release))
    except SyntaxError as error:
        # The display retains its last valid totals on ValueError while an
        # externally edited catalogue is malformed; keep the observer attached.
        raise ValueError('invalid translation catalogue') from error
    total = len(release.languages)
    return total - remaining, remaining, total


@dataclass(frozen=True)
class WorkflowView:
    input_mode: str = 'none'
    questions: bool = False
    progress: object = unchanged
    totals: object = None

    def display(self, stream, run):
        from launcher_display import TaskDisplay
        return TaskDisplay(stream, run=run, input_mode=self.input_mode,
                           totals=self.totals, log_path=run / 'output')


VIEWS = {
    'write-e2e': WorkflowView('chat', True, e2e_progress, e2e_totals),
    'fix-tests': WorkflowView('question', True, repair_progress),
    'run-tests': WorkflowView(),
    'sync-whatsnew': WorkflowView(totals=whatsnew_totals),
}


def view_for(label):
    return VIEWS.get(label, WorkflowView())
