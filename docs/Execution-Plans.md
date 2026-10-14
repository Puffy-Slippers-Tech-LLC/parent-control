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
`confinement` always uses **GPT-6.1 Sol xHigh**, without escalation.
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
tools/confinement --check
tools/confinement --tasks 1
tools/confinement --tasks 0
tools/confinement --stop
tools/execute-plan --plan 'docs/Example.md' --tasks 2
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

All launchers use the same terminal layout: tasks overview at top left, plan
totals at top right, execution details and optional input at bottom left, current
task summary and status/issues at bottom right. Plan/E2E sessions offer conversation input; repair offers input
for developer decisions; `run-tests` has no agent sessions or composer.
The top-left `Tasks: x/y` counts completed tasks in this run plus one against
the run's task limit. For zero or negative `--tasks`, y is the number completed
in this run plus the remaining tasks, so an unlimited run shows a numeric total.
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
The top and lower splits start at 75:25 with aligned dividers; each divider resizes
independently by dragging. The top-right `Total Tasks: x/y/z` shows completed
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
Native terminal selection requires the terminal's selection modifier while
mouse controls are enabled. `F2` releases the mouse for ordinary drag-to-select,
Ctrl+Shift+C and the terminal's right-click menu; press `F2` again to restore
pane controls. Non-chat displays also accept `m` outside a pending question.
This terminal protocol cannot provide unmodified native selection and application
mouse controls simultaneously. Page Up/Page Down remain available for keyboard
pane scrolling in either mode.
The live panes keep bounded history; the retained run log remains the complete
output source. On exit, the launcher restores the shell and input/cursor modes,
then appends the saved run log to native terminal scrollback for later copying
and browsing. Pipes receive plain output and retain the same owner/result semantics.

`--check` validates a plan and every unfinished brief without model sessions, VM
operations or Git changes. Generic `execute-plan` leaves changes for review.
Confinement retains its existing commit-and-push-after-each-accepted-task policy;
E2E retains its own Git and optimization workflow. Existing staged or unrelated
work is excluded; conflicting ownership stops close-out with a retained checkpoint.

## Extension boundary

Use composition with small policy objects and presentation strategies. Avoid a
single state machine containing every task type's acceptance branches.

| Shared component | Responsibility | Customization |
| --- | --- | --- |
| [`execution_plan.py`](../tools/execution_plan.py) | Markdown selection, dependency/pointer and completion guards | Master/queue paths, task briefs and acceptance metadata |
| [`plan_launcher.py`](../tools/plan_launcher.py) | Resumable ordinary-plan session driver | Immutable `PlanWorkflow`: name, plan, model/effort, session allowance, VM selection, Git policy |
| [`launcher_runtime.py`](../tools/launcher_runtime.py) | Common options, locked task budget and live limit changes | Worker defines an accepted task boundary and default budget |
| [`detached_launcher.py`](../tools/detached_launcher.py) | Owner locks, detached sessions, supervised transport, nested-test cleanup, following | Worker command, validated namespace, lifecycle callbacks |
| [`launcher_view.py`](../tools/launcher_view.py) / [`launcher_display.py`](../tools/launcher_display.py) | Independently split overview/totals and execution/status layout and input routing | `WorkflowView`: progress and plan-total projections, question support and optional composer |
| [`launcher_git.py`](../tools/launcher_git.py) | Literal file paths, worktree fingerprints and commit-intent recovery | Required close-out files and commit message; workflow owns push policy |

The current adapters use these components according to their workflow:

| Launcher | Shared infrastructure | Execution input and retained engine |
| --- | --- | --- |
| `write-e2e` | Task options/budgets, detached supervision, display, Git and queue reader | E2E master, ordered queue and briefs through its specialized acceptance, model and optimization engine |
| `fix-tests` | Task options/budgets, detached supervision, display and developer questions | Selected suite inventory, verification rounds and failure handoffs through its repair engine; no Markdown task plan |
| `run-tests` | Ownership lock primitives, output following, display, storage and retention | Selected suite inventory through its scheduler and test checkpoints; no Markdown task plan, agent composer or `--tasks` option |
| `confinement` | Ordinary plan driver, task options/budgets, detached supervision, display and Git | Confinement master, ordered queue and briefs through `PlanWorkflow`, with fixed Sol xHigh and per-task commit/push |

Run E2E plans through `write-e2e`; their task-specific acceptance metadata and
close-out rules remain with the E2E contracts. `execute-plan --check` validates
ordinary plans such as confinement, not the specialized E2E brief format.
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
