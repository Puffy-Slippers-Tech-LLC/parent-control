# 008 — Check locking while the broker is stopped

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 007.
Estimate: 30–60 minutes; outage/deadline/recovery form one history per target.

Use the [master](../Broker-Expiry-Plan.md) and task 007's maintained fault
mechanics, not its saved VM state. Extend system-282 with planned parameter
`broker-stop` (unimplemented). Deliberate service stop differs from a crash
because lifecycle restart policies may not restart it.

Stop the identity-recorded broker with the child already using its retained
desktop. Keep it unavailable across the original expiry; assert actual input
protection, preserved work and unaffected peer, then supported service recovery
and reconstruction within the declared outage-inclusive budget. Retained/fresh
future login denial alone cannot qualify an already exposed desktop.

Confirm the owned service is stopped before original expiry and remains stopped
through the required interval; a late stop cannot establish outage protection.

Use one finite grant-only history, not a repeat of daily/grant/combined cases.
Reuse crash-owner recovery checks and add only stop-specific lifecycle effects.
Do not add service policy or use a top-up/logout to make the result pass.
Run this delta on both targets, restore owned service/session/configuration
state, and retain any outage protection gap as a handover blocker.
