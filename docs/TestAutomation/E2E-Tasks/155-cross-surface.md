# 155 — Compare per-child choices across request surfaces

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-018 (58–61). Scope: FLOW12.

Required implemented capabilities: REQUEST06 soft-app scope; DESK12/REQUEST02; shared overlay bindings; FLOW05, FLOW06, FLOW07. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose each direction's declared exit/entry route and compare REQUEST03/UI12
before any edit. Duration, custom value and soft-app choice are shared per child.
The kiosk's selected child/parent are user-local; each child overlay remembers
its own parent. Do not require parent selection to copy between surfaces.
Retain interactive mute as the separate deferred scope in task 154; the current
forms have no such control. Qualify the second child without hidden state.

## Live VM acceptance

On the VM set distinct choices for both children and compare overlay→kiosk
and kiosk→overlay before selection edits. Compare shared request values and
independently remembered parent selections. If mute is restored in a future
release, qualify its separate per-surface persistence then. Each route finishes
with the destination form open; existing wider inventory obligations still need
explicit reconciliation before a scenario can be marked ready.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_remembered_choices`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
