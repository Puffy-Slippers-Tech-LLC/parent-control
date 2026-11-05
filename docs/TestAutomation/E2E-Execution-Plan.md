# E2E execution plan

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

Run `tools/write-e2e` (without `--planb`). Apply the
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md).
This plan owns only its queue, task briefs and next-task pointer.
[Plan B](E2E-Execution-PlanB.md) runs independently through the same launcher.

Task queue: [Plan A ordered checklist](E2E-Task-Queue.md).

## Next task

Next task: **159 — [E2E-022: app-restart-expired](E2E-Tasks/159-case-117.md)**.

The pointer always names this queue's first unchecked active row. Close only
that row after its acceptance and owned cleanup. Completed work stays complete;
no task in the other plan is a prerequisite for this plan's remaining work.
