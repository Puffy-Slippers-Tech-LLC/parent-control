# Efficient implementation and continuation

The [master backlog](Test-Automation.md) owns task order/completion; the
[daily guide](../Test-Automation.md) owns commands. **Quality takes absolute
precedence.** Reject savings that weaken correctness, security, coverage,
evidence, diagnosis or cleanup. Reading/time targets trigger review, never
omission of necessary work. This is the single implementation session procedure.

## Start with one bounded result

1. Use the applicable `AGENTS.md` instructions already supplied in context;
   read any missing or changed instructions. Read [Continuation.md](Continuation.md),
   the selected task section/active handoff and the relevant
   [checklist](Test-Automation.md#unfinished-tasks) entry. Resume that unfinished
   task if its dependencies are met; otherwise select the first ready unchecked
   task. Reconcile a stale pointer against the checklist, handoff and current
   files. A blocker stays unchecked and blocks dependent acceptance; independent
   ready work may proceed. If nothing is ready, save the concrete blocker. If
   all entries are complete, record completion and stop without rerunning suites.
2. State one next observable result, its smallest verification, planned slice
   budget, and the latest handoff's model/effort with its reason. Confirm both
   settings and wait for **“Go ahead”** at each fresh implementation session,
   including the same task. Explain that the documented
   [session loop](../Test-Automation.md#continue-implementation-in-fresh-sessions)
   requires this pause. Do not investigate code or run tests before confirmation.
   Explicit session instructions take precedence; do not request an approval
   already given for this session or repeat the machine-selection question.
3. After confirmation, inspect working-tree status and relevant changes. For
   architecture read [System-Design.md](../System-Design.md), then the owning
   module and applicable specification IDs. The task's first slice and optional
   [reuse-map row](Reuse-Map.md) route further reads. Follow contracts when the
   boundary needs them; do not load every task, all evidence or the entire diff.
4. Implement and verify the slice; preserve concurrent changes. Mark the task's
   one checklist entry complete only after all its deliverables and acceptance
   checks pass. Update reusable contracts and write the handoff below before
   ending. Do not start an unrelated next problem or recreate accepted setup.

A slice is one unresolved boundary, a fix plus verification, or several cases
using a proven helper. Plan one or two meaningful experiments, usually 15–30
minutes; this is an estimate, not a completion deadline.

## Reassess model and effort at every handoff

Reevaluate model and effort separately for the next slice at every handoff.
The latest applicable handoff overrides task-header defaults; revise it if
intervening changes alter the difficulty. Mirror the result in Continuation.md.

- Lower either setting for routine implementation, case tables or documentation
  only with a settled contract, explicit expected result and adequate checks.
  A short authorization, ownership, concurrency or evidence edit is not routine.
- Raise either when unresolved design or security/concurrency reasoning needs
  it. A failed test or long VM wait alone is not a reasoning difficulty.
- Choose the least costly available combination expected to preserve quality;
  retain stronger settings when capability is uncertain. Judge total work to a
  verified result, including rereads/corrections/retries, not price per token.
  Do not duplicate implementations merely to benchmark models.

Record exact settings and a fresh reason even when keeping both:

> **Next-session settings:** `<model>` / `<effort>`; model: lower/raise/keep;
> effort: lower/raise/keep. **Reason:** `<what is now proven and what remains>`.

Confirm at session start as above; within that session confirmation remains
valid unless recommending a setting change. Never claim to switch models or
read old transcripts to recover approval. Machine/VM authorization persists.

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

## Reuse established tools and bound harness work

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
   listing/refusal is implemented, execution remains gated by 19A. Never invoke
   guest pytest on the host, invent a selector, or bypass VM guards.
4. Fix the demonstrated cause. Prove a real success, deliberate denial/failure
   and one interaction before expanding cases. A shared prerequisite failure
   proves nothing about later assertions; keep those cases registered.
5. After two expensive attempts on one blocker, require new discriminating
   evidence or locally validated observability before a third. Carry counts,
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
itself. Do not edit manifests or exclude paths ad hoc. Task 28A's narrower,
validated build-input closure is planned; it is not an available cache today.

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

Update one active 200–400-word handoff in the task document. Link long historical
evidence without removing logs/artifacts. Include:

- Task/slice, next observable result, and authorized machine/VM scope.
- [Next-session settings](#reassess-model-and-effort-at-every-handoff): exact
  model/effort, lower/raise/keep for each, and reason.
- Proven facts/interfaces and the next read list: files/symbols/contract sections,
  not copied code or a retold investigation.
- Unresolved hypothesis, attempts spent, rejected explanations and next observation.
- Tested inputs, command/selector, evidence paths/digests and later changes;
  identify host-only edits and what invalidates prior verification. Give the
  exact next host check when known; label unresolved artifacts, never reuse a
  remembered acceptance path without verification.
- Remaining acceptance, exact next action and owned process/VM/cleanup state.
  Record outstanding operation identities. Historical “VM off” is not current
  state; never duplicate another session's work or overwrite its active handoff.

Then update [Continuation.md](Continuation.md): task/status, handoff link, next
slice, same settings/reason. Aim near 100 words; no copied logs or second
checklist. Check both records against current changes/evidence, preserving
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
