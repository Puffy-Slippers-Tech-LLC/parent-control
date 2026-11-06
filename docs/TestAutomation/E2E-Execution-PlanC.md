# E2E execution plan C

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanC.md

Run `tools/write-e2e --planc` from this plan's checkout; it defaults to the
current branch. Explicit `--branch NAME` selects another checkout. Apply the
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md).

Task queue: [Plan C ordered checklist](E2E-Task-QueueC.md).

## Next task

Next task: **285 — [E2E-049: flatpak-grid-child-overlay](E2E-Tasks/285-case-243.md)**.

This plan owns its queue, unchanged task briefs and next-task pointer.
It can run independently of all unfinished work in
[Plan A](E2E-Execution-Plan.md) and [Plan B](E2E-Execution-PlanB.md),
sequentially or concurrently in separate branches/checkouts.
Close only this queue's first unchecked active row after acceptance and owned
cleanup. Checked prerequisites are already delivered, with no cross-plan gate.
Apply the shared Snap acceptance boundary; deferred enforcement blocks no work here.
