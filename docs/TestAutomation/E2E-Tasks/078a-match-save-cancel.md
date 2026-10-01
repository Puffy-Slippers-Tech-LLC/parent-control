# 078a — Edit one match rule and Save or Cancel

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **PARENT13/15 match editor, valid Save and Cancel**. Named consumer: task **078** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **077** — PARENT10, PARENT11.
- **017** — PARENT08 snapshot saved/control states; installed qualification and owned cleanup passed.

## Implementation

Bind the owned match editor, one valid same-directory wildcard and explicit Save/Cancel. Compare Cancel with the earlier immutable rule and Save with independent row readback.

Keep the complete local precise-target/basename and Cancel matrix in UI preview,
using the same input and public result blocks. The installed qualification below
samples one rule and establishes its real saved value.

## Live VM acceptance

Enter the wildcard, Cancel and read the old rule; reopen, Save and read the new rule. Qualify an independently open editor and wrong-app/ambiguous-control refusal.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_match_save_cancel
```
