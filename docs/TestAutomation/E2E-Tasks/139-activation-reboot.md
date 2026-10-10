# 139 — Follow reboot activation after a real update

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: The real update, customer reboot/login and package activation checks must all complete.

## Scope and prerequisites

Deliver **LIFE04 update; LIFE05 reboot scope**. First scheduled consumer: [E2E-026, case 138](../E2E-Scenario-Recipes.md#e2e-026).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **135a** — Verified updater infrastructure and public saved-settings comparison.
- **007** — LIFE02 owned reboot and independent boot/greeter result.

## Implementation

Bind a verified old/new package profile requiring reboot activation. Extend LIFE04(update) and LIFE05 only for this route. Follow the displayed requirement for every named affected app/user; preserve all mechanical migration obligations.

Reuse `package_install.submit_release` / `observe_release` and the existing
`JourneyPlan.reboot_transition` / `InstalledJourney.submit_reboot` path. The
qualified `package_upgrade.PLAN` reads the upgrade notice without activating the
new release; add the observed post-upgrade reboot and affected-app/settings
result. Reuse unchanged package and reboot qualification rather than replaying
their refusal histories; full request-choice/enforcement coverage stays in case 138.

## Live VM acceptance

On the VM install the real update, read its reboot requirement, perform the normal reboot/login sequence and read settings before edits. Run the affected existing package activation checks separately.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_activation_reboot
```
