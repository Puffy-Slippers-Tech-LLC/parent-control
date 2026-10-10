# 050a — Read a revocation warning and Cancel

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **PARENT17/18 revocation target, warning and Cancel**. Named consumer: task **050** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021a** — Fixed kiosk FLOW05/06 approval and automatic GDM return.
- **044b** — Return to the retained Parent desktop/window for public balance readback.

## Implementation

Obtain a real kiosk grant, open the owned revocation warning, verify target and use Cancel. Reuse public settings/time observers; never seed grant state.

Add the missing guarded PARENT17/18 operation beside `AccessibleUI.revoke_disabled`,
using `parent-revoke-button`, the owned `parent-revoke-dialog` and its public
target/response IDs. Reuse `reach_time_explanation` after Cancel; qualify only
unchanged balances/settings and target safety. The exact existing 75-second,
soft-included kiosk approval is sufficient preparation; rejection, immediate exit
and child-desktop retention are outside this slice.

## Live VM acceptance

With a real grant, capture public settings/balance, open and Cancel the warning and independently compare unchanged values within elapsed-time bounds. Wrong child/confirmation refuses.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_revoke_cancel
```
