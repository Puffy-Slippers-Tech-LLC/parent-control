# 006b — Keep old expiry callbacks away from new sessions

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 005.
Estimate: 30–60 minutes; old-session effect history plus recovery on both targets.

Follow the [master](../Broker-Expiry-Plan.md). Extend system-282 with planned
parameter `expiry-session-replacement` (unimplemented). Read complete current
session identity and callback ownership paths. End/replace the target session
while a current expiry observation/callback is pending; an old callback must
not lock another session or a reused account identity. Use the minimum owned
account/session fixture and identity-checked cleanup, not a full account matrix.

Revalidate original versus replacement session, authoritative balance and exact
effect recipient. Positive replacement access and another foreground user's
input/work remain usable. Reuse existing identity/session mechanics; tasks
170/174/178/179 keep their broader residuals. Future broker pending effects are
external replacement gates, not an invented scheduler for this task.

Run changed current-owner checks on both targets and restore owned fixtures.
Missing supported session-control routes remain blockers; saved guest state and
mocked process identities supply no installed result.

Prepare replacement identity and its ample positive entitlement before the
pending-callback boundary. Establish pending/ended/replacement order through
the maintained controls and observations, not near-expiry sign-in speed. Keep
the original callback/deadline identity when checking the new usable desktop;
later navigation must not renew the old effect's budget.
