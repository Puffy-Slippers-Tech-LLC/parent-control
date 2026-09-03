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
- Never execute tests in the protected golden VM. Produce a new QCOW2 overlay and
  a uniquely named domain for every installed-system or end-to-end run. Test VMs
  must not expose a writable host filesystem such as the current `/Data` virtiofs
  share.
- Test the exact Debian package artifact as the primary release path. Test the
  direct installer separately. Record the artifact digest in every VM result.
- Give every normative statement in `Specification.md` a stable requirement ID
  and maintain machine-checked traceability from each ID to executable tests and
  collected evidence.
- Keep every critical end-to-end assertion three-sided: verify the visible user
  result, the authoritative backend state, and the absence of effects on other
  users.
- Use current public interfaces only. Pin current test-tool versions. In
  particular, use Dogtail 2.x rather than Ubuntu's legacy Dogtail 1.x package,
  and use the stable public os-autoinst test API.
- The natural-grant-expiry app-filter gap documented in `System-Design.md` is a
  required implementation task in this plan. Do not hide it with a release-gate
  skip or expected failure.
- The sequence below is fixed. There are no optional tasks, alternate paths, or
  decision branches.

## Progress checklist

Execution rule: a fresh Codex session must read `AGENTS.md`, this entire file,
`Specification.md`, and `System-Design.md`; locate the first unchecked task below;
report that task's recommended model and reasoning effort; and stop before making
changes. After the user switches to that model and effort and asks Codex to
execute, Codex must execute exactly that one task, run its stated verification,
change its checkbox from `[ ]` to `[x]`, append its completion record at the end
of this file, and stop. Never execute a second task in the same session. Never
redo a checked task. Running already-created regression tests as verification for
the current task is required and does not count as redoing prior work. A task
that is incomplete or blocked remains unchecked and receives no completion
record.

- [x] Task 01 — Establish specification IDs and executable traceability
- [x] Task 02 — Adopt pytest without rewriting the existing unit suite
- [x] Task 03 — Establish test categories, static checks, and coverage reporting
- [x] Task 04 — Add broker property and state-machine testing
- [x] Task 05 — Add a real private-D-Bus broker component harness
- [x] Task 06 — Establish modern hermetic GTK automation
- [ ] Task 07 — Automate the Parent App as a local component
- [ ] Task 08 — Automate the shared kiosk and child request form locally
- [ ] Task 09 — Add executable unit tests for child-extension JavaScript
- [ ] Task 10 — Automate the nested GNOME Shell child preview
- [ ] Task 11 — Build deterministic native and Flatpak test applications
- [ ] Task 12 — Add safe immutable VM baselines and disposable overlay clones
- [ ] Task 13 — Add Debian-package autopkgtest infrastructure
- [ ] Task 14 — Test installed broker identity and authorization boundaries
- [ ] Task 15 — Test installed catalog, fapolicyd, and process termination
- [ ] Task 16 — Test installed Malcontent, PAM, grants, and session behavior
- [ ] Task 17 — Implement and test broker-owned natural grant-expiry reconciliation
- [ ] Task 18 — Test package activation and saved-data migration end to end
- [ ] Task 19 — Establish the os-autoinst end-to-end test distribution
- [ ] Task 20 — Automate clean installation, reboot, and startup readiness
- [ ] Task 21 — Automate Parent App management scenarios
- [ ] Task 22 — Automate child countdown, expiry, lock, and login scenarios
- [ ] Task 23 — Automate child-overlay request and approval scenarios
- [ ] Task 24 — Automate dedicated kiosk request scenarios
- [ ] Task 25 — Automate application policy and multi-user isolation scenarios
- [ ] Task 26 — Automate failure, concurrency, persistence, and recovery scenarios
- [ ] Task 27 — Complete artifact, redaction, timeout, and flake controls
- [ ] Task 28 — Install CI and release gates and close the traceability matrix

## Rules for every task

1. Execute tasks strictly in checklist order. Do not skip, combine, reorder, or
   begin a later task.
2. Inspect the current worktree before editing. Preserve user changes and avoid
   unrelated cleanup.
3. Use `docs/System-Design.md` for architecture and trust boundaries. Preserve
   the broker as the authority and preserve real-caller validation on system
   D-Bus.
4. Use only maintained public APIs. Do not introduce hidden production D-Bus
   methods, test-only authorization bypasses, private GNOME Shell APIs, QEMU
   monitor hacks, or host-window coordinate automation.
5. Add useful stage, outcome, and error-category logging for changed runtime
   behavior. Never log a password, authentication token, private key, raw user
   data, or other PII. Use labels such as `[Child user]`, `[Administrator]`, and
   `[Request surface]`.
6. Read troubleshooting evidence from
   `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log` and the relevant
   journals. Never modify or delete logs.
7. Classify every new packaged system-integration file according to
   `docs/Package-Update.md` and add or update activation tests in the same task.
8. Complete and ship a migration according to `docs/Data-Migration.md` before a
   changed reader or writer uses incompatible saved data.
9. Treat the kiosk form and child overlay as two modes of one shared GTK GUI.
   Every form change and every form test must cover both modes.
10. Keep host-safe and guest-mutating commands visibly separate. `make check`
    must remain safe for the development host. VM mutation always requires an
    explicit guarded VM or image argument.
11. Use event-driven waits with bounded deadlines. Fixed sleeps are permitted
    only for a documented product duration that is itself under test.
12. Do not make a flaky assertion pass by retrying it. A whole-run rerun may
    classify a flake, but a release remains failed after any failed attempt.
13. Mark the task complete only after all task deliverables exist, focused tests
    pass, `make check` passes, documentation reflects the new commands, and
    `git diff --check` passes.
14. The completion record must contain the task number, completion date, short
    result, verification commands, and relevant commit hash when a commit exists.

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
mode. Task 28 switches the release gate to `--mode final`.

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

## Task documents

Each task is stored in its own document. A fresh execution session reads this
master document and only the first unchecked task document listed below. Do not
read other task documents until their checklist item becomes the first unchecked
item.

- [x] [Task 01 — Establish specification IDs and executable traceability](Task-01.md)
- [x] [Task 02 — Adopt pytest without rewriting the existing unit suite](Task-02.md)
- [x] [Task 03 — Establish test categories, static checks, and coverage reporting](Task-03.md)
- [x] [Task 04 — Add broker property and state-machine testing](Task-04.md)
- [x] [Task 05 — Add a real private-D-Bus broker component harness](Task-05.md)
- [x] [Task 06 — Establish modern hermetic GTK automation](Task-06.md)
- [ ] [Task 07 — Automate the Parent App as a local component](Task-07.md)
- [ ] [Task 08 — Automate the shared kiosk and child request form locally](Task-08.md)
- [ ] [Task 09 — Add executable unit tests for child-extension JavaScript](Task-09.md)
- [ ] [Task 10 — Automate the nested GNOME Shell child preview](Task-10.md)
- [ ] [Task 11 — Build deterministic native and Flatpak test applications](Task-11.md)
- [ ] [Task 12 — Add safe immutable VM baselines and disposable overlay clones](Task-12.md)
- [ ] [Task 13 — Add Debian-package autopkgtest infrastructure](Task-13.md)
- [ ] [Task 14 — Test installed broker identity and authorization boundaries](Task-14.md)
- [ ] [Task 15 — Test installed catalog, fapolicyd, and process termination](Task-15.md)
- [ ] [Task 16 — Test installed Malcontent, PAM, grants, and session behavior](Task-16.md)
- [ ] [Task 17 — Implement and test broker-owned natural grant-expiry reconciliation](Task-17.md)
- [ ] [Task 18 — Test package activation and saved-data migration end to end](Task-18.md)
- [ ] [Task 19 — Establish the os-autoinst end-to-end test distribution](Task-19.md)
- [ ] [Task 20 — Automate clean installation, reboot, and startup readiness](Task-20.md)
- [ ] [Task 21 — Automate Parent App management scenarios](Task-21.md)
- [ ] [Task 22 — Automate child countdown, expiry, lock, and login scenarios](Task-22.md)
- [ ] [Task 23 — Automate child-overlay request and approval scenarios](Task-23.md)
- [ ] [Task 24 — Automate dedicated kiosk request scenarios](Task-24.md)
- [ ] [Task 25 — Automate application policy and multi-user isolation scenarios](Task-25.md)
- [ ] [Task 26 — Automate failure, concurrency, persistence, and recovery scenarios](Task-26.md)
- [ ] [Task 27 — Complete artifact, redaction, timeout, and flake controls](Task-27.md)
- [ ] [Task 28 — Install CI and release gates and close the traceability matrix](Task-28.md)

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
