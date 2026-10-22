# Execution plans and shared launchers

Use this structure when asked to turn a large job into an execution plan. Create
a short master plan, one ordered task queue and a separate brief for each
unfinished task, following the [E2E queue](TestAutomation/E2E-Task-Queue.md).
The master owns the sole next-task pointer; the queue owns order, prerequisites,
completion and concise evidence. Briefs own finite deliverables and acceptance.
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
rows below it never run automatically. Completed rows may link to retained
evidence after their temporary briefs are removed.
The selected row's Estimate cell is planning/close-out bookkeeping: it may be
updated with timing or concise evidence without changing Scope or Requires.
Shared transition and restart guards normalize that cell and the selected task
link, including older checkpoints. They also permit destination-only repairs of
simple inline Markdown evidence links in the Estimate cells of tasks already
complete in the retained queue baseline. Link labels, surrounding evidence text,
timing, link count and every other predecessor field remain protected; unfinished
rows receive no such exception. Compare both the saved and current structures
using the retained completion baseline, without rewriting checkpoints.

Before repairing an expired evidence link, verify that its replacement retains
the same result, exact inputs/scope and cleanup record. Prefer a verified retained
bundle or accepted result and its command log over a short-lived report link.
A destination repair changes no acceptance or completion and needs no manual
replan, metadata commit or `--reconcile` operation. Broader wording, task, scope,
dependency or order changes still follow the explicit reconciliation contract.
Do not recreate an expired report or suppress a link failure to avoid that
contract. If a running controller predates this rule, preserve its queue baseline
and record the verified replacements in the current brief; return `continue`
for a fresh controller at the session boundary under the restart rule below.

Each brief includes `Acceptance: installed`, `Acceptance: host`,
`Acceptance: review` or `Acceptance: reconciliation` on its own line. Installed
briefs also declare `Targets: canonical-name, other-canonical-name`. Include
passing acceptance evidence for every declared target, regardless of acceptance
kind; use an empty check target only when the brief declares no targets. Include
purpose, scope, prerequisites, exact reading/implementation routes, finite
validation, expected results, cleanup and close-out. Mark planned selectors as
unimplemented until registered. Keep indivisible installed histories together;
split independent large work before execution without reducing acceptance.

### Accepted evidence lifetime and historical recovery

Before an ordinary plan closes an accepted task, the controller preserves its
selected plan/queue/brief inputs, exact result, prompt, command record, referenced
reports and owned-cleanup record through the shared verified bundle publication.
The plan namespace has its own bounded publication journal, separate from model
sessions and ordinary artifact exports. Each generation carries forward all
previous accepted proof within the existing limits; missing or changed proof and
budget exhaustion refuse close-out. The stable `accepted-evidence.json` locator
names the verified bundle and original members. Selected queue evidence links
and verified destinations in previously completed rows move to that locator
only after verification, retaining their labels and claims. Unfinished consumers
remain protected. A locator alone is no acceptance.
Publication recovery verifies the committed payload and publishes its matching
locator before retiring recorded older generations. Ordinary session and export
rotation remains bounded and unchanged.
Every fresh controller carries exact active and suspended task inputs, including
an unpublished accepted result's command and cleanup records. Failed startup
retries its recorded allocation before admitting another retention slot; changed
identities and exceeded budgets refuse while preserving the previous owner.

When an original report has rotated, an exact original member in an explicitly
selected, fully verified bundle can supply its proof. Live sources still undergo
the normal ownership, identity and conflict checks. If referenced proof is absent,
the controller preserves the exact rejected result and session records, then
returns to the coordinator to renew affected acceptance within the existing
session allowance. Task/queue baselines, targets, suspended work and Git ownership
remain protected. This recovery does not adopt unknown allocations, recreate
expired reports or forgive integrity failures; unfinished Git transactions still
refuse renewal.
Continuations, blocked decisions and prerequisite suspension retain the exact
renewal source across controller restarts until renewed proof is published and
verified; a non-completion handoff never releases that evidence.
The shared bundle reader resolves explicit plan references under its authorized
identity, including root-private target sources through the authenticated helper.
It reports exact missing references separately from ownership, permission and
integrity failures; only that missing-reference result enters renewal. Mandatory
controller records and previously accepted publications remain strict inputs.

Where detailed historical proof is already lost, destination-only repair cannot
make a stronger claim than the retained record supports. A selected recovery
brief may contain one finite `plan-evidence-recovery` JSON request, binding its
exact task/acceptance, protected checkpoint baseline, queue bytes, retained
developer authorization and exact before/after evidence links. A fresh inactive
controller verifies the request and bundle provenance before applying it. The
route permits only explicit completed-row proof-loss disclosures and verified
destination repairs for completed rows or suspended consumers. Disclosures retain
the original label with ` — detailed proof unavailable; retained accepted
completion`; they grant no missing check result or new acceptance.

The controller retains the exact original checkpoint, queue claims and
authorization before atomic publication, then updates only the corresponding
saved evidence cells. Completion, relative order, Scope, Requires, task identity,
acceptance, session counts and Git ownership remain protected. Interrupted
publication resumes only its exact recorded transaction. This route needs no
agent commit, competing launcher, manual checkpoint edit or general replan.
Ordinary transition guards remain strict. An agent preparing such a request for
a controller that predates the repair returns `continue`, leaving its task open
until the fresh controller applies the request and live acceptance passes.

## Execution and delegation

Read repository instructions, the master, the selected brief and only applicable
owning contracts/source. The shared coordinator prompt supplies the validated
checkout-relative master, queue and selected brief paths. Use those exact paths;
resolve other document links relative to their containing document rather than
guessing filenames from titles or launcher names. Preserve pre-existing changes
and valid evidence. Execute
the first unchecked task through implementation, required acceptance, owned cleanup
and close-out. A blocker keeps its row unchecked and its pointer unchanged. Record
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
The controller also recognizes the same valid insertion in a `continue` response
after owned cleanup and advances automatically, without spending a corrective
session solely to change the response status. It preserves the consumer's exact
handoff, acceptance, session counts and protected work; suspension earns no task
completion or extra allowance. Invalid insertions return to the original
coordinator under the existing response-recovery contract.
Other structural edits or changed acceptance
declarations refuse with the retained handoff for reconciliation; they are never
silently adopted as a weaker task.

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

Launcher coordinators are ephemeral and have no stored conversation rollout to
fork. On every `spawn_agent` call, explicitly set `fork_turns="none"`; omitting it
or using `"all"` can fail with `no rollout found`. Supply a self-contained helper
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

Run the lowest effective maintained checks and every task-required installed
history. Keep customer acceptance separate from engineering probes and preparation.
Do not weaken expectations to pass; follow
[failure handling](../tests/README.md#handling-test-failures). Retained evidence
must match the candidate, exact scope and required cleanup. Preserve useful
historical results and schedule invalidated histories explicitly.

## Common launcher interface

```sh
tools/execute-plan --plan 'docs/Example.md' --check
tools/execute-plan --plan 'docs/Example.md' --tasks 2
tools/execute-plan --plan 'docs/Example.md' --tasks 0
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
Fresh ordinary-plan observers paint their startup panel before validating saved
plan evidence, then reuse that screen when the backend starts. Ctrl+C retains
signal-based cancellation during preflight; chat input starts after publication.
Closing an observer terminal detaches. Repeating the command reconnects to
the same owner and retained checkpoint; model defaults do not change an active
run. Attachment and `--stop` use the master's stable checkout-relative path and
remain available while its contents or queue are incomplete; `--check` and fresh
execution still validate the plan. A fresh plan run automatically resumes unfinished work, including accepted
Git close-out and interrupted validation. It allows five more coordinator
sessions for that task; attaching never renews this allowance. An exhausted
session allowance stops with a retained handoff rather than skipping the task.
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
transactions and active owners must finish first. Ordinary restart guards remain
unchanged; this explicit operation is not an automatic structural override.

For explicitly reviewed consolidation of equivalent unfinished tasks, the same
route accepts repeated `--merge-task 'OLD=KEEP'` declarations and
`--reconcile-base FULL_COMMIT`. The base must be an ancestor commit whose master,
queue identities, completion, scopes and dependencies match the retained queue.
Only the declared unchecked source rows may disappear, into earlier unchecked
destinations; a source with a retained handoff cannot be removed. Surviving order
and unrelated scopes remain fixed. Dependencies must map through the declared
merges, and combined acceptance must retain the original kind and union of all
targets. Each combined brief retains every original queue Scope verbatim.
The checkpoint also retains the complete original briefs/scopes and supplies
them whenever the combined task runs, including after intervening work or a
prerequisite suspension. Original assertions remain required; current combined
briefs replace former single-target scheduling and queue close-out instructions.
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
keeps the original task, queue and acceptance baseline and uses the existing
session allowance; it grants no completion credit, promotion or extra sessions.
Stop/cancellation remain effective between attempts. Repeated rejection ends at
the normal session cap with a resumable checkpoint and diagnostic handoff.
If ordinary-plan controller or validation sources change during any session, the
controller stops at the next session boundary with the result and handoff retained,
before admitting another task, waiting for an answer or spending another session
under stale code. This includes a valid `continue` response: another coordinator
session in the same controller cannot load startup recovery changes. A fresh run
loads the repair and applies any exact evidence-recovery request before execution.
An unapplied request prepared during a session also stops the controller at that
boundary, even when no source file changed. Matching an applied request's identity
only avoids an unnecessary restart; startup still owns its full proof and
checkpoint verification.
An explicit `serverOverloaded` failed turn in an ordinary plan returns to the
same task and logical coordinator session after supervisor and nested cleanup.
Retry the configured model after delays of 5, 10, 20, 40 and 80 seconds. If all
five retries fail with that same capacity code, a GPT-6.1 Sol session gets one
final attempt on `gpt-6-astra` at the **exact same reasoning effort**. The model
override applies only to that session; the next session, including a continuation,
answered blocker or rejected response, starts with the workflow's configured
model again. No fallback is inferred for other configured models. Exhausting
the retry sequence or the single Astra attempt stops with a retained handoff.
Capacity attempts share one task-session slot and have their own finite counter;
they do not exhaust or renew the task's normal session allowance. Each attempt
reconciles partial work and retained results against the original queue,
suspended consumers, targets and protected work, and grants no completion.
The checkpoint retains failure details for recovery of partial task edits.
Every launcher restart starts a new session on the configured default model
and effort, with a fresh capacity retry sequence; it never resumes an old
fallback model or waits for the previous controller's retry deadline.
Stop, cancellation and controller-source changes remain effective during the
delay. The exact structured provider code and successful supervisor cleanup
are required; message text or an unexplained process exit cannot trigger retry.
Provider refusals, other failed agent processes, missing grants, ownership/cleanup
failures and Git close-out failures retain their explicit stop/recovery policies;
they are never converted into automatic response retries.
If a completed structured response survived before its acceptance checkpoint,
the ordinary-plan driver revalidates it against the retained task, targets,
queue and cleanup requirements before resuming Git close-out. It completes owned
nested cleanup first and counts the recovered task against the new run's limit;
it starts no new model session for an already valid completion. A changed scope,
dependency, acceptance declaration or unrelated completion still refuses recovery.
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
rechecking prior evidence and owned cleanup.

All launchers use the same terminal layout: tasks overview at top left, plan
totals at top right, execution details and optional input at bottom left, current
task summary and status/issues at bottom right. Task entries in the
overview and task summary use bold task labels, such as `Task 4-5c:`.
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
The Plan/E2E session line appends elapsed clock time, refreshing every minute even
without new output: `12m` below one hour, then `1h 0m`, `1h 12m`, and so on.
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

Only the `Ended:` and `Duration:` labels are bold terminal text; their values
use normal weight. Cancellation, exceptions and handled termination signals
retain this footer after terminal restoration; uncatchable termination cannot
run exit cleanup.
Pipes receive the same final recap as plain text and retain the same owner/result
semantics.

`--check` validates a plan and every unfinished brief without model sessions, VM
operations or Git changes. The shared ordinary-plan driver first pulls the current
branch's configured upstream with `git pull --no-rebase --ff --no-edit --no-autostash`,
then stages the accepted task's explicit owned paths, commits them as
`TA: Completed task ID`, and runs `git push` using the checkout's existing
remote and branch configuration. Both `execute-plan` and `reliability-plan`
inherit this policy. Only successful Git close-out counts the task against the
run limit and permits selecting the next task. The controller owns task commits
and pushes. If a pull changes HEAD, encounters merge conflicts or needs local
edits reconciled, the same task returns to its coordinator before any completion
commit. Resolve conflicts, complete any upstream merge, preserve unrelated work
and original staging, and re-run acceptance whose inputs changed. The coordinator
may use bounded Git reconciliation commands for that handoff; it never creates
the task completion commit or pushes. A subsequent close-out pulls again.
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
E2E retains its own Git and optimization workflow.
Already-running backends keep their original policy; attaching does not reload
code or defaults. Stop at a session boundary and start a fresh run to load a
changed policy. Tasks completed by an older review-only backend are not
retroactively committed by restart; preserve their changes for explicit close-out.

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
rejected results, handoffs, counters, accepted proof and Git ownership preserved.
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

| Shared component | Responsibility | Customization |
| --- | --- | --- |
| [`execution_plan.py`](../tools/execution_plan.py) | Markdown selection, dependency/pointer and completion guards | Master/queue paths, task briefs and acceptance metadata |
| [`plan_launcher.py`](../tools/plan_launcher.py) | Resumable ordinary-plan session driver | Immutable `PlanWorkflow`: name, plan, model/effort, session allowance, VM selection, Git policy |
| [`launcher_runtime.py`](../tools/launcher_runtime.py) | Common options, locked task budget and live limit changes | Worker defines an accepted task boundary and default budget |
| [`detached_launcher.py`](../tools/detached_launcher.py) | Owner locks, detached sessions, supervised transport, nested-test cleanup, following | Worker command, validated namespace, lifecycle callbacks |
| [`launcher_view.py`](../tools/launcher_view.py) / [`launcher_display.py`](../tools/launcher_display.py) | Synchronized overview/totals and execution/status column widths and input routing | `WorkflowView`: progress and plan-total projections, question support and optional composer |
| [`launcher_git.py`](../tools/launcher_git.py) | Upstream pull/reconciliation handoff, literal file paths, worktree fingerprints and commit-intent recovery | Ordinary-plan pull policy, required close-out files and commit message; workflow owns push policy |

The current adapters use these components according to their workflow:

| Launcher | Shared infrastructure | Execution input and retained engine |
| --- | --- | --- |
| `write-e2e` | Task options/budgets, detached supervision, display, Git and queue reader | E2E master, ordered queue and briefs through its specialized acceptance, model and optimization engine |
| `fix-tests` | Task options/budgets, detached supervision, display and developer questions | Selected suite inventory, verification rounds and failure handoffs through its repair engine; no Markdown task plan |
| `run-tests` | Ownership lock primitives, output following, display, storage and retention | Selected suite inventory through its scheduler and test checkpoints; no Markdown task plan, agent composer or `--tasks` option |
| `execute-plan` | Ordinary plan driver, task options/budgets, detached supervision and display | Caller-selected master, ordered queue and briefs through `PlanWorkflow`; shared per-task commit and push |
| `reliability-plan` | The same ordinary plan driver and shared lifecycle | [VM reliability](Reliability-Plan.md), with registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |
| `kiosk-prompt` | The same ordinary plan driver and shared lifecycle | [Kiosk baseline validation for v1.4](Kiosk-Session-Confinement-Plan.md#execution), with registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |
| `kiosk-desktop` | The same ordinary plan driver and shared lifecycle | [Unrestricted graphical desktop prevention](Kiosk-Desktop-Plan.md#execution), with its own master-path namespace, registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |
| `kiosk-prompt-new` | The same ordinary plan driver and shared lifecycle | [Remaining confinement improvements](Kiosk-Session-Confinement-New-Plan.md#execution), with its own master-path namespace, registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |
| `fixture` | The same ordinary plan driver and shared lifecycle | [Host-owned fixture migration](TestAutomation/Fixture-Execution-Plan.md#execution), with its own master-path namespace, registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |
| `export` | The same ordinary plan driver and shared lifecycle | [Test evidence and export infrastructure](TestAutomation/Export-Execution-Plan.md#scope-and-execution), with its own master-path namespace, host-only infrastructure acceptance and a GPT-6.1 Sol High coordinator; shared per-task commit and push |

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
must preserve identity, cancellation, retention and acceptance guards and cover
their own interruption/recovery boundaries. Plan namespaces are hashes of the
master's checkout-relative path under the shared storage allocator, keeping
independent plans separate and competing invocations of one plan serialized.

Repository operations still follow [Approval tools](Approval-Tools.md),
[test maintenance](../tests/README.md), and applicable
[VM](Mandates/VM-Mandate.MD), [UI](Mandates/UI-Automation-Mandate.MD) and
[storage](Mandates/Test-Storage-Mandate.md) mandates. Launcher reuse grants no
new product installation, publication, privileged operation or discard authority.
