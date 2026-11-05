# E2E execution plan B

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanB.md

Run `tools/write-e2e --planb` from this plan's checkout; it defaults to the
current branch. Explicit `--branch NAME` selects another checkout. Apply the same
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md) as Plan A.
This plan owns only its queue, task briefs and next-task pointer. It can run to
completion without executing or completing any unfinished Plan A task.

Task queue: [Plan B ordered checklist](E2E-Task-QueueB.md).

## Next task

Next task: **109 — [Observe Snap command denial and closure](E2E-Tasks/109-snap.md)**.

The pointer always names this queue's first unchecked active row. Close only
that row after its acceptance and owned cleanup. The checked baseline records
are already-delivered capabilities, not pending work in another plan.
