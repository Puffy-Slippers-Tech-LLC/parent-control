# E2E execution plan

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

Run `tools/write-e2e` (without `--planb` or `--planc`). Apply the
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md).
This plan owns only its queue, task briefs and next-task pointer.
[Plan B](E2E-Execution-PlanB.md) and [Plan C](E2E-Execution-PlanC.md)
run independently through the same launcher.

Task queue: [Plan A ordered checklist](E2E-Task-Queue.md).

## Next task

Next task: **107 — [E2E-025: included-new-login](E2E-Tasks/107-case-134.md)**.

The pointer always names this queue's first unchecked active row. Close only
that row after its acceptance and owned cleanup. Completed work stays complete;
no task in another plan is a prerequisite for this plan's remaining work.

Apply the [shared Snap acceptance boundary](E2E-Execution-Instructions.md#snap-acceptance-boundary).
Snap remediation is separate work and cannot block this plan or add Snap
enforcement assertions to its declared native/Flatpak/game cases.
