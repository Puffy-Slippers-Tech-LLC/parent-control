# 141 — Qualify product removal and reinstall commands

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-027/continuous (139). Scope: LIFE04 product remove/reinstall
profiles and LIFE05's corresponding notices. Reuse the qualified package
authentication, customer reboot/login and normal app-use blocks in a fresh installed VM. Product-update activation profiles are not prerequisites.

Contract: [customer package operations](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries)
and [package removal](../../SystemDesign/Package-Removal.md).

## Work

Bind the exact verified remove and reinstall commands, permitted prompts and
completion/reboot notices. Compose the corresponding LIFE05 notice/reboot path from the qualified LIFE02/GDM07 operations, and keep mechanical file,
account and migration checks under their existing system owners. Purge and
fresh-default observation are a separate capability.

## Live VM acceptance

Run the planned fixed qualification
`tools/run-tests integration check_e2e_product_removal` through the master's
existing-envelope contract. Remove normally, read the final reboot-required
text, reboot and enter an ordinary child desktop to use the prepared app.
Reinstall, follow its actual activation notice and open Parent normally.
Require affected package cleanup checks and successful owned cleanup.
Case 139 owns the complete continuous retained-settings lifecycle.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md)
and update LIFE04/LIFE05's qualified scope in [the catalogue](../E2E-Building-Blocks.md).
Delete this task when no longer needed, replacing its master link with plain
text. No new evidence/history document.
