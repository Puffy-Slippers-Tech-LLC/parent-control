# Test evidence and export target design

This is a proposed infrastructure design, delivered through the
[plan](Export-Execution-Plan.md) and [queue](Export-Task-Queue.md). It does not
describe new commands as implemented or replace existing runtime contracts.
E01 audits history and inventories; E01a proposes concrete protocols and interfaces;
E01b independently reviews and freezes schemas, coverage and task allocation before
implementation. E14 owns composed validation; E14a owns independent final review.

## Investigated failures and remaining exposure

Repository history and existing regressions show several distinct causes.
Commit IDs are historical source references, not passing test evidence. E01
rechecks complete changes and callers rather than relying on commit titles.

| Historical source | Finding | Required prevention |
| --- | --- | --- |
| `4cf81254` (2026-09-16), `test_regression.py` | Missing evidence-directory initialization blocked a run | Initialize and register atomically; test clean first use as well as reuse |
| `7e3f4698` (2026-09-23), storage-migration regressions | Test output moved from system temporary paths into shared storage | Use shared allocation and explicit legacy readers; never guess or reconstruct roots |
| `f1270ba7` (2026-09-28), `test_dev_tool_installation.py` | Installed helpers were bound to an absolute checkout path, breaking worktrees | Resolve the invoking checkout through the validated helper and retain repository identity |
| `e420ac4e` (2026-10-04), retained export guidance in `tests/README.md` | Repeated exports can evict other reports still needed for close-out; the commit documented this exposure | E03/E05/E06 deliver capture before rotation and reusable exports; retain the existing guidance until delivered |
| `0a87b716` (2026-10-06), `test_recovery.py` and retention cleanup-safety regressions | Startup recovery can retire an oversized completed execution allocation outside ordinary count rotation | E04 covers automatic host/privileged recovery as well as ordinary pruning; failed or unacknowledged required capture must preserve the original |
| `31c8c32c` (2026-10-11), `repair_evidence.py` and `test_fix_tests.py` | Original reports and command records can disappear during repair; retained diagnostic tails are bounded and partial | E07a reuses snapshots for diagnosis, preserves truncation/refusal status and never substitutes tails for complete proof |
| `c8fbcd58` (2026-10-17), recovery-diagnostic bundle regressions | Shared and selected-target diagnostic journals needed export discovery; first export and absent optional storage needed distinct handling | E01 inventories `qualification_storage.recovery_session()` and `vm_probe` producers; E06a captures their finalized records while retaining diagnostic status and existing refusal checks |
| `41f23bfd` (2026-10-18), checkpoint and repair regressions | Another invocation can replace a repair's selector checkpoint | E07a retains original selectors and existing host-only replay; malformed state and VM/mixed mismatch keep their refusals |
| `ac5573ff` (2026-10-19), execution-plan regressions | Legitimate destination-only evidence repairs could violate protected queue comparisons | Normalize only proven reference bookkeeping; protect claims, scope, completion and checkpoint ownership |
| `71473c09` (2026-10-20), `test_plan_evidence.py` and recovery tests | Accepted proof needed preservation beyond disposable sessions; stale controllers complicated recovery | Extend existing cumulative publication and restart recovery instead of another archive/launcher state machine |
| `502181f1` (2026-10-20), reference-parsing regressions | Sentence punctuation could become part of an evidence path | Generate structured references and share a tested parser; distinguish literal filename punctuation |
| `3e5cb3f3` (2026-10-20), bundle/helper/plan regressions | Interrupted publication and missing-reference renewal needed exact resumable handling | Separate missing proof from access/integrity refusal; preserve transaction and original attempt across restarts |
| `009f719c` (2026-10-20), verified-record regressions | Repeated archive verification made startup unnecessarily expensive | Verify once per pinned read scope, invalidate on mutation, never trust an unchecked cached path |
| `2ddcf5f7` (2026-10-20), retention/bundle regressions | Concurrent finished evidence readers were incorrectly exclusive | Shared read ownership; publication/cleanup excludes readers and writers in a defined lock order |
| `dbf40859` (2026-10-21), prerequisite/capacity recovery regressions | A failed capacity attempt can leave partial queue edits or a removed brief before a usable response exists | E07 preserves captured inputs, suspended work and session accounting through the existing recovery route; private fixtures simulate failures without starting a model |

Current [retention](../../tests/README.md#aggregate-output-retention) explicitly
warns that every ordinary export consumes a session and can evict another report.
The existing [plan evidence](../../tools/plan_evidence.py) captures explicit
result-check references and the selected queue row; reference rewriting is
limited to selected or previously completed queue Estimate cells. References in
design modules, catalogue prose and other consumers can remain disposable.
The [document checker](../../tools/document_checks.py) checks inline destination
existence, not matching result identity, reference-style links or fragments.
The developer reported another occurrence during this plan's authoring: two
earlier report links expired and retained-copy investigation began while an
installed check was still running. Reproduce that ordering with private host
fixtures: an unrelated synthetic check remains active while both legacy
references resolve from exact retained members. Never interpret that as authority
to inspect or publish the unrelated active owner's mutable allocation.
The developer also reported an older evidence link expiring when a new run
rotated local reports. E06/E14 must reproduce that startup ordering through the
[required regression histories](#required-regression-histories), including a
failed capture whose original remains required. These incidents need prevention
at producer and retirement boundaries, beyond a destination repair after loss.

The [kiosk verification record](../SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits)
also discloses raw system allocations rotated before archival despite surviving
host reports. These losses show that a summary or generic accepted locator cannot
replace the original result/JUnit/TAP/input/cleanup records. Large historical
bundles also approach the finite file limit; copying every old generation
indefinitely is not a capacity strategy. Treat each existing fix as a retained
regression, not an instruction to implement the same fix again.

## Scope and quality boundary

Change test tools, support, launchers, metadata and their documentation only.
Product behavior, product diagnostic downloads/uploads, product installation,
customer scenarios, UI-provider qualification, test verdicts, case inventories
and acceptance obligations remain with their existing owners. This plan runs
no product or VM acceptance. All implementation checks use host-private fixtures,
including helper/privileged/target protocol simulations. Do not weaken a test
assertion to make reference maintenance easier.

Keep public artifact reading/copying in the existing maintained reader. The
`tools/export` wrapper executes this plan; it must never become a competing copy,
archive or privileged shell route. Reuse shared storage, retention and bundle
publication. Add capabilities to existing scoped helpers only when needed, with
normal argument validation, installation regressions and setup routing.

## Stable and specific references

Use a versioned logical evidence identity that survives relocation and generation
rotation. Bind owner/repository/plan or run, task or case/check selector, attempt,
declared target, exact source/input identities, result status, original member
and digest, and command/cleanup dependencies. Retries and changed inputs receive
distinct identities; identical bytes from different checks are not equivalent
claims. A resolver must prove the requested record matches the requested context.

Extend the existing verified manifest/receipt/accepted locator rather than
introducing a second ZIP format. Generate document links selecting an exact
record, not merely the latest run or a generic `accepted-evidence.json` file.
Freeze the readable link/selector syntax through E01a/E01b and deliver it in E02/E09.
Preserve original member provenance and allow safe checkout-relative resolution;
do not treat an old absolute checkout path as current authority.

Capture callers supply structured records; free-form prose scraping is a legacy
reader only. Enumerate document consumers explicitly, including queue cells,
briefs, catalogue/design prose, report links and handoffs. Generated references
must distinguish live evidence, accepted historical evidence, superseded attempts,
unavailable historical proof and malformed/unsafe references. A stable locator
without a verified matching member remains insufficient proof.

## Capture and publication

Capture finalized check records before their execution journal can rotate, rather
than waiting for final task completion. The producer supplies an explicit finite
selection of result records, selection/input manifests, command logs, applicable
JUnit/TAP and owned-cleanup records. Preserve failed and interrupted attempts
under their own identities. Partial records remain partial and cannot become
passing acceptance. Bulk media stays separately referenced with an explicit
lifetime; do not silently omit media required by the original check.

The existing bundle route requires finished owners and independent publication.
Do not remove those guards to enable early capture. Introduce an owner-authorized
handoff of finalized immutable records into a bounded working collection. Define
the active-run authentication, locks, read-only finalized subset and acknowledgement
that makes it safe to release the source. Reject arbitrary reads from another
active run and any source mutation during transfer. Cancellation or a failed
acknowledgement must preserve the last valid source/publication and a resumable
record. Long task continuation, suspended prerequisites and later Git close-out
must not release unpublished required evidence.

Before retiring a source, confirm required captured dependencies are durable.
Publish the verified accepted manifest/locator before retiring superseded owned
generations. Recover crashes at capture, commit, locator replacement and retirement
through recorded identities. Keep the controller's protected queue/checkpoint
transaction separate from document rewriting; agents never edit checkpoints.
Every new or changed shared dependency follows the
[controller compatibility guard](#controller-compatibility-guard) in the task
that introduces it, before that task can close or the next task is admitted.

## Lifetime, capacity and reuse

Separate disposable output, working required proof and accepted referenced proof.
Ordinary last-three-run rotation must not delete the only copy required by a
working task or accepted reference. Prefer verified copying/carry-forward over
indefinitely pinning original execution allocations. Maintain an authoritative
reference/dependency catalogue; arbitrary document text must not create deletion
authority or allow unlimited retention. Unfinished and suspended consumers hold
their exact required collection until release through their owner.

E01 inventories every retirement entry point and its callers: ordinary
`Store.session()`/`prune()`, startup `Store.reconcile()` with `completed_guard`
through host and privileged recovery, publication commit/finish/recovery and
explicit discard. E04 applies required-dependency and durable-acknowledgement
checks at each applicable boundary. Failed capture, pending acknowledgement or
insufficient capacity cannot make an otherwise required source disposable.
Retain automatic oversized retirement for unreferenced disposable evidence;
unknown/replaced resources and absent discard authority remain refused.

Preserve existing finite byte, file, depth, selection and manifest limits unless
a separately reviewed requirement changes them. Account simultaneous old,
staging and new payloads, receipts and failed recovery allocations before starting
work. Deduplicate identical payload storage without merging differing provenance.
Plan bounded collection segments/compaction when one cumulative archive approaches
its limit; segmentation is not permission to multiply owner budgets. If required
proof cannot fit, report exact projected usage and a supported archive/release
action before destructive rotation or an expensive retry. Preserve current proof.
Required accepted proof has no automatic expiry merely because unrelated tests
ran; retirement requires released dependencies or verified replacement through
the owning contract. Explicit discard authority remains unchanged.
Historical references declared informational rather than required by any active
consumer may transition to explicit unavailable status under that owner. They
must not pin bulk output forever, silently vanish, or continue advertising
materialized proof. Capture remains finite; reaching a genuine required working
set limit is a capacity error, not permission to weaken a test.

Repeated export of the same verified source/selection should return a reusable
private export/receipt without creating a retention slot. Revalidate identity,
content and authority before reuse. A missing or replaced export must not be
returned as success. Distinct same-basename files retain distinct provenance.
Use grouped atomic publication for related files, shared reader locks and one
verification per bounded pinned read scope. A later changed archive invalidates
that scope; deduplication must not introduce unsafe hardlinks or shared writable
payloads. Keep source files unchanged and caller/root ownership boundaries intact.

Resolve explicitly selected, finished retained copies without unnecessarily
locking every unrelated execution journal. The existing selection catalogue can
eagerly inspect selected-target journals; E01a/E01b must freeze selective ownership and
lock ordering that allows an old archived member to resolve while a new producer
on that same target is active. This is an exact archived-member read, not an
exception allowing reads from active mutable sources. Ownership, conflict and
live-path revalidation still apply wherever the request actually depends on them.

Storage stays local/private under the shared allocator. Surviving a host loss or
materializing evidence in another checkout requires an explicitly configured
archive/import route; a Git link is no backup. External hosting, uploads and new
cloud dependencies are outside this plan. A missing local archive must be
reported as unavailable, never mistaken for successful verification.

## Proportional validation

Use one structured classification across readers, document checks and launchers:

| Condition | Required behavior |
| --- | --- |
| Wrong task/check/attempt/target/input, corrupt digest, unsafe ownership/path, untrusted publication or a conflicting record | Block the affected operation; preserve evidence and give a finite actionable diagnostic |
| Proof required by the current task or a declared active dependency is missing | Block acceptance; resolve an exact verified archive member or return the existing scoped renewal handoff; never invent a pass |
| A newly authored evidence or required instruction reference is broken, ambiguous or points to the wrong existing report | Block that reference's publication with document/line/identity details; unrelated suites do not rerun |
| A protected queue/checkpoint claim changes beyond authorized bookkeeping | Preserve the original transaction and follow the existing reconciliation/recovery contract |
| Equivalent relative spelling, harmless sentence punctuation, presentation-only formatting outside protected cells with an unchanged declared claim, or changed physical location with identical verified identity | Normalize or warn; preserve protected labels and claim bytes and do not reject otherwise valid infrastructure results |
| Unchanged historical proof is unavailable and no current acceptance/dependency relies on it | Record explicit nonpassing availability debt once and show an advisory; do not repeatedly block unrelated work or spend repair sessions |
| Optional presentation link/anchor is broken without affecting a required instruction or evidence identity | Give a scoped advisory; required reading/command and evidence references remain blocking |
| Access denied, integrity failure or active/foreign owner | Report the distinct refusal; never relabel it as expiry or retry authentication after denial |

The user explicitly authorized relaxing trivial validation while retaining test
quality. Implement this as typed severity and dependency relevance, not blanket
ignore lists, reduced assertions, fabricated receipts or suppression of errors.
Bind historical debt to the exact reference/claim revision; a changed or newly
introduced bad reference cannot inherit an exception. A historical unavailable
status is never a check pass, task completion or permission to use that proof.
Required/optional classification comes from the owning contract and structured
consumer declaration, not inferred from prose or chosen to bypass a failure.
Integrity, authority, identity and protected-claim failures take precedence over
presentation advisories. A new optional presentation anchor can be advisory
under its declared role; a required instruction or evidence reference cannot.
An absent, conflicting or changed consumer-role declaration cannot downgrade a
required reference to presentation or historical debt. Validate that declaration
against its owning contract before applying an advisory; changing the role or
claim invalidates any retained advisory classification for that reference.
Changing a label from `Ubuntu passed` to `Both targets passed` changes the claim,
even when its destination is unchanged. It never receives format-only treatment;
protected queue labels remain literal under existing transition guards.

Separate offline syntax/structure validation from evidence materialization.
Plan `--check` remains model-free, VM-free and Git-free; it must be usable on a
clean checkout without old local output. Semantic preflight validates only the
selected operation's required closure. Repository-wide audit is explicit and
read-only; unchanged unrelated history is reported without blocking unrelated
task execution. Inspect required identities early and validate publication again
at the mutation boundary. Avoid repeated full-archive scans and repair loops
when no relevant input changed. Diagnostics identify class, consumer/line,
expected versus actual identity, scope and one supported recovery route without
echoing secrets or dumping raw transcripts.

## Compatibility and migration

Retain old helper commands and versioned manifests/checkpoints until every
inventoried consumer has a verified route. Older running controllers keep their
code: use normal session-boundary restart and exact resumption. Preserve preexisting
dirty/staged work, accepted results, targets, session counts, queue order and
scope. Do not run competing launchers or rewrite protected evidence cells outside
the existing controller-owned recovery contract.

### Controller compatibility guard

Extend `plan_launcher.response_validator_sources()` and its existing content-change
regressions as shared dependencies are changed or introduced. E01 inventories
the controller's relevant validation/storage dependency closure, including
`test_retention.py`, `test_storage.py` and any extracted identity, reference,
capture or severity module. Follow the current callers into `test_input_transfer.py`
mutation guards, `test_activity.py` ownership and `launcher_git.py` close-out;
record which files affect the controller's retained decisions and why any audited
file is excluded. Include the authenticated helper dispatch where its source
changes affect those decisions. Use an explicit reviewed source inventory; no new
watcher, archive state machine or unbounded filesystem/import scan is needed.
Each introducing task registers its relevant dependencies and runs the guard's
private regressions before completion; E07 is the integration check, not the
first opportunity to add restart protection.

Change actual dependency-file bytes in fixtures, including an extracted module
while the original eight guarded files remain unchanged. Assert session-boundary
stop before another task, corrective session or blocked-answer continuation,
with exact response, inputs, counters and ownership retained for a fresh controller.
Connect the real fingerprint reader to the worker in these histories: a separate
hasher test plus worker tests using mocked source dictionaries cannot establish
the restart guarantee. Snapshot the registered inventory before mutation; verify
unchanged bytes cause no restart and every newly registered dependency is covered.
Preserve normal restart allowances under the existing launcher contract; capture
or retry operations grant no additional allowance. Older specialized controllers
retain their own lifecycle policy and use its supported
safe-boundary restart; this does not add model retries or change their budgets.

### Legacy reference migration

Inventory tracked references and explicitly registered local catalogues, not an
unbounded filesystem scan. Classify each as exact live proof, exact archived
proof, wrong/ambiguous destination, historical unavailable, example or operational
path. Preview finite migrations with exact original bytes and expected proof
digests; apply only an unchanged verified selection. Destination-only repairs
retain claims. Genuine historical proof-loss disclosure uses the existing exact
authorization/recovery route when it changes protected claims; absent authority
produces a concrete proposal and debt record, not a checkpoint edit or a false
completion. No missing product acceptance is executed by this plan.

## Required regression histories

These histories use private stores and simulated authenticated helper/controller
entry points. They perform no VM operation, actual authentication or model launch.
The ordinary-launcher module's `synthetic_plan_evidence` autouse fixture stubs
capture, carry, preservation, recovery and rewriting. Cross-boundary histories
must use the real evidence functions instead of those stubs and verify the
resulting private records. Retain the lighter isolated fixtures for their own
unit scope; they supply no composed evidence-lifetime acceptance.

1. **A later run rotates an older report.** E06 creates report A, its declared
   consumer/reference and complete result/input/command/cleanup closure. Start
   later runs through startup retention until A's original report path is actually
   retired, including more than three runs. Resolve A's exact check, attempt,
   target, inputs and dependencies through the stable reference with no check rerun
   or changed verdict. Assert the original path is absent, compare the complete
   retained closure's bytes/digests and keep A's invocation counter at one through
   resolution. E04 repeats retirement with failed capture and unacknowledged
   handoff: ordinary pruning and automatic oversized startup recovery must retain
   the required original until verified durable capture permits retirement. Also
   test unreferenced oversized evidence still retiring. E14 composes producer,
   consumer and reference generation across this sequence. A stale acknowledgement
   for a different attempt, source identity or dependency closure must not release
   the original; only the matching verified durable acknowledgement permits it.
2. **Two expired reports during an unrelated active producer.** E05a exercises
   the authenticated helper's `bundle-plan` dispatch through real
   `Selection.catalogue()`/`load()` and retention inspection, with a validated
   synthetic plan, target T, retained bundle B and two explicit old references.
   This is the existing `--plan`, `--target`, `--bundle`, repeated `--reference`
   selection shape; register any changed interface before use. Record the pre-fix
   eager-catalogue refusal or verify its earlier delivered fix/regression, then
   require both exact archived members to resolve while an unrelated producer on T
   holds its journal.
   Do not mock away selection or locking. Assert no unrelated journal inspection,
   mutable-payload reads/adoption, source rotation or checkpoint writes during
   resolution. Direct `inspect()`/`bundle-read` success is a useful control but
   insufficient acceptance: it already avoids the eager target catalogue. Keep
   missing, wrong-attempt/target, corrupt, denied and actual active-source refusals
   distinct. Do not reintroduce an already fixed refusal to manufacture a failing
   baseline. E07/E14 exercise this selection through an ordinary-plan consumer;
   any subsequent publication changes only that consumer's owned transaction.
   Simulate only caller authentication, target registration and privileged identity
   operations at the host boundary. Keep helper dispatch, plan validation, source
   selection, archive verification and retention locks real. Assert both original
   paths are absent and both requested original members and digests match.
3. **Changed dependency in a running controller.** E02 onward runs the
   [compatibility guard](#controller-compatibility-guard) when dependencies change;
   E07/E14 compose real file changes with continuation, blocked answers, suspended
   work and fresh-controller recovery. No extra task/session credit or stale
   validation is permitted.

## Infrastructure acceptance

Each task owns meaningful host regressions. E14 reuses their helpers and results
to add boundary-spanning histories, rather than rebuilding each task's safety
matrix. E14a independently reviews the final source and retained results.
Final composition uses private
producer/controller/helper fixtures to reproduce the historical failure families,
including more than three source sessions, more than three unrelated exports,
multiple targets with identical basenames, separate retries, changed source,
concurrent readers, denied authority, active owner, wrong checkout, capacity
exhaustion and injected interruption at each durable transition. Exercise
continuation, suspension, restart and accepted Git retry without running models,
VMs or product suites. Assert exact retained bytes/provenance, durable recovery,
bounded allocation counts/bytes, unchanged foreign resources and scoped severity.
Include two vanished legacy report paths with two exact retained members while
the same synthetic target has an unrelated active producer. Both references
must resolve without rotating sources, changing a checkpoint or reading/adopting
live mutable payloads. A missing archived member stays unavailable; denied access,
corruption and foreign-active ownership remain distinct refusals. The required
regression histories above select the actual integration paths; isolated bundle
member reads or mocked change dictionaries do not replace them.

The outcome is fewer avoidable errors with preserved test quality: repeated reuse
does not rotate exports; required proof survives unrelated runs; wrong existing
destinations fail; format-only changes do not fail; historical unavailable proof
is explicit and cannot satisfy active acceptance. All frozen consumers receive
a delivered migration or an explicit compatibility disposition. Independent final
review checks those outcomes against the source and original failure inventory.
