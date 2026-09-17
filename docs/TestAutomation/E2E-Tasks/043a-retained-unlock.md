# 043a — Qualify retained unlock and return from the lock screen

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **GDM02 retained-child lock entry; DESK08/11**. First scheduled consumer: [E2E-014, case 40](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.
- **042** — DESK05, DESK06, DESK07.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify GDM02(child, destination=lock) for the already observed retained child session. Compose DESK06, two fresh DESK07 proofs, UI19, submission and the declared success/time-denial observation. Bind the normal lock-screen Switch User route separately from rejected GDM; never reuse a GDM secret proof on the lock surface.

## Live VM acceptance

On the VM, enter the child with positive daily time, lock normally and unlock with the intended correct credential. In an independent attempt, prepare positive time in Parent, log Parent out normally and admit the child. Switch User from the child, sign Parent in fresh and change daily time to zero through the UI. Switch to GDM and select that retained child through GDM02; require its lock challenge and explicit time-limit denial after correct authentication. Reach GDM through the observed control. Refuse stale/wrong-recipient proofs and pass credential/cleanup checks before live execution. This configured-zero qualification makes no natural-expiry claim.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_retained_unlock
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
