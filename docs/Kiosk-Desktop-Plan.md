# Prevent full desktop access through the kiosk account

Task queue: [Ordered task queue](Kiosk-Desktop-Queue.md).
Next task: **D00a3 — [Remove saved-routing admission dependence](Kiosk-Prompt-Tasks/D00a3-routing-admission.md)**.

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

Reliability work here is limited to admission, startup, exit/reentry and recovery
failures caused by kiosk confinement or its direct consumers. Preserve the
working request/approval interface across that boundary. This is not general
product acceptance: do not add policy, language, reporting, reminder or other
feature campaigns. Broader recovery and standalone routes retain their owners
below. An unrelated product defect is reported to its owner, not absorbed here.

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
| Usability first | Passwordless sign-in, a usable request/approval journey and safe reentry take priority. Preserve existing time/app enforcement; desktop work uses the bounded checks below, not a general feature campaign. |
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

Start with a demonstrated failure. Prefer removing an obsolete restriction or
using an existing supported session/PAM/service mechanism before adding custom
code. An effective existing barrier or an absent defect needs no implementation.
Keep each fix at its current owner and remove obsolete direct consumers with it.

Add a helper, abstraction, persistent state, configuration probe or recovery
mechanism only when the direct approach cannot meet a concrete required behavior.
Keep any necessary rationale in the existing design note or short task result.
Keep the launcher as a thin shared-driver wrapper; use the shared lifecycle.

### Simple tests

Apply the same principle to test code, fixtures, qualification and acceptance
under the [test scope mandate](Mandates/Test-Scope-Mandate.md). Reuse existing
coverage and qualified operations. Add cases only for distinct uncovered product
outcomes or failure boundaries, using small representative inputs and the lowest
effective layer. Keep shared safety checks at their owner. Do not add tests of
tests or per-consumer matrices.

Use the [shortest reliable public journey](Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope);
remove redundant navigation, readbacks and incidental prerequisites while
preserving meaningful outcomes and safety guards. Run affected checks only;
reuse passed complete histories for unchanged scope under the usability gate.
A new task label or expired report needs no rerun. Keep both-target usability
and desktop outcomes. Normal diagnostics and a short queue/checkpoint result
suffice; add no framework, registry, proof archive or checker for this plan.

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

For this desktop queue, **the product-changing task itself must pass installed
usability on both Ubuntu and Fedora before it completes**. D00a, C07a, C07s and
C07 declare `Acceptance: installed` and both targets. The shared launcher pushes
and propagates completed tasks, so later acceptance rows cannot supply a missing
check after a product commit. Apply this rule to every product repair or inserted
product prerequisite too, including repairs found in single-target acceptance.
Keep such a repair in a both-target installed task before its consumer closes.
Do not change the shared launcher or introduce a delayed-push mechanism.

Use the [bounded confinement usability check](#bounded-confinement-usability-check)
on the exact built/installed candidate. Missing independent fixture, operation or
provider qualification is a small prerequisite **before product editing**; do not
mix new automation development with the fix or wait for D03. A failed, skipped,
unrun or other-candidate target leaves the product task open. Report expected
versus actual behavior and repair the same small boundary; add no further
restriction. Finish owned restoration before completion.

Trust completed results for unchanged scope under the shared completion policy.
A no-product-change task may reuse exact applicable installed results; new
variation or route assertions still need their own checks. Do not inspect old
report availability, rerun unchanged histories for task labels or claim a host
pass as installed acceptance. The remaining plan retains its own broader
acceptance and separate gate rows; this desktop update does not execute them.

Review every affected PAM/session/provisioning/frontend refusal and exception
path, including missing/stale owned state, lock contention, optional resources,
valid vendor variation and service readiness. Record why each can fail and its
normal-use control. Remove or repair unjustified admission predicates at their
owner; do not add an allowlist of familiar machines. Required-service outages
must retain a usable bounded retry/exit path and recover when service returns,
without fabricating a grant or weakening policy. Genuine parent/admin denial and
reviewed deliberate breach attempts retain their intended refusals.

A usability failure keeps its product task open. Final desktop acceptance may
reuse applicable results from that task; it must still prove every distinct
desktop attack and affected recovery result. No task closes by relabeling a
rejected login or diagnostic-only form as usable.

### Bounded confinement usability check

Keep one short public history per target, using existing qualified operations
and a fixed representative child/approver. It must show fresh passwordless
graphical entry to the usable request form, genuine parent approval with the
intended request result, denial/Cancel without a grant, normal exit and fresh
entry with another usable request. Observe each result; merely seeing a window
or passing an account-only PAM probe is insufficient. Reuse existing negative
and positive bindings rather than implementing another journey framework.

Add only controls directly affected by the confinement edit: ordinary-account
login for shared PAM/session changes, a shared-overlay request if its caller
changes, and a representative public time/soft-app/hard-block outcome if the
changed path can affect authorization or enforcement. Unchanged accepted policy
and feature histories remain accepted. Do not add settings matrices, general
feature qualification or repeated long human-pause tests; a new startup deadline
must still exclude time spent reading, choosing or authenticating.

Before the edit, name the finite benign/fault controls from the refusal audit
that this slice can affect. Cover distinct failure boundaries with representative
inputs, not combinations. Host tests own injected errors; installed engineering
checks own real dependency/lock/routing variation; public entry/request/reentry
owns the usability result after restoration. A fault-injection probe is not
customer acceptance. Reuse a complete existing history when it already proves
these outcomes; do not split out observations that would hide a denial or grant.

### Resilient admission and recovery

D00 must inspect the complete confinement admission/startup path, including
service dispatch, actual selected session/transport, routing reads and repair,
new/existing admission leases, contention, timeouts and owned lifecycle barriers.
Do not assume these are safe merely because they survived the v1.3 cutover or
because a test expects refusal. Benign variation and recoverable confinement
faults must not create a kiosk password requirement, persistent rejection or
manual-repair dependency. This is an acceptance requirement, not a best-effort
goal. A newly essential startup dependency must be justified by the reviewed
desktop barrier; unfamiliar configuration cannot make an optional input essential.
Classify each failure at its existing owner:

| Condition | Required behavior and finite control |
| --- | --- |
| Defined desktop attack | Block the demonstrated desktop route at its narrowest effective boundary; show normal kiosk entry/request/reentry still works after the attempt. |
| Benign unfamiliar configuration or missing optional input | Preserve kiosk entry and approval; ignore or isolate the irrelevant input rather than require a familiar host layout. Pair the affected predicate with a benign adjacent/unknown positive. |
| Transient required-service, routing or owned-lock fault | Use bounded retry or safe owned repair. Keep the confined app's retry/exit usable where safe; restoration must permit fresh passwordless use without reinstalling or manually deleting product state. Do not permanently quarantine an ordinary failed attempt. |
| Explicit administrator denial, active owned removal or foreign/live state | Preserve the actual authority and ownership barrier. Never bypass it, adopt foreign state or report it as an attack pass. Verify normal entry after the authorized owned operation completes where this slice changes that path. |

Changing an allowlist to a denylist does not satisfy this review. Trace every
default/exception return to its public login result. Prefer removing an avoidable
admission dependency or repairing routing safely within the attempt; where the
platform requires a fresh attempt, provide a bounded, usable return/retry rather
than a rejection loop. Never mechanically change PAM errors into success, enable
global null-password authentication, weaken parent approval or fall back to an
unrestricted desktop. A required outage can honestly prevent completion; it
cannot count as working normal use or as a successful attack defense.

Keep recovery inside the affected confinement boundary. Do not build a general
service supervisor, state framework, host inventory or broad lifecycle campaign.

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
- The observable route/input predicate that distinguishes that attempt from
  benign variation; do not infer intent from a discovery failure or unknown name.
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
the remaining plan's compatibility tasks retain their wider finite histories.
No whole-host inventory or exhaustive machine matrix is required.

### Inherited baseline requirements

Inherit the baseline's
[usability priority](SystemDesign/Kiosk-Confinement.md#usability-priority-and-reasonable-child-effort),
[reasonable-child threat scope](SystemDesign/Kiosk-Confinement.md#security-boundary-and-assumptions)
and [selected source boundary](SystemDesign/Kiosk-Confinement.md#selected-source-boundary).
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
These tasks do not execute or close the baseline queue. D00a owns both-target
tolerant-use checks before its completion; D00b cannot change product code.
D01 requires completed cleanup and baseline C05u/C05f for both targets. Trust their
completed rows under the shared [completion policy](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery).
Changed code receives affected checks in the current task; expired reports do
not reopen a prerequisite.
New namespaces never bypass an active owner, Git transaction, VM lease or
overlapping uncommitted work.

D01 maps local routes; D01r maps one named remote provider. D02 independently
reviews the combined minimal design. C07a owns graphical-session admission;
C07s owns desktop-enabling actions inside the request session;
C07 owns the named remote-desktop route. Existing effective barriers need proof,
not duplicate code. D00 and D02 identify exact usable bindings and missing small
qualification prerequisites before their product consumers. D03 audits the final
route map, timeouts, controls and restoration; it cannot postpone those prerequisites.
C11d/f and C12d/f preserve their stable desktop case identities and targets.
D04 closes only this desktop scope.

Each implementation task owns **one concrete defect and one enforcement or
recovery boundary**, with its direct tests. Ordinary tasks target 20–30 minutes
including review and checks. A product task has a 30–60 minute session exception
only to keep that small fix, review/build and both-target bounded usability
together before completion. Final installed tasks have the same 30–60 minute
exception for one route family and its controls/restoration. Independent missing
implementation or qualification becomes a bounded prerequisite before its selected consumer
under [ordinary-plan execution](Execution-Plans.md#execution-and-delegation).
Do not absorb a general feature, broker or recovery project into these tasks.
Before closing each design review, name the affected complete functions/callers,
test modules, finite cases and existing automation bindings in the design owner.
Classify each route as already effective, a missing justified barrier or excluded
with a reason. Freeze that finite slice before implementation; if it cannot fit
that budget, split independent defects or routes into bounded prerequisites
before editing product code. Do not create a host-only product prerequisite to
evade its installed gate, or combine distinct fixes to fill a task. Keep required
same-candidate acceptance with each fix. Independent provider/operation development
needs its own installed brief, explicit targets and qualification before consumption. A host task may update
bindings but cannot mark a new reusable capability qualified.
Apply the size check to review, automation and acceptance tasks too. If no safe
small split fits the budget, keep the task open with the precise boundary/budget
conflict; do not silently grow it or weaken the both-target gate.

## Acceptance

Require final-candidate public results on both `onpc-Ubuntu26.04` and
`onpc-Fedora44`; this does not broaden release support. Host/review checks and
baseline receipts grant no post-change desktop-defense pass.

| Owner | Required result |
| --- | --- |
| D00a / C07a / C07s / C07 | Before each product task completes: both-target bounded confinement usability, directly affected benign/fault controls, required review/build and owned restoration. No product change may rely on a later acceptance row. |
| C11d / C12d | Precisely mapped local graphical-session and request-session desktop attempts fail to yield a full kiosk desktop. Pair each distinct route with its normal-use and recovery controls and the bounded confinement usability result. Ordinary-account desktop login remains usable. Add only directly affected shared-overlay or enforcement controls. |
| C11f / C12f | The named supported remote provider admits an ordinary-account desktop and blocks the kiosk-account desktop; normal kiosk entry still works. An absent service or failed positive is no denial pass. |
| D04 | Candidate-matching desktop results, justified refusals, affected regression controls, provenance and owned restoration are inspectable for both targets. |

Use public actions/results for customer acceptance. Engineering probes, root
injections, saved session preferences and an unusable form do not replace that
proof. Trust completed checks for unchanged behavior. After a concrete shared
change, run the affected complete histories for the relevant callers, targets,
providers and inputs within the current task. Include affected regression
controls without executing the remaining plan's entire campaign.

For each desktop claim, keep the child-reachable action, observable predicate,
actual selected execution/session path, prohibited full-desktop result, target/
provider applicability and normal-use control together in the existing design
map. Saved defaults, a nologin shell, an unknown PAM service name or an absent
provider do not prove which desktop executable was prevented. A failed positive
or an unexercised route earns no defense claim. Scope closure to these exact
attacks; no arbitrary-code-containment or all-provider claim is implied.

## Task execution contract

Start at [System design](System-Design.md) and apply
[Approval tools](Approval-Tools.md), [Execution plans](Execution-Plans.md) and
the [test map](TestAutomation/README.md). Every brief inherits
[simple implementation](#simple-implementation) and [simple tests](#simple-tests).
Read the selected brief and affected source/callers/contracts.
VM/UI/storage mandates apply when triggered. Reuse
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

Run cleanup with D00a's installed gate, require completed baseline C05u/f at D01,
finish through D04, then start the remaining queue. An unfinished external prerequisite keeps
its consumer open with the owning queue and return condition. Completed rows
need no historical report inspection.
