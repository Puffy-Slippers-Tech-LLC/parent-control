# D02 — Review the minimal desktop protection design

Acceptance: review

Required tasks: D01r.
Estimate: 20–30 min.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract).

## Session boundary and deliverable

Review D01/D01r's finite full-desktop maps against complete affected functions,
callers and shared state. Allocate graphical-session admission to C07a,
request-session desktop escapes to C07s and the named remote provider to C07.
Each barrier needs a
deliberate-child negative and working request-only/ordinary-account controls.
Existing working barriers need verification, not new infrastructure.

Obtain independent Astra xHigh design review with explicit Usability priority
and Threat scope passed/failed findings. Resolve actionable findings before
completion. Retain ordinary trusted loading, parent approval and main features;
no global inventory, private runtime or broad authentication redesign.
Also require Denylist/default access passed/failed under the master's narrow
denylist: inspect all affected refusal/default/error branches and pair each
specific attack predicate with benign adjacent/unknown access controls. Prefer
blocking the prohibited action over rejecting entry to the request app.

Keep the reviewed map in the design owner. Each implementation slice remains
limited to its named boundary and directly affected regressions. Independent
implementation/qualification work follows the selected-consumer prerequisite
contract. Run links/plan checks; no implementation or live acceptance here.
