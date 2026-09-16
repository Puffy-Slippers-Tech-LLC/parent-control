# 005 — Qualify terminal administrator password input

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-002 (2). Scope: AUTH03 and FILE06's real administrator challenge/completion projections.

Required implemented capabilities: product-free graphical entry and verified package staging; FILE01/02; UI19/GDM05 challenge context. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Bind one declared installation command and selected administrator to the real non-echoing terminal challenge. Extend FILE06 to observe that challenge, then implement AUTH03's independent recipient qualification. Reuse applicable safety machinery; a generic Password string is insufficient. Qualification submits the command with FILE02, qualifies the challenge twice, types UI19 once and submits with UI05; LIFE04 is composed only afterward.

## Live VM acceptance

On the VM, reach a real package-command challenge, refuse wrong-account/wrong-recipient evidence, obtain two fresh intended proofs and type the fixture secret once. Captures and outputs remain secret-safe; completion is independently read.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_install`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
