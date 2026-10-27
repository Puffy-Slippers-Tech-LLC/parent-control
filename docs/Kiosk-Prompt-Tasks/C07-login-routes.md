# C07 — Protect the supported remote-desktop route

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C07s, C07r1, C07r2, C07r3, C07r4.
Estimate: 30–60 min; session exception: one small confinement fix, review/build and both-target usability.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use the provider chosen in D01r and reviewed in D02; inspect its actual authentication/
session path rather than assuming SSH/GDM PAM behavior. Keep ordinary-account
remote use working while refusing kiosk desktop access through that provider.
The [reviewed route](../SystemDesign/Kiosk-Confinement.md#d01r-remote-desktop-route-review)
is GNOME Remote Desktop system Remote Login over RDP, followed by remote GDM.
Complete D02's allocations from the [qualification gap](../TestAutomation/E2E-Building-Blocks.md#remote-login-qualification-gap)
before product editing. The existing vendor password gate may already suffice;
retain it without duplicate code if the real positive/negative checks pass.
The [frozen D02 design](../SystemDesign/Kiosk-Confinement.md#d02-minimal-desktop-design-decision)
allocates four small installed slices: preparation, safe connection/ownership,
ordinary remote desktop use, then the station attempt and recovery. These are now
queued immediately before this task as C07r1–C07r4. Complete them before editing;
split a slice further if it cannot fit 20–30 minutes including restoration.
Do not claim protection for providers outside the reviewed scope. Implement one
narrow provider boundary; do not replace shared passwordless authentication or
deny all unfamiliar PAM services. Split independent defects before editing.

Reuse or adapt existing host tests and installed provider/ordinary-account
positive and kiosk-negative bindings under [simple tests](../Kiosk-Desktop-Plan.md#simple-tests).
Cover distinct provider behavior without duplicating shared guard matrices.
Missing reusable provider automation requires a bounded
installed qualification prerequisite before product editing, not a host-only qualification claim or
service-disable shortcut. Check cumulative local/remote desktop coverage, then run
affected tests, independent review and final build. Preserve known limitations.

Before completing, pass the master's
[bounded confinement usability check](../Kiosk-Desktop-Plan.md#bounded-confinement-usability-check)
and directly affected benign/fault controls on both targets with this candidate.
Finish owned restoration. Either target failing or not run keeps the task open
before automatic commit/push. The named provider's complete ordinary-account
positive and kiosk-desktop negative remain C11f/C12f acceptance; an unavailable
provider cannot count as protection or excuse a broken normal kiosk login.
