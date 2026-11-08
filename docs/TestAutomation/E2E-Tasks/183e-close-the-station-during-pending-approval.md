# 183e — Close the station during pending approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 kiosk app-close**. First scheduled consumer: [E2E-039, case 175](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** The normal leave/close action must be reachable while the real prompt is pending. If the modal prevents it, leave this binding pending; signals, forced logout and agent Cancel cannot replace it.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021a** — Prepared kiosk request, real prompt and automatic successful approval/return.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.

## Implementation

Compose only the kiosk app-close branch with an already observed real AUTH01
prompt and explicit pre-request choices/balances. Use the shared Application UI
API surface `close` operation on the owned `kiosk-request-window`, preserving
its actual visibility, sensitivity and owned-modal refusals, observe GDM, then
re-enter the station. Cancel on the agent is not this route. Read REQUEST03
through the same API facade and require the old external prompt absent; a later
request must authenticate afresh in case 175.

Extend `kiosk_approved_flow.approved_request`, `onpc_gdm::enter_station` and
compose the existing shared API surface-close operation; FLOW17 has no callable
yet. Reuse the qualified prompt/automatic approval leaves. Neither retained-child
visits nor rejection, Cancel or immediate-success exit is exercised by this
composition.

The API delegates to the toolkit's normal close path; it has no request-specific
busy veto. The form's Cancel is disabled and Escape belongs to the authentication
agent while approval is pending, so neither substitutes for this window-close
route. Preserve the gate until that route independently reaches GDM.

## Live VM acceptance

On the VM, supply usable time and a real pending approval, close the station
through the declared public route, observe GDM and re-enter normally. Qualify
this new pending-prompt close composition, old-prompt absence, cancellation and
usable request return with unchanged choices/balances. Preserve its reachability
gate and focused ownership/refusal qualification. Case 175 owns fresh
authentication and the successful time/access result; do not repeat that
complete recovery here. Cancellation consumes no cooldown; add no fixed wait.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_close_the_station_during_pending_approval
```
