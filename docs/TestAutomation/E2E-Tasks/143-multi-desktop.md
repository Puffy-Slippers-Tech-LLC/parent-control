# 143 — Qualify distinct retained desktops for one child

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW14 same-child multi-desktop scope**. First scheduled consumer: [E2E-007, case 18](../E2E-Scenario-Recipes.md#e2e-007).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** A supported public route must create and revisit distinct same-child desktops. Resuming one desktop twice cannot qualify it.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **047a** — FLOW09 and FLOW14 distinct-user retention.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **050** — PARENT17, PARENT18.
- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Demonstrate a supported customer route to distinct same-child desktops and extend FLOW14 only if it exists. Repeated GDM selection may resume one desktop. Otherwise keep the precise obligation blocked for explicit system/customer ownership reconciliation.

## Live VM acceptance

Live UI actions must create two separately identifiable public activities for the same child, revisit both, and preserve an unrelated user's activity. No backend session creation/probes. A failed applicability check is not a completed scenario.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_multi_desktop
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
