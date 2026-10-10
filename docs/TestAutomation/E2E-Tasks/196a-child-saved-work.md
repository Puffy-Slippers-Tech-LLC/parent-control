# 196a — Save and reopen a child's synthetic work document

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FILE08/09 and APP03/04 child-owned saved work**.
First scheduled consumer: [E2E-050, case 247](../E2E-Scenario-Recipes.md#e2e-050).
Use the [file and activity contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — Guarded synthetic-file allocation, identity receipts and owned cleanup.
- **047** — Jordan's usable native activity and immutable public window/draft observations.
- **048e** — Riley's usable native activity and account-scoped activity observations.

## Implementation

Add the finite work-document binding to the maintained native work fixture and
shared FILE08/09 operations. `gui_application.py::main` currently has an in-memory
draft/Submit action, with no document Open/Save/reopen behavior.
`SyntheticFiles._command` runs as Jamie; checked 196 changes an attachment
source and does not supply child-owned editor work. Extend those shared owners
for one declared synthetic document per child, explicit Riley/Jordan identity,
bounded text and the exact owned destination. Baseline preparation owns reusable
fixture assets; attempts allocate their own documents through the shared lifetime.

Directly open the declared document in the work app, replace its text and Save
once through public fixture controls, then independently read saved content.
Capture its immutable window/activity through APP04. A same-window activity
comparison and a deliberate normal close/reopen have different results: the
latter must recover saved text in a new usable window. Keep those results
explicit in the shared operation; do not relaunch to satisfy retention.

## Live VM acceptance

Qualify a Jordan Save/reopen and independently supplied Riley document entry,
using distinguishable text and checking that the peer's file stays unchanged.
Require saved text after normal reopening and one usable action in that window.
Focused harness coverage rejects wrong account, undeclared/replaced paths,
links and uncertain/replayed input before mutation; retain those guards at
runtime. Reuse unchanged native-launch and file-lifetime qualification. Cross-user
retention, logout, enforcement and natural-lock histories belong to the consumers.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_child_saved_work
```
