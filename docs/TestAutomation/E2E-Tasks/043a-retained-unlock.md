# 043a — Observe retained-child time denial and return

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add configured-zero retained time denial and the shared command return from the locked session to GDM. Reuse 043c's successful unlock; keep the full public Parent/child setup and explicit-denial assertion.

Reuse the delivered scope of tasks **043c** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **GDM02 retained-child lock entry; DESK08/11**. First scheduled consumer: [E2E-014, case 40](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.
- **042** — DESK05, DESK06, DESK07.
- **043c** — GDM02 retained lock entry and DESK08 successful unlock.

## Implementation

Qualify GDM02(child, destination=lock) for the already observed retained child session. Compose DESK06, two fresh DESK07 proofs, UI19, submission and the declared success/time-denial observation. For DESK11 reuse `session_control.observe` with the bound `return-greeter` action after observing the denial; preserve the locked session without unlocking or locking again. Keep rejected GDM's Escape route separate; never reuse a GDM secret proof on the lock surface.

## Live VM acceptance

On the VM, enter the child with positive daily time, lock normally and unlock with the intended correct credential. In an independent attempt, prepare positive time in Parent, log Parent out normally and admit the child. Switch User from the child, sign Parent in fresh and change daily time to zero through the UI. Switch to GDM and select that retained child through GDM02; require its lock challenge and explicit time-limit denial after correct authentication. From unlocked desktops use DESK03; after the locked-child denial use DESK11's shared greeter-return command and require the same retained session and usable GDM. Only the retained account selection and authentication require graphical input. Refuse stale/wrong-recipient proofs and pass credential/cleanup checks before live execution. This configured-zero qualification makes no natural-expiry claim.

Record the same desktop/activity before locking and compare it after successful unlock; a newly launched window or fresh login cannot satisfy retention. Preserve two fresh same-user lock proofs, single-use delivery, wrong-recipient refusal and no replay after uncertain input.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_retained_unlock
```
