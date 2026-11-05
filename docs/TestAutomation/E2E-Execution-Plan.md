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

Next task: **103 — [Check returning after time runs out with blocked apps closed](E2E-Tasks/103-case-23.md)**.

The pointer always names this queue's first unchecked active row. Close only
that row after its acceptance and owned cleanup. Completed work stays complete;
no task in the other plan is a prerequisite for this plan's remaining work.
