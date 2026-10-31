# 197a — Approve a request and sign in as the chosen child

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW20 kiosk new/open form with fresh-child destination**. Named consumer: task **197k** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021a** — Fixed kiosk FLOW05/06 approval and automatic GDM return.
- **052** — TIME01 child-desktop presence and limits-off absence.

## Implementation

Inspect [313's shared delivery](../E2E-Building-Blocks.md#cross-plan-baseline-reuse)
first and reuse applicable request/grant/countdown and fresh-child leaves.
Its fixed Riley/Jamie/600-second/soft-included history does not qualify this
task's new/open form and account/soft-choice arguments. Implement only missing
bindings and retain the declared representative qualification below.

Compose kiosk FLOW04/FLOW05 with explicit fresh FLOW15 and countdown comparison. Accept GDM or an independently open station form; no implicit policy setup.

Reuse `request_flow.prepared_request`, `kiosk_approved_flow.approved_request`,
`journey_blocks.desktop_entry(entry='fresh')` and
`KioskRequestJourney.check_countdown`. Current approval leaves are the fixed
75-second/soft-included Riley/Jamie binding plus 313's finite 600-second work;
explicitly implement the remaining shared
FLOW20 caller-owned child, eligible-parent, duration and soft-choice arguments.
Bound them to Jordan/Riley, Jamie/Casey (the recipe's Sam), soft excluded/included
and the consuming recipes' finite 30/60/75/120/150/180/600/900/1200/7200-second requests.
Carry the selected child through real authentication, fresh destination identity
and public arithmetic comparisons. TIME01's
existing fresh-child entry supplies the necessary destination; no retained child
or Parent desktop is required for this slice.

## Live VM acceptance

Qualify new-form Riley/Jamie/30-second/soft-excluded and independently open-form
Jordan/Casey/75-second/soft-included requests with fresh-child destinations in
fresh guarded attempts. Publicly prepare 30 daily minutes for that child and
read at least 900 seconds of actual daily remaining before each approval;
these small additions test arguments and arithmetic, not short access lifetimes.
Keep zero-daily natural-expiry consumers on their own recipe profiles under
[explicit time preparation](../E2E-Scenario-Recipes.md#explicit-time-preparation).
Approve once per invocation, read success and automatic
exit, then perform the selected child's fresh entry and compare countdown with
elapsed-time bounds. These representative argument bindings qualify the shared
finite API; later cases own their exact values and histories, with no Cartesian
qualification matrix.

Implementation uses `kiosk_fresh_return.NEW_PLAN` / `OPEN_PLAN` and
`KioskFreshReturnJourney`, dispatched by `onpc_request_flow::kiosk_fresh_return`.
The shared `request_flow.approval_and_return(surface='kiosk', child_entry='fresh')`
composes caller-bound preparation and `kiosk_approved_flow.approved_request(explicit=True)`.
`JourneyPlan.kiosk_request` carries the same finite binding through the public
form, MATE recipient checks, credential owner and child countdown.

Focused qualification selector (not a standalone integration registration):

```sh
tools/run-tests integration check_e2e_kiosk_fresh_return
```

## Current blocker

Implementation and affected host validation pass. The developer authorized a
one-time preparation-tool repair in this session: single-VM preparation now
clears the inherited batch marker and preserves workflow context. Guarded,
nondeleting recovery verified and transferred the recorded standalone package
bundle; app-snapshot preparation and maintenance cleanup passed.

The next Ubuntu live attempt passed the earlier queue refusal, acquired and
isolated the VM, then stopped at
`fixtures:runner-not-qualified-for-clean-snapshot` before any parent/child
action. Both representative profiles remain unqualified. The retained runner
report is `output/test-runs/host/reports/20261031T040247Z-124beb24`;
owned cleanup and baseline restoration passed. Secondary final-provenance and
uncaptured-input failures are retained in that report.

Resume with GPT-6.1 Sol High. Investigate this newly retained failure in the next
session under the shared failure/diagnosis contract; preserve the fixture guard,
public assertions and current task order. No repair or live retry of this new
failure was attempted in this session.
