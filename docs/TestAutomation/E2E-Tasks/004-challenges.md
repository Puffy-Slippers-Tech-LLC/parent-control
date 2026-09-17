# 004 — Allow distinct single-use authentication challenges

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **UI19/GDM05 distinct single-use authentication challenges**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **003** — DESK02, DESK03, DESK04.
- **004a** — JourneyPlan repeated invocation IDs and assertion placement.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Replace the one-authentication-per-worker limitation with explicit, single-use challenge context for UI19/GDM05. Use the qualified repeated-stage interface. Preserve wrong-recipient refusal, two fresh intended-recipient checks, sealed capture, fixed secret input and a terminal failure latch; never clear the latch to authenticate again.

## Live VM acceptance

In one guarded VM attempt, authenticate the Parent, log out through the normal UI, then authenticate again with a new challenge. Reject stale/reused proofs in safety regressions; no reset of the existing failure latch. Run affected credential safety and ready cases 1, 3, 4, 5, 151.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_challenges
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
