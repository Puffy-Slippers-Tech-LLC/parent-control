# Efficient implementation and continuation

The [master backlog](Test-Automation.md) owns task order/completion; the
[daily guide](../Test-Automation.md) owns commands. **Quality takes absolute
precedence.** Reject savings that weaken correctness, security, coverage,
evidence, diagnosis or cleanup. Reading/time targets trigger review, never
omission of necessary work. This is the single implementation session procedure.

## Start with one bounded result

1. Use the applicable `AGENTS.md` instructions already supplied in context;
   read any missing or changed instructions. Read [Continuation.md](Continuation.md),
   the [master checklist](Test-Automation.md#unfinished-tasks), and relevant task
   sections/active handoffs. At every safe slice boundary, select the earliest
   unchecked task in checklist order whose dependencies are accepted and which
   has no current evidenced blocker. Finish or reconcile any already-owned
   operation and cleanup before switching tasks. The continuation records this
   selection; it cannot give later work priority merely because it was started.
   Correct a stale pointer before beginning another implementation slice.

   Before bypassing an earlier unchecked entry, record its unmet dependency or
   concrete blocker, supporting evidence and return condition in that task's
   handoff; link the deferral from the continuation. Reassess those conditions
   at each selection using current handoffs and operator instructions, without
   repeating unchanged failed attempts. Once an earlier task becomes ready,
   return to it at the next safe boundary and preserve the later task's progress
   in its own handoff. A resolved hold cannot justify another fallback slice.
   Explicit user-directed task selection takes precedence; record its scope and
   when checklist order resumes. Blocked entries remain unchecked and block
   dependent acceptance. If nothing is ready, save the concrete blocker. If all
   entries are complete, record completion and stop without rerunning suites.
   An explicit cumulative recovery budget in the selected task also persists
   across slices. Update its ledger and check its outcome thresholds before
   selecting more work. If it requires an operator decision, finish cleanup and
   return the existing unattended `blocked/decision` result; do not evade the
   boundary with independent-task fallback, renamed blockers or reset totals.
   This exception applies to an explicitly recorded recovery scope, not ordinary
   slice estimates. Task 20's [retained recovery](Task-20.md#bounded-recovery--2026-09-11)
   owns such a scope when selected again; the operator has prioritized all
   independent installed-app and infrastructure work before it in the master
   checklist. Earlier consumers may bring forward bounded shared prerequisites;
   record R1 recovery work in its ledger, without blocking unrelated tasks.
2. State one next observable result, its smallest verification, planned slice
   budget, actual model/effort and the latest handoff's recommendation with its
   reason. The user's continuation request or [launcher invocation](Unattended-Sessions.md)
   authorizes the bounded work and choices under the model policy below; do not
   add a separate “Go ahead” or model-selection pause. An interactive agent
   cannot change its own running model: disclose a mismatch and arrange the
   appropriate next session if the current capability is insufficient. Never
   claim to switch models. Existing execution and acceptance boundaries apply;
   do not repeat the machine-selection question.
3. Inspect working-tree status and relevant changes. For
   architecture read [System-Design.md](../System-Design.md), then the owning
   module and applicable specification IDs. Read the selected task's
   [reuse-map row](Reuse-Map.md) and follow its relevant shared-contract and
   limitation links before diagnosing or adding a helper. Compare the existing
   implementation, regression coverage and recorded qualification with the
   boundary needed now. In the handoff, link the reused contract and identify
   only the missing capability or changed assumption. If reopening a solved
   boundary, state the new evidence or invalidating change first; a new task or
   chat alone is not a reason. Do not load every task, all evidence or the entire diff.
4. Implement and verify the slice; preserve concurrent changes. Mark the task's
   one checklist entry complete only after all its deliverables and acceptance
   checks pass. Update reusable contracts and write the handoff below before
   ending. Do not start an unrelated next problem or recreate accepted setup.

A slice is one unresolved boundary, a fix plus verification, or several cases
using a proven helper. Plan one or two meaningful experiments, usually 15–30
minutes; this is an estimate, not a completion deadline.

## VM availability for all tasks

**Operator instruction — 2026-09-08:** the user confirmed there are no
concurrent VM operations and cleared the VM/writer-pause hold for **every
task**. This supersedes pending coordination requests and local-only fallback
instructions in earlier handoffs and evidence. Carry this clearance into future
handoffs; do not require another writer-pause confirmation, a clean Git status,
or a new session approval merely to use the already-authorized test VM.

At the next safe slice boundary, select dependency-ready installed/E2E work
using the checklist and current handoff. Finish an active owned operation and
cleanup before starting the next. Do not add local-only slices because of the
resolved hold. Task dependencies, implementation readiness and acceptance
requirements still apply.

Use the approved guarded runner, which acquires the shared VM lease. An off VM
status alone does not prove lease availability; let the runner check it. If it
reports an actual busy owner or unfinished operation, reconcile that operation
under the existing ownership rules. Never delete locks or take over a VM.

Source provenance is checked separately from VM availability. Finish edits
before running checks that snapshot the real checkout, including `make check`;
documentation writes can correctly fail those checks too. Build fresh artifacts
when required, and make no checkout edits during the attempt through terminal
collection and cleanup. Existing uncommitted changes
are valid captured inputs. A new provenance refusal requires diagnosis of its
recorded cause under the attempt limits; it does not restore a blanket VM hold
across the backlog. Report any new blocker with current evidence, affected
scope and the concrete next action. Historical failed results remain failed;
their old scheduling instructions do not override this clearance.

## Reassess model and effort at every handoff

**Operator policy — 2026-09-08:** quality is mandatory; conserving the weekly
subscription usage allowance is the secondary objective. This replaces every
blanket Astra/high pin and max-effort default, including instructions in older
handoffs and evidence. Historical settings still describe those past runs.
Selection under this policy is authorized for already-authorized work without
another settings confirmation.

Reevaluate model and effort separately for the next slice at every handoff.
The latest applicable handoff overrides task-header defaults; revise it if
intervening changes alter the difficulty. Mirror the result in Continuation.md.

| Next slice | Starting choice and reassessment |
| --- | --- |
| Bounded implementation with settled contracts, proven helpers and meaningful acceptance checks | `gpt-5.6-sol` / `high`. This is the general implementation default. |
| Unresolved architecture, authorization, concurrency, process ownership, difficult diagnosis across services, or broad semantic correctness review | `gpt-6-astra` / `high`. Select it upfront when needed; do not spend repeated weaker-model attempts discovering a known capability gap. |
| Routine case expansion, adapters or UI work with established interfaces and expected results | Consider `gpt-5.6-terra` / `medium` or `high` only after confirming that the contract and checks are adequate. |
| Mechanical documentation or mappings over verified decisions | Consider `gpt-5.6-luna` / `low` or `medium`; a change to privacy, evidence, acceptance or ownership policy is not mechanical. |

- Initially retain `high` for substantive implementation while choosing the
  model. Lower effort separately when the remaining reasoning is routine.
  Use `xhigh` or `max` only for an identified reasoning need recorded in the
  handoff, never because they were used before. A failed test or long VM wait
  alone does not justify stronger settings.
- Keep the same required tests, review, evidence and cleanup with every model.
  No model choice guarantees correctness. Retain stronger capability when the
  adequacy of a cheaper choice is uncertain, then reassess after the boundary
  is proven. Repeated corrections require reconsidering that class of work.
- Use **Standard processing**. Fast mode spends additional allowance for speed,
  without increasing model intelligence. The launcher explicitly sets
  `service_tier="default"`; a general user configuration must not silently
  enable Fast mode for its workers.
- Optimize allowance consumed per verified result, including context, reasoning,
  corrections and retries. Raw token counts, credit rates and the weekly meter
  are distinct: a stronger model can generate fewer tokens, and published
  credit ratios do not establish an exact weekly-limit multiplier. Use only
  already-exposed usage and real completed work; do not duplicate implementations
  to benchmark models, read old transcripts or add a model call just to route a
  slice. See [official usage guidance](https://learn.chatgpt.com/docs/pricing)
  and [Standard/Fast processing](https://learn.chatgpt.com/docs/agent-configuration/speed).

Record exact settings and a fresh reason even when keeping both:

> **Next-session settings:** `<model>` / `<effort>`; model: lower/raise/keep;
> effort: lower/raise/keep. **Reason:** `<what is now proven and what remains>`.

The [launcher settings contract](Unattended-Sessions.md#model-and-effort-selection)
defines the single machine-readable line in Continuation.md. The supervisor
reads it before each fresh slice; it does not use the task header or global
configuration as a silent fallback. A running worker records its actual settings
separately from its next recommendation. If new evidence requires a stronger
model, finish owned operations and save a precise handoff before the next
session. Do not start a nested model process or weaken verification to stay on
the current model. Machine/VM authorization persists.

## Keep context small and reset at problem boundaries

- Save a handoff and end at the agreed slice boundary. Batch adjacent cases
  sharing a proven helper; do not split every parameter into its own chat or
  expand a finished slice into an unrelated investigation.
- Review progress at ten minutes. Review context at roughly 50,000 current-context
  tokens if exposed, otherwise at 30 minutes. These are project heuristics;
  cumulative input/cached tokens are not current context. Do not inspect old
  session logs to estimate usage. At the threshold, stop broad reads, finish the
  bounded operation and cleanup, then hand off before another experiment.
  Explain overruns; a quiet VM wait alone is not new reasoning work.
- Search first, then read relevant ranges; start near 2,000 output tokens and
  widen when needed. Batch independent reads and inspect every result; keep
  dependent operations/edits sequential. Request counts, selected IDs and failure
  summaries before full JSON/JUnit/logs. Narrow truncated queries rather than
  repeating them. Preserve full private evidence and directly inspect relevant
  screenshots for visual assertions; summaries do not replace necessary review.
- Await running commands in bounded intervals and report stage changes. Retain
  their full result, session ID and exit status; poll yielded commands to exit.
  Do not repeatedly reinterpret unchanged evidence or load an unrelated problem
  while waiting. Missing `result.json`, a busy lease or an off VM does not prove
  interruption. Reconcile the original operation/evidence before recovery or a
  new run, including when its handle is lost.
- Finish owned commands, collection and guarded cleanup before handing off.
  If interrupted, record exact owned identities, command/session and recovery
  state; reconnect instead of duplicating the run. Never tear down a useful
  attempt for a timer or leave a live VM to reuse in the next chat.

After saving the handoff, use a fresh chat. Codex CLI `/new` resets chat context;
`/compact` summarizes the existing chat and is an alternative when the user
requests same-chat continuation. `/resume` reloads and `/fork` copies history.
These are user controls, not shell commands for the agent to execute.
[Official command documentation](https://learn.chatgpt.com/docs/developer-commands).
Automatic compaction does not extend the agreed slice.

## Reduce unnecessary model output

Optimize what enters or leaves the model. The launcher forwards CLI events to
the terminal without feeding that display back to its worker. Hiding or
restyling those events cannot reduce that worker's token usage.

| Content or operation | Token effect and handling |
| --- | --- |
| Model-written prose, scripts, patches and tool-call arguments | Output tokens. Generate necessary implementation once; avoid repeating it in reports. |
| Tool results sent back to the model, including file/log excerpts and screenshots | Input/context tokens. Select relevant evidence and expand when needed. |
| Local terminal rendering, saving existing output, or artifacts never sent to a model | No additional model tokens from those operations. Preserve useful detail. |

This distinction follows the official [tool-calling flow](https://developers.openai.com/api/docs/guides/function-calling#how-it-works)
and the CLI's [event stream](https://learn.chatgpt.com/docs/non-interactive-mode#make-output-machine-readable).
Capturing launcher output in another assistant's tool result makes that captured
text input to that assistant; ordinary operator terminal display does not.
Saving model-written prose in a file still requires generating it, and reading
it later adds context. File storage alone is not a token-saving technique.

- Keep regular progress updates brief and useful: findings, stage changes and
  the next check. Do not narrate every tool call, print a script before executing
  it, or repeat patches, commands and results already available from tools.
- Write necessary code through the approved editing tools and reuse maintained
  helpers for recurring operations. Keep code readable, logging sufficient and
  tests complete; do not minify scripts or bypass approval boundaries for brevity.
- Use focused reads and supported quiet/summary options through the approved
  launchers. Retain exit status, failure/skip/missing-case information and evidence
  paths. Full diagnostics stay in the existing artifacts; inspect relevant failure
  context before deciding. Expand an output limit or read the omitted range when
  truncation hides needed information. Do not hide errors, pipe tests through
  filters that conceal their status, or rerun tests merely to recover output.
- Report changed behavior, verification scope/results, material failures, cleanup
  and next action. Link evidence and use test IDs instead of copying code, full
  logs or passing-case lists. Preserve exact reproduction commands/selectors,
  input/run identities and recovery details once in the active handoff or evidence
  where needed. Keep summaries self-contained about the result and its limits.

These are defaults for removing repetition, not hard response/tool-output caps.
Expand whenever correctness, diagnosis or recovery requires it. Select model
and effort under the policy above; never skip required checks, delete evidence
or weaken cleanup to shorten a transcript. Compare already-exposed usage for comparable
verified work; fewer terminal lines or artifact bytes do not establish savings.

## Reuse established tools and bound harness work

When a shared problem is resolved or its qualification/diagnosis changes, update
its owning contract with the established cause (or explicitly unknown cause),
supported fix, canonical helper/symbol, regression file or case IDs, qualified
scope and remaining limitations. Link retained live evidence where applicable;
local checks alone do not establish live qualification. Update the affected
[reuse-map rows](Reuse-Map.md) with that contract and its downstream consumers
before ending the slice, even if the overall task remains unfinished. Keep
attempt counts and the next experiment in the active task handoff; link them
from the contract when an unresolved shared failure affects reuse. A passing
attempt does not close an intermittent failure whose cause remains unknown.

Before handing off, compare the owning contract, affected reuse-map links and
active handoff against the newest retained evidence. Correct stale qualification
claims in that same slice; keep historical evidence unchanged. Distinguish
locally tested, live-qualified, unresolved and unimplemented boundaries. Store
the durable problem/solution/regression record in the owning contract so it
survives replacement of the active handoff; the operator summary is not a worker
input. Link it rather than copying the investigation into downstream tasks.

Before reopening a recorded solution, identify the changed input/interface,
contradictory evidence or uncovered case. With none, continue using the existing
helper and applicable evidence under the [verification reuse rules](#decide-what-invalidates-earlier-verification).
If a reference is stale, reconcile it against the owning contract, current code
and retained evidence; repair the link or status without rerunning an experiment
merely to reconstruct the record. The map routes readers to these records; it
must not duplicate changing inventory counts or become another result ledger.

Keep the existing pytest/Hypothesis/coverage.py and Node/GJS foundations,
python-dbusmock private buses, Dogtail/AT-SPI components, and os-autoinst with
QEMU/libvirt for OS journeys. Use their maintained public interfaces and the
versions in `tests/test-tools-ubuntu-26.04.txt` and `tests/ui/requirements.txt`.
Qualify affected UI/backend behavior when those versions or interfaces change;
established tool names alone do not establish that our adapter works.

Before adding custom orchestration, identify the concrete missing capability
in the current app scenario or required safety boundary. Prefer an existing
fixture/API and a small adapter. Finish the bounded runner result and move to
product coverage; do not create a general framework, duplicate scheduler,
collector or selector for hypothetical future uses. Preserve owned cleanup,
secret protection, provenance and failure reporting with focused regressions.

Source/configuration checks may protect an actual interface or packaging rule.
Prefer executable behavior over source-string or call-order assertions for
runtime guarantees; retire redundant brittle checks when behavior is covered.
Keep source contracts and harness qualification out of product coverage claims.

## Make every expensive attempt answer a question

Before a live attempt, apply the [scope and prerequisite rules](E2E-Coverage.md#scope-tests-around-the-app):
name the app regression or harness guarantee, choose the lowest effective layer,
and separate supported fixture setup from the actions under test. Reuse bounded
provisioning helpers for unrelated OS work. Do not automate an upstream GUI or
multiply equivalent full journeys without an app-specific reason.

1. Identify the first failing boundary, one hypothesis and its discriminating
   observation. Separate helper, product, environment, collection and cleanup.
2. Validate parsers/selectors/collectors and failure paths locally first. Collect
   sufficient safe diagnostics for success and failure in the same boot; never
   export credentials or raw authentication terminal data.
3. Run the smallest guarded selection and its prerequisite closure through the
   [approved categories](Approval-Tools.md#category-coverage-and-future-additions).
   F1's installed selectors are implemented; register new areas there. Graphical
   execution uses the accepted 19A controller for ready declarations; pending
   selections still refuse before VM access. Never invoke
   guest pytest on the host, invent a selector, or bypass VM guards.
4. Fix the demonstrated cause. Prove a real success, deliberate denial/failure
   and one interaction before expanding cases. A shared prerequisite failure
   proves nothing about later assertions; keep those cases registered.
5. After two expensive attempts on one blocker, require new discriminating
   evidence or locally validated observability before a third. A narrower
   failure label alone does not reset that count. Before another diagnostic-only
   attempt, audit the supported operation and relevant OS implementation together,
   and consolidate observations that distinguish the remaining explanations in
   one run. State how each outcome changes the next action. Once an actionable
   interface defect is identified, prioritize its correction and qualification;
   do not spend another full journey collecting an incremental label. Carry counts,
   rejected hypotheses and next observation across chats. Record concrete
   design/external blockers and move only to authorized independent work;
   never weaken the boundary to obtain a pass.

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

Task verification lists are acceptance scope. Run common checks, including
`make check` and `git diff --check`, once after the final code change in a stable
batch; repeat only for subsequent changes, failures or unresolved concerns.
Label focused results with their scope. Safety prerequisites always run in
isolation before protected operations.

### Decide what invalidates earlier verification

| Change since the recorded result | Next verification |
| --- | --- |
| New chat; relevant inputs and environment unchanged | Check the retained result, scope and identities; continue at the next action. |
| Documentation only | Check changed links, commands and consistency plus `git diff --check`. Preserve runtime evidence with its original input identity. |
| Case, assertion, helper, product or configuration changed | Run affected cases and shared consumers. Broaden when the dependency closure is uncertain; do not guess that a change is harmless. |
| Tool, baseline, OS, transport, ownership or capture behavior changed | Revalidate affected compatibility/safety and real success/failure behavior; repeat applicable qualification. |
| Task acceptance or final release | Apply the full required scope above. Selected or historical evidence cannot replace a complete current-input release run. |

Use the handoff's command/scope, input identities, evidence and subsequent edits
to decide applicability. A Git commit misses uncommitted inputs; missing
provenance does not permit pass reuse. Never disable launcher safety tests to
deduplicate checks.

**Artifact reuse is a separate decision.** Today's `VerifiedInputs` requires
the package manifest's source digest to match the current checkout, including
documentation. A documentation handoff can therefore require a fresh artifact
for the next package-bearing VM attempt, even though it needs no product tests
itself. Do not edit manifests or exclude paths ad hoc. Task 20's
[recovery R1](Task-20.md#bounded-recovery--2026-09-11) owns the immediate stable
source-execution prerequisite; Task 28A retains the complete validated build-input
closure and artifact reuse. Neither planned capability is an available cache
today. Preserve the current contract until an equivalent replacement is verified.

Register each shared case/assertion once and link its requirements/tasks.
Applicable current-input evidence may support related implementation acceptance;
the final release still executes every required case. Group independent values
in a declared continuous scenario only where initial state/interactions allow;
follow [coverage selection](E2E-Coverage.md#bound-the-matrix-before-expanding-it).

Execute each required case once in ordinary acceptance. Repetition needs a
stability question, selection, count and stop condition. New graphical/cleanup
transport requires three complete qualification smokes, reusable until relevant
behavior/environment changes. No default repeated whole matrices or ten-run
loops. For intermittent defects, justify the independent attempt count; a
finite count cannot prove zero flakiness.

## Handoff format and cost review

Update one active handoff in the task document, normally 200–400 words. Use less
when sufficient and more when material evidence or recovery requires it; do not
pad to a target. Link long evidence without copying it or removing logs/artifacts.
Include:

- Task/slice, next observable result, and authorized machine/VM scope.
- [Next-session settings](#reassess-model-and-effort-at-every-handoff): exact
  model/effort, lower/raise/keep for each, and reason.
- Proven facts/interfaces and the next read list: files/symbols/contract sections,
  not copied code or a retold investigation.
- For shared fixes, links to the updated owning contract and affected reuse-map
  rows, including regression coverage, qualification limits and downstream users.
- Unresolved hypothesis, attempts spent, rejected explanations and next observation.
- Tested inputs, command/selector, evidence paths/digests and later changes;
  identify host-only edits and what invalidates prior verification. Give the
  exact next host check when known; label unresolved artifacts, never reuse a
  remembered acceptance path without verification.
- Remaining acceptance, exact next action and owned process/VM/cleanup state.
  Record outstanding operation identities. Historical “VM off” is not current
  state; never duplicate another session's work or overwrite its active handoff.

Reapply [task selection](#start-with-one-bounded-result), then update
[Continuation.md](Continuation.md) for the selected next task: task/status,
handoff link, next slice, and that task's settings/reason. Do not automatically
carry forward the task just worked on. Link any earlier deferred entries' blocker
records and return conditions; keep the completed slice's evidence in its task
handoff. Aim near 100 words; no copied logs or second checklist.
Check both records against current changes/evidence, preserving
unrelated edits; no commit is required. An interrupted handoff is reconciled
from files/evidence, never reconstructed by rerunning an experiment.

End each slice with its result, verification scope, any unfinished blocker,
and the handoff link. Say **“You can end this session”** and give the same prompt:

> Continue the next unfinished task in docs/Test-Automation.md. This is the dev and host machine.

On roadmap completion, mark the continuation complete and say no further
implementation session is needed.

Record experiments/results, preparation/test/cleanup time and already-exposed
usage in one evidence row; no telemetry service or log archaeology. Forecast
from measured cases, helper gaps and real waits after the first stable batch.
Optimize the dominant measured cost before adding caches/frameworks. Tokens,
model price and VM wall time differ; faster boots do not prove token savings.
Official [usage guidance](https://learn.chatgpt.com/docs/pricing) identifies
context, reasoning, tools and caching as factors, not savings for this checkout.
