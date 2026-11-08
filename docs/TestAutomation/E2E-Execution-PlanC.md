# E2E execution plan C

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanC.md

Run `tools/write-e2e --planc` from this plan's checkout; it defaults to the
current branch. Explicit `--branch NAME` selects another checkout. Apply the
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md).

Task queue: [Plan C ordered checklist](E2E-Task-QueueC.md).

The same-child/two-desktop scenarios, former tasks **143–149**, have been
removed from this plan. [Two desktops](../Two_Desktops.md) records the open
question and scenario descriptions only; it is not a task queue or prerequisite.
Do not implement those scenarios through this plan or block later work on them.
Former task **171** is likewise removed. [Unlock desktop](../Unlock_Desktop.md)
is an open investigation question, not an execution plan or prerequisite.
Existing ordinary sign-in/unlock and exhaustion coverage remains scheduled.

## Next task

Next task: **172j — [Require confirmed secure lock completion](E2E-Tasks/172j-lock-completion.md)**.

This plan owns its queue, remaining task briefs and next-task pointer.
It can run independently of all unfinished work in
[Plan A](E2E-Execution-Plan.md) and [Plan B](E2E-Execution-PlanB.md),
sequentially or concurrently in separate branches/checkouts.
Close only this queue's first unchecked active row after acceptance and owned
cleanup. Checked prerequisites are already delivered, with no cross-plan gate.
Apply the shared Snap acceptance boundary; deferred enforcement blocks no work here.
