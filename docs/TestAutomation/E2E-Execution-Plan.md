# E2E execution plan

Start each new session with:

> Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md

Run `tools/write-e2e` (without `--planb` or `--planc`). Apply the
[shared execution instructions](E2E-Execution-Instructions.md) and
[execution contracts](E2E-Execution-Contracts.md).
This plan owns only its queue, task briefs and next-task pointer.
[Plan B](E2E-Execution-PlanB.md) and [Plan C](E2E-Execution-PlanC.md)
run independently through the same launcher.

The remaining active work is the Lunar/Minecraft launcher group. Remaining-time
reminder qualification and its complete scenario belong to
[Plan C](E2E-Execution-PlanC.md); its fullscreen prerequisite is already delivered
and does not depend on this plan's launcher work.

The developer has finished manual Lunar/Minecraft installation and profile setup.
All remaining tasks use those supplied inputs after ordinary restore under the
[read-only profile contract](E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate).
Report any actual launcher/profile setup gap before implementing setup changes;
do not automate installation, downloads, integration or profile reconstruction.
Task 295 qualifies read-only verification. Later tasks retain their parent/child
launch, approval, denial, tray, reboot and autostart outcomes.

Task queue: [Plan A ordered checklist](E2E-Task-Queue.md).

## Next task

Next task: **296d — [Close Lunar to its tray and restore it](E2E-Tasks/296d-lunar-tray.md)**.

The pointer always names this queue's first unchecked active row. Close only
that row after its acceptance and owned cleanup. Completed work stays complete;
no task in another plan is a prerequisite for this plan's remaining work.

Apply the [shared Snap acceptance boundary](E2E-Execution-Instructions.md#snap-acceptance-boundary).
Snap remediation is separate work and cannot block this plan or add Snap
enforcement assertions to its declared native/Flatpak/game cases.
