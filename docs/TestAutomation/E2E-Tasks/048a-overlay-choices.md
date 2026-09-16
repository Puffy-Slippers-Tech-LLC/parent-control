# 048a — Choose overlay values and cancel or escape

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015/child-overlay-cancel and child-overlay-escape (44, 45). Scope: overlay bindings of REQUEST04/05/06(soft-apps)/08/11/12 and FLOW04. REQUEST02/03 and kiosk choice/exit implementations already exist.

Use the completed capabilities in the master row, maintained callables and a fresh guarded VM attempt. No previous task document or VM state is an input.
Read only the named [catalogue contracts](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and selected consumer recipe.

## Work

Reuse the shared form operations with explicit overlay selectors and the fixed child. Qualify approver/duration, custom text, soft-app choice, estimate, Cancel and Escape; compose overlay FLOW04 only after those bindings. Mute and authenticated outcomes belong to their later scoped capabilities.

## Live VM acceptance

In separate live attempts with publicly prepared usable child time, record an app activity, open the overlay, change each declared choice and read it back. Cancel or Escape must close the form and return to the same usable activity. Invalid custom text disables Request without a prompt; child selection is refused.

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
