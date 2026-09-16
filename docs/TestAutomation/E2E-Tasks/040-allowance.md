# 040 — Choose ordinary daily allowances

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015/kiosk-approved (49), then time-control journeys. Scope: PARENT05/06 for the undisputed valid values 0, preset 15 and custom 1439.

Required implemented capabilities: UI16, UI17 and PARENT08's saved/control snapshots. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Bind UI16 to the public custom-allowance field before composing PARENT06. Open the picker/custom editor, commit the declared valid value and read it back; PARENT08 separately proves saving. Keep the unresolved maximum-boundary and invalid-input qualification in its own scope so it cannot block ordinary time preparation.

## Live VM acceptance

In installed Parent, select the intended child, enable Screen time limit through UI17 if needed and observe saved, enabled allowance controls through PARENT08. Exercise 0, preset 15 and custom 1439, observe each committed display and saved state, then reopen to read the chosen value before editing. No time/policy file reads or synthetic balances.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_allowance`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
