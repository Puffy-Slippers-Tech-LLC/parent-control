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

Use the [implementation workflow](Implementation-Workflow.md): quality first,
one bounded problem, focused experiments and a durable handoff. The
[reuse map](Reuse-Map.md) routes every remaining task to shared work and records
cross-task gaps found in the documentation review. Read the selected row and its
relevant contract/limitation links before investigating shared infrastructure.
Publish shared fixes through the [reuse workflow](Implementation-Workflow.md#reuse-established-tools-and-bound-harness-work)
so later tasks inherit their implementation, regression coverage and known limits.

The [current continuation](Continuation.md) points to the next session's task
and handoff. The reordered backlog brings [F1](Task-F1.md)'s focused diagnosis
forward from Tasks 28/27 and [19P](Task-19.md#task-19p)'s feasibility check from
19A. Neither restarts completed setup. Task 14 is accepted; its
[completion handoff](Task-14.md#completion-handoff--2026-09-06-accepted) retains
the final evidence. Task 19A is also accepted; its
[controller audit](Evidence/19A-Controller-Acceptance-20260907.md) retains the
live execution and failure evidence. Select the next eligible entry in the
checklist's order under the [session procedure](Implementation-Workflow.md#start-with-one-bounded-result);
the continuation must reflect that selection.
Finish an already-running owned guarded attempt and its cleanup before changing
implementation tasks. Do not duplicate changing evidence or machine state here.

To continue building automation, say:

> Continue the next unfinished task in docs/Test-Automation.md. This is the dev and host machine.

To resume a particular problem, name its task and handoff explicitly. “Run
docs/Test-Automation.md” requests a test run; it does not advance this backlog.

## Implementing one task

Follow the [session procedure](Implementation-Workflow.md#start-with-one-bounded-result)
and its [output](Implementation-Workflow.md#reduce-unnecessary-model-output),
verification and handoff rules; they are maintained there once. Use the
checklist below for completion and each task's dependencies, deliverables and
acceptance criteria for scope. A completed slice alone never checks off a task.

An explicit documentation review may inspect and revise every relevant task.
It requires links/reference/consistency checks and `git diff --check`, with no
product tests, VM operations or implementation model-selection pause.
Remove obsolete completed work only after retaining contracts or unresolved
handoffs still needed by future tasks. Do not delete tests, source logs, saved
evidence or the VM baseline as documentation cleanup.

## Shared implementation and acceptance rules

- The operator has cleared the historical VM/writer-pause hold for **all
  tasks**. Apply [VM availability for all tasks](Implementation-Workflow.md#vm-availability-for-all-tasks),
  including its precedence over earlier evidence and handoffs. Proceed with
  dependency-ready guarded runs; no repeated coordination confirmation is due.
- Use maintained public APIs. The broker remains the policy and authorization
  authority. Preserve real caller validation and other-user isolation.
- Installed-system tests use actual processes, credentials and OS services.
  Local unit/component doubles do not fulfill installed or E2E acceptance.
- Apply the [app scope and prerequisite rules](E2E-Coverage.md#scope-tests-around-the-app)
  to every remaining task. Use reliable supported helpers for unrelated OS
  setup; assert the app's response. Test app-owned PAM/Polkit integration, not
  general Ubuntu password or account-management behavior.
- Every graphical task follows [E2E-Coverage.md](E2E-Coverage.md). Audit each
  variant's risk, layer and interacting dimensions before implementation. Keep
  complete required journeys and visible, authoritative and other-user evidence;
  place equivalent validation at its lowest effective layer. Fixture setup,
  fault/recovery and controlled-environment events have distinct evidence and
  cannot substitute for the product actions a journey claims to prove.
- Reuse the [established tools and bounded harness](Implementation-Workflow.md#reuse-established-tools-and-bound-harness-work).
  Add infrastructure only for an identified scenario or safety gap. Source
  contracts and runner qualification are supporting evidence, not customer
  behavior or a reason to defer product coverage indefinitely.
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
  under [Data migration](../SystemDesign/Data-Migration.md) before incompatible readers or
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

Use `tools/run-tests traceability stage` after specification
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
the reassessed recommendation for its remaining slice under the
[quality and weekly-allowance policy](Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff).
The launcher uses that choice from Continuation.md for each fresh session;
historical pinned settings are not mandates. Task numbers identify coverage
ownership, not equal effort or numeric execution order. The displayed checklist
order governs selection: take the earliest ready unchecked entry and record any
earlier deferral under the [session procedure](Implementation-Workflow.md#start-with-one-bounded-result).
Recheck deferrals at each safe slice boundary; a later task's active handoff does
not override an earlier task whose blocker has cleared. No second checklist is
needed for individual slices.

The order delivers focused feedback and resolves graphical feasibility first,
then proves installed authorization and the graphical install path before
expanding policy/lifecycle matrices. Later tasks extend these helpers. Required
coverage remains unchanged; these milestones are partial implementation results,
not release passes. Use measured slice/attempt times to forecast remaining work.

- [x] [Task F1 — Focused installed diagnosis, moved forward from Tasks 28/27](Task-F1.md)
- [x] [Task 19P — Prove graphical backend compatibility](Task-19.md#task-19p)
- [x] [Task 14 — Test installed broker identity and authorization boundaries](Task-14.md)
- [x] [Task 19A — Add the guarded os-autoinst worker and console transport](Task-19.md#task-19a)
- [x] [Task 19B — Add stable screen matching and graphical smoke](Task-19.md#task-19b)
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
