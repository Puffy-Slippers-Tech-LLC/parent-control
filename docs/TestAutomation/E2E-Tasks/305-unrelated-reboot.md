# 305 — Unrelated reboot requests leave all apps usable

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
One complete case is planned; its inventory ID and executable are not assigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **301** — Qualified shared installed restart modal and reboot/result operations.

Estimate: 40–60 minutes.
Session exception: A real unrelated package reboot request, three separate app entries and normal reboot controls form one continuous independently observed customer history.

## Scope and acceptance

Use the queue's [fresh-install regression scope](../E2E-Task-Queue.md#fresh-install-restart-regression-scope)
and [lifecycle behavior](../../Specification.md).

Begin with current product installation/reboot activation completed and public child policy configured. Observe usable Parent, child request and station request with no modal. Perform a declared verified unrelated package operation that genuinely requests reboot through its normal integration, without reinstalling/upgrading the product or causing a product reboot request. Before reboot, independently open all three apps through ordinary shared entry routes; require usable public controls and absent modal. Perform one ordinary planned system reboot and repeat all three no-modal/usability controls after fresh entry.

Gate: the unrelated package asset, normal public trigger and genuine reboot result must be declared and verified before execution. No suitable trigger is qualified yet. Missing assets/trigger remain a blocker; manually written `/run` markers or injected broker errors are engineering coverage.

Register one pending numeric case, its finite recipe, shared worker and exact
selector during implementation; regenerate coverage through the maintained
`tools/generate_test_coverage.sh` route. No executable selector exists yet.
Historical clean-install case 2 and task 300's Chinese latest-install history do not
supply this acceptance. Preserve failures, reconciliation and owned cleanup.
