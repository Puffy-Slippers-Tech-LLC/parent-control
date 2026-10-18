# 007a — Renderer role permission matrix

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract the generated policy matrix from 007. Read the
[renderer role contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
`tools/kiosk_confinement_policy.py`, complete role-policy generation call chains
and canonical policy regression tests before editing.

Regress the complete generated role-permission matrix. Only the
compositor/service, request-app and notification-provider roles receive the
narrow character-device mapping permission for Fedora `dri_device_t`. Assert
all excluded roles, no new executable transition and no general device mapping
permission. Preserve existing platform isolation rules and native positive/
negative control definitions. Add missing assertions without duplicating a full
policy fixture or changing permissions just to enable a test renderer.

## Acceptance and close-out

Run exact affected policy unit selections through `tools/run-tests unit` with
explicit timeouts. Assert both required grants and every excluded role/permission
against actual generated policy. Fix demonstrated policy-generation defects,
review resource changes, build after product/build-input edits and retain actual
passing evidence in existing owners. Close only 007a. Host policy results
establish neither native mapping nor usable renderer roles; 007b owns those.
