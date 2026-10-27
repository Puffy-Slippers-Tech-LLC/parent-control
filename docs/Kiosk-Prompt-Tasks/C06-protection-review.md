# C06 — Review the minimal remaining protection design

Acceptance: review

Required tasks: C06i.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Review C06a's login map, C06x's exposed-action map and C06i's consumed-input map
against complete affected functions/callers and shared state. Discovery is owned
by those prerequisites. Pair every proposed refusal with the
child's demonstrated access/deliberate action, prohibited result and working
normal-use control. Trust installed Python/GTK/GI/native code and lazy loading;
exclude child-controlled inputs at their real consumer boundary.

Consolidate the reviewed dispositions in the existing design owner. Allocate exact
remaining boundaries to C07t/C07b and C08a/C08. Full graphical desktop routes
remain documented in the confinement design. No new custom loader, global roster,
private runtime image or continuous library audit. Essential-service faults and
genuine parent/admin denial are separate from deliberate breaches.
Apply [simple product and tests](../Kiosk-Session-Confinement-New-Plan.md#simple-product-and-tests):
review both the proposed product fix and its test design against the direct
approach at the existing owner. Reuse effective barriers, coverage and qualified
operations; justify any necessary new abstraction, persistent state or test
machinery against a concrete gap. Keep this rationale in the existing design
note, without a separate review artifact or checker.

Apply the master's [confinement priority](../Kiosk-Session-Confinement-New-Plan.md#confinement-priority):
preserve the existing desktop boundary and document newly demonstrated
desktop gaps with their affected checks; review the remaining prohibited results.

Obtain independent Astra xHigh review with explicit Usability priority and
Threat scope passed/failed findings, resolving failures before completion.
Require Denylist/default access passed/failed too: inspect affected default/error
branches, reject only specifically justified deliberate attack predicates and
preserve passwordless app access for benign adjacent or unknown configuration.
Keep future queue scopes unchanged; unforeseen work is inserted only when its
consumer is selected. Check links/plan metadata. No implementation or live pass.
