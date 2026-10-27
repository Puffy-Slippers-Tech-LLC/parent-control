# U03 — Allow entry after brief admission contention

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U02.
Estimate: 30–60 min; session exception: one transient-contention/reentry history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read the [lease boundary](../SystemDesign/Kiosk-Confinement.md#lease-and-lifecycle-boundary),
`tools/pam_oh_no_parent_control.c`, `tools/oh-no-parent-control-kiosk-lifecycle`
and their lifecycle writers/readers. Discover complete lock/recovery tests first.

Trace immediate nonblocking-lock rejection. Add bounded waiting/retry only for
demonstrated transient contention. Never wait indefinitely or admit during
exclusive maintenance. Preserve identity, same-handle authorization and live
writer ownership. Stale lock/barrier repair belongs to U03a; do not delete or
adopt state to make contention disappear.

Host checks cover transient release, persistent contention/deadline and ownership
controls. Installed checks use one transient writer history, followed by the
master's bounded entry/use/reentry
control and ordinary-account login for shared PAM changes. Missing/unsafe state
is not proof of an attack or permission to bypass authority. Require scoped
checks, backend review/build and cleanup; close only U03.
