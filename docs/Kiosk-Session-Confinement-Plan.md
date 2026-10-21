# Usable kiosk session confinement

Task queue: [Ordered task queue](Kiosk-Prompt-Queue.md).
Next task: **C04u — [Qualify baseline entry and approval on Ubuntu](Kiosk-Prompt-Tasks/C04u-baseline-operations.md)**.

## Outcome

Keep passwordless kiosk sign-in and everyday product use working on supported
computers. Prevent a smart technical child from using ordinary kiosk routes to
reach a desktop, terminal, SSH, remote desktop or unrestricted application.
Preserve genuine parent approval and time/app enforcement.

This is a new execution plan. This revision changes planning and launcher-path
metadata only, with the requested documentation commit and push. It does not
execute the rebuild, accept active product changes or run product tests.

## Highest priority: product usability

**Product usability is the highest priority. Unexpected machine configurations
must not break passwordless sign-in, the request form or core end-to-end use.**

Every failed product use caused by our protection/confinement must have a
well-justified, concrete intentional breach effort available to a smart technical
child who is not a professional or world-class hacker. A protection review must
name the deliberate action, the child's actual access, the prohibited result
and why blocking that exact route is necessary. Pair it with a working normal-use
control. Unfamiliar files, services, package versions, permissions or configuration
alone do not supply this justification.

An unjustified protective failure is a product bug. Remove the unnecessary
protection, isolate the affected optional action or recover the owned state.
Do not rename a normal-use failure “intentional refusal” or “infrastructure.”
Explicit administrator policy and genuine parent denial remain authoritative.
A genuine essential-service/enforcement outage is an operational fault, not
evidence of a breach or successful confinement; keep safe retry/exit while fixing
it, without offering an unrestricted desktop or granting unauthorized access.

Human time choosing a language, reading a dialog, deciding a request or typing
a parent password is not machine-startup time. Trusted lazy loading and ordinary
package/account administration must not require a private product protocol.
Optional presentation/service failures use fallbacks and cannot veto core use.

## Mandatory threat scope: reasonable child effort

Include ordinary session selection, shortcuts, TTY/terminal attempts, SSH and
remote-desktop login attempts as the kiosk account, exposed links/choosers/handlers,
automatically exposed launch actions and simple changes to files/settings the
child can actually control. Block the unwanted route while keeping permitted use.

Very low-level attacks requiring expert exploitation are out of scope. Do not
assume arbitrary execution as the kiosk UID, compromised trusted packages/root,
kernel/boot/firmware exploitation or a sophisticated native-loader exploit chain.
Custom Python runtimes, ELF rewriting, continuous library auditing, per-import
authority protocols and private GI/graphics-driver images are not prerequisites.
Trust supported installed Python/GTK/system code; exclude demonstrably
child-controlled inputs at their actual selection boundary.

Engineering injections may help verify a real route but do not expand this
threat model. Do not infer child intent from machine drift. Broker validation,
parent authentication and ordinary time/app policy retain their existing scope.

## Target design

### Mandatory baseline: v1.3 kiosk session confinement only

**Build from the kiosk session confinement code in `releases/v1.3`, adding
justified protections. Do not subtract restrictions from main/v1.4 confinement.
Do not restore all kiosk code from v1.3.**

Use release commit `188be907c46b1cd0dabae06ac898c43e75beb05e`, available in
the local object database. The pin, not a moving branch, is authoritative.
No branch switch or wholesale checkout reset is needed.

Main remains the source for all non-confinement, non-security kiosk features:
shared request UI, Preferences/language, duration units/presets, notifications,
What's New, artwork, feedback/diagnostics and other current features. Keep other
main product code, including broker authorization/grant behavior, time/app
enforcement, packaging improvements and test tooling.

C01a/C01b/C01c/C01 map functions/configuration, active edits, callers and test
consumers before replacement. C02a–C02 reconstruct only session confinement
from the pin and connect it to main's feature code; C02d/C02e finish removal.
Shared Makefile, PAM, lifecycle, frontend and broker files require selective
hunk/function changes. Compatibility glue must not import the old confinement
framework by default. The release's old GDM hook is historical source, not proof
of correct routing on current GDM.

Use standard session/account/service integration and the smallest effective
route barriers. A copied v1.4 private graph, retained-view system, global inventory,
custom loader or admission protocol is not the baseline. Preserve necessary
authorization and owned cleanup behavior without preserving its old mechanism.

## Task boundaries

The highest-priority block is source-boundary review, session-confinement rebuild,
host TA cleanup and installed/E2E TA cleanup. Prove ordinary public use on both
targets before adding protections. Then review actual breach routes, add finite
protections with matching tests, qualify compatibility and close product/TA/docs
together. The queue is the sole task order; briefs hold finite deliverables.

The queue separates session, feature and automation source review; runtime,
broker, frontend, account, lifecycle and PAM preparation; activation and removal;
each automation layer and each protection boundary. Baseline operation
qualification precedes its customer journeys. Final host variation, optional
fallback, exposed-action and consumed-input acceptance each have their own
platform task. Aim for
15–30 minutes for ordinary work; the queue and briefs name longer indivisible
cutovers or installed histories explicitly. Estimates include reading, checks,
review, cleanup and close-out; they are not timers.

C01 records source findings and sizing risks without editing future queue rows.
If unexpected independent work remains when a consumer is selected, use the
[prerequisite handoff](Execution-Plans.md#execution-and-delegation): insert only
a contiguous unchecked prerequisite block immediately before that consumer,
preserve its original Scope/acceptance and earlier dependencies, and return
`prerequisite_required` after owned cleanup. Resume the consumer to verify its
full deliverable. Do not resize later tasks during another task's close-out.
Keep each fault/recovery/reentry history complete. No old completion transfers.

Every product slice includes the directly affected test and registration repairs
needed to pass its own checks. C03/C04 audit remaining automation, rather than
licensing broken imports or known customer regressions between product tasks.
C02a/C02b1/C02b/C02c1/C02c2/C02c prepare replacement slices while keeping the
selected production path coherent and buildable. C02 alone switches confinement
selectors, entry, PAM and package activation, including owned upgrade handling;
earlier frontend/broker decoupling may land only when independently compatible.
Prepared modules have no alternate live admission path. C02 removes temporary
live adapters/fallbacks; C02d/C02e delete the now-unconsumed runtime/native and
feature/protocol code. C03 cannot start until this source cleanup is complete.
No installed baseline or new protection work precedes the cleanup block.

## Acceptance

### Core product journey gate

Use the installed product's public actions: parent configures one child's
time/app limits; child reaches the normal request path; kiosk opens without a
password; child/approver selection and genuine parent authentication grant the
requested time and chosen soft-app access; the child can use it while hard
blocks remain; expiry or revocation restores the expected limits. Cover the
shared child-overlay request path when changed code serves both surfaces.

Also verify denied/cancelled approval makes no grant, Cancel/exit/reentry works,
a fresh request succeeds after switching sessions, and human pauses do not
cause forced logout. Preserve main's kiosk feature controls. Reuse existing
registered cases/operations; this is a finite regression slice, not all-product TA.

### Finite compatibility and defense checks

| Family | Required public result |
| --- | --- |
| Ordinary use | Core journey, fresh/repeated entry and retained main kiosk features work on each final candidate. |
| Host variation | One unrelated package/layout change and valid local PAM/service variation leave passwordless use intact. Unknown content has no admission vote. |
| Optional failure | Missing artwork/style/catalogue or optional service, including native-language fallback, leaves core form and genuine approval usable. |
| Recovery | A transient required-service interruption and one owned interrupted/stale state recover within finite machine-work bounds; live/foreign sessions are preserved. One unavailable child must not unnecessarily block requests for a healthy child. |
| Lifecycle | Relevant product/dependency update and subsequent entry preserve policy, features and justified activation; routine ambient drift needs no reboot. |
| Deliberate breach | Ordinary desktop/TTY/SSH/remote-desktop and exposed-launch/input attempts are blocked with permitted controls; genuine administrator/parent denial is honored. |
| Diagnostics | A retained original cause remains understandable after recovery and in a real Parent diagnostic download, without PII or submission. |

C04b maps baseline compositions without claiming qualification; C04u/C04f
implement or renew the changed public entry/approval operation on each target.
Additional independent operations require bounded prerequisites before their
first consumer, rather than being hidden in one qualification task. C04 confirms
readiness before C05u/C05f run the complete customer journey. C10 does the same
for final acceptance. A changed operation's old qualification is not reusable
merely because its function name or selector is unchanged.

C04/C10 bind exact existing or newly registered selectors, finite inputs and
restoration. Remote-desktop coverage names the supported provider and verifies an
ordinary-account positive; absent service is not a passed refusal. Probes and
fault injections supply engineering evidence separately from customer results.
No expert attack matrix, whole-host scan or Cartesian combination campaign.

Both `onpc-Ubuntu26.04` and `onpc-Fedora44` require applicable public results.
This does not broaden platform support or claim current Fedora release readiness.
New startup/loading changes invalidate affected earlier evidence; rerun only
those complete histories. A denied normal entry or diagnostic-only screen is
never a usability pass.

## Product and test automation must match

C03a1–C03 remove or port v1.4 confinement-specific unit/component/UI fixtures,
assertions and registrations. C04a–C04 do the same for system/E2E helpers, scenarios,
selectors, qualification inputs, coverage and documentation. Retain stable
customer case identities, required behavior, main feature coverage and historical
evidence. Remove tests of discarded implementation details; do not weaken a
customer outcome to accommodate broken code.

Every protection addition includes its own targeted tests and normal-use control.
C13 checks that no discarded mechanism survives as a hidden product dependency
or mandatory TA assertion. Existing maintained resource/retention rules still
apply; this plan authorizes no blanket deletion of artifacts or VM baselines.

### Cleanup includes committed code and old-plan active changes

**The relevant active confinement changes were created by the superseded
execution plan. They are cleanup inputs, not accepted deliverables to preserve.**
Inventory both checked-in main/v1.4 code and the old plan's staged, unstaged and
untracked changes, including new files and generated-input definitions. A file
being committed, locally modified, newly added or previously reviewed gives it
no entitlement to remain. Remove obsolete, conflicting, unfinished, duplicate
or unused code from either source as needed. Do not keep legacy or garbage code
as disabled copies, unselected fallbacks or speculative compatibility layers.

The C01 source/disposition table records provenance (release pin, committed main
and active old-plan delta), the retained behavior, action, receiving task, callers,
build/install/removal wiring and test consumers for each relevant interface.
C02d/C02e and C03/C04 verify removal against both inventories. A source-baseline
commit made for launcher ownership does not accept the old work or exempt it
from deletion. Preserve main's non-confinement features and unrelated work;
preserving a feature does not require keeping its obsolete confinement coupling.
Recorded evidence/checkpoints and owned installed state follow their retention
and migration contracts, rather than being treated as disposable source files.

Cleanup is limited to this confinement replacement and its affected consumers,
not a repository-wide refactor or cleanup. Within that scope, remove unused code,
imports/includes, generated-input definitions, build/install/removal wiring,
fixtures, selectors and superseded planning prose instead of leaving disabled
copies, compatibility shims without consumers, redirects or orphan briefs.
Keep current implementation descriptions accurate until the cutover; retire
obsolete prospective obligations and migrate surviving requirements to their
owning documents. Historical source decisions remain in Git, and accepted
evidence/checkpoints retain their existing ownership and retention protections.
The source/test disposition map and final audit must account for every removed
interface's callers. Unrelated product code and unrelated active work remain
preserved. This session updates the cleanup plan; future execution performs
these product and automation removals.

## Implementation baseline

The active v1.4 replacement is not accepted. Earlier source review reported optional/cosmetic
admission coupling, a global child-roster/NSS dependency, incomplete manager/fence
recovery and extra frontend readiness coupling. These are reasons to rebuild
from the specified release slice, not a backlog to perfect the old mechanism.
The unimplemented custom Python/native-loader proposal is discarded.

The [C01 source boundary](SystemDesign/Kiosk-Confinement.md#c01-selective-replacement-boundary)
supersedes the earlier frontend work report: the selected source has no visit
validation protocol or stylesheet fallback, and no active old-plan delta supplies
them. Current form readiness protects accounts, preferences and single-flight
requests; paint timings do not gate approval. Preserve those real feature guards,
pending-authentication cancellation and the direct broker request interfaces.
The post-authentication lifetime boundary is prepared by C02b1, with caller and
installed qualification obligations retained by C02b/C04. C-only locale and
stylesheet limitations remain receiving-task obligations, not accepted historical fixes.

## Scope reconciliation

This master, its queue and C-series briefs replace the former execution plan.
Old decisions and reports remain historical in Git/runner artifacts; they are
not active requirements or inherited acceptance. C01/C03/C04 reconcile current
design, reliability/proof consumers and TA against this plan. Do not preserve
obsolete tasks, native receipts, view generations or custom loading obligations
as hidden prerequisites. Saved controller checkpoints and artifact ownership
remain untouched. The launcher keys saved state by master path; this sole master
now lives at `docs/Kiosk-Session-Confinement-Plan.md`, also the wrapper's default.
The old master and its superseded briefs are removed, with incoming links updated;
there is no duplicate master, redirect or unused task brief.
Do not use ordinary `--reconcile` to overwrite the old R-series checkpoint.
For an existing old owner only, use the explicit former path
`--plan 'docs/Kiosk-Resilience-Plan.md' --stop` through the maintained launcher.
Owner attachment/stop resolves its path identity even without the former file.

### Before execution

These are launch prerequisites, not C01 deliverables or acceptance credit:

- Any old kiosk-plan owner must be inactive with its recorded cleanup and pending
  Git transaction resolved through the maintained owner/recovery route. A new
  namespace never bypasses that ownership. Old-path attachment/stop remains
  available even though the old master file has been removed.
- Commit the reviewed planning files before starting the controller. Resolve the
  pre-existing product/test changes that overlap this queue into a preserved,
  reviewed source baseline or isolated checkout before starting the controller.
  A source-baseline commit records work in progress, not product acceptance.
  Preserve unrelated changes and existing staging; no blanket staging, discard,
  manual checkpoint edit or implicit adoption is allowed. The shared launcher
  protects dirty baseline paths and otherwise cannot commit task close-out.
- Use the checkout's existing branch/upstream and credentials for the launcher's
  per-task pull, commit and push. Resolve missing configuration externally;
  do not change Git configuration as a task workaround.

The requested planning commit/push is allowed in this session; product-baseline
reconciliation, owner recovery and task execution remain deferred. `--check` proves
document structure/acceptance metadata only, not Git readiness, old-owner cleanup,
fresh-namespace availability or installed behavior. Verify those gates when
execution is explicitly requested; keep all tasks unchecked until then.

## Task execution contract

Each brief inherits this master's binding requirements. Start at
[System design](System-Design.md) and the [test map](TestAutomation/README.md)
for the affected owners; apply [Approval tools](Approval-Tools.md), the
[ordinary-plan execution/close-out contract](Execution-Plans.md#execution-and-delegation)
and [failure handling](../tests/README.md#handling-test-failures).
Use the task's exact source routes and finite checks, not a full-repository read.

Use maintained runner help/inventory and the lowest effective selectors with
explicit timeouts. UI/VM/storage work triggers its mandate. Any new or changed
reusable installed operation or scenario composition needs the
[shared live qualification](TestAutomation/E2E-Execution-Contracts.md#live-verification-contract)
before its consumer; a host mapping task cannot grant that qualification.
Keep candidate, commands, original expected/actual results and restoration in
maintained runner records. Complete owned cleanup and required independent
review before closing only the selected row and advancing the sole pointer.
Host/review/reconciliation evidence cannot replace an installed result.
Unforeseen independent work follows the selected-consumer handoff above.

### Launcher handoff and validation routes

Predecessor IDs refer to delivered scope in maintained owners, never a deleted
brief or saved guest state. Each selected task records its exact owned paths,
source/test dispositions, checks, expected/actual result, remaining blocker and
cleanup through the ordinary launcher's structured handoff. Keep the original
consumer's scope and acceptance when inserting prerequisites. No task silently
closes another plan's row or modifies a future task during close-out.

Use `tools/kiosk-prompt --check` for master/queue/brief structure. Use the
[maintained host consistency selection](TestAutomation/E2E-Execution-Contracts.md#completion-and-document-cleanup)
after planning or inventory edits and
`tools/run-tests unit 'tests/unit/test_execution_plan_launcher.py'` for launcher
path metadata. Discover product selections with `tools/run-tests --help`,
`tools/run-tests --list` and the selected installed runner's `--list`; there is
no invented C-series test selector. Keep finite values, qualification scope,
command, timeout and restoration in the recipe/catalogue or system-case owner
before its consumer starts. Product checks and `make build` apply only during
later implementation, not as a substitute for this planning validation.

## Execution

Use [Approval tools](Approval-Tools.md), [Execution plans](Execution-Plans.md),
the [test ownership map](TestAutomation/README.md) and
[failure handling](../tests/README.md#handling-test-failures). The coordinator is
GPT-6.1 Sol High; unresolved core design uses bounded Sol xHigh work under
AGENTS.md. Obtain independent Astra xHigh review for product changes and the
protection design, with explicit **Usability priority: passed/failed** and
**Threat scope: passed/failed** findings and resolutions. Review must challenge
unjustified refusals and unnecessary complexity.

Read-only validation:

```sh
tools/kiosk-prompt --plan 'docs/Kiosk-Session-Confinement-Plan.md' --check
```

After a later explicit execution request and the launch prerequisites above:

```sh
tools/kiosk-prompt --plan 'docs/Kiosk-Session-Confinement-Plan.md' --tasks 1
tools/kiosk-prompt --plan 'docs/Kiosk-Session-Confinement-Plan.md' --tasks 0
tools/kiosk-prompt --plan 'docs/Kiosk-Session-Confinement-Plan.md' --stop
```

These are alternatives: start with one task, select all remaining tasks, or stop
at a safe boundary. To attach without changing the current task limit, use the
same `--plan` with neither `--tasks` nor `--stop`. Omitted `--vm` uses configured
enabled targets; installed briefs still require every named target. A narrowed
diagnostic selection grants no other-target acceptance. No task execution,
checkpoint rewrite or product acceptance occurs in this planning revision.

During execution use the lowest effective maintained checks, `make build` after
packaged changes, and the VM/UI/storage mandates when triggered. Never install
the product on the development host. Ordinary product strings retain all-language
requirements; What's New synchronization still needs explicit authorization.
Close only with matching product/TA/docs, both-platform public evidence, justified
remaining protective refusals and completed owned cleanup.
