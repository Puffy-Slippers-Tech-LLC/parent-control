# C08a — Protect exposed launch actions

Acceptance: host

Required tasks: C07bf.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Implement C06's finite exposed-action entries at the actual public action or
handler boundary. Cover reachable links, chooser actions and automatic launches,
preserving the request form, genuine approval and retained main features.
Preserve the local desktop barriers in the confinement design; record newly
exposed desktop gaps there and include affected checks with the concrete change.

A blocked optional launch must not make core use fail. Retain ordinary-user
behavior and local UI coverage for the shared overlay. Add matching targeted
tests and finite installed bindings for each deliberate action and permitted
control. Do not turn widget mechanics into extra customer journeys.
Read the UI mandate for adapter changes; require review and final build.
