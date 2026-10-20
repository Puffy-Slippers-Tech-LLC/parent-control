# C02c1 — Prepare kiosk account provisioning

Acceptance: host

Required tasks: C02b.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

Read C01's complete account/session functions in tools/provision.py,
packaging/kiosk_confinement.py and the login-check callers. Reconstruct the
pinned release's kiosk account/session routing using current supported APIs.
Keep reserved-account ownership, ordinary users, main's non-confinement packaging
improvements and passwordless dedicated entry. The old GDM hook is historical
source, not qualified current-GDM routing.

Prepare only this account/provisioning slice and its direct tests. Keep it
unselected until C02; C02c owns native/distro PAM and C02c2 owns lifecycle
migration. Remove obsolete committed/active protocol coupling when independent,
otherwise record its exact cutover obligation. No new login-route defenses here.

Run focused provisioning/account composition and ownership/rollback tests,
independent backend review and final make build. No development-host installation.
Hand precise account/session and owned-state interfaces to C02c2/C02c.
