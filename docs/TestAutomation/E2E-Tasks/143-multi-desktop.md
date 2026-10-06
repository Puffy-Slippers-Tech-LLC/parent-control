# 143 — Qualify distinct retained desktops for one child

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW14 same-child multi-desktop scope**. First scheduled consumer: [E2E-007, case 18](../E2E-Scenario-Recipes.md#e2e-007).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** A supported public route must create and revisit distinct same-child desktops. Resuming one desktop twice cannot qualify it.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **047a** — FLOW09 and FLOW14 distinct-user retention.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **050** — PARENT17, PARENT18.
- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.

## Implementation

Demonstrate a supported customer route to distinct same-child desktops and extend FLOW14 only if it exists. Repeated GDM selection may resume one desktop. Otherwise keep the precise obligation blocked for explicit system/customer ownership reconciliation.

Limit preparation to a route already supported by the declared VM desktop and
the shared session helpers. Do not add seats, nested compositors, display
servers or remote-desktop infrastructure to manufacture this prerequisite.
Record an unavailable route and its return condition; preserve the multi-session
product obligation without substituting two windows on one desktop.

## Live VM acceptance

Live UI actions must create two separately identifiable public activities for the same child, revisit both, and preserve an unrelated user's activity. No backend session creation/probes. A failed applicability check is not a completed scenario.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_multi_desktop
```
