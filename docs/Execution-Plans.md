# Execution plans and shared launchers

Use this structure when asked to turn a large job into an execution plan. Create
a short master plan, one ordered task queue and a separate brief for each
unfinished task, following the [E2E queue](TestAutomation/E2E-Task-Queue.md).
The master owns the sole next-task pointer; the queue owns order, prerequisites,
completion and a short result note. Each task owns its deliverable and validation.
Link enduring requirements to their existing owners instead of copying them.
Planning, source review and partial progress do not complete execution tasks.

## Plan format

The master declares a checkout-relative queue link and its first unchecked task:

```markdown
Task queue: [Ordered task queue](Example-Task-Queue.md).
Next task: **001 — [First task](Example-Tasks/001.md)**.
```

Use `Next task: none.` after every active row is complete. The queue uses the
following columns; IDs are stable labels, never sort keys:

```markdown
| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 001 | [First task](Example-Tasks/001.md) | Baseline | Finite deliverable | 15–30 min |
| [ ] | 002 | [Second task](Example-Tasks/002.md) | 001 | Finite deliverable | 15–30 min |
```

List dependencies as comma-separated earlier IDs. Every unfinished row links
to an existing regular Markdown brief in the checkout. Keep scheduling exclusions
separate. An optional `## Deferred future work` heading ends the active queue;
rows below it never run automatically. Completed rows need only a plain task
title and, when useful, a short result note after their temporary briefs are removed.
The queue determines task selection; the master pointer is a readable summary.
A stale or missing pointer does not prevent execution. Ordinary plan launchers
keep the selected task IDs and use their current queue rows and briefs without
comparing content with saved definitions. Newly added unrelated tasks are ignored
until a new run; explicit prerequisite handoffs may extend the planned work.
Parallel removals, reorderings and scope or acceptance edits need no approval,
change report or reconciliation. Removed tasks are skipped without completion
credit; surviving tasks use their current definitions. A completed row stays
complete without reopening its brief, reports or validation.

Each brief includes `Acceptance: installed`, `Acceptance: host`,
`Acceptance: review` or `Acceptance: reconciliation` on its own line. Installed
briefs also declare `Targets: canonical-name, other-canonical-name`. These
existing metadata fields select the task's checks; they do not require archival
proof. The task reports the actual result for each declared target; use an empty
check target only when no targets are declared. Include purpose, finite scope,
prerequisites, necessary reading/implementation routes, expected results and
cleanup. Mark planned selectors as
unimplemented until registered. Keep indivisible installed histories together;
split independent large work before execution without reducing acceptance.

### Accepted evidence lifetime and historical recovery

A task is responsible for its own validation and owned cleanup before marking
its row `[x]`. Once marked done, it is done. Launchers and later agent sessions
select the next unchecked task and trust completed prerequisites.

Keep only the normal queue status, short result/handoff and current checkpoint
needed to resume interrupted work. Do not automatically collect or publish proof
bundles, preserve every turn, rewrite historical report links, run evidence
preflights or start acceptance-renewal sessions. A missing, expired or rotated
report never reopens a completed task or blocks the next task. A later code
change needs its own affected checks within the current task, not renewal of
historical completion.

Normal test output and useful failure diagnostics retain their existing bounded
storage. Ownership, input safety, cancellation, cleanup and Git transaction
recovery still apply to active operations. None requires an archive of previous
task results.

The legacy `plan_evidence`, evidence inventory/link readers and bundle/recovery
APIs remain available for explicitly requested archival inspection or repair.
Their identity, permission and integrity checks apply only to that requested
operation. They are optional tools, not launcher/task completion dependencies;
new launchers and session prompts must follow this same completion policy.

## Execution and delegation

At the start of every agentic session, including coordinators, workers, monitors,
advisers and reviewers, activate this goal using Codex's `/goal` command:

```text
/goal Simple, lean, robust, do not overenginering. If a problem can be solved by simplier approaches, do not use more complex ones
```

The launcher must set the session's actual Codex goal state, using the supported
goal API when running noninteractively; inserting the command as literal prompt
text does not satisfy this requirement. Apply it to every fresh session,
including continuations, repairs and retries, while preserving the selected
task's scope, acceptance and existing session limits.
Goal state requires a persistent thread: shared CLI sessions omit `--ephemeral`,
and interactive sessions use `thread/start` with `ephemeral: false`. Both
transports instruct the agent to inspect `get_goal` and activate the objective
with `create_goal` before task work; delegated assignments carry
the same setup requirement. Activation failure stops the session through its
existing blocker/error route instead of falling back to advisory prompt text.
Activation happens inside the assigned turn: setting an active goal on an idle
thread can start an automatic turn before the launcher supplies its task.
History-list recording and memories remain disabled; sessions still start with
fresh context and do not resume previous conversations. Complete the goal when
the bounded assignment has been verified, before its final handoff.

Read repository instructions, the master, the selected brief and only applicable
owning contracts/source. The shared coordinator prompt supplies the validated
checkout-relative master, queue and selected brief paths. Use those exact paths;
resolve other document links relative to their containing document rather than
guessing filenames from titles or launcher names. Preserve pre-existing changes
and useful current results. Apply [source discovery](Approval-Tools.md#source-discovery-before-reads)
before reading unverified source/test paths. Execute
the first unchecked task through implementation, its scoped checks, owned cleanup
and close-out. Trust checked prerequisite rows; do not inspect their old reports. A blocker keeps its row unchecked and its pointer unchanged. Record
the concrete blocker and return condition; do not silently skip it. Propose a
bounded prerequisite insertion before its consumer when new work is discovered.
The ordinary-plan driver accepts only a contiguous new unchecked prerequisite
block immediately before that unfinished consumer, with backward dependency
links, unchanged existing completion/order/scope and completed owned cleanup.
The consumer's Requires chain must include every new prerequisite, preserving
its previous dependencies; this insertion is the sole exception to preserving
that field during ordinary close-out.
The structured `prerequisite_required` handoff suspends the consumer and resumes
its retained work after those prerequisites pass, including across restarts.
Only an explicit `prerequisite_required` response expands the selected work;
a `continue` response does not discover or admit added tasks. It preserves the consumer's exact
handoff, acceptance, session counts and protected work; suspension earns no task
completion or extra allowance. Invalid insertions return to the original
coordinator under the existing response-recovery contract.
Other queue and acceptance edits are consumed directly by ordinary launchers;
they do not trigger snapshot comparisons or a change-acceptance log.

Drive subagents using **GPT-6.1 Sol with appropriate reasoning efforts** as needed
to divide and conquer. Prefer lower-effort agents for routine monitoring and
coverage refreshes: Low for read-only monitoring, Medium for settled routine
implementation or coverage maintenance, High or above for difficult diagnosis,
security, concurrency, ownership and independent review. Give bounded assignments,
explicit paths and disjoint write ownership. Keep one editor for shared state.
The coordinator owns task selection, resource/VM ownership, acceptance and
close-out; join and close workers before handoff or releasing resources. A
subagent's report is evidence to assess, not automatic acceptance.
Generated coverage-summary maintenance uses `tools/generate_test_coverage.sh`;
its collection follows the [runner inspection contract](../tests/README.md#aggregate-execution-and-reconnection),
which remains available while tests are running.

Launcher coordinators use persistent threads for goal state, while every helper
starts with fresh context. On every `spawn_agent` call, explicitly set
`fork_turns="none"`; never omit it or use `"all"`. Supply a self-contained helper
assignment with the exact scope, paths, relevant instructions, current evidence
and write ownership. The shared launcher injects this requirement for workers,
monitors, advisers and backend reviewers in both CLI and interactive sessions.
Existing delegation and model policies still apply.

Each derived launcher owns its coordinator default and escalation policy.
For product backend code involving core functionalities, the model, effort and
consultation requirements in
[AGENTS.md](../AGENTS.md) take precedence over ordinary-plan coordinator and
subagent defaults. Delegate scoped implementation or review to appropriately
configured subagents when the coordinator or routine `plan_worker` defaults do
not meet those requirements.
The mandatory independent **Astra xHigh** review for core backend changes applies
across **all launchers**, including repair, recovery and optimization. The shared
`detached_launcher.agent_command` injects this instruction and configures a
read-only `backend_reviewer` role, so a new launcher inherits the mandate while
choosing its own coordinator model and effort. Resolve actionable findings and
revalidate material revisions before completion. No review is required by this
exception for changes outside core backend code. Review supplies no acceptance
credit and changes no generic implementation, consultation or escalation policy.
`write-e2e` and `fix-tests` retain their existing
[model ladders and specialized execution contracts](../tests/README.md#scripted-repair-loop).
Their existing consultation/repair boundaries still apply; reusable infrastructure
does not move acceptance or resource ownership into an observer or worker.

Run the lowest effective maintained checks required by the current task,
including installed journeys when the behavior requires them. Keep customer
checks separate from engineering probes and preparation. Do not weaken
expectations to pass; follow [failure handling](../tests/README.md#handling-test-failures).
Report meaningful failures and unresolved work in the normal handoff.

## Common launcher interface

```sh
tools/execute-plan --plan 'docs/Example.md' --check
tools/execute-plan --plan 'docs/Example.md' --tasks 2
tools/execute-plan --plan 'docs/Example.md' --tasks 0
tools/execute-plan --plan 'docs/Example.md' --reload
tools/execute-plan --plan 'docs/Example.md' --stop
```

`--tasks N` limits completed tasks in this run. Zero and negative values mean
all remaining tasks. A larger positive limit warns and finishes successfully
when the queue is exhausted; the launcher never invents tasks to fill the limit.
On attachment, an explicit `--tasks` **replaces** the active run's total limit;
omitting it keeps that limit. Lowering a limit never interrupts accepted ongoing
work. Plan launchers and `write-e2e` default to one task; `fix-tests` defaults to
its complete selected repair/verification queue. In `fix-tests`, one task is a
category pass; an unfiltered verification `all` pass is one composite task.
Repair sessions and retries do not complete additional tasks. Its existing
`--resume` preserves passed categories and original selectors.

Plan launchers and `write-e2e` stop between sessions with `--stop`.
`fix-tests` and `run-tests` retain their cooperative cancellation semantics.
Fresh ordinary-plan observers paint their startup panel before loading the saved
queue/checkpoint, then reuse that screen when the backend starts. Ctrl+C retains
signal-based cancellation during startup; chat input starts when the owner is ready.
Closing an observer terminal detaches. Repeating the command reconnects to
the same owner and retained checkpoint; model defaults do not change an active
run. Attachment and `--stop` use the master's stable checkout-relative path and
remain available while its contents or queue are incomplete; `--check` and fresh
execution still validate the plan. A fresh plan run automatically resumes unfinished work, including accepted
Git close-out and interrupted validation. It allows five more task implementation
sessions for that task; attaching never renews this allowance. Ordinary-plan
coordinator repairs use a separate allowance of **three sessions per task**.
Git reconciliation and rejected response correction consume only that repair
allowance. Report expiry causes no repair session. Normal task continuations
consume only the implementation allowance. Both kinds retain unique turn identities
and count toward total coordinator activity, but grant no task completion.
The repair count survives reloads, fresh runs, prerequisite suspension and reviewed
reconciliation; none resets or replenishes it. Capacity retries keep the original
session's kind and charge neither allowance again. An exhausted allowance stops
with the exact retained handoff rather than skipping the task.
Older checkpoints retain their original charges; an absent repair counter starts
at zero without guessing or refunding historical turn classifications.
For an explicitly requested manual replan, first commit the reviewed master,
queue and unfinished briefs, preserving unrelated work. Use
`tools/execute-plan --plan 'docs/Example.md' --reconcile RUN --check` to inspect
the exact inactive retained run, then omit `--check` to adopt that queue.
Dedicated ordinary-plan wrappers expose the same option. This route preserves
the original checkpoint in its existing retained allocation and carries forward
unfinished task handoffs and session counts. It executes no task, changes no
Git content and grants no acceptance. Existing task order, scope and dependencies
remain protected; added tasks must be unchecked. A previously accepted task may
be acknowledged only when its matching passing result and cleanup are retained
and its completion is already recorded in the committed queue. Pending Git
transactions and active owners must finish first. This explicit administrative
operation retains its own guards; ordinary execution consumes current definitions
without requiring it.

For explicitly reviewed consolidation of equivalent unfinished tasks, the same
route accepts repeated `--merge-task 'OLD=KEEP'` declarations and
`--reconcile-base FULL_COMMIT`. The base must be an ancestor commit whose master,
queue identities, completion, scopes and dependencies match the retained queue.
Only the declared unchecked source rows may disappear, into earlier unchecked
destinations; a source with a retained handoff cannot be removed. Surviving order
and unrelated scopes remain fixed. Dependencies must map through the declared
merges, and combined acceptance must retain the original kind and union of all
targets. Each combined brief retains every original queue Scope verbatim.
The reconciliation checkpoint retains the original briefs/scopes for that
administrative operation. Ordinary execution follows the current combined brief.
This option grants no acceptance, completion or session-count reset.

Run the explicit merge command with `--check` first, then omit `--check` to adopt
it. Reconciliation preserves the exact prior checkpoint in its existing run
before atomic publication and verifies the adopted state through the ordinary
restart guards. It can also recover an older cancelled session still marked
in flight only when the inactive run has the exact zero-completion cancellation
result, caller-owned cancellation/cleanup markers, no agent response/error and
an empty nested-owner record. Other interrupted sessions retain their refusal;
never edit checkpoints or clear ownership records manually.

Ordinary plans, `write-e2e` and `fix-tests` share response recovery in
[`launcher_runtime.py`](../tools/launcher_runtime.py). A successful agent session
with missing/malformed JSON or a rejected handoff/acceptance/queue transition
returns to its coordinator after owned cleanup. The latest rejected response and
exact guard failure remain in the run allocation and corrective prompt. Recovery
keeps the task's handoff and counters. Ordinary plans use current queue and brief
definitions, while specialized launchers retain their own baseline policy. Ordinary plans use the
separate three-session coordinator repair allowance above; `write-e2e` and
`fix-tests` retain their existing session allowance. Recovery grants no completion
credit, promotion or allowance reset.
Stop/cancellation remain effective between attempts. Repeated rejection ends at
the applicable session cap with a resumable checkpoint and diagnostic handoff.
An explicit `--reload` requests fresh launcher code in an active run. Saved source
edits alone never trigger interpreter replacement. The ordinary-plan controller
reloads at the next session boundary with the result and handoff retained,
before admitting another task, waiting for an answer or spending another session
under stale code. This includes a valid `continue` response: another coordinator
session in the same controller cannot load changed controller code. After owned
cleanup, a fresh interpreter replaces the controller under the same ownership
lock, run identity, observer connection and scratch leases. Reload continues
the exact live checkpoint without replaying startup comparisons against edited
task, queue or acceptance metadata or reinterpreting its processed handoff.
Normal result and close-out validation still apply at their ordinary boundaries.
Reload preserves task/session counts, session caps, suspended consumers, answers,
capacity retry state and live task limits; it allocates no new retention slot and
grants no extra work. Stop and cancellation still take precedence. A failed reload
retains a resumable failure. Manual restarts also consume the current queue and
briefs without comparing their definitions with old snapshots.

The shared `--reload` option applies to ordinary plans and their dedicated wrappers,
`fix-tests`, `write-e2e`, `sync-whatsnew`, `run-tests` and its direct `run-unit-tests`
observer. Use the same plan/VM/scope
selection as for attachment. It keeps the terminal attached to the existing run;
when idle the flag is ignored and ordinary startup applies. It does not cancel work,
reset allowances or replay an observer's original task limit. Bare `fix-tests
--reload` requests both active repair scopes before following them.
Existing observers check the shared request while their owner is active.
[`launcher_bootstrap.py`](../tools/launcher_bootstrap.py) is the stable trampoline:
it only runs the entry point, lets an observer reload unwind its contexts, and
replaces the interpreter. Shared request and descriptor handling lives in
[`launcher_reload.py`](../tools/launcher_reload.py); observer reattachment lives in
[`launcher_observer.py`](../tools/launcher_observer.py), outside the bootstrap.
The fresh observer follows the exact retained run directly; it never replays
the launch command, reapplies `--tasks`, selects work or starts a new backend.
Its display rebuilds from retained output and progress. Unsent input, partial
keyboard/paste sequences, edited answers and active selections defer replacement
until finished or cleared. Terminal modes are restored before replacement;
reload adds no completion recap and does not cancel the owner. Internal test-frame
forwarders stay under their existing supervisor. Controllers reload only after
their admitted operations and cleanup finish. Ordinary plans and E2E implementation
retain session/task checkpoints; repair pipelines drain to retained boundaries before
their coordinator reloads; translations finish and retain their current batch.
The test scheduler stops admitting jobs, joins active work, saves completed cases
and reloads with the original selectors and checkpoint. Cancellation takes precedence;
cleanup/audit failures retain a failed result rather than being hidden by reload.
Subsequent supervisors import current code. Bootstrap edits require reattachment, as do observers
started before this support was installed. An observer reload/import failure
leaves the backend running and its retained result available for reattachment.
A controller import failure ends that owner with an incomplete result and its
last checkpoint retained for manual recovery.

Requests are asynchronous: “reload requested” confirms publication, not completed
replacement. A pipeline waiting for controller reload has retained its boundary;
the coordinator still waits for the other admitted pipelines and cleanup.
Owners started before this request protocol was installed cannot consume it;
finish or stop them through their existing interface, then start current code.
Reload keeps activity and scratch descriptors and an existing single-VM checkout
helper alive across exec. Drained VM workers retain their checkpoints and repair
source fence; their successors use the original selectors and same-run budgets.

Reload is not checkout isolation. Already-imported modules stay in memory until
their controller boundary, but fresh supervisors, test workers, dynamic imports
and installed helpers resolving this checkout can read saved edits immediately.
One admitted operation can therefore use code from more than one revision.
Finish coherent edits before requesting reload; the flag cannot refresh code
already loaded by an active child or undo work it has completed. No file watcher,
source snapshot or per-file hot-patching protocol is involved.

Capacity recovery applies to every launcher-owned model session: ordinary plans,
`fix-tests`, `write-e2e` (including optimization), `sync-whatsnew`, and worktree
conflict resolution. The shared runtime owns the retry policy. Ordinary plans
retain their checkpointed controller recovery; other workflows use the shared
supervisor without spending another task, repair, optimization or batch slot.
An explicit capacity-failed turn returns to the same task and logical session
after supervisor and nested cleanup.
Retry the configured model after delays of 5, 10, 20, 40 and 80 seconds. If all
five retries fail with that same capacity code, a GPT-6.1 Sol session gets one
final attempt on `gpt-6-astra` at the **exact same reasoning effort**. The model
override applies only to that session; the next session, including a continuation,
answered blocker or rejected response, starts with the workflow's configured
model again. Translation helpers follow their coordinator's temporary model;
other workflows retain their explicitly configured adviser/worker roles.
No fallback is inferred for other configured models. Exhausting
the retry sequence or the single Astra attempt stops with a retained handoff.
Capacity attempts share one task-session slot and have their own finite counter;
they do not exhaust or renew the task's normal session allowance. Each attempt
reconciles partial work and retained results against current task definitions
and protected work, and grants no completion.
Ordinary-plan checkpoints retain failure details for recovery of partial task edits;
other supervisors retain the provider error and current prompt in their existing run.
Every manually resumed launcher starts a new session on the configured default model
and effort, with a fresh capacity retry sequence; it never resumes an old
fallback model or waits for the previous controller's retry deadline. Automatic
ordinary-plan controller reload preserves the current logical session and capacity retry sequence.
Cancellation remains effective during every delay. Ordinary plans additionally
honor boundary stop and controller-source changes during backoff; other supervisors
finish the bounded logical session before their worker honors a boundary stop.
Interactive sessions require the exact structured
`serverOverloaded` provider code. Batch `codex exec` omits that code from its
terminal error, so only a failed process with a terminal `turn.failed` carrying
the exact provider message `Selected model is at capacity. Please try a different model.`
may substitute for the code. A different explicit code overrides that message.
Arbitrary output, partial message matches and unexplained process exits cannot
trigger retry. Successful owned cleanup is required before every retry.
Provider refusals, other failed agent processes, missing grants, ownership/cleanup
failures and Git close-out failures retain their explicit stop/recovery policies;
they are never converted into automatic response retries.
If a completed structured response survived before its acceptance checkpoint,
the ordinary-plan driver validates it against the current task and targets,
queue and cleanup requirements before resuming Git close-out. It completes owned
nested cleanup first and counts the recovered task against the new run's limit;
it starts no new model session for an already valid completion. Changed scope,
dependencies and acceptance declarations do not themselves refuse recovery.
A fresh controller also revalidates a previously rejected completion when its
exact response survives in the inactive run, including after the session cap.
The response must match that run's rejection reference and have no agent-error
record. Every current acceptance, queue and cleanup guard still applies; an
invalid or mismatched response keeps its corrective handoff. Recovery preserves
the original checkpoint, queue baseline and session counts.

If Codex rejects a turn with `cyberPolicy`, execution stops without automatically
retrying or changing models, prompts or permissions. Ordinary plan launchers
retain the provider's reason in `agent-error.json`, the checkpoint and handoff;
the unfinished task receives no acceptance credit. For a suspected false positive,
report it through Codex `/feedback`. For authorized security work requiring
Daybreak, resolve access for the identity, workspace or API project and product
surface in use before resuming; follow the
[official OpenAI guidance](https://learn.chatgpt.com/docs/cyber-safety).
Resume through the same launcher after resolution, preserving the saved task and
finishing any interrupted work and owned cleanup.

Plan-driven launchers use the same terminal layout: tasks overview at top left, plan
totals at top right, execution details and optional input at bottom left, current
task summary and status/issues at bottom right. Task entries in the
overview and task summary use bold task labels, such as `Task 4-5c:`.
The bottom-left transcript and prompt use the shared
[`SessionPanel`](../tools/launcher_session.py) component. Other launcher surfaces
can embed it in their own location without the plan overview or status columns.
The shared supervisor publishes session identity, model/effort and lifecycle in
`session-view.json`, and a bounded current-session `session-output.log`, inside
the existing owned run. These display artifacts carry no execution or acceptance
authority and retire with that run. Plan and repair sessions use the shared
conversation input throughout work, including steering the active agent and
answering pending developer decisions. Prompts entered between repair sessions
queue for the next agent in the displayed workflow.
The repair launcher's lower-left area additionally splits current pipeline status
from tabbed output, initially 1:2. Its draggable divider uses the shared ratio
and scrolling controls and retains the chosen proportion across terminal resizing.
**Active (Session)** and **Session** share the current session transcript and
chatbox; without an active session, **Session** shows `No active session` and
**Active (Launcher)** shows launcher output with the composer available between
sessions. **Launcher** shows output only. Click the tabs or use Alt+1/2/3. Session
discovery and input stay scoped to the attached workflow and its VM pipelines.
The top-left overview is at most five terminal rows high, including wrapped
lines, and shrinks further in short terminals. All overview content scrolls
together with the mouse wheel; click it to direct Page Up/Page Down there.
It reuses the bottom-left panel's scrollbar rendering and controls: a dim track
and draggable thumb, track clicks, and a pinned **↓** button to return to the
newest rows. Both panels hide these controls during native terminal selection.
It starts at the bottom and follows the newest rows until scrolled upward;
returning to the bottom resumes following. It has no `Tasks:` summary count.
Completed task entries in the top-left overview start with a green `✓`
checkmark and use green text.
The title is followed by one space and the task's elapsed duration in parentheses,
using the shared minute/hour format: `✓ Task title (12m)` or `✓ Task title (1h 12m)`.
Observers normalize completed rows retained by older backends to this green
checkmark format and remove the old `— complete` suffix. When an old row has
no recorded elapsed time, show `(duration unavailable)`; never fabricate timing.
Single-task E2E runs publish the same completed recap as multi-task runs.

Below the current task summary's separator, a bold `Explanation:` header precedes
the short plain-language purpose. Another separator precedes bold `Last Error:`
and `Status:` labels, with a blank line between the two fields. The last error
summary is red, followed by its elapsed age in parentheses, for example `(12m ago)`;
with no reported error, show a normal
`-` and no age. Errors belong only to the current task and retain their original
timestamp across retries, suspension, observer reconnections and backend restarts.
The age refreshes every minute without requiring new output. The status value is
exactly one of the following. With no last error, it is always blue `Running`:

| Status | Text color |
| --- | --- |
| Running (no last error) | Blue |
| Investigating | Blue |
| Root cause identified, fixing | Blue |
| Testing fix, previous error point not reached yet | Yellow |
| Testing fix, previous error point passed | Green |

Blue status values and the elapsed age use explicit blue (`#0098ff`) so terminal
palette settings cannot render them gray. The `Status:` label keeps its normal color.
The status is followed by its age in parentheses, such as `Running (12m ago)` or
`Investigating (1h 12m ago)`, using the shared minute/hour duration formatter.
Its clock resets only when the status value changes and refreshes every minute
without requiring new output. Task-local status timestamps survive retries,
suspension and observer reconnections. For older backends or non-agent workflows
without a retained timestamp, the observer measures from its first observation
of the current task/status.

Plan/E2E coordinators report a short `last_error` once per new occurrence and
update `status` through `LAUNCHER_STATUS` commentary. The launcher supplies the
error timestamp; repeated old failures must not reset it. Testing statuses require
evidence about the previous error point, not merely starting an unrelated test.

`fix-tests` uses the same metadata, validation and panel clocks, scoped to each
round/category. Its controller records each failed run once; repair agents update
their explanation and investigation/fixing status through the same commentary
protocol. Before corrective verification the controller sets the yellow testing
status, and a passing selected run sets green while retaining the last error and
its age. Diagnostic execution alone grants no verified-fix status. Moving to a
different category or round selects its own metadata and clocks.

Before launching the test or retry that verifies a fix at the previous error point,
the coordinator sends `Testing fix, previous error point not reached yet` in a
separate `LAUNCHER_STATUS` commentary before the verification tool call. Keep
that yellow status through setup, earlier steps and waiting for evidence that
the previous error point passed; do not leave the panel on fixing during that run.
Report `Testing fix, previous error point passed` only after observing that
evidence. A changed fix needing fresh verification returns to yellow before its
retry, even if an earlier candidate passed that point.
These fields are presentation only and never acceptance evidence. Conversation
lifecycle notices and developer questions appear separately from the status value.
Valid `LAUNCHER_STATUS` metadata is omitted from the general transcript and
descriptive output. Natural-language text following its JSON object is preserved
in both outputs, including when it follows on the same line.
Below `Status:`, a horizontal separator introduces the latest agent session's
descriptive output. This duplicates the agent's natural-language messages from
the full bottom-left transcript, excluding command activity such as `Ran …`,
`Explored …` and `Wrote …`, tool results, file changes, plans and developer input.
The descriptive pane follows new messages and has independent wheel scrolling
and a draggable scrollbar when its retained output exceeds the available space.
Click the pane to direct Page Up/Page Down to it. Scrolling it leaves the task
summary, explanation, error/status fields and full transcript in place. New
messages preserve a scrolled reading position; reaching the bottom resumes
following. Reconnection restores the bounded descriptive history, and each new
agent session starts an empty history. Sessions predating this feature leave
the pane empty; never infer prose by filtering rendered command output.
Plan/E2E sessions offer conversation input; repair offers input
for developer decisions; `run-tests` has no agent sessions or composer.
The retained run counter `Tasks: x/y/z`, included in plain output and the exit
recap, counts completed, unfinished and total tasks
in this run against the run's task limit; an active task remains unfinished
until completion. Unfinished is the total minus completed, with a minimum of zero.
For zero or negative `--tasks`, z is the number completed
in this run plus the remaining tasks, so an unlimited run shows a numeric total.
Plan/E2E observers read remaining counts from the current queue, including when
reconnecting to a backend started before numeric totals were recorded.
The conversation composer uses a light gray background with dark text across
its full textbox, including padding and border, like the standard agent chatbox.
Below the textbox, show the current session's model name and reasoning effort
(for example, `gpt-6.1-sol high`) in the same dim font as the former keyboard hint,
replacing `Enter: send · Shift+Enter: newline`. Read these values from the session
state so observer reconnection preserves them; leave unavailable values blank.
The conversation composer shows a blinking underscore cursor at the current
insertion position, including while another pane is selected or output scrolls.
Hovering over its text area requests an I-beam mouse pointer in terminals that
support pointer shapes.
While the agent works, the composer border shows `Working (duration)`, refreshing
every second even without output. This clock measures the active turn, survives
observer reconnection and resets on continuation after interruption or a reply.
The indicator disappears while waiting, interrupting, cleaning up or finished.
The Plan/E2E right-panel session line shows only the session number and elapsed
clock time, for example `Session [1]: 2m`, refreshing every minute even without
new output: `12m` below one hour, then `1h 0m`, `1h 12m`, and so on.
The clock starts with each session, survives observer reconnection and stops
when the session finishes.
The top and lower splits share one 75:25 width ratio. Dragging either vertical
divider resizes both frames together; their dividers stay aligned during dragging
and terminal resizing. The top-right `Total Tasks: x/y/z` shows completed
tasks in green, unfinished tasks in explicit grey (`#808080`) and the total in
the normal text color.
Displayed counters use the shared count styling function, overriding retained ANSI
colors so completed and unfinished counts stay distinct.
These counts cover the plan's entire active queue, excluding deferred future
work, regardless of `--tasks`. Completed is the accepted completion count from
the retained run counter plus tasks completed before this run; both counters use
the same budget snapshot. A queue checkbox edited during a session or pending
Git close-out grants no completion credit in either counter. The total refreshes
as the active queue changes, and unfinished is total minus accepted completions.
Displays without a Markdown plan show unavailable counts as dashes.
Below the counts, `Total Duration` shows elapsed time for the backend launcher
in the same minute/hour format. It refreshes every minute and continues across
tasks and observer reconnections. Each new backend process resets this clock;
previous backend runs never contribute elapsed time.
The live layout uses the terminal's alternate screen, keeping the shell prompt
and shell scrollback outside the launcher. Mouse controls are enabled on attachment:
the wheel scrolls the pane under the pointer, the output pane has its own
draggable scrollbar and **↓** returns to the newest output. Scrolling output
leaves the overview, totals, task summary and composer fixed. No F2 switch is
needed to start scrolling. The terminal's scrollbar does not control these panes.
Drag text with mouse controls enabled to select within the starting panel.
Selection and copied text stop at its boundaries, including the vertical divider;
releasing the drag sends the selected text to the clipboard through OSC 52.
The terminal must support and permit OSC 52 clipboard writes. Wide characters
and combining marks remain intact. Output arriving during a drag does not change
the text being copied; resizing cancels the selection. A click without a drag
does not replace the clipboard. Scrollbars and divider drags retain their controls.
`F2` releases the mouse for native terminal selection, Ctrl+Shift+C and the
terminal's right-click menu; press `F2` again to restore pane controls. Native
selection, including the terminal's selection modifier, belongs to the terminal
and can cross panel boundaries. Non-chat displays also accept `m` outside a pending
question. Page Up/Page Down remain available for keyboard pane scrolling in either mode.
The live panes keep bounded history; the retained run log remains the complete
output source. On exit, the launcher restores the shell and input/cursor modes,
then appends the saved run log to native terminal scrollback for later copying
and browsing. Its final recap starts with the full top-left tasks overview:
the pinned counter and task summaries in their displayed order, including entries
hidden by pane scrolling or terminal size. This recap follows the log replay and retains
the overview's completion checkmarks, durations, colors and bold task labels.
On every exit, regardless of the reason, append these two lines after the
summaries, including when no task summary is available:

- **Ended:** `hh:mm`, using local time with a two-digit 12-hour clock.
- **Duration:** elapsed time, such as `1h 12m`, using the shared
  [`clock_duration`](../tools/launcher_display.py) formatter and the backend's
  start clock used by `Total Duration`. Older backends without that clock use
  elapsed time since observer attachment.

When the entire execution-plan queue finishes successfully, append a final banner
after the recap and timing: `QUEUE COMPLETE` in bold green uppercase, with one
green line of `=` characters above and below it, each matching the message's
character length. The bottom border is the last output line.
Plain output retains the banner text without terminal styling. Task limits,
stops, cancellation and failures do not count as queue completion.

Only the `Ended:` and `Duration:` labels are bold terminal text; their values
use normal weight. Cancellation, exceptions and handled termination signals
retain this footer after terminal restoration; uncatchable termination cannot
run exit cleanup.
Pipes receive the same final recap as plain text and retain the same owner/result
semantics.

`--check` validates a plan and every unfinished brief without model sessions, VM
operations or Git changes. The shared ordinary-plan driver first pulls the current
branch's configured upstream with `git pull --no-rebase --ff --no-edit --no-autostash`,
then stages the accepted task's explicit owned paths plus its master and queue, commits them as
`TA: Completed task ID`, runs `git push` using the checkout's existing
remote and branch configuration, and completes
[shared worktree propagation](#shared-worktree-propagation). Both `execute-plan` and `reliability-plan`
inherit this policy. Only successful Git close-out counts the task against the
run limit and permits selecting the next task. The controller owns task commits
and pushes. If a pull changes HEAD, encounters merge conflicts or needs local
edits reconciled, the same task returns to its coordinator before any completion
commit. Resolve conflicts, complete any upstream merge, preserve unrelated work
and original staging, and re-run acceptance whose inputs changed. The coordinator
may use bounded Git reconciliation commands for that handoff; it never creates
the task completion commit or pushes. A subsequent close-out pulls again.
The same repair loop handles owned files changing after staging and before a
commit is written, preserving those edits and renewing affected acceptance.
Late response/queue validation and changed branch/upstream ownership also return
to repair, retaining any written commit and its original pull identity. Recovery
must restore that identity; observing another owner grants no adoption authority.
Harmless additional response/check metadata is ignored; required result fields,
passing checks and cleanup remain mandatory.
Existing staged or unrelated work is excluded; conflicting ownership stops
close-out with a retained checkpoint. A retained dirty-file baseline no longer
protects a path when its exact captured contents are now committed in HEAD;
new task edits on that path can close out normally, including after restart.
An already clean path whose working contents, executable mode and index match
HEAD is also released, even when its committed contents have advanced beyond
the captured baseline. Retained checkpoints do not lock clean files to an older
version. Release these clean paths from inherited and suspended baselines before
each agent session, including the first session after restart or a reviewed replan,
before the task can edit them.
Uncommitted baseline contents and pre-existing staged paths remain protected.
An ownership overlap returns the same task to its coordinator with the accepted
result and exact conflicting paths retained, before any pull or staging. Correct
an overbroad close-out path list without dropping required edits. If ownership
still cannot be established, preserve the baseline and return blocked with the
required developer decision or original-owner action; never adopt that work
merely because a later commit touched the same file.
Content-only file fingerprints omit executable mode, so release also requires a regular
working file with HEAD's executable mode; ambiguous deletion/type/mode changes
remain protected for explicit reconciliation.
Pull transport/configuration, staging,
commit or push failures retain the accepted result; a fresh run retries close-out
without repeating unaffected acceptance
or creating a duplicate completion commit. Missing upstream configuration or
credentials is a close-out failure; the launcher never changes Git configuration.
Commit recovery checks the retained branch and upstream before pushing. A legacy
pending commit without that identity requires explicit Git reconciliation.
The shared Git helper checkpoints the verified completion commit identity.
Recovery can reuse that exact commit after HEAD advances, provided it remains
an ancestor and its parent, subject, owned paths and committed entries still
match the saved intent. Legacy propagation checkpoints supply the same pinned
identity. Later task edits stay untouched and earn no acceptance credit.
E2E retains its own Git and optimization workflow.
Already-running backends keep their original policy; attaching does not reload
code or defaults. Stop at a session boundary and start a fresh run to load a
changed policy. Tasks completed by an older review-only backend are not
retroactively committed by restart; preserve their changes for explicit close-out.

## Shared worktree propagation

After a launcher pushes a task, optimization or verified repair commit, shared
Git infrastructure propagates that exact commit to every other branch listed in
[`config/worktree.json`](../config/worktree.json). Entries in `worktrees` are
branch names. Checked-out branches resolve through Git's registered worktree
inventory; exclude the current checkout by its resolved path. This is symmetric:
with `main` and `worktree` configured, either checkout merges its completed work
into the other.
Additional configured worktrees receive the same change. A checkout without this
configuration has no propagation destinations. A branch without a local checkout
uses its configured remote upstream, or the same branch name on the sole matching
remote when no upstream is configured. A detached checkout remains untouched.
Missing or ambiguous remote destinations, existing Git operations or missing
upstreams on checked-out branches refuse with an actionable retained checkpoint;
the launcher never creates local branches or changes Git configuration.

Remote destinations use a detached worktree inside the retained run allocation.
The controller fetches the remote branch, merges the exact completion commit and
pushes explicitly to that remote branch without force. Remote-only commits are
preserved, and conflicts use the same unattended resolver as checked-out targets.
The checkpoint retains checkout and remote identities across interruption; the
temporary worktree is removed after its push succeeds. Unchecked local branches
are left at their existing commits. Every configured destination must finish
before task completion.
If a remote branch advances before push, a non-fast-forward rejection triggers
a checkpointed refetch and merge in the same detached checkout, followed by a
normal push. Recovery resumes interrupted merges and preserves both histories.
Any conflicts enter the same unattended resolver before the controller commits
the merge or retries the push; unresolved conflicts prevent completion.
At most five push attempts run per invocation; other push failures retain the
transaction immediately.

This boundary is shared by ordinary-plan launchers, `write-e2e` (including its
optimization commits), and `fix-tests`. Every committing launcher must use
`launcher_git.commit_push_propagate()` for the entire commit, source push and
destination propagation operation. Commit creation and propagation helpers are
private to the shared Git module; launchers must not import or call them or
implement separate commit/push sequences. A repository regression check enforces
that private-helper boundary. There is no commit-only or push-disabled close-out
option. Callers retain acceptance, staging and source-pull policy, while the
shared operation owns the repository-wide lock and resumable Git writes.
It adds no propagation operation to
read-only checks or launchers that do not commit and push. Task completion and
selection of further work wait until every destination has been pushed.

For each destination, the controller records its branch, upstream, original
HEAD and a unique stash identity. It stashes staged, unstaged and untracked work
with `git stash push -u` when needed, fetches and merges its configured upstream,
and merges the source completion commit. The destination's active changes stay
outside these merges and their commits. It restores that exact stash with its
index state before pushing the destination. Restoration uses apply followed by
identity-checked drop after a successful push, providing the effect of stash pop
with recoverable write boundaries. An exact restoration permits stash retirement.
Restoration is rechecked after restart and before push or stash retirement, even
at an unchanged HEAD. New checkpoints retain the verified restored content, index
and modes, including resolved overlapping paths; older checkpoints retain their
original unaffected-path verification.
If unaffected content, index or modes differ, the controller reports the affected
paths to the existing restoration resolver before push. A recovery stash alone
does not establish restoration. Unresolved mismatches preserve current work and
the original stash without granting completion. Descendant commits remain intact;
paths changed by those commits require the resolver's preservation review rather
than an obsolete snapshot comparison.
Existing stashes remain untouched.

Merge and stash-restoration conflicts start supervised, unattended GPT-6.1 Sol
High resolution turns in the affected destination, using the shared agent and
cleanup infrastructure. No developer question is required. The resolver combines
both branches' intended changes, preserves destination active work (including
partial staging and untracked files), and validates affected behavior. It never
chooses ours/theirs wholesale, commits active work, force-pushes or drops a stash;
the controller owns merge commits and pushes. Incomplete resolutions continue
automatically for up to five turns; exhausted resolution, failed validation,
transport, credentials or hooks retain the transaction and stash without
granting completion.
Destination test runs register against the live source launcher and its exact
propagation checkpoint, while retaining destination-specific cleanup ownership.

One repository-wide lock covers source Git close-out and propagation, serializing
reverse-direction updates before either source writes its completion commit.
Competing close-outs wait unattended, with cancellation still available.
Checkpoint each destination's stash, fetch, merges, restoration, push and stash
retirement. Restart reuses the source task commit and completed destinations,
including when the source HEAD has advanced to a descendant of that exact commit;
an interrupted stash application is inspected by the automatic resolver before
any replay. Changed checkout/branch/upstream identities preserve pending work and
refuse unsafe recovery. Conflict resolution checks branch, upstream and ancestry
before and after each turn, including incomplete turns. A descendant destination
HEAD retains the propagated commit and continues automatically, keeping the
original stash when present, including during push recovery. Before restoration,
such advancement goes to the existing resolver instead of blindly applying the
stash over newer work. A rewritten or unrelated HEAD still refuses.
After reviewing the newer commits and resolving the original active work, an
inactive ordinary-plan run supports `--reconcile RUN --propagation-head FULL_HEAD`.
Run it with `--check` first, then without `--check`. It requires one pending
destination at restoration/push, its unchanged branch/upstream and configured
checkout, the exact reviewed HEAD containing both recorded commits, no pending
Git operation, and the original identity-recorded stash still present. It archives
the exact checkpoint before pinning the reviewed HEAD for controller-owned push.
It leaves plan acceptance, task/session counts and Git content unchanged and keeps
the original stash after push. This explicit acknowledgement follows review; mere
ancestry does not prove preservation of active work. Ordinary restart retains its
ancestry and restoration guards. The option cannot be combined with queue revisions.
Existing running backends require a fresh run
to load this policy.

## Reviewed plan splits

For an explicitly requested split, use `--reconcile RUN --split-plan PATH`
with `--reconcile-base FULL_COMMIT`. The base must be an ancestor whose master,
queue identities/completion, scopes and dependencies match the retained checkpoint.
The destination must be a committed, inactive, unstarted ordinary plan containing
exactly the original unchecked tail in order, with unchanged scopes, brief paths,
acceptance kinds and targets. Tasks with retained handoffs cannot transfer.
The source keeps its master/queue identity, surviving order/completion and
dependencies; new source prerequisites must remain unchecked.

The destination declares `Baseline plan: [Title](source-master.md).` and
`Baseline task: FINAL_ID.` on separate lines. Its first brief must explicitly
verify that source gate and applicable retained installed results before work.
The split validates those declarations and replaces the tail's external
dependency with that gate; the coordinator owns the evidence check. No task or
acceptance is granted by the declarations alone.

Previously reviewed scope reallocation in the surviving unfinished rows requires
one explicit `--revise-task ID` per changed Scope; no other Scope may change.
Review their receiving owners and full assertions before invoking this exception.
Retained active/suspended metadata must still match the base acceptance/targets.
If an older base committed a surviving row before its brief was tracked, use
that surviving task's reviewed committed declaration while preserving its exact
retained active/suspended acceptance metadata. A transferred brief must always
exist in the original base; this exception cannot establish its missing targets.
This exception does not apply to ordinary restart, merge reconciliation or task
close-out. The original checkpoint is archived before atomic adoption, with its
rejected results, handoffs, counters, completion status and Git ownership preserved.
The destination checkpoint is never created or copied.

A rejected structural handoff can enter this route only with the exact retained
non-completion response, owned cleanup and no agent error. The original rejection
is retained in the archived checkpoint and suspended work; a pending completion,
Git transaction, active owner or uncertain cleanup still refuses. `--check` first
validates without adoption; omit it only after review and committed planning inputs.
Retrying the identical operation verifies the retained receipt and resume guards.

```sh
tools/execute-plan --plan 'docs/Source-Plan.md' --reconcile RUN --split-plan 'docs/New-Plan.md' --reconcile-base FULL_COMMIT --revise-task ID --check
```

## Extension boundary

Use composition with small policy objects and presentation strategies. Avoid a
single state machine containing every task type's acceptance branches.

Presentation has two extension levels: the shared `WorkflowView` supports custom
launchers, and its `ExecutionPlanView` specialization owns all plan panel wiring.
Every execution-plan launcher, including `write-e2e`, supplies its checkout and
master plan to that specialization. It inherits the same layout, queue totals,
task/session labels, live timing, suspension display, completion overview and
observer reload identity. The shared progress infrastructure publishes compact
completion rows for both normal and recovered close-out. Individual plan engines
own task data, session descriptions and accepted completion boundaries; they do
not implement panel formatting or wiring. Thin plan entry points supply only
`PlanWorkflow` configuration. Non-plan launchers such as `fix-tests` use the base
presentation strategy directly and can customize their layout and progress.

| Shared component | Responsibility | Customization |
| --- | --- | --- |
| [`launcher_bootstrap.py`](../tools/launcher_bootstrap.py) / [`launcher_reload.py`](../tools/launcher_reload.py) / [`launcher_observer.py`](../tools/launcher_observer.py) | Stable interpreter trampoline, explicit reload requests and observer reattachment | Exact run, label and plan projection; never workflow admission |
| [`execution_plan.py`](../tools/execution_plan.py) | Markdown selection, dependency/pointer and completion guards | Master/queue paths, task briefs and acceptance metadata |
| [`plan_launcher.py`](../tools/plan_launcher.py) | Resumable ordinary-plan session driver | Immutable `PlanWorkflow`: name, plan, model/effort, session allowance, VM selection, Git policy |
| [`launcher_runtime.py`](../tools/launcher_runtime.py) | Common options, locked task budget and live limit changes | Worker defines an accepted task boundary and default budget |
| [`detached_launcher.py`](../tools/detached_launcher.py) | Owner locks, detached sessions, supervised transport, nested-test cleanup, following | Worker command, validated namespace, lifecycle callbacks |
| [`launcher_view.py`](../tools/launcher_view.py) / [`launcher_display.py`](../tools/launcher_display.py) / [`launcher_progress.py`](../tools/launcher_progress.py) | Synchronized panels, input routing, task formatting and durable completion rows | `ExecutionPlanView`: checkout/master data with shared plan wiring; `WorkflowView`: custom progress, layout options, questions and composer for other launchers |
| [`launcher_session.py`](../tools/launcher_session.py) | Shared session transcript/composer layout, editor and caret geometry | Host supplies viewport, transcript, session state and authorized input callback; usable in a plan pane or a dedicated watch terminal |
| [`launcher_git.py`](../tools/launcher_git.py) / [`launcher_worktrees.py`](../tools/launcher_worktrees.py) | Upstream reconciliation, literal paths and mandatory commit/push/propagation close-out with recovery | Workflow owns source-pull policy and commit scope; shared Git owns commit, push, destination discovery, stash/merge/restore, automatic conflict resolution and recovery |

The current adapters use these components according to their workflow:

| Launcher | Shared infrastructure | Execution input and retained engine |
| --- | --- | --- |
| `write-e2e` | Task options/budgets, detached supervision, `ExecutionPlanView`, shared plan progress, Git and queue reader | E2E master, ordered queue and briefs through its specialized acceptance, model and optimization engine |
| `fix-tests` | Task options/budgets, detached supervision, display and developer questions | Selected suite inventory, verification rounds and failure handoffs through its repair engine; no Markdown task plan |
| `run-tests` | Ownership lock primitives, output following, display, storage and retention | Selected suite inventory through its scheduler and test checkpoints; no Markdown task plan, agent composer or `--tasks` option |
| `execute-plan` | Ordinary plan driver, task options/budgets, detached supervision and display | Caller-selected master, ordered queue and briefs through `PlanWorkflow`; shared per-task commit and push |
| `reliability-plan` | The same ordinary plan driver and shared lifecycle | [VM reliability](Reliability-Plan.md), with registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |
| `kiosk-desktop` | The same ordinary plan driver and shared lifecycle | [Unrestricted graphical desktop prevention](Kiosk-Desktop-Plan.md#execution), with its own master-path namespace, registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |
| `kiosk-prompt-new` | The same ordinary plan driver and shared lifecycle | [Remaining confinement improvements](Kiosk-Session-Confinement-New-Plan.md#execution), with its own master-path namespace, registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |

Run `tools/reliability-plan --check` to validate its plan, or
`tools/reliability-plan --tasks 0` to execute its remaining queue. It defaults to
one task and supports the same `--vm`, attachment and `--stop` controls. The
generic `execute-plan --plan 'docs/Reliability-Plan.md'` entry shares its owner
and checkpoints. Installed briefs retain their explicit acceptance targets even
when a diagnostic invocation narrows VM selection.

Run E2E plans through `write-e2e`; their task-specific acceptance metadata and
close-out rules remain with the E2E contracts. `execute-plan --check` validates
ordinary plans, not the specialized E2E brief format.
The maintained E2E [host consistency checks](TestAutomation/E2E-Execution-Contracts.md#completion-and-document-cleanup)
validate its master, queue, briefs and scenario bindings.

A new ordinary plan needs Markdown and a thin wrapper constructing `PlanWorkflow`,
or the generic `execute-plan --plan` command. Specialized state machines such as
E2E acceptance and test repair compose the same ownership, budgets, Git and
presentation pieces while retaining their purpose-specific rules. New adapters
must preserve identity, cancellation, retention and current-task result guards and cover
their own interruption/recovery boundaries. Plan namespaces are hashes of the
master's checkout-relative path under the shared storage allocator, keeping
independent plans separate and competing invocations of one plan serialized.

Repository operations still follow [Approval tools](Approval-Tools.md),
[test maintenance](../tests/README.md), and applicable
[VM](Mandates/VM-Mandate.MD), [UI](Mandates/UI-Automation-Mandate.MD) and
[storage](Mandates/Test-Storage-Mandate.md) mandates. Launcher reuse grants no
new product installation, publication, privileged operation or discard authority.
