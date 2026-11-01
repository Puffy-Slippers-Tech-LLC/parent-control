# 009 — Check locking while the broker stalls

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 007.
Estimate: 30–60 minutes; stall and recovery retain the original deadline.

Read the [master](../Broker-Expiry-Plan.md), broker lifecycle and maintained
identity-recorded fault ownership helpers. Extend system-282 with planned
parameter `broker-stall` (unimplemented), using one bounded real process stall
while a child desktop is already usable. A slow mock response is insufficient.

Keep the stall through original expiry and observe secure input protection,
retained work and peer continuity. Resume/recover only the owned process via
maintained routes, then require reconstruction within the declared budget
including outage time, with no stale lock, duplicated time or replayed approval.
Where a health/heartbeat exists, it must represent useful deadline progress;
service liveness alone cannot establish enforcement. No heartbeat/supervision
implementation is authorized by this TA task.

Confirm the actual stall spans expiry; host scheduling or a slow reply cannot
substitute for that ordering. The original process identity must still own the
stall when recovery resumes it.

Reuse the shared crash mechanics and observation; add only the stalled-process
condition and its recovery. Run on both targets with finite fault/recovery
windows and serial identity-checked cleanup; unsupported progress remains a
concrete handover blocker.
