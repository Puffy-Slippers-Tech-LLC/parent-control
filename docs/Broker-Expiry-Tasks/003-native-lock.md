# 003 — Check native exhaustion locks

Acceptance: review

Required tasks: 002.
Estimate: 45–75 minutes; daily and grant natural-deadline histories on both targets.

Read the [master](../Broker-Expiry-Plan.md), native investigation and current
system-282/TIME04 implementations. Extend system-282 with planned parameters
`native-daily-lock` and `native-grant-lock` (unimplemented), consuming the shared
panel-free observation and task 002's independent native timing mechanics.

Observe daily-only and zero-daily grant-only natural exhaustion with the whole
extension disabled throughout the observation. Verify the extension's absence
at entry and after recovery; no recovery reactivation may mask native behavior.
Keep the daily-only child in active foreground use to its original deadline.
Assert protected input within the declared bound and preserved ordinary work.
The grant-only elapsed-time history owns the peer-foreground/background-target
variant: use existing switch helpers and prove the target's transition, not
only peer continuity. Daily use pauses while inactive; never expect its old
active-use deadline to survive a switch unchanged.

Keep existing extension-enabled expiry/recovery assertions. These parameters
qualify native enforcement specifically; do not duplicate combined-countdown,
fresh/retained admission or positive daily soft-app journeys. Native limitations
are findings, not justification to add a broker scheduler in this TA task.
If extension-disabled setup cannot preserve unrelated compatibility hooks,
report the boundary and distinguish narrower diagnostic isolation from a pass.

Run both native diagnostic histories on `onpc-Ubuntu26.04` and `onpc-Fedora44`,
restore owned state and review the actual native result. Both attempts are
required despite review metadata. This row characterizes native coverage and
gaps; an unsupported native result is a handover blocker, not a passing
enforcement selector. Do not register a failed protection outcome as a pass.
A regression on the production extension-enabled path still follows failure
handling. Missing observation/ownership routes block characterization itself.
