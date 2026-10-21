# C04r — Renew shared reminder persistence

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C04o.
Estimate: 20–30 min.

Apply the [master contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

Renew B3's changed complete reminder caller on both rebuilt targets, using
C04o's shared-overlay route and the
[finite reminder recipe](../TestAutomation/E2E-Scenario-Recipes.md#baseline-inputs-and-public-results).
This reuses E2E 312b's existing coverage under the
[reuse map](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).
Check exact evidence applicability first; renew only invalidated scope. Add no
new reminder feature automation. E2E 312 retains deletion/reboot persistence and
311 retains natural delivery/fullscreen behavior; neither blocks this baseline.
Use one Riley record, 90 seconds and literal `Save <work> & games!`, then edit
the same ID to 75 seconds in kiosk, Save/reopen and independently read it in the
overlay. Jordan's defaults and approver switching must not cross child state.
Preserve disabled sound/lightning and absent mute. Editing supplies no natural
notification-delivery claim; local reminder value matrices remain host UI.

Read the complete `tests/e2e/kiosk_reminders.py` plan/comparisons, its shared
`AccessibleUI` methods and
`tests/integration/graphical_smoke/lib/onpc_kiosk_reminders.pm`; reuse their public
API operations. Inspect `tests/integration/check_e2e_kiosk_reminder_binding.py`
and its exact current-candidate/per-VM inputs before invoking the existing
selector. Run affected host reminder and composition checks with finite timeouts,
then
`tools/run-tests --vm 'onpc-Ubuntu26.04,onpc-Fedora44' integration 'check_e2e_kiosk_reminder_binding'`.
Keep each 1800-second attempt and 90-second kiosk / 45-second overlay observations.

Restore feature edits publicly; retain exact candidate, caller, public saved
results and full collection/restoration. Renew affected prerequisite scope if
shared repairs invalidate it. Update the catalogue's exact both-target reminder
scope without completing a broader scenario. Owned cleanup must finish.
