# 007b — Native renderer functions and isolation

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 006, 007a.
Estimate: 45–75 minutes.
Session exception: all three actual confined renderer roles and enforcing
controls require complete installed qualification on both targets.

## Deliverable and route

Extract native functional rendering/isolation from 007. Read the
[renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs)
and complete platform/confinement qualifier and role-census helpers. Inspect
actual VM capabilities before selecting finite bindings. Planned selector
(unimplemented): `test_kiosk_renderer_roles`, area `enforcement`.

Exercise compositor, GTK request app and notification provider through native
supported VM paths with security enforcing. Observe usable request content and
a genuine notification, not just process existence. Record renderer, libraries,
available devices, role identities and strict waiting-session census. Use
existing native access-denial/positive-control bindings for available resources.
On Fedora retain `dri_device_t` mapping evidence wherever actually exercised.
Keep 007a's generated-policy proof distinct from native allows/denials.

Software rendering is a valid finite VM binding when the required functional
roles and isolation pass; explicitly retain absent GPU-mapping coverage. Do not
require new virtual GPU/passthrough or label unexercised mappings passing. Missing
capabilities required for these VM results remain blockers under the master's
bounded supporting-work route. Crash/reentry remains in 007.

## Acceptance and close-out

Run affected host policy/ownership checks, then the three functional roles and
native isolation controls on both targets. Retain capability/version/security
provenance, actual results and owned cleanup. Repair narrow demonstrated causes,
build as required and update exact qualified limitations in existing owners.
Close only 007b; its receipts must be rechecked for applicability by consumers.
