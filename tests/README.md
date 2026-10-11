# Test maintenance

Start with the [documentation map](../docs/TestAutomation/README.md) for ownership
and customer validation design. This document describes how to select and maintain tests;
it does not repeat completed setup tasks or historical acceptance results.

Use the section for the selected operation; an ordinary focused check does not
need the launcher implementation or retention details below.

| Operation | Read |
| --- | --- |
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
Cleanup is a lightweight serial ownership/recovery preflight before parallel
work. It runs no regression tests and has no host branch or cleanup join stage.
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
Unknown modules run exclusively as a runtime safeguard. Reviewed full
application-fixture construction runs as a separate unit-test job using artifact
build resource admission and compatible companions, rather than ordinary unit
packing.
This selection adds no other categories or cleanup prerequisite inventory.

Unit file/case selectors, `-k`, `-m` and scoped ignores preserve the exact
collected IDs, and each worker must account for every assigned case once.
`-x`/`--exitfirst` and positive `--maxfail` keep one serial invocation so the
failure limit remains selection-wide. `tools/run-unit-tests` remains the direct
serial route for narrow iteration or diagnosis. Its execution output also appears
in the left terminal of `tools/watch`, using the shared reconnectable session and
cooperative cancellation. Inspection/collection-only
commands keep their existing behavior. Unit buckets use the same CPU, memory,
swap and compatibility limits as other host work; I/O pressure is advisory for
ordinary units, while full fixture construction retains artifact I/O limits.

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
`fix-tests` and `write-e2e` share the VM queue through
`run-tests`.

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
script reruns that category with `run-tests --resume`, retrying the repaired case
and remaining cases without repeating its completed passes. Failures without a
case ID replay the original category selection without saved passes, including
diagnostic execution and its subsequent repair verification. Each newly entered
category and each fresh verification pass starts without `--resume`.
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
`--vm`, `--model`, `--effort`, `--rounds` and `--stop` remain launcher-owned,
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
Attach or cancel with the same scope, for example `tools/fix-tests host --stop`
or `tools/fix-tests vm --vm NAME --stop`. No categories select the VM namespace.

The launcher itself is Python scripting. New runs validate the selected model
and effort against the Codex CLI catalog before testing. Classification and
proven mechanical test repairs use **GPT-6.1 Sol Medium** in one session,
or **GPT-6.1 Sol Low** for unit failures.
App issues, uncertainty and unresolved security, concurrency, ownership or
difficult diagnosis end that session without edits and transfer to a fresh
**GPT-6.1 Sol High** session to recheck and repair, or **GPT-6.1 Sol Medium**
for unit failures. This raises reasoning effort
at the judgment boundary without paying for an additional adviser and a second
implementation context. Delegation stays disabled; classification is not an
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
`--resume`, a new run starts from its first category. Both paths use fresh case
budgets without loading old repair conversations; new verification rounds still
execute the complete requested selection. After a repair within verification,
the next clean pass clears previous category completions before queuing work;
an interruption can resume only that pass's completions.
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
`codex exec --ephemeral`, disabled conversation history and memories, and receives
the latest failure handoff. The script never resumes or forks a session; the app
review receives the latest failure handoff, classification or repair summary and applicable
developer answers. An answered blocker also supplies its latest repair handoff.
The [official noninteractive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
defines the ephemeral invocation. Existing CLI authentication, configuration,
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
retention policy. Machine-readable `failure.json` accompanies the printed prompt
and supplies stable retry category IDs. A missing or malformed handoff, agent
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
tools/write-e2e --vm NAME --sessions 3 --tasks 1
tools/write-e2e --vm NAME --tasks 2
tools/write-e2e --vm NAME
tools/write-e2e --vm NAME --stop
```

`--sessions N` limits the total number of new sessions across implementation,
live verification, retries, optimization and subsequent tasks. A new run with no options
defaults to 5 sessions and 1 completed task. A new run with `--tasks N` but no
`--sessions` has no total session limit. Each task can use at most 5 sessions
per new launcher process. A restarted launcher retains the task's cumulative
session count and adds 5 to it for that process's task cap. Attaching to a
running launcher does not renew the cap. If the task is still incomplete at
that cap, the entire launcher exits with failure and prints a bold
red warning as the final line after the summary and follow-up instructions.
The next task starts with its own cap of 5.
`--tasks N` limits completed tasks and defaults
to `1`. Both limits accept positive integers for a new run; the launcher stops
when either limit is reached. A task counts only after acceptance, queue
close-out, successful staging, its completion commit and `git push`. An empty active
queue stops the workflow. A task blocker pauses for your answer as described below.
With a live run, an invocation without
parameters attaches without changing limits. Explicit `--tasks` and `--sessions`
values are signed adjustments to the existing maxima: `--tasks 2` changes a
maximum of 1 to 3; `--tasks -1` changes 2 to 1. Omitted limits stay unchanged,
and an unlimited session maximum becomes sessions already started plus N.
Adjustments accumulate across terminals
and clamp at zero. They take effect before the next session; the current session
finishes normally and completed work is preserved. Invalid options are rejected.
An owner already finishing at its limit refuses adjustments; restart after it exits.
Workers started before adjustable-limit support require a restart to accept changes.
Closing the terminal detaches. Another invocation attaches to its styled output,
using the same compact session transcript as `fix-tests`: agent messages,
commands and their results remain visually separate, including without color.
`--stop` finishes the current session, including test cleanup and its handoff or
task close-out, then starts no further session. Ctrl+C cancels immediately and
waits for owned cleanup.

After each completed task, the launcher stages its owned paths and commits them
as `TA: Completed task ID`, then runs `git push` before selecting another task.
The push uses the checkout's existing Git remote and branch configuration.
Git uses literal paths
and `commit --only` so unrelated staged files remain outside the commit. Agents
return explicit owned paths and never commit themselves. A path overlapping
pre-existing staged work refuses close-out rather than committing that work.
A staging, commit or push
failure retains the accepted result; restart retries close-out without repeating
valid acceptance. Commit intent is checkpointed before Git writes. Recovery
recognizes only the matching immediate commit with unchanged owned files, avoiding
a duplicate after interruption; an unexpected HEAD or changed files refuse.
Push recovery retries the push after recognizing the existing commit.
Missing Git identity, remote/upstream configuration or a failing Git hook remains
an actionable close-out failure; the launcher does not change Git configuration
or bypass hooks.

Every **three accepted and committed tasks**, a fresh **GPT-6.1 Sol High** session
runs before another queue task. Its scope is the batch's exact three completed
queue IDs, displayed as the actual first-to-last ID range (IDs may have suffixes
or inserted prerequisites). It analyzes evidenced lessons from successful work
and merges useful guidance into the owning instructions/mandates without
duplicates. It also audits the batch's delivered or affected ready E2E cases:
cases compose shared building blocks, harness and libraries with finite case
data, ordering and assertions; one-off mechanics move to their reusable owners.
It preserves behavior, qualifications and guards, completes affected validation
and resource review, then the launcher stages the fix and commits it as
`TA: Refactored task FIRST to LAST`, then runs `git push` through the same
resumable close-out. A verified audit with no needed edits still
gets an empty checkpoint commit. Optimization cannot close or reorder queue rows.

The existing retained checkpoint owns pending batch IDs, the last optimized batch
and commit, and any active optimization handoff/commit intent. It survives
separate launcher runs, prerequisite suspension, stops and interruptions.
Tasks predating this policy are not retroactively counted. Optimization uses the
session budget and its own five-session cap, renewed on restart; it does not
count against `--tasks`. A due optimization runs even after the task limit, while
`--sessions`, stop and cancellation can defer it. Restart performs the due work
before another task, including when the active queue is empty. No parallel or
adviser agents run during optimization. A blocked optimization uses the same
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
Astra is prohibited for all `write-e2e` work and consultations.
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
directly, with delegation disabled; do not add an adviser or hand the repair
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
Consultations are part of the coordinator session, not extra `--sessions` units;
they still consume model usage. Do not introduce parallel agents or overlapping
coordinator work. `fix-tests` keeps delegation disabled.
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
inputs. Integration qualifications using `named_input()` register automatic
preparation in `tools/test_commands.py`; launcher coverage discovers consumers
independently so new wrappers cannot silently omit preparation.
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
   `tools/prepare-appsnapshot --vm NAME --y --mode online --overwrite false`,
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

Each session is a new `exec --ephemeral` process with history and memories
disabled. Only the latest standalone handoff crosses sessions. Existing CLI
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
All three launchers use its two-pane terminal display and the same output-following
loop. The upper pane pins the controller journey: `run-tests` shows the selected
category and position with overall progress; `fix-tests` adds the current round number and
the running-tests/fixing-errors status; `write-e2e` shows the task ID/title and
the session's implementation, recovery or numbered live-test phase, followed by
the model and reasoning effort selected for that session. Category and
session transitions update immediately. Routine overall counts refresh at most
once every five seconds, while detailed test progress and agent output continue
in the lower pane. Child output cannot move the cursor into the upper pane.

Ordinary VT terminals have no independent pane scrollback, so the upper pane
keeps the latest two major steps, with the newest always visible. Consecutive
steps share an identical leading heading once, retaining their distinct session
lines; hiding the older step restores the newest step's full heading. Header text
wraps to the observer's current width; older steps yield space first when the
terminal shrinks. A terminal too small for even the newest step plus an output
row clips the header until enlarged, staying on the alternate screen. Pipes and dumb
terminals accumulate plain output. Reconnection restores the latest controller
steps separately from the output tail. The live terminal retains a bounded
transcript on the alternate screen. On exit it restores the original screen,
cursor and input modes, then appends the latest controller steps and retained run
log to ordinary terminal scrollback. This includes cancellation, exceptions and
default termination signals (HUP, TERM and QUIT); SIGKILL cannot run terminal
cleanup. Replay uses the run log rather than the bounded live pane, and leaves
existing shell history intact. Full output remains in the existing run log,
subject to its storage limits. `run-tests` preserves its detailed dashboards when observed
through a workflow launcher, below that workflow's controller summary.
Mouse capture is off by default: plain dragging selects text and right-click
uses the host terminal's configured behavior, including VS Code's context menu.
The divider shows `m: scroll`; press `m` to enable pane clicks, wheel scrolling
and scrollbar dragging. The scrollbar is shown only in this mode, and the
divider changes to `m: select text`. Press `m` again to restore native selection
and menus. Mouse reporting applies to the whole terminal, so plain native
selection and scrollbar dragging use separate modes. Use Up/Down or Page Up/Page Down to scroll,
Tab to switch panes (initially the lower pane), and End to return to the newest
rows in either mode.
The shared [detached launcher module](../tools/detached_launcher.py) owns
workflow attachment, process supervision, fresh Codex transport, log rotation
and output following for `fix-tests` and `write-e2e`; `run-tests` shares its lock
primitives, output following and terminal display, and registers test owners
started inside an E2E agent session.
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
may overlap units, components, request behavior, screen fidelity and artifacts.
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
one bucket so its stable latest-evidence paths have one writer. Accessible
adapter and E2E spectator are separate parallel buckets: the adapter uses private
compositors, buses, settings and attempt artifacts (including its Shell search),
while the spectator uses process-local frame memory and per-test output. Host
aggregates and focused UI runs exclude `live_e2e` checks consistently during
collection and execution. Those checks belong to VM acceptance and are outside
the host-only UI category. Both host spectator buckets retain UI resource
admission and exclusion from publishing.
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

Artifact exports also use a bounded journal: each export starts a retention
session, so exporting the same report repeatedly can evict a different report
still needed for close-out. Reuse an existing retained export, preserve required
reports before their execution journal rotates, and verify their actual paths
after the final export/preparation/check. A remembered export path is not a
retention guarantee; see [artifact access](#prompt-free-test-artifact-access).

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

Host-only runs use `output/test-runs/host/state/retention-host/`; VM-containing runs and
snapshot preparation keep `output/test-runs/host/state/retention/`. Each journal retains
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
work must declare its lifetime and include first-run, unchanged-repeat, owned-update
and interrupted-retry checks for baseline reconciliation. See the
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
unfinished E2E plans, not completed lower-level tests. Keep all established
regressions and applicable safety execution intact. Customer E2E uses real
actions and visible results; mechanical installation/upgrade/removal retains
its internal checks. Pending legacy E2E declarations require scoped adaptation
with their first consumer, not deletion or weakening of existing unit/component
or system coverage.

| Location | Purpose | Real dependencies and isolation |
| --- | --- | --- |
| `tests/unit/` | Policy, arithmetic, property/state-machine, adapters, storage, migration, build, runner and source-contract regressions. | Host-safe; controlled doubles are allowed. Tests that launch fixtures still obey process ownership. |
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

Full `./setup.sh` and `--test-tools-only` both maintain graphical AppArmor policy. Classic VS Code
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
prints a new `output/test-runs/host/exports/onpc-artifact-export-*/<original-name>`
path, subject to bounded export retention. Its directory is
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

When changing a cleanup implementation, validate its cleanup-safety regressions
explicitly during development. They are not runtime prerequisites. For example,
this selection covers UI, nested-Shell, VM controller and persistent caller paths:

```sh
tools/run-unit-tests \
  tests/unit/test_ui_cleanup_safety.py \
  tests/unit/test_child_preview_cleanup_safety.py \
  tests/unit/test_prepare_baseline_cleanup_safety.py \
  tests/unit/test_system_runner_cleanup_safety.py \
  tests/unit/test_system_caller_cleanup_safety.py \
  tests/unit/test_system_agent_cleanup_safety.py -q
```

For a focused test, select the safety modules for every cleanup implementation
it uses. New controllers must add their own ownership regressions. The validated
category launchers perform live ownership and recovery checks without launching
additional test suites. Full unit/host/all selections retain the regressions.

Graphical adapter changes additionally require explicit validation with
`tests/unit/test_graphical_lease.py`. It covers
VM ownership refusal and real display descriptor transfer/revocation. The
worker adds `tests/unit/test_graphical_worker_cleanup_safety.py`. The privileged
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
section has a bold branch heading. Sections appear and disappear as runners
start and finish; when every runner is idle, the last finished terminal remains.
Click a terminal heading to open its branch tab. An individual branch tab shows
only its own terminal. Finished tabs retain their output and remain selectable.
Related Git worktrees are discovered automatically; launch `tools/watch` from an
unrelated checkout to add it to the same window. Branch names update after Git
branch switches; checkout paths identify separate tabs even when labels match.
The left terminal follows active VM `fix-tests`, then host `fix-tests` output before `run-tests`,
using VS Code Light+ colors, wrapping and vertical scrollback. The initial
horizontal split is 25%/75%, adjustable by dragging. The right viewer has one
flat tab row: **All**, **UI - category** for each active UI worker category,
and each registered VM's name. In the bottom **All** scope, category
tabs are prefixed with **[branch]:**. Each VM has one tab in the bottom
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
restore pytest's disk-backed default ([regressions](unit/test_support.py)). See the
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
recorded identity after owned descendants settle. Its
[legacy review publisher](ui/test_child_shell_lifecycle.py)
still copies attempt logs and screenshots to `artifacts/ui/child-shell/`;
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
   requirement, or the necessary harness safety guarantee. Follow the
   [app scope and prerequisite rules](../docs/TestAutomation/E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope).
   Use supported fixture helpers for unrelated OS/account/asset setup. Add
   regression cases at the lowest effective layer. Apply the
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
