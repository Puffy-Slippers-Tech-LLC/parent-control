# 005a — Start a graphical journey before product installation

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-002/clean (2). Scope: the existing journey envelope's product-free start, verified package asset staging and fresh administrator/terminal entry.

Use the completed capabilities in the master row, maintained callables and a fresh guarded VM attempt. No previous task document or VM state is an input.
Read only the named [catalogue contracts](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and selected consumer recipe.

## Work

Reuse the accepted product-free baseline and FIX04 transfer. Extend the existing declared setup mode so this journey starts without InstalledSetup installing or rebooting the product. Retain input digests, ownership, capture sealing, phase timing and cleanup. Qualify GDM07 and FILE01 on that baseline; no product installation happens in this slice.

## Live VM acceptance

Start a fresh guarded VM attempt from the accepted product-free baseline, authenticate the intended administrator through two fresh recipient proofs, launch Terminal and observe its usable nonsecret input. Verify the setup-mode/ownership refusals in isolated regressions before the live run. Do not use a maintenance reset as a customer step.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_install`, or the full named consumer
if runnable. Reuse the master's guarded qualification route; require all the
stated results and owned cleanup to pass. A diagnostic slice earns no scenario
coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md)
and update the callable, qualified scope and remaining work in
[the catalogue](../E2E-Building-Blocks.md). Delete this task when no longer needed,
replacing its master link with plain text. No new evidence/history document.
