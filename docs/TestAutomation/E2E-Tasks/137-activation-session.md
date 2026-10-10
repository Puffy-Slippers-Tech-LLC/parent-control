# 137 — Follow session activation after a real update

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: The real update, logout/login of every affected user and package activation checks must all complete.

## Scope and prerequisites

Deliver **LIFE04 update; LIFE05 session scope**. First scheduled consumer: [E2E-026, case 137](../E2E-Scenario-Recipes.md#e2e-026).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **135a** — Verified updater infrastructure and one public saved-settings comparison.
- **044** — Bound affected-user entry/return for the required session renewal.

## Implementation

Bind a verified old/new package profile requiring session activation. Extend LIFE04(update) and LIFE05 only for this route. Follow the displayed requirement for every named affected app/user; preserve all mechanical migration obligations.

Reuse `package_install.submit_release` / `observe_release`; bind the exact
session-activation notice and each named session's normal logout/fresh login.
The current `package_upgrade.PLAN` is a reboot-notice qualification, not this
binding. Keep one before/after saved-setting comparison per affected account;
the complete case owns app enforcement and request-choice persistence. Reuse
unchanged updater and entry qualification; do not repeat their refusal histories.

## Live VM acceptance

On the VM install the real update, read its session requirement, perform the normal logout/login for every affected user sequence and read settings before edits. Run the affected existing package activation checks separately.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_activation_session
```
