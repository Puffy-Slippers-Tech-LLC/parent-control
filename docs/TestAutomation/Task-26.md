# Task 26 — Failure, recovery, and continuous customer journeys

Execute 26A, 26B, and 26C separately. Reuse existing failure controls; add a new control
only at a maintained public guest OS boundary. No hidden production injection
method or authorization bypass is permitted.

Follow [E2E-Coverage.md](E2E-Coverage.md). Enumerate all assigned variants;
label deliberate real OS interventions and controlled-environment cases
separately from ordinary customer journeys. No mocked service, state injection
standing in for a customer action, or intermediate VM checkpoint is allowed.
Failure → recovery and restart → resumed use are continuous sequences, not
separate preconstructed states. Read-only state captures are evidence, never
restorable VM snapshots.

## Implementation slices

Use the [implementation workflow](Implementation-Workflow.md). These are small
work boundaries within the existing task, not extra acceptance checklists.
Verification below is task acceptance; edits use the smallest affected selection.

| Task | First proof, then expansion |
| --- | --- |
| 26A | Inventory existing canonical fault cases first; implement only missing graphical transitions/interactions, starting with one observable race. |
| 26B | One real restart/resumed-use boundary; then parameterize each required persistence boundary. |
| 26C | Prove the real-game E2E-023 path and its fullscreen/windowed variants before filling remaining journey gaps; reuse existing cases. |

## Task 26A

- Title: Prove adversarial transaction races and failure recovery.
- Depends on: Task 25B.
- Complexity: very high. Controlling stale identities, concurrent requests, and
  irreversible side effects across real services is the hardest remaining
  cross-component correctness task.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `xhigh`
- Work:
  1. Inventory existing evidence and complete the matrix for invalid/unauthorized
     calls, Polkit denial/cancel, requester disconnect, account/role/preference
     changes during authentication, usage-query failure, broker restart, agent
     failure, fapolicyd reload failure, and process-termination failure.
  2. Synchronize at observable public boundaries with bounded deadlines. Prove
     each intended failure actually occurred, rather than inferring it from a
     generic error or using a timing sleep.
  3. Verify reversible failures restore prior state and failed rollback read-back
     is reported distinctly. After partial process termination, keep strict
     blocks and required prior time while other users remain untouched.
  4. Interleave policy saves, approvals, revocations, and session preparation.
     Prove single-flight serialization, exactly-once grant changes, replacement-
     grant precedence, and repeat-interval consumption only after success.
  5. Verify displayed failures are actionable and expose no internal paths,
     service names, account PII, or backend details on both request surfaces.
  6. Publish a failure-case/evidence matrix and reusable assertions for 26B.
     Update failure, concurrency, and rollback mappings.
- Verification:
  - Run each new controller's cleanup-safety regressions in isolation first.
  - Run each complete failure/race attempt separately on the guarded VM; compare
    read-only before/after state evidence. Reset only outside complete attempts.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: the failure/race matrix is deterministic, fail-closed,
  and supported by evidence of the actual triggered boundary.

## Task 26B

- Title: Complete restart and persistence scenarios.
- Depends on: Task 26A.
- Complexity: medium. Restart boundaries and expected state are specified and
  reusable failure/guest controls now exist.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Restart Parent, both request surfaces, the broker, affected user sessions,
     package services, and the VM using the established guest controllers.
     Customer app/session/reboot operations use the real guest UI. Declare
     service interventions separately. Configure and approve through the real
     UI before each sequence; observe continuity across actual restarts rather
     than restoring saved VM state or reapplying expected preferences.
     Include real desktop idle, suspend/wake and resumed gameplay where
     required by the supported session matrix. A suspend/resume keeps its
     actual session/boot continuity; it is not a VM save-state/load-state test.
  2. At each boundary verify per-child preferences, shared choices, separate
     mute values, grants, extension publication, and enforcement. Distinguish
     durable data from derived state using the [state design](../SystemDesign/State.md).
  3. Verify recovery from a prior safe denial without retaining authorization or
     applying an obsolete grant/policy. Reuse 26A's state assertions.
  4. Update persistence/restart mappings and the boundary/evidence matrix.
- Verification:
  - Run cleanup-safety regressions in isolation before restart controllers.
  - Run complete restart attempts on the guarded VM; correlate visible results with
    authoritative state and boot/session identities.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: every specified persistence boundary is exercised with
  independent child state and correct recovery.

## Task 26C

- Title: Complete continuous customer journeys and coverage enumeration.
- Depends on: Task 26B.
- Complexity: high. Reuse established graphical helpers and installed
  assertions, but independently prove complete customer paths and their
  cross-user, policy, session, and package transitions.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Review the complete scenario inventory against E2E-Coverage.md, the product
     specification, system design, and package lifecycle contracts. Expand all
     applicable scenario families into explicit selectable variants and close
     missing customer transitions. Do not limit coverage to the seed table or
     the user's sample, or claim that separately passing fragments prove a
     continuous journey. Preserve earlier completed evidence and add the gaps.
  2. Supply a real, version-pinned installed game with reproducible offline
     gameplay and normal desktop launch. Record package/runtime/asset digests
     and guest requirements. Reuse the artifact contract for verified delivery;
     changes needed on the development machine belong in `setup.sh`. A sleeping
     process fixture, preview, menu-only launch, or fake game is insufficient.
  3. Implement E2E-023 exactly as a continuous graphical attempt: parent login
     and zero allowance → Switch User preserving the parent → correct-password
     child denial → real kiosk request/authentication → child login → gameplay
     → actual elapsed-time lock → correct-password unlock denial. Run windowed
     and fullscreen variants; preserve the real child session/game on expiry.
  4. Complete E2E-024/E2E-025 and any missing cross-surface journeys: additional
     time while active, both approval choices, expired/replacement grants, and
     independent children/other foreground users. Establish grants and policy
     through real UI operations; no hidden state writes, simulated clock,
     forced expiry/lock, checkpoint, or mid-journey reset is permitted.
  5. Complete E2E-026/E2E-027 through real customer package operations, including
     guest terminal input where appropriate. Reuse Tasks 18/20's installed
     assertions while actually performing update/activation, removal/reboot,
     post-removal login, reinstall with retained choices, and purge. Package
     fixture variants are separately identified and cannot replace the exact
     release artifact in its ordinary customer journeys.
  6. Register all executable cases and variants with ordered steps, visible
     outcomes, read-only backend corroboration, other-user assertions,
     package/source identity, session/boot continuity, and evidence locations.
     Record actual durations and any remaining gap; required gaps must be
     resolved before this task completes and before final release acceptance.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated operations.
  - Run every newly completed canonical journey/variant once, including both
    E2E-023 gameplay variants. Repetition follows a stated stability question;
    any rerun retains its first failure and begins the whole journey again.
  - Review screen/step traces against customer actions and check that backend
    witnesses did not produce the outcome. Verify gameplay, natural expiry,
    expected retained sessions, and other-user isolation.
  - Use `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`
    for the enumerated cases, then `make check` and `git diff --check`.
- Completion criteria: all applicable customer journeys are enumerated and
  implemented, including the continuous sample and real-game/lifecycle cases.
  Evidence demonstrates actual operations without mocks or VM state shortcuts;
  Task 28B still performs the independent final completeness audit.
