# 007a — Renderer mapping permission regression

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Check only the renderer-permission regression behind `4e08dcdb` and its adjacent safety controls.
Read the [renderer contract](../SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs),
[selected session baseline](../SystemDesign/Kiosk-Confinement.md#c02-activated-session-baseline)
and [current test dispositions](../SystemDesign/Kiosk-Confinement.md#c04a-installed-engineering-dispositions).
C02d removed the generated confinement policy and its role matrix; C03/C04
removed its tests/workers. There is no current generator or canonical test to
invoke under the former helper name. Before execution, map this incident's
permission and adjacent controls to the selected renderer/security boundary and
its actual host-test owner. If the current binding is absent, keep this row
unchecked; do not restore private roles or a generated-policy framework.

Retire the former generated private-role `dri_device_t` allow/exclude assertions;
their subjects and generator no longer exist. The surviving outcome is usable
native rendering under the selected enforcing security boundary, with narrow
regressions for any actual permission fix and its justified adjacent safety
controls. Use C06's deliberate-route review to identify those controls at actual
consumed/exposed boundaries. Unrelated roles and unknown ambient files have no
admission vote. Do not expand the incident into a complete role/permission matrix
or native notification feature qualification.

## Acceptance and close-out

Run exact affected renderer/security unit selections through `tools/run-tests
unit` with explicit timeouts. Assert the actual selected source/permission
boundary and its normal-use/safety controls, fix demonstrated defects and retain
passing evidence. Review resources and build after product/build-input edits.
Close only 007a. Host checks do not establish actual device mapping or usable
startup; 007b owns that incident path. This reconciliation supplies no host pass.
