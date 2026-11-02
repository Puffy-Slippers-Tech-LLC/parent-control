# 007 — Restore the extension when a child signs in or unlocks

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Category: system. Requires: 004. Estimate: 30–60 minutes.
Session exception: keep actual GDM admission and the retained desktop's unlock
in their own complete histories; startup or a synthetic PAM call cannot certify
both graphical results.

Read the [master](../Extension-Plan.md),
[v1.5 recovery entry points](../SystemDesign/Screen-Time.md#screen-time-model),
`system_session_expiry.verify_zero_time_pam`, `system_graphical_expiry.verify` and
the installed PAM/session-limit owner linked from the screen-time design.

Reuse the existing daily-time/no-grant PAM recovery branch and system 282's
native login/retained-session controls. Add only missing v1.5 coverage for a
child with positive native time and enabled saved controls:

- Fresh GDM login after deliberate individual/global disablement.
- One real authentication to unlock a retained child desktop after disablement,
  preserving its session and original work.

Observe the actual login/unlock recovery request and final native active state,
global switch and preserved other-extension choices. A monitor or startup repair
that happened first is not proof of this explicit entry point; use the master's
bounded engineering observation route. Preserve grants, usage and policy rather
than issuing a replacement approval. Existing zero-time denial remains required;
do not turn extension recovery into an admission bypass.

Use maintained GDM/session helpers and secret-recipient guards, without repeating
their qualification matrix or natural-expiry customer journeys. Keep the existing
system binding where possible; any new delta selector remains unimplemented until
registered. Qualify both targets and finish owned cleanup before checking the row.
