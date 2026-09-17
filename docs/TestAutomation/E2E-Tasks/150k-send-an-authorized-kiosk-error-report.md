# 150k — Send an authorized kiosk error report

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED11, FEED09 success and FEED14 kiosk**. First scheduled consumer: [E2E-047, case 221](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** Explicit sending authorization and the qualified public cooldown-error entry are both required.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **187k** — REQUEST09 cooldown and FEED15 kiosk; gate in brief.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind one reviewed synthetic Send on the actual kiosk error-report window. Reuse the qualified public cooldown-error prefix and shared submission operation; qualify the surface's confirmation and exit separately from ordinary Parent feedback.

## Live VM acceptance

On the VM, produce the public error, review the report and Privacy, Send once, observe acceptance and keep thanks visible for five seconds. Dismiss normally and require report closure plus GDM. Opening or successful transport alone cannot satisfy exit behavior.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_send_an_authorized_kiosk_error_report
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
