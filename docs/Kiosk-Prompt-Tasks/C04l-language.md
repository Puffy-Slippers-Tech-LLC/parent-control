# C04l — Reuse kiosk language coverage and check its human pause

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C04c.
Estimate: 20–30 min.

Apply the [master contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

Reuse B3's existing Jordan language binding and check its confinement pause from the
[finite recipe](../TestAutomation/E2E-Scenario-Recipes.md#baseline-inputs-and-public-results).
Use the existing `kiosk_language.PLAN` and `check_e2e_kiosk_language` coverage;
review exact candidate/caller/provider evidence before renewing affected scope.
Add only the confinement assertion: at its existing unset-language chooser,
wait 90 real seconds, freshly reacquire the same chooser/session/choice, then
Save and observe the usable form with preserved policy/request choices. Reuse
guarded TIME03. No Riley-specific general language suite or extra locale matrix
belongs here; the later core approval keeps its existing Riley/English binding.

Read `tests/e2e/kiosk_language.py`, `request_flow.py`, `real_interval.py`, shared
`journey_blocks.language_selection`, the corresponding complete `AccessibleUI`
language methods and `tests/integration/graphical_smoke/lib/onpc_request_flow.pm`.
Use shared API-backed language operations and guarded TIME03; do not duplicate
the language mechanics or implement a second pause mechanism.

Reuse the existing selector; no `check_e2e_baseline_language` suite is required.
Extend its shared composition only for the bounded confinement pause if missing.
Run affected host identity, pause, preservation and composition regressions with
finite timeouts before
`tools/run-tests --vm 'onpc-Ubuntu26.04,onpc-Fedora44' integration 'check_e2e_kiosk_language'`
when renewal is needed. Keep the 1800-second attempt,
90-second kiosk observation deadlines and original bounded wait mechanics;
human time is not startup time. Restore changed preferences through public
actions, then complete runner collection and owned baseline cleanup. Record
exact candidate/provider inputs and qualified existing binding in the catalogue;
remaining B3 scopes and C05 acceptance stay pending.
