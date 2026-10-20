# R02c — Add the automatic-service proof fixture

Acceptance: host

Required tasks: R02a — entry/activation boundary; R02b — companion PAM fixture.
Estimate: 20–30 minutes.

Read the [master early proof](../Kiosk-Resilience-Plan.md#acceptance), accepted
activation design, [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[UI mandate](../Mandates/UI-Automation-Mandate.MD) and maintained fixture owners.

## Session boundary and deliverable

Extract one unfamiliar administrator-owned host user service that automatically
activates and can expose an external launch UI. Use the selected startup/activation
mechanism; explicit launch alone is no proof of automatic activation. Provide an
ordinary-account control proving activation and the launch route work, plus kiosk
entry/genuine-approval and excluded-or-confined launch controls. The child uses
exposed UI; no assumed arbitrary code execution or new service-name mask qualifies.

Read full unit/generator/D-Bus/provider call paths actually used. Reuse public
semantic operations and baseline fixture ownership; do not add a coordinate or
presentation-adapter campaign. R02 owns final mixed proof composition.

## Acceptance and close-out

Run finite host activation/composition, observation, restoration and interrupted
cleanup checks. Review resource/parallelism/storage effects and keep reusable
inputs in maintained baseline preparation. Record exact registered inputs/callables
and test-double limits for both installed proofs; no live acceptance occurs here.
Apply master product review/build/localization gates to product changes and finish
owned cleanup.
