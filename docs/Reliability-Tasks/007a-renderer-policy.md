# 007a — Renderer mapping permission regression

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Check only the policy change behind `4e08dcdb` and its adjacent safety controls.
Read the [renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
`tools/kiosk_confinement_policy.py`, the complete affected generation call chain
and canonical policy tests. Map existing assertions before adding coverage.

The compositor/service, request-app and notification-provider roles alone
receive the narrow character-device mapping permission for Fedora
`dri_device_t`. Check those required grants, exclusion of other roles from this
permission, and absence of a new executable transition or general device-map
grant. Do not expand this into a complete role/permission matrix or native
notification feature qualification. Preserve existing broader policy tests.

## Acceptance and close-out

Run exact affected policy unit selections through `tools/run-tests unit` with
explicit timeouts. Assert against actual generated policy, fix demonstrated
generation defects and retain passing evidence. Review resources and build
after product/build-input edits. Close only 007a. Generated policy does not
establish actual device mapping or usable startup; 007b owns that incident path.
