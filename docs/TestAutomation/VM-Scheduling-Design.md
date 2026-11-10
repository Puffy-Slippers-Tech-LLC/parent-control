# Unified VM scheduling execution plan

Status: in progress. Completion is recorded in the ordered task queue.

Current validation constraint: all VMs are occupied and expected to remain so
for a very long time. Use non-VM validation only; do not attempt or wait for VM
validation. Required live qualification remains pending until VMs are available.

Task queue: [Ordered task queue](VM-Scheduling-Task-Queue.md).
Next task: **004 — [Move repairs and rounds onto shared scheduling](VM-Scheduling-Tasks/004.md)**.

## Goal and launcher

Make scheduling simple, lean and robust; optimize final ownership and control
flow rather than diff size. Replace duplicate machinery instead of hiding it
behind shared helpers or permanent compatibility paths.

Reuse `tools/execute-plan 'docs/TestAutomation/VM-Scheduling-Design.md'` when
execution is separately requested. A `tools/scheduling` wrapper adds only an
alias: this plan needs no special acceptance engine or options.
Use the existing [ordinary-plan driver](../Execution-Plans.md#extension-boundary)
and its task, recovery, delegation and close-out contracts. Do not add a launcher,
namespace registry, service or new command protocol.

## Core logic review mandate

Every task in this plan inherits this mandate, including repairs, recovery and
optimization; task briefs need not repeat it. Before completing any task that
changes core scheduling, coordination, admission, persistence or ownership logic,
obtain an independent, read-only review from an **Astra xHigh** subagent. This
review requirement overrides ordinary reviewer model defaults while preserving
the existing coordinator, implementation and escalation policies.

Activate the following actual goal in the reviewer's session under the shared
[goal activation contract](../Execution-Plans.md#execution-and-delegation);
prompt text alone does not satisfy it:

```text
/goal Simple, lean, robust; do not overengineer. Prefer solutions that simplify the resulting codebase as a whole, not merely minimize the patch. Keep refactoring within the task’s scope.
```

Resolve actionable findings and revalidate material revisions before completing
the task. Independent review does not replace the task's scoped validation or
acceptance requirements.

## Resulting ownership

| Owner | Responsibility |
| --- | --- |
| `vm_case_queue.py` | Pure selected-inventory, ordered-group and prerequisite planner |
| `vm_test_queue.py` under `run-tests` | One test coordinator per run: family work, claims, failure FIFO, impact-based admission and attempt acceptance |
| `vm_queue.py` | One VM executor: availability, reservations, capacity, supervised workers and owned cleanup; also serves preparation |
| `test_checkpoint.py` | Validated persistence, never another scheduler |
| `test_source.py` | Shared checkout admission gate, reader/writer leases, durable writer fence and source generation |
| `fix_tests.py` and selected agent adapter | Impact-triage/repair actions and native high-effort profile, requested rounds, allowances and Git outcomes |
| Existing pool, disk queue and host scheduler | Cross-run resource ownership and existing host scheduling |
| Existing presentation | Render authoritative state without a second completion ledger |

Ready workers request their family's next FIFO item; the coordinator records
each claim before execution. Preparation owns its finite operations and journals
without test state. Repair requests bounded attempts through the coordinator and
owns no family queue or VM dispatcher. Remove `fix_tests_queue.py`, repair-owned
family journals, per-VM round/category pipelines, duplicate slot handling and
completion reconciliation at the repair cutover.

## VM pool and family scheduling

The VM pool means the run's allowed VMs: resolve `--vm` when specified;
otherwise use the configured eligible VMs under the
[target-selection contract](../Mandates/VM-Mandate.MD#target-selection).
Availability and concurrency choose active workers within that pool; they never
expand it or remove a family's required coverage because its VMs are busy.

Each family independently runs the full specified case selection under existing
platform-applicability rules. VMs within a family are equivalent: a normal case
needs one accepted execution on any allowed VM in that family, with no credit
transferred between families. Cases wait in a FIFO per family, preserving selected
order and indivisible groups; ready VMs take the next item without advance shards.
Required-VM repair and recovery retain their original ownership.

Fill normal test slots evenly across families with available VMs and pending
work, giving each family one worker before adding a second, and so on. With
three families offering three available VMs each, concurrency six chooses
`2/2/2`; concurrency five chooses `2/2/1`. Rotate remainder priority as slots
refill; when concurrency is below the family count, every pending family still
gets a turn. Busy or drained families do not strand usable capacity, and active
attempts finish through cleanup before a worker yields its slot.

## Failure impact and admission

In `fix-tests`, collect bounded failure context, then use a fresh, adapter-resolved
high-effort session to decide whether more than one case may be affected; root
cause is not required. Pending triage, `yes` and `unsure` hold new case admission;
an evidenced `no` permits other eligible cases to continue. Already admitted work
finishes through cleanup. Each unresolved failure owns its hold, so one isolated
result cannot reopen admission while another failure still blocks it.

Keep isolated repairs queued while normal work continues. Acquire the existing
exclusive source lease at a naturally drained finite-pass boundary, preserving
source safety without snapshots or unverified concurrent reads. Blocking failures
force that drain; admission resumes after their fresh verification and close-out,
when no other blocking ticket or writer remains. Task 004 owns triage profiles,
durable decisions, recovery and the deliberate replacement of stop-on-any-failure.

## Delivery boundaries

The briefs preserve the proposed architecture and assign every change to one
deliverable. Establish retained-state protection first, then shared execution and
ordinary coordination, then one coherent repair/round/accounting cutover. Old
transactions must finish through their original supported implementation before
switching, or follow an explicitly authorized reset. Upgrade never authorizes
discarding claims, source edits, Git work or accepted progress.

Keep original selectors, family equivalence, lifecycle prerequisites, ordinary
runner failure semantics and required-VM recovery. Impact-based repair admission,
run-wide rounds and VM-independent logical task counts are deliberate changes
owned by task 004. Host work runs once per pass through its existing scheduler.
Preserve local-only execution and
the existing SSH-host refusal; remote workers, machine-wide concurrency changes,
general policy frameworks and unrelated test/fixture redesign are outside scope.

Each task owns its scoped validation and cleanup. Task 005 supplies bounded live
qualification; earlier host checks do not claim it. Maintain existing critical
execution/ownership coverage under the [test scope mandate](../Mandates/Test-Scope-Mandate.md),
without test-tool UI coverage or a helper-by-helper matrix. Move enduring rules
into [test maintenance](../../tests/README.md), the
[installed runner guide](../../tests/integration/README.md#aggregate-scheduling)
and applicable mandates as implementation lands, before removing completed briefs.
Trust checked prerequisites under the [completion contract](../Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery);
record short results, not proof archives.
