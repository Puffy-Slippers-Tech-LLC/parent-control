# 030a — Observe draft reset after Parent exits

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/draft-reopen (152). Scope: FEED10's app-exit branch.

Required implemented capabilities: FEED10(dialog), FEED01/03, UI16 and LIFE01 for Parent. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Extend FEED10 to close feedback, exit and relaunch Parent through LIFE01, then reopen feedback and compare against an explicit empty-draft expectation. Read before restoring any field.

## Live VM acceptance

Enter nonempty synthetic body/reply values on the live VM, close feedback, exit/relaunch Parent and reopen feedback. Require the declared reset fields and empty attachment list. Keep Send untouched; dialog-only reopening remains the separate preservation branch.

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
