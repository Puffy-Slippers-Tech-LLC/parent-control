# 154 — Deferred qualification of a restored mute choice

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-018 (58–61) and E2E-022 (116–125). Scope: REQUEST06 mute scope.

Required implemented capabilities: DESK12/REQUEST02; shared overlay bindings. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

Prerequisite gate: **A future release restores the public mute feature**.
The current specification documents silent request forms with no mute control
(ONPC-CORE-REQUEST-018). This task retains the earlier interactive-mute
obligation as deferred work; it is not a description of a current user feature.
Keep its checkbox and affected inventory variants pending. Observing absence
does not earn an interactive-mute pass.

## Work

Gate REQUEST06(mute) on the actual customer feature. Current
REQUEST_MEDIA_ENABLED=False hides it. Do not enable a test switch or silently
remove assertions. Supported duration/custom/soft-app persistence and user-local
parent selection can be reviewed independently; the existing inventory's wider
mute obligation remains unfulfilled until explicitly reconciled.

## Live VM acceptance

When the feature is publicly available, on live overlay and kiosk independently read initial mute, set a value and observe surface-specific behavior. Complete this implementation only after both routes qualify. An explicit decision to retire scope must instead mark that scope as excluded in the master and catalogue, preserve its obligation/owner, and never produce a passing checkbox or variant.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_remembered_choices`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
