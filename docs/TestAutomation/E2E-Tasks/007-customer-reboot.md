# 007 — Observe a deliberate customer reboot

Estimate: 40–60 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: Customer reboot continuity changes shared recorder/routing behavior and needs real installation, reboot, login and affected retained regressions.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **LIFE02**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries), [related block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — LIFE04 install only.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

Reuse [the qualified install composition](../E2E-Building-Blocks.md#customer-package-install-composition):
`tests/e2e/package_install.py` (`submit_install`, `observe_install`,
`PackageInstallJourney`) and `PackageInstallQualification` in
`tests/integration/parent_setup_qualification.py`. Its fixed selector is
`check_e2e_package_command`; its host regression is
`tests/unit/test_package_install_cleanup_safety.py`. Extend the shared
`InstalledJourney` boot-continuity boundary for the planned transition; preserve
the existing unplanned-boot refusal coverage in
`tests/unit/test_installed_journey_cleanup_safety.py`.

## Implementation

Add one explicitly planned customer boot transition to InstalledJourney, reusing the qualified product-free installation start. Reboot through the shared guarded SSH system command, bind the changed boot only as harness continuity, and reacquire fresh GDM. Unplanned reboot still fails. This task does not introduce another setup route.

Use one fixed supported guest reboot command in shared lifecycle infrastructure. Validate the owned VM and planned boot transition before submission, then independently observe the changed boot and fresh usable GDM. Do not automate Shell power menus or confirmations. A baseline reset or maintenance restore cannot satisfy reboot continuity.

## Live VM acceptance

In the same live installation attempt, perform the requested normal reboot, observe fresh usable GDM, sign in normally and reach the administrator desktop. No in-journey baseline restore or replacement adoption; run affected ownership/recorder safety checks.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_customer_reboot
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **007** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
