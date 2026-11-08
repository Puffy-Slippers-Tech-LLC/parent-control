# Unified VM scheduling proposal

Status: design only; no implementation or execution authorization. This proposal
describes the intended replacement architecture. The current
[test maintenance contract](../../tests/README.md#all-established-regressions)
and [VM mandate](../Mandates/VM-Mandate.MD) continue to govern existing tools.
This is not an execution plan and does not add or close E2E queue tasks.

## Objective and decision

Make the overall scheduling code simple, lean and robust. Optimize the resulting
ownership and control flow, not the size of the diff. Replace structures that
obstruct that result; do not preserve two implementations behind a shared helper
or add compatibility layers that become permanent scheduling paths.

Use one test scheduling coordinator for ordinary VM tests and repair execution,
owned by `run-tests`. Use one VM executor underneath it for reservations,
availability, concurrency and worker lifetime. Preparation uses that executor
through its authorized launchers; it does not enter the test coordinator.
`fix-tests` supplies repair actions and requests test passes, not another test
queue or another VM dispatcher.

One coordinator belongs to one run, not the entire machine. Existing VM-pool and
disk admission mechanisms coordinate resources across runs and checkouts.
No service, message broker, plugin framework or general workflow graph is needed.

## What is duplicated today

The [ordinary queue](../../tools/vm_test_queue.py) and
[repair queue](../../tools/fix_tests_queue.py) share
[case grouping and claim helpers](../../tools/vm_case_queue.py), but separately
manage family claims, worker orchestration, completion reconciliation and
restart state. The repair queue additionally maintains independently advancing
per-VM category/round pipelines. Sharing the claim function does not remove
these competing implementations of the same responsibility.

The existing [VM dispatcher](../../tools/vm_queue.py) also serves preparation.
Make it the common executor, moving reservation and capacity handling out of
test and repair callers. Keep family work selection in the test coordinator.
These are complementary responsibilities: only one owns pending test work;
only one implements VM admission and lifetime.

## Ownership after replacement

| Component | Owns | Must not own |
| --- | --- | --- |
| `vm_case_queue.py`: case planner | Selected inventory, ordered case groups, prerequisite and focused-retry scopes | Claims, VM slots, completion or repair decisions |
| `vm_test_queue.py`: test coordinator | Pending test work, family placement, claims, failure ordering, attempt acceptance and scheduling transitions | VM-pool/slot implementation, agent sessions or Git operations |
| `vm_queue.py`: VM executor | Availability, reservations, execution capacity, supervised worker lifetime, command completion and cleanup | Family/case queues, passing-test credit, repair tickets or rounds |
| `test_checkpoint.py`: persistence | Validated storage and resume of coordinator state and bounded attempt checkpoints | Independent scheduling decisions or repair state inferred from display files |
| `test_source.py`: source guard extracted from the repair queue | Checkout source reader/writer leases, retained writer fence and source generation | Case queues, VM placement or repair policy |
| `fix_tests.py`: repair workflow | Requested rounds/passes, agent sessions, intervention, budgets and repair/Git transaction outcomes | Case assignment, VM slots or passing-test credit |
| Existing VM pool and disk queue | Cross-workflow resource ownership on the executing host | Run-local case progress |
| Existing presentation | Rendering authoritative test and repair state | Its own completion ledger |

Workers execute assignments. They do not pull from or write a family queue, pick
their next category, advance rounds or decide that a family is complete.
The test coordinator is the only writer of test scheduling state. It accepts
worker results and repair outcomes through validated transitions. The executor
reports resource and operation state; it cannot mark a case complete.

Host test resource scheduling remains with the existing host scheduler. Each
requested pass runs its selected host work once, without VM slots. Host work
participates in the shared source guard and repair admission boundary. Unifying
VM scheduling does not require replacing the host resource scheduler.

## Work and execution

A test work item is an existing independently executable group: one E2E case,
one standalone system check, a stateful lifecycle history or an independent
system area. Preserve the current planner's preparation and prerequisite rules;
do not schedule prerequisite phases as separate normal work.

Normal test work targets a selected family. Recovery and focused repair attempts
retain their required VM. Do not invent arbitrary resource expressions or
dependency graphs. The planner produces bounded runner requests; the executor
launches them on the VM chosen by the test coordinator.

The coordinator selects the next eligible item and records its assignment before
execution. One VM executes at most one attempt at a time. Only selected VMs in
the correct family may receive family work. Required-VM verification and recovery
cannot move to another family member. No assignments may overlap on selected
case identities within a family and pass.

Use one ordered family queue for the selected categories in a test pass. Preserve
selector order, reverse-order behavior and lifecycle ordering through the planner.
Do not introduce new category-wide barriers; explicit prerequisites determine
which work can execute together. The selected families partition one pass, rather
than independently advancing rounds. VMs do not own categories, passes or rounds.

An execution attempt has a unique identity, its pass, assignment, VM and source/input
identity. Verification is a fresh attempt for a bounded scope of the same work;
it is not another queue or scheduler. Work, attempts and repair transactions need
distinct identities because they have distinct lifetimes, not separate generic
frameworks or databases.

## Shared VM execution, including preparation

The executor has one acquisition path and one finite-operation path. Conceptual
internal operations are `open(vm)` and `worker.execute(operation)`, with owned
close/cancellation through existing supervision. `open` yields an already
reserved, identity-checked worker or an availability wait; the parent can continue
servicing other VMs. `execute` obtains execution capacity and returns only after
the operation and its owned cleanup. It borrows an enclosing reservation when
present. These names specify responsibilities, not new public CLI commands.

The test coordinator requests workers for eligible VMs and assigns family work
when they become available. Request a worker only for admitted pending work or
retained recovery, and cancel an unused reservation waiter when its family work
has drained. A busy VM with no remaining assignment must not delay the pass.
Preparation supplies the selected finite VM list and
one authorized operation per VM to a `run_each` convenience operation in the same
executor. `run_each` enumerates the list; it does not own another pool, semaphore,
case queue or durable scheduling record. Operation results are returned by VM.

Preparation owns confirmation, baseline/snapshot semantics, operation journals,
input checks and final helper refresh. Its workers use the same availability and
capacity handling as tests. It continues after an individual VM preparation
failure; cancellation prevents queued operations while an active baseline
replacement finishes. Snapshot preparation retains its cooperative cleanup.
Those are fixed existing operation contracts, not arbitrary policy callbacks.
Helper refresh runs once after all baseline workers release their reservations.

Preparation never receives a repair ticket, round number, case checkpoint or
passing-test result. No test-specific state is needed to share VM execution.

Keep the [VM checkout and disk ordering](../Mandates/VM-Mandate.MD#central-vm-checkout).
The executor retains independent supervised workers for VM ownership; the
parent does not acquire several VM reservations. Nested work borrows the
appropriate worker's receipt. A worker waiting for an occupied VM does not
consume execution capacity needed by a free eligible worker.

Treat a VM reservation and an execution slot as different resources. A failed
VM's worker retains its reservation through investigation, verification and
owned cleanup, but does not retain a slot while waiting for its repair turn.
The active repair uses the required VM through that same worker. No worker may
hold an execution slot while waiting for source admission. Repair execution
borrows its writer's source lease instead of waiting for a new reader lease.
Never require a repair to obtain capacity held by its waiting workers.

Guard startup imports separately; do not hold a source reader lease while waiting
to acquire a VM. After acquisition, recheck source ownership before operation
admission. A foreign retained writer fence refuses normal work and releases an
otherwise idle reservation rather than parking on a VM needed by recovery.

An idle worker may release its reservation when it has no retained ownership or
transaction to finish. Cancellation prevents new work and waits for owned
cleanup. Never release claims or reservations merely because a case event,
timeout or controller exit was observed.

Apply configured concurrency through this one admission path, including explicit
single-VM selections and preparation. Preserve the current scope of concurrency;
do not quietly redefine it as a machine-wide cap across all independent runs.
The VM pool remains the cross-run exclusivity authority.

Current [VM configuration](../../tests/integration/vm_config.py) refuses SSH-host
execution; only local execution is implemented. Keep that refusal. Per-host
resource identities must remain explicit, but this refactor does not implement
remote workers or count an offline/unselected host's capacity.

## Failure and repair control flow

The test engine implements three concrete behaviors: ordinary stop-on-error,
continue independent work, and repair. Retain the existing public failure
semantics; these behaviors do not need an extensible policy framework.

In repair mode:

1. Record the failure and stop new source-reading work before relinquishing the
   failed attempt's source protection. Already admitted histories, areas and
   cases finish normally through cleanup. Collect additional failures in their
   observed FIFO order.
2. Once readers drain, grant the recorded repair transaction exclusive source
   ownership. The failing VM's supervised worker retains its reservation.
3. Recheck a queued failure after preceding repairs, through the same bounded
   attempt path, before spending another agent session.
4. Let the repair controller investigate and edit. Any test execution it requests
   returns to the engine; it cannot select another VM or widen original selectors.
5. Run fresh exact-case verification, including only required predecessors. Missing
   case identity uses the existing
   [bounded verification-selection contract](../../tests/README.md#scripted-repair-loop),
   not a whole-category fallback. Accept the result only after final cleanup.
6. Finish the repair controller's existing commit/push/propagation transaction.
   Only then close the ticket and admit the next repair. New normal work waits
   until the failure FIFO is empty.

The coordinator owns test admission and acceptance; the repair workflow supplies
editing and Git actions through the fixed interface below. Do not recursively
launch a family scheduler for verification or introduce a new background
service. Do not hold scheduling locks while waiting for an agent, VM,
subprocess, Git operation or cleanup.

## Fixed interface between scheduling and repair

Use a synchronous repair handler composed into the existing supervised run.
The coordinator invokes it only after normal work drains; its nested test
requests use the already idle coordinator and executor. Existing supervision
continues to service cancellation and reload. This needs no concurrent callbacks,
public command protocol or new interprocess message framework.

| Operation | Caller and precondition | Result and authority |
| --- | --- | --- |
| `execute_pass(request, repair_handler=None)` | Public runner or repair workflow; validated original selection, saved pass identity and failure options | Pass result: accepted case outcomes, terminal failures, cancellation/suspension and whether a repair or source change occurred; coordinator owns all assignments |
| `repair_handler(ticket, execution)` | Coordinator; FIFO head, no admitted source readers, exclusive source fence and original VM reservation retained | Repair outcome; handler owns agent/intervention/Git actions and persists their continuation before side effects |
| `execution.attempt(purpose, target=None)` | Active repair handler; `purpose` is recheck, diagnostic or verification | Fresh bounded attempt through the same runner and result validator; engine fixes the VM and original selectors and validates any replacement target |

A ticket contains its stable ID, original work/selection, reported or attempted
case, original VM (empty for host work) and failed attempt ID. It contains no
caller-supplied executable command. A replacement target is allowed only under
the existing bounded selection rule when identity is absent or retired.
Case-based suites cannot widen a missing-case retry to a category. Leaves without
case events keep their existing finite command-level verification; do not invent
a case identity or require a whole aggregate to qualify them.

Recheck occurs before new edits and can close a queued failure resolved by an
earlier repair. Diagnostics return observations and never close a repair.
Verification records an accepted attempt tied to the target and the current
source/inputs. Prior passes cannot substitute for it. If subsequent actions
change those source/inputs, that verification cannot close the transaction.
Attempt/result references are validated records, not a new cryptographic proof
system or another independently reconstructed completion ledger.

The handler returns exactly one of these outcomes:

- `resolved`: references the coordinator's successful recheck with no new edits,
  or its fresh verification plus the repair workflow's completed Git transaction
  (including the existing no-change close-out). The coordinator validates those
  references and releases only the qualified work.
- `leave_failed`: the existing intervention policy permits continuing; retain
  failure status. The source guard must establish that no unfinished writer or
  unresolved repair-owned edits remain before normal admission can resume.
  This is transaction ownership, not a requirement for a clean Git worktree;
  unrelated pre-existing work remains protected.
- `suspended`: investigation, verification, intervention or Git close-out is
  unfinished. Retain the ticket, source fence and continuation for resume.

An exception, lost handler result or mismatched attempt/transaction reference
leaves the transaction unfinished; none implies `resolved`. The coordinator does not interpret agent
claims or implement Git phases. Repair/Git journals own those phases; scheduling
stores their transaction reference and accepted outcome, not duplicate fields.

The durable scheduling modes are intentionally small:

| Current mode and event | Next mode and action |
| --- | --- |
| Running; first repairable failure | Draining; enqueue before releasing source protection and block new admission |
| Draining; active operations and readers finished cleanup | Repairing; invoke the FIFO head under its source fence |
| Repairing; ticket safely resolved or left failed | Remain repairing for the next ticket, or return to running when the FIFO and source fence are clear |
| Any mode; cancellation or unresolved handler | Stop admission and finish owned cleanup; return stopped/suspended with retained unfinished state |

Normal failure-stop still requests existing cooperative cancellation. Repair
drain lets admitted attempts finish. A task limit blocks new logical task
admission but lets an admitted repair and close-out finish. Restart recovers the
recorded mode and transaction instead of guessing them from dashboard status.

Source reader/writer protection includes startup imports, input preparation and
reload. An unfinished writer retains its durable source fence after cancellation
or process death. Host and VM runs sharing that checkout observe the same guard.
A failure may be left terminally failed under the existing intervention policy,
but unresolved source ownership cannot be cleared to permit normal work. Preserve
the retained recovery state rather than accepting unverified edits implicitly.

## State, credit and recovery

Keep one logical scheduling record for a run, including its family partitions,
claims and accepted case completions. Use existing validated storage primitives.
Choose the schema for clear ownership; preserving an old shape is not a reason
to retain duplicated state or reconciliation code.

Workers may write bounded attempt checkpoints and reports. Those are inputs to
one result-acceptance path, not additional family completion authorities. Before
credit, validate the run, pass, assignment, attempt, VM and original selection
against the recorded claim, plus the runner's final teardown/cleanup result. Missing,
stale, mismatched or merely diagnostic results cannot grant a pass. A late
cleanup failure leaves the affected work unfinished even after case pass events.

Partial case passes may survive a failed grouped attempt only where the existing
checkpoint contract permits them. Required lifecycle state is still recreated
by the next attempt. Bounded verification completes only the work it actually
qualifies; omitted cases and later phases remain pending.

On restart, exclude another coordinator with the existing ownership mechanisms,
recover retained VM claims under their original workers, finish accepted Git
close-out, then drain repair transactions before admitting normal work. Never
requeue an uncertain attempt until maintained recovery proves its cleanup.
Execution may repeat after a crash; accepted completion must never be fabricated
to promise exactly-once execution.

Standalone cleanup and reset must use the same coordinator state transitions
under exclusive ownership, rather than independently rewriting family claims.
Storage helpers validate and persist those transitions; they do not reconstruct
another scheduling algorithm for recovery.

Preserve accepted prior passes under the existing resume rules. A source repair
requires fresh verification and refreshed content-qualified inputs for subsequent
attempts; it does not invalidate every historical pass or redefine the selected
total. Selector, inventory and reset compatibility remain governed by
[runner resume](../../tests/README.md#resuming-test-execution).

## Rounds, progress and task limits

Keep the useful existing distinction in
[the repair loop](../../tools/fix_tests.py): round 1 processes the selected
categories and repairs failures; rounds 2 through X require a complete selected
pass needing no repairs. A bounded verification closes one repair, not a clean
verification round.

The repair workflow requests passes through `execute_pass`. In a verification
round, any repair or admitted source change causes another fresh complete pass
of the same selection after repairs settle. Only a full clean passing result
advances the round. Without explicit categories use the full regression scope;
with explicit categories preserve those exact selectors. Never widen a selected
run to `all`. Terminally left-failed cases retain the established finite
fail-and-continue outcome, never a clean-pass claim or an endless restart loop.
Record the shared source generation at pass admission and finalization so a
repair by an independent participating host/VM run also marks the pass changed.
This is coordination among maintained tools, not exclusion against manual edits.

One run-wide round replaces independent VM rounds. Every selected family must
finish the required pass before the round can advance. This is needed because a
repair on one VM can affect tests already executed on another VM or the host.
Resume retains the current pass and its valid partial results; a newly requested
clean pass has a new identity and intentionally reexecutes its full selection.
That does not invalidate historical completion or reopen other execution tasks.

Report logical case progress per family and category within the current pass;
report the round/pass once for the run. VM tiles show assignments, attempts and
resource waits, not independent copies of the full family inventory. Preparation
and prerequisite replay do not inflate selected totals. Failure remains failure.

Preserve the documented logical
[task units](../../tests/README.md#scripted-e2e-implementation): round-1
category selections, explicitly selected verification categories, and one
composite task for an unfiltered verification round. A VM category task covers
all selected families, rather than multiplying with VM count. Exact-case repair
attempts and resumed close-out spend no additional task. A fresh selected
verification pass admits category tasks again; an unfiltered verification round
retains its composite task until its clean pass or terminal failure outcome.

Use existing `TaskBudget` admission and completion with stable task identities.
The coordinator obtains admission once before a logical task's first assignment
and records completion only when its selected scope is settled. Failed settled
work can consume a task without becoming a pass. An already admitted task may
finish across families; no new category task starts after the limit is reached.
Resuming an interrupted task uses its recorded admission, not another allowance.

Run-wide rounds and task counts independent of participating VMs are deliberate
changes from the current pipeline implementation. The reason is stable selected
work semantics when adding or replacing workers, not cosmetic uniformity. The
family partition does not create an extra workflow task. Implementation must
update help and owning contracts explicitly and reject incompatible retained
pipeline state rather than silently reinterpret its budgets.

Repair session allowances, intervention decisions, exact-case acceptance and Git
close-out remain repair policy. Moving scheduling must not silently alter them.

## Replacement and validation boundaries

Build toward the ownership table and remove the superseded path. In particular,
delete repair-owned family claim journals, category/round dispatch, VM slot
management and test-progress reconciliation. The repair queue module should
disappear after its repair actions and shared source guard have clear owners.
Do not preserve it as a wrapper around another set of mutable scheduling records.

Use an explicit version boundary for retained state. Translate old state only
where its ownership and completion have a lossless mapping. Otherwise refuse
before execution with the applicable original recovery route; never reset or
discard retained claims automatically. A compatibility reader must not execute
the old scheduler alongside the replacement. Migration cannot require perpetual
support for every historical pipeline format.

Check retained ownership before switching implementations. Finish old-format
repair transactions through their original supported implementation first, or
use the existing explicit reset contract when abandoning saved progress is
authorized. Neither an upgrade nor a schema mismatch supplies that authorization.

Future implementation validation should reuse existing execution-integrity,
checkpoint and ownership regressions, including the relevant portions of
[checkpoint coverage](../../tests/unit/test_test_checkpoint.py),
[VM-pool coverage](../../tests/unit/test_vm_pool.py) and
[runner coverage](../../tests/unit/test_regression.py). Case selection must follow
the [test scope mandate](../Mandates/Test-Scope-Mandate.md), not a new test matrix
for every helper or caller. No tests are added or run for this design document.

The implementation needs evidence that concurrent family work is not duplicated;
occupied VMs do not block free workers; failure drains before source writes;
verification is fresh and bound to the original VM; stale or incomplete results
cannot pass; restart retains ownership and valid progress; and cancellation
finishes owned cleanup. Include representative maintained live acceptance for the
affected boundaries under the existing VM authorization and runner contracts.
Tests or live acceptance for an implementation are not supplied by this proposal.

The final architectural check is equally important: one test coordinator selects
family work and owns its state; one VM executor implements resource admission and
lifetime for every caller; one path accepts test attempt results. Preparation
has no test state and repair has no alternate scheduler. A larger refactor that
reaches that state is preferable to a smaller patch retaining duplicate ownership.
