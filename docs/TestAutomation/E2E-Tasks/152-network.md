# 152 — Observe feedback retry and recovery

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED09 Parent retry/recovery over qualified LIFE06**. First scheduled consumer: [E2E-033, case 157](../E2E-Scenario-Recipes.md#e2e-033).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

**Gate:** Authorization for the reviewed submission and the qualified LIFE06
VM Internet-isolation helper.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **193** — LIFE06.

## Implementation

Reuse LIFE06's qualified enter-offline/restore-online operations unchanged.
Extend FEED09 only for real retry and recovery during one authorized submission,
preserving the normal retry window and observation transport. Network setup is
already owned by 193a/193; do not choose another guest connection, networking
backend or management path here. No transport fault injection or forged response.

## Live VM acceptance

In the authorized live retry attempt, remove Internet access through LIFE06,
submit once, observe retry, restore Internet access before its deadline and
observe automatic success for that same submission. Run both supporting
operations from the existing test-control channel while keeping the current
app/session surface. If the qualified helper loses control or observation,
report that infrastructure failure; do not improvise another network route.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_network
```
