# U06 — Keep entry working after a relevant update

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U05.
Estimate: 45–90 min; session exception: one relevant update/activation/reentry history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read [activation](../SystemDesign/Lifecycle.md#package-activation-and-session-renewal),
the affected packaging callers and existing installed upgrade coverage. Use the
maintained prior/candidate package inputs and `make install` route.

Select one supported update crossing the kiosk integration changed by this plan.
Fix only demonstrated activation, PAM/account or retained-owned-state defects
that prevent usable passwordless entry after the required activation. Preserve
policy and ordinary accounts. Do not add ambient package inventories, unnecessary
reboot rules or a dependency/version compatibility matrix.

Observe the selected update, required restart/session renewal/reboot if any,
fresh passwordless entry, one genuine approval/time result, exit and usable
reentry. If existing upgrade coverage already proves the exact condition, reuse
its applicable result without duplicating it. This is not release acceptance,
all-version upgrade testing or removal qualification. Run affected checks and
required review/build for fixes, finish owned restoration and close only U06.
