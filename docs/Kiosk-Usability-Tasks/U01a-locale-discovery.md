# U01a — Keep approval working when locale discovery fails

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U01.
Estimate: 30–60 min; session exception: one discovery-failure/restoration history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read [native authentication fallback](../SystemDesign/Localization.md#native-authentication-fallback),
the locale discovery and preparation callbacks in
`kiosk/oh_no_parent_control_kiosk/agent_locale.py` and `main.py`, and discover
their existing tests. Reuse U01's delivered fallback, not its temporary brief.

Select one actual locale-discovery failure and remove its coupling to approval.
Use the safe native/source-text fallback while preserving saved language,
system settings, selected-parent identity and genuine vendor authentication.
A required agent-service failure still fails safely; do not turn all preparation
errors into success or add a locale inventory framework.

Run focused host checks for the selected discovery failure and bounded fallback.
On each target observe genuine approval and intended time access while discovery
is unavailable, then restore discovery and verify normal request use. Retain
affected denial/Cancel controls under the master; do not repeat U01's basic-locale
history. Run required review/build for changes and owned cleanup; close only U01a.
