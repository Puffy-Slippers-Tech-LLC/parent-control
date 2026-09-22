# 150k — Send an authorized kiosk error report

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FEED11, FEED09 success and FEED14 kiosk**. First scheduled consumer: [E2E-047, case 221](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** Explicit sending authorization and the qualified public cooldown-error entry are both required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **187k** — REQUEST09 cooldown and FEED15 kiosk; gate in brief.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind one reviewed synthetic Send on the actual kiosk error-report window. Reuse the qualified public cooldown-error prefix and shared submission operation; qualify the surface's confirmation and exit separately from ordinary Parent feedback.

## Live VM acceptance

On the VM, produce the public error, review the report and Privacy, Send once, observe acceptance and keep thanks visible for five seconds. Dismiss normally and require report closure plus GDM. Opening or successful transport alone cannot satisfy exit behavior.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_send_an_authorized_kiosk_error_report
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
Check **150k** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
