"""Plan projection metadata and counters consumed by ONPC: Watch."""

def plan_totals(root, path, *, queue=None):
    """Read the whole active queue, independent of run limits and pointer edits."""
    from execution_plan import Plan, queue_state
    plan = Plan(root, path, queue) if queue is not None else Plan.load(root, path)
    _, tasks = queue_state(plan.root, plan.path, plan.queue, validate_pointer=False)
    completed = sum(tasks.values())
    return completed, len(tasks) - completed, len(tasks)


def observed_plan_totals(root, run, reader):
    """Resolve plan counters from shared presentation metadata, including old runs."""
    try:
        projection = reader.read(run / 'plan-view.json')
    except FileNotFoundError:
        if run.parent.name == 'write-e2e':
            return plan_totals(root, 'docs/TestAutomation/E2E-Execution-Plan.md',
                               queue='docs/TestAutomation/E2E-Task-Queue.md')
        elif run.parent.parent.name == 'plans':
            # Older ordinary-plan runs did not publish their master path.
            # Their retained queue still supplies totals until reattachment.
            tasks = reader.read(run / 'checkpoint.json')['queue_before']
            completed = sum(tasks.values())
            return completed, len(tasks) - completed, len(tasks)
        else:
            return None
    return plan_totals(root, projection['plan'], queue=projection.get('queue'))


def publish_plan_view(run, path, *, queue=None):
    from detached_launcher import atomic
    atomic(run / 'plan-view.json', {'plan': path, 'queue': queue})
