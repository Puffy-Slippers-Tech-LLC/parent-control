# C07su — Verify normal kiosk use after C07s on Ubuntu

Acceptance: installed
Targets: onpc-Ubuntu26.04

Required tasks: C07s.
Estimate: 30–60 min; session exception: complete core customer history and restoration.

Apply the [usability stop gate](../Kiosk-Desktop-Plan.md#usability-stop-gate)
and the [owning task contract](../Kiosk-Desktop-Plan.md#task-execution-contract).

## Session boundary and deliverable

Verify the exact candidate delivered by C07s, including required review/build
and registered operation qualification. On onpc-Ubuntu26.04, apply the complete
core-use history and affected feature/shared-overlay/pause controls required by
the usability stop gate above. Use registered inputs and an explicit timeout;
do not infer a selector from this task ID.

Trust completed checks for unchanged scope. A concrete change needs affected
complete histories; expired reports do not require reruns. A rejected normal
session or diagnostic-only form keeps this gate open. Return corrections through
bounded prerequisites before the next protection slice. Record a short result
and finish owned restoration. This grants no route-negative, fault/recovery or
other-target acceptance.
