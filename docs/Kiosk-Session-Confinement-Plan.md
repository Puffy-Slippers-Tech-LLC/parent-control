# Kiosk confinement baseline validation for v1.4

Task queue: [Ordered task queue](Kiosk-Prompt-Queue.md).
Next task: **C04r — [Renew shared reminder persistence](Kiosk-Prompt-Tasks/C04r-reminders.md)**.

## Outcome

Validate the rebuilt v1.3 confinement baseline so v1.4 can ship with solid
passwordless kiosk entry, genuine parent approval and time/app enforcement.
Keep main's current non-confinement features. This plan ends at C05f after the
Ubuntu and Fedora baseline gates; new protections and compatibility improvements
belong to the [graphical desktop prevention plan](Kiosk-Desktop-Plan.md)
and `tools/kiosk-desktop`, followed by the
[remaining confinement plan](Kiosk-Session-Confinement-New-Plan.md) and
`tools/kiosk-prompt-new`. They are not prerequisites for this baseline.

Planning reconciliation grants no task completion or installed acceptance.
The existing master path, launcher and surviving brief paths remain stable for
retained baseline work. Completed C01–C04o rows keep their original evidence.

## Highest priority: product usability

**Product usability is the highest priority. Unexpected machine configurations
must not break passwordless sign-in, the request form or core end-to-end use.**

Every protection-caused failed use needs a concrete intentional breach effort
available to a smart technical child: name their actual access, deliberate action,
prohibited result and the matching working normal-use control. Unfamiliar files,
services, package versions or configuration alone supply no justification.
An unjustified protective failure is a product bug. Genuine parent denial and
explicit administrator policy remain authoritative. Essential-service outages
are faults to recover, with safe retry/exit and no unauthorized access.

Human time choosing a language, reading, deciding or typing a parent password
is not startup time. Trusted lazy loading and ordinary package/account
administration must not require a private product protocol. Optional presentation
or service failures cannot veto core use.

## Mandatory threat scope: reasonable child effort

The baseline retains its existing restrictions and authorization boundaries.
Ordinary session selection, shortcuts, TTY/terminal, SSH, remote desktop,
exposed links/choosers/handlers and child-writable consumed inputs are the
reasonable-child scope for the two improvement plans' finite route reviews.
Baseline failures must be diagnosed against actual public routes, without
inventing new defenses or expanding into those future reviews.

Do not assume arbitrary kiosk-UID execution, compromised trusted packages/root,
expert native-loader chains or kernel/boot/firmware exploitation. Trust supported
installed Python/GTK/system code. No custom runtime, private GI/graphics image,
continuous library audit or per-import authority protocol is a prerequisite.
Engineering injections remain separate from customer acceptance.

## Target design

### Mandatory baseline: v1.3 kiosk session confinement only

The selected confinement slice derives from release commit
`188be907c46b1cd0dabae06ac898c43e75beb05e` (`releases/v1.3`).
C01–C03 already record selective reconstruction and cleanup; do not repeat that
cutover, switch branches or restore all v1.3 kiosk code.

Main owns the shared request UI, Preferences/language, duration choices,
notifications, What's New, artwork, feedback and diagnostics, broker authorization,
time/app enforcement, packaging and test tooling. Preserve those features and
their useful diagnostics. Use the current
[selected session/PAM baseline](SystemDesign/Kiosk-Confinement.md#c02-activated-session-baseline),
not the discarded v1.4 private graph, retained-view, loader or admission framework.
The old release GDM hook is historical source, not current routing proof.

## Task boundaries

The queue is the sole order. C04p1/p check applicability of shared E2E fixture
and core-effects work; C04l/s/r/i reuse existing language, request-choice,
reminder and About coverage. Renew only invalidated routes. C04l/w add the
finite confinement human-pause/session-lifetime checks. C04j supplies thin core
orchestration, C04 audits readiness, and C05u/f accept the complete baseline.

New general feature bindings belong to the E2E queue, including the already
identified shared fixture/core-effects gaps in 313a/313. Those are the finite
outstanding core regression prerequisite, not permission for a larger feature
campaign. E2E 314/315's saved-preset editing, Hours and What's New journeys,
new language/reminder matrices and other general feature expansion do not block
this plan. Use the
[cross-plan reuse map](TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse)
for exact ownership, delivery and blockers. Never execute another queue implicitly.

Fix confinement-caused baseline defects with targeted regressions and normal-use
controls. Independent work discovered at the selected consumer follows the
[bounded prerequisite handoff](Execution-Plans.md#execution-and-delegation).
Do not resize later rows or import new-plan acceptance families into this queue.
Estimates include reading, validation, review, cleanup and close-out; longer
indivisible installed histories retain their explicit exceptions.

## Acceptance

### Core product journey gate

Use installed public actions: Parent configures one child's time/app limits;
kiosk opens without a password; child/approver choices and genuine parent
authentication grant the requested time and selected soft-app access; the child
can use it while hard blocks remain; public revocation restores restrictions.
Cover the shared overlay where changed code serves both surfaces.

Retain denial and Cancel with no grant, normal exit/reentry, session switching,
a successful fresh request, human language/authentication pauses and the existing
feature checks. Use the
[finite baseline recipe](TestAutomation/E2E-Scenario-Recipes.md#c04b-baseline-public-use-slice);
do not expand it into all-product automation.

### Evidence reuse and baseline limits

C04j's first complete history on each target may supply C05's installed evidence
under the [complete baseline evidence-reuse contract](TestAutomation/E2E-Execution-Contracts.md#complete-baseline-evidence-reuse).
Verify every assertion, exact candidate/caller/provider/input applicability and
collection/restoration. Execute only missing or invalidated complete histories.
Separate operation qualifications cannot replace the complete core history.
Existing feature and pause checks remain separate reusable evidence; do not
replay them solely for a different task label. C04 stays host acceptance, C05
stays installed acceptance, and only the selected row closes.

Both `onpc-Ubuntu26.04` and `onpc-Fedora44` require their declared results.
Fedora validation does not broaden release support. A denied normal entry,
diagnostic-only form, missing proof or host pass is no installed usability pass.
Preserve original failures, valid unchanged evidence and stable case IDs.

New unrestricted graphical desktop prevention and its installed histories belong
to the [desktop plan](Kiosk-Desktop-Plan.md#acceptance). Other deliberate-route
protection, host-variation, optional-fallback, recovery, update and post-change
defense histories belong to the
[remaining confinement plan](Kiosk-Session-Confinement-New-Plan.md#acceptance).
Existing baseline coverage and mandatory regression failure handling remain required. Completion
of this plan establishes the stated baseline, not unexecuted future protections.

## Product and test automation must match

Keep the completed source/test dispositions and current implementation accurate.
C04 audits affected remaining consumers without resurrecting removed mechanisms.
Discarded private protocol fixtures are not customer requirements. Preserve
main features, stable customer outcomes and evidence; no wholesale artifact or
VM-baseline deletion is authorized. C05f's close-out records matching baseline
product/automation/docs, both-target applicability and concrete remaining route
gaps for both improvement plans, without implementing them.

## Implementation baseline

C01–C03's source, cleanup and host evidence remain in the
[confinement design](SystemDesign/Kiosk-Confinement.md#c01-selective-replacement-boundary).
The rebuilt code, rather than active old-plan work, is the candidate for
validation. Current readiness and the remaining B3–B4 live gaps remain in the
[operation applicability map](TestAutomation/E2E-Building-Blocks.md#c04b-baseline-operation-applicability).
C04o closed its fixed overlay operation. C04p verified the finite both-target
grant/use/revocation qualification in the
[app-effects record](TestAutomation/E2E-Building-Blocks.md#c04p-time-and-app-effects-applicability).
Original stopped attempts retain no acceptance credit; no E2E queue row or
complete baseline journey closes through this reuse.

## Scope reconciliation

This baseline keeps `docs/Kiosk-Session-Confinement-Plan.md`,
`docs/Kiosk-Prompt-Queue.md` and `tools/kiosk-prompt`.
Unrestricted graphical desktop prevention is scheduled, unchecked, in
[Kiosk-Desktop-Queue.md](Kiosk-Desktop-Queue.md). The remaining C06–C13 work is
scheduled, unchecked, in [Kiosk-Prompt-New-Queue.md](Kiosk-Prompt-New-Queue.md).
Existing briefs retain stable paths under their respective masters. No old
completion, mutable VM state or task handoff transfers to either new namespace.
Desktop D01 explicitly verifies C05f's both-target accepted baseline; residual
C06a verifies accepted desktop D04 before further implementation.

The former R-series owner remains separate. Its attachment/stop route is
`tools/kiosk-prompt --plan 'docs/Kiosk-Resilience-Plan.md' --stop`;
never use reconciliation to overwrite that checkpoint.

### Before execution

Commit reviewed planning inputs first. Preserve unrelated changes and staging.
Overlapping uncommitted E2E 313 work needs its owner's reviewed source baseline or
an isolated checkout before task close-out; a planning commit cannot accept it.
Finish any existing owner, owned cleanup and pending Git transaction through its
maintained route. New namespaces do not bypass those gates.

If the original baseline/improvements split is still pending for an inactive
C04p checkpoint, its [reviewed split reconciliation](Execution-Plans.md#reviewed-plan-splits)
requires the original committed destination tail and five reviewed baseline scope
revisions. The later desktop reallocation is not an unchanged-tail destination;
do not pass it to that recovery command. Preserve C04p and suspended C04 handoffs,
counters, original rejected result and accepted proof. Already reconciled baseline
work retains its owner; no second baseline reconciliation is required by this split.
Use the existing branch/upstream/credentials; do not change Git configuration.

## Task execution contract

Start at [System design](System-Design.md) and the
[test map](TestAutomation/README.md), then the selected brief and affected owners.
Apply [Approval tools](Approval-Tools.md), the
[ordinary-plan contract](Execution-Plans.md#execution-and-delegation) and
[failure handling](../tests/README.md#handling-test-failures).
Use the lowest effective maintained checks with explicit timeouts. VM/UI/storage
work triggers its mandate. Changed reusable installed operations and compositions
need [live qualification](TestAutomation/E2E-Execution-Contracts.md#live-verification-contract).

The coordinator is GPT-6.1 Sol High; applicable AGENTS.md backend model/review
requirements remain binding. Protection/usability review must challenge
unjustified refusals and complexity. Finish review, required checks, owned cleanup
and launcher Git close-out before advancing only the selected row.

### Launcher handoff and validation routes

Retain exact candidate, command, finite values, expected/actual public results,
remaining blocker and restoration in maintained records. Predecessors mean
delivered scope, not removed briefs or saved guest state. No row closes another
queue. Missing feature work returns to its E2E owner.

Use both launcher `--check` routes and the
[host consistency selection](TestAutomation/E2E-Execution-Contracts.md#completion-and-document-cleanup)
after planning edits. Launcher changes also use
`tools/run-tests unit 'tests/unit/test_execution_plan_launcher.py'`.
Checks prove metadata and guarded recovery, not installed behavior.

## Execution

```sh
tools/kiosk-prompt --check
tools/kiosk-prompt --tasks 1
tools/kiosk-prompt --tasks 0
tools/kiosk-prompt --stop
```

These are alternatives. With no task limit or stop flag, attach to the existing
owner without changing its limit. Omitted `--vm` selects configured enabled
targets; installed briefs still require every declared target. Use fresh
controllers after launcher changes. Never install the product on the development
host. Build only after changes affecting packaged inputs; ordinary localized
strings retain all-language requirements and What's New sync needs explicit
authorization. This reconciliation executes no queue task.
