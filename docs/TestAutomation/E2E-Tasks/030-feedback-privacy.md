# 030 — Read privacy and preserve a dialog draft

Budget: 25–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/validation (153). Scope: FEED05 and FEED10's dialog-reopen branch.

Required implemented capabilities: FEED01/03 and UI16. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Implement Privacy read/close, then compose FEED10(dialog) from FEED03, UI18(feedback), FEED01 and UI12. Register feedback closure and compare the supplied draft before any new input.

## Live VM acceptance

On installed Parent, enter a synthetic body/reply, read the actual Privacy disclosure, close feedback and reopen it. Independently compare the preserved fields and control states before editing. A wrong window refuses closure. Keep Send untouched.

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
