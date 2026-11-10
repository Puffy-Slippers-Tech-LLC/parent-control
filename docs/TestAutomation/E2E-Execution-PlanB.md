# E2E execution plan B

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanB.md

Run `tools/write-e2e --planb` from this plan's checkout; it defaults to the
current branch. Explicit `--branch NAME` selects another checkout. Apply the same
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md) as Plan A.
This plan owns only its queue, task briefs and next-task pointer. It can run to
completion without executing or completing any unfinished Plan A or
[Plan C](E2E-Execution-PlanC.md) task. Installed pending-approval exits stay here.
Host-only feedback sending, without-logs and Stop obligations belong exclusively
to Plan C, alongside its system, calendar, preset and What's New groups.

Task queue: [Plan B ordered checklist](E2E-Task-QueueB.md).

## Next task

Next task: none.

Apply the [shared Snap acceptance boundary](E2E-Execution-Instructions.md#snap-acceptance-boundary)
to the deferred rows. If an inactive retained run points to a task absent from
the active queue, use the
[reviewed queue-revision reconciliation](E2E-Execution-Instructions.md#resume-after-a-reviewed-queue-revision)
with `--planb` and its exact run ID, previewing with `--check` first.
