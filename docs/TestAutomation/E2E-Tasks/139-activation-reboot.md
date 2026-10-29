# 139 — Follow reboot activation after a real update

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: Keep the real update, notice and customer reboot/login together.

## Scope and prerequisites

Deliver **LIFE04 update; LIFE05 reboot scope**. First scheduled consumer: [E2E-026, case 138](../E2E-Scenario-Recipes.md#e2e-026).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **135a** — Verified updater infrastructure and public saved-settings comparison.
- **007** — LIFE02 owned reboot and independent boot/greeter result.

## Implementation

Bind a verified old/new package profile requiring reboot activation. Extend
LIFE04(update) and LIFE05 only for this route. Follow the displayed requirement
for every named affected app/user.

Reuse `package_install.submit_release` / `observe_release` and the existing
`JourneyPlan.reboot_transition` / `InstalledJourney.submit_reboot` path. The
qualified `package_upgrade.PLAN` reads the upgrade notice without activating the
new release; add the observed post-upgrade reboot and affected-app/settings
result. The registered `check_e2e_kiosk_update_reentry` already owns genuine
prior/current installation, both activation reboots and usable station
approval/reentry. Reuse that finite station binding; add only missing Parent or
other affected-app public observations. Native policy, migration and grant
preservation probes stay in `package::test_previous_package_policy_preservation`.
Reuse unchanged package and reboot qualification rather than replaying their
refusal histories; case 138 owns public persisted-value/request-choice coverage.

## Live VM acceptance

On the VM install the real update, read its reboot requirement, perform the
normal reboot/login sequence and independently require each affected app usable
with retained visible settings before edits.
Run an existing package-owner check only when this implementation changes the
behavior it covers; do not repeat the unchanged station history as an extra
qualification of the same binding.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_activation_reboot
```
