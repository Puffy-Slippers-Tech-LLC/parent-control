# 037a — Save to a customer-selected location through the chooser

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/diagnostic-export (155). Scope: FILE03's save branch.

Required implemented capabilities: FILE03(open/cancel), FILE07/04, UI16 and FEED09's completed-collection observation. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Extend FILE03 for the real save chooser reached from feedback Download after collection. Bind the directory, filename, Save and closure; reject wrong chooser modes. FEED08 owns opening and reading the resulting artifact.

## Live VM acceptance

On the live VM, observe collection complete, open Download's chooser, choose a synthetic destination and filename, then Save. Independently observe closure and the named file in the file manager. Exercise Cancel from a fresh chooser and prove that no second file was created.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_feedback_local`, or the complete named consumer if
runnable. Reuse the master's guarded qualification route. Require every stated
result and owned cleanup on the live VM; diagnostic success earns no scenario
coverage.

## Close out

After successful cleanup, update the callable, qualified scope and remaining
work in [the catalogue](../E2E-Building-Blocks.md), then check this task in the
[master](../E2E-Execution-Plan.md). If the complete E2E consumer also passed, run
`tools/generate_test_coverage.sh` (the launcher for
`tools/generate_test_coverage.py`) before checking it off. Delete this task when
no longer needed, replacing its master link with plain text. No new evidence or
history document. Follow the master's Markdown checks.
