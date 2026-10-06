# 302 — Fresh-install reboot prompt: Parent

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
One complete case is planned; its inventory ID and executable are not assigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **301** — Qualified shared installed restart modal and reboot/result operations.

Estimate: 40–60 minutes.
Session exception: Genuine installation, Close and reopening, a real reboot and fresh Parent usability form one continuous independently observed customer history.

## Scope and acceptance

Use the queue's [fresh-install regression scope](../E2E-Task-Queue.md#fresh-install-restart-regression-scope)
and [lifecycle behavior](../../Specification.md).

Start from the product-free Ubuntu baseline, install the verified current package and observe its final reboot notice. Without reboot or upgrade, launch installed Parent as the administrator. Require one modal before management controls, with installation-neutral instructions, Close and Reboot now. Close exits Parent without boot change. Reopen and require the modal again. Activate Reboot now once through normal system authorization; independently observe a new boot, usable greeter and fresh administrator desktop. Reopen Parent, complete ordinary language setup if needed and require usable management with no restart modal.

Register one pending numeric case, its finite recipe, shared worker and exact
selector during implementation; regenerate coverage through the maintained
`tools/generate_test_coverage.sh` route. No executable selector exists yet.
Historical clean-install case 2 and task 300's Chinese latest-install history do not
supply this acceptance. Preserve failures, reconciliation and owned cleanup.
