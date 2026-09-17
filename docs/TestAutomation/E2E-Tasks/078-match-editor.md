# 078 — Edit, save, cancel or reset one match rule

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-006; E2E-020. Scope: PARENT13, PARENT15.

Required implemented capabilities: PARENT12, PARENT10, PARENT11; PARENT08. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Open/read the real draft editor and apply explicit responses; compare Cancel with the supplied old rule, invalid Save with validation, and Reset with its actual UI commit behavior. Qualify retained-editor saves after app removal and the subsequent catalogue refresh later with E2E-020.

## Live VM acceptance

In installed Parent, enter a synthetic valid rule, cancel and observe the old row, then save and observe the new rule. Exercise invalid Save and Reset. Empty or unrelated precise input keeps the editor open. A broker-rejected wildcard closes the editor and reports a failed save; dismiss its report and compare the restored rule. The documented precise-override restoration limitation also applies during this recovery, so record that branch if the fixture has a suggested wildcard; it is not evidence of a correct precise-rule round trip. Reset saves the detected default immediately. Use no saved-preference read.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_match_editor`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
