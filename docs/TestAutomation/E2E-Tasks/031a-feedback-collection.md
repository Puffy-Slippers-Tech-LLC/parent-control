# 031a — Observe diagnostic collection from its start

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/diagnostic-export (155). Scope: FEED09's collection trace and terminal state.

Required implemented capabilities: UI22, FEED01/03, FEED09 snapshots and UI18's feedback close binding. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Bind UI22 to collection and Download availability. Arm observation before FEED01 opens feedback, acknowledge readiness, then collect the required public transitions and terminal predicate. Reuse the snapshot observer for the final state.

## Live VM acceptance

On the live VM, open feedback once with observation already armed. Require the declared collection samples and eventual usable Download control. Close normally and qualify an independent entry. A missed required transient fails; do not delay the product or infer it from the final state.

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
