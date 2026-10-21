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
pre-form crash. 007a supplies the current renderer/security boundary's host regression.
Unrelated writable-directory variants from 006a/006b are not prerequisites.
Read the [renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
[crash diagnosis](../SystemDesign/Logging-and-Feedback.md#kiosk-startup-crash-diagnostics)
and the [current engineering dispositions](../SystemDesign/Kiosk-Confinement.md#c04a-installed-engineering-dispositions).
The former platform/native-loading qualifier and strict role census were
removed; the retained census is session-identity-only and proves no device
mapping or confinement. Map a maintained incident-specific renderer/provenance
binding before execution, preserving the actual GPU-mapping requirement below;
if unavailable, keep this row unchecked. Do not recreate a platform matrix.

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
   the real GPU character-device mapping under the selected enforcing policy.
   Record the actual device/context and startup outcome; the removed private
   MAC role/type mapping is not required. A software-renderer result
   without that mapping is useful limited evidence, not the missing GPU regression.
   Ubuntu supplies the corresponding usable enforcing startup control with its
   actual backend/path explicitly recorded.
4. Exit through station Cancel, observe usable GDM and compare the owned
   renderer/process/unit resources with their recorded baseline. Complete
   owned cleanup. A session-only census cannot supply the mapping proof in step 3.

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
