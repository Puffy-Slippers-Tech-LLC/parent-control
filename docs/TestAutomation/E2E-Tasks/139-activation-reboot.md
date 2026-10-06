# 139 — Follow reboot activation after a real update

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: The real update, customer reboot/login and package activation checks must all complete.

## Scope and prerequisites

Deliver **LIFE04 update; LIFE05 reboot scope**. First scheduled consumer: [E2E-026, case 138](../E2E-Scenario-Recipes.md#e2e-026).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **007** — LIFE02.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **079** — PARENT16 and FLOW03 public app-policy editing.
- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.

## Implementation

Bind a verified old/new package profile requiring reboot activation. Extend LIFE04(update) and LIFE05 only for this route. Follow the displayed requirement for every named affected app/user; preserve all mechanical migration obligations.

## Live VM acceptance

On the VM install the real update, read its reboot requirement, perform the normal reboot/login sequence and read settings before edits. Run the affected existing package activation checks separately.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_activation_reboot
```
