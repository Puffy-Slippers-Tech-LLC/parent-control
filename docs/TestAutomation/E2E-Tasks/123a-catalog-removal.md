# 123a — Save a match draft after fixture removal

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-020/remove (111). Scope: LIFE04's fixture remove/reinstall profiles and PARENT15's absent-row branch.

Required implemented capabilities: FLOW03, LIFE04 installation/authentication and DESK10 for Parent/editor and Terminal. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Bind verified fixture removal/reinstallation commands. Extend PARENT15 to save the real open draft when its app row is absent, with an explicit deferred-row result. Do not require a row that cannot exist until reinstall.

## Live VM acceptance

On the live VM, leave a nondefault match draft open, remove the fixture in a separate administrator terminal, return and Save. Observe exclusion from the public catalogue. Reinstall through the visible terminal, return to Parent and independently read the retained rule before editing it.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_catalog_change`, or the complete named consumer if
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
