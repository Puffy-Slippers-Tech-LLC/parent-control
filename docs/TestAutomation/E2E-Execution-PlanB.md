# E2E execution plan B

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanB.md

Run `tools/write-e2e --planb` from this plan's checkout; it defaults to the
current branch. Explicit `--branch NAME` selects another checkout. Apply the same
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md) as Plan A.
This plan owns only its queue, task briefs and next-task pointer. It can run to
completion without executing or completing any unfinished Plan A or
[Plan C](E2E-Execution-PlanC.md) task. Later system, calendar,
preset and What's New groups now belong exclusively to Plan C; current task
135a and its lifecycle consumers stay here.

Task queue: [Plan B ordered checklist](E2E-Task-QueueB.md).

Routine feedback sending rows are explicit **UI obligation** tasks using the
existing network-free component previews. Apply the
[feedback allocation](UI-and-E2E-Coverage.md#feedback-sending-allocation): no
inbox, recipient configuration, real-send permission or VM qualification gates
those rows. Explicit UI markers select host-only launcher handling, and allocation
metadata names the existing UI owners. Real sending is separate optional
integration work and must not become a queue prerequisite.

## Next task

Next task: **150 — [Check feedback success with the fake sender](E2E-Tasks/150-feedback-send.md)**.

Snap denial/closure work is deferred by developer decision, not passed. Apply the
[shared Snap acceptance boundary](E2E-Execution-Instructions.md#snap-acceptance-boundary);
it is not a prerequisite for active work or another product-choice gate.

For an inactive retained run still pointing at historical task 109, use the
[reviewed queue-revision reconciliation](E2E-Execution-Instructions.md#resume-after-a-reviewed-queue-revision)
with `--planb` and its exact run ID, previewing `--check` first. Preserve pending
cleanup/close-out transactions; do not rerun the failed Snap acceptance or erase
the checkpoint to advance. This is queue recovery, not a Snap product decision.

The pointer always names this queue's first unchecked active row. Close only
that row after its acceptance and owned cleanup. The checked baseline records
are already-delivered capabilities, not pending work in another plan.
