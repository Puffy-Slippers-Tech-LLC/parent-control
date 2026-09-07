# Remaining test automation implementation

This is an implementation backlog, not the daily test runbook. Use
[docs/Test-Automation.md](../Test-Automation.md) for commands and pass criteria,
[tests/README.md](../../tests/README.md) for test maintenance, and the
[installed runner guide](../../tests/integration/README.md) for reusable VM and
artifact contracts.

The existing foundation supplies pytest unit/property/contracts, private-D-Bus
components, hermetic GTK, child Node/GJS/nested-Shell tests, deterministic app
fixtures, package artifact building, a prepared VM baseline, and the guarded
installed-system runner. Their regression tests remain required. Completed
Tasks 01–13 and historical qualification records have been removed from this
active plan; reuse the implemented interfaces rather than repeating setup.

Start with the [implementation workflow](Implementation-Workflow.md): one
bounded problem, focused experiments, small reading scope, and a fresh chat
after a solved problem. It replaces automatic ten-minute session endings.

The [current continuation](Continuation.md) points to the next session's task
and handoff. The reordered backlog brings [F1](Task-F1.md)'s focused diagnosis
forward from Tasks 28/27 and [19P](Task-19.md#task-19p)'s feasibility check from
19A. Neither restarts completed setup. Task 14's existing work remains in its
[continuation handoff](Task-14.md#continuation-handoff--2026-09-06-incomplete).
Finish an already-running owned guarded attempt and its cleanup before changing
implementation tasks. Do not duplicate changing evidence or machine state here.

To continue building automation, say:

> Continue the next unfinished task in docs/Test-Automation.md. This is the dev and host machine.

To resume a particular problem, name its task and handoff explicitly. “Run
docs/Test-Automation.md” requests a test run; it does not advance this backlog.

## Implementing one task

1. Read `AGENTS.md`, [Continuation.md](Continuation.md), this selection procedure,
   the selected task's header/active handoff, and the relevant
   [workflow](Implementation-Workflow.md) rules. Keep this initial routing read
   small; do not investigate code or run tests before model confirmation.
   After confirmation, consult the [system design](../System-Design.md) when
   understanding architecture, then only the owning module and relevant
   specification IDs. Read changed files and the unresolved question, not every
   design/task document or archived investigation.
2. Resume the continuation's unfinished task when its dependencies are met.
   Otherwise select the first ready unchecked item below. The checklist owns
   completion; the continuation is a pointer, not another checklist. If it is
   absent or stale, reconcile against the checklist and the selected task's
   latest handoff/current files, without replaying completed work. A recorded
   external/design blocker stays unchecked and blocks dependent acceptance;
   independent ready work may proceed. If nothing is ready, report the concrete
   blocker and save the continuation. If all items are complete, record completion
   and tell the user the roadmap is finished; do not restart it or rerun suites.
3. State the selected task, one next observable result, planned slice budget,
   and the latest applicable handoff's recommended model and reasoning effort,
   including its reason. That recommendation takes precedence over the task
   header's initial defaults; [reassess it](Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff)
   if intervening changes alter the remaining work. Ask the user to confirm both settings
   and wait for an explicit “Go ahead” before implementation. **Ask at every new
   session, even for the same task and previously selected settings**, as requested
   by the user's [session loop](../Test-Automation.md#continue-implementation-in-fresh-sessions).
   A previous session's confirmation is historical context. Once confirmed in
   this session, proceed without asking again unless recommending a setting
   change. Mention this documented user preference as the reason for the pause.
   The standard prompt confirms this is the development/host machine; retain
   the recorded VM scope without another machine-selection question.
4. Execute one bounded slice of that task using the workflow's experiment
   budget. Prove the helper's basic success/failure before expanding variants.
   Batch routine cases that reuse it; hand off before an unrelated next problem.
   Preserve concurrent changes. Honor the authorized execution location; resolve any genuine
   machine ambiguity before VM mutation. Do not install the product on the
   development host or recreate the accepted environment.
5. Use focused checks during iteration and the task's full assigned scope for
   acceptance, following [verification scope](Implementation-Workflow.md#verify-at-the-right-scope).
   Run `make check` and `git diff --check` once after the final code change in a
   stable batch; context resets alone do not invalidate tests. Always run the
   applicable safety prerequisites before protected operations. Documentation
   reviews use links/reference/consistency checks and `git diff --check`, with
   no product tests, VM operations or model-selection pause.
6. Mark its single checklist entry complete only when deliverables and
   verification pass. Record a concise result and evidence reference in that
   task's document and update reusable contracts in the test guides.
   Missing work stays unchecked; never lower assertions to claim completion.
7. Save a 200–400-word [handoff](Implementation-Workflow.md#handoff-format-and-cost-review)
   at a solved problem boundary or context/budget review. Preserve the current
   hypothesis and attempts spent if unfinished. Complete owned operation cleanup
   before a fresh chat; do not restart a useful VM attempt to meet a timer.
   Reevaluate both model and effort for the next slice: lower, raise or keep
   each as its remaining difficulty warrants, with a short reason. Update the
   task handoff first, then mirror the recommendation and reason in
   [Continuation.md](Continuation.md). Point
   to the same task if unfinished and ready, or the next ready task if complete
   or blocked. Give an unstarted next task a concrete first slice. End the turn
   by saying the user can end this session and reuse the standard prompt.
   Do not automatically start the next slice or task in this session.
8. Remove obsolete one-time instructions after retaining reusable contracts and
   required evidence references. Do not make every continuation reread them.

An explicit documentation review may inspect and revise every relevant task.
Remove obsolete completed work only after retaining contracts or unresolved
handoffs still needed by future tasks. Do not delete tests, source logs, saved
evidence or the VM baseline as documentation cleanup.

## Shared implementation and acceptance rules

- Use maintained public APIs. The broker remains the policy and authorization
  authority. Preserve real caller validation and other-user isolation.
- Installed-system tests use actual processes, credentials and OS services.
  Local unit/component doubles do not fulfill installed or E2E acceptance.
- Every graphical task follows [E2E-Coverage.md](E2E-Coverage.md). Enumerate
  complete customer journeys and all required variants before implementing
  them; keep visible, authoritative and other-user evidence. Fault/recovery and
  controlled-environment cases are labeled separately and do not replace
  ordinary customer operations.
- Use the fixed existing VM and its guarded lease. The retained product-free
  baseline is an outer preparation/cleanup boundary only; no new snapshots,
  copies, overlays or in-journey restores. Source shares must be detached before
  test boot. Graphical backend compatibility with this ownership contract is
  checked early in Task 19P before committing to its runner or scenarios.
- Run cleanup-safety regressions in isolation before operations that terminate
  processes. Signal only explicitly spawned, identity-recorded processes.
  Non-VM UI pytest uses `tools/run-ui-tests` directly.
- Bound waits by observable readiness and deadlines. Wait for real product
  durations when time itself is under test. Preserve first failures; a later
  passing diagnostic attempt does not rewrite a failed result.
- Add useful stage/outcome/error-category logging without PII. Read product
  logs at `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log`; do not
  modify them. Redact only copied diagnostic artifacts.
- Update `setup.sh` for required host dependency changes. Classify new packaged
  integrations under [Package-Update.md](../Package-Update.md); ship migrations
  under [Data-Migration.md](../Data-Migration.md) before incompatible readers or
  writers. Shared form changes cover kiosk and child-overlay modes.
- Keep product/test inputs tied to one source content identity, including local
  changes. Exact package and fixture evidence must survive actual reboot,
  failure and cleanup. Supplemental migration/activation packages are distinct
  from the release artifact.
- The four daily commands and selection semantics are defined once in the
  [daily guide](../Test-Automation.md#daily-commands). One inventory and runner
  dispatch serves local use and CI. Existing focused `check-*` commands remain
  usable until the public aliases are implemented.
- One-time preparation and repeated harness qualification are excluded from
  ordinary `test-*` runs. Every required regression/variant still runs once;
  no formerly passing test is permanently exempted.

## Requirement and evidence maintenance

`tests/requirements.json` maps stable `ONPC-...` specification IDs to required
layers and executable evidence. Preserve IDs when wording is clarified and add
one for a new normative obligation, including a nested obligation. Existing
file references are structural checks, not proof that assertions ran.

Use `python3 tools/verify_test_traceability.py --mode stage` after specification
or mapping changes; ordinary `make check` retains stage mode. Only mark actual
runtime coverage `covered`. Source contracts support architecture checks but
cannot replace runtime acceptance.

F1 establishes selected test identities and diagnostic evidence; Tasks 19/27
extend the same contracts to graphical steps and all layers. Task 28 joins
expected and executed inventories and final-mode traceability.
Include harness, build and static regressions with no product requirement ID.
Missing/skipped/xfailing/flaky/failed evidence, wrong layers, stale artifacts,
partial journeys and failed cleanup prevent a complete pass. Review both
specification and architecture/lifecycle/threat coverage; resolve contradictions
explicitly instead of silently inventing a new guarantee or discarding a gap.

## Unfinished tasks

This is the single authoritative checklist. Each linked section is one task;
its initial model/effort recommendation remains there. The active handoff owns
the reassessed recommendation for its remaining slice. Task numbers identify coverage
ownership, not equal effort or an obligation to wait for unrelated earlier
numbers. No second checklist is needed for individual slices.

The order delivers focused feedback and resolves graphical feasibility first,
then proves installed authorization and the graphical install path before
expanding policy/lifecycle matrices. Later tasks extend these helpers. Required
coverage remains unchanged; these milestones are partial implementation results,
not release passes. Use measured slice/attempt times to forecast remaining work.

- [x] [Task F1 — Focused installed diagnosis, moved forward from Tasks 28/27](Task-F1.md)
- [x] [Task 19P — Prove graphical backend compatibility](Task-19.md#task-19p)
- [ ] [Task 14 — Test installed broker identity and authorization boundaries](Task-14.md)
- [ ] [Task 19A — Add the guarded os-autoinst worker and console transport](Task-19.md#task-19a)
- [ ] [Task 19B — Add stable screen matching and graphical smoke](Task-19.md#task-19b)
- [ ] [Task 20 — Automate clean installation, reboot, and startup readiness](Task-20.md)
- [ ] [Task 15A — Test installed catalog and application launch enforcement](Task-15.md#task-15a)
- [ ] [Task 15B — Test process confinement and execution-policy rollback](Task-15.md#task-15b)
- [ ] [Task 16A — Test real usage, grant arithmetic, midnight, and DST](Task-16.md#task-16a)
- [ ] [Task 16B — Test PAM login/unlock and managed-session lifetime](Task-16.md#task-16b)
- [ ] [Task 17A — Complete session-entry transaction and race regressions](Task-17.md#task-17a)
- [ ] [Task 17B — Prove expired and replacement grants on the installed system](Task-17.md#task-17b)
- [ ] [Task 18A — Test all package activation classes](Task-18.md#task-18a)
- [ ] [Task 18B — Test migration interruption, retry, and invalid data](Task-18.md#task-18b)
- [ ] [Task 18C — Test real package removal, reinstall, and purge](Task-18.md#task-18c)
- [ ] [Task 21A — Automate Parent discovery, navigation, and validation](Task-21.md#task-21a)
- [ ] [Task 21B — Automate Parent saves, live policy, and revocation](Task-21.md#task-21b)
- [ ] [Task 22A — Prove lock, retained-session unlock, and fresh-login enforcement](Task-22.md#task-22a)
- [ ] [Task 22B — Automate countdown display, visibility, and estimate recovery](Task-22.md#task-22b)
- [ ] [Task 23A — Automate real authentication and atomic child approval](Task-23.md#task-23a)
- [ ] [Task 23B — Automate shared form validation, choices, and overlay exit](Task-23.md#task-23b)
- [ ] [Task 24A — Prove restricted kiosk startup and authentication-agent recovery](Task-24.md#task-24a)
- [ ] [Task 24B — Complete kiosk form, approval, persistence, and logout cases](Task-24.md#task-24b)
- [ ] [Task 25A — Automate graphical launch-route and matching matrices](Task-25.md#task-25a)
- [ ] [Task 25B — Prove multi-session termination and grant isolation](Task-25.md#task-25b)
- [ ] [Task 26A — Prove adversarial transaction races and failure recovery](Task-26.md#task-26a)
- [ ] [Task 26B — Complete restart and persistence scenarios](Task-26.md#task-26b)
- [ ] [Task 26C — Complete continuous customer journeys and coverage enumeration](Task-26.md#task-26c)
- [ ] [Task 27A — Define and enforce the shared evidence and redaction contract](Task-27.md#task-27a)
- [ ] [Task 27B — Wire the remaining runners to the evidence contract](Task-27.md#task-27b)
- [ ] [Task 27C — Finish bounded waits and flake classification](Task-27.md#task-27c)
- [ ] [Task 28A — Implement the four test commands, CI, and the comprehensive gate](Task-28.md#task-28a)
- [ ] [Task 28B — Audit executable traceability and pass the release gate](Task-28.md#task-28b)
- [ ] [Task 28C — Finish the operator runbook and evidence index](Task-28.md#task-28c)
