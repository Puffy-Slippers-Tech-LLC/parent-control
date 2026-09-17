# 040a — Qualify daily-allowance boundaries

Budget: 25–45 minutes for focused review and normal verification; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-005 (7–12). Scope: PARENT06's finite boundary/invalid-input cases
and PARENT08's invalid-allowance snapshots. Ordinary allowance editing, UI17
and saved-state observations must already be qualified.

Read the [finite-value contract](../E2E-Building-Blocks.md#finite-values-and-applicability-constraints),
[screen-time model](../../SystemDesign/Screen-Time.md#screen-time-model), E2E-005
in the [inventory](../../../tests/e2e/scenarios.json), and the public
[allowance editor](../../../parent/oh_no_parent_control_parent/main.py).
Use a fresh installed VM attempt and maintained callables, not an earlier task
document or retained VM state.

## Work

The [functional specification](../../Specification.md#screen-time-setup-and-enforcement)
documents the current Parent UI range, 0–1439, separately from the broker and
saved-data range, 0–1440. The source-authoritative documentation review resolves
that description; it does not establish live acceptance or change executable
checks. Keep 1440 in the finite customer set as an invalid custom editor value.
Test the broker's accepted 1440 boundary separately at its technical interface.

Bind 0, preset 15 and custom 1439 to acceptance; bind custom 1440, -1, 1441,
empty and `abc` to visible rejection with the prior saved allowance preserved.
Retain the complete finite set. Existing executable checks are unchanged; if
one conflicts with this documented UI/API distinction, preserve and report
the mismatch under the repository failure contract before changing it.

## Live VM acceptance

On installed Parent, enable the target and observe saved, usable allowance
controls. Exercise the full finite set through the real editor. Every accepted
value must save and survive reopening; every rejected value must expose the
expected validation and preserve the last accepted value when reopened.
Do not read preferences or seed balances. Report a behavioral mismatch with
expected/actual results and preserve the runner failure before changing any
expectation.

Run affected checks and
`tools/run-tests integration check_e2e_allowance` through the master's planned
fixed qualification route. Require the resolved boundary assertions and owned
cleanup to pass; contract review alone cannot complete the task.

## Close out

After live acceptance and owned cleanup pass, update the callable, qualified
scope and remaining work in [the catalogue](../E2E-Building-Blocks.md), then
check this task in the [master](../E2E-Execution-Plan.md). If a complete E2E
consumer also passed, run `tools/generate_test_coverage.sh` (the approved launcher
for `tools/generate_test_coverage.py`) before checking off its scenario.
Delete this file when no longer needed and replace its master link with plain
text. No new evidence/history document. Validate changed Markdown as the master
requires.
