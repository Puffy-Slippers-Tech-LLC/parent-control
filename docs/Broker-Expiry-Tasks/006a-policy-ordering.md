# 006a — Apply the latest time decision at expiry

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 004, 005.
Estimate: 30–60 minutes; one finite policy-ordering family on both targets.

Follow the [master](../Broker-Expiry-Plan.md). Extend system-282 with planned
parameter `expiry-policy-order` (unimplemented). Read complete current broker
transaction and extension callback owners before exercising races.

Use representative orderings of renewal versus old expiry, revoke/allowance
reduction versus expiry, and disablement versus a pending current callback.
Observe authoritative commit order including Busy/refusal and rollback;
assert current entitlement rather than assuming concurrent requests all succeed.
An entitled desktop stays usable; a restricted one locks within declared bounds.
Retain work and unaffected peer input. Reuse host ordering from 005 and public
management helpers; do not duplicate generic concurrency obligations 147/148.

Run the new installed delta on both targets, restore owned state, and report
current-path mismatches under failure handling. Future broker effect callbacks
remain mandatory replacement gates; do not invent them in this TA task.
