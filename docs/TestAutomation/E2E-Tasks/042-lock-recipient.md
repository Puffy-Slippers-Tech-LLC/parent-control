# 042 — Prove the intended lock-screen recipient

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add DESK07 intended-recipient proofs on the qualified lock challenge. GDM proofs never authorize lock input; retain nonempty, unfocused, stale and wrong-user refusals.

Tasks **042a** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **DESK05, DESK06, DESK07**. First scheduled consumer: [E2E-014, case 40](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 direct logout command and independent GDM result.
- **042a** — DESK05/06 explicit Lock, curtain and challenge reveal.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement normal explicit Lock, curtain/challenge observation and a separate public lock-recipient proof. Bind intended identity and empty focused masked field; GDM proofs never authorize lock input.

Resolve this actual Shell lock surface separately from GDM; explicit locking uses shared DESK05 (Super+L or the session lock API). Observe that ordinary desktop input is blocked while locked. Reject ambiguous or wrong-owner challenges and qualify the guarded reveal/input/readback on the pinned VM.

## Live VM acceptance

On the VM, lock an observed usable fixture desktop, reveal its challenge through one declared normal key, and qualify the correct recipient. Refuse wrong-user/nonempty/stale proofs; this explicit Lock earns no natural-expiry credit.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_lock_recipient
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
