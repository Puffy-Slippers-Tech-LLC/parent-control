# C02a — Prepare the release-based session runtime

Acceptance: host

Required tasks: C01.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Reconstruct the pinned release's session desktop, GNOME target and app/agent
service arrangement, using C01's exact boundary. Read data/wayland-sessions,
data/gnome-session, data/systemd/user, the kiosk launcher and current native
session/agent callers. Connect to current feature entrypoints, not release UI.

Prepare only the replacement runtime and directly needed integration/tests.
Keep the replacement unselected until C02's cutover. The current selected
entry/session path must remain coherent and buildable. Reserve all production
selector and entry activation changes for C02; no competing admission path.
Record the prepared interface and its activation dependency in the design owner.

Verify commands, session identity, stop/exit ownership and packaging composition
with affected host tests. Preserve current notification and authentication-agent
behavior. Hand C02b/C02c exact interfaces and activation obligations. Apply the
master's product review and build gates; a prepared runtime is not live usability.
