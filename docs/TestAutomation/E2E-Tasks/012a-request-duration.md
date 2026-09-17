# 012a — Choose kiosk duration and app-access values

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015/kiosk-cancel and kiosk-escape (47, 48).
Scope: REQUEST04(duration), REQUEST05, REQUEST06(soft-apps) and REQUEST08's
numeric/rest-of-day estimates on kiosk.

Required capabilities: kiosk entry/readback and account selection, UI16, UI17,
PARENT08 saved/control snapshots and DESK03. Resolve maintained callables from
the [catalogue](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form).
No previous task document or attempt supplies context.

## Work

Bind UI15 to duration choices, UI16 to custom input and UI17 to the soft-app
toggle before composing the request blocks. Read choices and the public estimate
independently. Reuse shared form observations; mute remains a gated extension.

## Live VM acceptance

In a fresh installed VM attempt, enable the declared child through Parent,
observe saving, then Switch User to enter kiosk and select that child/approver.
Select a preset, a valid fraction and Rest of the day; observe each selection
and estimate with explicit elapsed-time bounds. Change the soft-app choice and
read it back. Invalid custom input shows validation while an otherwise ready
Request remains enabled. Selecting it keeps the same form open and starts no
authentication prompt. Do not change the clock or submit authentication.

Run affected checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_request_exit`, reusing the master's
guarded envelope. All stated results and owned cleanup must pass. A diagnostic
slice earns no scenario coverage.

## Close out

After live acceptance and owned cleanup pass, update the callable, qualified
scope and remaining work in [the catalogue](../E2E-Building-Blocks.md), then
check this task in the [master](../E2E-Execution-Plan.md). If a complete E2E
consumer also passed, run `tools/generate_test_coverage.sh` (the approved launcher
for `tools/generate_test_coverage.py`) before checking off its scenario.
Delete this file when no longer needed and replace its master link with plain
text. No new evidence/history document. Validate changed Markdown as the master
requires.
