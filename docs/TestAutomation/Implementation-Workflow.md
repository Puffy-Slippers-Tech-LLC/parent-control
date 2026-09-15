# Efficient implementation and continuation

The [master backlog](Test-Automation.md) owns task order/completion; the
[daily guide](../Test-Automation.md) owns commands. This document owns the
implementation session procedure. **Quality takes absolute precedence over
usage savings:** preserve correctness, security, coverage, evidence, diagnosis
and cleanup. Time, context and word targets trigger review, never weaker work.

**Operator scope — 2026-09-14:** prioritize the full customer E2E queue and
follow its [surface-only contract](E2E-Coverage.md). The timeout/login example
illustrates the rule; it is not the sole or preferred scenario. Preserve all
completed lower-level tests. Mechanical installation/upgrade/removal work
retains necessary internal inspection under Tasks 18/20. Deferred product
design, internal fault matrices and general infrastructure expansion are not
automatic fallback work or implicit customer dependencies.

## Retain useful evidence without one-off reports

For routine test/build failures, including `make test-all`, report the cause,
fix and verification in the conversation/PR. Update the owning contract for
reusable behavior/regression guidance and the existing active handoff when
continuation needs a blocker, next action or artifact reference.

Preserve runner reports, original failures, logs, screenshots, private artifacts
and useful qualification evidence for automation in progress. A new standalone
evidence document requires an explicit user request or a concrete ongoing
acceptance/recovery need that existing artifacts and the active handoff cannot
satisfy. A failed check, completed fix, passing-test list or session diary does
not qualify. This applies everywhere, not just `Evidence/`; do not copy machine
reports into prose or document documentation cleanup.

The same rule applies to additions inside existing documents: do not append
one-time run reports, incident timelines, qualification summaries, before/after
timings or superseded implementation histories to design and instruction docs.
Revise the current contract in place, retaining reusable rationale, limitations
and regression requirements. Per-run history belongs in generated runner
artifacts; an active handoff may link only the evidence needed for continuation.

This supersedes older per-attempt reporting instructions without changing
verification or retention requirements. Routine user-directed fixes need roadmap
handoff/continuation updates only if they change the ongoing task's state.

## Start with one bounded result

1. Use applicable `AGENTS.md` instructions already in context; read missing or
   changed instructions. Read [Continuation.md](Continuation.md), the
   [checklist](Test-Automation.md#unfinished-tasks) and relevant task sections/
   active handoffs. At every safe boundary, select the earliest unchecked entry
   in the customer queue whose concrete prerequisites are available and which
   has no current evidenced blocker. Whole internal test matrices and another
   task's full UI acceptance are not dependencies merely because it owns a helper.
   Finish or reconcile owned operations and cleanup before switching tasks.
   Correct stale continuation pointers; previously started work has no priority.
2. Before bypassing an earlier entry, record its dependency/blocker, evidence
   and return condition in its handoff and link it from the continuation.
   Recheck deferrals at each selection without repeating unchanged failures.
   Return when ready, preserving later work in its own handoff. Explicit user
   selection takes precedence; record its scope and when checklist order resumes.
   Blocked entries stay unchecked and block dependent acceptance. If none is
   ready, move to the authorized mechanical package queue with blockers recorded;
   if no active work is ready, save the blocker. If the active checklist is
   complete, report its scope and separate deferred work, then stop
   without rerunning suites.
3. Carry explicit cumulative recovery ledgers across slices and check their
   outcome thresholds before selecting more work. A required operator decision
   means finish cleanup and return unattended `blocked/decision`; no fallback,
   renamed blocker or reset totals may evade it. This applies to the recorded
   recovery scope, not ordinary slice estimates. Task 20's
   [retained R1 recovery](Task-20.md#bounded-recovery--2026-09-11) resumes in
   checklist order after prioritized customer journeys. Earlier consumers may
   repair a demonstrated shared prerequisite needed by their named scenario:
   charge their R1 recovery portion and apply its checkpoints to further recovery,
   without blocking unrelated work.
4. State the next observable result, smallest verification, planned budget,
   actual model/effort and latest handoff recommendation/reason. A continuation
   request or [launcher invocation](Unattended-Sessions.md) authorizes this
   work and model-policy choices; no separate “Go ahead”, settings or machine
   selection is due. Disclose model mismatch and arrange the next session if
   capability is insufficient; never claim to switch the running model.
   Execution and acceptance boundaries still apply.
5. Inspect status and relevant changes; preserve concurrent work. For customer
   E2E, read the selected visible behavior and existing graphical interfaces;
   do not audit product internals to invent acceptance prerequisites. Architecture
   reads for authorized mechanical/product work start at
   [System-Design.md](../System-Design.md). Before adding necessary infrastructure, read the
   selected [reuse-map row](Reuse-Map.md) and relevant contract/limitation links.
   Customer scenarios start with the [building blocks and lessons](E2E-Building-Blocks.md)
   before adding setup, pointer, navigation or recording code.
   Compare implementation, regressions and qualification to the needed boundary.
   Link the reused contract and identify only the missing capability or changed
   assumption; reopening a solution requires new evidence or an invalidating
   change. Do not load all tasks, evidence, old transcripts or the entire diff.
6. Implement and verify one coherent slice, update reusable contracts and save
   the handoff below. Check off a task only after all deliverables and acceptance
   checks pass; do not delete checklist entries during unattended work.
   Do not recreate accepted setup or start an unrelated next problem.

A customer slice targets one complete variant, or a small batch using a proven
interaction. A minimal adapter must serve that same named consumer. Freeze its
customer actions and visible finish line before coding. Mechanical package
slices target their declared qualification milestone. Plan usually 15–30 minutes;
this is an estimate, not a deadline or a reason to split every step into a chat.

## VM availability for all tasks

**Operator clearance — 2026-09-08:** no concurrent VM operations remain; the
VM/writer-pause hold is cleared for **every task**. This supersedes earlier
coordination requests and local-only fallback instructions. Preserve it in
handoffs. At the next safe boundary, proceed with dependency-ready guarded
installed/E2E work; do not require another coordination/session approval,
clean Git status or local-only slice because of the resolved hold.

The approved runner checks the shared VM lease; an off VM does not prove
availability. Reconcile actual busy owners or unfinished operations under
ownership rules. Never delete locks or take over a VM. Dependencies,
implementation readiness and acceptance still apply.

Source provenance is separate: finish edits before checkout-snapshot checks,
including `make check`, and build fresh artifacts when required. Documentation
writes can invalidate a snapshot too. Make no checkout edits during an attempt
through terminal collection and cleanup; existing uncommitted changes are valid
captured inputs. Diagnose new refusals under attempt limits and record their
current evidence, affected scope and next action. Historical failures remain
failed, but neither they nor a new scoped refusal restore the blanket hold.

## Reassess model and effort at every handoff

**Operator policy — 2026-09-08:** quality first, weekly subscription allowance
second. This replaces blanket Astra/high pins and max-effort defaults; historical
settings remain execution records. Settings choices for authorized work need
no further confirmation.

Reassess model and effort separately at every handoff from what is now proven
and what remains. The latest applicable handoff overrides task-header defaults;
revise it for intervening changes and mirror the choice in Continuation.md.

| Next slice | Starting choice |
| --- | --- |
| Bounded implementation; settled contracts, proven helpers, meaningful checks | `gpt-5.6-sol` / `high` (default). |
| Unresolved architecture, authorization, concurrency, process ownership, difficult cross-service diagnosis or broad semantic correctness review | `gpt-6-astra` / `high`, chosen upfront rather than after repeated weaker attempts. |
| Routine case expansion, adapters or UI with established interfaces/results | Consider `gpt-5.6-terra` / `medium` or `high` after confirming adequate contracts/checks. |
| Mechanical documentation/mappings over verified decisions | Consider `gpt-5.6-luna` / `low` or `medium`. Privacy, evidence, acceptance and ownership policy changes are not mechanical. |

- Start substantive implementation at `high`; lower effort separately when
  reasoning becomes routine. Use `xhigh`/`max` only for a documented need,
  not past usage, a failed test or a long VM wait.
- Keep required tests, review, evidence and cleanup with every model. When a
  cheaper model's adequacy is uncertain, retain stronger capability until the
  boundary is proven. Repeated corrections warrant reassessing that work class;
  no model guarantees correctness.
- Use **Standard processing**. The launcher sets `service_tier="default"`
  explicitly so user configuration cannot silently enable Fast. Fast spends
  more allowance for speed without increasing intelligence.
- Optimize allowance per verified result, including context, reasoning,
  corrections and retries. Tokens, credit rates and the weekly meter differ;
  fewer generated tokens or published credit ratios do not establish a weekly
  multiplier. Use already-exposed usage and completed work, without duplicate
  implementations, transcript archaeology or an extra routing model call.
  See [usage guidance](https://learn.chatgpt.com/docs/pricing) and
  [processing modes](https://learn.chatgpt.com/docs/agent-configuration/speed).

Record actual settings separately from this next-session recommendation, with
a fresh reason even when retaining both:

> **Next-session settings:** `<model>` / `<effort>`; model: lower/raise/keep;
> effort: lower/raise/keep. **Reason:** `<what is proven and what remains>`.

The [launcher settings contract](Unattended-Sessions.md#model-and-effort-selection)
requires one machine-readable line in Continuation.md; task headers and global
configuration are not fallbacks. If stronger capability becomes necessary,
finish owned work and save a precise handoff; never launch a nested model or
weaken verification. Machine/VM authorization persists.

After each clean unattended slice, a separate
[progress review](Unattended-Sessions.md#progress-review-between-slices) uses
Astra xHigh. It may revise handoffs and require an observable breakthrough with
Astra xHigh or max for one slice only. The launcher consumes that override
separately; keep ordinary reassessed settings in Continuation.md. Report whether
the breakthrough occurred. The override expires without waiving acceptance,
cleanup, permissions or required operator decisions.

## Keep context small and reset at problem boundaries

- End at the agreed slice boundary. Batch adjacent cases using a proven helper;
  neither split each parameter into a chat nor expand into unrelated work.
- Review progress at ten minutes; review context near 50,000 current-context
  tokens if exposed, otherwise at 30 minutes. Cumulative input/cached tokens
  are not current context; do not read old session logs to estimate it. At the
  threshold stop broad reads, finish the operation/cleanup and hand off before
  another experiment. Explain overruns; quiet VM waits are not reasoning work.
- Search first and read relevant ranges, starting near 2,000 output tokens.
  Batch independent reads and inspect each result; keep dependent operations
  and edits sequential. Request counts, selected IDs and failure summaries
  before full JSON/JUnit/logs. Narrow truncated queries or expand relevant ranges
  as needed. Preserve private evidence and inspect screenshots directly for
  visual assertions.
- Await commands in bounded intervals, report stage changes and poll to exit.
  Retain full results, session IDs and exit status. Do not reinterpret unchanged
  evidence or investigate unrelated work while waiting. Missing `result.json`,
  a busy lease or an off VM does not prove interruption: reconcile the original
  operation/evidence before recovery or rerun, even if its handle is lost.
- Finish commands, collection and guarded cleanup before handoff. On interruption,
  record owned identities, command/session and recovery state; reconnect rather
  than duplicate. Never kill a useful attempt for a timer or leave a live VM
  for the next chat.

After handoff use a fresh chat. CLI `/new` resets context; user-requested
`/compact` summarizes the same chat, `/resume` reloads history and `/fork`
copies it. These are user controls, not agent shell commands; automatic
compaction does not extend the slice.
[Command documentation](https://learn.chatgpt.com/docs/developer-commands).

## Reduce unnecessary model output

| Content/operation | Token effect |
| --- | --- |
| Model-written prose, scripts, patches, tool arguments | Output tokens: generate necessary content once. |
| Tool results sent to a model, including excerpts/screenshots | Input/context tokens: select relevant evidence and expand as needed. |
| Local terminal rendering, saving existing output, artifacts never sent to a model | No additional model tokens: preserve useful detail. |

The launcher forwards CLI events to the terminal without feeding that display
back to its worker; hiding or restyling it cannot save worker tokens. Capturing
it in another assistant's tool result does add input to that assistant.
Writing new prose to a file still costs generation, and reading it adds context.
See the [tool-calling flow](https://developers.openai.com/api/docs/guides/function-calling#how-it-works)
and [CLI events](https://learn.chatgpt.com/docs/non-interactive-mode#make-output-machine-readable).

Keep updates to findings, stage changes and next checks; do not repeat scripts,
patches, commands or results. Use approved editors, maintained helpers and
supported quiet/summary options. Preserve readable code, sufficient logging,
complete tests, exit status, failure/skip/missing-case details and evidence paths.
Inspect relevant failures and omitted context before deciding. Never minify
for brevity, hide errors/status through filters, or rerun tests just for output.

Reports must state changed behavior, verification scope/results, material
failures, cleanup, next action and limits. Link evidence/test IDs instead of
copying logs or passing-case lists. Keep exact reproduction selectors/commands,
input/run identities and recovery details once in the active handoff or evidence.
These are repetition-reduction defaults, not hard output caps. Expand for
correctness, diagnosis or recovery; never delete evidence or weaken checks.
Compare already-exposed usage for comparable verified work; terminal lines and
artifact bytes do not establish savings.

## Reuse established tools and bound harness work

For customer work, use the [customer reuse route](Reuse-Map.md#customer-scenario-work)
and accepted graphical input/setup/cleanup. Do not follow the historical probe,
policy or backend-fault chains as E2E dependencies. A helper change must name
the customer action that cannot run safely, the smallest missing capability,
the consumer acceptance signal and its stop condition. No standalone platform,
schema, collector, caching or upstream-internals project is authorized by a
customer test. Mechanical installation may retain its deeper qualification.

Before investigating a shared boundary, use its reuse-map row and owning
contract. Reopen a solution only for a changed input/interface, contradictory
evidence or uncovered case; otherwise apply the
[verification reuse rules](#decide-what-invalidates-earlier-verification).
Reconcile stale references against current code, contract and retained evidence,
then repair them without rerunning experiments merely to reconstruct history.

When a shared diagnosis, fix or qualification changes, update its owning
contract with cause (explicitly unknown if unresolved), supported fix, canonical
helper/symbol, regressions, qualified scope, limitations and retained live
evidence. Update affected [reuse-map rows](Reuse-Map.md) and downstream links
before handoff, even for unfinished tasks. Keep attempt counts/next experiment
in the active handoff, linked from the contract if the unresolved failure
affects reuse. A pass does not close an unexplained intermittent defect.

Compare contract, map and handoff with the newest evidence in the same slice.
Correct stale claims while preserving historical evidence. Distinguish local
tests, live qualification, unresolved and unimplemented work. The contract
retains reusable findings after handoff replacement; the map routes readers
without duplicating inventories or result ledgers. Link downstream tasks to
that record rather than copying investigations. Operator summaries are not
worker inputs.

Keep pytest/Hypothesis/coverage.py, Node/GJS, python-dbusmock private buses,
Dogtail/AT-SPI and os-autoinst with QEMU/libvirt. Use maintained public interfaces
and versions in `tests/test-tools-ubuntu-26.04.txt` and
`tests/ui/requirements.txt`; qualify affected UI/backend behavior when they
change. A tool's established name does not qualify our adapter.

Before custom orchestration, identify the current scenario's missing capability
or safety boundary. Prefer an existing fixture/API plus a small adapter.
Finish the bounded runner result and move to product coverage; no hypothetical
frameworks or duplicate schedulers, collectors or selectors. Cover owned cleanup,
secrets, provenance and failure reporting with focused regressions. Source/config
checks may protect real interfaces/packaging; prefer executable runtime behavior
to source-string/call-order assertions and retire redundant brittle checks.
Source contracts and harness qualification do not count as product coverage.

## Make every expensive attempt answer a question

For customer E2E the question is whether the declared real customer action
produces its visible result. Observe screens and normal interaction only.
An actual product failure stays failed with reproduction/evidence and a separate
repair blocker; do not investigate its internals in the E2E slice. Continue an
independent customer case or stop for a repair decision. The diagnosis procedure
below applies to necessary runner-safety failures and mechanical package work;
it does not authorize backend product probing in customer scenarios.

Apply [app scope/prerequisite rules](E2E-Coverage.md#scope-tests-around-the-app):
name the app regression or harness guarantee, choose the lowest effective layer,
separate fixture setup from actions under test, and use bounded provisioning
helpers for unrelated OS work. Upstream GUIs or duplicate full journeys require
an app-specific reason.

1. Name the first failing boundary, one hypothesis and a discriminating
   observation; distinguish helper, product, environment, collection and cleanup.
2. Validate parsers/selectors/collectors and failure paths locally. Collect safe
   success/failure diagnostics in the same boot; never export credentials or raw
   authentication terminal data.
3. Run the smallest guarded selection and prerequisite closure through
   [approved categories](Approval-Tools.md#category-coverage-and-future-additions).
   Extend F1's installed selectors for new areas; use the accepted 19A controller
   for ready graphical declarations. Pending selections refuse before VM access.
   Never run guest pytest on the host, invent selectors or bypass guards.
4. Fix the demonstrated cause; prove real success, deliberate denial/failure
   and one interaction before expansion. A failed shared prerequisite proves
   nothing about later assertions; keep those cases registered.
5. After two expensive attempts on one blocker, require new discriminating
   evidence or locally validated observability before a third. A narrower label
   does not reset the count. Before another diagnostic-only run, audit the
   supported operation and relevant OS implementation together; combine remaining
   discriminating observations in one run and state each outcome's next action.
   Once an interface defect is actionable, correct and qualify it instead of
   buying another incremental label with a full journey. Carry counts, rejected
   hypotheses and next observations across chats. Record design/external blockers;
   move only to authorized independent work without weakening boundaries.

An expensive attempt is a full guarded VM/system/E2E run or comparable build,
not a fast parser/unit check. Preserve original failures. Corrected code needs
a new attempt identity; an unchanged diagnostic rerun cannot turn a failed
release run green.

## Verify at the right scope

| Work stage | Required verification |
| --- | --- |
| Local edit/diagnosis | Meaningful relevant unit/component checks; prerequisite safety tests before protected operations. |
| Necessary OS/graphical helper | Focused refusal/cleanup checks, then qualify with its named real consumer; no product-internal proof for customer acceptance. |
| Stable variants | Every affected registered case/shared dependency once; both form surfaces where applicable. |
| Lettered task acceptance | All assigned cases/variants, affected regressions, `make check`, `git diff --check`; exact input identities/scope. |
| Documentation only | Links, references, consistency, `git diff --check`; no product/VM tests. |
| Customer/package acceptance | Current-input complete declared journeys and mechanical checks, separately labeled, plus existing required regressions; report unavailable comprehensive commands truthfully. |

Task verification lists define acceptance scope. Run common checks once after
the stable batch's final code change; repeat only for new changes, failures or
unresolved concerns. Label focused results. Safety prerequisites always run in
isolation before protected operations.

### Decide what invalidates earlier verification

| Change since the recorded result | Next verification |
| --- | --- |
| New chat, unchanged relevant inputs/environment | Check retained result, scope and identities; continue. |
| Documentation only | Links, commands, consistency and whitespace; preserve runtime evidence's original identity. |
| Case, assertion, helper, product or configuration | Affected cases/shared consumers; broaden if dependency closure is uncertain. |
| Tool, baseline, OS, transport, ownership or capture | Affected compatibility/safety, real success/failure and applicable qualification. |
| Task acceptance/final release | Full required scope above. |

Use recorded command/scope, input identities, evidence and subsequent edits.
A commit omits uncommitted inputs; missing provenance prevents pass reuse.
Never disable launcher safety tests to deduplicate checks.

**Artifact reuse is separate.** Today's `VerifiedInputs` requires the manifest's
source digest to match the checkout, including documentation. A documentation
handoff may require a fresh artifact for the next package-bearing VM attempt
despite needing no product tests itself. Do not alter manifests or exclude
paths ad hoc. Task 20 [R1](Task-20.md#bounded-recovery--2026-09-11) owns the
immediate stable source-execution prerequisite; deferred Task 28A retains broad
build-input closure/artifact reuse work. Neither is an available cache today;
preserve the contract until an equivalent replacement is verified.

Register each shared case/assertion once and link requirements/tasks. Applicable
current-input evidence can support related implementation acceptance; final
release still executes every required case. Group independent values only where
a declared continuous scenario's state/interactions allow, under
[coverage selection](E2E-Coverage.md#bound-the-matrix-before-expanding-it).

Ordinary acceptance executes each required case once. Repetition needs a stability
question, selection, count and stop condition. New graphical/cleanup transport
needs three complete qualification smokes, reusable until relevant behavior or
environment changes. No default repeated matrices or ten-run loops; justify
independent attempts for intermittent defects without claiming zero flakiness.

## Handoff format and cost review

### Measure completed customer outcomes

The implementation agent must finish each scenario's
[runtime registration](E2E-Coverage.md#register-each-runnable-scenario-within-its-implementation-task)
within that task. Verify its ready inventory entry for automatic `make test-all`
selection before claiming completion. Routine registration is the agent's work
and requires no manual operator action or separate launcher task.

Carry one cumulative progress record in the active handoff and mirror its compact
values in Continuation.md and the existing structured summary fields. Do not
read the operator log or create another report/telemetry system. Record:

- Completed customer variant IDs, passing-run evidence and confirmed ready
  inventory entries, cumulative completed count, remaining frozen customer scope
  and newly completed variants this slice.
- Actual executed visible steps toward the selected finish line; distinguish
  partial execution, local adapter checks and unexecuted plans.
- Scope additions, deduplication and transfers to engineering separately.
  A reduced denominator is not a completed scenario. Do not expand the finish
  line when a new internal question appears.
- Demonstrated product failures and exact affected cases, infrastructure
  blockers, and the return condition for each deferred case.
- Consecutive implementation slices without a completed customer variant.
  Carry it across chats, model changes and task switches; reset only when a
  complete customer variant passes. The documentation scope reset establishes
  the starting baseline and earns no runtime credit.

After **two customer implementation slices without a completed variant**, require
an intervention before another prerequisite slice: freeze additions and choose
a different concrete route to a visible finish line or a ready independent
customer case. The next slice must deliver that complete case or record a
specific blocker. Do not automatically renew a failed breakthrough or continue
the same dependency chain under a new name. Preserve blocked cases and proceed
only with independent ready work; if none exists, request a repair/scope decision.

A one-off necessary helper can reduce a frozen remaining step, but unit-test
counts, documentation updates, new probes and rewritten plans do not establish
healthy customer progress. Mechanical Tasks 18/20 instead measure completed
qualification milestones and remaining defects under their existing budgets;
installation internals do not become customer-scenario requirements.

### Save a compact continuation

Update one active task handoff, normally 200–400 words, shorter or longer as
needed. Link long evidence; preserve logs/artifacts. Include:

- Task/slice, next observable result and authorized machine/VM scope.
- Actual settings and [next settings](#reassess-model-and-effort-at-every-handoff):
  exact model/effort, lower/raise/keep for each and fresh reason.
- Completed customer outcomes, frozen remaining steps and relevant graphical
  interfaces; mechanical work may record internal facts and scoped read lists.
- Updated shared contracts/map links, regressions, qualification limits and consumers.
- Unresolved hypothesis, attempts, rejected explanations and next observation.
- Tested input identities, commands/selectors, evidence paths/digests and later
  edits (including host-only changes); invalidation conditions and exact next
  host check when known. Label unresolved artifacts; verify acceptance paths.
- Remaining acceptance, exact next action and owned process/VM/cleanup state.
  Record outstanding identities; historical “VM off” is not current state.
  Never duplicate another session's work or overwrite its active handoff.

Reapply [task selection](#start-with-one-bounded-result) and update
[Continuation.md](Continuation.md) for the next eligible task, which may differ:
task/status, handoff link, next slice, settings/reason, and earlier deferrals'
blocker/return links. Aim near 100 words without a second checklist or copied
logs. Keep completed-slice evidence in its task handoff. Check both records
against current edits/evidence, preserving unrelated work; no commit is required.
Reconcile interrupted handoffs from files/evidence, not rerun experiments.

End interactive slices with result, verification scope, unfinished blocker,
handoff link, **“You can end this session”**, and:

> Continue the next unfinished task in docs/Test-Automation.md. This is the dev and host machine.

Unattended slices instead use the [supplied structured report](Unattended-Prompt.md)
and end the turn. On completion, mark the continuation complete and state that
no further implementation session is needed.

When ongoing work needs it, record experiments/results, preparation/test/cleanup
time and already-exposed usage in the active handoff, not a new report or
per-attempt ledger. No telemetry service or log archaeology. Forecast after the
first stable batch from measured cases, helper gaps and real waits; optimize the
dominant cost before adding caches/frameworks. Tokens, model price and VM time
differ: faster boots do not prove token savings.
[Usage guidance](https://learn.chatgpt.com/docs/pricing) lists context, reasoning,
tools and caching as factors, not measured savings for this checkout.
