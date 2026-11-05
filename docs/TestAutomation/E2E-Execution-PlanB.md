# E2E execution plan B

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanB.md

Run `tools/write-e2e --planb`. Apply the same
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md) as Plan A.
This plan owns only its queue, task briefs and next-task pointer. It can run to
completion without executing or completing any unfinished Plan A task.

Task queue: [Plan B ordered checklist](E2E-Task-QueueB.md).

## Next task

Next task: **109p — [Prepare the declared Snap fixtures in the baseline](E2E-Tasks/109p-snap-fixtures.md)**.

The pointer always names this queue's first unchecked active row. Close only
that row after its acceptance and owned cleanup. The checked baseline records
are already-delivered capabilities, not pending work in another plan.
