# Test maintenance

Start with the [E2E building blocks](../docs/TestAutomation/E2E-Building-Blocks.md) for customer validation design. This document describes how to select and maintain tests;
it does not repeat completed setup tasks or historical acceptance results.

Use the [shared support guide](support/README.md) before adding fixture code.
It maps existing broker, D-Bus, preview, package, VM and E2E helpers to their
contracts. Reusable code belongs in support modules, not collected case files.

For unfinished implementation, follow the
[E2E building blocks](../docs/TestAutomation/E2E-Building-Blocks.md): read the
active problem and relevant code, prove one real helper path, then batch its
cases. Report results and retain runner artifacts before moving to a different
problem. A fresh chat does not require rerunning unaffected tests.

## All established regressions

Every test execution through `tools/run-tests` uses the same live dashboard and
final summary: category results, actual host branches and joins, durations and
overall wall time. Only selected categories appear; unused branches are omitted.
The `Overall` counts and percentage exclude cleanup safety prerequisites in both
`tools/run-tests` and `tools/fix-tests`. Cleanup retains its own progress rows,
and its failures still fail the run; overall wall time includes cleanup.
For example, `tools/run-tests unit -k 'grant' static shell` runs the selected unit
tests followed by shell checks in one report. Each category keeps its own
arguments, and all selections are validated before execution. Arbitrary category
groups run in order; unit/UI selections and the established aggregates use their
qualified parallel schedules.
Help, listing and collection-only commands keep their inspection output and take
one category at a time. `tools/run-tests --help` prints usage, including how
the `all` aggregate breaks down into separately runnable pieces. `tools/run-tests --list`
prints the ordered JSON granular inventory. Each entry has a `description` and
an explicit `args` array; executing each entry with those arguments covers the
same suites as `all`. It starts with unit and UI and ends with system and E2E.
Raw test output remains in the linked report streams.

Readiness and leaf/composite status are registered with each command in
`tools/test_commands.py`. New implemented leaves join the inventory and the
aggregate automatically; pending commands join when their registration becomes
implemented. Display names and retry handoffs do not require a second registry.

The inventory excludes composite aliases (`host`, `all`, `check`,
`component-all`), focused/instrumented repetitions (`traceability`, `coverage`),
fixture-building helpers and named integration/recovery operations. These remain
available in the separate helper section of `--help`. Traceability is included
in source checks; package artifacts include the fixture payload. Bare
`tools/run-tests artifacts` now performs two fresh builds and their
reproducibility comparison, matching the granular artifact category in `all`;
`artifacts build` still requests just one build. UI's explicit inventory arguments
select the aggregate's non-live scope; the shared launcher applies that same
host-only boundary to focused UI commands. Mandatory cleanup prerequisites
and required package inputs still run wherever the selected suite needs them.

The complete partition is **host + system + e2e = all**. Combine any of these
categories in one invocation; execution always orders host first, then system,
then E2E. For example:

```sh
tools/run-tests host
tools/run-tests system e2e
tools/run-tests e2e
tools/run-tests host system
tools/run-tests host system e2e
```

`host` includes discovery, isolated cleanup prerequisites, unit, component, UI,
fixture runtime, source/traceability, static, child Node/GJS, backend checks,
publishing checks, two fresh package builds and reproducibility comparison.
It uses the complete aggregate's existing four-branch scheduling and stops at
**Join host branches**, without VM discovery, authorization or execution.
If unfinished prior work requires VM recovery, `host` refuses and preserves the
evidence rather than touching the VM.

For routine Codex validation, preserve the scope justified by the change:
prefer `tools/run-tests ui` for UI-only checks and `tools/run-tests unit` for
unit-only checks, retaining any required file/case selectors. Use existing
launcher parallelism wherever supported within that selection. Do not expand
to `host` merely to accelerate a large suite. Direct unit/UI launchers remain
appropriate for narrow iteration or diagnosis.

`tools/run-tests ui` collects only its selected UI inventory, completes the
mandatory isolated cleanup prerequisites, then runs the existing
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

UI is a host-only category. Its shared launcher always excludes VM-dependent
`live_e2e` checks, including for focused marker or file selections. Direct
`tools/run-ui-tests` applies the same boundary and remains the serial narrow-check route. This development
tooling refactor activates on the next checkout launcher invocation (`none`);
it changes no installed helper, product service, or saved data.

`tools/run-tests unit` collects only the selected unit inventory and balances
reviewed modules across up to four branches. The [unit buckets](../tools/regression_unit.py)
are shared with `host`; each module and its fixtures stay in one worker. Workers
use private pytest temporary trees, disabled shared caches and process-local
doubles. Package/native fixtures build into private staging directories.
New/unreviewed modules and full application-fixture construction run exclusively.
This selection adds no other categories or cleanup prerequisite inventory.

Unit file/case selectors, `-k`, `-m` and scoped ignores preserve the exact
collected IDs, and each worker must account for every assigned case once.
`-x`/`--exitfirst` and positive `--maxfail` keep one serial invocation so the
failure limit remains selection-wide. `tools/run-unit-tests` remains the direct
serial route for narrow iteration or diagnosis. Inspection/collection-only
commands keep their existing behavior. Unit buckets use the same CPU, memory,
swap and compatibility limits as other host work; I/O pressure is advisory.

`system` and `e2e` remain sequential VM categories. A combined run shares one
report and reuses host's qualified package. Without `host`, the runner builds one
required package input automatically. After running host and E2E, only system
remains. Focused category commands remain available for diagnosis; they are not
additional phases of `all`.

`host-builds` remains a compatibility alias for `host`. Its `--serial-builds`
option runs publishing/builds after the host join for scheduling comparisons.

Complete categories and aggregates stop at the first reported
failure by default, with the same cooperative cleanup, final evidence and failure
investigation prompt as Ctrl+C. Use `tools/run-tests all --continue-on-errors`
(or the corresponding aggregate) to continue independent tests after failures.
Safety and infrastructure refusals still stop the run. Reattachment preserves
the original options. The flag takes no value and can accompany `--serial-builds`.
For selected granular categories, the leading `--stop-on-error` option enables
the same cooperative first-reported-failure cancellation without disabling
parallel scheduling, for example `tools/run-tests --stop-on-error unit`.
Ordinary selected commands keep their existing failure policy. The option
conflicts with `--continue-on-errors`.

### Scripted repair loop

Run [`tools/fix-tests`](../tools/fix-tests) to start or attach to the scripted
repair loop. Round 1 runs every entry in `run-tests --list`, using its explicit
arguments, until each passes. After a failure, a fresh Codex process receives
that run's generated investigation prompt, applies a repair, exits, and the
script reruns that category. Round 2 runs `run-tests all`; failures trigger
repair/category retries before another complete `all` run. Only a passing
complete run finishes the loop. Concurrently reported failures are handled by
category; interrupted companion categories are not falsely marked passed.
For each round-1 category, the launcher highlights
`Running category [category] (x/y)` beneath the test dashboard's `Overall` row,
then retains it after the completed test output with its position in the discovered list.
The exact argument arrays from that inventory are forwarded to the test runner.

Optional categories restrict both repair and verification: `tools/fix-tests host`,
`tools/fix-tests unit ui` and `tools/fix-tests "unit ui"` are supported.
Expansion uses the same `suite_inventory` utility as the `run-tests` host coordinator.
`host` (also `host-builds`) expands to all implemented host leaves, excluding
`system` and `e2e`; `all` expands to every implemented leaf. Overlapping selections
are deduplicated in inventory order, and unknown categories or diagnostic helpers
are rejected. With explicit categories, round 2 repeats only those leaves until
a complete selected pass needs no repairs; it never invokes the `all` aggregate.
Without categories the existing two-round full-regression behavior is unchanged.
Categories and model options apply to new runs; attaching keeps the active run's scope.

The launcher itself is Python scripting. At the start of each new run, it reads
the Codex CLI model catalog and selects the newest listed Sol model that supports
high reasoning (`gpt-6-sol` currently). Each failure starts with that model at
high reasoning. It classifies the failure first and repairs a test defect in the
same session. For an app issue or uncertain classification, it exits without
editing and the launcher starts a fresh session with the catalog's strongest
listed high-reasoning model (`gpt-6-astra` currently) to recheck and repair. The
next failure starts again with Sol. `--model` and `--effort` override the initial
agent for a new run; app review always uses the strongest model at high reasoning.
Each agent uses
`codex exec --ephemeral`, disabled conversation history and memories, and receives
the latest failure handoff. The script never resumes or forks a session; the app
review receives only the original handoff and the Sol classification summary.
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
no interactive input box or approval prompt; the result file still controls
repair verification. Development activation is `none`; new launcher processes
use the checkout code without product installation or a service restart.

Closing the terminal detaches; rerun `tools/fix-tests` to attach to the current
output, with a bounded tail of earlier output. `tools/fix-tests --stop` and
Ctrl+C request the same immediate cancellation. Tests receive the runner's
Ctrl+C path and finish guarded cleanup before exit. Agents receive termination,
with a three-second limit before their recorded process group is killed. If the
loop owner dies, its supervisor detects EOF and cancels the current operation.
Completed or dead owners never block a fresh run: file locks determine liveness,
old cancel markers are isolated by run, and normal `run-tests` startup performs
its existing retention/VM recovery. An attached predecessor's result is consumed
before starting the requested category; it never counts as that category passing.
On stale ownership, `fix-tests` invokes `tools/cleanup-e2e` to reconcile both
host and VM retention under their respective locks before retrying the category.
If automatic recovery's cleanup-safety run produces a normal failure handoff,
`fix-tests` repairs that failure and retries recovery before starting the requested
category. Recovery still fails closed when no actionable handoff is available.

Logs and small control files are private under `output/test-runs/host/fix-tests/`. They are
not agent conversation history. Existing test evidence remains under the runner's
retention policy. Machine-readable `failure.json` accompanies the printed prompt
and supplies stable retry category IDs. A missing handoff, unresolved prerequisite,
unmapped infrastructure failure or agent-reported blocker stops with evidence;
the loop does not alter expectations or bypass permissions to continue.

The process lifecycle is qualified using isolated test/agent doubles in
`test_fix_tests_cleanup_safety.py`; these tests never invoke the model or VM.

### Scripted E2E implementation

Run [tools/write-e2e](../tools/write-e2e) to implement the execution plan's first
unchecked active task through fresh unattended Codex sessions:

```sh
tools/write-e2e --sessions 3 --tasks 1
tools/write-e2e --tasks 2
tools/write-e2e
tools/write-e2e --stop
```

`--sessions N` limits the total number of new sessions across implementation,
live verification, retries and subsequent tasks. Omitting it imposes no session
limit. `--tasks N` limits completed tasks and defaults to `1`. Both limits accept
positive integers for a new run; the launcher stops when either limit is reached. A task counts
only after acceptance, queue close-out and successful staging. An empty active
queue or a blocker still stops the workflow. With a live run, an invocation without
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

The first session for each task uses GPT-6-Astra Low to implement and host-validate,
then hands off before live VM testing. The installed `codex exec` transport has
no in-session model-switch control, so live/repair sessions use the requested
GPT-6-Astra High fallback. On a first live failure the agent reviews unstaged
code, preserves evidence, repairs authorized defects, host-validates and hands
off before another live attempt. Further failures repeat that boundary. A
passing live session completes the plan's acceptance, checks the row and advances
its sole pointer. It returns an explicit list of task-related code, test and
close-out files; the launcher stages those files without committing before
starting another session. This staging uses literal Git paths and needs no
agent-side Git permission grant. Task 192 retains the plan's explicit host-only exception.
Staged code is the baseline; agents do not analyze staged diffs.

Each session is a new `exec --ephemeral` process with history and memories
disabled. Only the latest standalone handoff crosses sessions. Existing CLI
authentication, sandbox and command grants apply; missing grants or unresolved
behavior decisions stop with a blocker. No live Codex or VM work is performed
by the launcher's regression tests.

The shared [session renderer](../tools/launcher_render.py) applies these display
rules to every supervised agent; launchers do not format agent events themselves.
`run-tests` produces test dashboards rather than agent events and preserves
those dashboards when observed through either workflow launcher.
The shared [detached launcher module](../tools/detached_launcher.py) owns
workflow attachment, process supervision, fresh Codex transport, log rotation
and output following for `fix-tests` and `write-e2e`; `run-tests` shares its lock
primitives and registers test owners started inside an E2E agent session.
Cancellation or worker death cancels only those recorded test runs, validates
their directory identities and waits for guarded cleanup before releasing the
workflow lock. Already-running tests that the agent merely attaches to remain
owned by their original caller.

Private output and checkpoints use the shared storage and retention libraries
under `output/test-runs/host/write-e2e/`. At a successful task boundary, the
launcher prints a green `Task ID complete` line after acceptance and staging. It
saves the full summary and next-session prompt in `handoff.txt` without printing
them. At an incomplete session boundary or safe stop, it still prints and saves
the handoff. A new invocation after that boundary continues the latest
handoff with fresh session and task budgets. An interrupted or blocked checkpoint
starts an Astra High recovery session that rechecks evidence and cleanup,
resolves authorized remaining host work, then hands off before live testing.
Unresolved blockers stop again; an interrupted session that changed the queue
requires inspecting its saved handoff. The launcher never assumes an interrupted
live test passed. Lifecycle qualification lives in
[test_write_e2e_cleanup_safety.py](unit/test_write_e2e_cleanup_safety.py).

### Aggregate execution and reconnection

Run `make test-all` (`tools/run-tests all`, also the default with no arguments)
for all established regressions. `make test-all-verify` / `tools/run-tests all-verify`
are compatibility aliases for the same work. Every VM entry point uses
metadata-only snapshot verification, including standalone preparation,
maintenance, qualification and recovery. No path hashes VM images or runs
structural image scans. Ownership locks, snapshot/chain checks, targeted guest
inspection, package/artifact verification and cleanup remain active.
`--skip-backing-verification` remains an accepted compatibility no-op.
Reports record `metadata-only` and zero image-content verification bytes.
Both aggregate targets automatically discover all ready E2E variants, including
the installed Parent About/license scenario. For E2E-only runs, use
`tools/run-tests e2e --ready --artifacts '<fresh-artifact-directory>'`; for just
Parent About, replace `--ready` with `--scenario 'E2E-030/parent'`. The
[E2E runner guide](e2e/README.md#run-e2e-scenarios) covers building inputs, listing,
pending scope and prerequisites.
Every `tools/run-tests` category runs independently of its terminal. Closing the
terminal detaches the display; tests continue. Ctrl+C requests cancellation and
waits for owned cleanup. Invoke `tools/run-tests` in a new terminal to attach to
the existing progress and final output, including its exit status. Within the
requested host or VM scope, while a run is active or has an unread successful
result, execution invocations warn and attach to it, ignoring new arguments—even
another category or invalid options. Host and VM sessions have independent
ownership and reconnect state, so one of each can run concurrently.
The original selection and options remain in effect. Global and category help,
listings, and collection-only invocations always return their requested inspection
output without acquiring or checking test/session locks, attaching to a run, or
marking its result delivered.
A failed or incomplete idle session can be replaced by an explicit new selection;
its output is preserved and startup recovery runs before new VM checks. Host-only
execution refuses pending VM recovery.
Invoke without arguments to replay any unread VM-side result. After delivery,
or when no VM session exists, an invocation without arguments starts the `all`
aggregate. VM session output and ownership records live under
`output/test-runs/host/sessions/`; host-only records live under
`output/test-runs/host/sessions-host/`. Reconnect to a host-only run with a host
category such as `host`, `ui`, or `unit`.
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
Long rows are clipped to terminal width to keep cursor redraws aligned; the
live frame also fits the terminal height, using the output terminal's actual
dimensions instead of potentially stale `LINES`/`COLUMNS` environment values.
The saved final summary retains the full text of all rows. Full output is continuously
appended and flushed to `docs/TestAutomation/Evidence/test-all-runs/<run>/report.md`.
The accompanying `progress.json` records the latest category counts, states,
branch assignments and launch order. The final report includes the same branch
summary. Percentages describe completed checks, not estimated time remaining.
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
recovery window. Reviewed cleanup modules run in balanced buckets
with their fixtures kept together. **Join cleanup prerequisites** requires every
bucket to pass and exit before downstream execution. UI, component and
fixture-runtime workers validate the shared passing gate. Standalone prerequisite
calls and foreground/unattended VM dispatch share content-qualified cleanup
reuse; every live ownership, recovery and VM lease check still runs.

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
diagnostics remain available. Nested-Shell interaction resolves the owned
`child-request-button` by its public automation ID, semantically focuses that
control and reacquires it immediately before normal keyboard input. It does not
set Shell overview state directly or derive input from an AT-SPI allocation.
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
descriptor; another terminal's `tools/run-tests` attaches to its session.
Host-only selections use `artifacts/test-activity/host.lock`; selections with
VM or privileged integration work and standalone VM preparation keep
`artifacts/test-activity/lock`. Competing owners within each scope refuse.
Host-only tests can therefore run alongside `tools/prepare-appsnapshot`.
The VM's existing cross-controller lease remains independently authoritative.
Ordinary pytest caches are disabled. The report labels every output fragment
with its category and links separate private raw streams; one coordinator writes
all progress. Category `waiting` records time queued separately from execution.
Source identity is recorded at startup for reference. Checkout edits during a
run do not stop scheduling, invalidate results or expire the current activity's
passed cleanup prerequisites. Tests can load later edits; a passing run does not
certify one immutable checkout revision.

The aggregate dispatches each complete `system` or ready `e2e` selection in one
invocation through the shared VM launcher. Prerequisite checks run once at each
suite's startup, not between cases or phases. Both controllers use the shared
event writer for live counts and failures. A failure event is reported immediately;
automatic aggregate cancellation waits for the controller to finish evidence
collection, restoration and its final audit. Explicit user cancellation remains
available through the normal owned-process channel.

Automatic package preparation and the maintained cleanup coordinator can reuse
content-qualified startup work across invocations. See
[reusable startup preparation](e2e/README.md#reusable-startup-preparation) for the
input keys, invalidation and bounded storage contract. A cached qualification
does not bypass live ownership or VM checks. Explicit regression and fresh-build
selections remain fresh.

Installed-system runs retain one exclusive VM lease. Package installation/reboot
checks keep their lifecycle together on `onpc-baseline`; each post-install area
restores the same retained version snapshot used by E2E, preparing it only when
missing. Explicit upgrade attempts keep the upgraded state throughout their
selected checks. Multi-case E2E runs retain one exclusive VM lease and
connection across fresh-baseline cases. Baseline/chain metadata verification and
offline guest inspection run before the first case and after the last case or
failure. At case completion, the runner force-reverts the recorded guest directly
to the accepted off snapshot, without an ACPI shutdown wait; the next case
uses that restored state without restoring it again. Live lock, domain instance,
disk path/inode, snapshot metadata and isolation checks remain active. Each case
still provisions its own declared inputs and gets its own worker and evidence;
no product state continues between cases. Case results remain candidates until
the suite audit, host preservation check and actual lock/connection release pass.
Any case or transition failure stops the suite. Single-case runs retain their
full independent attempt lifecycle.

The command collects current unit/contract, private-D-Bus, UI and fixture runtime
cases; runs cleanup prerequisites in isolation before protected operations;
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
or an artifact build) counts as one check. Totals show `?` while discovery is
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
dispatcher and the `make test-all` Codex rule; restart Codex to load new rules.
Direct terminal use has no Codex approval layer. The equivalent already-approved
`tools/run-tests all` route remains available in an existing Codex session.
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
current run is preserved and reported as an error, and blocks a new run until
its evidence is explicitly reduced or removed. These are per-journal limits,
not a filesystem quota on an active build. Recovery receipts expire with their
run. Reconnect and repair directories also rotate; repair transcripts retain
a bounded tail (32 MiB threshold) between operations. Process-owned temporary
scratch uses an inherited owner lock and recorded directory identity: the next
launcher reclaims idle scratch, while active owners remain protected. Build
subprocesses forward inherited scratch leases through the fixture builder too.
Scratch initialization publishes a complete owner atomically from a recorded
staging slot; interrupted initialization and deletion can resume without
adopting unknown payloads or losing the directory identity.

`make test-all`, `make test-all-verify`, `tools/run-tests host` and
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
window rotate during preflight, before VM memory admission, after cleanup prerequisites
pass and the shared VM lease/journal show no unfinished recovery. A host-only
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

For older unregistered qualification directories, `tools/run-tests integration
check_tmp_storage` prints a read-only inventory with sizes and directory
identities. After reviewing the inventory, put only explicitly selected records
(`path`, `device`, `inode`, `mode`) in `artifacts/tmp-storage-cleanup.json`, then
run `tools/run-tests integration check_tmp_storage_cleanup`. This developer
cleanup requires an idle privileged retention owner and completed VM recovery,
refuses live process references, and validates every identity and mount boundary
before deleting anything. It never selects deletion targets by prefix or age.
Keep needed recent diagnostics out of the manifest. Both commands use the
existing integration dispatcher and its cleanup-safety gate.

System evidence keeps its registered allocation root at mode 0700; use the
installed artifact reader for privileged results. Legacy journals with mismatched
system-root modes require explicit migration; they cannot create an unbounded
archive outside rotation.

For the storage relocation, `tools/run-tests integration check_storage_migration`
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
journal. Unfinished host retention still refuses a new retained host run;
`tools/cleanup-e2e` reconciles both scopes under their respective locks.
The launcher must hold checkout activity ownership
and acquire the storage owner locks; a live owner is never killed or displaced.
The installed `check_test_recovery` route reconciles the VM through the existing
identity-checked recovery controller and shared VM lease. It also runs before a
new VM category, so a stale VM journal cannot strand otherwise completed host work.
Recovery runs its mandatory cleanup-safety prerequisites, not product suites.

After VM recovery succeeds, unfinished retention journals and recovery markers
are archived as `recovered-<run>.json` and `recovered-<run>.marker`. Every registered
allocation must pass ownership, identity and mount validation before its blocker
is cleared. Evidence remains in the normal rotation. After recovery succeeds,
older runs may expire under the count and byte limits; the recovered current run
remains. Recovery does not scan temporary-directory prefixes and is retryable.
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
not a byte quota on the retained runs or on unrelated applications/system logs.

Generated `test-all-runs/` reports are Git-ignored so streaming them cannot
invalidate package or E2E source provenance. Curated evidence elsewhere in this
directory remains tracked and continues to participate in source validation.
This command covers established regressions, not completion of the unfinished
release-acceptance roadmap.

## Test layers

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
tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q
tools/run-tests component 'tests/component/test_*.py' -q
tools/run-tests ui -q
tools/run-tests integration check_graphical_worker
tools/run-tests integration check_package_notice
tools/run-tests system --artifacts /tmp/onpc-test-artifacts/first --area authorization
tools/run-tests e2e --list
tools/diagnose journal --unit 'oh-no-parent-control*' --lines 500
tools/test-vm status
```

`check_package_notice` runs real APT and dpkg against tiny fixture packages in
private chroots under `/var/tmp/onpc-package-notice-*`. It exercises the production
notice bootstrap, helper, and removal hook through first install, reinstall,
remove/reinstall, and trigger failure. It changes no host packages or VM state;
it does not exercise the product's kiosk, PAM, or service provisioning.
Command output and results are retained for the artifact reader below.

Always quote filename patterns and parametrized IDs. The launchers validate
every selection and option, expand globs without a shell, preserve exit status,
and run cleanup prerequisites automatically before host-integrated operations.
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

Install or refresh with `./setup.sh --test-tools-only`, then restart Codex with
the project trusted. Use `./setup.sh --codex-rules-only` for rule-only updates.
Initial installation uses `./setup.sh --bootstrap-tools` and can require
one-time administrator authentication. Repeated bootstrap and all routine host
setup, including dependencies, use the dedicated `onpc-setup` action and never
fall back to an authentication dialog. Repairing an existing denied installation
requires running that setup mode from an administrator-authorized root session. Installed
Polkit grants permit active local administrators and deny excluded callers;
the new checkout wrappers check permission without requesting authentication.

Temporary screenshot cleanup still uses `tools/cleanup-screenshots` with
explicit caller-owned `/tmp/onpc-*.png` filenames. Privileged graphical smoke
exports still use
`pkexec /usr/local/libexec/onpc-export-screenshot SOURCE /tmp/onpc-new.png`;
the source must be a regular PNG directly inside an
`output/test-runs/{host,privileged}/allocations/onpc-graphical-smoke-*/testresults/`
directory (legacy `/tmp` sources are still readable). See the helper's validation
tests for ownership, size/signature and no-overwrite guarantees.

Full `./setup.sh` and `--test-tools-only` both maintain graphical AppArmor policy. Classic VS Code
snap attachment needs anonymous graphics-socket peer rules in libvirtd and
QEMU; the QEMU drop-in activates at the next guest start. Development helpers
activate on invocation (`none`), Polkit watches installed rules, and Codex
requires restart. No product package or saved-data change is involved.

### Prompt-free test artifact access

Use the installed `onpc-test-artifacts` helper for privileged inspection across
all test runs, names, extensions, and nested directories. Its Codex allow rule
and dedicated Polkit rule cover the whole helper, not individual files:

```sh
pkexec /usr/local/libexec/onpc-test-artifacts read /tmp/onpc-system-EXAMPLE/input/selected-inputs.json --bytes 8000
pkexec /usr/local/libexec/onpc-test-artifacts list /tmp/onpc-system-EXAMPLE
pkexec /usr/local/libexec/onpc-test-artifacts tail /tmp/onpc-system-EXAMPLE/private/command-1.log --bytes 16000
pkexec /usr/local/libexec/onpc-test-artifacts stat /tmp/onpc-system-EXAMPLE/evidence/result.json
pkexec /usr/local/libexec/onpc-test-artifacts export /tmp/onpc-future-run/results/recording.webm
```

`read` also accepts `--offset` for paging through large files. `list` returns
JSON names; `stat` returns JSON type, size, mode, and modification time. `export`
prints a new `output/test-runs/host/exports/onpc-artifact-export-*/<original-name>`
path, subject to bounded export retention. Its directory is
mode `700` and file mode `600`, both owned by the invoking account. Ordinary
readers can then inspect the copy without privilege. Existing graphical smoke
PNG exports continue to use `onpc-export-screenshot` above.

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

Install or refresh through `./setup.sh --test-tools-only`, then restart Codex
with this checkout trusted to load the new allow rule. Polkit grants activate
immediately for active local `sudo`-group administrators. Installation itself may
need administrator authentication. These development-only helpers activate on
invocation (`none`), are absent from the product package, and change no saved
application data. Restrictive organization-managed Codex policies still take
precedence over local allow rules.

### Manual entry points

Before a host-integrated test that terminates processes, run its cleanup-safety
regressions in isolation. They must pass before the protected operation starts.
For the existing aggregate local/system commands, this cleanup-only selection
covers the current UI, nested-Shell, VM controller and persistent caller paths:

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
category launchers now run these prerequisites automatically for focused and
aggregate protected operations. Direct legacy Make entry points still require
explicit safety prerequisites.

The developing graphical adapter additionally requires
`tests/unit/test_graphical_lease.py` in isolation before its live use. It covers
VM ownership refusal and real display descriptor transfer/revocation. The
worker adds `tests/unit/test_graphical_worker_cleanup_safety.py`. The privileged
integration dispatcher runs both automatically before
`integration check_graphical_worker`, whose non-VM fixtures verify byte transfer,
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

Open `tools/watch-ui` as the desktop user before or during a run. It discovers
private UI workers from this checkout for both `tools/run-ui-tests` and all
aggregate paths (`tools/run-tests ui`, `host`, `all`, and mixed selections).
**All branches** lays out up to four workers in a 2×2 grid, with a separate tab
for each worker. Both views show the current pytest node ID and phase. Workers
appear when their private compositor fixture starts, disappear on shutdown or
expired heartbeat, and later workers reconnect automatically. The viewer may be
opened, closed, resized or reopened without controlling the tests. Runs started
before this feature was loaded need to finish and start again to publish frames.
The viewer prints its private `/var/tmp/onpc-ui-viewer-*/viewer.log` location
at startup and records Python and native GTK output there, so later warnings
cannot interrupt the launching terminal. Reopen an existing viewer to load changes
to its output handling.

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
diagnostics at the printed `/var/tmp/onpc-ui-watch-*/capture.log`. Earlier setup
failures are reported by the runner. Optional observation never retries a test
action or changes test outcomes. Owned collector/service cleanup still runs.
Frames are review aids, never automation targets or acceptance evidence.

Activation is `none`: new test fixtures and viewer invocations load the source;
no product package, service or data migration is involved. The existing
`./setup.sh --test-tools-only` route installs the optional viewer desktop/icon
identity, and the existing executable-tool discovery includes `tools/watch-ui`
at the next rules refresh. No broader command or privilege grant is needed.

The bare-Mutter fixture disables its opening-window scale effect through
`MUTTER_DEBUG_DISABLE_ANIMATIONS`, the upstream default plugin's test switch.
Automation nevertheless reacquires controls by public ID and verifies semantic
readiness after transitions. Allowance coverage selects the declared choice
through its public action and independently verifies the saved value; it does
not depend on animation timing, pointer coordinates or menu placement.
Preview process logs are retained in private `/var/tmp/onpc-ui-preview-<run>/`
directories, printed by the fixture, so later pytest categories cannot rotate
away the first failure's diagnostics. These directories are disk-backed on the
development host; logs and existing failure evidence are never removed by tests.

Host pytest launchers fix `TMPDIR` to owner-locked scratch beneath
`output/test-runs/host/scratch/` for capture and temporary fixtures.
The three 100-run retention repetition tests explicitly use private `/tmp`
trees and check their peak footprint each iteration: fewer than 64 entries and
256 KiB of file contents per case. Their fixture removes only its own tree on
exit. All iterations and real filesystem calls remain; memory-backed `/tmp`
avoids repeated disk flush latency. Separate ordinary `tmp_path` tests verify
disk-backed journal sync ordering, write-failure propagation and preservation
of existing evidence. This narrow exception does not move runner journals,
capture, screenshots or other test fixtures to `/tmp`.
`tests.support.preview.boot_preview_session` scopes tempfile's default to `/tmp`
only while Dogtail boots its private graphical runtime. WebKit creates
`/var/tmp` as a symlink inside its sandbox, so placing `XDG_RUNTIME_DIR` beneath
that path causes sandbox startup to abort. The runtime keeps its existing owned
teardown; no sandbox protection is disabled. Success, failure and interruption
restore pytest's disk-backed default (`test_support.py`). See the
[upstream sandbox layout](https://github.com/WebKit/WebKit/blob/main/Source/WebKit/UIProcess/Launcher/glib/BubblewrapLauncher.cpp).
Request-layout, allowance and legend images use private `/var/tmp/onpc-*`
directories. After setup, assertions and all fixture teardown have passed,
the owning test removes its rendered PNGs and layout JSON. Failed, skipped,
interrupted or teardown-failed attempts keep their images. Input event streams,
preview logs and other diagnostics are preserved. Cleanup never scans old runs
or deletes another worker's artifacts. Nested-Shell tests also discard their
regenerable Mesa/NVIDIA shader caches after successful teardown, retaining
Shell logs and reviewable screenshots. Synthetic E2E preflight assets have an
explicit temporary-directory fixture lifetime, including setup failure.
`test_ui_artifacts_cleanup_safety.py` covers successful/failed teardown,
concurrent attempts, directory replacement and symlink/hardlink refusal.
An earlier parallel host run
exhausted the user quota on RAM-backed `/tmp`: retained layout cases used about
102 MiB each, and shared filesystem exhaustion broke capture writes and package
fixtures in other workers. Private filenames do not isolate storage capacity.
Pytest continues to own its numbered-directory locks and capture files; no
worker deletes another worker's evidence. Completed aggregate evidence follows
the [three-run retention policy](#aggregate-output-retention).
Maintainer-script fixtures use `tests.support.shell.relocate_system_paths` to
rewrite only original source matches in one pass. Sequential replacements
corrupt inserted roots containing `/var/` or `/home/`; `test_support_shell.py`
covers those roots and the real package configuration/removal suites exercise
the resulting scripts under `/var/tmp`.
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
`/tmp/onpc-gjs-coverage-<run>/` directory containing `coverage.lcov`.
Nested-Shell logs and screenshots
are under `artifacts/ui/child-shell/`; `latest/` is only a convenience copy,
never evidence for a different source revision or test attempt.

## Property tests, contracts and coverage

The committed `onpc` Hypothesis profile in `conftest.py` bounds deterministic
generated policy/transaction cases. Turn a discovered failure into a permanent
regression example, preserve its reproducer/profile, and check the real invariant
after each state transition. Do not add a production test mode to support it.

Source/configuration contracts protect supported APIs, ownership, packaging and
architecture. Keep them classified separately from executable customer behavior.
A file assigned the `contract` marker does not become runtime acceptance merely
because pytest executes its assertions.

`make check-coverage` currently reports Python branch coverage for its default
host collection under `artifacts/coverage/` (HTML and XML). It does not report
full graphical/system coverage. Inspect missing paths by security boundary:
caller/target validation, authorization, transactions and rollback, preferences,
migration, enforcement activation and process ownership. A blanket percentage
does not establish those behaviors. Future aggregate evidence must name the
layers actually measured and include the separate child-language results.

## Maintaining regression coverage

### Handling test failures

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
incorrect test API call or a harness crash. A product crash, timeout or failed
assertion can indicate a regression; its failure type alone does not establish
a mechanical test issue. Report the cause, correction and verification in the
normal work summary. A test's disagreement with the app alone never justifies
classifying the test as broken.

### Coverage maintenance workflow

1. Identify the changed behavior and its authoritative specification/design
   requirement, or the necessary harness safety guarantee. Follow the
   [app scope and prerequisite rules](../docs/TestAutomation/E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope).
   Use supported fixture helpers for unrelated OS/account/asset setup. Add
   regression cases at the lowest effective layer; exhaustive independent form
   values belong in local tests, with real installed/customer coverage for the
   boundaries and causal journeys that require it. App approval denial must
   assert unchanged grants/policy and recovery, not just Ubuntu's error message.
2. Classify the tests, their affected components/shared dependencies, runner,
   environment and safety prerequisites. Add them to the authoritative suite
   inventory when implemented; they must not be silently absent from `test-all`.
3. Maintain stable `ONPC-...` IDs and `requirements.json`. Run
   `python3 tools/verify_test_traceability.py --mode stage` after specification
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
