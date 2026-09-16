# 129a — Reach an overlay request from fullscreen gameplay

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-024/fullscreen (129, 131). Scope: DESK12's fullscreen reveal and the existing REQUEST02/12 return path.

Required implemented capabilities: Fullscreen game play, APP04 and overlay choices/cancel/escape. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Qualify the game's supported normal Shell reveal sequence, then reuse REQUEST02 to open one overlay. Bind the route back to the same game via DESK10 and compare its earlier activity. A missing panel route blocks these request consumers without blocking fullscreen expiry.

## Live VM acceptance

On the live VM, play fullscreen, capture activity, expose the panel normally and open the request overlay. Read the intended fixed child, cancel through the qualified form control and return to the same usable game activity. Repeat from an independent fullscreen entry and reject wrong-window proofs.

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
