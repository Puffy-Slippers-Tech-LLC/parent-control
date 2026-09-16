# 024a — Prepare multiple and ineligible-approver profiles

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-017/multiple and ineligible-parent (53, 56). Scope: FIX03's two finite eligible-choice profiles. Kiosk entry/choices and real approval-prompt cancellation must already be qualified.

Use the completed capabilities in the master row, maintained callables and a fresh guarded VM attempt. No previous task document or VM state is an input.
Read only the named [catalogue contracts](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and selected consumer recipe.

## Work

Extend the existing account-fixture route for exactly these profiles and preserve the request station and ownership checks. Register every declared eligible child/approver binding; ineligible identities must stay absent from the public choices. Keep policy and authentication outcomes under normal customer actions.

## Live VM acceptance

In separate live attempts, inspect each profile's exact offered children/approvers. For each declared valid target, select it, reach the correctly bound real authentication prompt and cancel normally. Verify ineligible approvers are excluded. Pass fixture ownership/cleanup regressions before these runs.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_kiosk_choices`, or the full named consumer
if runnable. Reuse the master's guarded qualification route; require all the
stated results and owned cleanup to pass. A diagnostic slice earns no scenario
coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md)
and update the callable, qualified scope and remaining work in
[the catalogue](../E2E-Building-Blocks.md). Delete this task when no longer needed,
replacing its master link with plain text. No new evidence/history document.
