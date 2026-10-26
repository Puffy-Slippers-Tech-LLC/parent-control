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
Apply the master's [simple implementation rule](../Kiosk-Desktop-Plan.md#simple-implementation):
prefer removal or existing supported configuration, then a direct fix at its
owner. Review the [test scope](../Kiosk-Desktop-Plan.md#simple-tests) too: reuse
coverage, select representative cases for distinct gaps and remove incidental
journey steps. Justify extra machinery only where the direct approach cannot
meet the required outcome. Keep the rationale in the existing design note.

Obtain independent Astra xHigh design review with explicit Usability priority
and Threat scope passed/failed findings. Resolve actionable findings before
completion. Retain ordinary trusted loading, parent approval and main features;
no global inventory, private runtime or broad authentication redesign.
Also require Denylist/default access passed/failed under the master's narrow
denylist: inspect all affected refusal/default/error branches and pair each
specific attack predicate with benign adjacent/unknown access controls. Prefer
blocking the prohibited action over rejecting entry to the request app.

Review the master's resilient admission dispositions as well as attack negatives.
Require an observable predicate for each precise desktop attempt and its actual
selected-session/launch boundary; saved defaults or an unknown service name are
not proof. Pair it with the benign adjacent input and affected fault/restoration
control. Preserve real lifecycle/admin barriers without treating ordinary faults
as attacks or weakening PAM authentication globally.

Freeze one small defect/boundary per product task, existing both-target usability
bindings, explicit timeouts and any missing qualification prerequisites. Prepare
those prerequisites before product editing. Split independent work if a fix,
review/build and the short both-target gate cannot fit 30–60 minutes. Do not move
its gate to a later task or expand it to a general feature campaign.

Keep the reviewed map in the design owner. Each implementation slice remains
limited to its named boundary and directly affected regressions. Independent
implementation/qualification work follows the selected-consumer prerequisite
contract. Run links/plan checks; no implementation or live acceptance here.
