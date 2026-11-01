# 007 — Check locking across a broker crash

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 003, 005.
Estimate: 30–60 minutes; crash, original deadline and recovery stay together.

Read the [master](../Broker-Expiry-Plan.md), Lifecycle service activation and
shared fault/process ownership helpers. Extend system-282 with planned parameter
`broker-crash` (unimplemented). Reuse installed supervision/credential/cleanup
infrastructure; no new daemon, recovery framework or product restart policy.

Crash the exact identity-recorded broker process while a child desktop is
already usable. Cross the original expiry during unavailability; observe
protected input and retained work throughout the declared window. Include a
pending lock request boundary to detect lost/replayed effects. Recover via the
supported lifecycle and reconstruct current native balance, grant and session
within a predeclared budget including outage time. Never reset the grant clock.

Confirm the exact crash/pending-request boundary before crossing expiry rather
than relying on a last-second signal. A restart first observed after expiry
cannot establish whether protection held during the required outage.

Reject duplicate time, replayed approval, stale effects or peer disturbance.
Observe useful deadline progress, not merely a running service. Current lack of
automatic restart is a recorded boundary, not an automatic pass or permission
to install supervision. Future replacement reruns must isolate the old request.

Register the distinct engineering fault once, review applicable resource
inventories, run the new parameter on both targets and restore only owned state.
No broader startup or retained-unlock matrix is imported.
