# 037 — Select multiple files or cancel through a real chooser

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/attachments (154). Scope: FILE03's open/cancel branches.

Required implemented capabilities: FILE07/04 and prepared synthetic files, plus FEED01/03. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Bind feedback Add files to its real chooser. Compose navigation, exact multi-selection, Open and independent closure. Preserve modifier selection so choosing a second file cannot silently drop the first. Cancel performs no addition.

## Live VM acceptance

In installed feedback, select two synthetic files and observe the exact set before Open. Require chooser closure, then independently compare the displayed attachment list. Reopen and Cancel with a different candidate selected; the prior attachment list must stay unchanged.

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
