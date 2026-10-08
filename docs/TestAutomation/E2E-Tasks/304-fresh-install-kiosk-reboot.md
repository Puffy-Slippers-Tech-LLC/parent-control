# 304 — Fresh-install reboot prompt: kiosk session

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
Case **259**, E2E-058 variant `kiosk` (`surface=kiosk`), follows its
[finite recipe](../E2E-Scenario-Recipes.md#e2e-058).

- **259 — kiosk:** `surface=kiosk`.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **301** — Qualified shared installed restart modal and reboot/result operations.

Estimate: 40–60 minutes.
Session exception: Genuine installation, first station login, Close and session re-entry, real reboot and public setup form one continuous independently observed customer history.

## Scope and acceptance

Use the queue's [fresh-install regression scope](../E2E-Task-Queue.md#fresh-install-restart-regression-scope)
and [lifecycle behavior](../../Specification.md).

Start from the product-free Ubuntu baseline, install the verified current package and observe its final reboot notice. Keep that boot and enter the newly created request-station account before any child policy setup. Require one modal on this first kiosk session in the selected child's initial language, with no first-run chooser displacing it. Require installation-neutral instructions, Close and Reboot now; no usable request is available. Close, exit the session normally and observe usable GDM without boot change. Re-enter and require the modal again. Activate Reboot now once through normal system authorization; observe a new boot and usable greeter. After ordinary public Parent setup enables the declared child, enter a fresh kiosk session and complete ordinary language setup if needed; require usable child/approver selection and request with no modal.

Implementation: `tests/e2e/fresh_kiosk_restart.py::PLAN` /
`onpc_customer_reboot::run_kiosk_notice`, using shared `restart_reentry('kiosk')`,
package recorder, station entry and modal operations. Jordan is the initial
child; select Jamie publicly before the final usability read through shared
`restart_kiosk_usability()`. Enable Jordan's 30 minutes publicly only after
reboot. Require all seven assertions, collection and owned cleanup.

Host composition/safety owners: `test_clean_install_cleanup_safety.py`,
`test_customer_reboot_cleanup_safety.py`, `test_e2e_case_composition.py`,
`test_e2e_progress.py` and the shared worker safety tests. Existing unit/cleanup
classifications retain private fixtures and bounded waited Perl children;
this adds no process, display, bus or storage owner.

Acceptance: `tools/run-tests --vm onpc-Ubuntu26.04 e2e --id '259'`.
Required regressions: `check_e2e_restart_notice` for the shared kiosk reentry and
usability changes, and `check_e2e_customer_reboot` for reboot continuity, each
through `tools/run-tests --vm onpc-Ubuntu26.04 integration <selector>`.
Regenerate coverage through `tools/generate_test_coverage.sh` after the case.
Historical clean-install case 2 and task 300's Chinese latest-install history do not
supply this acceptance. Preserve failures, reconciliation and owned cleanup.

## Remaining work after first live attempt

Host checks passed, including worker order/refusal, real recorder entry,
modal-result guards, inventory/composition/queue consistency, worker distribution,
transport/controller safety, all three GTK modal previews and traceability.
Coverage was regenerated. The first Ubuntu attempt failed at `usable-kiosk`
(`restart-kiosk-usable`) with `ui:kiosk-valid-selection`.
Expected: usable Jordan/Jamie selectors and enabled Request without the modal.
Actual: fresh default station form was independently observed, but the final
selection guard refused; which account differed and why remain uninvestigated.
No product defect or completed case is established.

Preserved [attempt report](../../../output/test-runs/host/exports/onpc-artifact-export-1j_zge1u/report.md)
and [final observer error](../../../output/test-runs/host/exports/onpc-artifact-export-9dj8iaup/command-0103-stderr.txt).
The original report is `output/test-runs/host/reports/20261008T020713Z-bc50c6eb/report.md`;
raw worker evidence is `output/test-runs/privileged/allocations/onpc-graphical-smoke-yyafmz4_`.
Independent postboot Jordan 1800-second daily/zero-grant setup and fresh
`station-branch` form proofs are in `output/test-runs/privileged/allocations/onpc-e2e-evidence-vhruevjp`.
Worker stop/callback closure, owned cleanup, suite cleanup and outer baseline
restoration passed; normal successful worker shutdown and collection did not.
No correction or retry followed this live failure. Investigate in the next session,
preserve expectations, rerun affected host checks and then case 259 plus both
required regressions before close-out. The pointer remains on 304.
