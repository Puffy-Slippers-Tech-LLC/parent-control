# 143 — Qualify distinct retained desktops for one child

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-007/multiple (18, 20) and E2E-021 (112–115). Scope: FLOW14 same-child multi-desktop scope.

Required implemented capabilities: APP04, FLOW08, FLOW09, FLOW14; PARENT16, FLOW03; PARENT17, PARENT18; DESK12/REQUEST02; shared overlay bindings. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

Prerequisite gate: **Supported customer route to distinct same-child desktops or explicit ownership decision**. If unavailable, leave this task unchecked with the concrete blocker/return condition in the master; continue independent work. An applicability check alone does not complete it.

## Work

Demonstrate a supported customer route to distinct same-child desktops and extend FLOW14 only if it exists. Repeated GDM selection may resume one desktop. Otherwise keep the precise obligation blocked for explicit system/customer ownership reconciliation.

## Live VM acceptance

Live UI actions must create two separately identifiable public activities for the same child, revisit both, and preserve an unrelated user's activity. No backend session creation/probes. A failed applicability check is not a completed scenario.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_revocation`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
