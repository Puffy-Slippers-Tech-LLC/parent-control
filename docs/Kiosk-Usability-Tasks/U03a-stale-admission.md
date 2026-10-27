# U03a — Restore entry after stale owned admission state

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U03.
Estimate: 30–60 min; session exception: one owned stale-state repair/reentry history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read the [lease boundary](../SystemDesign/Kiosk-Confinement.md#lease-and-lifecycle-boundary),
`tools/oh-no-parent-control-kiosk-lifecycle`, its lifecycle writers/readers and
the native admission callers. Discover existing lock/recovery tests.

Select one proven owned stale lock/barrier condition that strands entry. Reuse
supported lifecycle repair if effective; otherwise repair its demonstrated gap
at the existing owner. Never repair unknown, substituted or live state from PAM,
delete a marker merely because no lock appears live, or introduce a second
recovery framework. Interrupted configuration remains U05.

Use focused host checks for the chosen repair and its ownership/refusal controls.
On each target observe the exact stale condition, supported repair without manual
state deletion, and the master's passwordless entry/approval/time/reentry result.
Add ordinary login only if shared PAM/session behavior changes. Do not repeat
U03's transient contention history unless this edit affects it. Run required
backend review/build and owned cleanup; close only U03a.
