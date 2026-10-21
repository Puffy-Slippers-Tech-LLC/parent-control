# D02 — Review the minimal desktop protection design

Acceptance: review

Required tasks: D01.
Estimate: 20–30 min.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract).

## Session boundary and deliverable

Review D01's finite full-desktop map against complete affected functions,
callers and shared state. Allocate the narrow local session/desktop-escape
boundary to C07a and the named remote provider to C07. Each barrier needs a
deliberate-child negative and working request-only/ordinary-account controls.
Existing working barriers need verification, not new infrastructure.

Obtain independent Astra xHigh design review with explicit Usability priority
and Threat scope passed/failed findings. Resolve actionable findings before
completion. Retain ordinary trusted loading, parent approval and main features;
no global inventory, private runtime or broad authentication redesign.

Keep the reviewed map in the design owner. Each implementation slice remains
limited to its named boundary and directly affected regressions. Independent
implementation/qualification work follows the selected-consumer prerequisite
contract. Run links/plan checks; no implementation or live acceptance here.
