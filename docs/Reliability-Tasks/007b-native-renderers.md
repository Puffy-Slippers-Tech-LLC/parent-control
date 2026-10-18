# 007b — Native renderer functions and isolation

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 006, 007a, 007c.
Estimate: 30–60 minutes.

## Session boundary

Deliver compositor/service and GTK request-app rendering and native isolation.
006 supplies filesystem isolation; 007a supplies the host role matrix; 007c
supplies notification-provider rendering/isolation. Cumulative scope retains
all three native roles. Session exception: the compositor and request app jointly
produce one usable confined form, with enforcing controls on both targets.

## Deliverable and route

Extract native functional rendering/isolation from 007. Read the
[renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs)
and complete platform/confinement qualifier and role-census helpers. Inspect
actual VM capabilities before selecting finite bindings. Planned selector
(unimplemented): `test_kiosk_renderer_roles[compositor_request_app]`, area `enforcement`.

Exercise compositor and GTK request app through native supported VM paths with
security enforcing. Observe usable request content, not just process existence.
Record renderer, libraries, available devices, role identities and strict
waiting-session census. Use
existing native access-denial/positive-control bindings for available resources.
On Fedora retain `dri_device_t` mapping evidence wherever actually exercised.
Keep 007a's generated-policy proof distinct from native allows/denials.

## Work sequence

1. Verify the candidate and available renderer path; review applicability of
   007c's notification receipts rather than inheriting its VM state.
2. Start a fresh confined kiosk, record both role identities and independently
   observe usable request content through the shared product API.
3. Exercise applicable native positive/access-denial controls and retain actual
   renderer/device/security provenance for each role.
4. Observe owned shutdown and clean census/resource state. Keep notification
   controls in 007c unless changed shared inputs require their affected rerun.

Software rendering is a valid finite VM binding when the required functional
roles and isolation pass; explicitly retain absent GPU-mapping coverage. Do not
require new virtual GPU/passthrough or label unexercised mappings passing. Missing
capabilities required for these VM results remain blockers under the master's
bounded supporting-work route. Crash/reentry remains in 007.

## Acceptance and close-out

Run affected host policy/ownership checks, then the compositor/request-app result
and native isolation controls on both targets. Retain capability/version/security
provenance, actual results and owned cleanup. Repair narrow demonstrated causes,
build as required and update exact qualified limitations in existing owners.
Close only 007b; its receipts must be rechecked for applicability by consumers.
