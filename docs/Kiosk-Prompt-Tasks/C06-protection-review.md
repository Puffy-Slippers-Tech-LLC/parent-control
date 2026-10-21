# C06 — Review exposed routes and minimal protection design

Acceptance: review

Required tasks: C06a.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Inspect actual links, choosers, handlers, shortcuts, automatic exposed launches
and consumed startup/settings inputs. Pair every proposed refusal with the
child's demonstrated access/deliberate action, prohibited result and working
normal-use control. Trust installed Python/GTK/GI/native code and lazy loading;
exclude child-controlled inputs at their real consumer boundary.

Combine this with C06a's login map in the existing design owner. Allocate exact
boundaries to C07a/C07b/C07 and C08a/C08. No new custom loader, global roster,
private runtime image or continuous library audit. Essential-service faults and
genuine parent/admin denial are separate from deliberate breaches.

Obtain independent Astra xHigh review with explicit Usability priority and
Threat scope passed/failed findings, resolving failures before completion.
Keep future queue scopes unchanged; unforeseen work is inserted only when its
consumer is selected. Check links/plan metadata. No implementation or live pass.
