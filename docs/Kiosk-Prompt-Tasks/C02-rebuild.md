# C02 — Activate the rebuilt baseline and retire v1.4 confinement

Acceptance: host

Required tasks: C02c.
Estimate: 30–45 min; session exception: atomic activation and owned-state cutover.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use the delivered C02a runtime, C02b1/C02b approval integration and
C02c1/C02c2/C02c account/lifecycle/PAM slices. Perform the single production
activation and package-wiring cutover to release-based confinement. Preserve
their cumulative behavior. This is host composition/build work; do not install
on the development host.

Disconnect superseded production selectors, fallback paths and temporary live
adapters. Activate C02c2's owned upgrade/removal handling in this transaction;
existing installations cannot remain dependent on the old framework. Do not
delete arbitrary installed files or live sessions. C02d/C02e immediately delete
now-unconsumed committed and old-plan active source, generated-input definitions
and residual wiring before C03 or live baselines.

Update directly affected tests/registrations so the cutover builds and its
selected checks pass. C03/C04 own remaining audit work, not knowingly broken
dependencies. No v1.4 implementation remains active as a hidden fallback.
Remaining dead source has an exact C02d/C02e removal entry, not an exemption.
Update actual design, obtain independent product/backend review and run final
make build. Hand exact source/removed-interface/test dispositions to C02d.
Public usability and new route defenses remain later gates.
