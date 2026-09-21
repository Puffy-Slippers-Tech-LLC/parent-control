# 011 — Enter and read the request station

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **REQUEST01, REQUEST03**. First scheduled consumer: [E2E-017, case 57](../E2E-Scenario-Recipes.md#e2e-017).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Use the existing repository-owned source interfaces and guarded attempt
envelope. Their host qualification does not qualify the external GDM entry path
or the installed station surface.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

Blockers, in required order:

1. The current GDM adapter refuses without a complete public-ID mapping.
   Implement and qualify the station entry route under the approved
   [external-provider exception](../../../AGENTS.md#ui-automation-mandate),
   preserving ownership, ambiguity, recipient and input guards. Missing provider
   IDs do not require renewed approval or an upstream ID change.
2. After GDM entry is qualified, the guarded kiosk GUI must expose its existing
   repository-owned `kiosk-*` IDs on the installed station accessibility bus.
   The earlier guarded attempt visibly reached the form, but its observer
   received only the desktop root and timed out before any control. Resume the
   form qualification when the installed observer can resolve and read those
   IDs.

The provider exception applies only to GDM; the repository-owned request form
still requires public IDs. Host adapter/UI results establish the owned ID
implementation and safe refusal behavior only.

## Implementation

Qualify the GDM02 passwordless station route and its public request form, plus
UI15 session choice only if offered. Implement station entry and shared immutable
observations of public form names, roles, states and messages; fixed overlay-child
binding is qualified later. App behavior must be operated and observed entirely
through the GUI. Do not inspect or qualify services, D-Bus state or other app
internals, or use them as readiness or acceptance checks.

## Live VM acceptance

From live GDM enter the dedicated station through its offered session control, observe one request form and exact public child/approver/duration/control state. Prove unavailable selectors without activating them. No desktop-login shortcut.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_kiosk_entry
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
If a complete E2E scenario passed, refresh coverage immediately after that case.
Use `tools/generate_test_coverage.sh`, which runs `tools/generate_test_coverage.py`.

Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and the selected family's status
in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md); leave unfinished scope pending.
Check **011** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
