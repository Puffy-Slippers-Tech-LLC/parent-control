# Task 21 — Parent App management journeys

Execute 21A and 21B separately. Use Task 19's public graphical helpers and
versioned guest assertions from the installed-system tasks.

Follow [E2E-Coverage.md](E2E-Coverage.md), expanding the assigned scenario
families only after auditing existing entries and dimensions. Saves and other
asserted product transitions use Parent's real UI. Unrelated account, application
and input-file setup follows the [prerequisite contract](E2E-Coverage.md#prepare-prerequisites-through-supported-helpers).
Never inject tested grant/authentication outcomes. Each scenario is a continuous
attempt on the existing VM, without intermediate resets.

## Implementation slices

Use the [implementation workflow](Implementation-Workflow.md). These are small
work boundaries within the existing task, not extra acceptance checklists.
Verification below is task acceptance; edits use the smallest affected selection.

| Task | First proof, then expansion |
| --- | --- |
| 21A | One real Parent discovery/access journey; then batch compatible navigation and validation steps. |
| 21B | First prove one real kiosk approval and one Parent save with other-user evidence; then extend the shared helpers to transaction variants. |

Before 21A acceptance, resolve the [E2E-005 ownership split](Reuse-Map.md#resolve-before-the-affected-batch):
its pending variants currently belong to 21A but require 21B's complete
transaction journey. Preserve all actions/assertions and stable IDs when
correcting the declarations. Complete E2E-030/031's normative requirement links
within 21A; E2E-032/033 delivery and transport-retry acceptance belongs to 26C.
Share helpers and reference canonical cases, without counting partial journeys.

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
  2. Keep Parent running and create a real eligible child through a supported
     guest account CLI or public AccountsService fixture helper. Verify the
     account exists and is eligible, then prove Parent discovers it without
     restarting. Select each child and check independent preferences, status,
     catalog and loading gates. Ubuntu's account-creation UI is outside scope.
     Record creation as a normal fixture event, with bounded readiness and owned
     cleanup. Reconcile E2E-003's pending `step-2` OS-UI declaration with this
     setup/observation boundary before implementation; preserve its discovery
     assertions and IDs. Do not hide the write in a read-only probe.
  3. Cover daily allowance boundaries from zero to 1440 minutes, application
     search/filter, all three displayed rules, and precise/version-tolerant
     matching controls using existing backend fixtures.
     Inventory installed Parent surfaces beyond those controls, including
     About/license access and feedback drafting, validation, attachment review,
     cancel and retry behavior. Use local component/property tests for exhaustive
     independent validation values and representative installed journeys for
     real integration, each meaningful control/flow and access restriction.
     Generate synthetic attachments and test inputs through fixture helpers;
     editing them in unrelated desktop apps is not a prerequisite. About/license
     access needs a focused check, not an additional OS lifecycle matrix.
     Passing local fake-transport feedback tests is not external-delivery
     acceptance. Reconcile layer/case mappings under the coverage contract.
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
- Depends on: Task 21A and the Task 15B/16B failure and ownership helpers.
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
