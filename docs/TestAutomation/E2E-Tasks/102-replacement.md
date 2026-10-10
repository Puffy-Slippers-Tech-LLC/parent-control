# 102 — Compose expiry recovery through kiosk approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW11**. First scheduled consumer: [E2E-009, case 23](../E2E-Scenario-Recipes.md#e2e-009).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **062** — TIME04.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **065a** — FLOW13 grant-only profile and explicit revoke preparation.

## Implementation

Compose DESK11, FLOW06, retained FLOW15 and APP02/04/03 with explicit retained-or-closed expectations. A legitimate unlock must precede activity inspection; the closed branch ends at APP02.

Use grant-only preparation for this expiry/replacement slice; the combined
daily/grant profile is unrelated. Reuse `journey_blocks.desktop_entry` and
`onpc_desktop_session::enter_desktop` for the retained child return, and
`onpc_request_flow::obtain_time` for approval. FLOW11's composition and its
explicit prior-activity comparisons remain planned; do not import a qualifier's
wrong-entry history into cases 23/24.

## Live VM acceptance

Let real child time expire, obtain a replacement through kiosk, unlock normally and observe the declared same usable activity or closed blocked app. Compare only earlier public observations; no claim about unseen events under lock.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_replacement
```
