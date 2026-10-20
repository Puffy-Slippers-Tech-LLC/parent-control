# R01a — Choose the execution and activation boundary

Acceptance: review

Required tasks: Baseline.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md),
[architecture decisions](../SystemDesign/Kiosk-Confinement.md#architecture-decisions-required-before-the-entry-proof)
and [execution contract](../Execution-Plans.md#execution-and-delegation).

## Session boundary

Extract the execution/activation decision from R01. R01b–R01e own authentication,
approval, configuration and readiness; R01 owns their integrated independent review.
This task selects a mechanism and records its limits; it implements nothing.

## Deliverable and route

Trace actual GDM selection/routing, PAM children, manager startup, first exec,
compositor/form launch and open/setcred/close teardown. Read complete affected
functions and necessary callers/callees in `pam_oh_no_parent_control.c`,
`oh-no-parent-control-login-check`, `kiosk_*startup.h`, preparation/policy modules,
`kiosk_session.c` and packaging session/PAM integration. Record actual inherited
UID/GID/filesystem credentials and where newly owned state is initialized.

Choose one supported boundary with source/public-API basis for both platforms.
Trace consumed code, units, dependencies, drop-ins, generators, D-Bus activation,
module/plugin searches and reload. Classify each as excluded, deliberately
consumed or confined; directory precedence and known-name masks alone are
insufficient. Identify reachable desktop/SSH/exposed-handler routes and actual
child write authority on consumed inputs. Do not infer authority from mode bits
alone or scan unrelated host contents. A read-only mount does not prove backing
byte lifetime. Keep the established compositor/form initially; no universal
executable allowlist or replacement general-purpose image engine.

## Acceptance and close-out

Contribute execution predicates, positive/negative controls and sanitized causes
to the single ledger in the confinement owner. Identify first-exec, pre-boundary
child, automatic-service and teardown witnesses needed by R02a/R02c. Leave
unresolved cross-boundary questions explicit for R01; no architecture acceptance
is claimed until that gate. Check changed links/document consistency, preserve
existing evidence and leave no runtime resources.
