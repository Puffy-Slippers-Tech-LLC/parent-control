# Backend hardening execution plan

## Mission

Harden time-limit and application-restriction enforcement without replacing
Malcontent wholesale. The product broker must own policy, authorization,
transactions, reconciliation, and health reporting. Malcontent remains a
replaceable adapter for GNOME Shell, PAM, AccountsService, timer usage, and
Flatpak integration until measured evidence justifies replacing a specific
subsystem.

Target threat model: a managed, non-administrator child may use a terminal,
create launchers, copy and execute files, make D-Bus and Polkit calls, and run
arbitrary code as their own UID. The child does not possess administrator
credentials, cannot become root, cannot modify the boot chain, and cannot
exploit kernel vulnerabilities. Parent authentication must authorize only the
specific operation displayed to the parent.

This plan excludes GUI styling, cosmetic changes, remote administration, web
filtering, and a greenfield Malcontent replacement.

## Required reading and baseline

Before changing code, read these files in order:

1. `AGENTS.md`
2. `docs/System-Design.md`
3. `docs/Package-Update.md`
4. `docs/Data-Migration.md`
5. `docs/malcontent014-integration.md`
6. `docs/app-filter-design.md`
7. `docs/gnome50-integration.md`
8. `broker/oh_no_parent_control/core.py`
9. `broker/oh_no_parent_control/adapters.py`
10. `broker/oh_no_parent_control/service.py`
11. `broker/oh_no_parent_control/execution_policy.py`
12. `child/extension.js` and `kiosk/oh_no_parent_control_kiosk/main.py`

Then run:

```bash
git status --short
make check
```

The worktree may already contain user changes, including unfinished fapolicyd
work. Preserve them. Never reset, discard, or rewrite unrelated changes.

If a live-system test fails, inspect
`/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log`. If sandboxing blocks
the read, immediately request escalation for the smallest read-only command.
Never modify or remove logs.

## Execution rules

- Execute tasks in dependency order. Do not start a dependent task while a
  prerequisite has failing acceptance criteria.
- Keep each task reviewable. Prefer one task per commit when commits are in
  scope.
- Run focused tests during implementation and `make check` before completing
  every task.
- Update `docs/System-Design.md` in the same task as an architectural change.
- Add only public, documented, maintained integration points. If the required
  guarantee cannot be implemented with supported APIs, record the limitation
  and stop that task instead of using private GNOME state or an undocumented
  workaround.
- Treat `/var/lib/oh-no-parent-control/preferences/<uid>.json` as canonical for
  configured product policy. AccountsService and fapolicyd are derived
  enforcement state. `malcontent-timerd` remains canonical for measured usage,
  and AccountsService `ActiveExtension` remains runtime grant state.
- No front end may write AccountsService policy directly after Phase 1.
- A rejected, cancelled, disconnected, invalid, or partially failed request
  must not grant time or relax application policy.
- fapolicyd failure may degrade application enforcement but must not prevent the
  broker from serving unrelated time-status and management calls.
- When a task adds, moves, changes, or removes packaged integration, classify
  its activation in `tools/package_activation.py`, include its installed path in
  `ACTIVATION_MANIFEST_PATHS`, and add a focused activation test.
- When a task makes saved preferences incompatible, implement and test the
  versioned migration before changing any production reader or writer.

Recommended execution order:

```text
H-00 -> H-01 -> H-50 -> H-40 -> H-02
     -> H-10 -> H-11 -> H-12 -> H-13
     -> H-20 -> H-21 -> H-22 -> H-30
     -> H-31 -> H-32 -> H-33 -> H-41
     -> H-51 -> H-52 -> H-60 -> H-61 -> H-62
```

The dependency field is authoritative if this order and a task discovered
during implementation conflict.

## Sizing and model legend

Complexity measures implementation scope:

- `S`: localized change, normally under one day.
- `M`: several files or one integration boundary, roughly 1–3 days.
- `L`: cross-component change, roughly 3–7 days.
- `XL`: security-critical or system-wide work, likely more than one week.

Difficulty measures reasoning and failure risk: `Low`, `Moderate`, `High`, or
`Very high`.

Model recommendations follow the current OpenAI model roles: GPT-5.6 Sol for
complex reasoning and coding, Terra for balanced implementation work, and Luna
for cost-sensitive repetitive work. See the
[official model guide](https://developers.openai.com/api/docs/models). Use the
exact model and reasoning effort listed unless it is unavailable.

## Target architecture

```text
Parent app ───────────────┐
Child extension ──────────┼── system D-Bus ──> broker policy core
Kiosk request station ────┘                       │
                                                  ├── PolicyStore
                                                  ├── UsageLedger
                                                  ├── SessionEnforcer
                                                  ├── AppEnforcer
                                                  └── AuthorizationProvider
                                                       │
                                                       ├── Malcontent/AccountsService
                                                       ├── malcontent-timerd
                                                       └── fapolicyd
```

The broker validates one request, obtains one narrowly scoped authorization,
computes one desired state, and performs one verified transaction. Adapters do
not decide product policy.

## Phase 0: freeze contracts and create seams

### [x] H-00 — Capture the reproducible baseline

- **Depends on:** none
- **Complexity:** S
- **Difficulty:** Low
- **Recommended model:** `gpt-5.6-terra`, reasoning `medium`
- **Activation:** none
- **Migration:** none

Actions:

1. Record Ubuntu, GNOME Shell, AccountsService, Malcontent, fapolicyd, Flatpak,
   and PAM package versions in `tests/integration/README.md`.
2. Record whether each dependency is installed, enabled, and usable; do not
   silently substitute mocks for missing system services.
3. Document the commands for running unit tests and future destructive VM-only
   integration tests.
4. Add a baseline test inventory separating unit/source-contract tests from
   live integration tests.

Acceptance:

- A new agent can identify the exact supported platform and missing local
  dependencies without reading chat history.
- `make check` passes.
- No production behavior changes.

### [x] H-01 — Codify the threat model and enforcement guarantees

- **Depends on:** H-00
- **Complexity:** M
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-sol`, reasoning `xhigh`
- **Activation:** none
- **Migration:** none

Actions:

1. Add `docs/Threat-Model.md` using the threat model at the top of this plan.
2. Enumerate assets: daily allowance, runtime grants, permanent app blocks,
   conditional app blocks, parent credentials, preference records, timer usage,
   generated execution rules, and audit logs.
3. Enumerate trust boundaries for front ends, broker, Polkit, AccountsService,
   Malcontent daemons, PAM/GDM, Flatpak, and fapolicyd.
4. Specify failure behavior for unavailable services, partial writes, caller
   disconnects, identity changes, concurrent requests, and backend drift.
5. Explicitly exclude root, administrator credentials, offline disk changes,
   alternate boot media, and kernel exploits.
6. Add a requirements-to-test matrix. Every in-scope bypass must map to a unit
   or VM integration test planned below.

Acceptance:

- The document answers whether copying a binary, constructing a D-Bus call, or
  invoking the Polkit action is in scope.
- No requirement claims Malcontent alone is a hard security boundary.
- Unsupported guarantees are labeled as release blockers or explicit product
  limitations.

### [ ] H-02 — Introduce backend ports without behavior changes

- **Depends on:** H-01
- **Complexity:** M
- **Difficulty:** Moderate
- **Recommended model:** `gpt-5.6-terra`, reasoning `high`
- **Activation:** process-restart
- **Migration:** none

Actions:

1. Define narrow protocols for `PolicyStore`, `UsageLedger`,
   `SessionEnforcer`, `AppEnforcer`, and `AuthorizationProvider`.
2. Move Malcontent/AccountsService and fapolicyd-specific calls behind those
   protocols. Keep product validation and grant calculations in `core.py`.
3. Preserve existing D-Bus signatures and behavior.
4. Replace broad adapter exceptions with typed, redacted domain failures.
5. Add contract tests for every adapter using deterministic fakes.

Acceptance:

- `core.py` contains no Gio, GLib, subprocess, filesystem-rule, or D-Bus
  implementation details.
- Existing public D-Bus behavior and all tests remain unchanged.
- The Malcontent implementation can later be replaced without changing request
  policy code.

## Phase 1: make the broker own child requests

### [ ] H-10 — Define a unified access-request transaction

- **Depends on:** H-02
- **Complexity:** L
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-sol`, reasoning `xhigh`
- **Activation:** process-restart
- **Migration:** none

Actions:

1. Extract a request command containing caller role, target UID, approver UID,
   requested duration, end-of-day mode, and conditional-app choice.
2. Share validation, rate limiting, selected-approver validation, usage query,
   cumulative-grant calculation, account revalidation, caller-liveness checks,
   write ordering, read-back verification, and rollback between kiosk and child
   requests.
3. Reject access requests when parent control is disabled for the target.
4. Compute the complete desired app filter before authorization.
5. Do not write any state until authorization and the parent-scoped usage query
   both succeed.
6. Preserve the formula:

   ```text
   ActiveExtension = max(daily allowance remaining,
                         current grant remaining)
                     + additional grant
   ```

Acceptance:

- Kiosk behavior is unchanged.
- All pre-authorization and post-authorization identity changes fail closed.
- Failure-injection tests cover every write and rollback step.
- No transaction can return `approved` after an app-policy failure.

### [ ] H-11 — Add broker-mediated `RequestOwnAccess`

- **Depends on:** H-10
- **Complexity:** L
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `max`
- **Activation:** process-restart; session-renewal for the child payload in H-12
- **Migration:** none

Actions:

1. Add `RequestOwnAccess` to the canonical D-Bus XML and service introspection.
2. Derive the target UID from the system-bus caller and require it to remain an
   eligible managed child.
3. Add a dedicated Polkit action for the broker-mediated child request. It must
   authorize the request only; it must not imply AccountsService actions and
   must not use retained `auth_admin_keep` authorization.
4. Restrict the authentication identity to the broker-validated selected local
   administrator.
5. Include the child label, requested duration, and app-relaxation choice in the
   authorization details shown to the parent.
6. Revalidate caller connection, child account, approver account, enabled state,
   and preferences immediately before writes.
7. Apply the unified H-10 transaction as root after authorization.
8. Add D-Bus policy, adapter, core, service, Polkit, spoofed-detail, and
   disconnected-caller tests.

Acceptance:

- A child can request access only for their own UID.
- A child-created process cannot choose an unvalidated approver or target.
- Authorization does not grant the child any direct AccountsService
  capability.
- One parent authentication covers the verified time and app transaction.
- Denial, cancellation, agent loss, timeout, and caller disconnect produce no
  writes.

### [ ] H-12 — Migrate the child extension and remove direct privileged writes

- **Depends on:** H-11
- **Complexity:** M
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-terra`, reasoning `high`
- **Activation:** session-renewal for extension files; process-restart for
  removed or changed Polkit integration
- **Migration:** none

Actions:

1. Add a child D-Bus client for `RequestOwnAccess`.
2. Replace the extension's `withAuthorization()` and direct AccountsService
   writes with the single broker call.
3. Display granted time only after the broker returns a verified `approved`
   result.
4. Remove `parentalApproval.js`, `sessionLimitsClient.js`, and
   `appFilterClient.js` when no supported code references them.
5. Remove the old `ApproveTimeAndApps` Polkit meta-action and its
   `org.freedesktop.policykit.imply` permissions.
6. Remove the corresponding selected-admin rule branch if it is no longer
   shared.
7. Update packaging, uninstall paths, activation manifests, source-contract
   tests, and `docs/System-Design.md`.

Acceptance:

- `rg` finds no child-side AccountsService `Properties.Set` for `AppFilter` or
  `ActiveExtension`.
- `rg` finds no product Polkit action implying Malcontent `ChangeOwn` actions.
- Child, kiosk, and parent source tests pass.
- A live child request completes with one parent prompt and one broker
  transaction.

### [ ] H-13 — Prove transaction atomicity under injected failures

- **Depends on:** H-12
- **Complexity:** M
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-sol`, reasoning `high`
- **Activation:** none
- **Migration:** none

Actions:

1. Build a state-machine test fixture for old and desired daily limit, limit
   type, app filter, native execution rules, and active extension.
2. Inject failure before and after every backend call, verification read, and
   rollback call.
3. Test concurrent child/kiosk requests, duplicate completion, D-Bus caller
   disconnect, and approver-role changes.
4. Assert that permanent blocks are never relaxed by a failed request.
5. Assert that rollback failure produces a distinct critical health state and
   never reports success.

Acceptance:

- Every transaction transition has a deterministic test.
- The only successful terminal state is the fully verified desired state.
- The only failed terminal states are the fully restored old state or an
  explicit critical inconsistency state.

## Phase 2: establish canonical policy and reconciliation

### [ ] H-20 — Define canonical versus runtime state

- **Depends on:** H-13
- **Complexity:** M
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-sol`, reasoning `high`
- **Activation:** process-restart
- **Migration:** none unless the preference schema changes

Actions:

1. Introduce an immutable `DesiredPolicy` derived only from validated product
   preferences and current account eligibility.
2. Keep measured usage and current grant expiry out of saved preferences.
3. Derive desired `LimitType`, `DailyLimit`, and `AppFilter` from
   `DesiredPolicy`.
4. Make fapolicyd rules a derived projection of desired app policy, not a
   projection of arbitrary AccountsService state.
5. Document ownership for every field and service in `System-Design.md`.

Acceptance:

- Each persisted or runtime field has exactly one named authority.
- No reconciler imports externally changed AccountsService policy into product
  preferences.
- No startup reconciliation clears a still-valid runtime grant.

### [ ] H-21 — Implement idempotent startup and drift reconciliation

- **Depends on:** H-20
- **Complexity:** L
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `xhigh`
- **Activation:** process-restart
- **Migration:** none

Actions:

1. Build an idempotent reconciler that loads every eligible child's validated
   preferences and computes desired enforcement state.
2. Correct `LimitType`, `DailyLimit`, and `AppFilter` drift using verified
   writes.
3. Reconcile fapolicyd from desired policy independently of AccountsService
   signal payloads.
4. Preserve active grants unless policy is disabled or an explicit operation
   clears them.
5. Handle account creation, deletion, UID reuse, admin promotion, and malformed
   preference records without assigning stale policy to another identity.
6. Replace one-thread-per-signal behavior with a bounded, coalescing work queue.
7. Ignore self-generated redundant signals without suppressing later external
   drift.

Acceptance:

- Repeated reconciliation with unchanged state performs no writes or reloads.
- An external AccountsService policy change is restored from preferences.
- Account deletion removes generated execution rules.
- A signal storm has bounded memory, thread count, and reload count.

### [ ] H-22 — Add backend health and inconsistency reporting

- **Depends on:** H-21
- **Complexity:** M
- **Difficulty:** Moderate
- **Recommended model:** `gpt-5.6-terra`, reasoning `high`
- **Activation:** process-restart
- **Migration:** none

Actions:

1. Add a broker health model for policy store, AccountsService, timer usage,
   session enforcement, Flatpak filter projection, and native execution policy.
2. Add a read-only administrator D-Bus health method with stable machine-readable
   state and redacted messages.
3. Record the last successful reconciliation and the category of the last
   failure without exposing paths or child data to unauthorized callers.
4. Keep time-status methods available when only native app enforcement is
   degraded.
5. Make app-policy mutations and access requests fail closed when their required
   app enforcer is unhealthy.

Acceptance:

- Health distinguishes `healthy`, `degraded`, and `inconsistent` states.
- fapolicyd downtime does not prevent broker registration or unrelated reads.
- App-relaxation requests cannot succeed while app enforcement is inconsistent.

## Phase 3: harden application identity and native execution

### [ ] H-30 — Isolate fapolicyd activation from broker availability

- **Depends on:** H-22
- **Complexity:** M
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-terra`, reasoning `xhigh`
- **Activation:** process-restart
- **Migration:** none

Actions:

1. Remove fatal synchronous fapolicyd reconciliation from broker construction.
2. Start the broker, expose degraded app-enforcement health, and schedule a
   bounded initial reconciliation.
3. Serialize and coalesce rule generation and reloads.
4. Retain atomic file replacement, reload verification, and rollback.
5. Ensure failed reload rollback cannot recursively trigger unbounded work.
6. Add service-start, daemon-down, timeout, malformed-rule, rollback-failure,
   and recovery tests.

Acceptance:

- The broker owns its D-Bus name when fapolicyd is unavailable.
- Time reads and non-app operations continue to work.
- App mutations fail closed until successful reconciliation.
- Recovery requires no broker restart and produces one aggregate reload.

### [ ] H-31 — Specify supported application identities

- **Depends on:** H-30
- **Complexity:** L
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `max`
- **Activation:** none for the design; implementation is H-32
- **Migration:** assess and specify before H-32

Actions:

1. Research current public Malcontent, Flatpak, desktop-entry, fapolicyd, Snap,
   Steam, Waydroid, interpreter, and AppImage identity mechanisms using primary
   documentation and installed interfaces.
2. Classify launchers as:
   - unique Flatpak application;
   - unique native executable;
   - shared runtime or wrapper;
   - unsupported or ambiguous.
3. Define collision semantics when multiple desktop entries resolve to one
   enforcement target.
4. Test path copies, hard links, renamed files, content-identical copies,
   executable replacement during update, whitespace/comma paths, scripts,
   interpreters, Steam, Waydroid, Snap, and Flatpak.
5. Write an ADR selecting only supported enforcement primitives. If per-payload
   control behind a wrapper is not reliably enforceable, group those launchers
   or mark them unsupported instead of presenting false per-app control.
6. Specify the exact saved-data migration needed if app keys, target types, or
   state semantics change.

Acceptance:

- Every catalog entry has a documented stable enforcement identity or an
  explicit unsupported classification.
- The design does not equate a desktop ID with enforceable process identity.
- The ADR explains behavior after application updates and alternate launches.
- H-32 has deterministic expected behavior and migration requirements.

### [ ] H-32 — Implement collision-safe catalog and enforcement identities

- **Depends on:** H-31
- **Complexity:** XL
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `max`
- **Activation:** process-restart; session-renewal only if child payload changes
- **Migration:** required if H-31 changes saved app identity or semantics

Actions:

1. Implement the H-31 identity types in catalog, validation, preference policy,
   Malcontent projection, and native enforcement projection.
2. Make shared-runtime collisions visible as one enforcement group or reject
   unsupported independent states.
3. Prevent contradictory saved states for launchers sharing one enforceable
   target.
4. Implement supported copy/update resistance selected by the ADR.
5. Add a versioned, forward-only migration before deploying changed readers or
   writers.
6. Preserve uninstalled app policy without generating invalid active rules.
7. Add fixtures for real desktop-entry patterns without depending on the
   developer's installed applications.

Acceptance:

- Blocking one entry cannot silently block unrelated entries without the policy
  model representing that shared group.
- Direct launch, desktop-file launch, and the tested alternate paths have the
  same result.
- Application update behavior matches the ADR without a stale-hash window.
- Old preference fixtures migrate deterministically and retain user intent.

### [ ] H-33 — Add enforcement conformance tests

- **Depends on:** H-32
- **Complexity:** L
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-terra`, reasoning `high`
- **Activation:** none
- **Migration:** none

Actions:

1. Create a generated test application set containing unique binaries, copied
   binaries, scripts, interpreters, shared wrappers, paths with spaces, desktop
   files, and a Flatpak fixture where available.
2. Test allowed, permanent, conditional-blocked, approved-relaxation, expired,
   and rollback states under the managed UID.
3. Assert administrator and unrelated-user execution remains unaffected.
4. Verify rule ordering against existing administrator fapolicyd policy.
5. Verify uninstall removes only product-owned rules and never modifies logs or
   unrelated policy.

Acceptance:

- The threat-model application bypass matrix runs in a disposable VM.
- Every supported identity type has positive and negative execution tests.
- No test depends only on launcher visibility as proof of execution denial.

## Phase 4: contain Malcontent and login-path risk

### [ ] H-40 — Resolve CVE-2026-44931 for the supported platform

- **Depends on:** H-50
- **Complexity:** XL
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `max`
- **Activation:** reboot if PAM/GDM integration changes; otherwise classify the
  actual packaged daemon or policy path before implementation
- **Migration:** Malcontent timer data is external state; do not add it to the
  product preference migration chain

Actions:

1. Recheck current Ubuntu security status and package changelog at execution
   time; do not assume the vulnerability remains unfixed.
2. Reproduce bounded disk growth in a disposable VM, never on the development
   host.
3. Prefer a distribution-fixed package and enforce its minimum version in both
   Debian dependencies and `install.sh`.
4. If no supported fix exists, prepare a minimal API-compatible downstream
   patch based on upstream source, including caller validation and per-user
   bounds. Do not add a broad D-Bus deny rule that breaks GNOME Shell usage
   reporting.
5. Add abuse, legitimate high-volume reporting, upgrade, restart, and existing
   timer-store compatibility tests.
6. Block release if neither a fixed package nor a reviewed compatible patch is
   available.

Acceptance:

- An ordinary local user cannot grow timer storage without a tested bound.
- Legitimate GNOME Shell usage records still work.
- Installation cannot silently select a known-vulnerable dependency.
- The fix and ownership of future security updates are documented.

### [ ] H-41 — Characterize and harden timer and PAM failure behavior

- **Depends on:** H-40, H-50
- **Complexity:** XL
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `max`
- **Activation:** reboot for PAM/GDM changes; process-restart for broker or
  timer-service integration; session-renewal for child extension changes
- **Migration:** none unless a new product-owned data family is introduced

Actions:

1. Test fresh login when daily allowance is exhausted, when only a grant is
   valid, and when no limit exists.
2. Test timer daemon absent, activation timeout, crash during a session, corrupt
   store, read-only store, clock adjustment, DST, midnight rollover, suspend,
   resume, idle time, and concurrent graphical sessions.
3. Record whether each failure is fail-open or fail-closed in PAM and GNOME
   Shell 50.
4. Implement only supported service ordering, restart, and health mechanisms.
5. Do not inspect or modify private `TimeLimitsManager`, `AuthPrompt`,
   `ScreenShield`, or lock-screen state.
6. If an in-scope fail-closed guarantee is impossible through supported APIs,
   document it as a release blocker and open an upstream integration request.
7. Update PAM/GDM activation classifications and reboot tests for any changed
   login integration.

Acceptance:

- The failure matrix contains observed results from the supported Ubuntu image.
- Exhausted users cannot obtain a usable session through a tested daemon-start
  race.
- No implementation depends on private GNOME JavaScript APIs.
- PAM changes activate only at a clean reboot boundary.

## Phase 5: build the system integration gate

### [ ] H-50 — Create a disposable Ubuntu integration harness

- **Depends on:** H-00, H-01
- **Complexity:** XL
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-sol`, reasoning `xhigh`
- **Activation:** none for test-only files
- **Migration:** none

Implementation note (2026-09-01): the guarded harness, deterministic guest
provisioning, clean-install runner, artifact collector, destruction checks, and
host-safe contract tests are implemented. The task remains unchecked until the
clean-install acceptance run is performed on a disposable VM; it must not be
performed on the development workstation.

Actions:

1. Create `tests/integration/` with an Ubuntu 26.04 VM workflow matching the
   supported GNOME, Malcontent, AccountsService, PAM, Flatpak, and fapolicyd
   versions.
2. Make all host-altering tests refuse to run unless an explicit disposable-VM
   marker is present.
3. Provision administrator, child, kiosk, and unrelated standard-user accounts
   deterministically.
4. Install through the real package or `install.sh`; do not assemble product
   files manually.
5. Capture service status, D-Bus replies, rule snapshots, login results, and
   product logs as test artifacts with secrets redacted.
6. Provide `setup`, `run`, `collect`, and `destroy` commands. Destruction must
   target only an explicitly named disposable test VM.

Acceptance:

- A new agent can create and test a clean machine from documented commands.
- The harness cannot mutate the host when the VM marker is absent.
- A clean install and `make check` both pass in the supported image.

### [ ] H-51 — Automate the end-to-end policy matrix

- **Depends on:** H-13, H-21, H-30, H-33, H-41, H-50
- **Complexity:** XL
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `xhigh`
- **Activation:** none for test-only files
- **Migration:** none

Actions:

1. Automate parent enable/disable, daily limit, permanent block, conditional
   block, child request, kiosk request, grant accumulation, expiry, and
   rest-of-day flows.
2. Cover denial, cancellation, wrong password, Polkit agent loss, caller
   disconnect, account promotion/deletion, service restarts, partial failures,
   and concurrent requests.
3. Cover direct executable launch, desktop launch, copied executable, wrapper
   groups, Flatpak, update replacement, and missing application targets.
4. Cover fresh boot, login, lock, unlock denial, suspend/resume, midnight, DST,
   and multi-session usage.
5. Assert both externally visible behavior and canonical/derived state.

Acceptance:

- Every in-scope threat in `Threat-Model.md` maps to a passing test.
- A test fails if launcher hiding works but execution enforcement does not.
- A test fails on state drift even if the immediate UI reports success.

### [ ] H-52 — Make integration results a release gate

- **Depends on:** H-51
- **Complexity:** M
- **Difficulty:** Moderate
- **Recommended model:** `gpt-5.6-terra`, reasoning `high`
- **Activation:** none
- **Migration:** none

Actions:

1. Define required unit, package, migration, activation, clean-install, upgrade,
   and VM integration jobs for release.
2. Separate fast presubmit tests from privileged VM tests without allowing a
   release to skip the latter.
3. Publish a concise failure summary and preserve redacted artifacts.
4. Document the exact supported package versions and last successful matrix.
5. Add a release checklist requiring zero unresolved `inconsistent` health
   states and no known in-scope bypass.

Acceptance:

- Release documentation cannot be completed without a successful VM run.
- Failures identify the subsystem and scenario without requiring GUI inspection.
- Test results are reproducible from a clean image.

## Phase 6: measure before replacing Malcontent

### [ ] H-60 — Add adapter-level reliability metrics

- **Depends on:** H-22, H-52
- **Complexity:** M
- **Difficulty:** Moderate
- **Recommended model:** `gpt-5.6-terra`, reasoning `medium`
- **Activation:** process-restart
- **Migration:** none; do not store metrics in preference records

Actions:

1. Add bounded local counters for authorization failures, usage-query failures,
   reconciliation failures, rollbacks, rollback failures, timer busy retries,
   fapolicyd reload failures, and detected drift.
2. Keep labels low-cardinality and omit usernames, UIDs, app names, paths,
   passwords, and request contents.
3. Expose an administrator-only diagnostic snapshot or write aggregate events
   through the existing broker logger.
4. Define reliability thresholds for evaluating an adapter replacement.

Acceptance:

- Metrics contain no child-identifying or app-usage information.
- Counters are bounded and cannot fill disk.
- A clean VM run has documented expected counter values.

### [ ] H-61 — Prototype an alternative usage ledger in shadow mode

- **Depends on:** H-41, H-52, H-60
- **Complexity:** XL
- **Difficulty:** Very high
- **Recommended model:** `gpt-5.6-sol`, reasoning `max`
- **Activation:** process-restart if packaged; otherwise none for an isolated
  test prototype
- **Migration:** give any product-owned ledger its own versioned data family;
  never place it in preference records

Actions:

1. Implement only the `UsageLedger` port behind a disabled-by-default shadow
   adapter. Do not enforce from it.
2. Define interval validation, overlap merging, active/idle semantics,
   concurrent sessions, suspend/resume, day boundaries, clock changes, storage
   ownership, quotas, corruption recovery, and privacy authorization.
3. Compare shadow results with `malcontent-timerd` across the H-51 matrix.
4. Record mismatches without changing grants or lock decisions.
5. Add bounded storage, migration, crash-consistency, and local-DoS tests.

Acceptance:

- Shadow mode cannot alter enforcement.
- Every mismatch is classified and reproducible.
- The prototype meets storage and abuse bounds before any replacement proposal.

### [ ] H-62 — Run the replacement decision gate

- **Depends on:** H-61 and a representative observation period
- **Complexity:** M
- **Difficulty:** High
- **Recommended model:** `gpt-5.6-sol`, reasoning `xhigh`
- **Activation:** none
- **Migration:** none

Actions:

1. Compare the hardened adapter with an API-compatible Malcontent fork and a
   subsystem replacement using measured failure rate, bypass rate, maintenance
   time, upstream responsiveness, test coverage, and package compatibility.
2. Include GNOME Shell, PAM, AccountsService, Flatpak, GNOME Software, timer
   storage, D-Bus API, security-update, and release-engineering ownership.
3. Estimate initial engineer-months and annual maintenance for each option.
4. Prefer an API-compatible fork over a greenfield replacement if upstream
   maintenance is the primary problem.
5. Approve replacement only when the shadow ledger meets the full integration
   matrix and the expected ongoing cost is lower than maintaining the adapter.
6. Record the decision in an ADR. Do not start production replacement in this
   task.

Acceptance:

- The decision uses measured post-hardening evidence rather than wrapper count.
- The proposal identifies every external consumer that must remain compatible.
- A no-replacement decision includes explicit future reevaluation triggers.

## Completion criteria

The hardening program is complete only when all of the following are true:

- Child and kiosk requests are broker-mediated, narrowly authorized, verified,
  and transactional.
- No child code directly writes Malcontent/AccountsService policy.
- Product preferences are canonical for configured policy; derived backend
  drift is detected and corrected.
- fapolicyd failure cannot prevent broker availability, and app operations fail
  closed while app enforcement is unhealthy.
- Application identities and wrapper collisions have explicit, tested
  semantics; unsupported granularity is not presented as enforceable.
- CVE-2026-44931 is fixed or the release is blocked.
- PAM, GNOME Shell, timer, Flatpak, and native-execution behavior is tested on a
  clean supported Ubuntu VM, including failure and update paths.
- Package activation and saved-data migrations match their respective design
  documents.
- `make check` and the complete VM release matrix pass.
- Any Malcontent replacement proposal has passed the shadow-mode decision gate.
