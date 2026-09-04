# Test automation execution plan

## Summary

- Use a layered test system. `pytest` owns host-safe unit, property, contract,
  and component tests; `autopkgtest` owns installed Debian-package and operating-
  system integration tests; `os-autoinst` with its QEMU backend owns graphical
  end-to-end scenarios across installation, reboot, GDM, parent, child, kiosk,
  lock, and unlock screens.
- Preserve the existing guarded VM provisioning and redacted artifact collection.
  Do not turn the existing SSH/libvirt harness into a custom screen automation
  framework.
- Task 12 has one explicit preparation exception for the existing
  `ubuntu26.04` VM: an operator runs `make prep-vm` there once to create the
  fixed test accounts, without installing the product, and then runs
  `make prep-host` manually on the development host to capture a powered-off,
  pre-install baseline. Never execute product tests in that source VM. Later
  installed-system and end-to-end runs must use disposable guests derived from
  the captured baseline and must not expose a writable host filesystem such as
  the source VM's `/Data` virtiofs share.
- The Task 12 source VM already exists and uses
  `/Data/virt-manager/ubuntu26.04.qcow2`; its repository checkout is available
  at `/Data/Code/PST/parent-control`, the same path as on the development host.
  Task 12 must not download a cloud image or create a replacement source VM.
- Test the exact Debian package artifact as the sole release path. Record the
  artifact digest in every VM result.
- Give every normative statement in `Specification.md` a stable requirement ID
  and maintain machine-checked traceability from each ID to executable tests and
  collected evidence.
- Keep every critical end-to-end assertion three-sided: verify the visible user
  result, the authoritative backend state, and the absence of effects on other
  users.
- Use current public interfaces only. Pin current test-tool versions. In
  particular, use Dogtail 2.x rather than Ubuntu's legacy Dogtail 1.x package,
  and use the stable public os-autoinst test API.
- Expired-grant reconciliation follows the current specification and
  `System-Design.md`: expiry locks without immediately closing applications;
  session entry re-reads the grant under the broker transaction lock. An
  expired grant restores complete policy and closes blocked apps, while an
  active replacement grant preserves its approved policy and processes.
  Task 17 completes verification and any demonstrated gaps in this existing
  path. Do not introduce the obsolete natural-expiry scheduler.
- The sequence below is fixed. There are no optional tasks, alternate paths, or
  decision branches.

## Progress checklist

Execution rule (task implementation only): a fresh Codex session must read
`AGENTS.md`, this entire file, `Specification.md`, and `System-Design.md`;
locate the first unchecked task below;
read its task document's shared introduction and selected task section; report
that task's recommended model and reasoning effort; and stop before making
changes. After the user switches to that model and effort and asks Codex to
execute, Codex must execute exactly that one task, run its stated verification,
change its checkbox from `[ ]` to `[x]`, append its completion record at the end
of this file, and stop. Never execute a second task in the same session. Never
redo a checked task. Running already-created regression tests as verification for
the current task is required and does not count as redoing prior work. A task
that is incomplete or blocked remains unchecked and receives no completion
record. Update both checklist copies when completing a task.

An explicit request to review or revise this plan is documentation work, not
execution of the first unchecked task. For that request, read all requested
unfinished tasks and update their scope, sequencing, and recommendations without
requiring a model-switch pause. Preserve completed tasks and completion records.

- [x] Task 01 — Establish specification IDs and executable traceability
- [x] Task 02 — Adopt pytest without rewriting the existing unit suite
- [x] Task 03 — Establish test categories, static checks, and coverage reporting
- [x] Task 04 — Add broker property and state-machine testing
- [x] Task 05 — Add a real private-D-Bus broker component harness
- [x] Task 06 — Establish modern hermetic GTK automation
- [x] Task 07 — Automate the Parent App as a local component
- [x] Task 08 — Automate the shared kiosk and child request form locally
- [x] Task 09 — Add executable unit tests for child-extension JavaScript
- [x] Task 10A — Refactor the child preview into reusable orchestration
- [x] Task 10B — Add the isolated nested-Shell lifecycle smoke
- [x] Task 10C — Automate child indicator request interaction
- [x] Task 10D — Verify reload, preserve artifacts, and finish integration
- [x] Task 11 — Build deterministic native and Flatpak test applications
- [x] Task 12A — Add guarded in-VM test-account preparation
- [ ] Task 12B — Add host-only pre-install baseline capture
- [ ] Task 12C — Capture and verify the prepared VM baseline
- [ ] Task 13A — Build reproducible package and fixture artifacts
- [ ] Task 13B — Add the guarded autopkgtest QEMU runner and install smoke
- [ ] Task 14 — Test installed broker identity and authorization boundaries
- [ ] Task 15A — Test installed catalog and application launch enforcement
- [ ] Task 15B — Test process confinement and execution-policy rollback
- [ ] Task 16A — Test real usage, grant arithmetic, midnight, and DST
- [ ] Task 16B — Test PAM login/unlock and managed-session lifetime
- [ ] Task 17A — Complete session-entry transaction and race regressions
- [ ] Task 17B — Prove expired and replacement grants on the installed system
- [ ] Task 18A — Test all package activation classes
- [ ] Task 18B — Test migration interruption, retry, and invalid data
- [ ] Task 19A — Add the guarded os-autoinst worker and console transport
- [ ] Task 19B — Add stable screen matching and graphical smoke
- [ ] Task 20 — Automate clean installation, reboot, and startup readiness
- [ ] Task 21A — Automate Parent discovery, navigation, and validation
- [ ] Task 21B — Automate Parent saves, live policy, and revocation
- [ ] Task 22A — Prove lock, retained-session unlock, and fresh-login enforcement
- [ ] Task 22B — Automate countdown display, visibility, and estimate recovery
- [ ] Task 23A — Automate real authentication and atomic child approval
- [ ] Task 23B — Automate shared form validation, choices, and overlay exit
- [ ] Task 24A — Prove restricted kiosk startup and authentication-agent recovery
- [ ] Task 24B — Complete kiosk form, approval, persistence, and logout cases
- [ ] Task 25A — Automate graphical launch-route and matching matrices
- [ ] Task 25B — Prove multi-session termination and grant isolation
- [ ] Task 26A — Prove adversarial transaction races and failure recovery
- [ ] Task 26B — Complete restart and persistence scenarios
- [ ] Task 27A — Define and enforce the shared evidence and redaction contract
- [ ] Task 27B — Wire the remaining runners to the evidence contract
- [ ] Task 27C — Finish bounded waits and flake classification
- [ ] Task 28A — Install CI jobs and the serial release command
- [ ] Task 28B — Audit executable traceability and pass the release gate
- [ ] Task 28C — Finish the operator runbook and evidence index

## Rules for every task

1. Default computer running the task is dev machine, and the app is not allowed
   to be installed. The dev machine is also a host of a test VM where app is to be
   installed and tested. If the task or any steps in it requires test machine (VM),
   clarify and wait for confirmation before proceeding to ensure the right change job
   is done on the right machine.
2. Execute tasks strictly in checklist order. Do not skip, combine, reorder, or
   begin a later task.
   Every lettered checklist item is a separate task, including sections that
   share a document (for example 13A and 13B). Read the shared introduction and
   only the selected section; finish and record that section, then stop for the
   next task's model selection. Task 12's manual preparation/read-only acceptance
   boundary remains unchanged.
3. Inspect the current worktree before editing. Preserve user changes and avoid
   unrelated cleanup.
4. Use `docs/System-Design.md` for architecture and trust boundaries. Preserve
   the broker as the authority and preserve real-caller validation on system
   D-Bus.
5. Use only maintained public APIs. Do not introduce hidden production D-Bus
   methods, test-only authorization bypasses, private GNOME Shell APIs, QEMU
   monitor hacks, or host-window coordinate automation.
6. Add useful stage, outcome, and error-category logging for changed runtime
   behavior. Never log a password, authentication token, private key, raw user
   data, or other PII. Use labels such as `[Child user]`, `[Administrator]`, and
   `[Request surface]`.
7. Read troubleshooting evidence from
   `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log` and the relevant
   journals. Never modify or delete logs.
8. Classify every new packaged system-integration file according to
   `docs/Package-Update.md` and add or update activation tests in the same task.
9. Complete and ship a migration according to `docs/Data-Migration.md` before a
   changed reader or writer uses incompatible saved data.
10. Treat the kiosk form and child overlay as two modes of one shared GTK GUI.
    Every form change and every form test must cover both modes.
11. Keep host-safe and guest-mutating commands visibly separate. `make check`
    must remain safe for the development host. VM mutation must pass all fixed
    environment and identity guards defined by its task. The Task 12 preparation
    commands use their documented, validated defaults and require no VM, image,
    UUID, or output-directory arguments.
12. Use event-driven waits with bounded deadlines. Fixed sleeps are permitted
    only for a documented product duration that is itself under test.
13. Do not make a flaky assertion pass by retrying it. A whole-run rerun may
    classify a flake, but a release remains failed after any failed attempt.
14. Mark the task complete only after all task deliverables exist, focused tests
    pass, `make check` passes, documentation reflects the new commands, and
    `git diff --check` passes.
15. The completion record must contain the task identifier, completion date, short
    result, verification commands, and relevant commit hash when a commit exists.
    Include a concise handoff with the implemented helper/API contract, exact
    focused test selectors, artifact locations, and any remaining coverage
    assigned to the next task. Reuse this handoff rather than rereading completed
    task documents or reimplementing their fixtures.
16. Before any host-integrated test that terminates processes, run its
    cleanup-safety regressions in isolation. Cleanup may signal only explicitly
    spawned, identity-recorded processes; never infer ownership from names,
    environment variables, runtime directories, or host-wide `/proc` scans.
    Non-VM UI pytest runs must use `tools/run-ui-tests --timeout <duration>
    <pytest-arguments>` directly.
17. Recommendations apply to the bounded task as written. If verification exposes
    a deeper defect, preserve evidence and reassess the affected implementation
    work; never lower acceptance criteria to fit a cheaper model. All tasks
    remain mandatory regardless of the model used.

## Requirement-ID and traceability maintenance

Every normative bullet in `docs/Specification.md` begins with one stable
`ONPC-...` requirement ID. Preserve an existing ID when wording is clarified;
assign a new ID only for a new normative obligation and retire an ID only when
the obligation is removed. Nested normative bullets, including application
policy states, are independent requirements.

`tests/requirements.json` is the authoritative mapping. Each record contains
the ID, specification section, responsible component, required test layer,
executable test references, supporting source-contract references, evidence
type, and coverage state. Test references must be repository-relative existing
files under `tests/`. A supporting contract is never acceptance evidence. Mark
a record `covered` only after its runtime test actually executes the stated
behavior; `planned` is permitted only while the validator runs in stage mode.
The final release mode rejects planned records and records without executable
test references.

Run `python3 tools/verify_test_traceability.py --mode stage` after every
specification or test mapping change. `make check` runs this command in stage
mode. Task 28A wires the release gate to `--mode final`; Task 28B closes and
verifies every release mapping. Ordinary `make check` retains stage mode.

## Target suite interfaces

The completed plan exposes these stable entry points:

- `make check`: syntax, static contracts, traceability validation that is valid
  at the current plan stage, and host-safe unit tests.
- `make check-component`: host-safe private-D-Bus, hermetic GTK, JavaScript, and
  nested-shell component tests.
- `make check-system VM_IMAGE=<explicit-path>`: installed-package tests in a
  guarded disposable QEMU overlay.
- `make check-e2e VM_IMAGE=<explicit-path> SCENARIO=<explicit-name>`: one
  graphical os-autoinst scenario in a disposable QEMU overlay.
- `make check-release VM_IMAGE=<explicit-path>`: the final serial release gate,
  covering the full requirement manifest without skips or expected failures.

These commands are introduced by the tasks below. Earlier tasks use the commands
that already exist at that point in the sequence.

## Model and effort selection — reviewed 2026-09-04

The 18 unfinished tasks were reviewed as full scopes and are now 34 separately
executable tasks. These assignments are engineering judgments about this repo,
not measured cost-per-task results. Completed tasks retain their original text.

OpenAI's current catalog positions Astra for the hardest work, Sol for complex
professional work, Terra for balanced capability/cost, and Luna for
cost-sensitive work. The published standard API input/output rates below are
per million tokens, not Codex subscription charges.
[Official model catalog](https://developers.openai.com/api/docs/models).

| Model | API input / output | Use in this plan |
| --- | --- | --- |
| `gpt-6-astra` | $10 / $50 | VM/storage ownership, real authorization, process/session isolation, transaction races |
| `gpt-5.6-sol` | $4 / $20 | Bounded cross-service integration, real authentication, migration, redaction, acceptance audit |
| `gpt-5.6-terra` | $2 / $12 | Existing-framework test matrices, UI journeys, adapters, CI wiring |
| `gpt-5.6-luna` | $0.20 / $1.20 | Fixed-contract artifact adapters and documentation from verified evidence |

Use `medium` for bounded implementation and `low` for the final runbook.
Use `high` for security-sensitive integration; reserve `xhigh` for Task 26A's
adversarial concurrency/failure matrix. No task needs `max` by default.
These efforts are supported by the documented models; Astra does not support
`none`. [Astra model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra).

Higher per-token price does not by itself predict total task cost: retries,
reasoning/output volume, and context rereads matter. OpenAI reports token
efficiency gains for Astra on some evaluations, not a guarantee for this repo.
[Official model guidance](https://developers.openai.com/api/docs/guides/latest-model).
Keep tightly coupled safety implementation and its regressions together; split
only where a tested interface lets a cheaper model complete the follow-up.
Runtime duration alone is not a reason to use a stronger model, and longer VM
waits do not need higher reasoning effort.

The table assumes the selected model is available in the execution session.
The official catalog currently describes staged Astra access; these
recommendations do not establish availability for every account. Record the
actual model/effort with execution evidence if it differs from the recommendation.

## Task documents

Each link selects one executable task. Some documents contain multiple lettered
sections; read the shared introduction and the linked section only. A fresh
execution session reads this master document and the first unchecked task, not
other task documents or later sections. The model/effort suffixes below mirror
the recommendations in those sections.

- [x] [Task 01 — Establish specification IDs and executable traceability](Task-01.md)
- [x] [Task 02 — Adopt pytest without rewriting the existing unit suite](Task-02.md)
- [x] [Task 03 — Establish test categories, static checks, and coverage reporting](Task-03.md)
- [x] [Task 04 — Add broker property and state-machine testing](Task-04.md)
- [x] [Task 05 — Add a real private-D-Bus broker component harness](Task-05.md)
- [x] [Task 06 — Establish modern hermetic GTK automation](Task-06.md)
- [x] [Task 07 — Automate the Parent App as a local component](Task-07.md)
- [x] [Task 08 — Automate the shared kiosk and child request form locally](Task-08.md)
- [x] [Task 09 — Add executable unit tests for child-extension JavaScript](Task-09.md)
- [x] [Task 10A — Refactor the child preview into reusable orchestration](Task-10A.md)
- [x] [Task 10B — Add the isolated nested-Shell lifecycle smoke](Task-10B.md)
- [x] [Task 10C — Automate child indicator request interaction](Task-10C.md)
- [x] [Task 10D — Verify reload, preserve artifacts, and finish integration](Task-10D.md)
- [x] [Task 11 — Build deterministic native and Flatpak test applications](Task-11.md)
- [x] [Task 12A — Add guarded in-VM test-account preparation](Task-12A.md)
- [ ] [Task 12B — Add host-only pre-install baseline capture](Task-12B.md) — `gpt-6-astra` / `high`
- [ ] [Task 12C — Capture and verify the prepared VM baseline](Task-12C.md) — `gpt-5.6-terra` / `medium`
- [ ] [Task 13A — Build reproducible package and fixture artifacts](Task-13.md#task-13a) — `gpt-5.6-terra` / `medium`
- [ ] [Task 13B — Add the guarded autopkgtest QEMU runner and install smoke](Task-13.md#task-13b) — `gpt-6-astra` / `high`
- [ ] [Task 14 — Test installed broker identity and authorization boundaries](Task-14.md) — `gpt-6-astra` / `high`
- [ ] [Task 15A — Test installed catalog and application launch enforcement](Task-15.md#task-15a) — `gpt-5.6-terra` / `high`
- [ ] [Task 15B — Test process confinement and execution-policy rollback](Task-15.md#task-15b) — `gpt-6-astra` / `high`
- [ ] [Task 16A — Test real usage, grant arithmetic, midnight, and DST](Task-16.md#task-16a) — `gpt-5.6-sol` / `high`
- [ ] [Task 16B — Test PAM login/unlock and managed-session lifetime](Task-16.md#task-16b) — `gpt-6-astra` / `high`
- [ ] [Task 17A — Complete session-entry transaction and race regressions](Task-17.md#task-17a) — `gpt-6-astra` / `high`
- [ ] [Task 17B — Prove expired and replacement grants on the installed system](Task-17.md#task-17b) — `gpt-5.6-sol` / `high`
- [ ] [Task 18A — Test all package activation classes](Task-18.md#task-18a) — `gpt-5.6-terra` / `high`
- [ ] [Task 18B — Test migration interruption, retry, and invalid data](Task-18.md#task-18b) — `gpt-5.6-sol` / `high`
- [ ] [Task 19A — Add the guarded os-autoinst worker and console transport](Task-19.md#task-19a) — `gpt-6-astra` / `high`
- [ ] [Task 19B — Add stable screen matching and graphical smoke](Task-19.md#task-19b) — `gpt-5.6-terra` / `medium`
- [ ] [Task 20 — Automate clean installation, reboot, and startup readiness](Task-20.md) — `gpt-5.6-sol` / `high`
- [ ] [Task 21A — Automate Parent discovery, navigation, and validation](Task-21.md#task-21a) — `gpt-5.6-terra` / `medium`
- [ ] [Task 21B — Automate Parent saves, live policy, and revocation](Task-21.md#task-21b) — `gpt-5.6-terra` / `high`
- [ ] [Task 22A — Prove lock, retained-session unlock, and fresh-login enforcement](Task-22.md#task-22a) — `gpt-6-astra` / `high`
- [ ] [Task 22B — Automate countdown display, visibility, and estimate recovery](Task-22.md#task-22b) — `gpt-5.6-terra` / `medium`
- [ ] [Task 23A — Automate real authentication and atomic child approval](Task-23.md#task-23a) — `gpt-5.6-sol` / `high`
- [ ] [Task 23B — Automate shared form validation, choices, and overlay exit](Task-23.md#task-23b) — `gpt-5.6-terra` / `medium`
- [ ] [Task 24A — Prove restricted kiosk startup and authentication-agent recovery](Task-24.md#task-24a) — `gpt-5.6-sol` / `high`
- [ ] [Task 24B — Complete kiosk form, approval, persistence, and logout cases](Task-24.md#task-24b) — `gpt-5.6-terra` / `medium`
- [ ] [Task 25A — Automate graphical launch-route and matching matrices](Task-25.md#task-25a) — `gpt-5.6-terra` / `high`
- [ ] [Task 25B — Prove multi-session termination and grant isolation](Task-25.md#task-25b) — `gpt-6-astra` / `high`
- [ ] [Task 26A — Prove adversarial transaction races and failure recovery](Task-26.md#task-26a) — `gpt-6-astra` / `xhigh`
- [ ] [Task 26B — Complete restart and persistence scenarios](Task-26.md#task-26b) — `gpt-5.6-terra` / `medium`
- [ ] [Task 27A — Define and enforce the shared evidence and redaction contract](Task-27.md#task-27a) — `gpt-5.6-sol` / `high`
- [ ] [Task 27B — Wire the remaining runners to the evidence contract](Task-27.md#task-27b) — `gpt-5.6-luna` / `medium`
- [ ] [Task 27C — Finish bounded waits and flake classification](Task-27.md#task-27c) — `gpt-5.6-terra` / `high`
- [ ] [Task 28A — Install CI jobs and the serial release command](Task-28.md#task-28a) — `gpt-5.6-terra` / `medium`
- [ ] [Task 28B — Audit executable traceability and pass the release gate](Task-28.md#task-28b) — `gpt-5.6-sol` / `high`
- [ ] [Task 28C — Finish the operator runbook and evidence index](Task-28.md#task-28c) — `gpt-5.6-luna` / `low`

## Completion records

Append one entry only after its checklist item has been changed to `[x]`:

```text
### Task NN completed — YYYY-MM-DD

- Result: <concise description>
- Verification: `<command>`; `<command>`
- Commit: <hash or "not committed">
```

### Task 01 completed — 2026-09-03

- Result: Added 79 stable specification IDs, a complete planned traceability manifest, and stage/final validation.
- Verification: `python3 tools/verify_test_traceability.py --mode stage`; `python3 -m unittest tests/unit/test_verify_test_traceability.py -v`; `make check`; `git diff --check`
- Commit: not committed

### Task 02 completed — 2026-09-03

- Result: Added strict pytest configuration, Ubuntu-pinned test-tool documentation, a host-safe `make check-unit` entry point, and setup.sh installation of pytest without rewriting the unittest suite.
- Verification: `PYTHONPATH=/tmp/onpc-pytest/usr/lib/python3/dist-packages make PYTHON=/usr/bin/python3 check-unit`; `PYTHONPATH=/tmp/onpc-pytest/usr/lib/python3/dist-packages make PYTHON=/usr/bin/python3 check`; `git diff --check`
- Commit: not committed

### Task 03 completed — 2026-09-03

- Result: Added explicit pytest test-layer markers and classification, scoped branch-coverage reporting for product Python packages, maintained ShellCheck/GJS static-check entry points, boundary coverage guidance, and marker/coverage documentation.
- Verification: `make check-marker MARKER=unit`; `make check-marker MARKER=contract`; `make check-coverage`; `make check`; `git diff --check`
- Commit: not committed

### Task 04 completed — 2026-09-03

- Result: Added deterministic Hypothesis properties and a two-child broker transaction state machine; fixed fail-closed public error translation for pre-write account snapshots in approval and revocation paths.
- Verification: `make check-unit`; `python3 tools/verify_test_traceability.py --mode stage`; `make check`; `git diff --check`
- Commit: not committed

### Task 05 completed — 2026-09-03

- Result: Added injectable broker service construction and a real Gio component harness on python-dbusmock private session and test-system buses, covering every public method, asynchronous dispatch, cancellation, caller disappearance, public errors, redacted logging, and lifecycle cleanup.
- Verification: `make check-component` (repeated within one process and in three fresh processes); `python3 tools/verify_test_traceability.py --mode stage`; `make check`; `git diff --check`
- Commit: not committed

### Task 06 completed — 2026-09-03

- Result: Added hash-pinned Dogtail 2.x hermetic GTK automation with private D-Bus/AT-SPI, deterministic bare-Mutter previews, accessible control metadata, and parameterized request-surface smokes.
- Verification: `make check-component` (three consecutive clean runs); `make check`; `git diff --check`
- Commit: not committed

### Task 07 completed — 2026-09-03

- Result: Added scripted broker injection and executable Parent UI coverage for startup failures, account and loading state, status retries, screen-time controls, app policies, save ordering and rollback, revocation, and the absence of time-grant controls.
- Verification: `.venv/onpc-ui-tests/bin/python -m pytest tests/ui -m ui -k parent` (three consecutive clean runs); `make check-component`; `make check`; `git diff --check`
- Commit: not committed

### Task 08 completed — 2026-09-03

- Result: Added deterministic shared request-form component automation for kiosk and child-overlay modes, including real bare-Mutter Escape input, mode-specific identity and exit behavior, remembered choices and mute state, all request outcomes, and accessible locked controls.
- Verification: `tools/run-ui-tests --timeout 900s tests/ui/test_request_form_component.py -m ui -q -k kiosk` (three consecutive clean runs); `tools/run-ui-tests --timeout 900s tests/ui/test_request_form_component.py -m ui -q -k 'not kiosk'` (three consecutive clean runs); `tools/run-ui-tests --timeout 900s tests/ui/test_request_form_component.py -m ui -q` (three consecutive clean runs); `make check-component`; `make check`; `git diff --check`
- Commit: not committed

### Task 09 completed — 2026-09-03

- Result: Extracted platform-neutral child countdown, display, estimate, retry, request-overlay, and session-preparation decisions; added Node logic tests, GJS Gio/GLib adapter tests, LCOV artifacts, and component-runner integration.
- Verification: `make check-child-node`; `make check-child-gjs`; `make check-component`; `make check`; `python3 tools/verify_test_traceability.py --mode stage`; `git diff --check`
- Commit: not committed

### Task 10A completed — 2026-09-03

- Result: Refactored the child preview into a sourceable orchestration boundary with isolated environment setup, generation logs, bounded readiness, event-driven reloads, and process-group cleanup.
- Verification: `python3 -m pytest tests/unit/test_child_preview.py -m contract -q`; `make check`; `git diff --check`
- Commit: not committed

### Task 10B completed — 2026-09-03

- Result: Added the GNOME Shell 50 Mutter Devkit lifecycle smoke with a copied packaged extension, private XDG/settings/D-Bus/AT-SPI/PipeWire state, bounded semantic readiness, complete extension-attributable log checks, and identity-recorded deterministic teardown; also removed deprecated indicator construction and made extension shutdown idempotent.
- Verification: `python3 -m pytest tests/unit/test_child_preview_cleanup_safety.py -q`; `tools/run-ui-tests --timeout 120s tests/ui/test_child_shell_lifecycle.py -m ui -q` (three consecutive fresh processes); `make check-component`; `make check`; `git diff --check`
- Commit: not committed

### Task 10C completed — 2026-09-04

- Result: Added supported virtual-keyboard interaction with the real nested-Shell indicator, a preview-only initially-closed scenario, observable single-flight process/window/accessibility assertions while opening and running, shared child-overlay close/reopen coverage, redacted diagnostics, and deterministic teardown.
- Verification: `python3 -m pytest tests/unit/test_child_preview_cleanup_safety.py -q`; `tools/run-ui-tests --timeout 180 tests/ui/test_child_shell_lifecycle.py::test_child_indicator_opens_one_shared_overlay_and_can_reopen -q` (three consecutive fresh processes); `make check-component`; `make check`; `git diff --check`
- Commit: not committed

### Task 10D completed — 2026-09-04

- Result: Added controlled-copy nested-Shell reload evidence with observable generations, per-attempt and stable log/PNG artifacts captured through GNOME Shell's public Screenshot D-Bus service, lifecycle/error-category records, extension-attributable diagnostic scans, and truthful child component requirement mapping.
- Verification: `python3 -m pytest tests/unit/test_child_preview_cleanup_safety.py -q`; `tools/run-ui-tests --timeout 360s tests/ui/test_child_shell_lifecycle.py -m ui -q` (three consecutive fresh processes: 80.02s, 80.39s, 80.03s); `python3 tools/verify_test_traceability.py --mode stage`; `make check-component`; `make check`; `git diff --check`
- Commit: not committed

### Task 11 completed — 2026-09-04

- Result: Added source-built static native test targets, exact/space/version-pattern AppImage-style copies, deterministic child and system desktop entries, a self-contained minimal Flatpak repository and bundle, digest verification, and UID-recorded launch/cleanup helpers. The builder accepts only explicit empty output beneath `/tmp`; Flatpak smoke state is isolated below that temporary payload.
- Verification: `make check-test-fixtures`; `python3 -m pytest tests/unit/test_child_preview_cleanup_safety.py -q`; `make check`; `git diff --check`
- Commit: not committed

### Task 12A completed — 2026-09-04

- Result: Added a fixed-path, fail-closed `make prep-vm` workflow that prepares and verifies exactly two test parents and two test children with one shared password prompt, refuses product installation or residue, and writes a secret-free root-owned baseline record without installing the product.
- Verification: `python3 -m pytest tests/unit/test_prepare_vm.py tests/unit/test_prepare_vm_contract.py -q`; `bash -n tests/integration/prepare-vm`; `python3 -m py_compile tests/integration/prepare_vm.py tests/unit/test_prepare_vm.py tests/unit/test_prepare_vm_contract.py`; `make check`; `git diff --check`
- Commit: not committed
