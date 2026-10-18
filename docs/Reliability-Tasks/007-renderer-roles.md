# 007 — Native VM renderer roles and crash recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 30–60 minutes.

## Session boundary

Deliver abnormal app shutdown, bounded usable-GDM return and fresh kiosk entry.
007a supplies the host role matrix; 007b cumulatively supplies all three functional
renderers and native isolation, including 007c's notification provider, with
actual capability limits. Session exception: crash,
shutdown and reentry must remain one owned installed history on each target.

## Purpose and route

Required tasks: 006, 007a, 007b.
Read the [master](../Reliability-Plan.md),
[renderer role contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
[crash diagnostics](../SystemDesign/Logging-and-Feedback.md#kiosk-startup-crash-diagnostics),
policy generation and the existing platform/confinement qualifier call chains.

Planned selector (unimplemented): `test_kiosk_renderer_role_recovery`, area
`enforcement`, reusing the native platform and waiting-session census helpers.
Use 007b's qualified available VM paths, rechecking candidate applicability.

## Finite history and expected results

Start a fresh usable confined kiosk using the qualified renderer binding and
record actual renderer/security/role provenance. In an owned engineering branch,
terminate only the exact recorded app process to exercise abnormal session
shutdown. Require bounded
return to usable GDM, preserved crash outcome and a fresh successful kiosk
entry; no broad process-name signal or global security disable is allowed.
Task 010 owns full diagnostic-export survival.

Together with 007a/007b, cumulative acceptance retains the native renderer paths
available in both VMs, all three functional roles, enforcing isolation and
crash/reentry. Software rendering is a valid VM binding when those results pass;
record absent GPU-mapping coverage explicitly instead of requiring a new virtual
GPU or passthrough capability. A missing capability needed for these required
VM results remains a blocker under the master's bounded supporting-work route.
Never label an unexercised mapping passing or change product permissions solely
to make qualification possible.

## Work sequence

1. Recheck cumulative renderer qualification against the actual candidate/path;
   start a fresh usable kiosk and record the exact app identity and role census.
2. Induce abnormal shutdown only for that recorded app and preserve the native
   crash outcome before reentry.
3. Independently observe bounded return to usable GDM, then freshly enter a
   usable confined kiosk on the same qualified binding.
4. Compare the role/resource census and complete owned cleanup. Full crash
   evidence export remains the separate result in 010.

## Validation and close-out

Run affected host policy, diagnostic-provenance and ownership/cleanup tests.
Qualify crash/reentry on both targets; retain renderer/security/version
provenance and the strict role census. Fix root causes
with the narrow required permission or lifecycle handling, build as required
and update exact qualified scope in the existing owners.
