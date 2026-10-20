# C01 — Define the v1.3 session-confinement boundary

Acceptance: review

Required tasks: C01c.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use the cumulative C01a/C01b/C01c table to classify each mechanism: reconstruct the
release session-confinement slice, retain current feature/policy behavior, or
remove superseded confinement-only code. Name the receiving C02 preparation,
activation or C02d/C02e removal owner for each interface and directly affected
tests. Account separately for checked-in code and old-plan active changes.
Delete obsolete old-plan work as needed; do not retain legacy/garbage code,
unselected implementations or speculative shims to preserve past effort.

Retain language/preferences, duration controls, notifications, What's New,
artwork, feedback and shared child-overlay behavior. Preserve broker caller
validation, genuine parent authentication, cancellation and grant/time/app
semantics; classify active visit/receipt coupling by behavior, not filename.
Do not restore whole shared files. The release GDM PreSession hook is historical
source, not a qualified current-GDM enforcement route.

Resolve prospective design conflicts in the confinement owner and identify
reliability/proof consumers for C04. Remove the obsolete R-series programme's
prospective instructions; keep accurate current implementation descriptions
until their cutover. Record remaining ordinary-child route gaps for C06a/C06.
Obtain independent Astra xHigh review of provenance and feature
preservation. No product changes or new loader architecture. Record sizing
risks without changing later queue rows; the selected consumer owns any future
prerequisite insertion. Links/plan checks and resolved review findings close this
review; no installed acceptance is claimed.
