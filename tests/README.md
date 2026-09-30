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
host-only boundary to focused UI commands. Owned cleanup and required package
inputs still run wherever the selected suite needs them.

The complete partition is **host + system + e2e = all**. Combine any of these
categories in one invocation; execution always orders host first, then system,
then E2E. For example:

```sh
tools/run-tests host
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
for active guests' cleanup. `--vm NAME` narrows tests to one enabled entry.
All `--vm` options and Make `VM=` parameters accept either the exact configured
name or its `id`. IDs resolve from the current `config/test-vm.json` on every
invocation; changing or swapping them needs no helper refresh or baseline
replacement. Active runs keep their canonical names, so attachment uses the
current ID for the original guest. UUID pins, leases and journals remain scoped
to that guest. Names and IDs have no hardcoded mappings in consumers.
Host work runs once; VM workers keep individual reports and journals, with a
retained queue summary linking their logs and failure handoffs. Required package
inputs are prepared through the maintained builders. Repair and implementation
agents remain serial; `fix-tests` and `write-e2e` share the VM queue through
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

### Scripted repair loop

Launcher agents and sessions use `tools/prepare-baseline --vm NAME --mode auto --y`
when an authorized baseline refresh is needed. Explicitly authorized manual-mode
preparation uses `--mode manual --y`. The flag suppresses the y/n prompt; manual
work omits it to retain confirmation. Warnings and all safety checks still apply.
The shared launcher prompts carry this instruction; runners never prepare a
baseline implicitly. See [VM preparation](integration/Environment.md).

Run [`tools/fix-tests`](../tools/fix-tests) for the configured enabled VM queue,
or with `--vm NAME` for one enabled VM, to start or attach to the scripted
repair loop. Round 1 runs every entry in `run-tests --list`, using its explicit
arguments, until each passes. After a failure, a fresh Codex process receives
that run's generated investigation prompt, applies a repair, exits, and the
script reruns that category. `--rounds X` defaults to 1, running only round 1.
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
`host` (also `host-builds`) expands to all implemented host leaves, excluding
`system` and `e2e`; `all` expands to every implemented leaf. Overlapping selections
are deduplicated in inventory order, and unknown categories or diagnostic helpers
are rejected. With explicit categories, round 2 repeats only those leaves until
a complete selected pass needs no repairs; it never invokes the `all` aggregate.
Without categories verification uses the full regression aggregate.
Categories, rounds and model options apply to new runs; attaching keeps the active run's options.

The launcher itself is Python scripting. New runs validate the selected model
and effort against the Codex CLI catalog before testing. Classification and
proven mechanical test repairs use **GPT-6.1 Sol Medium** in one session.
App issues, uncertainty and unresolved security, concurrency, ownership or
difficult diagnosis end that session without edits and transfer to a fresh
**GPT-6.1 Sol High** session to recheck and repair. This raises reasoning effort
at the judgment boundary without paying for an additional adviser and a second
implementation context. Delegation stays disabled; classification is not an
extra read-only agent before every mechanical repair.

If verification after a claimed repair still fails, the next repair goes
directly to GPT-6.1 Sol High with the latest failure evidence and previous repair
summary. It stays there until that category passes, even if the next failure
is different. This conservative rule avoids another Medium classification pass;
it does not wait for E2E's two-live-attempt threshold. A passing category clears
that handoff. A new failure chain starts with classification. Detaching preserves
the live loop; after a stopped/dead owner, a new run starts fresh, as before,
without loading old repair conversations or assuming old verification applies.
An answered blocker keeps its current model/phase and is not a failed repair.
Ownership recovery remains the existing scripted `cleanup-e2e` operation; a
normal cleanup failure handoff enters the same repair policy, while refusal
without a handoff still stops. No model performs routine ownership recovery.

`--model` and `--effort` override the initial agent for a new run; review uses
GPT-6.1 Sol High. Sol must be `gpt-6.1-sol`; other Sol versions are refused, with no
silent fallback. Sol High/Extra High requests retain their requested effort. Both required
model/effort pairs must be listed. All agent sessions pin **Standard speed**,
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
round, phase, selected model/effort and Standard speed. Session exit, structured
result and category verification events link classification, blockers and retries
to the repair chain. Missing counters are unknown, including a session with no
reported usage; they are never zero-filled. An interrupted verification has no
success event. A category pass is local verification, not proof that later
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
live verification, retries and subsequent tasks. A new run with no options
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
close-out and successful staging. An empty active
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

Initial implementation and follow-up sessions use GPT-6.1-Sol Medium as
coordinator and implementer. After two recorded live attempts on an unfinished
task, subsequent sessions use GPT-6.1-Sol High, including after a launcher restart.
A new task starts with 6.1 Sol Medium again; a suspended consumer retains its
own attempt count. Preparation failures and session count alone do not trigger
escalation. Settled implementation, mechanical
repairs, test execution and close-out stay with that coordinator. Unresolved
root causes, security, concurrency, ownership and risky
correctness questions require one bounded GPT-6-Astra High consultation through
the [read-only adviser](../tools/write_e2e_adviser.toml). Prefer GPT-6.1 Sol High
over Astra Low for implementation and recovery.
This policy overrides model recommendations in older saved handoffs.
Consult before implementing an unresolved risky design, including in the initial
session. All coordinators and advisers pin Standard speed, so personal Fast
settings cannot silently increase subscription usage. Keep source reads and
diagnostic output scoped, reuse unchanged context and carry concise handoffs;
never reduce required understanding, assertions, acceptance or cleanup.

Consultations are sequential: the coordinator gives one exact question, relevant
source/evidence paths, applicable contracts and user decisions in a fresh context,
waits for the answer, then closes the adviser before resuming work or consulting
again. Codex V1 is configured with one concurrent child slot and one level of
delegation. The adviser cannot delegate further and is configured read-only; its
instructions prohibit edits, tests/builds, VM control and task completion. It
returns concise findings, evidence, a proposed correction, uncertainty and required
regressions. The coordinator checks the advice and owns all implementation,
validation, cleanup and queue updates. Advice provides no acceptance credit.
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
recovery. A preparation failure before VM access does not count as a failed live
attempt: repair authorized mechanical defects or prepare missing generated inputs
through the maintained artifact builder and resume validation in the same session.
Do not ask the developer to choose between building and restoring qualification
inputs. Integration qualifications using `named_input()` register automatic
preparation in `tools/test_commands.py`; launcher coverage discovers consumers
independently so new wrappers cannot silently omit preparation.
Only a prerequisite requiring external action or an unresolved behavior decision
returns a blocker with the actual validation outcome. A passing session completes
the plan's acceptance, checks the row and advances its sole pointer. It returns an explicit
list of task-related code, test and
close-out files; the launcher stages those files without committing before
starting another session. This staging uses literal Git paths and needs no
agent-side Git permission grant. Task 192 retains the plan's explicit host-only exception.
Staged code is the baseline; agents do not analyze staged diffs.

Close-out ignores reported paths that are absent from both the working tree and
the Git index, such as temporary briefs created and deleted within the task.
Tracked deletions still stage normally. If staging fails after acceptance, the
launcher retains the accepted result and current handoff. Restart revalidates
that result against the saved queue state and retries only its staging before
selecting the next task; it does not repeat the completed live acceptance or
rewrite the previous run's evidence. Unrelated interrupted queue changes still
refuse recovery.

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
submitted answer wins. Your answer continues the same task through a fresh Sol
Medium recovery session with the saved handoff and your instructions. It does not
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
the session's implementation, recovery or numbered live-test phase. Category and
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
The full engineering handoff remains in `handoff.txt`, without being repeated in
the blocked display. An interrupted session that changed the queue
requires inspecting its saved handoff. The launcher never assumes an interrupted
live test passed. Lifecycle qualification lives in
[test_write_e2e_cleanup_safety.py](unit/test_write_e2e_cleanup_safety.py).

### Aggregate execution and reconnection

Run `tools/run-tests all` for the enabled VM queue, or `make test-all VM=NAME`
(`tools/run-tests all --vm NAME`, also the default with only `--vm NAME`) for one enabled VM,
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
the existing progress and final output, including its exit status. While any run
is active, execution invocations warn and attach to it, ignoring new categories or invalid options. VM attachment and cancellation
require the original configured `--vm NAME` for narrowed runs; missing or different
names refuse. Configured queue runs attach and cancel without `--vm`.
`tools/run-tests --vm NAME --stop` attaches to a narrowed VM run, requests
cancellation, and waits for owned cleanup; when idle it returns without starting
tests or consuming saved results. An active host run is found even with no
arguments or a VM category, and an active VM run is found with host arguments.
Host and VM activity locks remain separate so standalone VM preparation can
overlap host tests. If older launchers already started both scopes, attachment
prefers the requested scope (VM for no arguments).
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
recovery window. Reviewed cleanup modules run in balanced buckets using measured
module costs shared with unit scheduling. Modules keep their fixtures together;
the large installed-journey safety matrix explicitly permits eight pieces of
exact test IDs because its fixtures and outputs are function-local. This review
applies to both schedulers, with a regression guard against shared fixture scope.
Its synthetic inventories contain only the exercised scenario family, preserving
that family's complete matrix and the real durable recorder while avoiding copies
of unrelated families for every injected fault. These are explicit regression
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
checks keep their lifecycle together on `onpc_baseline`; each post-install area
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

Full GUI-only matrices belong in preview UI tests. Installed E2E retains a small
component check plus distinct backend, persistence and OS integration results.
Both layers reuse shared GUI operations and public readers; see the
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
tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q
tools/run-tests component 'tests/component/test_*.py' -q
tools/run-tests ui -q
tools/run-tests integration --vm NAME check_graphical_worker
tools/run-tests integration --vm NAME check_package_notice
tools/run-tests system --vm NAME --artifacts /tmp/onpc-test-artifacts/first --area authorization
tools/run-tests e2e --vm NAME --list
tools/diagnose journal --unit 'oh-no-parent-control*' --lines 500
tools/test-vm --vm NAME status
```

`check_package_notice` runs real APT and dpkg against tiny fixture packages in
private chroots under `/var/tmp/onpc-package-notice-*`. It exercises the production
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
`pkexec --keep-cwd /usr/local/libexec/onpc-export-screenshot SOURCE /tmp/onpc-new.png`;
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
and dedicated Polkit rule cover the whole helper, not individual files. Run from
the checkout root and keep `--keep-cwd` before the helper path:

```sh
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts read '/tmp/onpc-system-EXAMPLE/input/selected-inputs.json' --bytes 8000
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts list '/tmp/onpc-system-EXAMPLE'
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts tail '/tmp/onpc-system-EXAMPLE/private/command-1.log' --bytes 16000
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts stat '/tmp/onpc-system-EXAMPLE/evidence/result.json'
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts export '/tmp/onpc-future-run/results/recording.webm'
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
The left terminal follows active `fix-tests` output before `run-tests`,
using VS Code Light+ colors, wrapping and vertical scrollback. The initial
horizontal split is 25%/75%, adjustable by dragging. The right viewer has one
flat tab row: **All**, **UI - category** for each active UI worker category,
and each registered VM's name. In the bottom **All** scope, category and VM
tabs are prefixed with **[branch]:**. Its viewer **All** tab puts active viewers
in one flat grid ordered by bottom branch, UI category name, then registered VM
order. One cell fills the space; additional cells use two columns with as many
rows as needed, leaving the right cell blank on an odd final row. Cell titles
match their top tabs. Large grids scroll vertically at their minimum cell size.
Double-click a cell to open its individual top tab while
keeping the current bottom branch scope. UI categories and VMs share this grid;
there is no nested UI tab row or separate UI/VM split. Viewer activity is
independent of terminal activity. Locked VM tabs appear normally; unlocked VM tabs are gray and
remain selectable, including running guests left idle between maintenance
commands. The controller publishes that state through the read-only feed;
the viewer never acquires a VM lease. Neither launcher accepts a VM parameter.

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
diagnostics at the printed `/var/tmp/onpc-ui-watch-*/capture.log`. Earlier setup
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
incorrect test API call, a harness crash or missing generated qualification
inputs that the maintained builder can prepare under existing authorization.
Resolve these implementation details without a developer question, preserving
existing inputs and validation guards. A product crash, timeout or failed
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
