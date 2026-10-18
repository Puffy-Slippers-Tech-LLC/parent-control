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
link, including older checkpoints; every other row field remains protected.

Each brief includes `Acceptance: installed`, `Acceptance: host`,
`Acceptance: review` or `Acceptance: reconciliation` on its own line. Installed
briefs also declare `Targets: canonical-name, other-canonical-name`. Include
passing acceptance evidence for every declared target, regardless of acceptance
kind; use an empty check target only when the brief declares no targets. Include
purpose, scope, prerequisites, exact reading/implementation routes, finite
validation, expected results, cleanup and close-out. Mark planned selectors as
unimplemented until registered. Keep indivisible installed histories together;
split independent large work before execution without reducing acceptance.

## Execution and delegation

Read repository instructions, the master, the selected brief and only applicable
owning contracts/source. Preserve pre-existing changes and valid evidence. Execute
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
It grants no completion credit. Other structural edits or changed acceptance
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

Each derived launcher owns its coordinator default and escalation policy.
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
Closing an observer terminal detaches. Repeating the command reconnects to
the same owner and retained checkpoint; model defaults do not change an active
run. Attachment and `--stop` use the master's stable checkout-relative path and
remain available while its contents or queue are incomplete; `--check` and fresh
execution still validate the plan. A fresh plan run automatically resumes unfinished work, including accepted
Git close-out and interrupted validation. It allows five more coordinator
sessions for that task; attaching never renews this allowance. An exhausted
session allowance stops with a retained handoff rather than skipping the task.
Ordinary plans, `write-e2e` and `fix-tests` share response recovery in
[`launcher_runtime.py`](../tools/launcher_runtime.py). A successful agent session
with missing/malformed JSON or a rejected handoff/acceptance/queue transition
returns to its coordinator after owned cleanup. The latest rejected response and
exact guard failure remain in the run allocation and corrective prompt. Recovery
keeps the original task, queue and acceptance baseline and uses the existing
session allowance; it grants no completion credit, promotion or extra sessions.
Stop/cancellation remain effective between attempts. Repeated rejection ends at
the normal session cap with a resumable checkpoint and diagnostic handoff.
Provider refusals, failed agent processes, missing grants, ownership/cleanup
failures and Git close-out failures retain their explicit stop/recovery policies;
they are never converted into automatic response retries.
If a completed structured response survived before its acceptance checkpoint,
the ordinary-plan driver revalidates it against the retained task, targets,
queue and cleanup requirements before resuming Git close-out. It completes owned
nested cleanup first and counts the recovered task against the new run's limit;
it starts no new model session for an already valid completion. A changed scope,
dependency, acceptance declaration or unrelated completion still refuses recovery.

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
overview and task summary use bold task labels, such as `Task 4-5c:`; the
top-left counter also uses bold `Tasks:` with normal-weight numeric counts.
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
The top-left `Tasks: x/y` counts completed tasks in this run plus one against
the run's task limit. For zero or negative `--tasks`, y is the number completed
in this run plus the remaining tasks, so an unlimited run shows a numeric total.
Plan/E2E observers read remaining counts from the current queue, including when
reconnecting to a backend started before numeric totals were recorded.
The conversation composer uses a light gray background with dark text across
its full textbox, including padding and border, like the standard agent chatbox.
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
tasks in green, unfinished tasks in blue and the total in the normal text color.
These counts cover the plan's entire active queue, excluding deferred future
work, regardless of `--tasks`, and refresh automatically as the queue changes.
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
and browsing. Its last output is the full top-left tasks overview: the pinned
counter and task summaries in their displayed order, including entries hidden by
pane scrolling or terminal size. This recap follows the log replay and retains
the overview's completion checkmarks, durations, colors and bold task labels.
Pipes receive the same final recap as plain text and retain the same owner/result
semantics.

`--check` validates a plan and every unfinished brief without model sessions, VM
operations or Git changes. The shared ordinary-plan driver first pulls the current
branch's configured upstream with `git pull --no-rebase --ff --no-edit --no-autostash`,
then stages the accepted task's explicit owned paths, commits them as
`TA: Completed task ID`, and runs `git push` using the checkout's existing
remote and branch configuration. Both `execute-plan` and `install-coverage`
inherit this policy. Only successful Git close-out counts the task against the
run limit and permits selecting the next task. The controller owns task commits
and pushes. If a pull changes HEAD, encounters merge conflicts or needs local
edits reconciled, the same task returns to its coordinator before any completion
commit. Resolve conflicts, complete any upstream merge, preserve unrelated work
and original staging, and re-run acceptance whose inputs changed. The coordinator
may use bounded Git reconciliation commands for that handoff; it never creates
the task completion commit or pushes. A subsequent close-out pulls again.
Existing staged or unrelated work is excluded; conflicting ownership stops
close-out with a retained checkpoint. Pull transport/configuration, staging,
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
| `install-coverage` | The same ordinary plan driver and shared lifecycle | [Core installation coverage](TestAutomation/Core-Installation-Coverage-Handoff.md), with registered VM selection and a GPT-6.1 Sol High coordinator; shared per-task commit and push |

Run the core installation queue with `tools/install-coverage --tasks 0` to finish
all remaining tasks, or omit `--tasks` for one task. Its `--check` and `--stop`
use the common interface above. The dedicated wrapper and `execute-plan --plan`
share the master's namespace and checkpoints; they cannot start competing owners.

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
