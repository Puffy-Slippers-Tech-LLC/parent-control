# 019 — Qualify the real selected-parent approval prompt

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-017 valid selection and request approval. Scope: REQUEST09, AUTH01.

Required implemented capabilities: REQUEST04, REQUEST05, REQUEST06, REQUEST08; UI19/GDM05 challenge context; JourneyPlan repeated stages/assertions. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement Request submission once, then AUTH01 over the actual system agent: selected parent, child, duration, app choice and sole empty masked focused field. Add owned kiosk-agent routing without treating agent metadata as an approval result.

## Live VM acceptance

On the VM, prepare a valid kiosk request, submit once and inspect the real challenge. Refuse wrong parent/request and nonempty/stale field proofs; an otherwise ready form rejects an invalid custom duration with validation and no prompt when Request is selected, while unavailable forms keep Request disabled. Finish through the normal agent Cancel control.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_kiosk_choices`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
