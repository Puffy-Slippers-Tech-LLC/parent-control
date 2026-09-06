# Task 21 — Parent App management journeys

Execute 21A and 21B separately. Use Task 19's public graphical helpers and
versioned guest assertions from the installed-system tasks.

Follow [E2E-Coverage.md](E2E-Coverage.md), expanding the assigned scenario
families and dimensions before implementation. Configure through Parent's real
UI; backend fixtures are installed application inputs or read-only assertions,
never injected preferences, grants, or authentication. Each scenario is a
continuous attempt on the existing VM, without intermediate resets.

## Task 21A

- Title: Automate Parent discovery, navigation, and validation.
- Depends on: Task 20.
- Complexity: medium. Semantic UI cases reuse established account and runner
  fixtures without adding privileged transaction infrastructure.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Log in as an eligible administrator, launch Parent from the app grid, and
     verify eligible children and exclusion of ineligible accounts.
  2. Create a child after installation and prove dynamic discovery. Select each
     child and check independent preferences, status, catalog, and loading gates.
     Create that account through the real administrator account-management UI.
  3. Cover daily allowance boundaries from zero to 1440 minutes, application
     search/filter, all three displayed rules, and precise/version-tolerant
     matching controls using existing backend fixtures.
     Inventory installed Parent surfaces beyond those controls, including
     About/license access and feedback drafting, validation, attachment review,
     cancel and retry behavior. Add explicit scenario variants for applicable
     behavior; passing local fake-transport feedback tests is not installed
     or external-delivery acceptance.
  4. Test standard-user launcher access and direct broker management denial,
     reusing Task 14's real-UID assertions. Record direct broker attacks as
     supplemental installed-system cases, not substitutes for launcher denial.
  5. Update only discovery, access, and control-validation mappings proven here;
     leave transaction outcomes to 21B.
- Verification:
  - Run all assigned scenario variants as complete independent attempts;
    reset the retained baseline only outside attempts. Correlate UI screenshots
    with account/catalog and real-caller evidence.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: Parent discovery, navigation, validation, and access
  restrictions have installed graphical evidence.

## Task 21B

- Title: Automate Parent saves, live policy, and revocation.
- Depends on: Task 21A.
- Complexity: high. UI ordering must be correlated with several privileged
  transactions, using already-tested backend assertions.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Work:
  1. Enable and disable screen time and change an enabled allowance. Verify
     extension activation, saved preferences, live policy, and grant semantics.
     Introduce the minimal real kiosk-entry/request/password approval helper
     needed to establish existing grants here. Tasks 22/23/24 reuse and extend
     it; their later full matrices are not a reason to inject a grant now.
  2. Change app rules and match choices; verify immediate auto-save in interaction
     order, disabled conflicting controls, selected-child process effects, and
     independence of the other child's state.
  3. Exercise failed save and revocation confirmation, including cancel and
     confirmed revocation. Verify restored controls, actionable rollback copy,
     grant/filter results, and unrelated-process survival.
  4. Reuse failure and ownership helpers from Tasks 15B/16B rather than adding a
     UI-only approximation of transaction state. Label intentional OS failures
     as fault/recovery variants; customer save and revocation actions remain
     graphical and real, and observation helpers cannot apply the outcome.
  5. Update Parent transaction and account-isolation mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before process fixtures.
  - Run complete transaction attempts on the guarded VM, correlating screens
    with broker, AccountsService, fapolicyd, and private-state guest assertions.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: management saves and revocation have visible,
  authoritative, and other-user isolation evidence.
