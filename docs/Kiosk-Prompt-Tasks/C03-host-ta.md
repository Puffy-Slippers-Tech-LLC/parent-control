# C03 — Finish shared-form and host automation alignment

Acceptance: host

Required tasks: C03b.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Audit the shared request-form UI tests and current feature units using C01's
preservation map. Keep language/preferences, presets, notifications, What's New,
feedback, optional style fallback, safe Cancel/exit and human-pause behavior.
Run both kiosk and child-overlay parameters for changed shared behavior.

Complete the cumulative C03a1/C03a/C03b host map for checked-in coverage and all
old-plan active additions: every removed mechanism's
fixture/import/registration is removed or mapped to its surviving behavior owner.
No legacy or unfinished garbage test remains solely to preserve old-plan work.
Use focused unit/UI checks, not an all-product suite. Read the UI mandate before
UI automation work. C04 receives coherent shared APIs and remaining installed
coverage gaps; host results grant no installed acceptance.
