# 070 — Double-click kiosk Request and observe one prompt

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **UI20; REQUEST10 kiosk binding**. First scheduled consumer: [E2E-014, case 41](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **020** — AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits.
- **016a** — UI22.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement one deliberate native double-click gesture first. Surround it with UI22 prompt/form-count and Request availability traces; REQUEST10 also independently checks final counts. No input repair or internal exactly-once claim.

## Live VM acceptance

On the live kiosk, double-click an enabled Request once and observe one prompt plus the declared inhibition/count trace, then finish through the qualified agent. Disabled/hidden controls never receive the gesture. Overlay binding remains a separate slice.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_double_request
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
