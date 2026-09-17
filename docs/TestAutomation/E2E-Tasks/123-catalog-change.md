# 123 — Keep an unsaved match draft across a fixture update

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-020/update (110). Scope: LIFE04's fixture-update profile, PARENT15 retained-editor save and catalogue refresh through LIFE01.

Required implemented capabilities: FLOW03, LIFE01 Parent restart, LIFE04 installation/authentication and DESK10 for Parent/editor and Terminal. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Bind a verified old/new fixture package pair and extend LIFE04(update). Leave the real Edit Match Rule draft open while the package changes, then foreground that same editor and Save normally.

## Live VM acceptance

On the VM, type a nondefault unsaved match draft, update the fixture through a separate visible administrator terminal, return to the same editor and Save. Close/reopen Parent through LIFE01, reselect the child and independently read the refreshed public app row and expected rule; save-time target resolution does not refresh existing rows. Preserve owned cleanup; no autosave pause or saved-preference probe.

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
