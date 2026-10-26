"""Presentation strategies: workflows supply data, the shared display owns UI."""

from dataclasses import dataclass
from pathlib import Path

from launcher_runtime import task_progress
from launcher_progress import plan_progress


def unchanged(run, steps, child_steps):
    return steps


def repair_progress(run, steps, child_steps):
    from launcher_progress import repair_progress as overlay
    return task_progress(run, overlay(run, steps, child_steps=child_steps))


def plan_totals(root, path):
    """Read the whole active queue, independent of run limits and pointer edits."""
    from execution_plan import Plan, queue_state
    plan = Plan.load(root, path)
    _, tasks = queue_state(plan.root, plan.path, plan.queue, validate_pointer=False)
    completed = sum(tasks.values())
    return completed, len(tasks) - completed, len(tasks)


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
    overview_current: bool = False
    cancel_on_ctrl_c: bool = False
    plan: tuple | None = None
    execution_tabs: bool = False

    def display(self, stream, run):
        from launcher_display import TaskDisplay
        return TaskDisplay(stream, run=run, input_mode=self.input_mode,
                           totals=self.totals, overview_current=self.overview_current,
                           cancel_on_ctrl_c=self.cancel_on_ctrl_c,
                           execution_tabs=self.execution_tabs,
                           log_path=run / 'output')


class ExecutionPlanView(WorkflowView):
    """All plan launchers inherit the same panes, progress and reload wiring."""

    def __init__(self, root, path):
        root = Path(root)
        super().__init__('chat', True,
            lambda run, steps, child_steps: plan_progress(run, steps, child_steps,
                remaining=lambda: plan_totals(root, path)[1]),
            lambda: plan_totals(root, path), plan=(str(root), path))


def plan_view(root, path):
    return ExecutionPlanView(root, path)


VIEWS = {
    'fix-tests': WorkflowView('chat', True, repair_progress, overview_current=True,
                              cancel_on_ctrl_c=True, execution_tabs=True),
    'run-tests': WorkflowView(),
    'sync-whatsnew': WorkflowView(totals=whatsnew_totals),
}


def view_for(label):
    return VIEWS.get(label, WorkflowView())
