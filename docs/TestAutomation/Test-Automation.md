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

The first unfinished item is Task 14. Its
[continuation handoff](Task-14.md#continuation-handoff--2026-09-05-incomplete)
is the authoritative location for current remaining work, accepted interfaces,
and evidence needed to resume. Do not duplicate changing pass counts, temporary
paths, or machine state here.

## Implementing one task

1. Read `AGENTS.md`, the [system design](../System-Design.md), the
   [specification](../Specification.md), this plan, and the selected task's
   shared introduction and section. Read referenced durable contracts as
   needed; do not reread completed implementation instructions.
2. Select the first unchecked item below. Report its task-local recommended
   model/effort and stop before implementation unless the current user/session
   has already authorized that task and setting. The existing Task 14 handoff's
   resumption authorization remains applicable.
3. Execute that one lettered task in dependency order. Preserve concurrent
   changes. Honor the authorized execution location; resolve any genuine
   machine ambiguity before VM mutation. Do not install the product on the
   development host or recreate the accepted environment.
4. Run the task's verification and required safety prerequisites. Runtime/test
   implementation requires `make check` and `git diff --check` as common
   checks. A documentation-only review uses link/reference/consistency checks
   and `git diff --check`; it does not trigger tests, VM operations, or a model
   switch just because a task document contains verification commands.
5. Mark its single checklist entry complete only when deliverables and
   verification pass. Record a concise result and evidence reference in that
   task's document, update reusable contracts in the test guides, and stop.
   Missing work stays unchecked; never lower assertions to claim completion.
6. For task implementation exceeding ten minutes, use the next clean checkpoint
   to save a concise continuation handoff in the task document: remaining work,
   suitable model/effort, exact selectors, artifact identities, current machine
   state and recovery needs. Preserve evidence and pause. This checkpoint rule
   is for implementation; it does not interrupt an explicitly authorized
   documentation cleanup or change how a future test command runs.
7. If the things that are one-time, no longer needed in future daily maintenance (i.e.,
   make test-* commands), remove once the job is done.

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
  an explicit Task 19A prerequisite, not an assumed capability.
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

Tasks 19/27 add scenario/test/variant/step identities and current-run evidence;
Task 28 joins expected and executed inventories and final-mode traceability.
Include harness, build and static regressions with no product requirement ID.
Missing/skipped/xfailing/flaky/failed evidence, wrong layers, stale artifacts,
partial journeys and failed cleanup prevent a complete pass. Review both
specification and architecture/lifecycle/threat coverage; resolve contradictions
explicitly instead of silently inventing a new guarantee or discarding a gap.

## Unfinished tasks

This is the single authoritative checklist. Each linked lettered section is
one implementation task; its model/effort recommendation remains in that
section. Do not maintain a second checkbox or a copied completion chronology.

- [ ] [Task 14 — Test installed broker identity and authorization boundaries](Task-14.md)
- [ ] [Task 15A — Test installed catalog and application launch enforcement](Task-15.md#task-15a)
- [ ] [Task 15B — Test process confinement and execution-policy rollback](Task-15.md#task-15b)
- [ ] [Task 16A — Test real usage, grant arithmetic, midnight, and DST](Task-16.md#task-16a)
- [ ] [Task 16B — Test PAM login/unlock and managed-session lifetime](Task-16.md#task-16b)
- [ ] [Task 17A — Complete session-entry transaction and race regressions](Task-17.md#task-17a)
- [ ] [Task 17B — Prove expired and replacement grants on the installed system](Task-17.md#task-17b)
- [ ] [Task 18A — Test all package activation classes](Task-18.md#task-18a)
- [ ] [Task 18B — Test migration interruption, retry, and invalid data](Task-18.md#task-18b)
- [ ] [Task 18C — Test real package removal, reinstall, and purge](Task-18.md#task-18c)
- [ ] [Task 19A — Add the guarded os-autoinst worker and console transport](Task-19.md#task-19a)
- [ ] [Task 19B — Add stable screen matching and graphical smoke](Task-19.md#task-19b)
- [ ] [Task 20 — Automate clean installation, reboot, and startup readiness](Task-20.md)
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
