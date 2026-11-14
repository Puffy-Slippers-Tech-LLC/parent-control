# Execution plans and shared launchers

Use this structure when asked to turn a large job into an execution plan. Create
a short master plan, one ordered task queue and a separate brief for each
unfinished task using the format below.
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

When generating or revising tasks, make the title itself a short, plain-language
explanation of what the task achieves. Use everyday words understandable without
technical background; keep commands, paths, internal labels and implementation
details in the brief. For example, use `Check that the child locks when time runs out`
for a task about expiry enforcement. Use the same title in the queue link,
master pointer and brief heading, preserving stable task IDs and file paths.
The shared launcher displays this title directly in its overview and current-task
summary; there is no separate task explanation field or section. Shared agent
instructions apply this rule to every execution-plan launcher, including tasks
inserted as prerequisites during a run.

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

The requirements below remain the enforced Codex policy. Codex role assets own
helper profiles. Workflows own escalation timing, overrides, budgets and acceptance.

At the start of every agentic session, including coordinators, workers, monitors,
advisers and reviewers, activate this goal using Codex's `/goal` command:

```text
/goal Simple, lean, robust; do not overengineer. Prefer solutions that simplify the resulting codebase as a whole, not merely minimize the patch. Keep refactoring within the task’s scope.
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
`detached_launcher.agent_command` injects this instruction and requests a
read-only `backend_reviewer` role, so a new launcher inherits the mandate while
choosing its own coordinator model and effort. Native role files currently
inherit the parent sandbox; separately enforced helper isolation and explicit
retirement remain unqualified.
The required read-only and join/close boundaries remain unchanged.
Resolve actionable findings and
revalidate material revisions before completion. No review is required by this
exception for changes outside core backend code. Review supplies no acceptance
credit and changes no generic implementation, consultation or escalation policy.
`fix-tests` retains its existing
[model ladder and specialized execution contract](../tests/README.md#scripted-repair-loop).
Its existing consultation/repair boundaries still apply; reusable infrastructure
does not move acceptance or resource ownership into an observer or worker.

Run the lowest effective maintained checks required by the current task,
including installed journeys when the behavior requires them. Keep customer
checks separate from engineering probes and preparation. Do not weaken
expectations to pass; follow [failure handling](../tests/README.md#handling-test-failures).
Report meaningful failures and unresolved work in the normal handoff.

## Common launcher interface

Shared public launchers and standalone VM tools accept optional `--host NAME`,
using the [shared VM filter](Mandates/VM-Mandate.MD#target-selection).
The narrowed canonical VM names use the existing attachment/resume binding rules.
This option filters VMs only; `--branch` continues to control where the launcher runs.

Public commands using the shared controller accept `--branch NAME`, selecting a
branch from `config/environment.json`. Without it, the matching `launchers` entry's
`default_branch` wins, then the invoking checkout's current Git branch.
The invoking checkout must be on a registered Git branch, whose host is the tool
host. Local placement uses
the branch's `host` and `repo_root`, verifies the branch is already checked out,
and launches the destination checkout's controller there. It never switches Git
branches. Host `enabled` flags govern VM scheduling, not controller placement.
The selected branch's host is the controller host. When it equals the tool host,
the controller runs locally, including on a host labelled `transport: ssh`.
When the hosts differ, placement uses SSH, including when the destination is
labelled `transport: local`. SSH uses the configured host name as a private
OpenSSH alias and its optional `ssh_port` (otherwise OpenSSH selects the port).
It runs the selected checkout's launcher on that host, verifies
the checked-out branch, and pins the destination without reapplying remote
launcher defaults. Arguments are shell-quoted; stdin/stdout/stderr and exit status
travel through SSH without allocating a remote terminal.
Authentication is noninteractive and requires an already trusted host key;
connection failures never fall back to local execution. Run `./setup.sh --server`
on the server and `./setup.sh --connect-server` on the client first. No additional
controller service is needed. Source and credentials remain host-local; dispatch
does not synchronize checkouts or forward the client's environment.
After placement and destination checkout verification, shared controller admission
synchronizes upstream before importing the workflow, host filtering, VM selection
or workflow validation reads the destination configuration. It fetches first,
then uses `git pull --no-autostash` when an update is needed. Synchronization
holds the selected controller family's admission gates, verifies idle kernel
owners, and takes the shared Git transaction lock and exclusive source lease.
Retained repair impact holds and pending recovery do not skip this step.
For a retained source writer, only its original repair's `--resume` may synchronize.
The fence, holds, dirty/staged/untracked edits, checkpoints and accepted results
remain owned by recovery; synchronization neither settles nor transfers them.
With retained repair recovery, startup permits only a fast-forward pull and
refuses before job allocation if Git cannot preserve local work or has an
unfinished operation. Existing Git transaction journals pin their source base:
startup fetches and verifies that source already contains upstream, refusing
before changing HEAD if an update would supersede their recorded recovery.
Ordinary pull failures retain their low-effort recovery agent;
startup requires explicit success and a successful pull retry. Attachments and
controls keep their existing routes without mutating active source. A new job
cannot fall back to stale imports when synchronization is busy.
Independent host/VM scopes can start while another scope is active if a
fetch-only check confirms that their shared source already contains upstream.
It never applies updates over a live controller; an attachment can still use
that owner, while a new job refuses until source can be synchronized safely.
The bootstrap remains a placement-only handoff. When early synchronization changes HEAD,
admission replaces the launcher interpreter before selection, retaining the verified
destination and avoiding a second pull. Controller imports and newly launched jobs
therefore use the synchronized source. Before any potentially mutating pull,
startup durably advances the shared generation without clearing repair fences
or holds and forwards its locks to the Git child, including across controller
death. A fetch that confirms source is current advances no generation.
Valid accepted results remain recovery authority rather than being rerun merely
because the controller was refreshed.
The controller's current working source owns VM execution. Workers on another
host receive isolated source copies, including uncommitted changes, through the
shared [VM source transfer](../tests/integration/Environment.md#shared-vm-configuration).
Shared host identity, checkout validation and SSH construction live in
`tools/host_dispatch.py`; launcher admission lives in the reloadable
`launcher_controller.py`. The stable
public commands return after controller admission. Inspection commands such as
`--help` use the same branch selection and placement rules.
Internal `run-tests CATEGORY --unattended` children stay in their controller's
checkout and retain its activity ownership; public defaults are not reapplied.
Repair-runner invocations carrying `ONPC_RUNNER_INVOCATION` likewise stay in
their repair controller's checkout, so verification executes the repaired source.
The shared detached-controller environment also pins internal `run-tests` calls
to that controller's root, including inventory discovery before a repair
invocation exists. Explicit `--branch` still overrides this internal default.

```sh
tools/execute-plan 'docs/Example.md' --check
tools/execute-plan 'docs/Example.md' --tasks 2
tools/execute-plan 'docs/Example.md'
tools/execute-plan 'docs/Example.md' --reload
tools/execute-plan 'docs/Example.md' --stop
```

`--tasks N` limits completed tasks in this run. Zero and negative values mean
all remaining tasks. A larger positive limit warns and finishes successfully
when the queue is exhausted; the launcher never invents tasks to fill the limit.
On attachment, an explicit `--tasks` **replaces** the active run's total limit;
omitting it keeps that limit. Lowering a limit never interrupts accepted ongoing
work. All shared launchers default to `0`, running all remaining tasks in their
selected queue. In `fix-tests`, a round-1 category or explicitly selected
verification category is one logical task across every selected family and host
work. An unfiltered verification round is one composite task, retained across
fresh passes until clean completion or terminal failure. Fresh selected
verification passes charge their categories again. Family partitions, exact-case
attempts, repair sessions and resumed close-out cost no additional tasks.
Admission is charged once before assignment and completed once when its scope
settles, including failure without passing credit. A limit blocks new tasks while
admitted work and close-out finish; resume retains charged admissions, valid
current-pass results and original selectors. Rounds are run-wide, independent of
the number of VMs; see the [repair loop](../tests/README.md#scripted-repair-loop).

`--add-session N` adds a positive integer to the running launcher's current
task/case session allowance. Use the same plan, scope and VM selection as for
attachment. For example, `tools/execute-plan 'docs/Example.md' --add-session 5`
changes a five-session allowance to ten, and session admission uses ten immediately.
It requires an active allowance; it does not start a launcher or reopen one
that has committed to stopping. Repeated increments accumulate. Grants survive
controller reloads and prerequisite suspension within the same run; a fresh run
keeps its existing budget-renewal policy. Ordinary plans keep implementation and
coordinator repair allowances separate: the increment applies to the currently
displayed kind. It grants no acceptance or task completion credit.

The shared launcher publishes the current used count and computed allowance in
`session-allowance.json`, separately from its controller-owned checkpoint. The
allowance gate serializes increments, publications and ordinary-plan exhaustion
decisions. `fix-tests` publishes its serialized repair's allowance at the parent
controller, including while verification or intervention is pending.
ONPC: Watch uses these values for both **Session x/y** labels and offers
**Add 5 Sessions** in the launcher actions menu. Adding sessions during an
allowance intervention resumes that same task/case without a second grant;
an unrelated developer decision still requires an answer.

Plan launchers stop between sessions with `--stop`.
`--cancel-stop` clears that queued request and exits immediately. The worker
accepts the stop under the same run lock used to cancel it. Once accepted,
cancellation fails with a red “already stopping and is not cancellable” message;
it never removes a committed stop. Existing runs must be restarted with updated
launcher code to support cancellation.
`fix-tests` and `run-tests` retain their cooperative cancellation semantics.
Launcher commands start the detached controller, print a green startup acknowledgement
or a red failure, and exit. The acknowledgement reports admission, not completion.
Repeating a command updates or acknowledges the existing owner without opening a
terminal client. ONPC: Watch can attach at any time for progress, results, questions
and conversation; closing Watch leaves the controller running. Model defaults do
not change an active run. On attachment, `--reload` or `--stop`, omitted `--vm` preserves that owner's VM queue
and concurrency; fresh execution uses the current configured defaults. An explicit
`--vm` must match the active run's binding.
Attachment and `--stop` use the master's stable checkout-relative path and
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
reconciliation; none resets or replenishes it. Only an explicit `--add-session`
grant increases its allowance. Capacity retries keep the original
session's kind and charge neither allowance again. An exhausted allowance stops
with the exact retained handoff rather than skipping the task.
This is a launcher failure: the unfinished task remains unchecked and later
tasks do not start, since they may depend on it. Only `fix-tests` may record an
exhausted case as failed and continue
its independent repair queue; that exception must not enter shared plan execution.
Older checkpoints retain their original charges; an absent repair counter starts
at zero without guessing or refunding historical turn classifications.
For an explicitly requested manual replan, first commit the reviewed master,
queue and unfinished briefs, preserving unrelated work. Use
`tools/execute-plan 'docs/Example.md' --reconcile RUN --check` to inspect
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

Ordinary plans and `fix-tests` share response recovery in
[`launcher_runtime.py`](../tools/launcher_runtime.py). A successful agent session
with missing/malformed JSON or a rejected handoff/acceptance/queue transition
returns to its coordinator after owned cleanup. The latest rejected response and
exact guard failure remain in the run allocation and corrective prompt. Recovery
keeps the task's handoff and counters. Ordinary plans use current queue and brief
definitions, while specialized launchers retain their own baseline policy. Ordinary plans use the
separate three-session coordinator repair allowance above; `fix-tests`
retains its existing session allowance. Recovery grants no completion
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
`fix-tests`, `sync-whatsnew`, `run-tests` and its direct `run-unit-tests`
launcher. Use the same plan/VM/scope selection as for an existing run.
The request returns immediately; when idle the flag is ignored and ordinary startup
applies. It preserves workflow progress and allowances. Bare `fix-tests --reload`
requests both active repair scopes. Shared request and descriptor handling lives in
[`launcher_reload.py`](../tools/launcher_reload.py). Internal test-frame forwarders
stay under their existing supervisor. Controllers reload only after
their owned operations and cleanup finish. VM test coordinators interrupt guest
steps through the [owned interruption route](../tests/README.md#scripted-repair-loop)
instead of waiting for admitted groups to finish. Ordinary plans and E2E implementation
retain session/task checkpoints; repair coordinators join interrupted attempts and
retain their pass, FIFO tickets and source ownership before reloading;
translations finish and retain their current batch.
The test scheduler stops admitting jobs, joins active work, saves completed cases
and reloads with the original selectors and checkpoint. Cancellation takes precedence;
cleanup/audit failures retain a failed result rather than being hidden by reload.
Subsequent supervisors import current code. Watch reads retained state independently.
A controller import failure ends that owner with an incomplete result and its
last checkpoint retained for manual recovery.

Requests are asynchronous: “reload requested” confirms publication, not completed
replacement. A worker waiting for controller reload has retained its boundary;
the coordinator still joins other owned attempts and their cleanup. VM attempts
use the interruption route above; other workflows retain their documented boundaries.
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
`fix-tests`, `sync-whatsnew`, and worktree
conflict resolution. The shared runtime owns the retry policy. Ordinary plans
retain their checkpointed controller recovery; other workflows use the shared
supervisor without spending another task, repair or batch slot.
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

ONPC: Watch owns the interactive launcher interface: task overview, status,
transcripts, conversation, developer questions, controls and retained results.
See the [Watch guide](../vscode/onpc-watch/README.md). Launcher commands have no
terminal display, keyboard editor, mouse handling or output-following loop.
Test invocations inside plan agents, repair supervisors or Make recipes still
wait for their result; their exit status remains the test verdict. Supervised
tests forward progress to their owning controller without a terminal UI.

### Git close-out and recovery

`--check` validates a plan and every unfinished brief without model sessions, VM
operations or Git changes. The shared ordinary-plan driver first pulls the current
branch's configured upstream with `git pull --no-rebase --ff --no-edit --no-autostash`,
then validates the accepted task's explicit owned paths, captured session changes,
and its master and queue, then invokes the repository's
[`$commit` skill](../.agents/skills/commit/SKILL.md) in a supervised GPT-6.1 Sol
High session with the suggested message `TA: Completed task ID`. The adapter's
`commit_helper` profile supplies that pinned
model/effort pair. Its supervised caller checks catalogue readiness before
starting task supervision, retaining the executable check during preparation. Loading
the shared Git modules or doing deterministic Git work requires no agent CLI.
The skill owns
the commit, source push and
[shared worktree propagation](#shared-worktree-propagation). `execute-plan`
inherits this policy. Only successful Git close-out counts the task against the
run limit and permits selecting the next task. The controller delegates Git
close-out to the skill after acceptance. If a pull changes HEAD, encounters merge conflicts or needs local
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
For new close-outs, the commit skill reviews ownership against the retained
session context and commits only this task's changes. Candidate paths and staged
files alone do not establish hunk ownership. Preserve unrelated staged, unstaged
and untracked work, including within shared files; ambiguous ownership blocks
close-out.
A retained dirty-file baseline no longer
protects a path when its exact captured contents are now committed in HEAD;
new task edits on that path can close out normally, including after restart.
An already clean path whose working contents, executable mode and index match
HEAD is also released, even when its committed contents have advanced beyond
the captured baseline. Retained checkpoints do not lock clean files to an older
version. Release these clean paths from inherited and suspended baselines before
each agent session, including the first session after restart or a reviewed replan,
before the task can edit them.
Unstaged baseline contents on paths that were not pre-staged remain protected.
Session changes are captured and checkpointed at each turn's exit, including the
final turn and deleted task briefs, even when the response omits them from
`stage_paths`. Close-out includes captured paths that still differ from the task's
baseline. Restart reuses those recorded candidates rather than attributing later
checkout edits to a finished session.
An ownership overlap returns the same task to its coordinator with the accepted
result and exact conflicting paths retained, before any pull or staging. Correct
an overbroad close-out path list without dropping required edits. If ownership
still cannot be established, preserve the baseline and return blocked with the
required developer decision or original-owner action; never adopt that work
merely because a later commit touched the same file.
When the developer explicitly authorizes review of shared work, the ordinary-plan
control route `--review-ownership RUN --check` returns a token for the current
task, checkout, branch/upstream, HEAD, index, protected baselines and shared file
contents/modes. Review those inputs, then use `--review-ownership RUN --approve TOKEN`
to permit the commit skill to review their hunks. This control operation starts
no workflow, writes no Git data and never rewrites the ownership checkpoint.
It requests a controller reload after the current session and cleanup finish.
The controller must be active; otherwise start the same plan normally and review
its new current run. Approval never transfers between runs.
Changed inputs invalidate the approval before close-out. Original fingerprints
remain protected; approval grants neither acceptance nor ownership. The skill
must omit unrelated candidates/hunks and refuse ambiguous work. It may not
commit pre-existing work merely because its path was approved for review.
Fresh controller imports recover the exact retained accepted result before
charging another repair turn, only when its current row, checks, cleanup and
ownership guards pass. Clean paths need no review exception. Uncommitted skill
retries recheck approval; journaled source commits retain normal Git recovery.
Content-only file fingerprints omit executable mode, so release also requires a regular
working file with HEAD's executable mode; ambiguous deletion/type/mode changes
remain protected for explicit reconciliation.
Pull transport/configuration, staging,
commit or push failures retain the accepted result; a fresh run retries close-out
without repeating unaffected acceptance
or creating a duplicate completion commit. Missing upstream configuration or
credentials is a close-out failure; the launcher never changes Git configuration.
Transient Git transport/service failures use shared backoff: 30 seconds, then
60, 120, 240 and at most 300 seconds between attempts. The retry window ends
three hours after the first transient failure, including time spent in retries;
retried controller-owned network commands are limited to the remaining window.
Healthy initial operations have no new total-duration limit. Commit-skill retries
resume the same durable journal and
pinned commit, preserving accepted work and completed destinations. Cancellation
still stops retry backoff, including boundary pulls and verification fetches.
Explicit permission/authentication denials, missing
configuration, ownership problems and merge conflicts do not trigger outage
retries. Push races retain their existing bounded reconciliation policy.
Commit recovery checks the retained branch and upstream before pushing.
Non-skill commit checkpoints are unsupported and require explicit Git
reconciliation, preserving the checkpoint and saved work before resuming.
The skill keeps a durable per-close-out Git journal under the retained run,
recording its source commit before pushing and the exact pushed HEAD before
destination writes. Restart resumes that journal with the same pinned commit.
The controller independently fetches every configured remote branch and checks
that it contains the pinned commit before accepting completion. If the skill
already returned complete, recovery retries only that independent verification,
using its retained result and journal without starting another commit session.
Verification reports fetch errors separately from missing remote ancestry and
preserves Git diagnostics. Later task edits
stay untouched and earn no acceptance credit.
E2E retains its own Git and optimization workflow.
Already-running backends keep their original policy; attaching does not reload
code or defaults. Stop at a session boundary and start a fresh run to load a
changed policy. Tasks completed by an older review-only backend are not
retroactively committed by restart; preserve their changes for explicit close-out.

## Shared worktree propagation

New launcher close-outs use the repository's
[`$commit` skill](../.agents/skills/commit/SKILL.md) for the full workflow through
`launcher_git.commit_push_propagate()`. The shared boundary retains the repository
lock, accepted task context, branch/upstream identity and configured destinations.
The skill preserves unrelated work and journals Git writes. Merge and saved-work
restoration conflicts, including interrupted restorations, enter the skill's
[automatic resolution procedure](../.agents/skills/commit/references/conflict-resolution.md)
for the source or any destination. Its dedicated resolver may edit affected
product, plan or test files and run the lowest effective affected validation
through maintained launchers under existing authorization and ownership rules.
Changed accepted inputs require revalidation; unchanged acceptance stays valid.
This exception authorizes conflict repair, not another task or changed
expectations. Destination active edits retain their index state and stay outside
completion and merge commits. The journal records resolution and validation.
Only exhausted resolution, unresolved intent/ownership, unauthorized behavior
changes, unavailable permissions/prerequisites or failed pushes stop close-out.
A blocker retains the accepted result and Git journal. Completion requires
verified remote containment on the source and every destination, with the source
checkout on its original branch.
The shared close-out boundary also reports a terminal Git failure to the current
task panel, replacing an earlier passing-test status with the close-out error.
Panel reporting is best effort and must preserve the original Git failure if
the task metadata cannot be read or written.

The following placement rules apply to skill close-outs. Controller
stash/merge/resolver recovery remains in use for safe-boundary pulls;
close-outs follow the skill's ownership and recovery instructions.

After a launcher pushes a task, optimization or verified repair commit, shared
Git infrastructure propagates its pinned pushed HEAD to every other branch listed in
[`config/environment.json`](../config/environment.json). Entries in `branches` declare
`name`, `host` and absolute `repo_root`. The source branch and resolved checkout
must match their declaration. Branches assigned to the same host must be registered
Git worktrees at the declared paths. Each receives the completed change; this is
symmetric in every direction. Branches on other hosts receive remote pushes,
regardless of the host's VM scheduling `enabled` flag. Host names describe branch
placement; they do not initiate SSH operations. A registry without branch entries
has no propagation destinations. A branch on another host
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
If an older run's temporary checkout expires while close-out awaits a push or
stash retirement, recovery recreates the exact recorded merge commit in the
current run and resumes that phase. Remote identity checks and normal push-race
handling still apply; task acceptance and the completion commit are retained.
A missing checkout with unfinished merge work or saved active edits refuses
with a recovery diagnostic rather than adopting or discarding that work.
If a remote branch advances before push, a non-fast-forward rejection triggers
a checkpointed refetch and merge in the same detached checkout, followed by a
normal push. Recovery resumes interrupted merges and preserves both histories.
Any conflicts enter the same unattended resolver before the controller commits
the merge or retries the push; unresolved conflicts prevent completion.
Detached destinations allow at most five push attempts per invocation; other
push failures retain the transaction immediately.

Checked-out destinations use the same bounded refetch/merge retry on a rejected
push. Their restored active edits are saved again through the existing stash
transaction; earlier recorded backup stashes retire only after the new restore
is verified and the push succeeds. Backups already marked for preservation remain.
Source pushes also reconcile a remote advance through a retained self-merge.
The original task commit stays immutable. Its commit intent records the actual
successfully pushed HEAD, including any merge resolution, and propagation uses
that pinned commit. A restart resumes that exact propagation before accepting
completion; it does not repin a transaction with completed destinations.

This boundary is shared by ordinary-plan launchers and `fix-tests`.
Every committing launcher must use
`launcher_git.commit_push_propagate()` for the entire commit, source push and
destination propagation operation. Commit creation and propagation helpers are
private to the shared Git module; launchers must not import or call them or
implement separate commit/push sequences. A repository regression check enforces
that private-helper boundary. There is no commit-only or push-disabled close-out
option. Callers retain acceptance and candidate path validation, while the
shared operation owns the repository-wide lock and supervised skill invocation.
Task completion and
selection of further work wait until every destination has been pushed.

Plan controllers pull their current branch at session boundaries before
new work. Repair controllers pull during fenced startup and before repair turns;
translation controllers pull at startup and between batches. No timer runs and
no pull mutates a checkout during its active child session or tests. Pending
accepted close-out and commit/pull intents retain their existing recovery route.
The shared pull uses the configured upstream with the same recorded stash,
merge and index restoration mechanics, retaining its `upstream_pull` transaction
inside the workflow checkpoint. Clean synchronization uses Git alone. An agent
starts only for merge or saved-work restoration conflicts. Pulls do not push
unpublished local work. An incoming HEAD change requests controller reload before
new work so updated controller code takes effect too.

Remote pushes update branch refs immediately. A physical checkout on another host
receives those updates when its controller reaches a safe pull boundary; an
inactive checkout receives them when its controller starts. No background service
or remote checkout mutation is performed.

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

An older checkpoint may have captured unmerged index stages before stashing.
Those paths require the restoration resolver's preservation review, rather than
recreating an unresolved index. The controller retains the original stash and
pins the reviewed conflict-free content, staging and modes for subsequent checks;
unaffected paths still require exact restoration.

Before a transaction has written its active-work stash, a resumed destination
may adopt a descendant HEAD and refresh its active-work snapshot. Branch and
upstream identity checks still apply. A matching transaction stash retains its
original base; a rewritten or unrelated HEAD still refuses recovery.

Merge and stash-restoration conflicts start supervised, unattended GPT-6.1 Sol
High resolution turns in the affected destination, using the shared agent and
cleanup infrastructure and the adapter's `conflict_resolver` profile.
The current profile remains pinned independently of coordinator overrides.
The resolver's supervised caller likewise checks catalogue readiness before
starting task supervision. Catalogue support does not prove live model access.
No developer question is required. The resolver combines
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
The Launcher output reports synchronization lock waits, acquisition and release,
upstream synchronization, and Git fetch, pull, push, remote lookup, merge, stash,
commit and worktree operations as they start and finish. Command arguments and
captured Git output stay out of these progress messages.
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
tools/execute-plan 'docs/Source-Plan.md' --reconcile RUN --split-plan 'docs/New-Plan.md' --reconcile-base FULL_COMMIT --revise-task ID --check
```

## Extension boundary

Use composition with small policy objects and presentation strategies. Avoid a
single state machine containing every task type's acceptance branches.

Every execution-plan launcher publishes its checkout and
master plan through `publish_plan_view`. Watch owns layout, task/session labels,
live timing, suspension display and completion overview.
Watch's Status tab uses the same plan totals and
duration above the task/session rows for every plan launcher. The shared Session
link shows the current task's session number until completion. Pending questions
inherit flashing status, countdowns and the `+10m` action for timed questions,
including when a fresh run resumes directly into an unanswered blocker.
Shared presentation metadata records the master path and optional explicit queue
in the owned run;
older ordinary-plan runs use their retained queue totals until reattached.
The shared progress infrastructure publishes compact completion
rows for both normal and recovered close-out. Individual plan engines
own task data, session descriptions and accepted completion boundaries; they do
not implement panel formatting or wiring. Thin plan entry points supply only
`PlanWorkflow` configuration. Non-plan launchers such as `fix-tests` use the base
presentation strategy directly and can customize their layout and progress.

| Shared component | Responsibility | Customization |
| --- | --- | --- |
| [`execution_plan.py`](../tools/execution_plan.py) | Markdown selection, dependency/pointer and completion guards | Master/queue paths, task briefs and acceptance metadata |
| [`plan_launcher.py`](../tools/plan_launcher.py) | Resumable ordinary-plan session driver | Immutable `PlanWorkflow`: name, plan, model/effort, session allowance, VM selection, Git policy |
| [`launcher_runtime.py`](../tools/launcher_runtime.py) | Common options, locked task budget and live limit changes | Worker defines an accepted task boundary and default budget |
| [`detached_launcher.py`](../tools/detached_launcher.py) | Owner locks, detached sessions, supervised transport, nested-test cleanup, startup acknowledgement | Worker command, validated namespace, lifecycle callbacks |
| [`launcher_view.py`](../tools/launcher_view.py) / [`launcher_display.py`](../tools/launcher_display.py) / [`launcher_progress.py`](../tools/launcher_progress.py) | Watch projection metadata, status formatting and durable completion rows | Master and queue paths published for Watch |
| [`launcher_session.py`](../tools/launcher_session.py) | Bounded Watch session transcript projection | Watch supplies retained transcript and session state |
| [`launcher_git.py`](../tools/launcher_git.py) / [`launcher_worktrees.py`](../tools/launcher_worktrees.py) | Upstream reconciliation, literal paths and mandatory commit/push/propagation close-out with recovery | Workflow owns safe pull boundaries and commit scope; shared Git owns pulls, commit, push, destination discovery, stash/merge/restore, automatic conflict resolution and recovery |

The current adapters use these components according to their workflow:

| Launcher | Shared infrastructure | Execution input and retained engine |
| --- | --- | --- |
| `fix-tests` | Task options/budgets, detached supervision, display and developer questions | Selected suite inventory, verification rounds and failure handoffs through its repair engine; no Markdown task plan |
| `run-tests` | Ownership lock primitives, output following, display, storage and retention | Selected suite inventory through its scheduler and test checkpoints; no Markdown task plan, agent composer or `--tasks` option |
| `execute-plan` | Ordinary plan driver, task options/budgets, detached supervision and display | Caller-selected master, ordered queue and briefs through `PlanWorkflow`; shared per-task commit and push |

For E2E batches, use ordinary plans whose installed briefs declare their targets
and exact cases. The [E2E implementation guide](../tests/e2e/README.md#verify-edits)
owns composition, scoped qualification and live acceptance in both ordinary
plans and normal coding sessions.

A new ordinary plan needs Markdown and a thin wrapper constructing `PlanWorkflow`,
or the generic `execute-plan PATH` command. Specialized state machines such as
test repair compose the same ownership, budgets, Git and
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
