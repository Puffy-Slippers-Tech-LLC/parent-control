# 007 — Native VM renderer roles and crash recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and route

Required tasks: 006.
Read the [master](../Reliability-Plan.md),
[renderer role contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
[crash diagnostics](../SystemDesign/Logging-and-Feedback.md#kiosk-startup-crash-diagnostics),
policy generation and the existing platform/confinement qualifier call chains.

Planned selector (unimplemented): `test_kiosk_renderer_role_recovery`, area
`enforcement`, reusing the native platform and waiting-session census helpers.
Read actual VM rendering capabilities before choosing the finite binding.

## Finite history and expected results

Exercise the compositor, GTK request app and notification provider through their
native supported VM rendering paths with enforcing security enabled. Record
the actual renderer, libraries, available devices and confined role identities.
On Fedora, retain native `dri_device_t` mapping evidence wherever that path is
actually exercised. A software path supplies functional renderer evidence only;
it cannot qualify an unobserved GPU mapping.

Independently regress the complete generated role-permission matrix at host
scope: only the compositor/service, request-app and notification-provider roles
receive the narrow character-device mapping permission, with no new executable
transition or general device permission. Use existing applicable native
access-denial/positive-control bindings for the guest's available resources.
Keep host policy results distinct from actual native allow/deny evidence.

Observe usable request content and a genuine notification, not merely a live
process. In a separate owned engineering branch, terminate only the exact
recorded app process to exercise abnormal session shutdown. Require bounded
return to usable GDM, preserved crash outcome and a fresh successful kiosk
entry; no broad process-name signal or global security disable is allowed.
Task 010 owns full diagnostic-export survival.

The finite installed acceptance is the native renderer paths available in the
two registered VMs, all three functional roles, enforcing isolation and
crash/reentry. Software rendering is a valid VM binding when those results pass;
record absent GPU-mapping coverage explicitly instead of requiring a new virtual
GPU or passthrough capability. A missing capability needed for these required
VM results remains a blocker under the master's bounded supporting-work route.
Never label an unexercised mapping passing or change product permissions solely
to make qualification possible.

## Validation and close-out

Run affected host policy, diagnostic-provenance and ownership/cleanup tests.
Qualify actual rendering, restriction and crash/reentry on both targets; retain
renderer/security/version provenance and the strict role census. Fix root causes
with the narrow required permission or lifecycle handling, build as required
and update exact qualified scope in the existing owners.
