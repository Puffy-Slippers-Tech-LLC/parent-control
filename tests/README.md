# Test maintenance

Start with the [documentation map](../docs/TestAutomation/README.md) for ownership
and customer validation design. This document describes how to select and maintain tests;
it does not repeat completed setup tasks or historical acceptance results.

Use the section for the selected operation; an ordinary focused check does not
need the launcher implementation or retention details below.
Each task owns its checks and cleanup before marking itself done. Launchers
and later sessions trust completed rows and move to the next unchecked task.
They do not collect archives or revalidate old reports to prove completion;
report expiry never reopens a task. Follow the shared
[completion policy](../docs/Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery)
for current and future launcher/session behavior.

| Operation | Read |
| --- | --- |
| Decide whether to add, retain or remove tests | [Test scope mandate](../docs/Mandates/Test-Scope-Mandate.md) |
| Choose or run regressions | [Suite selection](#all-established-regressions); `tools/run-tests --help` and `--list` |
| Add a host module or change resources | [Parallelism review](#host-test-parallelism-review) and [coverage maintenance](#coverage-maintenance-workflow) |
| Investigate a failure or continue prior work | [Failure handling](#handling-test-failures), [reconnection](#aggregate-execution-and-reconnection), then [resume](#resuming-test-execution) if needed |
| Automate repairs or E2E implementation | [Repair loop](#scripted-repair-loop) or [E2E launcher](#scripted-e2e-implementation), respectively |
| Read, export or reclaim test output | [Artifact access](#prompt-free-test-artifact-access), [retention](#aggregate-output-retention) and [cleanup safety](#cleanup-safety-prerequisites) |
| Observe a host UI run | [Host UI viewer](#watching-host-ui-tests) |

Tests and agents must use `make install` as the single entry point for product
installation, reinstallation or upgrades from the checkout. It detects the
target distribution and invokes the internal `installdeb` or `installrpm` module.
Do not call separate package-specific installation targets or reproduce their
package-manager recipes in checkout-based test runners. Product installation
still requires an authorized installed-system target; the development host is
not an installation target.

Use the [shared support guide](support/README.md) before adding fixture code.
It maps existing broker, D-Bus, preview, package, VM and E2E helpers to their
contracts. Reusable code belongs in support modules, not collected case files.

For queued E2E implementation, follow the
[execution plan](../docs/TestAutomation/E2E-Execution-Plan.md) and its first
unchecked active row. The [building blocks](../docs/TestAutomation/E2E-Building-Blocks.md)
own reusable operations, not task selection. Each complete scenario remains its
own task and independent attempt. A fresh chat does not require rerunning
unaffected tests.

## All established regressions

Every test execution through `tools/run-tests` uses the same live dashboard and
final summary: category results, actual host branches and joins, durations and
overall wall time. Only selected categories appear; unused branches are omitted.
Cleanup is a lightweight serial ownership/recovery preflight before host work
or each VM worker's own tests. VM workers recover independently under their
reservations, so an occupied VM does not stall a free worker. Cleanup runs no
regression tests and has no host branch or cleanup join stage.
Recovery failures still fail the run; overall wall time includes cleanup.
For example, `tools/run-tests unit -k 'grant' static shell` runs the selected unit
tests followed by shell checks in one report. Each category keeps its own
arguments, and all selections are validated before execution. Arbitrary category
groups run in order; unit/UI selections and the established aggregates use their
qualified parallel schedules.
Help, listing and collection-only commands keep their inspection output and take
one category at a time. `tools/run-tests --help` prints usage, including how
the `all` aggregate breaks down into separately runnable pieces. `tools/run-tests --list`
prints the ordered JSON granular inventory. Each entry has a `description`, a
`scope` of `host` or `vm`, and
an explicit `args` array; executing each entry with those arguments covers the
same suites as `all`. It starts with unit and UI and ends with system and E2E.
Raw test output remains in the linked report streams.

Readiness and leaf/composite status are registered with each command in
`tools/test_commands.py`. New implemented leaves join the inventory and the
aggregate automatically; pending commands join when their registration becomes
implemented. Display names and retry handoffs do not require a second registry.

The inventory excludes composite aliases (`host`, `vm`, `all`, `check`,
`component-all`), focused/instrumented repetitions (`traceability`, `coverage`),
fixture-building helpers and named integration/recovery operations. These remain
available in the separate helper section of `--help`. Traceability is included
in source checks; package artifacts include the fixture payload. Bare
`tools/run-tests artifacts` now performs two fresh builds and their
reproducibility comparison, matching the granular artifact category in `all`;
`artifacts build` still requests just one build. UI's explicit inventory arguments
select the aggregate's non-live scope; the shared launcher applies that same
host-only boundary to focused UI commands. Owned cleanup and required package
inputs still run wherever the selected suite needs them.

The complete partition is **host + vm = all**, with **vm = system + e2e**.
Every implemented leaf belongs to exactly one of these scopes. Combine these
categories in one invocation; execution always orders host first, then system,
then E2E. For example:

```sh
tools/run-tests host
tools/run-tests vm --vm NAME
tools/run-tests host vm --vm NAME
tools/run-tests system --vm NAME e2e
tools/run-tests e2e --vm NAME
tools/run-tests host system --vm NAME
tools/run-tests host system e2e --vm NAME
```

`host` includes discovery, unit (including cleanup regressions), component, UI,
fixture runtime, source/traceability, static, child Node/GJS, backend checks,
publishing checks, two fresh package builds and reproducibility comparison.
It uses the complete aggregate's existing four-branch scheduling and stops at
**Join host branches**, without VM discovery, authorization or execution.
If unfinished prior work requires VM recovery, `host` refuses and preserves the
evidence rather than touching the VM.

`vm` runs system tests and ready E2E scenarios, preparing their required package
inputs without running host test suites. Separate `host` and `vm` invocations
may run in parallel. Each scope has its own activity lock, session discovery,
attachment, cancellation and retained results; combined selections reserve both
locks. Narrower categories use their owning scope's lock.

For routine Codex validation, preserve the scope justified by the change:
prefer `tools/run-tests ui` for UI-only checks and `tools/run-tests unit` for
unit-only checks, retaining any required file/case selectors. Use existing
launcher parallelism wherever supported within that selection. Do not expand
to `host` merely to accelerate a large suite. Direct unit/UI launchers remain
appropriate for narrow iteration or diagnosis.

`tools/run-tests ui` collects only its selected UI inventory, then runs the existing
[UI buckets](../tools/regression_ui.py) through the same four-branch scheduler
as `host`. The shared job builder in [regression.py](../tools/regression.py)
serves both routes; [selected execution](../tools/regression_selection.py) adds
no unrelated unit coverage, package builds or VM work. Other selected categories
remain ordered around UI execution.

Workers receive exact collected test IDs and the original validated options,
preserving partial files, parametrized cases, `-k`, `-m` and scoped ignores.
Collection and completion must match those IDs. Modules with shared fixtures
stay together; unreviewed modules run exclusively, and resource admission can
reduce concurrency. UI execution defaults to the host's 1800-second timeout per
bucket; an explicit `--timeout` replaces that default. `-x`/`--exitfirst` and
positive `--maxfail` retain one serial invocation with the original failure
limit. Help and collection-only requests do not schedule test execution.

Every UI invocation owns a private process group. Cancellation first
interrupts pytest for normal fixture cleanup; a deadline sends termination.
If it remains unresponsive, the controller kills only that owned group after 30 seconds.
Private preview/capture services remain in the group. The coordinator records
the failure or interruption and finishes its handoff, allowing `fix-tests` to
repair and retry a failed category instead of waiting indefinitely for a worker.
It also bounds pipe draining if pytest exits while a descendant retains stdout;
the group leader remains unreaped until cleanup finishes, preventing PID reuse.
After forced termination and confirmed leader exit, any remaining pipe readers
are closed; a writer in another session cannot extend the cleanup deadline.
Failed pidfd acquisition likewise closes readers before waiting for the killed
owned leader. These paths never signal an outside pipe holder.
This uses the shared controller rather than the host's `timeout` implementation.
Nested Shell runs use a separate [guardian](support/child_shell_owner.py), whose
stdin lifetime pipe detects cancellation or death of its pytest worker. The
guardian owns the short socket runtime and forwards scratch owner descriptors.
It requests the runner's trapped cleanup with SIGTERM, then retires unresponsive
work through the same bounded controller. Only this isolated guardian enables
Linux [child subreaping](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html):
kernel-adopted descendants of its sole explicit launch are recorded and reaped,
signalling only live children, even when private services create separate sessions.
No host process scan, environment match or executable-name match establishes ownership.
The runtime remains allocated until this entire tree has finished cleanup.
VM restoration keeps its separate guarded cooperative cleanup contract.

UI is a host-only category. Its shared launcher always excludes VM-dependent
`live_e2e` checks, including for focused marker or file selections. Direct
`tools/run-ui-tests` applies the same boundary and remains the serial narrow-check route. This development
tooling refactor activates on the next checkout launcher invocation (`none`);
it changes no installed helper, product service, or saved data.

Host UI category logs retain `ui-timing` events for every case's setup, call and
teardown, plus five-second checkpoints at instrumented operation completions.
The monotonic timestamps correlate directly with `resources.jsonl`. Aggregates
separate reader snapshots/waits, synchronous and batched AT-SPI calls, semantic
and keyboard input, preview launch/cleanup and session boot/teardown. Durations
are inclusive; `self_seconds` excludes instrumented children, so nested totals
must not be added. Checkpoints include active outer operations; a blocked call
cannot emit a checkpoint until it returns. No labels, input arguments, returned
UI text or exception messages enter these records. The existing report retention
owns the stream; timings do not change selectors, assertions or deadlines.
`ui-trace` records entry/exit with parent span IDs for GUI composites, registered
reader operations and waits. Wait stages identify predicate source locations,
attempt numbers, pending/query/incomplete retries, dispatch and sleep. Entries
are flushed before the work, so an unfinished span remains visible after forced
termination; a missing exit alone is not proof of deadlock. `ui-reader-timing`
retains the reader's existing actual tree/node counts and input offsets for each
registered operation. `reader.traversal` measures consumed tree generators,
including incomplete reads. Snapshot-call counts can include cached projections;
they are not counts of fresh traversals. Trace durations and operation deltas
are inclusive and must not be summed across nested spans. No predicate closures,
descriptions, GUI arguments or return values are recorded.
Phase checkpoints also retain worker CPU time, time spent writing the existing
event stream, synchronous query counts/durations by finite public protocol names,
and batch query counts/errors and occupancy. Batch wall time is recorded once
per batch size, never attributed to each parallel query. These counters distinguish
repeated or poorly batched reads from remote waiting and output overhead; correlate
them with the existing resource samples before choosing a correction. They add no
UI reads, input, poller or files and retain no bus/object addresses or query values.

Product tree discovery uses each fresh API inventory's native roles, topology
and logical availability. It observes labels on demand through scoped element
snapshots, while document aliases retain their precise readiness and capability
reads. Mutations and independent value/text result reads still resolve the live
control. Character and format-run inspection shares one text/document read within
its immutable projection, which is rebuilt at the next observation and invalidated
before input. External-provider complete observations and input guards are unchanged.

`tools/run-tests unit` collects only the selected unit inventory and balances
reviewed modules across up to four branches. The [unit buckets](../tools/regression_unit.py)
are shared with `host`; each module and its fixtures stay in one worker. Workers
use private pytest temporary trees, disabled shared caches and process-local
doubles. Package/native fixtures build into private staging directories.
Unknown modules run exclusively as a runtime safeguard. The retained fixture
output-refusal checks use small private files and ordinary unit
packing; fixture construction runs through its normal builder workflow.
This selection adds no other categories or cleanup prerequisite inventory.

Unit file/case selectors, `-k`, `-m` and scoped ignores preserve the exact
collected IDs, and each worker must account for every assigned case once.
Unit, component and UI selections accept `--timeout DURATION` or
`--timeout=DURATION` before or after test paths. Durations must be positive and
finite, with optional `s`, `m`, `h` or `d` suffixes. The runner applies the limit
separately to collection and each scheduled worker, preserving it through
parallel dispatch and serial failure-limit execution; it never forwards it to
a pytest timeout plugin. Unit and component have no deadline by default.
Their scheduled workers still allow 30 seconds for cancellation cleanup before
retiring the owned process group; an output pipe cannot hold shutdown open
indefinitely. Privileged cooperative cleanup keeps its guarded wait.
Direct UI keeps its 60-second default; scheduled UI keeps the bucket default
described above. Explicit limits use the shared owned-process controller and
bounded cleanup described above for UI.
`-x`/`--exitfirst` and positive `--maxfail` keep one serial invocation so the
failure limit remains selection-wide. `tools/run-unit-tests` remains the direct
serial route for narrow iteration or diagnosis. Its execution output also appears
in the left terminal of `tools/watch`, using the shared reconnectable session and
cooperative cancellation. Inspection/collection-only
commands keep their existing behavior. Unit buckets use the same CPU, memory,
swap and compatibility limits as other host work; I/O pressure is advisory for
ordinary units. Actual artifact construction retains its artifact I/O limits.

### Host test parallelism review

Every added host test module and every change to its resource ownership must
receive a parallelism review in the same task. Review mutable paths and caches,
owned subprocesses and cleanup, sockets/buses/displays, shared fixtures, external
services and CPU/memory/I/O demand. Private state qualifies for compatible
overlap; expensive work needs appropriate resource admission, not automatic
exclusivity. Keep module fixtures together and preserve exact selected cases.

Update the applicable [unit](../tools/regression_unit.py),
[cleanup](../tools/regression_cleanup.py) and [UI](../tools/regression_ui.py)
classifications with the isolation rationale. Cleanup modules participate in
both unit and prerequisite inventories and need both classifications. For other
host categories, review the [resource and compatibility policy](../tools/regression_resources.py).
Record the specific conflicting shared resource for any required exclusivity.
Do not declare work complete with a module merely left in the unreviewed fallback.

`test_e2e_baseline_auth_pause.py` uses pytest-private records, in-memory public
UI/transport doubles, fake clocks and bounded waited Perl children. It owns no
VM, display, socket, bus, external service, shared cache or fixture build; its
small CPU/I/O load permits compatible unit overlap. It adds no cleanup module
or resource owner. Existing MATE and TIME03 host checks retain those same
private resources and their current classifications.

The [host inventory regression](unit/test_regression_unit.py) detects modules
left unreviewed across all three inventories; a reviewed exclusive exception
requires an explicit path and concrete reason. Unknown modules still execute
exclusively at runtime so incomplete checkouts fail safely. Validate partition
coverage and compatible overlap for the changed scope using the maintained
launcher, without expanding validation to unrelated host categories.

`system` and `e2e` remain sequential within each VM. VM tests default to every
entry in `config/test-vm.json` whose `enabled` equals the string `"true"`.
Its positive integer `concurrency` limits active guests: 1 is serial, 2 permits
two simultaneous guests. Free slots refill until every enabled VM executes,
including after another guest fails. Cancellation stops queued work and waits
for active guests' cleanup. `--vm` accepts one name or ID, a comma-separated
list, `all-enabled`, or `all`. Explicit entries and `all` include disabled VMs.
Baseline and app-snapshot preparation use the same selector and rolling scheduler,
with `tools/prepare-vm` defaulting to `all` (including disabled VMs) in both
modes and app-snapshot preparation defaulting to enabled VMs; see the
[VM mandate](../docs/Mandates/VM-Mandate.MD#authority-and-operation).
All `--vm` options and Make `VM=` parameters accept either the exact configured
name or its `id`. IDs resolve from the current `config/test-vm.json` on every
invocation; changing or swapping them needs no helper refresh or baseline
replacement. Active runs keep their canonical names, so attachment uses the
current ID for the original guest. UUID pins, leases and journals remain scoped
to that guest. Names and IDs have no hardcoded mappings in consumers.
Host work runs once; VM workers keep individual reports and journals, with a
retained queue summary linking their logs and failure handoffs. Required package
inputs are prepared through the maintained builders. Repair agents remain serial
within each host or VM workflow; implementation agents remain serial.
`write-e2e` shares the VM execution queue through `run-tests`. `fix-tests`
owns independent per-VM case pipelines under the
[repair loop](#scripted-repair-loop).

VM ownership is coordinated by the host-wide
[VM pool](../docs/Mandates/VM-Mandate.MD#central-vm-checkout), keyed by domain UUID.
Requests for an occupied VM wait automatically across launchers and worktrees;
other VMs remain independent. Use `tools/vm-pool --vm NAME -- COMMAND ARGUMENTS`
to retain an investigation reservation between commands. One request chain owns
one VM at a time; batches use independent workers. Checkout-local activity and
retained results do not constitute a VM reservation.

`host-builds` remains a compatibility alias for `host`. Its `--serial-builds`
option runs publishing/builds after the host join for scheduling comparisons.

Complete categories and aggregates stop at the first reported
failure by default, with the same cooperative cleanup, final evidence and failure
investigation prompt as Ctrl+C. Use `tools/run-tests all --vm NAME --continue-on-errors`
(or the corresponding aggregate) to continue independent tests after failures.
Safety and infrastructure refusals still stop the run. Reattachment preserves
the original options. The flag takes no value and can accompany `--serial-builds`.
For selected granular categories, the leading `--stop-on-error` option enables
the same cooperative first-reported-failure cancellation without disabling
parallel scheduling, for example `tools/run-tests --stop-on-error unit`.
Ordinary selected commands keep their existing failure policy. The option
conflicts with `--continue-on-errors`.

### Resuming test execution

`tools/run-tests --resume` restores the latest public selection and retries its
failed or interrupted category and cases. It can also accompany the original
categories and selectors, for example `tools/run-tests --resume --stop-on-error
unit 'tests/unit/test_core.py' -q`. A new execution without `--resume` resets the
checkpoint and starts that selection from the beginning. Attachment to a live
owner keeps that owner's options; inspection never changes checkpoints.

Resumed category, bucket and overall counters include retained passes and keep
the original selected total in the dashboard, controller header and saved progress.
For example, after nine passes in a 100-case selection, completing the first retry
shows `10/100`, not `1/91`. `fix-tests` uses the same counters for its resumed
test runs and repair retries. A fresh verification pass starts its counts over.

Only completed cases without a reported failure are retained as passes. Failed
cases, interrupted cases and queued work run again; parallel workers retain
their independent completions. Pytest passes commit after teardown. An abrupt
owner/machine failure can lose the last one-second checkpoint interval, causing
those cases to run again. A failed final controller/cleanup audit repeats a case
so an empty selection cannot certify recovery. Changed selectors refuse resume;
start without the option to reset. Host and individual VM checkpoints remain
separate, and a retry can narrow an aggregate to an original category.
Case IDs above the snapshot length limit are replayed rather than retained as
passes. Resume repairs older checkpoints containing such IDs while keeping all
other valid passes; malformed state and unsafe files still refuse execution.

Preparation, ownership recovery and validated package inputs still run. System
upgrade and removal/repair lifecycle cases replay their state-changing predecessors when
needed to reach the failed phase. Commands without case events remain one atomic
test operation and resume at their category boundary. Small private checkpoints
use the shared storage/state route; retained reports keep their normal lifetime.

### Scripted repair loop

When baseline preparation is needed, follow the
[VM mandate](../docs/Mandates/VM-Mandate.MD#vm-host-setup-and-baseline) for mode
authorization, selectors and confirmation. Runners never prepare a baseline
implicitly; guest prerequisites are described in [VM preparation](integration/Environment.md).

Run [`tools/fix-tests`](../tools/fix-tests) for the configured enabled VM queue,
or with `--vm NAME` for one registered VM, to start or attach to the scripted
repair loop. Round 1 runs every entry in `run-tests --list`, using its explicit
arguments, until each passes. After a failure, a fresh Codex process receives
that run's generated investigation prompt, applies a repair, exits, and the
script uses `run-tests --resume --resume-case=CASE --resume-case-only` to retry that exact case
under its original selectors and on its failing VM, retaining required lifecycle
prerequisites. A passing retry leaves the category incomplete. The launcher
closes out the verified repair before resuming the remaining cases with
`run-tests --resume`, without repeating completed passes. Failures before a case
event retain the exact case the launcher was attempting as context, including
preparation failures; this does not claim that its test body ran or failed.
For the case-based `system`, `e2e`, `unit`, `component`, `ui` and `fixture-runtime`
categories, a failure without a reported case ID never triggers a whole-category
verification. Other leaves retain their command-level verification.
The repair agent can name one existing, relevant
`verification_case` within the original category and selectors and explain how
it exercises the failed operation and correction. Otherwise the launcher chooses
a recent case, or just the first case in that selection. Missing case identity
or uncertain relevance must not block selection or widen verification.
The launcher reruns that case
and its required prerequisites through the case-only runner, for diagnostic
execution and corrective verification alike. Each newly entered
category and each fresh verification pass starts without `--resume`.

For a configured VM queue, host categories run once and each VM owns its
system/E2E pipeline, checkpoint and reports through all requested rounds. The
registry concurrency cap limits these pipelines. Normal cases execute in
parallel through fresh case-only runner invocations with the original selectors
and required lifecycle prerequisites. Package preparation reuses content-qualified
inputs, rebuilding when source changes; each next case loads the current inputs
instead of retaining a whole category's frozen inputs.

Every failed case joins one launcher-wide FIFO repair queue. Active cases finish;
new normal cases wait until the entire queue is empty. Exactly one repair,
exact-case verification and commit/push/propagation transaction runs at a time.
Its source lease survives worker reload and remains held by its supervisor during
owned cleanup. Other VMs cannot load its unverified edits. A queued failure is
rechecked after preceding repairs land, before spending another agent session,
so a shared fix can resolve multiple VM failures without duplicate edits. A stopped
repair with unresolved edits keeps the source fenced for its retained recovery.
`RepairCoordinator` owns admission, FIFO ownership and release under the existing
shared gate; workers retain their execution and descriptor leases. Admission
checks the queue, unfinished source owner and kernel lease in one transition.
Explicit `--resume` derives `closeout`, `repair` or `complete` from the existing checkpoints:
accepted Git work runs first, then each FIFO ticket drains in one recovery worker
before normal work starts. The parent does not restart an incomplete recovery
worker to retry it with fresh case budgets.
Cancellation stops admission and waits for every active pipeline's owned cleanup;
resuming retains each VM's completed work. Task limits count host categories once
and VM categories per VM, across their independently advancing rounds.
Worker startup and reload imports also hold a source lease, and propagation
resolvers retain both workflow ownership and that transaction's lease through
cleanup. Explicit resume drains every retained transaction for each FIFO ticket before
host or normal VM work, retaining the source fence through ownership recovery;
completed pipeline labels never bypass checkpoint selector/round validation.
Lifecycle prerequisite rows are replayed by their dependent case's runner rather
than dispatched again as separate normal cases.

After confirming that the specific repaired case passed, the launcher stages
the repair's explicit owned files, commits them as `TA: Fixed CATEGORY CASE`
(with the VM name when applicable), and runs `git push` before any remaining
case, another repair session or category. It also completes
[shared worktree propagation](../docs/Execution-Plans.md#shared-worktree-propagation)
before advancing. This uses the current branch's configured upstream.
This per-case close-out applies to every category, whether host or VM.
Case verification requires the runner's teardown-complete pass for that exact
case and VM under the original selectors; a different failure alone does not
prove a pass. Non-case repairs in case-based suites require a fresh, teardown-complete pass of their
explicit bounded verification case. A saved pass from before the repair cannot
qualify it. The bounded pass closes only the repair; remaining category cases
stay pending and resume under normal parallel scheduling after close-out.
Diagnostic execution alone never triggers a commit. Agents report `stage_paths`
and leave staging, commits and pushes to the launcher. Pre-existing dirty or
staged work is protected; overlapping close-out refuses rather than including it.
Edits left by another repair or diagnostic in the retained launcher run recover
automatically when recorded session changes and exact fingerprints trace the
overlapping baseline back to a clean start. The original ownership checkpoints
remain intact; unrelated edits, mismatched fingerprints and pre-existing staged
work still refuse. Recovery grants no verification credit to the earlier case.
Staging, commit or push failures stop advancement and retain the accepted repair.
The next invocation with `--resume` retries that close-out before tests or agents, preserving
branch/upstream identity and recognizing an already-created completion commit.
Later file changes do not invalidate a recorded case pass or block its Git
close-out; the existing explicit-path and ownership checks still apply.
No force-push, automatic pull or Git configuration change is performed.
With `--resume`, unverified repair scopes survive restart separately from the fresh agent-session budgets.
If another invocation replaces a host category's runner checkpoint between
attempts, the repair launcher replays the same category and original selectors
once without saved passes. Only a validated checkpoint selection mismatch
permits this replay; invalid or unsafe state still stops with the runner's error.
VM and mixed requests retain the mismatch refusal because they can span
additional checkpoint stores that have not yet been validated.
`--rounds X` defaults to 1, running only round 1.
With X >= 2, it repeats verification X-1 times, labeled rounds 2 through X
in the top frame. Each verification round runs `run-tests all`; failures trigger
repair/category retries before another complete `all` run. Only a passing
complete run finishes the loop. Concurrently reported failures are handled by
category; interrupted companion categories are not falsely marked passed.
For each round-1 category, the launcher highlights
`Running category [category] (x/y)` beneath the test dashboard's `Overall` row,
then retains it after the completed test output with its position in the discovered list.
The exact argument arrays from that inventory are forwarded to the test runner.

Optional categories restrict both repair and verification: `tools/fix-tests host`,
`tools/fix-tests vm`,
`tools/fix-tests unit ui` and `tools/fix-tests "unit ui"` are supported.
Category arguments pass through to the runner, for example `tools/fix-tests e2e --id 6`
or `tools/fix-tests unit 'tests/unit/test_fix_tests.py' -q`. The exact selectors
are retained for repairs and every verification round. Launcher options such as
`--vm`, `--model`, `--effort`, `--rounds`, `--tasks` and `--stop` remain launcher-owned,
are recognized before or after categories, and are removed from the forwarded
arguments. For example, `tools/fix-tests e2e --id 6 --rounds 3` forwards
`e2e --id 6` for each of three rounds. Inspection
flags are not repair selections; use `run-tests` for listing or collection.
Expansion uses the same `suite_inventory` utility as the `run-tests` host coordinator.
`host` (also `host-builds`) expands to all implemented host leaves;
`vm` expands to all implemented VM leaves, and `all` expands to every
implemented leaf. The repair launcher preserves the runner's category definitions,
scope metadata and ordering without a separate category registry. Overlapping selections
are deduplicated in inventory order, and unknown categories or diagnostic helpers
are rejected. With explicit categories, round 2 repeats only those leaves until
a complete selected pass needs no repairs; it never invokes the `all` aggregate.
Without categories verification uses the full regression aggregate.
Categories, rounds and model options apply to new runs; attaching keeps the active run's options.
Host-only repair runs keep their own workflow owner and output under
`output/test-runs/host/fix-tests-host/`; VM-containing runs use the existing
`output/test-runs/host/fix-tests/`. Separate host and VM repair runs may overlap.
Attach with the same scope. Bare `tools/fix-tests --stop` cancels active host
and VM repair runs in the current checkout, requesting both cancellations before
waiting for owned cleanup. Categories or `--vm` narrow cancellation, for example
`tools/fix-tests host --stop` or `tools/fix-tests vm --vm NAME --stop`.
Without `--stop`, no categories select the VM namespace.

The launcher itself is Python scripting. New runs validate the selected model
and effort against the Codex CLI catalog before testing. Classification and
proven mechanical test repairs use **GPT-6.1 Sol Medium** in one session,
or **GPT-6.1 Sol Low** for unit failures.
App issues, uncertainty and unresolved security, concurrency, ownership or
difficult diagnosis end that session without edits and transfer to a fresh
**GPT-6.1 Sol High** session to recheck and repair, or **GPT-6.1 Sol Medium**
for unit failures. This raises reasoning effort
at the judgment boundary without paying for an additional adviser and a second
implementation context. Ordinary delegation stays disabled; the shared mandatory
[backend review](../docs/Execution-Plans.md#execution-and-delegation) remains
required only for core backend changes. Classification is not an
extra read-only agent before every mechanical repair.

If verification still reports the same case, its next repair escalates from
**GPT-6.1 Sol Medium** to **GPT-6.1 Sol High**, from High to **GPT-6.1 Sol xHigh**,
and from xHigh to **GPT-6.1 Sol Max**. A stall uses the same immediate escalation
ladder. Unit failures use a ladder one tier lower throughout:
**GPT-6.1 Sol Low → Medium → High → xHigh**, stopping at xHigh.
The runner-reported failure category selects the ladder, including unit failures
within mixed selections, expanded aggregates and aggregate verification.
The latest evidence and that case's previous repair summary accompany
each fresh session. Selected tiers survive blocker answers and returns to an
unresolved case; neither a blocker nor a diagnostic experiment is a failed repair.
A newly exposed case starts with Low classification for unit failures and Medium
otherwise, even in the same category.
Before a repair or diagnostic retry, the launcher copies bounded private failure
context into `failure-evidence-*.json` beside its control files. These snapshots
include the runner handoff, per-VM report logs and recent failed-attempt command
output/error tails, read through the scoped artifact reader when privileged.
They survive ordinary execution-journal rotation for the repair run's lifetime;
missing/refused reads and size limits remain explicit. Bulk captures retain their
normal retention policy. A snapshot is investigation evidence, never a pass.
Repair verification uses the existing runner checkpoint for the exact category,
selectors, case and target after teardown. An unrelated failure or aggregate
summary cannot substitute for that case's result. Completed repairs and saved
Git close-out do not reopen old reports or archive declarations.
The repair launcher keeps its current unvalidated response, prompt and session
metadata in the existing checkpoint for interrupted recovery. It does not copy
whole turn trees or carry proof bundles across tasks. Optional bounded failure
context is diagnostic; unavailable copies do not change a test result.
When reviewed decision dependencies change, `fix-tests` automatically replaces
its controller at a child-free boundary in the same live run. It retains the
owner lock, output stream, scratch leases, selectors, rounds, task counts,
case-session budgets, escalation tiers, diagnostic observations and answered
blockers. The fresh interpreter validates the exact retained response before
repair verification or close-out, keeping the original failure and owned-file
baseline. Reloading grants no new session or retry credit and requires no
reattachment or manual restart. Cancellation still takes priority. The separate
E2E implementation launcher retains its source-change handoff behavior.
The runner's `failure.json` includes `failures` entries with category, case ID
and VM name; host cases have an empty VM name. Worker bucket names, report paths
and model-generated labels never define a case. Multi-VM handoffs retain each
guest's identity. Within a category, handoffs preserve the order in which
failures were observed, so the first failure is repaired before later cases
that may have failed because of it. Repeated failures of the same case retain
its original position. The repair targets one reported case at a time and
reruns the original category selectors. A passing category clears its repair
handoffs.

Each case has at most **five agent sessions per launcher run**, including
classification, escalated repair and answered-blocker continuations. Counts survive
switching cases and later verification rounds; another case or VM has its own
budget. Non-case failures and legacy handoffs without case IDs share a category
infrastructure budget (VM-scoped when supplied). Verification and owned cleanup
after the fifth session still finish, and a pass is accepted. If further repair
is needed, the run fails before a sixth session or another blocker question.
`repair-stop.json` retains that case's identity, count, latest failure prompt and
last agent result, even if another case was repaired in between. An entire category
has no five-session cap. At the highest tier, `stalled` ends the run early when
there is no useful authorized next step; speculative edits or repeated attempts
are not required. Lower-tier stalls escalate within the same budget. Missing prerequisites
and permissions use their maintained repair/blocker routes, not model escalation
by themselves. These are session limits, not token budgets.

Detaching preserves the live loop. After a stopped/dead owner, `fix-tests --resume`
restores the latest selection, completed categories, current round and pending
runner checkpoint. Explicit categories retain their original selectors. Without
`--resume`, a new run starts from its first category with empty repair, queue,
pending close-out and pipeline status state. Both paths use fresh case
budgets without loading old repair conversations; new verification rounds still
execute the complete requested selection. After a repair within verification,
the next clean pass clears previous category completions before queuing work;
an interruption can resume only that pass's completions.
Fresh startup preserves source edits as existing checkout work, but does not
inherit unfinished repairs or their Git ownership bookkeeping. Only `--resume`
recovers pending repairs and accepted Git close-out before tests. An active run
still reattaches regardless of `--resume`; a fresh allocation starts only after
its owner and owned cleanup release their locks. Lock files remain in place;
kernel locks, rather than file existence, determine ownership.

Use `tools/fix-tests --resume` without repeating the original arguments to
restore the saved selection and VM queue. Its startup line lists retained passed
categories. A session-limit or stalled handoff does not erase those category
passes, including a completed diagnostic test run; resuming does not reinterpret
an old agent conversation. Failed/interrupted cases still need their matching
runner checkpoint. Additional verification rounds deliberately run their fresh
required selection; do not add `--rounds` just to continue a stopped round.

An answered blocker keeps its current model/phase and is not a failed repair.
Ownership recovery remains the existing scripted `cleanup-e2e` operation; a
normal cleanup failure handoff enters the same repair policy, while refusal
without a handoff still stops. No model performs routine ownership recovery.

`--model` and `--effort` override the initial agent for a new run. Explicit
stronger effort choices are never downgraded: Sol xHigh moves to Sol Max for
non-unit failures and remains xHigh for unit failures. An explicit Sol Max
override remains there for either category. Omitting `--effort` selects each
failure category's initial tier; an explicit effort applies to both ladders.
Every tier uses `gpt-6.1-sol`; other models,
including other Sol versions, are refused with no silent fallback.
The selected pair, automatic escalation tiers and any override-specific reachable
pairs must be listed in the existing CLI catalog before testing begins.
All agent sessions pin **Standard speed**,
including answered blockers and repair retries, overriding personal Fast defaults.
Prompts require scoped reading and concise evidence handoffs without reducing
understanding, tests, cleanup or behavior-confirmation requirements.
Each agent uses
`codex exec` with a fresh persistent thread, disabled history-list recording and
memories, and receives
the latest failure handoff. The script never resumes or forks a session; the app
review receives the latest failure handoff, classification or repair summary and applicable
developer answers. An answered blocker also supplies its latest repair handoff.
The [official noninteractive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
defines the invocation. The shared [goal setup](../docs/Execution-Plans.md#execution-and-delegation)
requires persistence and activates the actual goal before task work.
Existing CLI authentication, configuration,
workspace sandbox and command rules remain in effect; agents cannot request
interactive approvals. Install/authenticate Codex separately before starting.
Agent output uses `exec --json` events rendered with the setup-provided Rich
library: compact bulleted Markdown messages, `Ran` commands and `Explored`
read/search entries, plans, tool activity and file-change summaries. Consecutive
reads and searches share one heading and display filenames. Commands
use blue executable names and green quoted arguments; output and connectors are
gray, with red failure statuses. Short output previews appear beneath commands,
limited to three display lines with an omitted-line count. Successful exploration
bodies and zero exit statuses are hidden. Interleaved results repeat their
command context. Full output is retained in
`agent-commands.log` inside the same run, using the transcript's size limit.
Reasoning events are hidden; user-facing agent updates and
final results remain visible. Diffs use syntax colors, hunk line numbers and
pale red/green backgrounds for removals/additions
when supplied by the event; file-change events containing only paths show those
paths without inventing a diff. The detached supervisor renders an append-only,
100-column transcript with ANSI styling retained on reattachment. Terminal
observers wrap its text to their current width with hanging indentation preserved.
CLI diagnostics
remain separate from event parsing, and unknown events remain visible. There is
no interactive agent approval prompt; developer decisions use the launcher's
shared question menu described below. The result file still controls repair
verification. Development activation is `none`; new launcher processes
use the checkout code without product installation or a service restart.

When a useful experiment requires instrumentation before a corrective edit is
justified, return the structured status **`diagnostic_ready`**. Its summary must
identify the hypothesis, bounded instrumentation changes, expected observations,
evidence location and interpretation. Instrumentation must preserve behavior,
privacy, assertions and validation guards. This outcome claims no repair.
The launcher owns exactly one rerun of the original authorized selectors per
diagnostic outcome; agents cannot supply commands, run tests or nested launchers.
It retains a bounded output snapshot and runner handoff in private
`diagnostic-*.json` files, then supplies the observations to a fresh session at
the same tier and under the same case/VM budget, even when the category passed.
An intervening failure in another case or preparation is handled separately;
the original diagnostic handoff remains pending until its case returns or the
category passes. The fifth session's diagnostic run still finishes, but further
interpretation requires stopping at the budget boundary. `stalled` means no
useful authorized next step exists, rather than an experiment awaiting execution.

Closing the terminal detaches; rerun `tools/fix-tests --vm NAME` to attach to the current
output, with a bounded tail of earlier output. `tools/fix-tests --vm NAME --stop` and
Ctrl+C request the same immediate cancellation. Tests receive the runner's
Ctrl+C path and finish guarded cleanup before exit. Agents receive termination,
with a three-second limit before their recorded process group is killed. If the
loop owner dies, its supervisor detects EOF and cancels the current operation.
Completed or dead owners never block a fresh run: file locks determine liveness,
old cancel markers are isolated by run, and normal `run-tests` startup performs
its existing retention/VM recovery. An attached predecessor's result is consumed
before starting the requested category; it never counts as that category passing.
On stale ownership, `fix-tests` invokes `tools/cleanup-e2e --host-only` when no
VM is selected, or the selected VM/queue recovery route otherwise, before
retrying the category. Host recovery requires no VM configuration or privilege.
Recovery still fails closed when no actionable handoff is available.

Logs and small control files are private under `output/test-runs/host/fix-tests/`. They are
not agent conversation history. Existing test evidence remains under the runner's
retention policy. The terminal prints the report and `Failure handoff:` paths
with a short instruction to read and follow the handoff's `prompt` field;
the full investigation prompt is saved in machine-readable `failure.json` with
stable retry category and case IDs. `fix-tests` reads that saved prompt directly,
so terminal output omits the long manual-session prompt. For a manual handoff,
ask the new session to read the indicated `failure.json` and follow its `prompt`.
A missing or malformed handoff, agent
crash or unmapped infrastructure failure stops with evidence.

`agent-usage.jsonl` records CLI turn counters with session/repair IDs, attempt,
case identity, per-case session number, round, phase, selected model/effort and
Standard speed. `tier_transition` events record old/new model and effort and
the escalation reason. Session exit, structured result, session-limit and category
verification events link classification, blockers and retries to the repair chain.
Missing counters are unknown, including a session with no
reported usage; they are never zero-filled. An interrupted verification has no
success event. `diagnostic_execution` records observations separately from repair
verification. A different failing case or preparation failure is not a failed
verification of the repaired case: `passed` is null and `outcome` is
`unknown_or_not_executed` until evidence resolves it. A later same-case failure
or category pass records that resolution under the original identity.
A category pass is local verification, not proof that later
aggregate verification will pass. Records are observational, never resume state;
recording failure warns without interrupting repair or cleanup.

OpenAI's [model guidance](https://learn.chatgpt.com/docs/models#gpt-61-sol)
recommends GPT-6.1 Sol for complex coding at lower cost than Astra. Luna is
suited to focused repeatable tasks, but this classifier can edit tests and must
distinguish mechanical defects from product regressions; lowering it further
needs quality evidence. [Standard speed](https://learn.chatgpt.com/docs/agent-configuration/speed)
avoids Fast's 2.5x included-usage multiplier when Fast would otherwise apply.
[Included usage](https://learn.chatgpt.com/docs/pricing) depends on the workload;
API prices and purchased-credit rates do not establish Pro weekly savings.
Compare total counters per verified repair chain (including failures and blocked
sessions), first-pass success and review findings with the account's weekly
dashboard. Host regressions establish routing and safety contracts, not equal
model success rates or a measured allowance improvement. No paid-model benchmark
is part of launcher validation.

An agent-reported blocker pauses the loop for developer instructions using the
same [question implementation](../tools/launcher_question.py) as `write-e2e`.
The menu offers two or three suggestions, selects the first recommendation by
default, and includes editable Other input. Enter submits the selection; neither
elapsed time nor disconnection submits an answer. Reattach with `tools/fix-tests --vm NAME`
to answer. No tests or repairs start while waiting. After an answer, a fresh
session receives the failure evidence, latest repair handoff and developer
instructions, rechecks prerequisites, and continues the same repair phase.
Decisions remain available to later repairs in the run within their stated scope.
Ctrl+C or `--stop` cancels a paused run without answering.

The [failure mandate](#handling-test-failures) still applies: classify from evidence,
report expected versus actual behavior and ask before accepting changed behavior
or altering expectations unless that exact change is already authorized. The
loop does not weaken checks or bypass permissions to continue.

The process lifecycle is qualified using isolated test/agent doubles in
`test_fix_tests_cleanup_safety.py`; these tests never invoke the model or VM.

### Scripted E2E implementation

Run [tools/write-e2e](../tools/write-e2e) to implement the execution plan's first
unchecked active task through fresh unattended Codex sessions:

```sh
tools/write-e2e --vm NAME --tasks 1
tools/write-e2e --vm NAME --tasks 2
tools/write-e2e --vm NAME
tools/write-e2e --vm NAME --stop
```

`--tasks N` limits completed tasks and defaults to `1`. There is no total
session limit. Each task can use at most 5 sessions per new launcher process.
A restarted launcher retains the task's cumulative
session count and adds 5 to it for that process's task cap. Attaching to a
running launcher does not renew the cap. If the task is still incomplete at
that cap, the entire launcher exits with failure and prints a bold
red warning as the final line of its worker summary, after the follow-up
instructions and before the shared observer's final tasks overview recap.
The next task starts with its own cap of 5.
Zero and negative task limits run all remaining tasks. An oversized positive
limit warns and finishes when the queue is exhausted. A task counts only after
acceptance, queue close-out, successful staging, its completion commit and
`git push`. An empty active queue stops the workflow. A task blocker pauses for
your answer as described below.
With a live run, an invocation without parameters attaches without changing the
task limit. Explicit `--tasks`
values replace the existing maximum: `--tasks 2` sets it to 2; `--tasks -1`
or `--tasks 0` removes the task limit. An omitted limit stays unchanged.
Replacements are serialized across terminals. They take effect
before the next session; the current session
finishes normally and completed work is preserved. Invalid options are rejected.
An owner already finishing at its limit refuses adjustments; restart after it exits.
Workers started before adjustable-limit support require a restart to accept changes.
Closing the terminal detaches. Another invocation attaches to its styled output,
using the same compact session transcript as `fix-tests`: agent messages,
commands and their results remain visually separate, including without color.
`--stop` finishes the current session, including test cleanup and its handoff or
task close-out, then starts no further session. In the interactive chat composer,
Cancel, Escape or Ctrl+C interrupts the active turn and waits for owned cleanup, leaving
the same session open for further instructions. Escape preserves the session when
already waiting. Ctrl+C again while waiting for
input cancels the entire launcher. Piped observers retain signal cancellation.

After each completed task, the launcher stages its owned paths and commits them
as `TA: Completed task ID`, then runs `git push` and completes
[shared worktree propagation](../docs/Execution-Plans.md#shared-worktree-propagation)
before selecting another task. Optimization commits use the same propagation.
The push uses the checkout's existing Git remote and branch configuration.
Git uses literal paths
and `commit --only` so unrelated staged files remain outside the commit. Agents
return explicit owned paths and never commit themselves. A path overlapping
pre-existing staged work refuses close-out rather than committing that work.
A staging, commit or push
failure retains the accepted result; restart retries close-out without repeating
valid acceptance. Commit intent is checkpointed before Git writes. Recovery
recognizes the matching immediate commit with unchanged owned files and saves
its identity. A saved completion or propagation identity also permits recovery
from a descendant HEAD after verifying the original committed tree against the
intent; later edits remain untouched. Unrecorded HEAD changes or mismatched
completion contents refuse, avoiding duplicate or unrelated completion credit.
Push recovery retries the push after recognizing the existing commit.
E2E results report the current task's host/live outcomes and may include scoped
`checks` containing kind, target and result. Passing live results cover the selected
targets. Saved results may contain an ignored legacy `evidence` string; new
responses need no evidence field. Continuations and Git
retries use the saved outcome without reopening referenced files, authenticating
archival declarations or collecting turn capsules. A completed task stays done.
Missing Git identity, remote/upstream configuration or a failing Git hook remains
an actionable close-out failure; the launcher does not change Git configuration
or bypass hooks.

Every **three accepted and committed tasks**, a fresh **GPT-6.1 Sol High** session
runs before another queue task. Its scope is the batch's exact three completed
queue IDs, displayed as the actual first-to-last ID range (IDs may have suffixes
or inserted prerequisites). This required session optimizes the current code;
it does not collect proof, inspect old reports or repeat completed tasks' checks.
Refactoring changes receive only their affected validation; unchanged code needs
no new test run. It analyzes lessons from successful work
and merges useful guidance into the owning instructions/mandates without
duplicates. It also audits the batch's delivered or affected ready E2E cases:
cases compose shared building blocks, harness and libraries with finite case
data, ordering and assertions; one-off mechanics move to their reusable owners.
It also cleans up code delivered or affected by each task that became messy
across progressive sessions of that same task, including redundant or obsolete
code, temporary workarounds and inconsistent structure left by successive attempts.
It preserves behavior, qualifications and guards, completes affected validation
and resource review, then the launcher stages the fix and commits it as
`TA: Refactored task FIRST to LAST`, then runs `git push` through the same
resumable close-out. A verified audit with no needed edits still
gets an empty checkpoint commit. Optimization cannot close or reorder queue rows.

The existing retained checkpoint owns pending batch IDs, the last optimized batch
and commit, and any active optimization handoff/commit intent. It survives
separate launcher runs, prerequisite suspension, stops and interruptions.
Tasks predating this policy are not retroactively counted. Optimization uses
its own five-session cap, renewed on restart; it does not
count against `--tasks`. A due optimization runs even after the task limit, while
stop and cancellation can defer it. Restart performs the due work
before another task, including when the active queue is empty. No parallel or
ordinary adviser agents run during optimization; the shared mandatory backend
review remains required for core backend changes. A blocked optimization uses the same
developer question and answer recovery as task work.

New tasks start with **GPT-6.1 Sol High** as coordinator and implementer. The
launcher promotes the implementer automatically within the existing five-session
task cap:

| Evidence at the session boundary | Next coordinator and implementer |
| --- | --- |
| First unsuccessful substantive live attempt | Sol High gets one repair session |
| Two unsuccessful substantive live attempts | GPT-6.1 Sol Extra High (`xhigh`), normally session 3 |
| A correction fails at the same checkpoint without meaningful progress, or reasoning stalls | GPT-6.1 Sol High → GPT-6.1 Sol Extra High → GPT-6.1 Sol Max |
| Further failures with verified progress or new diagnostic evidence | Keep the selected tier; the two-attempt promotion still applies |

Every tier uses `gpt-6.1-sol`, with `high`, `xhigh`, then `max` reasoning effort.
Astra is reserved for the shared mandatory independent review of core backend
changes; implementation and ordinary consultations retain their Sol policy.
Promotion survives launcher restarts,
answered blockers and prerequisite suspension; a new task resets to Sol High.
A GPT-6.1 Sol Max reasoning stall stops the launcher early with retained
evidence. Other incomplete outcomes retain the ordinary session cap. Promotion
never renews that cap or bypasses acceptance, staging, ownership or cleanup.

Structured results carry `progress`: a stable `failure_checkpoint` scoped to its
qualification/regression, the `furthest_checkpoint` independently verified, and
`repair_outcome` (`advanced`, `diagnostic`, `failed_repair`, `stalled` or
`not_applicable`). Handoffs retain the supporting evidence, attempted correction
and expected/actual result. Generic SSH/worker errors, timestamps and report paths
are not checkpoint identities. `failed_repair` must match both previous checkpoint
fields; advancing a verified milestone keeps the current tier. Classify from
already collected evidence without diagnosing or retrying a new live failure;
use `diagnostic` when uncertain. Diagnostic-only live failures still count toward
the two-attempt promotion. Semantic classification remains the agent's
responsibility; the launcher validates field consistency and enforces promotion.
Legacy unfinished checkpoints use their retained live-attempt count to select
Sol High or Sol Extra High; missing repair evidence never implies Max.

Only normal failed live handoffs and reasoning stalls with an actual failed live
result increment the new unsuccessful-attempt counter. Blockers, interruptions,
preparation and raw session counts do not promote. Missing authority, external
prerequisites and customer behavior decisions still use the maintained blocker
route. A reasoning stall with no useful authorized next step may return `stalled`
before live execution, with the actual validation outcome and owned cleanup;
it promotes without inventing a live attempt or asking the user an unnecessary
question. Normal handoffs retain the host/live validation boundary below.

While Sol High is coordinating, use one bounded **GPT-6.1 Sol Max** consultation through the
[read-only adviser](../tools/write_e2e_adviser.toml) when a High repair failed
verification without improving the explanation, conflicting evidence prevents
a defensible correction, or a consequential security, concurrency or ownership
design question remains unresolved. State the concrete escalation reason and
what High already established. Ordinary diagnosis, missing prerequisites,
permissions and preparation failures use their maintained repair/blocker routes.
After promotion, the selected Sol 6.1 tier owns implementation and validation
directly, with ordinary delegation disabled; the mandatory backend review remains
available at every tier. Do not add an ordinary adviser or hand the repair
back to Sol High. The adviser configuration pins `gpt-6.1-sol` at `max` effort.
This policy overrides model recommendations in older saved handoffs.
Consult before implementing such an unresolved risky design, including in the
initial session without first spending a failed attempt. All coordinators and
advisers pin Standard speed, so personal Fast settings cannot silently increase
subscription usage. Keep source reads and
diagnostic output scoped, reuse unchanged context and carry concise handoffs;
never reduce required understanding, assertions, acceptance or cleanup.

Consultations are sequential: the coordinator gives one exact question, relevant
source/evidence paths, attempted corrections, applicable contracts and user
decisions in a fresh context,
waits for the answer, then closes the adviser before resuming work or consulting
again. Codex V1 is configured with one concurrent child slot and one level of
delegation. The adviser cannot delegate further and is configured read-only; its
instructions prohibit edits, tests/builds, VM control and task completion. It
returns concise findings, evidence, a proposed correction, uncertainty and required
regressions. The coordinator checks the advice and owns all implementation,
validation, cleanup and queue updates. Advice provides no acceptance credit.
Consult once per unresolved question; repetition requires materially new evidence
or a distinct question. Carry the question, findings, attempted correction and
remaining uncertainty in the handoff across sessions and restarts. Cosmetic
rewording or another failed run is not new evidence. These consultation rules
are agent instructions; the launcher enforces the coordinator session cap and
concurrency/depth bounds, not semantic novelty or an adviser token ceiling.
Consultations are part of the coordinator session, not extra task sessions;
they still consume model usage. Do not introduce parallel agents or overlapping
coordinator work. While Sol High coordinates, the same single slot also supports
bounded GPT-6.1 Sol Low `plan_monitor` observations or Sol Medium `plan_worker`
coverage refreshes under the [common delegation contract](../docs/Execution-Plans.md#execution-and-delegation).
These roles never implement repairs, operate VMs, run acceptance or close tasks;
coverage writes are limited to explicitly assigned generated assets. The
coordinator verifies their output. Higher coordinator tiers retain their existing
direct-work policy. `fix-tests` keeps ordinary delegation disabled. Both retain
the shared mandatory backend review, without changing their model ladders.
Start a new launcher run to adopt this policy; attaching to an existing run
does not reconfigure its already-running coordinator.

Each run retains `agent-usage.jsonl` beside its existing output, with one record
per reported CLI turn: cumulative launcher session number, task, phase, selected
model/effort/speed and available input, cached-input, output and reasoning-output
counts. Missing counters remain unknown, not zero. These are CLI-reported turn
counters; adviser inclusion is not established, so do not treat them as complete
account usage or add reasoning counters to output without checking their semantics.
Recording failure warns without interrupting validation or cleanup. Compare
usage per accepted task (including retries and consultations) and the account's
weekly dashboard, together with first-pass acceptance and review findings.
Host regressions validate routing and preservation of acceptance gates; they do
not establish equal model success rates or a measured allowance improvement.
OpenAI's [model guidance](https://learn.chatgpt.com/docs/models#gpt-61-sol)
recommends 6.1 Sol for complex coding at near-Astra capability. Its
[pricing documentation](https://learn.chatgpt.com/docs/pricing#token-rates)
separates credit rates from included subscription usage, and
[Standard speed](https://learn.chatgpt.com/docs/agent-configuration/speed)
avoids Fast mode's 2.5x included-usage multiplier. No fixed weekly savings are
inferred from API prices or the counters.

The first session implements, host-validates and runs the first live VM test.
Success completes acceptance and close-out in that session; failure preserves
evidence and hands off after cleanup, leaving review and repairs to the next
session. Every subsequent session, including recovery after an interruption
or answered blocker, investigates the previous VM failure when present, reviews
unstaged code and retained evidence, and repairs authorized defects before host
validation and live VM acceptance in that same session. Recovery first rechecks
the interrupted operation or blocked prerequisite and owned cleanup. Every live
failure ends the session after evidence preservation and cleanup; investigation
and repairs of that new failure belong to the next session. A normal handoff
requires passing host checks and a completed failed VM attempt, including in
recovery. The diagnostic continuation below permits further useful live
investigation of a retained failure without another acceptance attempt.
A preparation failure before VM access does not count as a failed live
attempt: repair authorized mechanical defects or prepare missing generated inputs
through the maintained artifact builder and resume validation in the same session.
Do not ask the developer to choose between building and restoring qualification
inputs. Integration qualification wrappers declare their input profile with
literal `named_input()` options. `tools/test_commands.py` reads that declaration
without importing the wrapper; no separate selector/preparation lists are
maintained. All profiles bind automatically to the selected VM, including
callers omitting `vm_source`. The shared `tools/vm_artifacts.py` route selects
an explicit `deb` or `rpm` builder from pinned baseline provenance before
dispatch, and rechecks cached bundles against that format. A wrong cached
format refuses without replacing evidence or entering the journey. Genuine
upgrade pairs pin v1.2 for DEB and v1.3 for RPM through that same infrastructure.
`system --upgrade-inputs` prepares the selected VM's pair before the existing
explicit current/previous package route, including independent parallel workers.
The low-level builder API and CLI require a package format;
no DEB fallback is permitted. Host Debian reproducibility/cache routes supply
`deb` explicitly. Launcher coverage discovers consumers independently and
checks a new unlisted wrapper against both verified platform results.
Current-package authentication regressions use `named_input(package_source=True)`
in both selector and launcher preparation. A fixed legacy input can select an
older version snapshot even after current app preparation succeeds. Preserve
existing immutable bundles; prepare the new source-specific input rather than
replacing the old bundle or relaxing snapshot validity.
Only a prerequisite requiring external action or an unresolved behavior decision
returns a blocker with the actual validation outcome. A passing session completes
the plan's acceptance, checks the row and advances its sole pointer. It returns an explicit
list of task-related code, test and
close-out files; the launcher stages, commits and pushes those files before
starting another session. This staging uses literal Git paths and needs no
agent-side Git permission grant. Task 192 retains the plan's explicit host-only exception.
Staged code is the baseline; agents do not analyze staged diffs.

#### Live diagnosis before another repair attempt

After an initial scoped live attempt, start repair with bounded source and
retained-error review. Use a directly established mechanical cause to make a
focused correction. When that review leaves competing explanations, the failure
depends on transient session/process state, or a correction fails again at the
same checkpoint without explaining why, move to live reproduction and probing
before another speculative patch or full acceptance run. Do not wait for a fixed
number of failures or require maintenance for every straightforward defect.
Explain the unresolved question and the observation that would distinguish its
possible causes. A timeout or generic transport error alone does not identify one.

The repair session's sequence is evidence review → live reproduction/probes when
needed → focused live fix experiment → maintained correction and host checks →
clean acceptance. Failed formal acceptance still ends the session after evidence
and owned cleanup; the next session investigates it. Diagnostic experiments on
the previous failure happen before that session's formal acceptance attempt.
They do not erase the original failure, supply acceptance credit, renew session
limits or alter the launcher's unsuccessful-attempt/promotion accounting.

If bounded live investigation remains unresolved but has useful next work,
return structured status `investigating` after owned maintenance cleanup, with
`live_result: not_run`, actual `host_validated`, empty `stage_paths`, no blocker,
and progress outcome `diagnostic` with an empty `failure_checkpoint`. Report
actual new observations and an exact next live experiment in the handoff. This
is a continuation of a prior failed acceptance attempt, not an alternative to
the first attempt or a way to skip validation after a supported correction.
The launcher refuses it without a prior failed acceptance or if it claims a new
live pass/failure, staging or queue advancement. It retains the formal failure's
progress separately from diagnostic progress, preserving subsequent
same-checkpoint failed-repair promotion. Each continuation consumes the existing
session budget, but increments neither live/unsuccessful-attempt counts nor the
model tier. Success still requires all host and clean live acceptance checks.
This route also applies to optimization repair after its own failed validation.
Formal live outcomes are retained independently of promotion counters. A failed
attempt reported with a blocker permits diagnostic continuation after the blocker
is resolved, without counting the blocker as a failed repair. Blockers, stalls and
diagnostic rounds without a new live attempt preserve the last formal outcome and
its checkpoint evidence. An outstanding optimization live failure requires a
subsequent clean live pass; host-only completion cannot clear it.

Engineering investigation and customer E2E acceptance are separate activities.
During investigation, use whatever guest-side inspection, debugger, temporary
instrumentation, direct internal API calls or controlled state changes are needed
to establish the cause and validate a correction. Root access is one available
tool, not the required investigation context: reproduce and probe under the
actual account, privileges, environment and session where the failure occurs,
including a non-admin child's graphical session and session bus. Switch identities
or instrument that context as needed; success from a root shell cannot establish
the result in the affected child session. E2E restrictions to public actions and
results do not restrict these engineering experiments. Use the owned disposable
VM and maintained transport/observation routes, record the experimental changes,
then validate the maintained fix with clean customer acceptance.

1. Let any test runner finish collection and owned cleanup. Do not suspend its
   process, intercept teardown, borrow its lease or adopt a foreign running VM.
   Start an owned online maintenance instance through
   `tools/prepare-appsnapshot --vm NAME --y --overwrite false`,
   under the [live preparation contract](../docs/TestAutomation/E2E-Execution-Contracts.md#live-verification-contract).
   A matching instance already owned by this workflow can be reused through its
   maintained ownership checks. Use the selected registered target, valid package
   input and required baseline; a missing prerequisite follows its repair/blocker
   route. This creates a separate reproduction after the failed attempt's cleanup;
   it does not retain the failed runner's state.
2. Recreate the smallest history that actually exhibits the original symptom,
   using the existing shared journey/helpers and the same relevant accounts,
   policy, session transitions and timing. Stop progression at the suspect
   boundary and keep this maintenance guest running while investigating. Do not
   invoke another full test whose cleanup would remove that reproduction. If a
   shared operation lacks a diagnostic entry point, add the smallest maintained
   route in its owner rather than duplicate case mechanics or bypass guards.
   An unreproduced symptom is an unresolved hypothesis, not a validated fix.
3. Use `tools/test-vm --vm NAME exec [--timeout SECONDS] -- COMMAND [ARG ...]`
   for direct guest investigation under the [VM mandate](../docs/Mandates/VM-Mandate.MD#owned-maintenance-and-execution).
   Its `--input-file 'PATH'` option passes a bounded caller-owned regular file to
   guest stdin when a diagnostic script/input is needed; it is not a host shell
   or arbitrary privileged host-file reader. Shared watch, intention, guarded
   transport and VM identity checks remain active between commands. Probe actual
   process/session ownership, service and bus state, API responses or event order
   as the question requires, instead of inferring them only from postmortem logs.
   Keep output bounded and free of secrets/PII. Internal instrumentation belongs
   to engineering diagnosis. Guest experiments may inspect and manipulate internal
   product state; actual secret entry still requires a verified recipient and
   must respect uncertain-input guards.
4. State a hypothesis and its predicted observation before each experiment.
   Capture the unmodified symptom and relevant live state, change one causal
   factor where practical, then independently observe the same operation/result.
   Change guest runtime state and add temporary diagnostic instrumentation as
   needed; prefer reversible changes when practical. Record exactly what changed
   and whether the prediction held. Product
   installation, reinstallation and upgrade still use `make install`; do not
   turn guest tinkering into an alternate deployment or prerequisite-preparation
   route. Do not modify reusable snapshots or weaken assertions/ownership/input
   guards. If a transition destroys the reproduction, deliberately recreate its
   history before the next comparison. A successful command, a vanished symptom
   without a reproduced baseline, or an extra sleep alone is not causal evidence.
5. If still unresolved, continue live probing and live fix validation in further
   rounds. Choose the next discriminating observation from what the previous
   experiment established; retain and retire disproven hypotheses. One
   inconclusive probe does not send the workflow back to log-only guessing.
   Repeated experiments need a new hypothesis, changed probe or materially new
   evidence. Bound each command and investigation to the existing task/session
   limits; do not create an unbounded retry loop or claim a reasoning stall while
   a useful authorized experiment remains. A handoff carries the symptom,
   reproduction inputs/commands, established observations, rejected explanations,
   temporary changes and before/after results, evidence locations, cleanup and
   exact next live probe. End the session with owned maintenance cleanup; the
   following coordinator recreates the reproduction under its own ownership
   and continues the live investigation instead of inheriting a guest or
   restarting already disproven theories. If safe reproduction is unavailable,
   record why, the remaining uncertainty and the best supported next observation;
   do not manufacture a cause or ask for approval already provided.
6. Move a causally supported correction into maintained source/shared helpers and
   add the lowest effective regression when needed. Remove temporary
   instrumentation, finish affected host checks and run
   `tools/test-vm --vm NAME stop` to complete maintenance cleanup before formal
   acceptance through `tools/run-tests` with the original required selectors and
   assertions. Acceptance uses fresh declared state and the maintained package,
   not experimental guest mutations. Keep expected versus actual behavior and
   unresolved product decisions under [failure handling](#handling-test-failures).

Close-out ignores reported paths that are absent from both the working tree and
the Git index, such as temporary briefs created and deleted within the task.
Tracked deletions still stage normally. If Git close-out fails after acceptance, the
launcher retains the accepted result and current handoff. Restart revalidates
that result against the saved queue state and retries only its staging/commit/push before
selecting the next task; it does not repeat the completed live acceptance or
rewrite the previous run's evidence. Recovery preserves newly queued unchecked
tasks; changes to existing task order or another task's status still refuse.

If a session discovers a missing capability, the plan permits inserting an
unchecked prerequisite immediately before its unfinished consumer. The launcher
validates that insertion, preserves the consumer's handoff, staging ownership
and session counts, and starts the prerequisite in a fresh session. This earns
no completion or live-acceptance credit. Existing task order/status must remain
unchanged, and the inserted rows must be explicit dependencies with briefs.
After the prerequisites pass, the consumer resumes in a recovery session.
Restart also recognizes this dependency relationship in an older interrupted
checkpoint, preserving its evidence and requiring cleanup verification first;
unrelated queue changes still refuse. No checkpoint deletion or manual editing
is needed.

An authorized scope exclusion is recorded as `Excluded tasks: **ID, ID**` in
the canonical queue. On restart, an interrupted excluded prerequisite can
return to its saved suspended consumer only when every removed row is explicitly
excluded and unchecked, all remaining rows retain their order/status, and the
consumer is the first unchecked task. Pending completion and optimization are
never bypassed. The launcher preserves session/model history, staging ownership
and retained evidence, and requires cleanup verification in recovery. Exclusion
earns no acceptance credit; current briefs supersede excluded-task handoffs.

Each session is a new Codex `app-server` process with a fresh persistent thread,
history-list recording and memories disabled. The shared
[goal setup](../docs/Execution-Plans.md#execution-and-delegation) activates the
actual goal before task work. Follow-up chat and interrupted-turn continuation
use that same thread and consume no new launcher session. Only the latest
standalone handoff crosses sessions. Existing CLI
authentication, sandbox and command grants apply; missing grants or unresolved
behavior decisions pause with a blocker. No live Codex or VM work is performed
by the launcher's regression tests.

When a task is blocked, both launchers ask in everyday language: what prevents
progress, how it affects the work, why the agent cannot resolve it, and what
specific decision or action the user needs to take. Questions and choices must
also make sense without Linux or test-system knowledge. Technical commands,
paths and error codes belong in the saved handoff. Each choice says who does
what and what happens next; two versions of the same repair are not distinct
choices. Access failures require checking the exact command against its grant
before blaming host permissions or asking for administrator help.
The launcher asks one concrete question with two or three suggestions, the recommended
action first, and a gray **Other** placeholder for your instructions. Choose a
number or use Up/Down, then press Enter to submit. Selecting Other lets you type
your own instructions; Backspace edits and Ctrl+U clears them. Page Up/Page Down
still scroll the explanation. Blank input never chooses an answer, and pasting
multiple lines does not submit automatically.

The workflow waits indefinitely without starting another model session or
consuming session allowance. An unchanged prompt performs no repeated layout or
terminal writes; keyboard input and terminal resizing remain responsive.
Closing the terminal leaves it paused; rerun
`tools/write-e2e` in an interactive terminal to answer. Piped output remains an
observer and never invents an answer. With multiple attached terminals, the first
submitted answer wins. Your answer continues the same task through a fresh
recovery session at its retained model tier, with the saved handoff and your instructions. It does not
count as passing the blocked prerequisite. If a session limit was exhausted at
the blocker, answering grants one recovery session beyond that limit; automatic
work remains subject to the limits afterward. `--stop` saves the pending question
and exits cleanly; Ctrl+C retains its cancellation behavior. Restarting a paused
task asks for its answer before doing more work.

The shared [session renderer](../tools/launcher_render.py) applies these display
rules to every supervised agent; launchers do not format agent events themselves.
All launchers use the same output-following loop and
[three-pane task display](../tools/launcher_display.py), customized with
[presentation strategies](../tools/launcher_view.py). The upper pane pins the controller journey: `run-tests` shows the selected
category and position with overall progress; `fix-tests` adds the current round number and
the running-tests/fixing-errors status.
Each `fix-tests` VM heading includes a bold, colored status: gray for
`Queued on VM slot` or `Queued on <VM> repair`, blue for `Running`, orange for
`Repairing`, `Verifying` or `Save fix`, green for `Complete`, and red for
`Waiting for input`, `Task limit reached`, `Stopping`, `Stopped` or `Blocked`.
The repair wait names the transaction owner through verification and Git
close-out; cases already executing retain their active status until they wait.
The lower frame divides execution details and optional session input on the left
from current task summary and status/issues on the right. `run-tests` has no
session composer; `fix-tests` offers input for developer decisions. E2E and
ordinary plan workflows offer the conversation composer described below.
The upper and lower frames share an initial width ratio of 75:25; dragging either
vertical divider resizes both frames together and keeps their dividers aligned.
The shared ratio survives terminal resizing. Both dividers turn blue while dragging
and return to their normal color on release. Hover requests the standard horizontal
resize pointer over dividers and an I-beam over the conversation composer's text
area using OSC 22; terminals without pointer-shape support keep their
own pointer, including VS Code's integrated terminal (xterm.js does not implement
OSC 22). The live layout owns an alternate screen, keeping the shell prompt and
shell scrollback outside the launcher. Mouse controls start enabled: wheels
scroll the pane under the pointer, and the output pane has its own draggable
scrollbar. The terminal's scrollbar does not control the panes. Scrolling output
keeps the overview, totals, task summary and composer fixed. F2 releases mouse
reporting for ordinary native selection, Ctrl+Shift+C and the terminal's configured
right-click menu; F2 again restores pane controls. While mouse controls are
enabled, use the terminal's native selection modifier to select text. Unmodified
native selection and application mouse controls cannot be offered simultaneously
through this terminal protocol. Non-chat displays also accept m when no blocker
question is pending; F2 remains available during questions.
The bottom-right panel shows the current task ID/title, session count/duration,
session phase and selected model/effort. Below a horizontal separator, the
plain-language task explanation stays fixed across retries and reconnects unless
the task scope changes. The agent writes it once rather than repeating it in
progress output. The shared [panel contract](../docs/Execution-Plans.md#common-launcher-interface)
owns the bold explanation/error/status labels, separators, task-local error age
and colored status values. These updates are presentation only, never
acceptance evidence.

`fix-tests` populates those same fields during testing and repair: both a reported
Last Error and Status show `(duration ago)`, refreshing without new output and
surviving observer reconnection. Each round/category keeps its own metadata;
repair retries retain the error clock, and corrective verification changes status
before testing and after a passing selected run.

The bottom-left composer accepts typing during work. Enter sends; Shift+Enter
inserts a newline in terminals supporting modified-key reporting, which the
display enables while attached. Alt+Enter and Ctrl+J also insert a newline;
multiline paste never sends
automatically. Arrow keys, Home/End, Backspace/Delete and Ctrl+U/Ctrl+K edit
the draft. Its height follows the content, scrolling around the caret when
space is limited. Messages steer an active turn or start a continuation in the
same session after interruption. Replies appear in the left transcript. The
composer owns Cancel/Escape/Ctrl+C; the output pane has no termination shortcut.
Pending blocker questions appear above the composer: send a suggested number
or type your own instructions. Multiple observers share the existing first-answer
rule. Mouse wheels scroll the panel under the pointer by default.
The top-left overview follows the shared
[five-row scrolling contract](../docs/Execution-Plans.md#common-launcher-interface)
and omits the run's `Tasks:` count. The top-right plan totals remain visible.
Category and session transitions update immediately. Routine overall counts refresh at most
once every five seconds, while detailed test progress and agent output continue
in the lower pane. Child output cannot move the cursor into the upper pane.

Overview text wraps to the observer's current width and scrolls within the
five-row limit, starting at the newest rows. Pipes and dumb
terminals accumulate plain output. Reconnection restores the latest controller
steps separately from the output tail. The live panes retain a bounded transcript;
dashboard redraws and arriving output never enter the shell's scrollback while
attached. On exit the launcher restores the primary screen, cursor and input
modes, then replays the saved run log, including an unfinished final line, into
native scrollback. This includes cancellation, exceptions and
default termination signals (HUP, TERM and QUIT); SIGKILL cannot run terminal
cleanup. Existing shell history is preserved. Full output remains in the existing run log,
subject to its storage limits. The full top-left overview and exit timing are
appended under the shared [exit recap contract](../docs/Execution-Plans.md#common-launcher-interface),
including summaries outside the visible pane; pipes receive the same plain-text
recap. `run-tests` preserves its detailed dashboards when observed
through a workflow launcher, below that workflow's controller summary.
For `run-tests` and `fix-tests`, mouse capture starts enabled, as in the chat displays.
The divider shows `F2/m: select text`; press `F2` (or `m` outside a pending question)
to release mouse controls for ordinary native selection and context menus.
The divider changes to `F2/m: scroll/resize`.
A pinned **↓** button at the lower pane's
bottom-right corner returns to the newest output and resumes following it.
The button stays outside the scrolling transcript and follows terminal resizing.
The scrollbar and button hide while the terminal owns selection. Press `F2` or `m`
again to restore pane controls. Use Up/Down or Page Up/Page Down to scroll a pane,
Tab to switch panes (initially the lower pane), and End to return to the newest
rows in either mode.
The [common execution-plan contract](../docs/Execution-Plans.md) defines Markdown
plans, delegation, shared `--tasks` semantics and extension boundaries. The
[generic launcher](../tools/execute-plan) runs ordinary plans; E2E and repair
retain their specialized state machines and existing model ladders. Repair's optional
`--tasks` bounds completed category passes (an unfiltered verification `all`
pass counts as one composite task); omission retains the full selected loop.

The shared [detached launcher module](../tools/detached_launcher.py) owns
workflow attachment, process supervision, fresh Codex transport, log rotation
and output following for `fix-tests`, `write-e2e` and ordinary plan workflows;
`run-tests` shares its lock
primitives, output following and terminal display, and registers test owners
started inside an E2E or ordinary plan agent session. The
[adapter map](../docs/Execution-Plans.md#extension-boundary) distinguishes their
shared components and retained execution engines.
Their model workflows use the shared
[response recovery contract](../docs/Execution-Plans.md#common-launcher-interface)
for rejected agent handoffs, preserving acceptance guards and existing session caps.
All launcher-owned model sessions also use that contract's capacity recovery:
5, 10, 20, 40 and 80 second retries, then one session-only GPT-6.1 Sol to
GPT-6 Astra fallback at unchanged effort. Capacity attempts do not advance the
repair/E2E model ladders or consume additional logical session slots.
Cancellation or worker death cancels only those recorded test runs, validates
their directory identities and waits for guarded cleanup before releasing the
workflow lock. Already-running tests that the agent merely attaches to remain
owned by their original caller.

Private output and checkpoints use the shared storage and retention libraries
under `output/test-runs/host/write-e2e/`. In a launcher handling multiple tasks,
each completed task's top-pane session updates are replaced after acceptance
and staging by `Task ID: Title (sessions=N, duration=D)`, preserving the bold
task-label link and title from its live update and using that task's
session count and duration (`12m` below an hour, `1h 31m` from an hour onward).
Current-task updates keep their existing format.
Completed optimization sessions use the same green compact summary, retaining
their optimization batch heading and their own session count and duration.
These compact summaries survive attachment and replace the completed task's
controller scrollback too. At launcher exit, the final recap includes every
task completed in that run, in order, with the existing detailed format:
a green `Task ID complete.` line,
followed by the number of sessions spent on that task (including earlier
launcher runs) and the cumulative sessions actually consumed by the current
launcher run, including earlier sessions only for the unfinished task being
resumed. A new launcher starting a different task resets that total; unused
session allowance is never counted. It
saves task-session worktree changes across handoffs and stages them with the
agent's explicit file list, including changes from the final session. Changes
already present before the task and generated `output/` artifacts are excluded.
The launcher saves the full summary and next-session prompt in `handoff.txt`
without printing them. At an incomplete session boundary or safe stop, it still prints and saves
the handoff. A new invocation after that boundary continues the latest
handoff with fresh session and task budgets. An interrupted checkpoint
starts a recovery session under the model policy above that rechecks evidence and cleanup,
resolves authorized remaining work, then runs host and live VM validation in
that session. A pass closes the task; a failure preserves evidence and hands off
for investigation and repairs in the next session.
Blocked checkpoints retain their pending question and pause again until answered.
If the developer removes the unfinished current task and explicitly declares it
under `Excluded tasks:` in the queue, restart selects the next task with a fresh
task budget and no acceptance credit for the removed task. Retained queue order
and completion states must be unchanged; pending acceptance/commit recovery still
refuses exclusion. Saved evidence and partial source work remain preserved, and
the recovery session verifies prior owned cleanup before new live work.
The full engineering handoff remains in `handoff.txt`, without being repeated in
the blocked display. If an interrupted session checked its own task but did not
save a valid completion response, the launcher automatically starts a recovery
session for that task before selecting the next one, even if the queue is empty.
Recovery inspects the saved handoff and retained acceptance/cleanup evidence,
reuses sufficient passing results and completes missing validation or close-out.
If acceptance remains incomplete, it restores the task's unchecked row, brief
and pointer before continuing. Only a validated completion response and successful
staging permit advancement. Newly added unchecked tasks are preserved and included
in recovery's status checks. Removed or reordered existing tasks, changes to another
task's status and newly added completed tasks still refuse recovery.
The launcher never assumes an interrupted live test passed. Lifecycle qualification
lives in
[test_write_e2e_cleanup_safety.py](unit/test_write_e2e_cleanup_safety.py).

### Aggregate execution and reconnection

Run `tools/run-tests all` for the enabled VM queue, or `make test-all VM=NAME`
(`tools/run-tests all --vm NAME`, also the default with only `--vm NAME`) for one registered VM,
for all established regressions. `make test-all-verify VM=NAME` / `tools/run-tests all-verify --vm NAME`
are compatibility aliases for the same work. Every VM entry point uses
metadata-only snapshot verification, including standalone preparation,
maintenance, qualification and recovery. No path hashes VM images or runs
structural image scans. Ownership locks, snapshot/chain checks, targeted guest
inspection, package/artifact verification and cleanup remain active.
`--skip-backing-verification` remains an accepted compatibility no-op.
Reports record `metadata-only` and zero image-content verification bytes.
Both aggregate targets automatically discover all ready E2E variants, including
the installed Parent About/license scenario. For E2E-only runs, use
`tools/run-tests e2e --vm NAME --ready --artifacts '<fresh-artifact-directory>'`; for just
Parent About, replace `--ready` with `--scenario 'E2E-030/parent'`. The
[E2E runner guide](e2e/README.md#run-e2e-scenarios) covers building inputs, listing,
pending scope and prerequisites.
Every `tools/run-tests` category runs independently of its terminal. Closing the
terminal detaches the display; tests continue. Ctrl+C requests cancellation and
waits for owned cleanup. Invoke `tools/run-tests --vm NAME` for a VM run in a new terminal to attach to
the existing progress and final output, including its exit status. While a run
is active in the requested scope, execution invocations warn and attach to it,
ignoring new categories or invalid options. VM attachment and cancellation
require the original canonical `--vm` selection for explicitly selected runs;
missing or different selections refuse. Default queue runs attach and cancel
without `--vm` or with the original list. IDs resolve to names before saving
the selection; repair retries forward those names rather than expanding to all enabled VMs.
`tools/run-tests --vm NAME --stop` attaches to a narrowed VM run, requests
cancellation, and waits for owned cleanup; when idle it returns without starting
tests or consuming saved results. Attachment searches only the requested scope:
use a host category for host work and `vm` for VM work. Host and VM sessions and
activity locks are independent, allowing separate runs and standalone VM
preparation to overlap host tests. No arguments select the VM session namespace.
The original selection and options remain in effect. Global and category help,
listings, and collection-only invocations always return their requested inspection
output without acquiring or checking test/session locks, attaching to a run, or
marking its result delivered.
A failed or incomplete idle session can be replaced by an explicit new selection;
its output is preserved and startup recovery runs before new VM checks. Host-only
execution refuses pending VM recovery.
When no run is active, an unread successful result is replayed within the
requested host or VM scope. Invoke without arguments to replay any unread VM-side
result. After delivery, or when no VM session exists, an invocation without arguments starts the `all`
aggregate. VM session output and ownership records live under
`output/test-runs/host/sessions/`; host-only records live under
`output/test-runs/host/sessions-host/`. Reconnect to a host-only run with a host
category such as `host`, `ui`, or `unit` to replay its idle result.
Runs started before reconnect support
cannot be adopted; their existing checkout lock still prevents duplicate launches.
Refresh an older installed dispatcher with `./setup.sh --test-tools-only` before
using the new fast mode. Neither aggregate accepts suite selectors. The terminal shows
colored category progress with branches for the four host workers, a join before
the exclusive VM stages, and overall wall time. Publishing, build A, build B and
comparison appear individually under the host branch that runs them. Branch assignment reflects
actual launches; work waiting for capacity or headroom stays unassigned. All
branches refresh together, including elapsed times while children are quiet.
Idle branch headings are gray; running branch headings are bold.
Queued categories with a known reason display `[Waiting]` and that reason,
including observed and required RAM for memory admission. These rows remain
visible ahead of completed work when the terminal is short.
Completed categories remain under the branch that ran them, in launch order.
Detailed dashboard rows are clipped to terminal width to keep cursor redraws
aligned; controller headers wrap without clipping. The lower frame fits the
space beneath the header, using the output terminal's actual
dimensions instead of potentially stale `LINES`/`COLUMNS` environment values.
The saved final summary retains the full text of all rows. Full output is continuously
appended and flushed to the run's retained `report.md`.
The accompanying `progress.json` records the latest category counts, states,
branch assignments and launch order. Case IDs and retained-pass inventories live
in adjacent immutable `inventory-NNN.json` files; each progress row names its file
and entry index. The inventory is published only when categories or their inventories
change, and identical progress snapshots and session frames are not rewritten.
Live terminal/watch readers reuse unchanged JSON payloads after checking the
current file's identity, timestamps and safety on every poll; changed or replaced
files are read again. Log readers continue reading only appended bytes.
Rejected metadata does not stop attached log replay or final-result delivery and
is never forwarded to a supervising launcher. Checkpoints synchronize new
inventory contents and directory entries before synchronizing referring status.
The final report includes the same branch summary. Percentages describe completed
checks, not estimated time remaining.
Each run gets a new private directory. Aggregate retention keeps the last three runs;
registered output older than that window is removed when the next run starts.
Output is flushed for live readers on every fragment. Routine progress snapshots
are coalesced to one per second and disk synchronization is batched every five
seconds while the coordinator runs. Failure events, category closure and final
closure force synchronization; fixture failures are durable before cancellation.
This avoids report traffic repeatedly closing the runner's own I/O pressure gate.
An abrupt machine failure can lose the latest routine checkpoint interval.
Resume checkpoints also coalesce successful completions over five seconds,
instead of rewriting the growing pass inventory every second. Failure events
and finalization synchronously save pending completions. An abrupt machine
failure can replay uncheckpointed passes; in-flight work is never certified.
Retention pins replacement-publication ownership before its source writer lock,
but reads and verifies cumulative archives only when selecting originals for
retirement. Nonexpiring startup and finalization preserve those originals without
rereading their replacement payloads. Actual retirement still verifies complete
replacement custody before deleting any original or sealed slot.
The two capture-history size-limit regressions buffer physical sync only while
generating their hundreds of input seals, using module-local OS references.
Their publication, interruption, acknowledgement and retirement boundaries keep
real sync. Small file/directory sync-failure regressions preserve required-source
and same-slot retry coverage without repeating those flushes for every input.
Bulk evidence ZIP writes synchronize at most 4 MiB at a time and pace copying
at 4 MiB/s, including failed-run publication. Each batch has its own time budget;
slow reads cannot accumulate credit for a later write burst. Every bulk flush
also leaves recovery time equal to its duration, capped at one second, even when
a slow flush exhausts the throughput budget. This bounds dirty archive writes
while avoiding thousands of tiny syncs and multiplied disk-contention delays.
Small bundles keep their normal final sync. These are archive-publication
mechanics, not task progression requirements: ordinary plans and E2E
implementation do not publish closed turns or cumulative proof before advancing.
Explicit archive operations keep their normal verification and recovery guards.
For an explicitly requested legacy archive, acknowledgements share one verified
cumulative archive while its ownership locks and descriptors remain pinned.
Each selected record checks its request, delivery and source provenance; later
archive inspections verify it again. Ordinary runner completion uses no such
acknowledgement.
The detached coordinator spaces capture and retention journal syncs by at
least 100 ms. Host pytest workers (unit, component, UI and fixture tests) pace
real `fsync` calls in their fixture/test context, including recording,
report, evidence and other storage helpers. Workers omit the fixed floor: each
sync leaves recovery time equal to nine times its measured duration. This
reduces contention from parallel small-file transactions without withholding
workers because of unrelated host I/O. Every sync still executes before its
transaction advances, with the same error propagation and recovery ordering.
The `unpaced_journals` fixture is reserved for qualifying the pacer itself;
ordinary durability and fault-injection tests keep real, paced syncs.

The aggregate uses at most four host workers, subject to compatibility and CPU,
memory and swap admission. Host-wide I/O pressure is recorded but does not gate
ordinary host tests, including cleanup and UI buckets: background disk traffic
must not strand otherwise available branches. Publishing, artifact builds, VM
launches and host work overlapping builds retain their I/O admission limits and
recovery window. Reviewed cleanup modules run in balanced buckets using measured
module costs shared with unit scheduling. Modules keep their fixtures together;
the large installed-journey safety matrix explicitly permits eight pieces of
exact test IDs because its fixtures and outputs are function-local. This review
applies to both schedulers, with a regression guard against shared fixture scope.
Its synthetic inventories contain only the exercised scenario family, preserving
that family's complete matrix and the real recorder while avoiding copies
of unrelated families for every injected fault. The matrix's opt-in
`collector_sync` fixture checks flushed bytes and file-before-directory sync
for every collector write without forcing repeated physical flushes. It replaces
only the collector's OS reference; retention journals keep real synchronization.
The collector regressions in `test_e2e_evidence.py` exercise real file/directory
sync and refusal before registration when either sync fails. Launcher dispatch
parameters use synthetic package identities instead of repeatedly scanning the
checkout; `test_test_storage_cleanup_safety.py` retains real source-byte identity
and preservation checks. These are explicit regression
tests, included in unit/host/all coverage; startup and cleanup do not run them.
Actual cleanup runs serially before worker scheduling with every live ownership,
recovery and VM lease check intact. It creates no pytest fixtures or qualification
reports and has no parallel cleanup branches or join stage.

Host work and independent publishing/build jobs share the branches; comparison
joins both successful builders and their validated distinct outputs. Publishing
may overlap units, components, request behavior and artifacts.
Artifact operations may overlap known parallel host categories and each other.
Every VM attempt remains exclusive after the host/build join. Resource shortages
defer launches, and already-running tests finish normally when load rises.
VM memory admission budgets 50% of configured guest RAM, plus QEMU/controller
overhead (10% of configured RAM, at least 1 GiB) and the 2 GiB host reserve.
This deliberately allows memory overcommit instead of requiring all guest RAM
to be available before launch. Pressure and swap admission checks still apply;
the estimate is not a peak-memory guarantee and does not resize the guest.
Scheduler changes take effect in new runner processes, not an already-waiting
coordinator.

Private `resources.jsonl` and
`schedule.jsonl` retain sampled host load, dependencies, admitted companions and
wait reasons. Estimates guide ordering without relaxing resource or test limits.

UI bucket collection and completion must match the original discovered test IDs
exactly; count-only matches cannot pass. New UI modules run exclusively until
their isolation is reviewed in `tools/regression_ui.py`. Nested Shell stays in
one bucket so its stable latest-evidence paths have one writer. The accessible
adapter uses private compositors, buses, settings and attempt artifacts,
including its Shell search. Recording and viewer tool UI tests are excluded under
the [test scope mandate](../docs/Mandates/Test-Scope-Mandate.md). Non-product
unit coverage is not added by default unless specifically requested; maintain
existing shared safety regressions and validate ordinary encoding, masking,
publication or helper changes through their existing consumers.
Host aggregates and focused UI runs retain the `live_e2e` exclusion during
collection and execution so VM-dependent checks cannot enter the host category.
The private compositor fixture is explicitly required by the nested-Shell module,
so its outer Devkit viewer never depends on a prior module's display setup. The
checkout `dogtail_config.ini` disables Dogtail's shared `/tmp` debug file through
supported configuration; captured console output and existing per-test
diagnostics remain available. Nested-Shell product interaction binds the owned
`child-panel` Application UI API endpoint, resolves `child-request-button` in its
surface and invokes its ordinary `activate` operation. Panel preferences use
canonical boolean values and text observations use the same shared facade as
installed E2E. No focus or native key/pointer input is required for these controls.
Repeated activation still proves the launcher count, single-flight request
handling, one overlay and clean reopen.
Test fixture setup/teardown failures and pytest infrastructure failures stop further host scheduling and cancel owned
companions through normal cleanup. Assertions, deadlines and launcher safety
prerequisites are unchanged; no automatic retries are used. Each UI raw stream
includes pytest phase durations for tuning estimates, including setup and
teardown; estimates are ordering hints, never timeout or resource permissions.

Ctrl+C displays a red notice throughout shutdown: “Tests interrupted. Shutting
down safely; please wait for cleanup to finish.” Repeated interrupts keep the
same cooperative cleanup behavior. After owned commands exit, the notice changes
to “Tests interrupted. Shutdown finished; see cleanup results above.” This applies
to host-only runs and every stage of both complete aggregates.

The maintained launchers hold a checkout activity lock for the full command,
including cleanup. Aggregate children join through an inherited locked file
descriptor; another terminal's `tools/run-tests` attaches within the same scope.
Host-only selections use `artifacts/test-activity/host.lock`; selections with
VM or privileged integration work keep
`artifacts/test-activity/lock`. These are the only two test scope locks;
`all` and mixed host/VM selections reserve both, including cleanup.
Competing owners within each scope refuse. Named VM preparation also retains
its existing per-guest lease and ownership checks.
Standalone app-snapshot preparation uses `vm-NAME.lock` in that same directory,
with a shared lease on `lock`. Different named VMs may prepare concurrently;
the same name and existing aggregate owners remain excluded. Child workers
inherit the exact named lock descriptor, and retention stays separate per VM.
Host-only tests can therefore run alongside `tools/prepare-appsnapshot`.
The VM's existing cross-controller lease remains independently authoritative.
Ordinary pytest caches are disabled. The report labels every output fragment
with its category and links separate private raw streams; one coordinator writes
all progress. Category `waiting` records time queued separately from execution.
Source identity is recorded at startup for reference. Checkout edits during a
run do not stop scheduling or invalidate results. Tests can load later edits; a passing run does not
certify one immutable checkout revision.

The aggregate dispatches each complete `system` or ready `e2e` selection in one
invocation through the shared VM launcher. Prerequisite checks run once at each
suite's startup, not between cases or phases. Both controllers use the shared
event writer for live counts and failures. A failure event is reported immediately;
automatic aggregate cancellation waits for the controller to finish evidence
collection, restoration and its final audit. Explicit user cancellation remains
available through the normal owned-process channel.

Automatic package preparation can reuse content-qualified inputs across invocations. See
[reusable startup preparation](e2e/README.md#reusable-startup-preparation) for the
input keys, invalidation and bounded storage contract. Cleanup does not use a
test qualification cache. Explicit regression and fresh-build
selections remain fresh.

Installed-system runs retain one exclusive VM lease. Package installation/reboot
checks keep their lifecycle together on `onpc_baseline`; post-install checks use
the content-qualified version snapshot. Explicit upgrade attempts keep upgraded
state throughout their selected checks. The
[common attempt envelope](../docs/TestAutomation/E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope)
owns snapshot freshness, online/offline restore, per-case provisioning and final
audit. Multi-case E2E runs share the lease and connection, while each case gets
its own declared inputs, worker and evidence with no product state carried from
another case. Case results remain candidates until suite audit, host preservation
and actual lease release pass; a case or transition failure stops the suite.

The command collects current unit/contract, private-D-Bus, UI and fixture runtime
cases (including cleanup-safety regressions in the unit category);
runs source/static, child Node/GJS and backend checks; runs the local publishing
module (source packaging/integrity, clean sbuild with declared tests, and source
and binary Lintian); builds two fresh artifact
sets and compares them; then runs the full installed-system selection and every
E2E variant whose inventory status is `ready`. New cases within these suites and
newly registered ready variants need no edit to the aggregate. Pending roadmap
variants and deliberate failure/recovery qualification routes are excluded.
Register new system areas through the existing system selection contract;
the aggregate always requests its full selection.

Both aggregate targets run the same publishing module through
`tools/run-tests publish` and [`tools/publishing_checks.py`](../tools/publishing_checks.py).
It includes current uncommitted source edits and requires no release credentials.
It never publishes. `make publish` delivers a release without rerunning local
publishing tests; see [publishing](../docs/Publishing.md#local-publishing-tests).

Counts are collected pytest cases, registered installed-system executions and
E2E variants. A non-pytest command (such as static checks, Node's complete suite,
or an explicitly selected artifact build) counts as one check. Discovery and
prerequisites, cleanup prerequisites, and automatic package input preparation
remain visible but do not contribute to overall completed or total counts.
For `system`, those counts include only registered installed-system executions.
Totals show `?` while discovery is
incomplete. Completed counts include failed cases, so 100% means execution
completed; only a green check means success. A failing prerequisite or VM
attempt blocks its dependent operations. Skipped or expected-failure cases are
reported as incomplete coverage and prevent a green aggregate result.

Ctrl+C latches cancellation, prevents further tests from starting, and waits
for every active child's cleanup, including guarded VM restoration. Repeated
Ctrl+C does not interrupt cleanup. No process-name scans or unrelated process
signals are used. A controller losing its parent’s pipe also cancels. Cleanup
can take several minutes; do not use SIGKILL if you want normal restoration.
Failures are emitted when pytest reports them, including setup/teardown errors;
partial output is flushed before progress updates. Guest traceback details are
flushed in the private guest results, while registered failure IDs immediately
reach the report. Existing collection returns those private diagnostics even on
interruption. Abrupt machine power loss can still prevent guest collection.

Run from the prepared development host as the normal user. The aggregate never
installs dependencies or opens an authorization dialog: unavailable tools,
authorization, baseline or inventory cause failure. After updating the runner,
refresh through `./setup.sh --test-tools-only`. This installs the maintained
dispatcher and the `make test-all VM=NAME` Codex rule; restart Codex to load new rules.
Direct terminal use has no Codex approval layer. The equivalent already-approved
`tools/run-tests all --vm NAME` route remains available in an existing Codex session.
This is development/test tooling only; package update activation is **none**.

### VM watch recordings

`tools/run-tests` automatically records system and E2E execution through the
same GTK layout, read-only VM feeds and filtered SSH terminals as `tools/watch`.
One private renderer/encoder belongs to the runner, including its concurrent VM
queue. For `fix-tests` VM queues, the parent repair launcher owns that controller
through all worker retries and owned cleanup; nested runners inherit its verified
endpoint rather than creating competing controllers. Its recording index belongs
to the parent run. Capture includes only that queue's feeds from this checkout: another
controller's secret seals cannot authorize recording its display. A visible watch
window can be opened, closed or absent independently.
The recording is human review material; test assertions and result reports
remain authoritative. Qualified masked graphical authentication in GDM, lock
screens and MATE/Shell Polkit prompts remains visible, including rejection and
failure results. Fresh recipient checks and private credential delivery remain
mandatory. Serial, VT6 and installation authentication retain opaque secret-input
intervals, with nonsecret labels identifying the current VM panels; retained
command text follows the shared watch filtering contract. On release, opacity
remains until visible VM textures have refreshed after the safe result and GTK
has had another paint interval.

Final WebMs live directly in the shared managed
`output/test-runs/recordings/` directory, already gitignored by `output/`.
It stays private to the unprivileged recording owner. An old `host/recordings/`
directory moves intact on the next recording start, after its controller and
case leases are idle; conflicting destinations are preserved and refused.
Names are `category-ID-VMnames.webm`, for example
`e2e-150-Ubuntu26.04-Fedora44.webm`. Names include the VMs actually visible in
the clip, ordered by numeric IDs in `config/test-vm.json`, with the common
`onpc-` prefix omitted. VM workers share one capture; concurrent executions of
the same case merge into one clip. Different cases can overlap in time.

`system --list` displays persistent numeric IDs; `system --id N[,N...]` selects
them without changing existing `--area`/`--test` or checkpoint identities.
System lifecycle phases share one case ID; parameter variants have separate
IDs. Existing assignments must never be renumbered or reused.

Each category/ID retains only its latest playable recording, including a failed
test's recording. Publication is atomic and replaces the earlier owned clip
even when its VM-name suffix changes. Encoder/validation failure preserves the
previous file and reports an infrastructure error. Every candidate is decoded
in full before publication. Temporary full-session media
uses shared scratch; final recordings have no automatic age or size rotation.
This explicit latest-only policy is separate from ordinary report retention.
Publication displays one refreshing `Recording: x/y` progress line in the runner
and watch terminal, counting completed clips out of the session's total.
Individual recording paths remain in the session's `recordings.json` index.

The private renderer requires the existing GTK/Mutter/VTE development stack and
FFmpeg, installed only through `./setup.sh`. It records at 5 fps with one fast VP9
encoder and bounded frame handoff. No audio is recorded. Keyframe-aligned clips
can include a short prelude, whose visible VMs also appear in the filename.
Transient GTK paint gaps retain the last safe frame and are counted separately
from encoder overload; a sustained rendering stall fails capture.
Recording is an ordinary development aid: new unit tests require a specific
request, and UI tests are excluded under the
[test scope mandate](../docs/Mandates/Test-Scope-Mandate.md).
Do not automatically relocate its deleted playback, masking, publication or
benchmark matrix to another layer. Runtime safeguards remain part of the recording contract.

### Aggregate output retention

The [test storage mandate](../docs/Mandates/Test-Storage-Mandate.md) specifies the
required shared helpers and forbids producer-selected temporary storage roots.

All new bulk test output lives in the gitignored, disk-backed
`output/test-runs/` tree. `host/` and `privileged/` separate caller and root
ownership. Storage refuses tmpfs/ramfs and symlinked ancestors. Allocation roots
are private; reports, reconnect sessions, repair logs, exports, cache receipts
and journals have separate subdirectories. Small AF_UNIX runtime sockets remain
in short `/tmp` directories because Linux limits socket paths to 107 bytes;
their owners remove them on close. Explicit screenshot exports retain the
existing caller-owned `/tmp/onpc-*.png` contract.

Each retention journal keeps at most three runs and 4 GiB of allocated blocks,
checked at session boundaries. Older completed runs expire first; an oversized
current run is preserved and reported as an error at finalization. Before new
execution, automatic recovery retires oversized completed execution evidence
under the activity/storage owner locks, after recorded VM recovery and the
privileged live-reference audit. It reports this retirement; active owners,
unresolved recovery and unsafe identities still refuse. Other journals retain
their oversized evidence until explicit cleanup. These are per-journal limits,
not a filesystem quota on an active build. Recovery receipts expire with their
run. Reconnect and repair directories also rotate; repair transcripts retain
a bounded tail (32 MiB threshold) between operations. Process-owned temporary
scratch uses an inherited owner lock and recorded directory identity: the next
launcher reclaims idle scratch, while active owners remain protected. Build
subprocesses forward inherited scratch leases through the fixture builder too.
Scratch initialization publishes a complete owner atomically from a recorded
staging slot; interrupted initialization and deletion can resume without
adopting unknown payloads or losing the directory identity.
Pruning always audits registered allocations and budgets, but rewrites its
journal only when retiring records. Session lifecycle and allocation changes
still synchronize before returning; unchanged pruning adds no duplicate flushes.

During retention recovery, captures from the same workflow share one verified
cumulative archive while its journal locks and file descriptors remain pinned.
Each capture still requires its exact authenticated request and original-file
provenance. Releasing that scope ends reuse; later recovery verifies the archive
again, including corruption and replacement checks.

Artifact exports also use a bounded journal: each explicitly requested export
starts a retention session and can retire older exports. Reuse an existing
retained export when available; see [artifact access](#prompt-free-test-artifact-access).
An expired report/export affects its availability for inspection, never a
completed task's status. Ordinary plans follow the shared
[completion policy](../docs/Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery)
without cumulative proof publication, evidence renewal or historical-link repair.

Multi-file evidence uses `Store.inspection()` and `Store.publication()` in the
same export journal, with the same three-run/4-GiB limits. Read-only inspections
share ownership and journal locks, allowing concurrent bundle reads while
excluding writers, publication and cleanup until the last reader exits.
Publication registers
one empty staging allocation before writing, measures existing plus projected
output before allocation, and checks actual simultaneous usage before commit.
It leaves the previous journal and every existing export unchanged on precommit
failure. A durable committed receipt owns any interrupted retirement. Ordinary
writers refuse a pending publication; the bundle route re-verifies its complete
payload before finishing retirement. `--defer-cleanup` commits verified evidence
while retaining old exports until `bundle-finish`; this permits safety validation
before the first changed deletion. It is unfinished cleanup, not another export
slot. No new export may start until that cleanup is finished.

When retained builder output establishes an interruption before manifest
publication, use `tools/cleanup-e2e --vm NAME --discard-unpublished-input CHECK`
for its exact named qualification input, then resume normal preparation. The
[storage mandate](../docs/Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes)
owns the identity, completed-owner and publication guards. This action preserves
reports and journals and supplies no test acceptance; normal nonempty input
verification/refusal remains unchanged.

An evidenced batch/per-VM input ownership conflict has a separate nondeleting
recovery: `tools/cleanup-e2e --vm NAME --transfer-batch-input CHECK`. The
[storage mandate](../docs/Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes)
owns its two-owner audit, published-input verification and resumable transaction.
Inputs normally prepare inside their VM worker's retention session. This route
preserves reports and original records; it neither rotates evidence nor supplies
acceptance. Pending transfers refuse ordinary retention writes until recovery
finishes with the original selector.

When the developer explicitly authorizes discarding saved results, use
`tools/cleanup-e2e --vm NAME --discard-completed` for all completed registered
execution results of that VM, or `tools/cleanup-e2e --host-only --discard-completed`
for ordinary host execution results. Without `--vm`, the former processes every
enabled VM serially. This removes all recorded allocations in the selected
execution journal, including its current oversized run and retained history;
it does not select only enough files to meet the budget. Normal cleanup still
preserves evidence. Workflow/session logs, recovery-diagnostic journals,
unregistered files and other VMs' journals are outside this explicit route.
The privileged operation reconciles the VM first, then holds its compatibility
and named leases through live-reference checks, a full identity/mount audit and
deletion. Active retention owners and unfinished/marked journals refuse discard.
Host execution uses its checkout activity and retention owner locks. Journals
are left intact, making partial deletion retryable without adopting replacements.
The argument-free `check_retained_runs_cleanup` dispatcher entry serves this
operation without creating a new retention session or rotating evidence.
Refresh the dispatcher through `./setup.sh --test-tools-only` after changing its
recovery entry list. This development tooling changes no product state.

`make test-all VM=NAME`, `make test-all-verify VM=NAME`, `tools/run-tests host` and
`tools/run-tests host-builds` share **last-three-runs** retention. The runner
records each newly allocated report, publishing snapshot (including Lintian scratch), sbuild output,
package artifact directory, sbuild scratch parent, GJS coverage directory, persistent
UI log/render directory and nested Shell review copy in `artifacts/ui/child-shell/`.
Each new aggregate keeps the two preceding completed runs alongside
the current run, removing older registered directories, including logs and
failed-test evidence. Failed or cooperatively interrupted runs count toward the
same three-run limit. Copy any evidence needed for longer work before it expires.

When a producer exclusively recreates and registers a previously removed named
output, its latest allocation record owns that path. Older records remain in
the journal but cannot validate or delete the newer allocation. Recovery and
rotation validate the latest recorded identity, ownership and mount boundaries;
an unregistered replacement still refuses. The recreated output expires with
its latest owner.

Host-only runs use `output/test-runs/host/state/retention-host/`; VM workers and
snapshot preparation use `output/test-runs/host/state/retention-<canonical-target>/`.
The queue summary uses `retention-batch/`; older single-target records remain in
`retention/`. Each journal retains
its own last three runs, so active host evidence cannot block VM preparation
or be rotated by it. Existing records stay in their original journal.
Privileged system/E2E
outputs have a separate root-owned journal under
`output/test-runs/privileged/state/retention-<uid>/`; all VM categories in
one aggregate share its run token. Privileged outputs older than its three-run
window rotate during serial preflight, before VM memory admission, after the
shared VM lease/journal show no unfinished recovery. A host-only
run or a failure before VM execution does not discard the last VM diagnostics.
Refresh the installed dispatcher with `./setup.sh --test-tools-only` after this
change. Test tooling has package update activation **none**.

Standalone graphical smoke qualifications (including their installed-journey
wrappers) and spectator qualifications join this same privileged journal.
Their working directories and private collectors are registered before use;
the three-run limit applies to failed qualifications too. When already inside
an E2E retention session they reuse its run rather than rotate it. Invocation
validation precedes storage allocation, and unfinished VM recovery still blocks
rotation. These checkout-side changes activate on the next invocation without
an installed-helper refresh.

Transport, attachment and worker diagnostic reports are registered evidence,
separate from disposable scratch. Recovery diagnostics use their own bounded
`output/test-runs/privileged/state/recovery-diagnostics-<uid>/` journal, so a
failed or interrupted recovery keeps its logs without rotating or clearing the
unfinished VM journal. The existing VM lease still controls recovery itself.

For older unregistered qualification directories, `tools/run-tests integration --vm NAME
check_tmp_storage` prints a read-only inventory with sizes and directory
identities. After reviewing the inventory, put only explicitly selected records
(`path`, `device`, `inode`, `mode`) in `artifacts/tmp-storage-cleanup.json`, then
run `tools/run-tests integration --vm NAME check_tmp_storage_cleanup`. This developer
cleanup requires an idle privileged retention owner and completed VM recovery,
refuses live process references, and validates every identity and mount boundary
before deleting anything. It never selects deletion targets by prefix or age.
Keep needed recent diagnostics out of the manifest. Both commands use the
existing integration dispatcher and live ownership checks.

System evidence keeps its registered allocation root at mode 0700; use the
installed artifact reader for privileged results. Legacy journals with mismatched
system-root modes require explicit migration; they cannot create an unbounded
archive outside rotation.

For the storage relocation, `tools/run-tests integration --vm NAME check_storage_migration`
prints a read-only legacy inventory when `output/test-runs/storage-migration.json` is
absent. A reviewed manifest contains exact `path`, `device`, `inode`, `mode` and
`uid` records. With the manifest present, the same command locks legacy owners,
checks VM recovery and live process references, copies and verifies diagnostic
files into bounded disk storage, then removes the exact audited originals.
Legacy reconnect, repair and generated report directories can be explicitly
migrated by the same manifest. Frozen package inputs and stale sockets are disposable. Unknown identities,
mounts or copy failures refuse deletion; unrelated `/tmp` files are not swept.

Storage leases exclude active owners; deletion uses recorded directory identities
and pinned descriptors, refusing replacements, symlink ancestors and mounts.
No `/tmp/onpc-*` or `/var/tmp/onpc-*` prefix sweep is used. An unfinished retention
journal on the VM side after abrupt termination triggers automatic recovery
before selected VM checks start. Host-only runs never inspect or recover that
journal. Host startup automatically reconciles unfinished host retention under
the host activity and storage owner locks. Reconnect registration journals are
also reconciled under the startup gates and activity lock before registration.
`tools/cleanup-e2e --host-only` exposes the same host recovery without VM access;
plain `tools/cleanup-e2e` reconciles enabled VMs followed by host retention.
The launcher must hold checkout activity ownership
and acquire the storage owner locks; a live owner is never killed or displaced.
The installed `check_test_recovery` route reconciles the VM through the existing
identity-checked recovery controller and shared VM lease. It also runs before a
new VM category, so a stale VM journal cannot strand otherwise completed host work.
Recovery runs no test suites and creates no parallel cleanup branches.
Recorded maintenance cleanup also accepts an already restored, powered-off guest
when its active and inactive XML exactly match the recorded original. It audits
the baseline snapshot and guest before completing the stale journal, without
shutting down, reverting or redefining the VM. A running replacement instance
still refuses; shut it down through the VM manager before retrying recovery.
Changed guest state or configuration preserves the journal and evidence.
Online snapshot startup records the restored instance before progress teardown,
logging or fresh run metadata. Ordinary recovery can therefore restore that
recorded instance even if startup failed before its saved snapshot tag was
rebound, after verifying the private snapshot and isolation proofs. An abrupt
interruption before the instance is recorded still refuses automatic adoption.
For an explicitly inspected and authorized live instance in that narrow gap,
`tools/test-vm --vm NAME recover-online ID` accepts only a matching interrupted
online start/cleanup journal, private saved-memory proof, baseline and exact
current instance. It restores the baseline and leaves the VM off; it supplies no
test acceptance and does not adopt a replacement for a recorded instance.

After VM recovery succeeds, unfinished retention journals and recovery markers
are archived as `recovered-<run>.json` and `recovered-<run>.marker`. Every registered
allocation must pass ownership, identity and mount validation before its blocker
is cleared. Evidence remains in the normal rotation. After recovery succeeds,
older runs may expire under the count and byte limits; the recovered current run
remains unless it alone exceeds the execution storage budget. Oversized completed
execution allocations then retire automatically through the same identity audit,
with VM leases held through privileged deletion. Recovery does not scan
temporary-directory prefixes and is retryable.
Changed identities, an active lease, unsupported VM interruption phases, or a failed
baseline audit still refuse a new run and preserve evidence with a diagnostic.
Ordinary test failures and cooperative Ctrl+C finish their storage ownership.
Fixture setup/teardown or pytest infrastructure failures pin host evidence with
`recovery-required` instead of assuming every fixture exited successfully.
Deletion failures also stop the next run instead of silently accumulating output.
Sbuild scratch uses its supported `unshare_tmpdir_template` inside a registered
`output/test-runs/host/sbuild/onpc-sbuild-scratch-*` parent with mode 0711 (traversable by the
subordinate build user, not publicly listable). Sbuild normally cleans its chroot.
Retention inspects registered scratch and removes expired scratch in a user
namespace mapping the caller and its configured subordinate IDs, so interrupted
builds cannot strand rotation on subordinate-owned private directories. The
namespace worker inherits the storage leases and repeats ownership, inode and
mount checks; it does not change file permissions or ownership. Inspection keeps
evidence intact, and deletion follows the same three-run rotation. Missing ID
mapping prerequisites or failed audits refuse startup and preserve the journal.
This development-tool change activates on invocation, with no product migration
or service restart.

Historical directories created before registration, standalone command outputs,
curated evidence, logs outside registered test directories and operator exports
are not automatically adopted or deleted; their names alone are not proof of
ownership. Pytest temporary roots retain pytest's bounded rotation;
ordinary pytest caches and the Hypothesis example database are disabled. Build
scratch directories use scoped cleanup; VM guest changes use baseline restoration.
This bounds repeated aggregate-generated output for unchanged test scope; it is
not a filesystem quota on active writes or unrelated applications/system logs.

Generated `test-all-runs/` reports are Git-ignored so streaming them cannot
invalidate package or E2E source provenance. Curated evidence elsewhere in this
directory remains tracked and continues to participate in source validation.
This command covers established regressions, not completion of the unfinished
release-acceptance roadmap.

## Test layers

Reusable one-time guest setup belongs in `tools/prepare-vm`, including
fixed app fixtures, launchers, dependencies and persistent harness settings.
Tests and app-snapshot preparation verify those inputs; missing/stale state
requires a separate authorized baseline refresh, never an in-test installer or
repair fallback. Keep attempt credentials/transport/evidence, product installation
and deliberate scenario mutations in their existing lifetime owners. New fixture
work must declare its lifetime. Coverage of shared baseline reconciliation follows
the [test scope mandate](../docs/Mandates/Test-Scope-Mandate.md); ordinary fixture
features do not require per-consumer first-run, repeat, update or retry matrices. See the
[preparation inventory](integration/Environment.md#reusable-preparation-ownership)
and [VM mandate](../docs/Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).

Individual widget behavior and local validation belong in preview UI tests.
Installed E2E verifies realistic customer journeys and meaningful outcomes,
including persistence, authorization, enforcement and OS integration. UI
operations serve those journeys; no installed copy of each component check is
required. Simplify repeated navigation and incidental assertions in completed
and planned cases. Both layers reuse shared GUI operations and public readers; see the
[coverage allocation and duplicate review](../docs/TestAutomation/UI-and-E2E-Coverage.md).

The [2026-09-14 customer scope](../docs/TestAutomation/E2E-Building-Blocks.md) changes
unfinished E2E plans. Preserve product regressions and the shared safety checks
under the [test scope mandate](../docs/Mandates/Test-Scope-Mandate.md).
The default against new non-product unit tests does not require removing existing units.
Customer E2E uses real
actions and visible results; mechanical installation/upgrade/removal retains
its internal checks. Pending legacy E2E declarations require scoped adaptation
with their first consumer, without weakening required product coverage.

| Location | Purpose | Real dependencies and isolation |
| --- | --- | --- |
| `tests/unit/` | Product behavior and existing shared infrastructure regressions under the [test scope mandate](../docs/Mandates/Test-Scope-Mandate.md). By default, no new unit tests for non-product code, unless specifically asked for. | Host-safe; controlled doubles are allowed. Tests that launch fixtures still obey process ownership. |
| `tests/support/` | Explicitly imported host fixtures, doubles, readers and process helpers. | No case collection or live VM operations at import time; guest execution uses `tests/integration` helpers. |
| `tests/fixtures/` | Fixture builders and actual Flatpak runtime acceptance via `make check-test-fixtures`. | Owned processes, private Flatpak state and system bus; runtime tests require unprivileged kernel namespaces and are outside default package-build collection. |
| `tests/component/` | Real broker D-Bus dispatch and serialization on private buses. | Real Gio/GLib transport; injected backend adapters. This is not real installed authorization. |
| `tests/ui/` | Parent, shared request form, feedback UI and nested-Shell component behavior. | Private compositor, D-Bus/AT-SPI/XDG/settings; preview/fake dependencies are declared component inputs. |
| `tests/child/` | Platform-neutral child JavaScript and GJS adapters. | Node and GJS runners; component evidence, not installed GNOME/PAM acceptance. |
| `tests/system/` | Installed package, real caller credentials and OS integration. | Only through the guarded VM runner; excluded from default host discovery. |
| `tests/e2e/` | [Scenario inventory and guarded execution contract](e2e/README.md). | E2E-001 executes real GDM/serial input. Pending customer journeys retain their explicit status and cannot pass through host doubles. |

The current pytest discovery paths and markers are defined in
[pyproject.toml](../pyproject.toml) and [conftest.py](conftest.py). Default pytest
collection includes unit and private-bus components, not the whole product
test matrix. Markers select tests only within the correctly configured runner;
they cannot supply graphical isolation or turn a host process into a guarded
guest. Do not use generic `check-marker`/`check-coverage` as an E2E launcher.

## Cleanup-safety prerequisites

### Approved test and diagnostic categories

Use the [repository approval tools guide](../docs/Approval-Tools.md) for the
complete current/future category matrix, validated options, targeted VM control,
read-only system diagnostics, and trust boundaries. Stable entry points are:

```sh
tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' 'tests/unit/test_graphical_lease.py' -q
tools/run-tests component 'tests/component/test_*.py' -q
tools/run-tests ui -q
tools/run-tests integration --vm NAME check_graphical_worker
tools/run-tests integration --vm NAME check_package_notice
tools/run-tests system --vm NAME --artifacts '<builder-returned-directory>' --area authorization
tools/run-tests e2e --vm NAME --list
tools/diagnose journal --unit 'oh-no-parent-control*' --lines 500
tools/test-vm --vm NAME status
```

`check_package_notice` runs real APT and dpkg against tiny fixture packages in
private chroots allocated through shared retained storage. It exercises the production
notice bootstrap, helper, and removal hook through first install, reinstall,
remove/reinstall, and trigger failure. It changes no host packages or VM state;
it does not exercise the product's kiosk, PAM, or service provisioning.
Command output and results are retained for the artifact reader below.

Always quote filename patterns and parametrized IDs. The launchers validate
every selection and option, expand globs without a shell, preserve exit status,
and retain live ownership checks without running extra prerequisite test suites.
Unit/property/contract selections stay in `tests/unit`, components in
`tests/component`, and UI tests in `tests/ui`. Arbitrary pytest config/plugins,
external paths, symlinks, shell commands and Make argument injection are refused.

The root-owned test dispatcher supports integration, system, E2E and pinned-VM
operations. Its Codex approval and Polkit authorization are separate controls.
It trusts the configured checkout's test code and imports. New files within a
supported category need no per-file approvals. Unimplemented E2E scenarios and planned runners
remain unavailable until implemented; registering an approval is not test
coverage. The updated rules replace broad direct pytest/privileged-reader grants
and restrict relevant old global approvals; use the validated entry points.

The privileged dispatcher disables bytecode writes in its own interpreter and
its children so test runs cannot leave root-owned checkout caches that break
`make build`. Tools refresh also returns an old root-owned `tools/__pycache__`
directory to the owner/group of `tools`, allowing ordinary Debian clean to
remove the cached files. This repair preserves contents, refuses symlinks, and
does nothing when the cache is absent or already owned by a non-root user.

Setup modes, administrator bootstrap, denied-installation repair and activation
belong to [one-time setup](../docs/Approval-Tools.md#one-time-setup).
Use that route for missing prerequisites or changed installed helpers; ordinary
tests never install dependencies or broaden authorization.

Explicit graphical-smoke PNG exports and caller-owned temporary PNG cleanup
follow the [screenshot export and cleanup contract](../docs/Mandates/Test-Storage-Mandate.md#screenshot-export-and-cleanup).
Other artifact exports use the reader below.

Full `./setup.sh`, `--vm-host-only` and `--test-tools-only` maintain graphical
AppArmor policy where libvirt's profiles exist. Hosts without libvirt skip this
stage; Fedora keeps SELinux without AppArmor changes. Classic VS Code
snap attachment needs anonymous graphics-socket peer rules in libvirtd and
QEMU; the QEMU drop-in activates at the next guest start. Development helpers
activate on invocation (`none`), Polkit watches installed rules, and Codex
requires restart. No product package or saved-data change is involved.

### Prompt-free test artifact access

Use the installed `onpc-test-artifacts` helper for privileged inspection across
all test runs, names, extensions, and nested directories. Its Codex allow rule
and dedicated Polkit rule cover the whole helper, not individual files. Run from
the checkout root and keep `--keep-cwd` before the helper path. Substitute exact
returned report/artifact paths for the placeholders below:

```sh
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts read '<report-directory>/input/selected-inputs.json' --bytes 8000
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts list '<report-directory>'
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts tail '<report-directory>/private/command-1.log' --bytes 16000
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts stat '<report-directory>/evidence/result.json'
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts export '<report-directory>/results/recording.webm'
```

`read` also accepts `--offset` for paging through large files. `list` returns
JSON names; `stat` returns JSON type, size, mode, and modification time. `export`
prints an `output/test-runs/host/exports/onpc-artifact-export-*/<original-name>`
path, subject to bounded export retention. Identical requests reuse a freshly
verified private copy without starting a retention run or evicting another
report. The source path, identity, content, checkout and caller must still match;
changed sources receive a new copy. Missing, replaced or corrupt saved copies
refuse specifically instead of returning a remembered path. Its directory is
mode `700` and file mode `600`, both owned by the invoking account. Ordinary
readers can then inspect the copy without privilege. Graphical-smoke PNG exports
follow the separate [screenshot contract](../docs/Mandates/Test-Storage-Mandate.md#screenshot-export-and-cleanup).

Sources may be anywhere beneath `/tmp/onpc-*`, `/var/tmp/onpc-*`,
`/var/tmp/oh-no-parent-control-artifacts`, `/var/log/oh-no-parent-control`, or
this checkout's `tests/`, `artifacts/`, and `output/`. This includes private test
inputs and raw diagnostics for local inspection. Raw exports retain their source
contents; only validated, redacted evidence is suitable for sharing. No sources
are edited, deleted, or made public. Symlink traversal, hard-linked files,
special files, and unrelated host paths are refused. Reads use pinned file
descriptors; exports create new private files without caller-selected write paths.

Use ordinary unprivileged tools for accessible artifacts, this helper for
privileged ones, and the installed test dispatcher for test execution and its
temporary writes. Do not use `pkexec head`, `cat`, `cp`, or an interpreter for
routine artifact work: general root programs have no password-free Polkit grant.
Adding future tests or file formats under these storage roots needs no new rule.

These development-only helpers are absent from the product package. Follow
[one-time setup](../docs/Approval-Tools.md#one-time-setup) for installation,
refresh and rule loading, and [approval limits](../docs/Approval-Tools.md#approval-limits-and-review-findings)
for policy refusals. Initial bootstrap and routine refresh have different
authorization requirements; a missing grant is not permission to retry authentication.

#### Complete qualification evidence bundles

Use the same installed artifact helper for a finite set of files from recorded,
finished allocations, including the caller's shared and selected-target
recovery-diagnostic journals used by maintenance probes. Select exact files or
directories containing only evidence; never select an attempt directory containing
SSH keys or online snapshot state.
Recorded runner output under `host/sessions-host`, `host/sessions` and selected
targets' `host/sessions/vm-NAME` is also supported. The reader holds the session's
retention journal and its separate idle worker lock through publication; active,
unregistered or replaced sessions refuse. Archived session members retain their
exact original path, journal and target scope after session rotation.
Plan references already present in a selected verified bundle use that archived
proof even when the original still exists. They do not require its producer
journal to be idle. Explicit live sources and references absent from the selected
archives still require finished owners; archive integrity and target checks remain.
For scoped plan requests, helper exit 4 with `{"error":"evidence_busy"}` identifies
temporary owner contention. Controllers wait and reselect the exact publication
without spending model sessions. Other refusals retain their existing handling.
Use repeated `--source` arguments for result/JUnit/native/cleanup records,
input manifests and the corresponding host reports. Directories are inventoried
recursively with finite depth/file/byte limits; no glob or arbitrary archive
command is accepted. `--target` accepts registered canonical names and selects
their privileged evidence and host-report journals alongside the fixed shared
host journals; it performs no VM operation and selects no other target's journal.

```sh
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts bundle-plan --target 'onpc-Ubuntu26.04' --target 'onpc-Fedora44' --source '<recorded-allocation>/evidence' --source '<recorded-allocation>/guest-results' --source '<recorded-host-report>' --bundle '<previous-export>/evidence.zip' --summary
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts bundle-export --target 'onpc-Ubuntu26.04' --target 'onpc-Fedora44' --source '<recorded-allocation>/evidence' --source '<recorded-allocation>/guest-results' --source '<recorded-host-report>' --bundle '<previous-export>/evidence.zip' --expect '<selection_sha256>'
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts bundle-list '<returned-export>/evidence.zip' --summary
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts bundle-list '<returned-export>/evidence.zip' --path '<original-file-path>'
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts bundle-read '<returned-export>/evidence.zip' --path '<original-file-path>' --bytes 8000 --offset 0
```

Omit `--bundle` for the first bundle. The plan inventories every selected original
path, logical/allocated size, file/allocation identity, owning journal/run and
SHA-256; `--summary` displays allocation totals instead of the complete file list.
Explicit legacy plan-archive operations support repeated `--reference` paths
with a validated `--plan`. The shared reader resolves those references with its journal
leases held: live files retain normal identity checks, and an absent file can use
its exact original member in an explicitly selected verified bundle. Missing
references return exit 3 and finite JSON `error: evidence_unavailable` plus exact
`paths` for the requested inspection. This does not renew acceptance or reopen
tasks. Other failures remain exit 2; mandatory `--source` and `--bundle` inputs
never receive this missing-reference distinction.
When references have vanished and only finished bundles are selected, discovery
authenticates and inspects their exact publication owners, without inspecting
unrelated current producer journals, including those for the same target. The
same isolation applies when a completion also selects fresh controller records:
discovery reads authenticated journal metadata under shared writer locks, then
pins and audits only owners with selected allocations, plus the publication
destination. It releases discovery locks before inspecting finished owners, so
unrelated active producers can continue registering output. Selected active or
unfinished owners still refuse; metadata, identity and budget checks remain in
force for the selected journals.
The archived member retains its original path, attempt and target provenance. A live
original still requires its normal owner and identity checks; a reappearing
original, wrong target, denied reader, corrupt archive or active selected owner
refuses rather than becoming missing evidence. Readers recheck absence and pinned
archive identities before returning, keep deterministic journal lock order and
exclude publication writers throughout their read scope. Discovery never rotates
sources or writes workflow checkpoints.
Complete nonempty directory selections retain the bounded
[directory closure](../docs/TestAutomation/Export-Design.md#canonical-identities-and-wire-records)
in the verified manifest. An expired directory reference requires this exact
closure and every member's target authority, including after cumulative export
rotation. Legacy files-only archives support exact original files; matching some
descendants never establishes the complete original directory. Empty or changed
live directories refuse instead of falling back to old contents.
It also checks source budgets and conservative simultaneous export space before
publication. Export requires the exact plan digest and repeats these guards.
Concurrent identical exports serialize the reuse decision under the publication
owner. The existing manifest/receipt is the reuse record; operational journal
usage snapshots do not change the selected source provenance. Reuse verifies
the saved archive again and allocates no retention slot. Related files selected
together publish atomically through the same bundle transaction; an interrupted
copy cannot publish a partial group or retire earlier exports.
Earlier verified bundles are flattened with new evidence; identical original
records deduplicate and conflicting records refuse. Every selected file is
preserved, including host selection/results. No file is silently omitted.
An explicitly selected archive may belong to another caller-owned workflow's
publication namespace, including a runner's cumulative capture archive. Discovery
derives only that archive's canonical publication journal and verifies its recorded
allocation, receipt and complete contents, using the same owner checks as bundle
inspection. This applies alongside live reports and controller records too; it
does not admit the other workflow's raw allocations or register acceptance claims.
For a legacy `--reference` to a schema-2 archive, preserve the fully verified ZIP
and receipt as exact payload files instead of flattening logical records together
with unstructured controller files. Their original publication provenance survives
rotation. This grants no structured acceptance; use the runner-issued reference
and consumer for an exact logical claim. Explicit `--bundle` inputs retain the
normal flattening and complete logical-inventory requirements.

Schema-2 bundles add strict `onpc-evidence-record` version-1 identities and an
exact logical-member map to the existing ZIP format. Repository, owner, workflow,
task/check/attempt, target and input/source hashes identify a claim; its closure
binds verdict, members, dependencies and cleanup. Physical generation changes
preserve those identities. Equal bytes or basenames never merge distinct claims.
Schema-1 bundles and their receipts remain readable without implicit upgrades.
All physical members and the finite logical dependency closure are verified
before a logical member is returned; unknown fields, conflicting closures,
wrong checkouts and ambiguous mappings refuse.
Within one pinned verified-read scope, multiple bounded member reads share one
complete archive verification. Each read rechecks the archive and receipt
identities; mutation or scope release invalidates that trust. Concurrent readers
share the finished owner, while publication waits until readers release it.

`bundle-read` accepts either legacy `--path` or the complete
`--record-id`, `--member-id`, `--closure-sha256` triple. The same offset and
16-MiB slice limits apply; this selects an exact member, never a latest result.
The helper also registers repeated `--record-reference` and exactly one
`--consumer` canonical JSON object (sorted keys, compact separators, ASCII
escapes), alongside validated `--plan`. This selection mode refuses until the
custody owner supplies authenticated consumer registration; caller JSON cannot
establish a claim revision or relax input assertions. Trusted host callers use
`plan_evidence.resolve_reference` with an explicit plan/document read scope and
an owner-issued consumer declaration. The selector fragment is
`onpc-evidence-v1:RECORD_ID:MEMBER_ID:CLOSURE_SHA256`, with three lowercase
SHA-256 values. Generic locators remain legacy navigation. The library's typed
structured absence carries `error: evidence_unavailable`, `schema: 1` and exact
`references`; access, integrity and context failures remain refusals. Resolution
returns verified metadata/closure plus a bounded diagnostic slice, explicitly
marking an incomplete slice for large members. No capture or custody operation
is introduced by this reader interface.

When explicitly asked to author archival evidence links, use the
[document evidence interfaces](../docs/Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery)
and `tools/read-only evidence-links --plan ... --declarations ...`. Generated
destinations select one authenticated record/member/closure; disposable report
and export paths are permitted only as exact original inputs to a verified
preview, never as new enduring destinations. `runner_evidence.reference_locator`
derives the workflow's cumulative publication journal from authenticated checkout
identity. `runner_evidence.resolve_reference(..., metadata=True, count=0)` returns
the verified record, member, dependency closure and bundle paths without copying
payload bytes. Its default byte-reader behavior is unchanged. The document
resolver also accepts `count=0` for metadata-only verification. A generic journal
or accepted locator supplies navigation alone. Owner declarations retain the
original target, attempt, inputs, verdict, cleanup and selected member digest;
same bytes from another claim do not satisfy them. Preview/apply introduces no
new acceptance, role downgrade, historical migration or publication gate.

Bundles contain at most 60,000 files and a 64-MiB manifest, without a separate
bundle byte ceiling. Source depth is at most 32, with at most 256 explicit
selections. The unchanged 4-GiB export journal budget accounts all simultaneous
old and staging allocations; an insufficient budget refuses before rotation.
Plan each finite campaign and
preserve required proof before another source session can rotate it. Alternate
two cumulative target bundles when needed; keep each target's newest complete
bundle within the three-export window and check both after every later export.
Do not increase budgets or drop files on refusal.

Publication returns a private caller-owned `onpc-evidence-bundle-*/evidence.zip`
and receipt under shared exports. The bundle has generated member names, a
path/digest/provenance manifest and its checksum; the receipt binds the complete
ZIP checksum and file identity. Inspection checks all bytes, names, provenance
and digests before returning a manifest or an original-file slice (at most
16 MiB). It bounds the archive directory before parsing and never extracts files.
Links, hard links, special files, unsafe owners/groups, substitutions, source
mutation, mount escapes, credentials and incomplete publications refuse. Private
group metadata is allowed only when that group admits the caller and root.
Sources remain unchanged; sharing retains the raw-export privacy restriction.

Only recursively selected directories freeze their membership and content
metadata. Ancestors used to reach selected proof retain strict identity,
ownership, permission and mount checks, while unselected sibling writes remain
allowed. Live launcher chat/checkpoint updates and worktree propagation can
therefore coexist with publication without invalidating unchanged proof. Selected
file/tree mutations and ancestor substitutions still refuse.

For an explicit validation boundary, append `--defer-cleanup` to export. Inspect
the returned bundle, finish the required safety checks, then run:

```sh
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts bundle-finish
```

This re-verifies the committed bundle before deleting only recorded retired
exports. Interrupted commit/cleanup resumes through the same maintained route;
an unsafe replacement or corrupted committed payload stays preserved and refused.
`bundle-finish` accepts no caller-selected path. For a preparing interruption,
use `pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts bundle-recover`.
This removes only its recorded incomplete staging allocation and preserves every
prior export; a committed interruption instead verifies the bundle before
finishing recorded retirement. Then inspect a fresh plan and retry export.
Ordinary plan/inspection refuses the pending transaction rather than rotating it.

### Manual entry points

Keep the checkout and VS Code workspace on the host. Unit/UI/host launchers
continue to run locally. After the ordinary online `tools/prepare-appsnapshot
--vm NAME` workflow leaves an owned running guest, investigate its OS as root
from the host terminal:

```sh
tools/test-vm --vm 'NAME' exec -- 'id' '-u'
tools/test-vm --vm 'NAME' exec -- 'journalctl' '--boot' '--lines=100' '--no-pager'
tools/test-vm --vm 'NAME' exec -- 'systemctl' 'status' 'oh-no-parent-control-broker.service' '--no-pager'
tools/test-vm --vm 'NAME' exec --timeout 600 -- 'sh' '-c' 'id -u; uname -a'
```

Replace `NAME` with the exact configured VM name. `exec` preserves current guest
state, uses the existing root SSH credentials and returns guest stdout, stderr
and exit status. It supports arbitrary guest programs, shells and interpreters;
it provides finite commands rather than an interactive shell. `--` separates
guest arguments from host options, including guest `--vm`/`--help` arguments.
Use `tools/watch` for the shared live screen and filtered command transcript.
The existing detached display observer remains attached when probes finish.
An active test controller, unowned guest or unavailable current online snapshot
credentials cause refusal. A baseline-only `tools/test-vm start` does not provide
app-snapshot credentials; use the existing online app preparation workflow.
Collect needed logs before an explicit restore. Provision the host route and
missing SSH client only through `./setup.sh --test-tools-only`; full setup also
includes it. No source mount or VS Code remote backend is involved.

When changing a concrete dangerous cleanup operation, select the existing
regression at its shared ownership boundary under the
[test scope mandate](../docs/Mandates/Test-Scope-Mandate.md). A new controller
or consumer does not require its own unit suite or repeated cleanup matrix.
New unit tests for non-product recording, viewer, fixture and oracle code require a specific request.
Unchanged cleanup implementations need no prerequisite regression run before
ordinary product tests. The validated category launchers retain live ownership
and recovery checks without launching additional test suites.

Changes to graphical ownership or descriptor transfer use the existing shared
regressions in `tests/unit/test_graphical_lease.py`. They cover
VM ownership refusal and real display descriptor transfer/revocation. The
worker's existing owner is `tests/unit/test_graphical_worker_cleanup_safety.py`;
ordinary adapter or worker changes do not automatically require these checks. The privileged
integration dispatcher executes only the requested operation.
`integration check_graphical_worker` has non-VM fixtures that verify byte transfer,
normal exit, controller disconnect, and forced supervisor interruption. This
qualifies namespace containment, not the actual os-autoinst/VM integration.

Signal only explicitly spawned, identity-recorded processes. Never infer
ownership from names, environment variables, runtime directories, a host-wide
process scan, or a guessed ancestry relationship. A reused identity must be
refused, not cleaned up. Preserve failed evidence and source logs.

## Local component work

Use `make check-component` for the current component aggregate after its safety
prerequisites. For a focused non-VM UI run, invoke the launcher directly:

```sh
tools/run-ui-tests --timeout 360s tests/ui/test_child_shell_lifecycle.py -q
tools/run-ui-tests --timeout 180s tests/ui/test_request_form_component.py -q
```

Do not inline the launcher's environment or invoke it through another shell.
Both kiosk and child-overlay parameter values remain required for shared-form
changes. Use meaningful accessible names and visible state; do not replace
behavioral tests with checks of widget internals or source strings.

The isolated Dogtail environment is declared in
[ui/requirements.txt](ui/requirements.txt); host tooling comes from
[test-tools-ubuntu-26.04.txt](test-tools-ubuntu-26.04.txt) and `setup.sh`.
Keep versions/hashes there rather than copying dated package tables into docs.
Nested-Shell tests reuse `child/preview-orchestration.sh`, a controlled copy of
the packaged extension, and private runtime state. They must not change the
developer's desktop, extension settings or live source. Preview launchers are
development tools, not customer E2E commands.

### Watching host UI tests

Open `tools/watch` (or `make watch`) as the desktop user before or during a run.
Both return after launching and repeated launches present one watcher for the
desktop user session, including launches from other checkouts. Bottom tabs show
**All** and each checkout's current Git branch name, in fixed discovery order.
The bottom **All** tab divides the left terminal panel into equal vertical
sections for branches with active runner output, in bottom-tab order. Each
section has one bold title combining the branch and terminal status, such as
**[main] Terminal Outputs -- fix-tests**. Sections appear and disappear as runners
start and finish; when every runner is idle, the last finished terminal remains.
Click a terminal heading to open its branch tab. An individual branch tab shows
only its own terminal. Finished tabs retain their output and remain selectable.
Related Git worktrees on named branches are discovered automatically; detached
snapshots appear only when `tools/watch` is launched from that checkout. Launch
`tools/watch` from an unrelated checkout to add it to the same window. Branch
names update after Git branch switches; checkout paths identify separate tabs
even when labels match.
The footer's right-aligned resource line refreshes every second with host CPU,
memory and disk activity percentages. Fixed-width percentage fields keep labels
and separators stationary as values change; labels are bold and values use normal
weight. Disk follows Resources' Drive Activity
calculation (the greater of read and write time over the sample interval),
showing the busiest physical disk and excluding partitions and virtual mappings.
Unavailable measurements show a dash until a valid sample is available.
The left terminal follows active VM `fix-tests`, then host `fix-tests` output before `run-tests`,
using VS Code Light+ colors, wrapping and vertical scrollback. The left panel
has **Run Status** and **Session** tabs below its heading separator.
Run Status keeps the live pipeline dashboard and test output. Session embeds the
shared [session panel](../tools/launcher_session.py), following the active agent
in that checkout, including VM repair pipelines and plan launchers. Its transcript,
scroll position and draft are independent of Run Status. Interactive sessions
support the existing prompt, interruption and continuation controls; batch repair
sessions retain their developer-decision input. Without a live workflow session,
the tab shows an empty-state message. Input is checked against the displayed
owner and session before delivery. Newly started supervisors publish these session
artifacts; already-running supervisors keep their existing output until restarted.
The initial
horizontal split is 25%/75%, adjustable by dragging. The right viewer has one
flat tab row: **All**, **[branch] UI - category** for each active UI worker
category, and **[branch] VM name** for each registered VM, for example
**[main] onpc-Ubuntu26.04**. UI and VM tabs share the same prefix in every scope.
The prefix follows the source checkout and updates when activity moves to
another worktree. Each VM has one tab in the bottom
**All** scope, using the checkout with its current controller or running display.
Idle VM tabs in the combined scope come from the watcher's initial checkout's
current registry. Other worktrees' retired names remain available in their own
branch scope and appear globally only while they have live activity. Registry
name/ID changes update the existing viewer without restarting it; a removed
selected VM tab returns to **All**. Registry reads share the background checkout
discovery worker and never block GTK rendering.
Its viewer **All** tab puts active viewers in one flat grid ordered by bottom
branch and UI category name, followed by VMs in ascending numeric configured ID
order. Legacy VMs without IDs follow in registration order. VM tabs use that
same order, and each tile title exactly matches its tab header.
One cell fills the space; additional cells use two columns with as many
rows as needed, leaving the right cell blank on an odd final row. Cell titles
match their top tabs. Large grids scroll vertically at their minimum cell size.
Double-click a cell to open its individual top tab while
keeping the current bottom branch scope. UI categories and VMs share this grid;
there is no nested UI tab row or separate UI/VM split. Viewer activity is
independent of terminal activity. Locked VM tabs appear normally; unlocked VM tabs are gray and
remain selectable, including running guests left idle between maintenance
commands. The controller publishes that state through the read-only feed;
the viewer never acquires a VM lease. Neither launcher accepts a VM parameter.
The lease keeps one authenticated display feed connected through guest shutdown,
snapshot restoration, offline inspection and gaps between steps. It shows the
current operation while no guest display exists and attaches each newly guarded
display to the same feed. The feed ends after the exclusive VM lock is released.
The viewer clears the screen when the VM is off. Serial archive controllers
publish their operation to each selected VM, including after queue-wide
validation before the first VM is bound.

Each VM's transport runs in its own worker with bounded latest-frame queues.
Socket waits and shared-memory reads stay outside GTK and cannot block another
cell. The grid renders at up to 10 fps per VM; an individual VM tab renders at
up to 30 fps. Hidden panels inspect metadata twice per second and do not copy
frame pixels or update widgets. Display and progress registrations are separate
for each VM, and old controllers retain a compatible single-registry fallback.
The viewer discovers
private UI workers from each checkout for both `tools/run-ui-tests` and all
aggregate paths (`tools/run-tests ui`, `host`, `all`, and mixed selections).
Each UI cell and its individual tab show the current pytest node ID and phase. Workers
appear when their private compositor fixture starts, disappear on shutdown or
expired heartbeat, and later workers reconnect automatically. The viewer may be
opened, closed, resized or reopened without controlling the tests. Runs started
before this feature was loaded need to finish and start again to publish frames.
The detached service records Python and native GTK output in a retained
`onpc-watch-viewer-*/viewer.log` allocation under this checkout's test storage.
Its location is printed in the service journal. Close and reopen the viewer to
load source changes. VM display, progress and command publications carry their
checkout identity, so activity appears in the checkout that started it. Already
running controllers without that metadata remain visible in the watcher's
initial checkout until they finish. The viewer does not create runner state,
consume results or change test ownership. Ctrl+C and **Stop command** retain
the displayed runner's cooperative cancellation route.

The shared [fixture](ui/conftest.py) owns an optional
[collector](../tools/ui_watch_capture.py) and private PipeWire/WirePlumber
policy services. Capture uses Mutter 50's existing monitor through ScreenCast,
as permitted for the development preview; it creates no monitor or input session.
The unprivileged per-checkout registry is user-private. Spectators receive only
sealed read-only frame memory, never test buses, input handles or process controls.
Publication is bounded to ten updates per second, with no reader backpressure.
Display changes may interrupt PipeWire capture. The collector clears the old
image and reconnects its capture session, preserving the worker tab and grid
cell. Recovery is limited to three retries within a 15-second outage window.
Teardown sends an [out-of-band flush](https://gstreamer.freedesktop.org/documentation/gstreamer/gstevent.html#gst_event_new_flush_start)
to unblock streaming before stopping the pipeline during concurrent PipeWire
buffer removal. Reconnection clears published pixels before teardown. The scale
regression requires a frame from a replacement capture generation after both
applying and restoring the scale, retaining the worker identity throughout;
a later timestamp from the outgoing stream is not recovery evidence.
Capture failure is reported in the viewer when publication is available, with
diagnostics at the printed `onpc-ui-watch-*/capture.log` allocation. Earlier setup
failures are reported by the runner. Optional observation never retries a test
action or changes test outcomes. Owned collector/service cleanup still runs.
Frames are review aids, never automation targets or acceptance evidence.

Activation is `none`: new test fixtures and viewer invocations load the source;
no product package, service or data migration is involved. The existing
`./setup.sh --test-tools-only` route installs the optional viewer desktop/icon
identity, and the existing executable-tool discovery includes `tools/watch`
at the next rules refresh. No broader command or privilege grant is needed.

The bare-Mutter fixture disables its opening-window scale effect through
`MUTTER_DEBUG_DISABLE_ANIMATIONS`, the upstream default plugin's test switch.
Automation nevertheless reacquires controls by public ID and verifies semantic
readiness after transitions. Product UI and E2E coverage use the shared
[Application UI API](../docs/TestAutomation/Application-UI-API.md) facade,
canonical values and ordinary control handlers. Allowance selection uses
`setValue` on `parent-daily-limit-selector`, followed by independent saved-value
readback. Custom entry uses `setText` and normal activation/validation;
popup rendering, focus, key injection and menu placement are not prerequisites.
Preview process logs use private `onpc-ui-preview-<run>/` allocations printed by
the fixture. Capture, previews and render diagnostics use the shared disk-backed
allocation and retention routes in the
[storage mandate](../docs/Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes).
Legacy `/tmp` or `/var/tmp` arguments to the shared allocator are redirected;
use the printed allocation path to inspect evidence. Fixtures preserve their
logs; later retention follows the
[aggregate policy](#aggregate-output-retention).

Host pytest launchers set `TMPDIR` through shared owner-locked scratch for capture
and temporary fixtures. The retention repetition test covers pass, failure and
interruption across 100 real-filesystem iterations each, checking fewer than
64 entries and 256 KiB of file contents at every iteration. Ordinary `tmp_path`
checks retain disk-backed journal sync ordering, write-failure propagation and
evidence preservation. The legacy
[`repetition_tree` fixture](unit/test_test_retention_cleanup_safety.py) still allocates
directly under `/tmp`; migrating it to the mandate's shared fixture route remains
required. Preserve all iterations and footprint assertions during that migration.

[The preview boot helper](support/preview.py) scopes tempfile's default to `/tmp`
only while Dogtail boots its private graphical runtime. WebKit creates
`/var/tmp` as a symlink inside its sandbox, so placing `XDG_RUNTIME_DIR` beneath
that path causes sandbox startup to abort. The runtime keeps its existing owned
teardown; no sandbox protection is disabled. Success, failure and interruption
restore pytest's disk-backed default. See the
[upstream sandbox layout](https://github.com/WebKit/WebKit/blob/main/Source/WebKit/UIProcess/Launcher/glib/BubblewrapLauncher.cpp).
This legacy Dogtail boot route and its [observer ownership check](support/ui_watch.py)
still require migration to the centrally owned short-runtime
helper; preserve the sandbox constraint and owned teardown. The
[socket exception](../docs/Mandates/Test-Storage-Mandate.md#prohibited-storage-choices)
does not provide a separate bulk-evidence route.

Request-layout, allowance and legend images use shared private render
allocations. After setup, assertions and all fixture teardown have passed,
the owning test removes its rendered PNGs and layout JSON. Failed, skipped,
interrupted or teardown-failed attempts keep their images. Input event streams,
preview logs and other diagnostics are preserved. Cleanup never scans old runs
or deletes another worker's artifacts. Nested-Shell tests also discard their
regenerable Mesa/NVIDIA shader caches after successful teardown, retaining
Shell logs and reviewable screenshots. Synthetic E2E preflight assets have an
explicit temporary-directory fixture lifetime, including setup failure.
`test_ui_artifacts_cleanup_safety.py` covers successful/failed teardown,
concurrent attempts, directory replacement and symlink/hardlink refusal.
Private filenames do not isolate storage capacity; retained images must not
compete with runtime sockets on memory-backed storage.
Pytest continues to own its numbered-directory locks and capture files; no
worker deletes another worker's evidence.
Maintainer-script fixtures use `tests.support.shell.relocate_system_paths` to
rewrite only original source matches in one pass. Sequential replacements
corrupt inserted roots containing `/var/` or `/home/`; `test_support_shell.py`
covers those roots and the real package configuration/removal suites exercise
the resulting scripts in launcher-configured disk scratch.
Request-layout checks exercise the shared form at supported display scales
through public IDs, including selected approver, duration, submission and exact
submitted values. Retained rendering artifacts are review evidence, not targets
or acceptance criteria. Missing public IDs and inaccessible controls fail the
consumer; labels, geometry and screenshots cannot substitute for identity.
Launcher storage and immediate fixture-failure cancellation have regressions in
`test_test_launchers.py` and `test_regression.py`. The coordinator latches
cancellation after persisting the first setup/teardown failure, before category
exit, and continues draining owned cleanup output.

Node and GJS checks are available as `make check-child-node` and
`make check-child-gjs`. The latter prints its private
`onpc-gjs-coverage-<run>/` shared allocation containing `coverage.lcov`.
The nested-Shell guardian uses the shared short-runtime helper and removes its
recorded identity after owned descendants settle. The shared lifecycle runner
starts GNOME Shell headlessly with a virtual Wayland output. Panel, reminder,
overlay, language and reload checks use public Application UI values and
lifecycle results; no outer compositor, Devkit viewer, PipeWire capture,
screenshot service or geometry assertion is required. Interactive child previews
retain their visible Devkit viewer and its guarded ownership/cleanup. The
[legacy review publisher](ui/test_child_shell_lifecycle.py)
still copies attempt logs to `artifacts/ui/child-shell/`;
`latest/` is only a convenience copy. Migration of that publisher to shared
disk allocations remains required; preserve each attempt's evidence and avoid
using the convenience copy for another revision or run.

## Property tests, contracts and coverage

The committed `onpc` Hypothesis profile in `conftest.py` bounds deterministic
generated policy/transaction cases. Turn a discovered failure into a permanent
regression example, preserve its reproducer/profile, and check the real invariant
after each state transition. Do not add a production test mode to support it.

Source/configuration contracts protect supported APIs, ownership, packaging and
architecture. Keep them classified separately from executable customer behavior.
A file assigned the `contract` marker does not become runtime acceptance merely
because pytest executes its assertions.

Use `tools/run-tests coverage` for Python branch coverage of the unit and
private-D-Bus component selections. It prints a fresh shared `onpc-coverage-`
allocation containing `.coverage` and `coverage.xml`. The legacy
[`make check-coverage` target](../Makefile) still writes HTML/XML to `artifacts/coverage/`;
its storage route requires migration under the storage mandate. Neither route
reports full graphical/system coverage. Inspect missing paths by security boundary:
caller/target validation, authorization, transactions and rollback, preferences,
migration, enforcement activation and process ownership. A blanket percentage
does not establish those behaviors. Future aggregate evidence must name the
layers actually measured and include the separate child-language results.

## Maintaining regression coverage

### Core installation and runtime compatibility

Changes to package admission, PAM, native executable inventories, trust backends,
provisioning or broker startup must review environment dimensions as well as test
counts. Identify the exact existing installed assertion for each affected result;
missing input variants remain uncovered even when many cases share one baseline.
Unknown or unsafe configurations still require an explicit supported/refused
decision; adding tests does not authorize widening product permissions.

| Dimension | Required distinction and existing owner |
| --- | --- |
| PAM environment | Plain supported stacks and reviewed optional native callbacks, includes/substacks, trusted distro aliases, original local overrides and vendor updates. Host parsing/composition belongs to `test_kiosk_confinement.py` and `test_package_configuration.py`; installed callbacks belong to the first-configuration, confinement and `system_pam_variants.py` environment histories. Verify the effective optional rule, not only its package. |
| Lifecycle composition | Run production migration and confinement together through the real package script with private filesystem inputs. A success stub for every helper cannot establish their composition. Use `tests.support.package_scripts`; native kernel/service tools may remain explicit doubles at host scope. |
| Failure and recovery | Missing/failing policy tools, unsupported control flow and vendor drift must retain broker exclusion, preserve state and avoid success output. A repaired input must permit a normal retry through activation. Existing first-configuration/removal histories own installed interruption and recovery. |
| Upgrade and live dependencies | Fresh installation, unchanged reinstall and actual earlier-package upgrade are separate histories. Record native dependency versions and qualify changed inputs; startup against freshly updated dependencies does not establish replacement while a session is retained. Use the existing upgrade interfaces and confinement replacement/reexec checks. |
| Core customer results | Installation/service readiness is not proof of daily/grant arithmetic, hard/soft enforcement, lock/unlock, multi-session isolation or persistence. Keep their complete installed obligations in the existing E2E inventory/queue; pending journeys remain pending despite component/system passes. |

The core installation queue completed on 2026-10-18 and its temporary launcher,
plan and briefs were retired. Accepted installed histories remain in the existing
system cases; they do not complete pending customer E2E journeys.

| Accepted history | Ubuntu report | Fedora report |
| --- | --- | --- |
| First configuration, case 4 | `20261018T001146Z-fde699d8` | `20261018T001146Z-106f25a9` |
| Native confinement, case 267 | `20261018T001931Z-c3d8d88c` | `20261018T001931Z-3ecc56f3` |
| Earlier-package upgrade, case 287 | `20261018T190013Z-06fb3398` | `20261018T190013Z-480dd9e4` |
| Native dependency update, case 289 | `20261018T221414Z-71987d6a` | `20261018T221414Z-ffdaf92b` |

Both native update phases passed on each target with matching input/helper
bindings, complete cleanup and restored, powered-off VMs. The accepted pairs
were Ubuntu bubblewrap `0.11.1-1` → `0.11.1-1ubuntu0.3` and Fedora
xdg-dbus-proxy `0:0.1.6-4.fc44` → `0:0.1.9-1.fc44`.
The cumulative 4,329-file evidence bundle is retained at
`output/test-runs/host/exports/onpc-evidence-bundle-imeub3ps/evidence.zip`,
SHA-256 `fdbf8cf7e9732308ceee22a720fdaf5df6d0d1b6c0f4b2d5e1916beacbe37df1`.
These receipts describe historical acceptance; later candidates require matching
evidence or the affected complete history again.

### Sealed producer handoffs

Routine reports use their existing registered allocation and bounded retention.
`regression.Report` writes command outcomes, exact selected/resumed/completed and
failed IDs, progress and useful logs. Closing it syncs those files and releases
its owner; it does not build archives, seal proof or publish receipts. Coverage
commands must produce their actual private XML and database results. Report
rotation affects inspection availability, never completed task status.

Normal owned rotation also retires legacy automatic runner archive requirements,
including interrupted or expired publications, without rebuilding them. It still
checks recorded ownership and allocation identities. Explicit archives and
required recording captures retain their own publication guards.

A VM batch launches the selected workers, joins their owned processes and uses
their actual exit status after guarded cleanup. It keeps target-specific logs and
`results.json`; it does not read old worker reports to verify archival claims.
A successful worker's obsolete diagnostic pointer is ignored. Failed-worker
details remain useful diagnosis, without a second proof protocol.

Qualification and recovery sessions keep their selected owner/run guards,
separate journals, private command logs and actual result files. System and E2E
controllers preserve input validation, selected cases, assertions and outer
cleanup. The E2E collector validates only its current private copies and excludes
secrets; it creates no startup/terminal archive or transitive record graph.
Post-cleanup return values and exit status remain authoritative, including late
failures. Normal watch recordings retain their own policy.

The following sealed capture/publication APIs support explicitly requested
archival operations only. Ordinary test runs, preparation, repair and task
progression do not invoke or recover them. A requested archive keeps its identity,
permission and integrity guards; failure of that export does not reopen a
completed task.

`ReportEvidence.finalize` accepts explicit closed members with `path` and `role`,
seals their command/result/input/cleanup records, publishes the selected closure
and acknowledges it under the source owner. Returned references bind workflow,
record, member and closure digest. `runner_evidence.resolve_reference` verifies
an explicitly selected archive under its owner lock. Existing legacy publications
remain readable. Concurrent explicit producers serialize publication and
acknowledgement; source retirement keeps the normal ownership and integrity
guards.

`tools/evidence_capture.py` owns authenticated finalized subsets for evidence
producers. A producer obtains an opaque in-process handle only inside its live
`Store.session`; the held owner descriptor, journal identity, run and newly issued
attempt bind its exact context. Paths, inherited activity descriptors,
`ONPC_TEST_RETENTION`, caller JSON and a nonce cannot issue that authority.
The activity lock remains coordination only.
`issue_session` issues a fresh attempt; `resume_session(store, capture_id)` instead
rebinds an exact retained intent to the same run's newly held owner. A handle
expires with its issuing process/session and cannot turn a retry into the old
attempt.

The producer registers a bounded `required` intent and disjoint sealed slot
before copying its finite finalized allowlist. `sealing` retains the original
identities and exact stage across interruption. Only a separately committed,
finished snapshot owner permits `sealed` inspection while its parent continues
writing other files. Producer-side pinned before/after identities and hashes bind
original provenance to sealed bytes; readers open only the registered snapshot.
Every slot and its recovery metadata count against the parent's existing budget.
Outstanding handoffs prevent source retirement, including ordinary count/size
rotation; creating another subowner grants no additional retention allowance.
Privileged sources commit their private safety witness before caller registration.

The artifact helper registers repeated `--capture` IDs for `bundle-plan` and
`bundle-export`, within the existing 256-selection total. Capture-only planning
opens only those independently finished owners and does not catalogue an active
parent. `bundle-custody --transaction ID --expect REQUEST_SHA256 --operation inspect`
authenticates one exact request without a supplied journal, UID or destination.
Missing, pending, active, foreign, replaced or changed registrations and snapshots
refuse. `bundle-export --capture ID --expect SELECTION_SHA256` publishes the exact
selection through the shared verified bundle transaction. Captures from one
authenticated workflow use its bounded cumulative publication journal, separate
from disposable exports and accepted-plan proof. Each replacement carries the
previous required records. Its matching locator commits before older generations
retire; interrupted copies reuse the exact registered stage and file identities.
Repeated identical requests independently verify and return the existing copy.

`bundle-acknowledge --capture ID --expect REQUEST_SHA256`
records acknowledgement only under a finished source owner. An active producer
uses `evidence_capture.acknowledge_capture(..., session_handle=HANDLE)` with its
issued live handle. Both routes independently verify the destination's complete
logical closure, request, attempt and original identities before recording custody
in the source journal. The helper accepts no caller-selected destination, owner
or journal. A successful seal, receipt JSON or acknowledgement supplies no test
pass. Source retirement pins and re-verifies the current cumulative replacement,
audits the complete deletion set, and removes only recorded originals and slots.
Pending, changed or missing replacement proof preserves the required source.

`tools/capture_publication.py` owns `capture-publication.json` in that workflow's
existing retention directory. Its published generation is the locator, with a
single pending request/stage/receipt for recovery, rather than a separate index.
Caller-slot `publication.json` contains exactly `schema:1`, `capture_id`,
`request_sha256` and the derived `journal`; this pointer is never authority.
The parent charge's version-1 `onpc-capture-acknowledgement` binds `request`,
`delivery` and the exact `caller_slot` cleanup identity. The private parent record
survives partial source/slot deletion until recorded cleanup finishes. Source,
seal, old generations, staging and control/recovery copies retain their existing
byte, file and metadata limits; capacity refusal preserves prior proof.

P03 lives in `tests/unit/test_evidence_capture.py`, using private synthetic owners
and real storage/retention locks. It covers authority, exact context, immutable
mapping, refusal, bounded capacity and resumable interruption. These are host
infrastructure checks, with no installed-product or VM acceptance credit.
Repeated source-owner reopenings recover the same request, seal and publication
allocation through more than three interrupted transitions. A real failed copy
or acknowledgement capacity refusal keeps the original bytes and dependency
registration through oversized startup recovery; only the matching verified
acknowledgement permits retirement. `tests/unit/test_plan_evidence.py` composes
that handoff with real input capture/carry and serialized suspended checkpoints:
five restarts and unrelated export/source rotations preserve the exact result,
input, command and cleanup bytes, including failed and partial interrupted proof.
These shared-mechanism checks do not replace the producer/consumer integrations
assigned to later export tasks.

Required recordings use the same sealed publication route before latest-only
replacement. `recording_storage.Store.owner()` holds an existing case without
allocating or recovering a recording. Its `require_capture()` requires both that
case lease and a live issued workflow handle; the case manifest records the exact
media and machine-generated origin witness before copying. The complete two-member
diagnostic closure preserves original identities and provenance. Publication alone
cannot release it: `acknowledge_required()` durably records the independently
verified receipt in both owners. Overwrite and unlink pin and reverify that copy.
Failed capture, missing acknowledgement and stale destinations preserve the old
recording. A later requirement waits for ordinary cleanup of the exact previous
parent charge, then removes only its recorded witness. Disposable recordings keep
their existing latest-only policy; producer wiring remains with its owning task.
After interruption, `resume_capture_session()` reissues the declaration's exact
attempt only while its original workflow run and case are held. This also covers
interruption before the parent charge exists; the saved context, consumers and
dependencies supply the recovery inputs. A new attempt cannot replace that
pending declaration. Lost acknowledgement replies retry the same receipt.
Required-recording manifests use the shared evidence metadata bound so valid
consumer and dependency records fit; legacy recording manifests keep their
existing smaller input bound.

### Handling test failures

On resume, reconcile the current working tree, the active runner's actual
selection, and the latest retained category/attempt results with the handoff.
The handoff can predate an already tested correction or a still-running retry.
Attach to a matching run through the maintained launcher and let its cleanup
finish; do not mistake attachment for execution of new arguments. Coordinate
one editor for the same task when another agent is active, including close-out;
the VM lease does not serialize source/document edits. Preserve existing work
and valid results instead of restarting the whole investigation.

Tests protect required behavior and catch regressions. Current app behavior is
not sufficient evidence that a failing expectation is wrong. Investigate the
failure against the authoritative specification/design requirement and any
explicit behavior change authorized in the session.

When a test detects changed app behavior or a behavioral mismatch, preserve the
failure evidence and report a potential regression: identify the test, expected
and actual results, and the relevant requirement. Ask the developer whether the
change is intended before accepting the observed behavior or changing the
expectation, unless that specific behavior change is already explicitly
authorized. Do not weaken, skip, delete or rewrite checks, or alter requirements,
merely to make current app behavior pass. If intent remains unclear, keep the
behavioral failure unresolved while continuing independent work.

Fix mechanical test issues automatically without asking for confirmation when
the evidence shows a defect in test code, fixtures or the harness and the
intended behavior check is preserved. Examples include a broken import, an
incorrect test API call, a harness crash or missing generated qualification
inputs that the maintained builder can prepare under existing authorization.
Resolve these implementation details without a developer question, preserving
existing inputs and validation guards. A product crash, timeout or failed
assertion can indicate a regression; its failure type alone does not establish
a mechanical test issue. Report the cause, correction and verification in the
normal work summary. A test's disagreement with the app alone never justifies
classifying the test as broken.

Classify supporting qualification and feature results separately. A supporting
failure does not establish a product defect without evidence connecting it to
the required product behavior, and it does not erase an independently valid
feature pass. Keep unresolved safety qualification open; a feature pass does
not qualify its harness. Before repairing an incidental dependency, apply the
[product-focused review](../docs/TestAutomation/E2E-Execution-Contracts.md#product-focused-journeys).

Read the failed operation's retained error and independent result, not only a
generic worker/SSH error or its last printed title. A title may precede a failed
exchange. Use the [composition preflight](../docs/TestAutomation/E2E-Building-Blocks.md#composition-preflight)
to distinguish competing explanations and retire disproven repair hypotheses.
A pre-acquisition busy-controller refusal follows the
[VM ownership contract](../docs/Mandates/VM-Mandate.MD#authority-and-operation);
it supplies no product result and does not invalidate independently passed
categories. Once ownership is released and readiness is established, retry only
the unexecuted/failed selection with its original assertions.

### Coverage maintenance workflow

1. Identify the changed behavior and its authoritative specification/design
   requirement, or the necessary harness safety guarantee. Apply the
   [test scope mandate](../docs/Mandates/Test-Scope-Mandate.md) before adding
   coverage or carrying forward an existing matrix. Follow the
   [app scope and prerequisite rules](../docs/TestAutomation/E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope).
   Use supported fixture helpers for unrelated OS/account/asset setup. Add
   regression cases only for required product behavior or an uncovered core
   execution/verdict or dangerous-action guarantee at its shared owner. Apply the
   [result-oriented UI scope](../docs/Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope):
   representative GUI choices and meaningful boundaries verify final functionality;
   pure value combinations belong in lower-layer tests when warranted. Remove
   incidental popup, focus, caret and rendering assertions instead of relocating
   them into UI coverage. Keep real installed/customer coverage for the
   boundaries and causal journeys that require it. App approval denial must
   assert unchanged grants/policy and recovery, not just Ubuntu's error message.
   For every new E2E case and maintenance change, apply the mandate's
   [three review questions](../docs/Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope)
   to steps, observations, prerequisites and acceptance, including shared flows
   and qualification commands. Reject conclusively invalid accounts/ownership
   before unrelated UI discovery; keep that refusal in focused safety coverage.
   Ordinary feature cases retain runtime guards without repeating unchanged
   qualification histories. Reconcile recipes and unfinished consumers under the
   [journey review contract](../docs/TestAutomation/E2E-Execution-Contracts.md#product-focused-journeys);
   remove an unnecessary dependency before adding adapters, retries or timeouts.
2. Classify the tests, their affected components/shared dependencies, runner,
   environment and safety prerequisites. Add them to the authoritative suite
   inventory when implemented; they must not be silently absent from `test-all`.
3. Maintain stable `ONPC-...` IDs and `requirements.json`. Run
   `tools/run-tests traceability stage` after specification
   or mapping changes. Current file-existence validation is structural; only
   actual executable evidence justifies `covered`. Supporting contracts cannot
   satisfy a required runtime layer.
4. For graphical work, enumerate and implement the applicable variants under
   [scenario decomposition](../docs/TestAutomation/E2E-Building-Blocks.md#complete-scenario-decomposition)
   and [scenario inventory](e2e/scenarios.json). Record the complete journey,
   real actions and visible results, including other-user surfaces when applicable.
   Keep internal fault qualification in its separate test layer.
   A passing fragment is not a full journey.
5. Run the relevant verification once per ordinary attempt, with bounded waits
   and preserved first failures. Repeated harness qualification is explicit
   maintenance work, not a permanent multiplier in daily commands.
   During implementation, use focused selections and run common checks after
   the stable batch's final edit. Full task verification is an acceptance step,
   not a loop after every diagnostic change. Register canonical cases once
   even when several requirement/task IDs use them; retain every required layer.

Feedback component tests use a fake delivery transport and do not send mail.
Their evidence cannot prove external delivery. Any live delivery test must
declare the actual service, explicit authorization and dedicated test recipient;
never send automated customer journeys to a production support inbox or label
a fake transport as real delivery. The scenario inventory and final audit must
state this boundary explicitly rather than hiding missing external evidence.

Reusable VM/package fixture interfaces are in the
[installed runner guide](integration/README.md). The
[E2E building blocks](../docs/TestAutomation/E2E-Building-Blocks.md) track
unfinished automation, not daily procedures.
