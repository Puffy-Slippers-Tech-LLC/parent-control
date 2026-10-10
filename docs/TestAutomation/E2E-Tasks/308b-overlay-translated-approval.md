# 308b — Qualify translated overlay approval and return

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **048d** — Real Shell approval, explicit overlay success and automatic return.
- **300i** — Installed Riley overlay language selection.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify Riley's product language Hebrew with its desktop/native Shell agent
remaining English. Publicly prepare the same finite Riley/Jamie/75-second,
soft-app-included request as the existing approval binding. Require the correct
translated product request context, fresh Shell recipient proofs and sealed
single-use password input. Independently read Hebrew success and return to the
same usable child activity with unchanged synthetic content and the expected
public time increment. Repeat independent entry and retain existing refusals.

The shared `kiosk_approval_success` currently accepts English overlay results
only. Extend the product-message/result branch without relabeling or replacing
the native agent. Chinese MATE qualification cannot authorize Shell input.
Preserve the ordinary approval calculation and real time/policy semantics.

## Shared implementation

Reuse `request_flow.overlay_authentication`, the shared Shell approval worker
and `AccessibleUI.kiosk_approval_success` in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py).
Use public request/result observations, not broker preference or grant probes.

## Implementation entry

Planned selector: `check_e2e_overlay_translated_approval`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_overlay_translated_approval`.
Reuse unchanged fixed English approval/return qualification. Qualify only the
affected Hebrew request/success branches and their Shell secret/recipient guards;
do not replay the predecessor's complete authentication history.
