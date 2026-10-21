# C07 — Protect the supported remote-desktop route

Acceptance: host

Required tasks: C07b.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use the provider chosen and justified in C06a; inspect its actual authentication/
session path rather than assuming SSH/GDM PAM behavior. Keep ordinary-account
remote use working while refusing kiosk desktop access through that provider.
Do not claim protection for providers outside the reviewed scope.

Update exact host tests and installed provider/ordinary-account positive and
kiosk-negative bindings. Missing reusable provider automation requires a bounded
installed qualification prerequisite, not a host-only qualification claim or
service-disable shortcut. Check cumulative C07a/C07b route coverage, then run
affected tests, independent review and final build. Preserve known limitations.
