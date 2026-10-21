# C09a1 — Preserve native authentication language fallback

Acceptance: host

Required tasks: C09af.
Estimate: 20–30 min.

Apply the [remaining-plan task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract).

## Session boundary and deliverable

Extract native authentication locale/translation coupling from C09a. Read the
actual agent_locale, agent launch and provisioning consumers plus the
[localization owner](../SystemDesign/Localization.md). Address only demonstrated
failure of genuine selected-parent authentication when optional translations or
native locales are unavailable; use safe native/untranslated fallback, including
the finite C/C.UTF-8-only fixture already required by C11a1/C12a1.

Preserve supported personal languages, main features, human decision/password
pauses, genuine parent denial and Cancel. No private runtime or language inventory
may veto core use. Verify an already working fallback instead of adding code.

Maintain focused host regressions and exact installed bindings for C10 and
C11a1/C12a1. Keep those final histories' presentation controls from C09a intact.
Run affected checks, required review and final build for packaged changes; update
all supported languages if user-visible strings change. Host results grant no
installed qualification. Record candidate/evidence impact and owned restoration
in the existing design/test owners.
