# 052a — Measure countdown ticks and guarded intervals

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-011/daily-only (27), then natural-expiry journeys. Scope: TIME03 followed by TIME02.

Required implemented capabilities: TIME01 and FLOW13's daily-only profile. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Implement the bounded monotonic TIME03 wait with guard/deadline checkpoints first. Compose TIME02 from fresh TIME01 samples and measured intervals, with explicit formatting and rounding bounds. Elapsed time alone is never an enforcement result.

## Live VM acceptance

On the live VM, publicly establish short daily-only time, enter the child and observe minute ticks and final-second changes over real measured intervals. Require the declared sample order and tolerances. No guest clock adjustment or usage probe is allowed.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_countdown`, or the complete named consumer if
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
