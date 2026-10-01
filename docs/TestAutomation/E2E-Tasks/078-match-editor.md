# 078 — Validate and reset one match rule

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add local invalid drafts and immediate Reset-to-default save. Reuse 078a's editor/Save/Cancel; broker-rejected reports remain task 186.

Reuse the delivered scope of tasks **078a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts**. First scheduled consumer: [E2E-045, case 205](../E2E-Scenario-Recipes.md#e2e-045).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **077** — PARENT10, PARENT11.
- **017** — PARENT08 snapshot saved/control states; installed qualification and owned cleanup passed.
- **078a** — PARENT13/15 match editor, valid Save and Cancel.

## Implementation

UI owns the full local empty/unrelated-input, Cancel and Reset matrix, sharing
the installed editor input/read operations. This remains required task scope.

Implement PARENT13 first, then PARENT15 Save, Cancel, Reset and local invalid-draft results. Compare Cancel with the supplied old rule and Reset with its immediate default save. Broker-rejected wildcard reporting is qualified separately with FEED15.

## Live VM acceptance

In installed Parent, save one valid same-directory wildcard and read the new
rule, then Reset and read the immediately saved detected default. Keep one local
invalid-input refusal to qualify that input route; full validation permutations
and Cancel comparisons run in UI. Bind inputs before execution and use no
preference reads. Real broker-rejected reporting remains task 186.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_match_editor
```
