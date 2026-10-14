"""Presentation strategies: workflows supply data, the shared display owns UI."""

from dataclasses import dataclass

from launcher_runtime import task_progress


def unchanged(run, steps, child_steps):
    return steps


def e2e_progress(run, steps, child_steps):
    from write_e2e import task_progress as progress
    return progress(run, steps)


def repair_progress(run, steps, child_steps):
    from launcher_progress import repair_progress as overlay
    return task_progress(run, overlay(run, steps, child_steps=child_steps))


def plan_progress(run, steps, child_steps):
    return task_progress(run, steps)


@dataclass(frozen=True)
class WorkflowView:
    input_mode: str = 'none'
    questions: bool = False
    progress: object = unchanged

    def display(self, stream, run):
        from launcher_display import TaskDisplay
        return TaskDisplay(stream, run=run, input_mode=self.input_mode, log_path=run / 'output')


VIEWS = {
    'write-e2e': WorkflowView('chat', True, e2e_progress),
    'fix-tests': WorkflowView('question', True, repair_progress),
    'run-tests': WorkflowView(),
}


def view_for(label):
    return VIEWS.get(label, WorkflowView())
