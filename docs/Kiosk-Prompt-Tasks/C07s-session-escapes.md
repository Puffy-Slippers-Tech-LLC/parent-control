# C07s — Prevent desktop launches from the request session

Acceptance: host

Required tasks: C07af.
Estimate: 20–30 min.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract).

## Session boundary and deliverable

Extract request-session desktop escapes from C07a. Use D01/D02's finite actual
action/launch callers and add only missing barriers to actions yielding a full
kiosk desktop. C07a owns graphical-session admission; standalone terminal/TTY,
SSH and other exposed-action results retain their remaining-plan owners.

Cover each justified barrier with permitted form/genuine approval controls and
ordinary-account/shared-overlay behavior. Reuse applicable checks for effective
routes. Follow [simple tests](../Kiosk-Desktop-Plan.md#simple-tests): update
directly affected host regressions and local installed bindings consumed by D03
and C11d/C12d; add cases only for uncovered outcomes and keep stable case IDs.

Run scoped checks, required independent backend review where triggered and the
final packaged-input build. New independent provider automation needs a bounded
installed prerequisite before its consumer; a host pass grants no qualification.
Record the finite changes, candidate/evidence impact and owned restoration in the
existing design/test owners.
