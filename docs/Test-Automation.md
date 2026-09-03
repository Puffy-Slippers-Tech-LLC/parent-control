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

- [ ] Task 01 — Establish specification IDs and executable traceability
- [ ] Task 02 — Adopt pytest without rewriting the existing unit suite
- [ ] Task 03 — Establish test categories, static checks, and coverage reporting
- [ ] Task 04 — Add broker property and state-machine testing
- [ ] Task 05 — Add a real private-D-Bus broker component harness
- [ ] Task 06 — Establish modern hermetic GTK automation
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

## Task details

### Task 01 — Establish specification IDs and executable traceability

- Complexity: medium-high. The mechanics are simple, but preserving the exact
  meaning and acceptance scope of every normative statement needs care.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: make completeness measurable before adding new test layers.
- Work:
  1. Add a stable, unique ID to every normative bullet in `Specification.md`,
     including nested app-policy states and all component requirements. Preserve
     the normative wording.
  2. Create `tests/requirements.json` using a documented schema with requirement
     ID, specification section, responsible component, required test layer,
     executable test references, evidence type, and current coverage state.
  3. Populate all requirement records. Existing tests may be referenced only
     when they execute the stated behavior; source-text assertions may be listed
     as supporting contracts but never as acceptance evidence.
  4. Add `tools/verify_test_traceability.py` using the Python standard library.
     It must reject duplicate IDs, missing specification IDs, unknown test
     references, invalid layer names, and malformed records.
  5. Add focused unit tests for the validator and wire its stage-appropriate mode
     into `make check`. The stage-appropriate mode validates structure and known
     references while allowing explicitly recorded `planned` coverage until
     Task 28.
  6. Document the requirement-ID and mapping maintenance rules in this file and
     the integration test README.
- Verification:
  - Run the traceability validator directly.
  - Run its focused unit tests.
  - Run `make check`.
  - Run `git diff --check`.
- Completion criteria: every normative specification statement has exactly one
  stable ID, every ID has a valid manifest record, and no unsubstantiated
  acceptance claim is present.

### Task 02 — Adopt pytest without rewriting the existing unit suite

- Complexity: low-medium. Pytest directly collects the existing unittest suite.
- Recommended Codex model: `gpt-5.6-luna`
- Recommended reasoning effort: `medium`
- Objective: create one scalable Python runner while retaining all current test
  coverage and host safety.
- Work:
  1. Add a repository pytest configuration with strict marker and warning
     handling, deterministic test paths, and xUnit2 JUnit output support.
  2. Define and document reproducible test-tool dependencies for Ubuntu 26.04.
     Prefer Ubuntu packages for PyGObject-integrated tools and pin non-Ubuntu
     Python wheels with hashes in an isolated test environment.
  3. Make pytest collect all existing `tests/unit` unittest cases without a bulk
     syntax conversion.
  4. Preserve the existing syntax, XML, policy, and private-API source checks.
  5. Add a host-safe `make check-unit` target and make `make check` invoke it.
  6. Produce a JUnit report under an ignored artifacts directory only when the
     caller requests report output.
- Verification:
  - Prove that pytest collects at least the same 288 existing tests.
  - Run `make check-unit` and `make check`.
  - Run `git diff --check`.
- Completion criteria: the original suite passes under pytest, `make check`
  remains non-privileged and host-safe, and no existing test was silently lost.

### Task 03 — Establish test categories, static checks, and coverage reporting

- Complexity: low-medium. This is runner configuration and targeted cleanup.
- Recommended Codex model: `gpt-5.6-luna`
- Recommended reasoning effort: `medium`
- Objective: make test intent and blind spots visible without imposing a
  misleading repository-wide percentage target.
- Work:
  1. Register the markers `unit`, `contract`, `component`, `ui`, `system`, `e2e`,
     `slow`, and `guest_mutating` and apply them to current and new tests.
  2. Add coverage reporting for broker, parent, kiosk, common, and tools Python
     modules with branch coverage enabled.
  3. Record per-security-boundary coverage expectations for broker validation,
     transactions, preferences, migration, execution policy, and process
     ownership. Do not set a blanket 100-percent repository threshold.
  4. Add maintained ShellCheck and GNOME-compatible JavaScript lint entry points.
     Keep syntax checks in place.
  5. Reclassify source-text assertions as `contract`. Keep valuable architecture
     guards while ensuring traceability never counts them as runtime acceptance.
  6. Document commands for selection by marker and for producing local coverage
     artifacts.
- Verification:
  - Run each host-safe marker selection.
  - Generate HTML and XML coverage reports.
  - Run `make check` and `git diff --check`.
- Completion criteria: every current test has an understandable layer, coverage
  reports name the important unexecuted paths, and static tools use maintained
  configurations.

### Task 04 — Add broker property and state-machine testing

- Complexity: medium-high. The broker's rollback and multi-state invariants need
  model-based reasoning.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: systematically exercise combinations that example-based unit tests
  cannot cover economically.
- Work:
  1. Add Hypothesis tests for remaining-time arithmetic, duration validation,
     usage-interval merging, local-midnight calculations, preference
     normalization, pattern validation, and migration inputs.
  2. Add a rule-based state machine for two children, two administrators, the
     kiosk caller, and an unrelated user.
  3. Model enable, disable, daily-limit change, policy change, request approval,
     denial, cancellation, revocation, account-role change, requester
     disconnect, and adapter failure at every transaction boundary.
  4. Assert after every action that hard blocks remain hard, child state is
     isolated, successful grants are accumulated correctly, unsuccessful
     operations do not relax state, and rollback matches the defined recovery
     state.
  5. Use the broker's injected clocks and adapter protocols. Do not add a
     production test mode.
  6. Update requirement mappings for the properties now exercised.
- Verification:
  - Run the new tests with a committed deterministic Hypothesis profile.
  - Re-run saved failing examples.
  - Run `make check` and `git diff --check`.
- Completion criteria: important broker invariants are checked across generated
  sequences and all failures shrink to reproducible examples.

### Task 05 — Add a real private-D-Bus broker component harness

- Complexity: high. It crosses GLib event loops, asynchronous replies, caller
  disconnects, and service dependencies.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: execute the broker's real D-Bus dispatch and public error contract
  without touching the host system bus.
- Work:
  1. Use current `python-dbusmock` support for a private session bus and a private
     bus addressed as the test system bus.
  2. Refactor service construction through ordinary dependency injection so
     tests can supply broker adapters, configuration, clocks, and a temporary
     log writer. Do not add a test-only public API or authorization bypass.
  3. Call every public D-Bus method through a real `Gio.DBusConnection` and
     assert signatures, serialization, error names, public error text, and
     completion on the GLib main loop.
  4. Exercise concurrent request dispatch, caller disappearance, cancellation,
     worker exceptions, malformed JSON, and unknown methods.
  5. Assert that D-Bus logs identify stages and error categories without UIDs,
     usernames, labels, request secrets, or paths supplied by callers.
  6. Update the D-Bus requirement mappings.
- Verification:
  - Run the private-D-Bus suite repeatedly in one process and in fresh processes.
  - Run `make check` and `git diff --check`.
- Completion criteria: the real service dispatch layer is executable on a
  private bus and no test contacts or changes the host system bus.

### Task 06 — Establish modern hermetic GTK automation

- Complexity: medium-high. Wayland input, accessibility selectors, and GTK4
  lifecycle handling must be deterministic.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: create a maintained semantic UI harness for GTK component tests.
- Work:
  1. Pin current Dogtail 2.x with hashes in the isolated test-tool environment.
     Do not use Ubuntu's legacy Dogtail 1.x package.
  2. Use Dogtail's hermetic session support with a private D-Bus, private AT-SPI
     bus, bare Mutter compositor, virtual monitor, and deterministic GTK theme,
     scale, locale, and animation settings.
  3. Use the maintained Ubuntu `gnome-ponytail-daemon` package for real Wayland
     session runs that require injected pointer or keyboard input.
  4. Add stable accessible names and descriptions to all important Parent and
     request-form controls. These identifiers must be meaningful accessibility
     metadata, not hidden test IDs.
  5. Add reusable pytest fixtures for launching an app, waiting for an
     accessibility node, taking a screenshot, collecting application logs, and
     shutting the hermetic session down cleanly.
  6. Add a minimal smoke test for Parent preview, kiosk preview, and child-overlay
     preview. Parameterize shared-form checks across both request modes.
  7. Add `make check-component` without changing `make check` into a graphical
     or privileged command.
- Verification:
  - Run the smoke tests three consecutive times.
  - Confirm no process, bus, or temporary directory remains after each run.
  - Run `make check` and `git diff --check`.
- Completion criteria: semantic GTK automation passes on Ubuntu 26.04 Wayland
  without coordinate scripts or access to the developer's logged-in session.

### Task 07 — Automate the Parent App as a local component

- Complexity: medium. Existing controller seams and preview data reduce the
  system dependencies.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Objective: replace acceptance reliance on source-text assertions with
  executable Parent UI behavior.
- Work:
  1. Supply scripted fake-broker responses through constructor injection and
     launch the production Parent window in the hermetic GTK harness.
  2. Test denied startup, broker-unavailable startup, no-child messaging,
     account switching, loading masks, status retries, unavailable status, daily
     presets, custom limits, enable and disable, app search and filters, precise
     and pattern rule editing, auto-save order, save rollback, and revocation
     confirmation.
  3. Prove that controls which conflict with a pending load or save are disabled.
  4. Prove that no Parent surface can grant additional time.
  5. Assert visible text and accessibility state rather than internal widget
     field names.
  6. Update Parent requirement mappings and keep source-contract tests only as
     secondary guards.
- Verification:
  - Run the Parent UI tests three consecutive times.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: every Parent component requirement has a local behavioral
  test or an explicit later E2E mapping.

### Task 08 — Automate the shared kiosk and child request form locally

- Complexity: medium-high. The same widgets have different caller identity,
  mute storage, and exit semantics.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: prove shared behavior once and mode-specific behavior twice.
- Work:
  1. Parameterize one semantic request-form suite over kiosk and child-overlay
     modes.
  2. Test loading, no-child, no-approver, control-disabled, predefined duration,
     rest-of-day, custom range and precision, approver selection, soft-app
     selection, duplicate prevention, denial, cancellation, service failure,
     approval, and redacted error copy.
  3. Test fixed child identity and overlay close behavior in child mode.
  4. Test child selection, return-to-login action, and logout behavior in kiosk
     mode.
  5. Test shared remembered choices and separate kiosk/child mute values.
  6. Test Escape while idle and while an authentication request is active.
  7. Update request-station and child-overlay requirement mappings.
- Verification:
  - Run both parameter values explicitly and together three consecutive times.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: every shared behavior runs against both modes and every
  differing behavior has a mode-specific assertion.

### Task 09 — Add executable unit tests for child-extension JavaScript

- Complexity: medium. Testable logic must be separated from Shell-bound actors
  without changing runtime behavior.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Objective: move beyond JavaScript syntax and source-string checks.
- Work:
  1. Extract pure formatting, countdown cadence, estimate preservation,
     validation, retry classification, and display-state calculations into
     side-effect-free ECMAScript modules.
  2. Test platform-neutral modules with Node's maintained built-in test runner.
  3. Test GJS-specific Gio and GLib adapters with the maintained public
     Jasmine-for-GJS approach or a small GJS runner using public APIs. Do not use
     deprecated `jsUnit`.
  4. Cover final-minute seconds, zero, values above one day, transient timer
     failure, busy retries, refresh-after-overlay, and duplicate-overlay guards.
  5. Enable GJS coverage output for the extracted modules and add it to local
     component artifacts.
  6. Update child component requirement mappings.
- Verification:
  - Run Node and GJS tests separately and through `make check-component`.
  - Run `make check` and `git diff --check`.
- Completion criteria: child logic executes in tests, Shell-only code is thin,
  and no test imports private GNOME Shell resources.

### Task 10 — Automate the nested GNOME Shell child preview

- Complexity: high. A Shell extension runs inside the compositor and must be
  tested through supported Shell lifecycle behavior.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: turn the existing Mutter-devkit preview into a repeatable component
  smoke and interaction suite.
- Work:
  1. Refactor `child/preview` into reusable start, readiness, reload, and cleanup
     operations while retaining the interactive developer command.
  2. Start GNOME Shell through the public Mutter devkit in private XDG, settings,
     and D-Bus directories.
  3. Verify that the extension loads, the indicator appears, accessible naming is
     present, the request action launches the shared child overlay, only one
     overlay appears, and clean shutdown produces no Shell warning or critical
     attributable to the extension.
  4. Verify extension reload after source changes through a controlled temporary
     copy, not the developer's live source tree.
  5. Capture the nested Shell log and screenshot as component artifacts.
  6. Update child extension requirement mappings that this environment truthfully
     covers.
- Verification:
  - Run the automated preview three consecutive times.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: the extension is executed inside GNOME Shell 50 under an
  isolated supported preview environment with deterministic cleanup.

### Task 11 — Build deterministic native and Flatpak test applications

- Complexity: medium-high. Fixtures must represent real execution identities
  without becoming product dependencies.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: provide stable targets for catalog, enforcement, and termination
  tests.
- Work:
  1. Add a tiny source-built native GUI or long-running process fixture that
     reports readiness and exits cleanly. Build it only in the test environment.
  2. Produce exact-path, path-with-spaces, and versioned AppImage-style copies,
     plus a nonmatching executable in the same directory.
  3. Add child-only and system `.desktop` fixture entries with deterministic IDs,
     names, icons, and executable targets.
  4. Add a minimal Flatpak fixture, local repository, and bundle built without a
     network dependency during test execution.
  5. Add helpers that launch the fixtures as a specified UID and report process
     identity without logging usernames or command-line secrets.
  6. Verify fixture digests and keep all fixture installation scoped to disposable
     test images.
- Verification:
  - Build fixtures from a clean checkout.
  - Launch and terminate each fixture in an unprivileged temporary environment.
  - Run `make check`, relevant component tests, and `git diff --check`.
- Completion criteria: all supported native, pattern, and Flatpak enforcement
  cases have reproducible self-contained targets.

### Task 12 — Add safe immutable VM baselines and disposable overlay clones

- Complexity: very high. This controls destructive boundaries, libvirt storage,
  identity, credentials, and reliable cleanup.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: make every guest mutation disposable while preserving the protected
  Ubuntu baseline and the development host.
- Work:
  1. Extend the guarded integration controller with explicit commands to build a
     powered-off Ubuntu 26.04 Desktop baseline and to create a unique QCOW2
     overlay clone from an explicitly supplied baseline path.
  2. Keep the current official-image digest verification, deterministic account
     provisioning, exact package matrix, random per-run credentials, marker,
     token-bound domain description, SSH host-key isolation, redaction, and exact
     storage deletion checks.
  3. Create two clean baseline products: Ubuntu Desktop before product install
     and product-installed/rebooted baseline generated from a named Debian
     artifact. Record provenance and digests for both.
  4. Never mutate or revert the `ubuntu26.04` golden domain. Never attach its
     active writable layer to a test domain.
  5. Define generated test domains without filesystem passthrough, shared host
     directories, USB redirection, or access to `/Data`. Transfer artifacts over
     the guarded SSH channel or a read-only generated disk.
  6. Make teardown recoverable and exact: stop and undefine only the token-matched
     disposable domain, then remove only its validated overlay, seed, credentials,
     and state directory.
  7. Add signal handling and a stale-run audit command. Never perform wildcard
     cleanup.
  8. Add unit tests for every refusal and target-validation path and update the
     integration README.
- Verification:
  - Run host-safe harness unit tests.
  - Create, boot, shut down, and destroy one non-product disposable clone.
  - Prove the baseline digest did not change and no filesystem share exists in
    generated domain XML.
  - Run `make check` and `git diff --check`.
- Completion criteria: all later VM tests consume isolated overlays and cannot
  write the protected VM or the host `/Data` tree.

### Task 13 — Add Debian-package autopkgtest infrastructure

- Complexity: high. Package installation, reboot capability, and testbed cleanup
  must align with Debian and Ubuntu conventions.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: test the installed binary package and system integration separately
  from graphical user journeys.
- Work:
  1. Add a reproducible package-build command that produces a named `.deb` and
     SHA-256 record without installing it on the host.
  2. Add `debian/tests/control` and test executables using the required
     `isolation-machine`, root, and reboot capabilities.
  3. Configure `autopkgtest-virt-qemu` to consume only the Task 12 disposable
     baseline and overlay mechanism.
  4. Install the exact built package, reboot through autopkgtest, and verify
     package status, installed file ownership and modes, service readiness,
     D-Bus activation, PAM registration, Polkit files, session descriptors,
     generated execution rules, and reboot marker behavior.
  5. Add a separate direct-installer system test using a fresh overlay. Never let
     direct-installer success substitute for package success.
  6. Export xUnit/TAP results and guest artifacts through the existing redacted
     collector.
  7. Add the guarded `make check-system VM_IMAGE=...` entry point.
- Verification:
  - Run package build twice and compare package contents and recorded inputs.
  - Run the clean package and direct-installer tests on fresh overlays.
  - Run `make check` and `git diff --check`.
- Completion criteria: installed-system tests exercise the real package lifecycle
  and leave the baseline and host unchanged.

### Task 14 — Test installed broker identity and authorization boundaries

- Complexity: very high. These are security boundaries that cannot be proven by
  same-UID mocks.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove real caller identity and role enforcement on the installed
  system bus.
- Work:
  1. Expand deterministic accounts to two eligible children, two eligible
     administrators, one locked administrator, the kiosk user, an unrelated
     standard user, and noninteractive/system fixtures.
  2. Invoke every broker method from real processes running under each relevant
     UID and record the allowed or denied D-Bus result.
  3. Verify account discovery after installation, sorting, exclusions, icon
     handling, locked-approver exclusion, and child-owned target derivation.
  4. Verify that front ends cannot read private preference records and cannot
     claim another component in `LogEvent`.
  5. Verify stale-account, changed-role, caller-disconnect, and selected-approver
     revalidation with actual system-bus names.
  6. Exercise interactive Polkit selection later through E2E; this task proves
     all non-graphical policy and broker boundaries.
  7. Update broker and account requirement mappings.
- Verification:
  - Run the authorization matrix in a fresh installed overlay.
  - Inspect redacted broker logs and D-Bus results.
  - Run `make check-system`, `make check`, and `git diff --check`.
- Completion criteria: every method/role cell in `System-Design.md` has an
  installed-system assertion and cross-account attempts fail closed.

### Task 15 — Test installed catalog, fapolicyd, and process termination

- Complexity: very high. The test must prove kernel execution behavior and UID-
  confined termination, not merely generated rule text.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: execute application-policy enforcement through all supported paths.
- Work:
  1. Install the Task 11 fixtures for each relevant user and verify the catalog
     sees system and child-only launchers for the selected child, not the
     administrator's substitutions.
  2. Apply allowed, hard, and soft policies while screen-time control is enabled
     and disabled.
  3. Execute native targets from a launcher, file-manager activation, and command;
     execute the Flatpak fixture by its full identity.
  4. Test exact paths, spaces, matching future versioned filenames, unrelated
     same-directory files, target refresh after update, and preservation after a
     launcher disappears.
  5. Run the same executable as the selected child and unrelated users and prove
     UID-scoped enforcement.
  6. Start blocked fixtures in every live session for one child, trigger approval
     and revocation termination paths, and prove pidfd/Flatpak confinement and
     unrelated-process survival.
  7. Force fapolicyd reload failure in the disposable guest and prove transactional
     policy restoration and clear PII-safe logs.
  8. Update application-policy requirement mappings.
- Verification:
  - Run the full enforcement matrix from a fresh installed overlay.
  - Capture source and compiled fapolicyd rules and process evidence.
  - Run `make check-system`, `make check`, and `git diff --check`.
- Completion criteria: supported application routes are tested against real
  fapolicyd and Flatpak behavior with positive, negative, and isolation evidence.

### Task 16 — Test installed Malcontent, PAM, grants, and session behavior

- Complexity: very high. Time authority is distributed across Malcontent,
  AccountsService, PAM, systemd, and the broker.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove non-graphical time and login enforcement before UI scenarios.
- Work:
  1. Verify actual Malcontent usage recording, overlapping-interval handling,
     daily allowance calculation, zero-minute grant-only mode, and authoritative
     ActiveExtension values.
  2. Grant the minimum supported 0.1 minute and verify fixed-duration accumulation
     against both daily remaining time and an existing later grant.
  3. Verify rest-of-day arithmetic in dedicated disposable boots configured for
     ordinary midnight and both daylight-saving transition directions. Keep the
     entire VM clock coherent and preload all artifacts before time-shifted boots.
  4. Use `pamtester` for positive and negative account-management results and
     for the product's `gdm-password` authentication check. Verify
     administrator, kiosk, and unrelated-account exemptions on both applicable
     paths.
  5. Create real child sessions and verify that runtime caps are cleared only for
     managed children, broker restart clears stale caps, and expiry does not
     terminate the session.
  6. Verify a zero-time child fails the fresh-login account check and retained-
     session unlock authentication check, then verify a grant permits both at
     the backend and PAM levels. Graphical proof remains mapped to Task 22.
  7. Update time, PAM, and session requirement mappings.
- Verification:
  - Run all clock scenarios from fresh overlays.
  - Capture Malcontent replies, AccountsService properties, PAM results, logind
    state, boot IDs, timezone, and clocks.
  - Run `make check-system`, `make check`, and `git diff --check`.
- Completion criteria: real system authorities agree with the broker time model
  and the tests do not change the development-host clock.

### Task 17 — Implement and test broker-owned natural grant-expiry reconciliation

- Complexity: very high. This is a privileged transactional scheduler with
  startup, timer, race, and rollback behavior.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: close the documented implementation gap before release E2E tests
  rely on natural expiry.
- Work:
  1. Implement the broker-owned design already specified in
     `System-Design.md`: read ActiveExtension at startup, schedule the verified
     expiry, re-read authoritative state at the deadline, restore the canonical
     hard-and-soft filter only when no grant remains, and activate fapolicyd
     transactionally.
  2. Reschedule safely after approval, extension changes, revocation, parent-
     control changes, clock changes, broker restart, and child removal.
  3. Serialize expiry with approval and revocation so stale timers cannot undo a
     newer grant or policy.
  4. Add PII-safe logs for schedule, cancellation, wake, stale deadline, filter
     restore, accepted outcome, backend failure, and rollback failure.
  5. Add deterministic fake-clock unit tests, private-D-Bus component tests, and
     installed-system tests with real short grants.
  6. Prove hard blocks never relax, soft blocks restore on natural expiry, and
     unrelated children remain unchanged.
  7. Update `System-Design.md` to remove the implementation-gap statement and
     describe the completed lifecycle.
  8. Verify the existing package-activation classification for changed broker
     files and update activation tests in the same change.
  9. Update all natural-expiry requirement mappings. Do not mark the behavior
     skipped or expected-failing.
- Verification:
  - Run focused scheduler race and rollback tests repeatedly.
  - Run the installed short-grant expiry scenario.
  - Run `make check-component`, `make check-system`, `make check`, and
    `git diff --check`.
- Completion criteria: natural expiry restores canonical application enforcement
  after startup and at runtime, with transactional failure behavior and no stale-
  timer race.

### Task 18 — Test package activation and saved-data migration end to end

- Complexity: very high. Multiple real package versions and activation boundaries
  must be produced and verified.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove the package lifecycle described in `Package-Update.md` and
  `Data-Migration.md` on installed machines.
- Work:
  1. Build versioned package fixtures that differ in exactly one reviewed
     activation class: `none`, `process-restart`, `session-renewal`, and `reboot`.
  2. Install and upgrade them in order, proving broker PID behavior, session
     payload behavior, reboot-required markers, and next-boot activation.
  3. Create realistic records for every released saved-data version and perform
     single-step and multi-version upgrades with the package scripts.
  4. Interrupt migration between records, verify the marker keeps the broker
     unavailable, retry package configuration, and prove already migrated records
     remain correct.
  5. Verify invalid, duplicate-key, unsafe-mode, future-version, and rollback-
     unsupported data fail closed without replacement by defaults.
  6. Test a package or broker restart with every enabled child and prove current
     extension payload publication and saved-policy enforcement.
  7. Update package, migration, persistence, and startup requirement mappings.
- Verification:
  - Run every upgrade fixture from its own fresh overlay.
  - Record old/new package digests, boot IDs, broker PIDs, session IDs, migration
    records, and reboot markers.
  - Run `make check-system`, `make check`, and `git diff --check`.
- Completion criteria: all activation classes and released migration paths are
  verified through real package maintainer scripts.

### Task 19 — Establish the os-autoinst end-to-end test distribution

- Complexity: high. The framework owns QEMU, VNC, serial consoles, screen
  matching, secrets, and result artifacts.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: create the outside-the-VM driver required for GDM and lock-screen
  acceptance.
- Work:
  1. Add a repository-local os-autoinst test distribution under `tests/e2e` with
     `main.pm`, a small distribution class, public console definitions, scenario
     modules, needles, configuration templates, and a guarded launcher.
  2. Use Ubuntu 26.04's maintained `os-autoinst` package and the QEMU backend.
     Pin and record the worker tool versions. Do not attach to the protected
     libvirt domain and do not use the svirt root-password workflow.
  3. Use stable Perl test modules for os-autoinst orchestration. Keep complex
     backend assertions in versioned guest scripts and pytest tests.
  4. Configure a VNC graphical console plus virtio serial terminal. Use the
     graphical console only for real user actions and visible assertions; use the
     serial console for setup, state assertions, and artifact collection.
  5. Store passwords in os-autoinst secret variables and enter them with the
     secret-safe password API. Never put them in screenshots, command output, or
     vars artifacts.
  6. Use small stable screen-match regions, accessible text, explicit click
     points, and excluded dynamic areas. Never match a whole animated screen.
  7. Add one smoke scenario that boots a disposable Task 12 overlay, recognizes
     GDM, switches to serial, executes a harmless command, switches back, records
     a screenshot, and shuts down.
  8. Add the guarded `make check-e2e VM_IMAGE=... SCENARIO=...` command.
- Verification:
  - Run the smoke scenario three consecutive times from fresh overlays.
  - Review screenshots, video, serial output, secrets redaction, and overlay
    cleanup.
  - Run `make check` and `git diff --check`.
- Completion criteria: os-autoinst reliably controls boot, graphical input, and
  serial assertions without touching the protected domain or host data.

### Task 20 — Automate clean installation, reboot, and startup readiness

- Complexity: high. This is the first complete release-path graphical job.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: prove a clean supported Ubuntu machine reaches a safe login screen
  after installing the exact release artifact.
- Work:
  1. Start from the before-product baseline and upload the exact `.deb`, fixture
     bundle, and their digests through the controlled asset channel.
  2. Verify the product is absent, install the package through its real package
     path, record output, and verify the product-created reboot marker.
  3. Reboot through os-autoinst power and console APIs.
  4. Assert visually that GDM becomes usable only after fapolicyd readiness and
     the broker's startup reconciliation completes.
  5. Assert through serial that installed files, ownership, services, D-Bus,
     Polkit, PAM, session descriptors, configuration, extension payload, logs,
     and execution policy match the package.
  6. Prove a broker startup reconciliation failure prevents broker readiness and
     a fapolicyd readiness failure prevents managed graphical login startup.
  7. Collect all startup evidence and update installation/startup requirement
     mappings.
- Verification:
  - Run the clean-install scenario twice from separate fresh overlays.
  - Run package-focused system tests, `make check`, and `git diff --check`.
- Completion criteria: a digest-identified release package passes a real clean
  installation and reboot with visible and backend readiness evidence.

### Task 21 — Automate Parent App management scenarios

- Complexity: medium-high. The UI is semantic, but it drives several privileged
  transactions.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: execute the Parent component requirements as real user journeys.
- Work:
  1. Log in as an eligible administrator, launch Parent from the app grid, and
     verify the correct children and no ineligible accounts are listed.
  2. Create a new child after installation and verify dynamic discovery.
  3. Select each child and verify independent preferences, status, catalog, and
     loading behavior.
  4. Enable and disable screen time, exercise zero through 1440-minute boundaries,
     change an enabled allowance, and verify extension and live policy results.
  5. Search and filter the selected child's applications, set all three rules,
     select precise and version-tolerant matching, and verify immediate ordered
     auto-save.
  6. Exercise a failed save and revocation confirmation and verify rollback copy
     and restored controls.
  7. Attempt launch as a standard user and attempt broker management methods
     directly as that user; verify both visible and D-Bus denial.
  8. Update Parent and account requirement mappings.
- Verification:
  - Run the Parent scenario from a fresh installed overlay.
  - Verify UI screenshots against broker, AccountsService, fapolicyd, and private
    record evidence collected through root serial assertions.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: Parent management works for an administrator and remains
  inaccessible to standard users through both launcher and direct API paths.

### Task 22 — Automate child countdown, expiry, lock, and login scenarios

- Complexity: very high. This crosses GNOME Shell, Malcontent, logind, lock
  screen, PAM, retained sessions, and foreground-user isolation.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove the complete child time-enforcement experience.
- Work:
  1. Configure the child through Parent, log out, log in as that child, and verify
     extension installation, panel visibility, and minute countdown.
  2. Use the minimum real grant duration to verify the final-minute seconds
     display without a production clock hook.
  3. Wait for real expiry and verify the GNOME lock screen appears, the child
     session remains live, and another foreground user's session remains active.
  4. Attempt to unlock without time and verify the `gdm-password`
     authentication path denies it. Separately use public `loginctl` test
     orchestration to expose the retained desktop without new time and verify
     the extension immediately locks it again.
  5. End the retained session, attempt a fresh GDM login, and verify PAM denial.
  6. Grant time, then prove both retained-session unlock and fresh login succeed
     during a grant.
  7. Verify the panel control appears only in the unlocked child desktop and never
     on GDM or the lock screen; verify no custom lock-screen control exists.
  8. Verify a temporary Malcontent read failure preserves the last display and a
     later verified refresh recovers.
  9. Update child time, lock, login, and isolation requirement mappings.
- Verification:
  - Run the scenario twice from fresh installed overlays.
  - Correlate screenshots with logind sessions, PAM results, Malcontent usage,
    ActiveExtension, and PII-safe component logs.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: the child is locked rather than logged out, retained-
  session unlock and fresh login are denied at zero, grants restore both paths,
  and no other user is disturbed.

### Task 23 — Automate child-overlay request and approval scenarios

- Complexity: very high. The scenario includes a real system authentication
  prompt and atomic policy/time changes.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove a signed-in child can request access without gaining reusable
  authority.
- Work:
  1. Open the request overlay from the child panel and verify the child identity
     is fixed and only eligible approving parents appear.
  2. Exercise predefined, rest-of-day, minimum, maximum, fractional, and invalid
     custom durations; prove invalid input never invokes Polkit.
  3. Select each eligible parent and verify the system prompt is restricted to
     exactly that parent and displays child, duration, and soft-app choice.
  4. Exercise authentication cancellation and a rejected password, then retry
     successfully without losing the form choices or consuming the rate interval.
  5. Approve without soft apps and prove blocked child apps close before time is
     active while unrelated apps remain.
  6. Approve with soft apps and prove open apps remain, hard launches remain
     blocked, soft launches work, and natural expiry restores soft blocks.
  7. Attempt rapid duplicate submission and prove exactly one grant transaction.
  8. Verify Escape, explicit cancel, success confirmation, automatic close,
     remembered shared choices, child-only mute value, and post-close countdown
     refresh.
  9. Prove the child has no reusable Polkit authorization or management access.
  10. Update child-request and approval requirement mappings.
- Verification:
  - Run denial/cancel and approval cases from separate fresh overlays.
  - Correlate UI results, correlation IDs, process evidence, AppFilter,
    ActiveExtension, and logs.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: child-overlay requests satisfy identity, authentication,
  transaction, exit, persistence, and least-authority requirements.

### Task 24 — Automate dedicated kiosk request scenarios

- Complexity: high. The dedicated GNOME session has special startup, app, agent,
  and logout behavior.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: prove the GDM-visible kiosk remains a request-only session.
- Work:
  1. Select the dedicated session at GDM and verify the kiosk starts full-screen
     with its Polkit agent and no general desktop.
  2. Verify eligible children and approvers, child switching, loading gates,
     disabled-control explanation, remembered shared choices, and kiosk-only mute
     persistence.
  3. Exercise invalid input, authentication cancel, rejected password, successful
     approval with both soft-app choices, and rapid duplicate submission.
  4. Verify explicit cancel and Escape return to GDM and approval returns to GDM
     after the brief confirmation.
  5. Stop the authentication agent during a request, verify a safe denial, restart
     the maintained user service, and complete a later request successfully.
  6. Attempt to launch Parent, a terminal, settings, user management, and arbitrary
     desktop applications; prove the session remains request-only.
  7. Update kiosk requirement mappings.
- Verification:
  - Run the kiosk scenario twice from fresh installed overlays.
  - Correlate screen evidence with kiosk systemd user units, sessions, broker
    calls, grants, and logs.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: kiosk approval works and every exit, failure, and success
  path returns to a restricted state or GDM.

### Task 25 — Automate application policy and multi-user isolation scenarios

- Complexity: very high. Multiple graphical sessions and execution routes must
  remain independently observable.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove end-to-end enforcement rather than merely backend rule state.
- Work:
  1. Create simultaneous sessions for two children, an administrator, and an
     unrelated user using the deterministic Task 11 applications.
  2. Apply distinct policies to both children and launch targets from the app
     grid, desktop launcher, file manager, command, and Flatpak identity.
  3. Verify allowed, hard, and soft states with screen time both enabled and
     disabled.
  4. Verify precise and version-tolerant AppImage matching, same-directory
     nonmatches, supported renamed/copied limitations, target update between
     display and save, and missing-launcher retention.
  5. Approve and revoke grants while matching processes are open across multiple
     sessions for the selected child.
  6. Prove every required selected-child process closes, every other user's
     process remains, the strict filter remains on partial termination failure,
     and time is not granted or revoked partially.
  7. Verify hard blocks never relax, soft blocks relax only for an explicit
     soft-app grant, and soft blocks restore after expiry, revocation, and screen-
     time reapplication.
  8. Update application, revocation, and multi-user requirement mappings.
- Verification:
  - Run the scenario from a fresh installed overlay.
  - Capture per-session screenshots, kernel-reported process UIDs, Flatpak
    instance IDs, filters, fapolicyd rules, grants, and logs.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: every supported application route and isolation promise
  has user-visible and authoritative evidence.

### Task 26 — Automate failure, concurrency, persistence, and recovery scenarios

- Complexity: very high. Failures must occur at controlled real boundaries
  without adding production backdoors.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove fail-closed and rollback guarantees across restarts and user
  interactions.
- Work:
  1. Exercise invalid and unauthorized calls, Polkit denial and cancellation,
     requester disconnect, account and preference changes during authentication,
     usage-query failure, broker restart, authentication-agent failure,
     fapolicyd reload failure, and process-termination failure.
  2. Use disposable-guest service and process controls at public OS boundaries.
     Do not add a hidden failure-injection method to production.
  3. Verify each reversible failure restores the complete prior state and reports
     rollback failure distinctly when read-back cannot be verified.
  4. Verify irreversible partial process termination keeps strict blocks and old
     time while leaving other users untouched.
  5. Submit concurrent and rapid repeat requests and revocations and prove single-
     flight serialization, exactly-once grant changes, and correct rate-interval
     consumption.
  6. Restart Parent, request surfaces, broker, affected user sessions, package
     services, and the whole VM; verify preferences, remembered choices, grants,
     extension publication, and enforcement at each documented boundary.
  7. Verify all displayed failures are actionable and reveal no internal path,
     service name, account PII, or backend detail.
  8. Update failure, concurrency, persistence, and recovery requirement mappings.
- Verification:
  - Run each destructive failure from its own fresh overlay.
  - Compare before/after authoritative state snapshots and review redacted logs.
  - Run `make check-e2e` for these scenarios, `make check`, and
    `git diff --check`.
- Completion criteria: every specified failure class has a deterministic
  fail-closed scenario and all persistence boundaries are exercised.

### Task 27 — Complete artifact, redaction, timeout, and flake controls

- Complexity: medium-high. Evidence from three runners must use one secure,
  diagnosable format.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: make failures actionable without leaking credentials or accepting
  flaky passes.
- Work:
  1. Define one run manifest for unit, component, system, and E2E results with run
     ID, test ID, requirement IDs, source revision, package digest, baseline
     digest, package matrix, boot ID, timezone, tool versions, start/end times,
     and result.
  2. Collect JUnit/TAP, coverage, screenshots, os-autoinst video, serial logs,
     service status, relevant journals, D-Bus replies, PAM results, session state,
     source and compiled fapolicyd rules, process evidence, and product logs.
  3. Extend redaction tests for openQA variables, password-like fields, SSH keys,
     bearer values, Polkit text, screenshots, archive names, and manifest fields.
  4. Never alter source logs. Redact only copied artifacts and retain checksums of
     the redacted archive.
  5. Standardize bounded waits and diagnostic messages for boot, SSH, D-Bus,
     service readiness, screen needles, app start/exit, lock, and logout.
  6. Add a whole-scenario rerun command that records both attempts and preserves
     the original failure. Never convert a failed-then-passed release result to a
     pass.
  7. Run selected stable component and E2E scenarios repeatedly to identify and
     fix synchronization races at their root causes.
- Verification:
  - Generate passing and intentionally failing artifacts from every runner.
  - Run automated secret scans and safe-archive extraction tests.
  - Run stable smoke scenarios ten consecutive times.
  - Run `make check`, relevant component/system/E2E tests, and
    `git diff --check`.
- Completion criteria: every failure produces complete PII-safe evidence and no
  assertion depends on an unexplained delay or retry-to-pass behavior.

### Task 28 — Install CI and release gates and close the traceability matrix

- Complexity: medium-high. This assembles completed layers into enforceable,
  resource-aware gates.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: make the complete specification the release criterion and keep
  feedback proportional to test cost.
- Work:
  1. Define pre-commit/local, pull-request, nightly, updates-canary, and release
     jobs using the stable suite interfaces from this plan.
  2. Run host-safe unit and contract tests on every change. Run hermetic component
     tests and package build on every pull request. Run installed-system tests on
     the protected VM worker for every pull request. Run all graphical scenarios
     nightly and for releases.
  3. Keep one pinned supported Ubuntu/package-matrix lane as the release gate and
     one current-security-updates lane as a canary. Never silently rewrite the
     supported matrix from canary results.
  4. Serialize jobs on a single VM worker. Preserve the design for later parallel
     workers through independent immutable overlays rather than shared mutable
     snapshots.
  5. Make CI always upload the Task 27 artifact manifest and redacted evidence.
  6. Switch the traceability validator to final mode: reject every `planned`,
     skipped, expected-failing, missing, or nonexistent release mapping.
  7. Audit every specification ID against executable evidence. Remove obsolete
     source-only acceptance claims and retain useful source checks as contracts.
  8. Add `make check-release VM_IMAGE=...` and document operator prerequisites,
     estimated resource use, exact commands, recovery, and result interpretation.
  9. Execute the complete release command from a clean baseline and preserve its
     final artifact set.
- Verification:
  - Run CI configuration validation.
  - Run the traceability validator in final mode.
  - Run `make check-release` from a clean Ubuntu baseline.
  - Confirm zero skipped or expected-failing release requirements.
  - Run `make check` and `git diff --check`.
- Completion criteria: every applicable statement in `Specification.md` maps to
  passing executable evidence, and the release command fails closed on any
  missing, skipped, flaky, or failed requirement.

## Completion records

Append one entry only after its checklist item has been changed to `[x]`:

```text
### Task NN completed — YYYY-MM-DD

- Result: <concise description>
- Verification: `<command>`; `<command>`
- Commit: <hash or "not committed">
```
