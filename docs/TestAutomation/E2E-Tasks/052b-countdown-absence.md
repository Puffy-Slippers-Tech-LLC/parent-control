# 052b — Prove countdown absence on other surfaces

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **TIME01 lock/GDM/other-user absence**. First scheduled consumer: [E2E-011, case 27](../E2E-Scenario-Recipes.md#e2e-011).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — TIME01 child-desktop presence and limits-off absence.
- **043a** — GDM02 retained-child lock entry; DESK08/11.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind complete, fresh absence observations to each positively identified surface.
A disconnected observer, inaccessible tree or wrong surface cannot prove absence.
Keep input routes outside TIME01; it only observes the caller's stated surface.

## Live VM acceptance

In a fresh installed VM attempt, prepare ample positive daily time publicly,
enter the child and read its countdown. Lock normally and require countdown
absence on the identified lock surface. Unlock legitimately and observe the
countdown again. Switch User to GDM and require absence, then enter the named
other user and require absence on that desktop. Qualify independently reached
entry states and wrong-surface refusal. No natural-expiry or tick claim is made.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_countdown_absence
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
