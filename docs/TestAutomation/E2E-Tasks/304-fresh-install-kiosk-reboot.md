# 304 — Fresh-install reboot prompt: kiosk session

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
One complete case is planned; its inventory ID and executable are not assigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **301** — Qualified shared installed restart modal and reboot/result operations.

Estimate: 40–60 minutes.
Session exception: Genuine installation, first station login, Close and session re-entry, real reboot and public setup form one continuous independently observed customer history.

## Scope and acceptance

Use the queue's [fresh-install regression scope](../E2E-Task-Queue.md#fresh-install-restart-regression-scope)
and [lifecycle behavior](../../Specification.md).

Start from the product-free Ubuntu baseline, install the verified current package and observe its final reboot notice. Keep that boot and enter the newly created request-station account before any child policy setup. Require one modal on this first kiosk session in the selected child's initial language, with no first-run chooser displacing it. Require installation-neutral instructions, Close and Reboot now; no usable request is available. Close, exit the session normally and observe usable GDM without boot change. Re-enter and require the modal again. Activate Reboot now once through normal system authorization; observe a new boot and usable greeter. After ordinary public Parent setup enables the declared child, enter a fresh kiosk session and complete ordinary language setup if needed; require usable child/approver selection and request with no modal.

Register one pending numeric case, its finite recipe, shared worker and exact
selector during implementation; regenerate coverage through the maintained
`tools/generate_test_coverage.sh` route. No executable selector exists yet.
Historical clean-install case 2 and task 300's Chinese latest-install history do not
supply this acceptance. Preserve failures, reconciliation and owned cleanup.
