# E2E execution plan B

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanB.md

Run `tools/write-e2e --planb` from this plan's checkout; it defaults to the
current branch. Explicit `--branch NAME` selects another checkout. Apply the same
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md) as Plan A.
This plan owns only its queue, task briefs and next-task pointer. It can run to
completion without executing or completing any unfinished Plan A or
[Plan C](E2E-Execution-PlanC.md) task. Installed pending-approval exits, cooldown
reports and diagnostic-collection work stay here. Host-only feedback sending,
without-logs and Stop obligations belong exclusively to Plan C, alongside its
system, calendar, preset and What's New groups.

Task queue: [Plan B ordered checklist](E2E-Task-QueueB.md).

The installed report journeys retain their own acceptance under the
[feedback allocation](UI-and-E2E-Coverage.md#feedback-sending-allocation).
They do not wait for Plan C's component sending checks, and those checks do not
wait for this plan's installed cooldown or collection-failure triggers.

## Next task

Next task: **183e — [Close the station during pending approval](E2E-Tasks/183e-close-the-station-during-pending-approval.md)**.

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
