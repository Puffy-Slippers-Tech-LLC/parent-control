# 007c — Native notification-provider isolation

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 006, 007a.
Estimate: 30–60 minutes.
Session exception: real notification rendering, enforcing role controls and
owned closure require complete installed qualification on both targets.

## Deliverable and route

Extract notification-provider rendering/isolation from 007b. 006 supplies native
filesystem isolation; 007a supplies the host role-permission matrix. Read the
[renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
complete platform/confinement and role-census helpers, and the existing reminder
preview operations in `tests/e2e/accessible_ui.py`. The installed
`check_e2e_kiosk_notification_wellbeing.py` route demonstrates functional preview,
but does not establish this native role/security qualification. Reuse its minimal
shared preview/Cancel operations without adding the unrelated wellbeing matrix.
Planned selector (unimplemented):
`test_kiosk_renderer_roles[notification_provider]`, area `enforcement`.

## Work sequence

1. Start a fresh confined kiosk on an available supported VM renderer path with
   security enforcing. Record the waiting-session census and exact provider role,
   renderer, libraries, available devices and security context.
2. Use the public reminder-preview operation and independently observe actual
   notification content. Process existence alone cannot prove rendering.
3. Apply existing native positive/access-denial controls for that provider's
   available resources. Retain Fedora `dri_device_t` mapping evidence only where
   actually exercised; keep generated-policy proof separate from native results.
4. Cancel the preview, observe closure and unchanged reminder state, then
   complete owned cleanup and check the role census.

## Acceptance and close-out

Run affected host policy/input/ownership guards before the complete functional
and native-isolation branch on both targets. Retain renderer/version/security
provenance, independent results and cleanup receipts. Software rendering is a
valid binding with explicit absent GPU-mapping coverage; an unsupported required
capability remains a blocker. Repair narrow demonstrated causes and follow
master build/registration/evidence rules. Close only 007c. Compositor/request-app
qualification remains in 007b and crash/reentry in 007.
