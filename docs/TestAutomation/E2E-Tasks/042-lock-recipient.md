# 042 — Prove the intended lock-screen recipient

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add DESK07 intended-recipient proofs on the qualified lock challenge. GDM proofs never authorize lock input; retain nonempty, unfocused, stale and wrong-user refusals.

Reuse the delivered scope of tasks **042a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **DESK05, DESK06, DESK07**. First scheduled consumer: [E2E-018, case 58](../E2E-Scenario-Recipes.md#e2e-018).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 direct logout command and independent GDM result.
- **042a** — DESK05/06 explicit Lock, curtain and challenge reveal.

## Implementation

Reuse the [qualified Parent lock surface](../E2E-Building-Blocks.md#parent-lock-surface-qualification) and add a separate public lock-recipient proof. Bind intended identity and empty focused masked field; GDM proofs never authorize lock input. The delivered DESK06 read observes identity and password role, but does not prove an empty field or authorize a secret.

Source routes: `desktop_session.LOCK_PLAN` / `SUPPLIED_LOCK_PLAN`,
`journey_blocks.lock_challenge`, `onpc_desktop_session::lock` / `observe_lock`,
`AccessibleUI.shell_lock_window` / `shell_lock_snapshot` / `lock_surface`, and
the lock-result decoder in `ui_observations.py`. Reuse the actual unlock-window
identity beneath permitted empty ancestors; preserve ownership, protected
traversal, session rechecks and refusal before input. Host checks live in
`test_e2e_desktop_session.py` and `test_desktop_session_cleanup_safety.py`.
The delivered qualification selector is `check_e2e_lock_surface`; the recipient
selector below remains unimplemented.

Resolve this actual Shell lock surface separately from GDM; explicit locking uses shared DESK05 (Super+L or the session lock API). Observe that ordinary desktop input is blocked while locked. Reject ambiguous or wrong-owner challenges and qualify the guarded reveal/input/readback on the pinned VM.

## Live VM acceptance

On the VM, lock an observed usable fixture desktop, reveal its challenge through one declared normal key, and qualify the correct recipient. Refuse wrong-user/nonempty/stale proofs; this explicit Lock earns no natural-expiry credit.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_lock_recipient
```
