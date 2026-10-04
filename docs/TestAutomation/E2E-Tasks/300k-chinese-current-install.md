# 300k — Qualify Chinese first presentation after the latest installation

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **006** — LIFE04 verified current-package installation and independent completion/version/reboot notice.
- **007** — LIFE02 customer reboot and fresh-boot observations.
- **300a** — Chinese baseline assets and read-only FIX06.
- **300b** — DESK13 Jordan desktop-language setting and independent readback.
- **300e** — Chinese pre-reboot notice and untouched first-presentation readers.

Estimate: 35–50 minutes.
Session exception: The package installation, unchanged-boot notice, customer reboot and untouched first kiosk presentation form one continuous qualification attempt.

## Scope and acceptance

Qualify the changed fresh-install binding needed by [task 300](300-localization.md).
Start product-free, verify one latest current-source package and Chinese assets,
set Jordan's desktop locale through DESK13 and explicitly renew the session.
Install that package once through LIFE04. Independently read completion,
installed version, reboot notice and unchanged boot. Enter kiosk before any
Parent policy setup or automatic language handler; require Jordan and the
Chinese reboot-required message and buttons. Close/return normally, reboot once
through LIFE02, confirm a new boot, perform only necessary public policy setup,
and observe the untouched Chinese chooser/default/form for Jordan. Cancel
without saving and independently read the Chinese form.

Use the finite values and entry order in the
[Chinese recipe](../E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle-planned-task-300).
No approval belongs to this slice. Wrong package/boot/child, stale ownership,
chooser-displaced notice and replay must refuse. Preserve English administrator
and station languages and the unset personal preference.

## Shared implementation

Reuse `ChineseKioskJourney` and the initial-presentation operations in
[chinese_kiosk_lifecycle.py](../../../tests/e2e/chinese_kiosk_lifecycle.py) and
[AccessibleUI](../../../tests/e2e/accessible_ui.py), with the existing current-only
LIFE04/LIFE02 path. Separate shared operations from the historical dual-package
qualification; do not copy its lifecycle or require v1.2.

## Implementation entry

Implemented selector: `check_e2e_chinese_current_install`; live qualification pending.
Its source-bound single-package inputs are prepared automatically. The fixed
composition is `chinese_current_install.PLAN` / `ChineseCurrentInstallJourney`,
with `ChinesePresentationMixin` and the shared worker renewal/notice/form leaves.
Run `tools/run-tests integration check_e2e_chinese_current_install`, then the
affected `check_e2e_customer_reboot` and `check_e2e_chinese_kiosk_lifecycle`
regressions. Historical upgrade evidence does not qualify the new composition.

## Current validation boundary

Host composition, refusal/ownership, recorder and source validation passed:
`20261004T182558Z-16efaa1b` contains 2517 unit checks plus source validation.
Plan, inventory and coverage consistency also passed; the earlier two real GTK
first-presentation checks remain applicable. Changes affect tests and
documentation only, so no package build is required.

The earlier product-free renewal failure was reproduced as a mechanical
binding defect: installed standard entry required the absent kiosk account.
Pre-install Jordan renewal and Jamie return now explicitly use the product-free
list/focus binding, proving station absence and preserving ordered,
role-specific fresh recipient proofs. The second live attempt verified this
correction, the renewed Chinese desktop, current-package installation and
independent reread, the unchanged-boot Chinese restart notice, normal return,
customer reboot submission and `e2e:boot-change-verified`.

That attempt failed at `chinese-current-install.customer-reboot.greeter`.
Expected: a successful fresh greeter observation after the independently
confirmed new boot. Actual: `reboot-greeter` has a request but no successful
reply; the runner recorded `e2e:worker-execution-failed`, `CommandError` and
secondary `command:failed:ssh`. Its cause remains uninvestigated at the session
failure boundary. Post-reboot Chinese chooser/default/form acceptance and both
required lifecycle regressions remain unrun. Worker cleanup, baseline
restoration and finalization passed; the lease is complete and the VM is off.

Resume from `output/test-runs/host/reports/20261004T182828Z-50571e3e/report.md`
and its `category-001.log`, `failure.json` and `progress.json`. Retained
allocations are `onpc-graphical-smoke-y0f5d4dl`,
`onpc-e2e-evidence-ajvpxne8` and `onpc-e2e-evidence-jld0qd1w` under the
maintained privileged allocation root. Use the approved artifact reader to
investigate this new failure, then host-verify a settled correction and rerun
the qualification and the two required regressions.
Keep this task and the plan pointer unchanged until all acceptance passes.
