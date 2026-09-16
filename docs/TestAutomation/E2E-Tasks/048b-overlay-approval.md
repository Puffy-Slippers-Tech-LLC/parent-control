# 048b — Qualify approval and rejection on the child overlay

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015/child-overlay-approved (46), then E2E-013 overlay rejection. Scope: overlay REQUEST09, AUTH01/02, REQUEST11(success/rejection), REQUEST12(automatic), FLOW05/07. Kiosk authentication and overlay choices/exits must already be qualified.

Use the completed capabilities in the master row, maintained callables and a fresh guarded VM attempt. No previous task document or VM state is an input.
Read only the named [catalogue contracts](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and selected consumer recipe.

## Work

Bind the real desktop authentication agent and selected request to fresh recipient proofs. Reuse sealed single-use authentication and shared form results. Qualify overlay approval, wrong-password and cancellation before composing overlay FLOW05/07; kiosk proofs cannot authorize desktop input.

## Live VM acceptance

In independent live VM attempts, submit a valid overlay request, verify the exact child/approver/duration/app choice, then approve, reject or cancel. Observe the corresponding form result; success returns automatically to the child desktop, while rejection/cancellation preserves choices. Wrong/stale recipient proofs refuse before secret input.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_request_exit`, or the full named consumer
if runnable. Reuse the master's guarded qualification route; require all the
stated results and owned cleanup to pass. A diagnostic slice earns no scenario
coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md)
and update the callable, qualified scope and remaining work in
[the catalogue](../E2E-Building-Blocks.md). Delete this task when no longer needed,
replacing its master link with plain text. No new evidence/history document.
