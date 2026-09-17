# 019 — Qualify the real selected-parent approval prompt

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **REQUEST09, AUTH01 kiosk**. First scheduled consumer: [E2E-016, case 50](../E2E-Scenario-Recipes.md#e2e-016).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **012a** — REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk.
- **004** — UI19/GDM05 distinct single-use authentication challenges.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement Request submission once, then AUTH01 over the actual system agent: selected parent, child, duration, app choice and sole empty masked focused field. Add owned kiosk-agent routing without treating agent metadata as an approval result.

## Live VM acceptance

On the VM, prepare a valid kiosk request, submit once and inspect the real challenge. Refuse wrong parent/request and nonempty/stale field proofs; an otherwise ready form rejects an invalid custom duration with validation and no prompt when Request is selected, while unavailable forms keep Request disabled. Finish through the normal agent Cancel control.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_auth_prompt
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
