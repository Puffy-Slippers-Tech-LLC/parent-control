# U01 — Keep approval working with only basic locales

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: Baseline.
Estimate: 30–60 min; session exception: one complete basic-locale fallback/restoration history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read [native authentication fallback](../SystemDesign/Localization.md#native-authentication-fallback),
`kiosk/oh_no_parent_control_kiosk/agent_locale.py`, its preparation callbacks in
`main.py` and the vendor-agent unit/callers. Discover existing locale regressions.

Remove the demonstrated non-C locale requirement
using safe native/source-text fallback. Preserve saved language, genuine
selected-parent authentication and its vendor helper. No custom password dialog,
translation inventory, global locale changes or authentication bypass.

Cover C/C.UTF-8-only inventory at the host layer. Discovery succeeds in this
task; U01a owns discovery failure and reuses this fallback.
Qualify this installed fallback with a genuine approval and
observed intended time access, denial/Cancel without a grant, and restored normal
language/request use. This is not an all-language matrix.
Do not treat a completed systemd restart as proof of a visible working agent.
Run affected regressions, required review/build and owned restoration before
closing only U01.
