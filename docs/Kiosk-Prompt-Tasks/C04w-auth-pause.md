# C04w — Qualify the parent decision pause

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C04l.
Estimate: 20–30 min.

Apply the [master contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

Check that confinement preserves B3's genuine MATE approval during a human pause from the
[finite recipe](../TestAutomation/E2E-Scenario-Recipes.md#baseline-inputs-and-public-results).
Use Riley/Jamie, English, zero daily/grant, Custom `1.25` Minutes / 75 seconds,
soft included. Observe the intended open authentication context, wait 45 real
seconds, reacquire the same request/challenge and two fresh recipient proofs,
authenticate once, observe explicit success and automatic GDM return. Independently
read the same child's genuine grant with real elapsed-time/precision bounds.
Reuse C04f's existing Riley/English request binding; C04l's separate Jordan
chooser check supplies no Riley language qualification or open authentication wait.
This is a bounded confinement session-lifetime delta, not new general approval
or delayed-arithmetic feature coverage. E2E-048 owns its distinct arithmetic and
second-request histories under the [reuse map](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).

Read `tests/e2e/kiosk_approval.py`, `request_flow.py`, `request_composition.py`,
`real_interval.py`, the shared `AccessibleUI.mate_prompt`/recipient operations
and `tests/integration/graphical_smoke/lib/onpc_request_flow.pm`. Reuse C04f's
shared approval and grant comparison and guarded TIME03. Never let proof acquired
before the pause authorize secret input; no password enters the product API.

Register a qualifier (planned `check_e2e_baseline_auth_pause`, unimplemented).
Run host wait, stale-challenge, input-refusal, grant and composition checks with
finite timeouts before
`tools/run-tests --vm 'onpc-Ubuntu26.04,onpc-Fedora44' integration 'check_e2e_baseline_auth_pause'`
once registered. Preserve 1800-second attempts, 90-second kiosk observations,
recipient freshness and original estimate bounds; human time is separate from
startup. Keep exact candidate/MATE/locale/keyboard and fresh proof evidence.
Finish collection and owned baseline restoration, record only this qualification,
and renew affected earlier scope if shared code changes it. C05 remains pending.
