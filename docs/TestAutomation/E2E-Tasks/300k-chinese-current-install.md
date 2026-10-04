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

Host composition, refusal/ownership, recorder, source and two real GTK
first-presentation checks passed. Auto baseline preparation completed after the
pre-lease `baseline:preparation-outdated` refusal; that refusal was not a live
attempt.

The first live current-install attempt, `20261004T180943Z-25f6f7fb`, failed
after independently verified Chinese assets, the `zh_CN` account readback and
`language-parent-logout`. The next checkpoint is `language-installed-greeter`
(`ui:gdm-standard-list`). Expected: fresh child-entry greeter, then the renewed
Chinese desktop before installation. Actual: no successful greeter observation;
the runner recorded `e2e:worker-execution-failed` and `command:failed:ssh`.
The retained `private/command-0367-stderr.txt` establishes a mechanical binding
defect: Jamie and Jordan each had one owned row, but installed standard entry
required the absent kiosk account (`ui:gdm-account-cardinality`). The host
regression reproduced that same refusal. Pre-install Jordan renewal and Jamie
return now explicitly use the product-free list/focus binding, proving station
absence and preserving ordered, role-specific fresh recipient proofs.
Worker cleanup, baseline restoration and finalization finished; the
VM is off. No product installation, reboot or first kiosk presentation was
reached. The lifecycle regressions remain unrun.

Resume from `output/test-runs/host/reports/20261004T180943Z-25f6f7fb/report.md`
and its `category-001.log`. Private attempt/evidence allocations are
`onpc-graphical-smoke-c5oezl6s` and `onpc-e2e-evidence-vd3vnyuj` under the
maintained privileged allocation root. Use the approved artifact reader for
their retained error logs. Host-verify the correction, then rerun the fixed
qualification and the two required regressions.
Keep this task and the plan pointer unchanged until all acceptance passes.
