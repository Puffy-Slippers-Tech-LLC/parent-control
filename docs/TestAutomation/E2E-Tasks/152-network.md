# 152 — Change connectivity through public network controls

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED09 Parent retry/recovery over qualified LIFE06**. First scheduled consumer: [E2E-033, case 157](../E2E-Scenario-Recipes.md#e2e-033).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

**Gate:** Authorized sending and a public connectivity route that preserves the guarded observation channel.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **193** — LIFE06.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse LIFE06's already-qualified public disconnect/reconnect controls. Extend FEED09 only for real retry and recovery during one authorized submission, preserving the normal retry window and safe observation transport. No transport fault injection or forged response.

## Live VM acceptance

In the authorized live retry attempt, disconnect through UI, submit once, observe retry, reconnect before its deadline and observe automatic success for that same submission. If network controls also sever required harness access with no supported route, retain the blocker.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_network
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
