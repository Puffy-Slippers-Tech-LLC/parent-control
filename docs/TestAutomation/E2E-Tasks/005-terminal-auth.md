# 005 — Qualify terminal administrator password input

Estimate: 40–60 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: A real installation challenge, sealed secret delivery, command completion and the affected credential/retained regressions remain one qualification.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **AUTH03; FILE06 package challenge/completion**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **005a** — Product-free graphical start and verified package staging.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind one declared installation command and selected administrator to the real non-echoing terminal challenge. Extend FILE06 to observe that challenge, then implement AUTH03's independent recipient qualification. Reuse applicable safety machinery; a generic Password string is insufficient. Qualification submits the command with FILE02, qualifies the challenge twice, types UI19 once and submits with UI05; LIFE04 is composed only afterward.

Bind the actual qualified terminal owner/window to the declared package command and administrator. Generic password text, echoed input or backend identity alone cannot authorize a secret. Keep wrong-recipient, stale/reused-proof, non-echoing-input, capture and uncertain-delivery regressions; read real command completion independently.

## Live VM acceptance

On the VM, reach a real package-command challenge, refuse wrong-account/wrong-recipient evidence, obtain two fresh intended proofs and type the fixture secret once. Captures and outputs remain secret-safe; completion is independently read.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_terminal_auth
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **005** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
