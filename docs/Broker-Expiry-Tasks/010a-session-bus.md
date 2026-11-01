# 010a — Check expiry after the child bus restarts

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 005, 007.
Estimate: 30–60 minutes; real bus replacement and recovery on both targets.

Follow the [master](../Broker-Expiry-Plan.md). Extend system-282 with planned
parameter `expiry-session-bus` (unimplemented). Replace the actual child session
bus-daemon/broker process while expiry work is pending, using the maintained
fault owner. This is the bus transport boundary; task 011a alone owns replacement
of the `org.gnome.ScreenSaver` provider on an otherwise live bus.

Identity-record the process and bus-owner change. Observe actual protection
through original grant expiry and supported reconnection/reconstruction within
declared outage-inclusive bounds, preserving work and peer input. Stale replies
must not reach another session or award time. If real bus replacement necessarily
ends the desktop, report the retention limitation under failure handling; a new
session cannot count as retained work. Do not replace the real boundary with a
client disconnect or guessed identity.

Run the distinct delta on both targets, restore only owned state and retain
unsupported recovery as a handover blocker. No generic disconnect/reader matrix.
