# 070a — Observe one prompt after an overlay double-click

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-014/child-overlay (38–40). Scope: REQUEST10's overlay binding, reusing qualified UI20, UI22 and overlay authentication.

Use the completed capabilities in the master row, maintained callables and a fresh guarded VM attempt. No previous task document or VM state is an input.
Read only the named [catalogue contracts](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and selected consumer recipe.

## Work

Bind the existing double-click and public trace projections to the overlay's Request control and desktop agent. Do not reimplement the gesture or widen the kiosk qualification.

## Live VM acceptance

On a live child desktop with publicly prepared usable time, double-click Request once. Observe the declared inhibition trace and exactly one prompt/form, then finish through qualified approval and automatic overlay exit. Hidden/disabled controls must refuse the gesture.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_request_duration`, or the full named consumer
if runnable. Reuse the master's guarded qualification route; require all the
stated results and owned cleanup to pass. A diagnostic slice earns no scenario
coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md)
and update the callable, qualified scope and remaining work in
[the catalogue](../E2E-Building-Blocks.md). Delete this task when no longer needed,
replacing its master link with plain text. No new evidence/history document.
