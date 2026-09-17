# 048b — Qualify approval and rejection on the child overlay

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07**. First scheduled consumer: [E2E-015, case 46](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **021** — FLOW05/06/07 kiosk.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the real desktop authentication agent and selected request to fresh recipient proofs. Reuse sealed single-use authentication and shared form results. Qualify overlay approval, wrong-password and cancellation before composing overlay FLOW05/07; kiosk proofs cannot authorize desktop input.

## Live VM acceptance

In independent live VM attempts, submit a valid overlay request, verify its child/approver/duration/app choice, then approve, reject or cancel. Qualify automatic and approved immediate exit separately; both return to the same child desktop. Rejection/cancellation preserves choices. Wrong/stale recipient proofs refuse before secret input.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_overlay_approval
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
