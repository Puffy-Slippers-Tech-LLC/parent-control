# 012 — Select kiosk accounts and read availability

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-017/disabled-child (57), then empty-account cases (54, 55). Scope: REQUEST04's kiosk child/approver selection and REQUEST08's unavailable-state readback.

Required implemented capabilities: REQUEST01/03, UI17, PARENT08's saved/control snapshots and DESK03. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Bind UI15 to the offered child/approver selectors, then compose REQUEST04 with independent REQUEST03 readback. Read each exact eligible choice set before selection. Bind REQUEST08's unavailable explanation and distinguish disabled selectors from empty lists. Duration editing, numeric estimates and toggles remain pending.

## Live VM acceptance

In one fresh live attempt, disable the target in Parent, observe saved state, Switch User and enter the station. Read its disabled-child explanation, unavailable Request and absence of an authentication prompt. In another attempt, enable the target publicly and observe saved state before station entry; inspect offered lists, select the intended eligible child/approver and independently read the selection. Do not activate disabled controls. Empty-account fixture profiles are qualified by their own consumer.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_kiosk_accounts`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
