# 006 — Restore the extension when kiosk time is approved

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Category: system/integration. Requires: 001. Estimate: 30–60 minutes.
Session exception: genuine authentication, grant commit and resulting native
activation must be observed in the same retained child session on each target.

Read the [master reuse map](../Extension-Plan.md#reuse-and-duplicate-avoidance),
[grant transactions](../SystemDesign/Broker.md#authorization-and-grant-transactions),
`Broker._grant`, `system_session_expiry.verify_request_extension` and the existing
system 282 kiosk-grant recovery branch.

Extend that owner only for missing v1.5 kiosk recovery assertions. With saved
controls enabled and a deliberately individually/globally disabled child
extension, submit one genuine kiosk request and complete real parent authentication.
Observe the approval path's activation request, actual native configured/active
state, global switch and exact other-extension choices. Continuous monitoring may
already have repaired the desktop; use bounded engineering call-path observation,
not a race that requires the disabled state to persist through authentication.

Verify the granted time is the specified single transaction, not replayed by
recovery; preserve the selected child's session and unrelated-child policy/grants.
Retain existing failure/rollback checks without repeating the full approval,
Polkit, app-policy or extension-rollback matrices. Do not create a duplicate
customer E2E approval case or require a new graphical provider qualifier merely
to send the existing genuine broker request.

Reuse system 282 if it owns the complete engineering assertion; otherwise
register only the missing standalone integration delta before running. Record
both target results, the real binding and completed owned cleanup.
