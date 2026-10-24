# Prevent full desktop access through the kiosk account

Task queue: [Ordered task queue](Kiosk-Desktop-Queue.md).
Next task: **D00 — [Audit the confinement replacement and cleanup boundary](Kiosk-Prompt-Tasks/D00-cleanup-audit.md)**.

## Outcome and scope

Prevent a child from entering a full, unrestricted graphical desktop as the
`oh-no-parent-control` kiosk account. Preserve its passwordless request-only
session, genuine parent approval, time/app enforcement and ordinary-account
desktop access. Cleanup of conflicting unfinished confinement and its obsolete
automation is the first work. Desktop prevention follows cleanup and accepted
baseline use.

Own local graphical-session selection, reachable request-session escapes that
yield a full desktop, and one named supported remote-desktop provider. Review
actual child access and the prohibited result before adding a barrier.

Standalone SSH, terminal/TTY access, other exposed actions/consumed inputs and
general confinement compatibility/recovery improvements belong to
[remaining confinement improvements](Kiosk-Session-Confinement-New-Plan.md),
run by `tools/kiosk-prompt-new`. Its C06a requires this plan's accepted D04 gate.
Neither launcher executes or closes the other's tasks. Allocate a cross-boundary
route's desktop-enabling step here and its other results there; reuse shared
mechanisms and exact applicable evidence without duplicate implementation.

## Usability and threat scope

### Binding planning requirements

These requirements bind this master, every brief and the
[remaining plan](Kiosk-Session-Confinement-New-Plan.md). They replace conflicting
unfinished confinement instructions; historical completion and evidence remain
historical. A task cannot relax them to obtain a pass.

| Requirement | Execution consequence |
| --- | --- |
| Usability first | Passwordless sign-in, a usable request form and the complete approval/time/app journey take priority. |
| Unexpected machine configuration | Unrelated packages, valid service/PAM variation and optional resources cannot veto normal use. |
| Justified protection failures | Every protective refusal needs actual child access, a deliberate breach action, a prohibited result and a working normal-use control. Essential outages need recovery; parent/admin denial remains authoritative. |
| Reasonable-child coverage | Allocate ordinary desktop/session, terminal, TTY, SSH, remote-desktop and exposed-launch attempts to the route owners below. |
| Bounded threat | Exclude very low-level professional/world-class attacks, arbitrary kiosk-code execution premises and unnecessary Python/native-loader hardening. |
| Selected source | Derive only kiosk session confinement from `releases/v1.3`, pinned at `188be907c46b1cd0dabae06ac898c43e75beb05e`, then add justified protections. Never derive it by subtracting restrictions from main/v1.4 confinement. |
| Feature preservation | Retain main's non-confinement kiosk features, authorization, time/app behavior and unrelated code. Do not restore the whole v1.3 kiosk tree. |
| Cleanup priority | D00/D00a/D00b account for conflicting unfinished source, direct consumers and obsolete v1.4 automation before new protections. Reuse verified C01–C04 deliveries rather than repeat the cutover. |
| Complete plan replacement | These two masters and their queues own future improvement work. Old R-series/private-runtime instructions supply no fallback requirements. Preserve their evidence and ownership records. |

### Simple implementation

Apply the repository mandate to every task: **Simple, lean, robust, do not
overenginering. If a problem can be solved by simplier approaches, do not use
more complex ones.**

Start with the demonstrated failure and the smallest change at its existing
owner. Reuse maintained session, PAM, service and test mechanisms. An effective
existing barrier or an absent defect needs no new implementation. Add a helper,
abstraction, persistent state or recovery mechanism only when a concrete required
behavior cannot be handled clearly by the existing path; explain that need in
the normal task result. Remove obsolete code and direct consumers together.

Keep design notes in the existing owner and results in the queue/checkpoint.
Follow the [test scope mandate](Mandates/Test-Scope-Mandate.md): validate affected
product behavior and shared safety guarantees at the lowest effective layer.
Do not create a framework, registry, evidence archive or dedicated test suite to
police this plan. Preserve the usability gates and required customer outcomes.

### Route allocation

| Result | Sole implementation and acceptance owner |
| --- | --- |
| Local graphical desktop selection | D01/D02, C07a, C11d/C12d |
| Request-session actions yielding a full desktop | D01/D02, C07s, C11d/C12d |
| One named supported remote-desktop provider | D01r/D02, C07, C11f/C12f |
| Standalone terminal/TTY and SSH | Remaining C06a/C06, C07t/C07b, C11t/e and C12t/e |
| Other exposed launches and child-controlled inputs | Remaining C06x/C06i/C06, C08a/C08, C11g/g1 and C12g/g1 |

A shared mechanism has one editor and one implementation owner. Its consumers
retain their own public outcomes and candidate-applicability checks.

### Usability stop gate

**Normal kiosk availability is the absolute highest priority.** A valid supported
configuration must open the passwordless request session and keep core use
working. A protection that breaks or rejects that normal session is a blocker,
even if its negative security test passes. Unexpected configuration alone is
never evidence of an intentional breach.

After every product-changing protection or recovery slice, the queue places a
separate installed usability gate for Ubuntu and Fedora before the next product
slice. Each gate requires the complete core-use history in this plan's acceptance
contract, with its affected shared-overlay/feature/pause controls, on that exact
candidate. Follow the baseline's complete-history reuse contract: trust recorded
completed results for unchanged scope and rerun affected histories after a concrete
change. A no-product-change slice needs no new proof or report-availability check.
Do not postpone a normal-entry failure to the final campaign or add another
restriction while either target is failing. A gate closes only with usable
public results and owned restoration, never by relabeling rejection as safe.
These gates consume the accepted baseline's registered core composition; they
do not wait for D03 or remaining C10, which freeze the later route/fault acceptance
maps. Missing independent core qualification becomes a bounded prerequisite at
the selected gate. Do not invent selectors or a circular readiness dependency.

Review every affected PAM/session/provisioning/frontend refusal and exception
path, including missing/stale owned state, lock contention, optional resources,
valid vendor variation and service readiness. Record why each can fail and its
normal-use control. Remove or repair unjustified admission predicates at their
owner; do not add an allowlist of familiar machines. Required-service outages
must retain a usable bounded retry/exit path and recover when service returns,
without fabricating a grant or weakening policy. Genuine parent/admin denial and
reviewed deliberate breach attempts retain their intended refusals.

A usability failure keeps its gate open, records expected/actual behavior and
returns the correction to its product owner through bounded prerequisites. Renew
affected complete histories after correction. The final acceptance tasks audit
the final candidate and may reuse these exact histories; they do not require
duplicate runs solely for a new task label.

### Admission uses a narrow denylist

**Default to passwordless kiosk-app access. Reject only a specifically recognized,
reviewed intentional attack pattern.** This is a denylist, never a whitelist of
recognized machine states. Unrecognized or strange files, packages, versions,
services, PAM layouts, locale data, environment values or other configuration
must not break or reject normal kiosk access merely because they are unfamiliar.
An unfamiliar configuration is not out of scope merely because the product has
not recognized it; support is not a configuration whitelist in disguise.
Do not deny an entire session when only an exposed action needs a narrow barrier.

For every protective rejection predicate, the existing design owner must record:

- The exact reachable caller/action/input and the child's demonstrated control.
- The specific deliberate breach pattern and prohibited result it enables.
- The narrow enforcement point and reason an action-level barrier is insufficient
  if session admission itself must refuse.
- A recognized-attack negative, a working normal-use positive, and benign adjacent
  or unknown configuration that must still allow passwordless app access.
- Recovery/restoration and target applicability, without a catch-all default deny.

Missing state, failed discovery, an unknown service or package, a parse exception,
content drift and lock contention are not attack patterns by themselves. Audit
those error/default branches explicitly. Repair owned recoverable state or keep
the kiosk app available with bounded retry/exit; do not translate uncertainty into
session rejection. Do not infer child control from unfamiliar content or a mode
bit alone. Specific deliberate terminal/TTY/SSH/desktop-launch attempts can have
reviewed route predicates; rejecting every unrecognized route is not a substitute.

This default concerns access to the restricted request app. Genuine parent/admin
authorization and required time/app enforcement still govern grants. An essential
service outage may prevent completing a request, but must not be disguised as an
attack or a reason to require a kiosk password, expose a desktop, fabricate approval
or disable enforcement. Keep the app's recovery path usable. Explicit parent or
administrator denial remains authoritative.

D00 inventories each affected refusal/error branch. D02 and remaining C06 record
an explicit **Denylist/default access: passed/failed** review alongside usability
and threat scope. A missing attack justification or a benign unknown rejected by
protection fails review and blocks that task. Both-target usability gates include
the finite benign/unknown variations directly affected by their product slice;
the final compatibility tasks retain their wider finite histories. No whole-host
inventory or exhaustive machine matrix is required.

### Inherited baseline requirements

Inherit the baseline's
[usability priority](Kiosk-Session-Confinement-Plan.md#highest-priority-product-usability),
[reasonable-child threat scope](Kiosk-Session-Confinement-Plan.md#mandatory-threat-scope-reasonable-child-effort)
and [selected source boundary](Kiosk-Session-Confinement-Plan.md#target-design).
Every refusal needs actual child access, a deliberate action, the prohibited
desktop result and a working normal-use positive. Trust installed Python/GTK/GI,
native code and normal lazy loading. No private runtime, loader, global inventory
or arbitrary-kiosk-execution premise. Unknown host content cannot veto entry.
Human decisions/authentication are not machine-startup time. Preserve genuine
parent/admin denial, main features and safe recovery from essential outages.

## Task boundaries and size

D00 audits the release lineage and residual cleanup map. D00a closes conflicting
source and package consumers; D00b closes obsolete automation consumers. Empty
residual scope needs an explicit verified disposition, not speculative changes.
These tasks do not execute or close the baseline queue. D01 requires completed
D00u/f tolerant-use gates and baseline C05u/C05f for both targets. Trust their
completed rows under the shared [completion policy](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery).
Changed code receives affected checks in the current task; expired reports do
not reopen a prerequisite.
New namespaces never bypass an active owner, Git transaction, VM lease or
overlapping uncommitted work.

D01 maps local routes; D01r maps one named remote provider. D02 independently
reviews the combined minimal design. C07a owns graphical-session admission;
C07s owns desktop-enabling actions inside the request session;
C07 owns the named remote-desktop route. Existing effective barriers need proof,
not duplicate code. D03 freezes exact finite selectors, inputs, qualifications,
timeouts, normal-use controls and restoration before installed consumers.
C11d/f and C12d/f preserve their stable desktop case identities and targets.
D04 closes only this desktop scope.

Each implementation task owns one reviewed boundary and its directly affected
tests/registration repairs. Ordinary tasks target 20–30 minutes including review
and checks. Local installed tasks retain a 30–60 minute exception for complete
desktop-attempt/core-use/restoration histories. Independent missing implementation
or qualification becomes a bounded prerequisite before its selected consumer
under [ordinary-plan execution](Execution-Plans.md#execution-and-delegation).
Do not absorb a general feature, broker or recovery project into these tasks.
Before closing each design review, name the affected complete functions/callers,
test modules, finite cases and existing automation bindings in the design owner.
Classify each route as already effective, a missing justified barrier or excluded
with a reason. Freeze that finite slice before implementation; if it cannot fit
one session, use the selected-consumer prerequisite route before editing product
code. Independent provider/operation development needs its own installed brief,
explicit targets and qualification before consumption. A host task may update
bindings but cannot mark a new reusable capability qualified.

## Acceptance

Require final-candidate public results on both `onpc-Ubuntu26.04` and
`onpc-Fedora44`; this does not broaden release support. Host/review checks and
baseline receipts grant no post-change desktop-defense pass.

| Owner | Required result |
| --- | --- |
| C11d / C12d | Reviewed local graphical-session and request-session desktop attempts fail to yield a full kiosk desktop. Passwordless request-only entry, genuine approval, requested time/soft-app use, continued hard blocks, denial/Cancel without grant, exit/reentry and a fresh request work. Ordinary-account desktop login remains usable. Include affected shared-overlay/feature/pause controls. |
| C11f / C12f | The named supported remote provider admits an ordinary-account desktop and blocks the kiosk-account desktop; normal kiosk entry still works. An absent service or failed positive is no denial pass. |
| D04 | Candidate-matching desktop results, justified refusals, affected regression controls, provenance and owned restoration are inspectable for both targets. |

Use public actions/results for customer acceptance. Engineering probes, root
injections, saved session preferences and an unusable form do not replace that
proof. Trust completed checks for unchanged behavior. After a concrete shared
change, run the affected complete histories for the relevant callers, targets,
providers and inputs within the current task. Include affected regression
controls without executing the remaining plan's entire campaign.

## Task execution contract

Apply the [baseline task contract](Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[Approval tools](Approval-Tools.md), [Execution plans](Execution-Plans.md) and
the [test map](TestAutomation/README.md). Read the selected brief and affected
source/callers/contracts. VM/UI/storage mandates apply when triggered. Reuse
qualified mechanics under the
[cross-plan reuse map](TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).
New general feature automation remains in the E2E queue.

The coordinator is GPT-6.1 Sol High. Applicable AGENTS.md core-backend model and
independent Astra xHigh review requirements remain binding. D02's independent
design review records explicit Usability priority and Threat scope passed/failed
findings; resolve actionable findings and revalidate material edits.

Keep a short result or actionable handoff with expected/actual failures,
task-owned paths and cleanup. Normal runner diagnostics are sufficient; no proof
bundle or retained-report audit is required. Close only the selected row after
review, validation, restoration and launcher Git close-out. Preserve stable IDs,
historical evidence and unrelated work. Build after final packaged-input edits;
product-string changes cover all supported languages.

## Execution

`tools/kiosk-desktop` uses the ordinary shared driver, GPT-6.1 Sol High,
registered VM selection and an independent namespace keyed by this master path.
It inherits task budgets, attachment/stop, guarded recovery and per-task
commit/push. Planning creates no completion or installed pass.

```sh
tools/kiosk-desktop --check
tools/kiosk-desktop --tasks 1
tools/kiosk-desktop --tasks 0
tools/kiosk-desktop --stop
```

These are alternatives. Omitted `--vm` selects configured enabled targets;
installed briefs still require their named target. The existing-grant equivalent
is `tools/execute-plan --plan 'docs/Kiosk-Desktop-Plan.md'`. A new executable joins
the next normal [rules refresh](Approval-Tools.md#one-time-setup); do not refresh
rules or install the product on the development host merely to check this plan.

### Split lifetime

Each master path keeps its own shared-driver namespace. Preserve active owners,
checkpoints, handoffs, pending Git work and VM leases; do not copy or clear them
to move work between launchers.

### Retained-run admission

Use the [common launcher interface](Execution-Plans.md#common-launcher-interface).
Ordinary execution consumes current queue rows and briefs without snapshot
comparisons or a plan-specific migration gate. Explicit administrative
`--reconcile` retains its own guards; it is not required for ordinary execution.
`--check` validates current plan metadata and grants no installed acceptance.

Run cleanup and D00u/f, require completed baseline C05u/f at D01, finish through
D04, then start the remaining queue. An unfinished external prerequisite keeps
its consumer open with the owning queue and return condition. Completed rows
need no historical report inspection.
