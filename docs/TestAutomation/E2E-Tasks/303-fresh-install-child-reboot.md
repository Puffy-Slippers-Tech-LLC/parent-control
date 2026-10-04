# 303 — Fresh-install reboot prompt: Child App

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
One complete case is planned; its inventory ID and executable are not assigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **301** — Qualified shared installed restart modal and reboot/result operations.

Estimate: 40–60 minutes.
Session exception: Genuine installation, child desktop entry, Close and reopening, real reboot and public setup form one continuous independently observed customer history.

## Scope and acceptance

Use the queue's [fresh-install regression scope](../E2E-Task-Queue.md#fresh-install-restart-regression-scope)
and [lifecycle behavior](../../Specification.md).

Start from the product-free Ubuntu baseline, install the verified current package and observe its final reboot notice. Keep that boot, enter the declared ordinary child desktop through shared session mechanics and launch installed `oh-no-parent-control-child`. Do not enable child controls first: policy is guarded and the new panel need not already be loaded. Require one modal before a usable request, Close/default and Reboot now. Close the notice and exit the overlay normally; require the same child desktop/boot. Reopen and require the modal again. Activate Reboot now once through normal system authorization; observe a new boot and usable greeter. After ordinary public Parent setup enables the child, enter a fresh child desktop and reopen its form. Complete ordinary language setup if needed; require the fixed correct child and usable request with no modal.

Register one pending numeric case, its finite recipe, shared worker and exact
selector during implementation; regenerate coverage through the maintained
`tools/generate_test_coverage.sh` route. No executable selector exists yet.
Historical clean-install case 2 and task 300's Chinese latest-install history do not
supply this acceptance. Preserve failures, reconciliation and owned cleanup.
