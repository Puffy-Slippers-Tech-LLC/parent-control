# 007 — Renderer crash and kiosk reentry

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 007a.
Estimate: 30–60 minutes.
Session exception: abnormal exit, usable-GDM return and fresh entry retain one
causal session history per installed target.

## Purpose and route

Follow the [master](../Reliability-Plan.md),
[renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs)
and [crash diagnostics](../SystemDesign/Logging-and-Feedback.md#kiosk-startup-crash-diagnostics).
The lesson from `4e08dcdb` is that a pre-form crash can kill the app and session;
neither a startup callback nor a surviving reporter is a recovery oracle.
Read complete platform/confinement qualifier and owned-process cleanup helpers.
007a supplies the affected permission's host guard; the GPU-specific mapping
proof in 007b is independent of this abnormal-exit recovery result.

Planned selector (unimplemented): `test_kiosk_renderer_role_recovery`, area
`enforcement`. Use the existing qualifier's supported renderer/provenance
mechanics and recheck candidate applicability. Software rendering is sufficient
for this exit/reentry history; it grants no GPU mapping credit to 007b.

## Work sequence and expected results

1. Start a fresh usable confined kiosk and record the exact app process,
   renderer/security provenance and waiting-session census.
2. In the engineering fixture, terminate only that identity-recorded app.
   Preserve the real exit/signal and session shutdown result before reentry.
   This tests abnormal-exit recovery; it does not recreate or prove a GPU denial.
3. Independently observe bounded return to usable GDM, then fresh usable confined
   entry on the same supported binding. Do not disable security or repair the
   result with unrecorded process signals or manual session changes.
4. Compare owned process/unit/mount state and complete cleanup. Full causal
   diagnostic-export survival belongs to 010, which reuses these fault mechanics.

## Validation and close-out

Run affected host diagnostic-provenance and ownership/cleanup checks, then the
complete abnormal-exit/reentry history on both targets. Retain first failure,
native exit, usable recovery and cleanup receipts. Repair demonstrated lifecycle
defects, build after product edits and update exact coverage in existing owners.
Close only 007. 007b's mapping proof must remain distinct from this induced exit.
