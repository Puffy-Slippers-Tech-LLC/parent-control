# 129 — Play fullscreen to natural lock

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-023/fullscreen (127). Scope: APP05/FLOW10's fullscreen gameplay binding.

Required implemented capabilities: Qualified windowed game assets, APP05/FLOW10 and TIME04. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Extend the real game's mode/level selection and ordinary input observations to fullscreen. Keep countdown reads conditional on public visibility during play. Reuse the bounded natural-expiry loop.

## Live VM acceptance

On the live VM, select fullscreen through the game's normal control, start the declared level and observe actual play/input effects. Play to natural lock and prove normal input belongs to the lock. Do not require a Shell panel or visible countdown while the game hides them.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_game`, or the complete named consumer if
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
