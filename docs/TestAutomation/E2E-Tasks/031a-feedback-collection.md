# 031a — Observe diagnostic collection from its start

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FEED09 collection trace**. First scheduled consumer: [E2E-031, case 155](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify queue rows; no predecessor brief is needed):

- **016a** — UI22.
- **030** — FEED05; FEED10 dialog persistence.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind UI22 to collection and Download availability. Arm observation before FEED01 opens feedback, acknowledge readiness, then collect the required public transitions and terminal predicate. Reuse the snapshot observer for the final state.

## Live VM acceptance

On the live VM, open feedback once with observation already armed. Require the declared collection samples and eventual usable Download control. Close normally and qualify an independent entry. A missed required transient fails; do not delay the product or infer it from the final state.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_feedback_collection
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
Check **031a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
