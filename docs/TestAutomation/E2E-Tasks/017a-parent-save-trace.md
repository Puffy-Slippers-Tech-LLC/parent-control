# 017a — Observe saving while a Parent control changes

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-005 (7–12). Scope: PARENT08 transition mode. Its snapshot mode, UI17 and UI22 must already be qualified.

Use the completed capabilities in the master row, maintained callables and a fresh guarded VM attempt. No previous task document or VM state is an input.
Read only the named [catalogue contracts](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and selected consumer recipe.

## Work

Bind UI22 to Parent's saving and conflicting-control states. Arm observation and acknowledge readiness before one caller-owned Screen time limit change; collect the trace and terminal saved result without delaying the product.

## Live VM acceptance

On installed Parent, change Screen time limit once with the observer already active. Require the specified saving/control-inhibition samples and final saved state. A missed transient is unproven. Reuse the ordinary snapshot result; a final switch value cannot substitute for the trace.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_allowance`, or the full named consumer
if runnable. Reuse the master's guarded qualification route; require all the
stated results and owned cleanup to pass. A diagnostic slice earns no scenario
coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md)
and update the callable, qualified scope and remaining work in
[the catalogue](../E2E-Building-Blocks.md). Delete this task when no longer needed,
replacing its master link with plain text. No new evidence/history document.
