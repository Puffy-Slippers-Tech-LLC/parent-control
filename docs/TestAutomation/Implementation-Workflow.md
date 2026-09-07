# Efficient implementation and continuation

Use this workflow when building unfinished automation. The [master backlog](Test-Automation.md)
owns task order and completion; the [daily guide](../Test-Automation.md) owns test
commands. This workflow replaces the automatic ten-minute handoff rule. Its
purpose is to discard solved, irrelevant context while preserving useful work
and keeping each experiment cheap. It does not relax product acceptance.

## Start with one bounded result

Start from [Continuation.md](Continuation.md). Read `AGENTS.md`, the selected
task's header/active handoff, and the master's selection rules. Recommend the
model and effort and wait for confirmation before implementation, including
when resuming the same task in a new session. After confirmation, for
architecture consult [System-Design.md](../System-Design.md) and
the owning module. Find the relevant specification IDs/sections with `rg`.
Read referenced code and contracts only when they affect the current question.
Do not load the entire specification, all task documents, historical sessions,
or completed acceptance records on every continuation.

State the next observable result, its smallest verification, and an initial
budget in one short paragraph. A slice is one unresolved boundary, one fix plus
its verification, or a batch of cases using an already-proven helper. The
lettered task remains the full acceptance unit; finishing a slice does not
finish its task. Choose a slice expected to need one or two meaningful experiments,
usually 15–30 minutes. These are planning defaults, not completion promises.

## Reassess model and effort at every handoff

**Reevaluate both settings whenever writing a handoff**, based on the next
unfinished slice and the evidence just obtained. Task-header recommendations
describe the initial work; they are fallback defaults only when no current
handoff recommendation exists. The latest applicable handoff recommendation
takes precedence, and [Continuation.md](Continuation.md) must mirror it.

- Recommend a cheaper capable model and/or lower effort when difficult design
  or diagnosis is finished and the remaining slice is routine implementation,
  parameter cases using proven helpers, or documentation.
- Recommend a stronger model and/or higher effort when remaining uncertainty,
  security/concurrency reasoning, or an unresolved design boundary needs it.
  A failed test or long VM wait alone is not evidence that a stronger model is
  needed; identify the reasoning difficulty that warrants the change.
- Evaluate model and effort separately. Choose the least costly available
  combination expected to complete the slice reliably. Record exact settings,
  whether each is lowered, raised or kept, and one short reason relating finished
  work to remaining difficulty. Keeping both still requires a fresh assessment;
  copying the old settings without reassessment does not satisfy the handoff.

Use this compact field in every active handoff:

> **Next-session settings:** `<model>` / `<effort>`; model: lower/raise/keep;
> effort: lower/raise/keep. **Reason:** `<what is now proven and what remains>`.

On a fresh start, use that recommendation for the selected slice. If intervening
changes invalidate it, briefly explain the revised recommendation and update
the handoff and pointer before implementation. Do not revert to a more expensive
task-header default merely because it is listed first. Confirm the resulting
recommendation at each fresh session under
the user's [session loop](../Test-Automation.md#continue-implementation-in-fresh-sessions).
Within that session, confirmation remains valid unless recommending a setting
change. Never claim to switch a model yourself. Preserve machine/VM authorization
across sessions and do not ask the user to repeat information in the standard
prompt. Do not read old transcripts to recover a model approval.

## Keep context small and reset at problem boundaries

- After completing the agreed slice, save its durable conclusion and end the
  session for a fresh chat. A few adjacent parameter cases sharing the same
  proven helper can form one slice. Do not expand a finished slice into an
  unrelated investigation merely because the parent task remains unchecked.
- Ten minutes is a progress review, not an instruction to end the chat. Check
  whether the current hypothesis is yielding evidence and whether older context
  is still useful. A quiet VM wait is elapsed time, not new reasoning work.
- Use roughly 50,000 current-context tokens as a review threshold when that
  telemetry is available. This is a project heuristic, not a model limit or a
  quota. Do not confuse cumulative input/cached tokens with current context.
  If telemetry is unavailable, use a 30-minute review and problem boundaries;
  do not open old session logs just to estimate usage. On a threshold review,
  stop broad reads and finish the current bounded operation, then hand off and
  end the session before another experiment. Do not continue peeling unrelated
  problems in the same growing context. Record a brief reason for an overrun.
- Keep code/log output focused: search first, read relevant ranges, and export
  structured test/failure summaries. Start with about 2,000 output tokens per
  read and widen only for a specific need. Save full diagnostics as safe files;
  do not repeatedly feed whole files, XML, journals, or truncated dumps back
  into the conversation. Never discard necessary evidence to meet this target.
- While a command runs, await its output in bounded intervals and report stage
  changes. Do not spend the wait repeatedly reconsidering unchanged evidence
  or loading the next unrelated problem. Use scripts to summarize routine
  results so a model is needed for a new finding, not every log line.
- Preserve the full command result, including its session ID and exit status.
  A yielded command is still running; poll that session until it exits. Missing
  `result.json`, a busy lease, or an off VM during preparation/shutdown does not
  establish interruption. Before diagnosing recovery or launching another run,
  reconcile the original command's completion and retained result. If its handle
  was lost, inspect that attempt's evidence without assuming it failed.
- A clean handoff means commands have finished, evidence is retained, and the
  guarded runner has completed cleanup. If interrupted, record the exact owned
  running command/session and recovery state; reconnect to that operation,
  rather than launch a duplicate. Do not tear down a useful experiment merely
  to meet a chat timer or leave a live VM for the next chat to reuse.

The default loop ends with a saved handoff and a new session. In Codex CLI,
`/new` creates a fresh chat; `/compact` summarizes earlier turns but is not the
requested new-session handoff. Use it as an alternative only if the user asks
to continue in the same chat. `/resume` reloads the old transcript and `/fork`
copies it, so neither is a context reset. Save the handoff first; these are
user controls, not shell commands an agent should pretend to execute.
[Official command documentation](https://learn.chatgpt.com/docs/developer-commands).
Automatic context compaction is not permission to extend the slice into hours.

## Make every expensive attempt answer a question

1. Identify the first failing boundary and one hypothesis. State the observation
   that would distinguish it from the alternatives. Separate test-helper,
   product, environment, collection and cleanup failures.
2. Verify the parser, selector, collector syntax and failure handling locally
   where possible. Before booting, ensure the attempt will collect the safe
   diagnostics needed whether it passes or fails. Gather independent relevant
   observations in that attempt; do not require another boot for each missing
   log category. Never export credentials or raw authentication terminal data.
3. Run the smallest guarded selection and its prerequisite closure. Until
   [F1](Task-F1.md) exists, use only the implemented controller; never invoke
   guest pytest on the host, invent a selector, or bypass VM guards.
4. Interpret the result and fix the demonstrated cause. First prove one real
   success and one deliberate denial/failure; then one interaction; only then
   expand the matrix. Cases that all fail at a shared prerequisite provide no
   new evidence about their later assertions. Keep existing cases registered.
5. After two expensive attempts on the same blocker, do not launch a third
   speculative attempt. First identify new discriminating evidence or fix the
   missing observability, and validate that locally. Carry the attempt count,
   rejected hypotheses and next observation across handoffs. A fresh chat does
   not reset this limit. If progress needs a design decision or unavailable
   external capability, record the concrete blocker and move only to authorized
   independent work; do not weaken the boundary to make the test pass.

An expensive attempt is a full guarded VM/system/E2E run or comparable build,
not a fast parser/unit check. Preserve the original failure. A corrected-code
run is a new attempt with its own identity; an unchanged diagnostic rerun must
not turn a failed release run green.

## Verify at the right scope

| Work stage | Required verification |
| --- | --- |
| Local edit/diagnosis | Relevant meaningful unit/component checks; prerequisite safety tests before any protected operation. |
| New OS or graphical helper | Host-safe refusal/cleanup checks, then its smallest real success and denial/failure case. |
| Stable batch of variants | Each changed/affected registered case and shared dependency once; both form surfaces where applicable. |
| Lettered task acceptance | All assigned cases/variants plus affected regressions, `make check`, and `git diff --check`; record exact input identities and scope. |
| Documentation-only change | Links, references, consistency, and `git diff --check`; no product/VM tests. |
| Full release acceptance | One current-input `test-all` including all required suites and variants; no historical or selected results substituted. |

Task documents' verification lists describe acceptance, not commands to repeat
after each edit or handoff. Run common checks once after the final code change
in a stable batch; repeat when later edits, failures or dependencies justify it.
Do not rerun unrelated UI, install/reboot, reproducibility or full system suites
merely because a chat restarted. Safety prerequisites still run in isolation
before the operations they protect. A focused result is labeled with its scope;
it never claims a complete system/release pass.

Register shared assertions and scenarios once, linking all requirements/tasks
they satisfy. Reuse their code and current-input evidence when accepting related
implementation work; final release execution still runs every required case.
Group compatible independent validations in a declared continuous scenario,
while retaining separate cases where initial state or interactions differ.
Follow [coverage selection](E2E-Coverage.md#bound-the-matrix-before-expanding-it).

Ordinary acceptance executes each required case once. Repetition needs an
explicit stability/flake question, selected smoke, count and stop condition.
Qualify a new graphical/cleanup transport with three complete smoke attempts;
reuse that qualification until its behavior or environment changes. Do not
repeat whole scenario matrices twice, or impose ten-run loops by default.
For a demonstrated intermittent defect, choose and record a justified number
of independent complete attempts; a finite count is not proof of zero flakiness.

## Handoff format and cost review

Keep one active handoff for the task, normally 200–400 words, in its owning
document. Update that section in place; do not append another narrative at
every checkpoint. Move long historical evidence into a linked record read only
if needed. Preserve the actual logs/artifacts. Include:

- Task/slice, next observable result, and authorized machine/VM scope.
- Mandatory [next-session settings assessment](#reassess-model-and-effort-at-every-handoff):
  exact model/effort, lower/raise/keep decision for each, and a short reason based
  on the remaining slice. Confirmation is required next session.
- Proven facts and existing interfaces to reuse, with file/section references.
- Unresolved hypothesis, attempts spent, rejected explanations and the exact
  next discriminating observation. Do not retell the investigation.
- Changed inputs, focused command/selector and evidence paths/digests; state
  explicitly which edits have not been exercised in the VM.
- Owned process/VM/cleanup state, remaining acceptance and the exact next action.
  Record outstanding operations by their owned identities; never assume that
  a historical “VM off” observation describes current state. If another session
  owns an operation or task, do not duplicate it or overwrite its active handoff.

Then update [Continuation.md](Continuation.md) with the task ID, status, active
handoff link, next slice and its freshly assessed model/effort recommendation
with the same short reason. Keep this pointer
short (about 100 words), with no copied logs, parallel checklist or growing
history. A checkpoint need not be a Git commit; preserve unrelated working-tree
edits. Before ending, check that both records agree with current changes and
evidence. If interrupted before this update, the next session reconciles the
pointer with the checklist, owning handoff and current files; it must not repeat
an experiment solely to reconstruct a missing narrative.

End each slice with its result, verification scope, any unfinished blocker,
and the handoff link. Say **“You can end this session”** and give the same prompt:

> Continue the next unfinished task in docs/Test-Automation.md. This is the dev and host machine.

Leave the next slice for that new session. On final roadmap completion, mark the
continuation complete and say no further implementation session is needed.

Record per-slice experiments and results, preparation/test/cleanup time, and
context/usage if already exposed. One compact row in the handoff/evidence is
enough; no new telemetry service. After F1 and the first stable matrix batch,
estimate remaining work from measured cases, helper gaps and real waits.
Optimize the dominant measured cost before adding caches or frameworks.
The objective is fewer iterations and less repeated context; do not promise
days become hours before measuring, or obtain that result by dropping required
security, lifecycle or customer coverage. [Usage guidance](https://learn.chatgpt.com/docs/pricing).
