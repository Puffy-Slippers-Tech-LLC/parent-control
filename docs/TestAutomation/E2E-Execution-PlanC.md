# E2E execution plan C

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-PlanC.md

Run `tools/write-e2e --planc` from this plan's checkout; it defaults to the
current branch. Explicit `--branch NAME` selects another checkout. Apply the
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md).

Task queue: [Plan C ordered checklist](E2E-Task-QueueC.md).

This queue also owns the remaining feedback UI obligations and remaining-time
reminder qualification/scenario. Each moved group retains its original briefs,
prerequisite order, scope and acceptance. Checked baseline rows reuse already
delivered capabilities; no unfinished work in another plan is required.

Routine feedback sending rows are explicit **UI obligation** tasks using the
existing network-free component previews. Apply the
[feedback allocation](UI-and-E2E-Coverage.md#feedback-sending-allocation): no
inbox, recipient configuration, real-send permission or VM qualification gates
those rows. Explicit UI markers select host-only launcher handling, and allocation
metadata names the existing UI owners. Real sending is separate optional
integration work and must not become a queue prerequisite.

The same-child/two-desktop scenarios, former tasks **143–149**, have been
removed from this plan. [Two desktops](../Two_Desktops.md) records the open
question and scenario descriptions only; it is not a task queue or prerequisite.
Do not implement those scenarios through this plan or block later work on them.
Former task **171** is likewise removed. [Unlock desktop](../Unlock_Desktop.md)
is an open investigation question, not an execution plan or prerequisite.
Existing ordinary sign-in/unlock and exhaustion coverage remains scheduled.

## Next task

Next task: **190o — [Stop an overlay report](E2E-Tasks/190o-confirm-stopping-a-sending-overlay-report.md)**.

The developer authorized pre-test guest clock preparation for task **239** and all
remaining calendar tasks (**240, 242, 245**), under the
[calendar preparation contract](E2E-Scenario-Recipes.md#natural-calendar-windows).
This replaces older scheduling-only gates in their briefs: prepare the declared
eligible date/window before parent or child input, then let time advance normally.
Preserve each case's full bound, natural boundary and public-result assertions.
Future cases still own their fixture extension, implementation and acceptance.

This plan owns its queue, remaining task briefs and next-task pointer.
It can run independently of all unfinished work in
[Plan A](E2E-Execution-Plan.md) and [Plan B](E2E-Execution-PlanB.md),
sequentially or concurrently in separate branches/checkouts.
Close only this queue's first unchecked active row after acceptance and owned
cleanup. Checked prerequisites are already delivered, with no cross-plan gate.
Apply the shared Snap acceptance boundary; deferred enforcement blocks no work here.
