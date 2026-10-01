# 187o — Review an overlay cooldown report

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add review-report entry, Privacy and normal report-close destination. Reuse 187a's actual cooldown trigger and decline result; preserve independent attempts for both outcomes.

Tasks **187a** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **REQUEST09 cooldown and FEED15 overlay**. First scheduled consumer: [E2E-039, case 176](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** The normal overlay reopen-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.
- **030** — FEED05; FEED10 dialog persistence.
- **187a** — REQUEST09 overlay cooldown and FEED15 decline branch; gate in brief.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify the public reopen/Request route within the actual five-second cooldown, then report-review/decline bindings and their overlay destinations. Reuse selected-parent approval; never extend product timing.

## Live VM acceptance

On the VM, approve once, reopen and Request before five seconds from success, and read the actual too-soon result. In independent attempts review and decline reporting, checking form/report destinations and original balance before any new approval.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_read_overlay_cooldown_errors_and_report_choices
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
