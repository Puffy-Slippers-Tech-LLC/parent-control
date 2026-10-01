# 135 — Follow a real process-activation update

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: Real update activation and the affected mechanical package checks remain required alongside the narrowed process branch.

## Session boundary

Add the process-activation profile, notice and normal affected-app close/reopen sequence. Reuse 135a's fixed update/result infrastructure while retaining distinct live evidence for both profiles.

Reuse the delivered scope of tasks **135a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **LIFE04 update; LIFE05 process/none scope**. First scheduled consumer: [E2E-026, case 136](../E2E-Scenario-Recipes.md#e2e-026).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **028** — LIFE01.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **007** — LIFE02.
- **079** — PARENT16 and FLOW03 public app-policy editing.
- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **135a** — LIFE04 update and LIFE05 no-action notice.

## Implementation

Bind a verified old/new package profile requiring process activation. Extend LIFE04(update) and LIFE05 only for this route and the explicit no-action notice branch. Follow the displayed requirement for every named affected app/user; preserve all mechanical migration obligations.

## Live VM acceptance

On the VM install the real process-activation update, read its requirement, perform the normal close/reopen sequence and read settings before edits. In an independent attempt, qualify the declared real no-action update profile: read its notice and observe unchanged usable app entry without adding an activation action. Both claimed LIFE05 branches require live results. Run the affected existing package activation checks separately.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_activation_process
```
