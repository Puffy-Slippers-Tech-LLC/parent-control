# Remaining kiosk confinement improvements

Task queue: [Ordered task queue](Kiosk-Prompt-New-Queue.md).
Next task: **C06a — [Review remaining login routes](Kiosk-Prompt-Tasks/C06a-login-review.md)**.
Baseline plan: [Full desktop prevention](Kiosk-Desktop-Plan.md).
Baseline task: D04.

## Outcome

Improve confinement after the
[accepted baseline](SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits) and
[full desktop prevention](Kiosk-Desktop-Plan.md) complete.
Keep passwordless kiosk use, genuine parent approval and time/app enforcement
working while closing justified routes available to a smart technical child.
Own standalone terminal/TTY and SSH access, other exposed actions/consumed inputs,
compatibility/recovery/lifecycle work and its final acceptance. Desktop tasks
retain their stable IDs under the desktop owner. No task completes through planning.

## Usability and threat scope

The desktop master's [binding planning requirements](Kiosk-Desktop-Plan.md#binding-planning-requirements),
[simple implementation rule](Kiosk-Desktop-Plan.md#simple-implementation)
and [route allocation](Kiosk-Desktop-Plan.md#route-allocation) apply to every row
here. Residual conflicting source and obsolete v1.4 automation cleanup is first,
under D00/D00a/D00b; C06a verifies that handoff through D04. This queue adds only
justified protections to the pinned v1.3 confinement slice, retaining main's
non-confinement features. Do not recreate the old main/v1.4 subtraction approach.
The desktop master's [usability stop gate](Kiosk-Desktop-Plan.md#usability-stop-gate)
is binding here: each product slice is followed by separate both-target core-use
renewals before the next product slice. A normal broken/rejected kiosk session
blocks advancement immediately. Final acceptance may reuse exact applicable
gate evidence; qualification and customer histories retain their own assertions.
The master's [narrow denylist](Kiosk-Desktop-Plan.md#admission-uses-a-narrow-denylist)
also binds this queue: unknown/strange configuration preserves passwordless app
access. Only specifically justified deliberate breach patterns may be rejected;
uncertainty, failed discovery or missing optional state is not such a pattern.

The desktop master's [inherited baseline requirements](Kiosk-Desktop-Plan.md#inherited-baseline-requirements)
also apply, including trusted installed loading, genuine parent/admin denial,
usable service recovery and preservation of main's non-confinement features.

## Simple product and tests

Every task, including implementation, repair, qualification and acceptance,
inherits the desktop master's [simple implementation](Kiosk-Desktop-Plan.md#simple-implementation)
and [simple tests](Kiosk-Desktop-Plan.md#simple-tests) rules. Apply the repository
principle to both product code and test code: prefer the simplest approach that
meets the required behavior reliably.

Start with the demonstrated gap and its existing owner. Reuse an effective
barrier, supported platform mechanism or existing test before adding code.
Choose a direct fix unless a concrete requirement makes it insufficient;
justify necessary extra machinery briefly in the existing design or task result.
Remove obsolete direct consumers with the fix. Keep this launcher a thin
shared-driver wrapper; add no plan-specific framework or policy checker.

For tests, follow the [test scope mandate](Mandates/Test-Scope-Mandate.md):
cover distinct product outcomes and failure boundaries with representative inputs
at the lowest effective layer. Reuse qualified operations and complete unchanged
histories; avoid duplicate per-task suites, per-consumer matrices and tests of
tests. Simplification preserves required security assertions, both-target
usability gates, complete recovery histories and ownership/cleanup guards.

## Confinement priority

Full kiosk desktop prevention is the first security priority and belongs only to
[the desktop plan](Kiosk-Desktop-Plan.md), run by `tools/kiosk-desktop`.
That owner includes local graphical-session selection, request-session escapes
yielding a full desktop and the named supported remote-desktop provider.
C06a verifies its accepted D04 gate before this plan proceeds. Each launcher
owns its queue, briefs and acceptance; neither implicitly closes the other.

If later work exposes a full-desktop route or invalidates desktop evidence,
record the affected route/candidate and return condition under the desktop owner.
Renew the affected desktop history there before claiming combined final readiness.
Reuse shared mechanisms and matching evidence without duplicating implementation.

## Task boundaries

Before closing C06a, require completed desktop D04 and baseline C05f/C05u for
their declared targets. Trust completed rows under the shared
[completion policy](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery);
do not inspect old reports. An unfinished prerequisite leaves C06a unchecked
with its owning queue and return condition. Concrete later changes receive
affected checks within the current task.
A new namespace is no authorization to bypass an active baseline owner, pending
Git transaction, live VM lease or uncommitted overlapping source work.

The [C05f baseline handoff](TestAutomation/E2E-Building-Blocks.md#c05f-fedora-baseline-acceptance)
accepts both targets' unchanged complete core histories and separate feature/pause
results. Standalone terminal/TTY and SSH remain unqualified for C06a/C06; other
exposed actions and child-controlled consumed inputs remain for C06x/C06i.
The desktop owner retains all full-desktop routes, including its named remote
provider, and its D04 gate remains required. These coverage gaps are not observed
baseline failures. This handoff closes no remaining-plan row or final defense gate.

C06a reviews remaining SSH/terminal/TTY routes. C06x maps exposed actions and
C06i separately maps child-controlled consumed inputs; C06 independently reviews
the combined finite design. C07t/C07b and C08a/C08 add only missing justified barriers,
with targeted tests and normal-use controls. Desktop barriers remain in their plan.
C09 addresses demonstrated confinement-caused availability/recovery/lifecycle
coupling. Existing effective barriers need verification, not duplicate code.
General broker/feature projects are outside these rows' scope.
C09a owns optional presentation fallback; C09a1 separately owns native-language
fallback without changing genuine selected-parent authentication. C13a audits
final source/test dispositions; C13 audits final evidence and documentation.

New tests appropriate to planned confinement changes belong here, including
finite public negative/positive bindings, recovery histories and candidate-specific
final acceptance. Reuse shared E2E mechanics and exact qualified slices under the
[cross-plan reuse map](TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).
New general feature automation belongs to the
[E2E queue](TestAutomation/E2E-Task-Queue.md), including policy/app effects,
saved presets/units, language/reminder matrices and What's New. Do not duplicate
its implementation or silently execute/close its rows.
A feature exposed by a confinement change needs its relevant regression control,
not an unrelated feature suite.

Every product slice includes its directly affected test/registration repairs.
C10 freezes exact finite selectors, inputs, qualifications, timeouts and restoration
before final consumers; missing independent work becomes a bounded prerequisite
under [ordinary-plan execution](Execution-Plans.md#execution-and-delegation).
Keep complete fault/recovery/reentry histories together and preserve queue order.
Apply the desktop master's finite design/implementation boundary: record complete
affected functions/callers, finite test inputs, bindings and qualification gaps
before product edits. A task with no demonstrated defect verifies the existing
boundary; it must not invent restrictions or speculative recovery infrastructure.
Split oversized independent work at the selected consumer before implementation.
New reusable operations need explicitly targeted installed qualification before
their first composition consumer; host registration is no qualification. C10
only audits readiness and cannot absorb missing capability development.

## Acceptance

The baseline gate remains independent and grants no post-change defense pass.
After changes, qualify applicable final candidate histories on both
`onpc-Ubuntu26.04` and `onpc-Fedora44`. This does not broaden release support.

| Family | Required result and owner |
| --- | --- |
| Core use | C11/C12: passwordless entry, genuine approval, requested time and soft-app use, continued hard blocks, denial/Cancel without grant, exit/reentry, fresh request and affected shared-overlay/feature/pause controls. |
| Host variation and optional failures | C11a/a1 and C12a/a1: one unrelated package/layout change, valid PAM/service variation and finite presentation/native-language fallbacks preserve genuine approval. |
| Required-service and child isolation | C11b/b1 and C12b/b1: bounded recovery, intact policy, healthy-child requests while another integration is unavailable, restored-child use, retained sanitized original cause and real Parent diagnostic download without submission. |
| Owned state and updates | C11c/c1 and C12c/c1: complete interrupted/stale-state and relevant update/reentry histories, preserving foreign/live sessions, policy and current features. |
| Remaining login routes | C11t/e and C12t/e: standalone terminal/TTY and SSH access blocked, paired with usable kiosk and ordinary-account positives. Absent service or failed positive is no refusal pass. Full graphical desktop results remain with the desktop plan. |
| Exposed actions and inputs | C11g/g1 and C12g/g1: finite deliberate link/chooser/handler/automatic-launch and child-writable consumed-input attempts blocked, with permitted form/approval and trusted-code/lazy-loading controls. |
| Close-out | C13: matching product/automation/docs, provenance, justified refusals, inspectable both-target evidence and owned restoration; verify separately accepted desktop results still apply and require renewal there if invalidated. |

Keep customer results separate from engineering probes and fault injection.
A diagnostic-only screen, denied normal entry, host mapping or historical proof
cannot replace installed acceptance. Trust completed checks for unchanged
behavior; run affected complete histories within the current task after concrete
shared changes. Do not claim arbitrary provider coverage,
run expert-attack/whole-host matrices or turn every host UI value into E2E work.

## Task execution contract

Start at [System design](System-Design.md) and apply
[Approval tools](Approval-Tools.md), [Execution plans](Execution-Plans.md) and
the [test map](TestAutomation/README.md). Every brief inherits
[simple product and tests](#simple-product-and-tests). Read the selected brief and affected
source/callers/contracts. VM/UI/storage mandates apply when triggered.
Use maintained selectors with explicit timeouts and live qualification for new
or changed reusable installed operations before their consumers.

The coordinator is GPT-6.1 Sol High. Applicable AGENTS.md core-backend model and
independent Astra xHigh review requirements remain binding. C06's independent
protection-design review retains explicit Usability priority and Threat scope
passed/failed findings; resolve actionable findings and revalidate material edits.
No host/review result supplies installed acceptance.
The C06 review also records Denylist/default access passed/failed and checks
benign adjacent/unknown controls for every proposed protective rejection.

Keep a short result or actionable handoff with expected/actual failures,
task-owned paths and cleanup. Normal runner diagnostics are sufficient; no proof
bundle or retained-report audit is required. Close only the selected row after
required review/checks/owned cleanup and launcher Git close-out. Keep stable case
identities, historical failures and unrelated work. Retire obsolete source/test
consumers within changed confinement scope; retain accepted evidence ownership.

## Execution

`tools/kiosk-prompt-new` is a thin ordinary-plan adapter with an independent
namespace keyed by this master path. It shares budgets, attachment/stop, guarded
recovery and per-task commit/push through the shared ordinary-plan driver.

```sh
tools/kiosk-prompt-new --check
tools/kiosk-prompt-new --tasks 1
tools/kiosk-prompt-new --tasks 0
tools/kiosk-prompt-new --stop
```

These are alternatives. Omitted `--vm` selects configured enabled targets;
every installed brief still requires its named target. Attach without flags to
retain the active task limit. The generic entry
`tools/execute-plan --plan 'docs/Kiosk-Session-Confinement-New-Plan.md'`
shares this owner. A namespace with no retained run needs no checkpoint migration.
Apply the [common launcher interface](Execution-Plans.md#common-launcher-interface)
and desktop master's [split lifetime](Kiosk-Desktop-Plan.md#split-lifetime).
Ordinary execution uses current rows and briefs without a plan-specific migration
or evidence preflight. Preserve owners, handoffs and pending transactions.

New executable command grants join at the next normal
[rules refresh](Approval-Tools.md#one-time-setup); the generic entry is available
under the existing grant meanwhile. Never broaden command rules or install the
product on the development host. Build after final packaged-input changes.
All-language product-string requirements remain; What's New synchronization
requires its separate explicit request.
