# 150 — Submit one authorized synthetic report and read success

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-032/success (156). Scope: FEED11, FEED14.

Required implemented capabilities: FEED06, FEED07, FEED12, FEED13; FEED09; FEED05, FEED10. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

Prerequisite gate: **Explicit sending authorization covering this qualification and the later case-156 run, plus a dedicated test-recipient profile**. If unavailable, leave this task unchecked with the concrete blocker/return condition in the master; continue independent work. An applicability check alone does not complete it.

## Work

Prepare the concrete synthetic report, attachments and dedicated recipient for review before any Send. Reuse existing authorization only if it covers these contents and the planned qualification/scenario submissions. Compose reviewed FEED03/Privacy evidence, one Send, FEED09 sending/success and FEED14 dismissal. Qualify these FEED09 projections only here.

## Live VM acceptance

With authorized service configuration, submit once on the VM, observe the actual app response, dismiss confirmation and reopen feedback to observe clearing. No provider receipt probe or automatic repeat send. Planning is not sending authorization.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_delivery`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
