# 043a — Observe retained-child time denial and return

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add configured-zero retained time denial on two distinct authentication surfaces:
retained-session GDM reauthentication and the child's actual lock screen. Reuse
043c's successful unlock; keep the full public Parent/child setup, explicit
time-denial assertions and the route-specific return to usable GDM.

Reuse the delivered scope of tasks **043c** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **GDM02 retained-child reauthentication denial; DESK08/11 actual lock-screen denial and return**. First scheduled consumer: [E2E-018, case 58](../E2E-Scenario-Recipes.md#e2e-018).
Read the named [block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043c** — GDM02 retained-child GDM reauthentication and DESK08 direct child lock-screen successful unlock, with preserved original activity.

## Implementation

Reuse the separate successful routes in the
[delivered qualification](../E2E-Building-Blocks.md#successful-child-unlock-and-retained-gdm-reauthentication-qualification).
GDM account selection opens GDM reauthentication; it does not directly activate
the child's lock screen. The retained GDM branch uses
`onpc_gdm::sign_in_challenge`, two fresh GDM03 proofs, GDM05/UI19 and one
submission, then requires the specific product time-limit denial without
desktop access. Use `rejected_gdm_return` /
`onpc_gdm::return_from_time_denial` for its guarded return to the account list.

Qualify independent valid entry to the same child's actual lock screen through a
maintained public session operation, without authenticating, unlocking or
relocking it. Missing supported entry is a blocker. Observe DESK06, obtain two
fresh same-user DESK07 proofs, deliver sealed single-use UI19 input and submit
once; require the lock surface's specific time-limit denial without desktop
access. For DESK11 reuse `session_control.observe` with the bound
`return-greeter` action after preserving that denial observation. Keep the same
locked session and independently require usable GDM. GDM proofs never authorize
lock-screen input; a GDM denial cannot satisfy the actual lock-screen assertion.

## Live VM acceptance

Use independent restored attempts for the two surfaces. In each, prepare
positive time in Parent, log Parent out normally and admit the child. Switch
User from the child, sign Parent in fresh and change daily time to zero with no
grant through the public UI. From unlocked desktops use DESK03.

For retained GDM reauthentication, select the retained child through GDM02,
observe the actual GDM challenge and require its explicit time-limit denial
after correct authentication. Return through the qualified rejected-GDM route
and independently observe the usable account list. For actual lock-screen
denial, independently enter the preserved child's locked session, observe the
actual lock challenge and require its explicit time-limit denial after correct
authentication. Return through DESK11's bound shared greeter command and
independently observe usable GDM and the same retained session. Do not replace
either assertion with the other surface's result. Authentication remains real
graphical input. Refuse stale/wrong-recipient proofs and pass credential/cleanup
checks before live execution. This configured-zero qualification makes no
natural-expiry claim.

Reuse 043c's unchanged exact successful-unlock/activity qualification, rerunning
affected branches only when necessary. Its evidence supplies no saved VM state
for this new denial/return composition. Preserve retained-session identity,
independent valid entry, two fresh recipient proofs for the actual surface,
single-use delivery, wrong-recipient refusal and no replay after uncertain input.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_retained_unlock
```
