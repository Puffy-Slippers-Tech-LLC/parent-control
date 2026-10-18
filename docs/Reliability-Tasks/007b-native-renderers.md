# 007b — Native renderer startup regression

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 007a.
Estimate: 30–60 minutes.
Session exception: actual renderer startup, usable form and enforcing native
mapping evidence must describe the same installed attempt on each target.

## Deliverable and route

Reproduce the renderer/confinement boundary behind `4e08dcdb`'s Fedora
pre-form crash. 007a supplies the changed mapping permission's host regression.
Unrelated writable-directory variants from 006a/006b are not prerequisites.
Read the [renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
[crash diagnosis](../SystemDesign/Logging-and-Feedback.md#kiosk-startup-crash-diagnostics)
and complete existing platform/confinement qualifier and role-census helpers.
Extend their incident-specific binding; do not recreate a platform matrix.

Planned selector (unimplemented):
`test_kiosk_renderer_startup_reliability`, area `enforcement`.
Discover actual registration and available VM renderer paths before running it.

## Work sequence

1. Record candidate, renderer/library versions, device availability, native
   security context and exact compositor/app identities. Security stays enforcing.
2. Start a fresh confined kiosk on the supported native path. Independently
   observe a ready usable request form, rather than accepting process existence,
   policy text or a painted frame as the result.
3. On Fedora require evidence that the incident's renderer actually exercises
   the allowed `dri_device_t` character-device mapping. Bind the observation to
   the real role/device and record startup outcome. A software-renderer result
   without that mapping is useful limited evidence, not the missing GPU regression.
   Ubuntu supplies the corresponding usable enforcing startup control with its
   actual backend/path explicitly recorded.
4. Exit through station Cancel, observe usable GDM and compare the owned
   role/resource census with its recorded baseline. Complete owned cleanup.

Keep existing confinement guards and 007a's narrow negative controls. No extra
all-role resource-denial or notification-preview journey is required. Do not
change product permissions to enable a test renderer, disable security or add
GPU passthrough infrastructure. If the registered target cannot exercise the
required Fedora mapping, keep that branch and this task unfinished with exact
capability evidence and a return condition; never label another path equivalent.

## Acceptance and close-out

Run affected host policy/input/ownership checks, then the complete startup result
on both targets. Retain actual renderer/device/security provenance, independent
functional results and cleanup receipts. Repair demonstrated causes at the
owning boundary, build as required and update exact qualified limits in existing
owners. Close only 007b; abnormal exit/reentry remains in 007.
