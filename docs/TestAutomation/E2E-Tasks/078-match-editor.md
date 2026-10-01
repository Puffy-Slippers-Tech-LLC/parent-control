# 078 — Validate and reset one match rule

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add local invalid drafts and immediate Reset-to-default save. Reuse 078a's editor/Save/Cancel; broker-rejected reports remain task 186.

Tasks **078a** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts**. First scheduled consumer: [E2E-045, case 205](../E2E-Scenario-Recipes.md#e2e-045).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **077** — PARENT10, PARENT11.
- **017** — PARENT08 snapshot saved/control states; installed qualification and owned cleanup passed.
- **078a** — PARENT13/15 match editor, valid Save and Cancel.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

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

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_match_editor
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
