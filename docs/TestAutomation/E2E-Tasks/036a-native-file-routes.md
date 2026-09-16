# 036a — Launch native fixtures from the file manager

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-019/native file-manager routes (74–79). Scope: APP01/02/03's native file-manager bindings.

Required implemented capabilities: FILE04/05, prepared native assets and FLOW03 with grid/command denial qualification. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Bind the file manager's offered launch action to the exact native fixture, including applicable space/version/copy/rename inputs. Observe its usable or blocked result through the existing app projections. Qualify this route independently of desktop-launch availability.

## Live VM acceptance

On the live VM, launch the declared fixture from the file manager and perform one normal action with a visible result. Apply a public Parent block and observe the declared denial/absence. Repeat with the applicable copied/renamed target. No alternative launch route can stand in for this action.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_app_routes`, or the complete named consumer if
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
