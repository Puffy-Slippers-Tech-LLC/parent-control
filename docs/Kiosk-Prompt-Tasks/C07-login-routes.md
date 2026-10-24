# C07 — Protect the supported remote-desktop route

Acceptance: host

Required tasks: C07sf.
Estimate: 20–30 min.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use the provider chosen in D01r and reviewed in D02; inspect its actual authentication/
session path rather than assuming SSH/GDM PAM behavior. Keep ordinary-account
remote use working while refusing kiosk desktop access through that provider.
Do not claim protection for providers outside the reviewed scope.

Reuse or adapt existing host tests and installed provider/ordinary-account
positive and kiosk-negative bindings under [simple tests](../Kiosk-Desktop-Plan.md#simple-tests).
Cover distinct provider behavior without duplicating shared guard matrices.
Missing reusable provider automation requires a bounded
installed qualification prerequisite, not a host-only qualification claim or
service-disable shortcut. Check cumulative local/remote desktop coverage, then run
affected tests, independent review and final build. Preserve known limitations.
