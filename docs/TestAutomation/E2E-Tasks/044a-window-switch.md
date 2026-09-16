# 044a — Return to an already-open window on one desktop

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/diagnostic-export (155). Scope: DESK10 on an already authenticated Parent desktop; FILE01 and FEED01/03 supply visible windows.

Use the completed capabilities in the master row, maintained callables and a fresh guarded VM attempt. No previous task document or VM state is an input.
Read only the named [catalogue contracts](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and selected consumer recipe.

## Work

Implement bounded normal app-switcher navigation to an explicitly identified existing window. Independently observe its active state. Bind Parent, Terminal and feedback first; the diagnostic-viewer binding is qualified by FEED08. Do not log out, unlock, relaunch a window or restore fields.

## Live VM acceptance

Open Parent feedback with a synthetic draft and Terminal on the same live desktop. Switch to Terminal and back normally, verify the intended active window each time and compare the unchanged draft before editing. An absent target must fail without relaunching it. No retained-user or child-login work is needed.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_feedback_local`, or the full named consumer
if runnable. Reuse the master's guarded qualification route; require all the
stated results and owned cleanup to pass. A diagnostic slice earns no scenario
coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md)
and update the callable, qualified scope and remaining work in
[the catalogue](../E2E-Building-Blocks.md). Delete this task when no longer needed,
replacing its master link with plain text. No new evidence/history document.
