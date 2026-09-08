# Task 24 — Dedicated kiosk request scenarios

Execute 24A and 24B separately. Reuse Task 23's shared request-form helpers;
retain kiosk-specific account selection, request method, mute, and logout.

Follow [E2E-Coverage.md](E2E-Coverage.md). Enumerate the kiosk variants and
execute actual GDM entry, customer requests, system password prompts, and
return-to-GDM behavior. Never launch a preview or inject request results. No
VM checkpoint may replace entry, approval, exit, or a cross-surface round trip.

## Implementation slices

Use the [implementation workflow](Implementation-Workflow.md). These are small
work boundaries within the existing task, not extra acceptance checklists.
Verification below is task acceptance; edits use the smallest affected selection.

| Task | First proof, then expansion |
| --- | --- |
| 24A | Reuse the basic kiosk entry/approval helper; prove restriction and one agent recovery before expanding cases. |
| 24B | Adapt the shared case table by surface, preserving kiosk exits and targets; then prove the cross-surface round trip. |

## Task 24A

- Title: Prove restricted kiosk startup and authentication-agent recovery.
- Depends on: Task 23B.
- Complexity: high. Dedicated-session composition, containment, and service
  recovery require integration reasoning beyond routine form interactions.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Select the dedicated session at GDM and verify fullscreen kiosk startup,
     maintained Polkit agent readiness, and absence of a general desktop.
  2. Attempt Parent, terminal, settings, user management, and arbitrary desktop
     launches through relevant supported session paths. Prove request-only
     restrictions after success and failure.
  3. Stop the authentication-agent service during a request using public guest
     service controls; verify safe denial, restart its maintained user service,
     and complete a later request.
     Classify this declared real-service intervention as fault/recovery; keep
     the uninterrupted normal kiosk approval journey separately required.
  4. Publish kiosk entry/exit and agent-recovery helpers; update session
     restriction and recovery mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated controls.
  - Run each complete kiosk restriction/recovery variant once; reset the baseline
    only outside attempts, never between the failure and recovery steps.
    Correlate screens, user units, sessions, broker calls, grants, and logs.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: the kiosk starts and recovers as a request-only session.

## Task 24B

- Title: Complete kiosk form, approval, persistence, and logout cases.
- Depends on: Task 24A.
- Complexity: medium. This adapts the tested shared form matrix to a now-proven
  kiosk session.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Verify eligible children/parents, child switching, loading gates, no-child
     and no-approver states, and the explanation when control is disabled.
     Prepare real account/role fixtures with supported guest helpers; account
     creation interfaces and third-party account administration are outside scope.
  2. Reuse Task 23 cases for invalid input, auth cancel, rejected password,
     both approval choices, and duplicate submission. Verify kiosk broker
     targeting and selected-parent restriction with authoritative state. Keep
     exhaustive equivalent input values in the shared local tests; execute the
     distinct kiosk workflows and relevant boundaries graphically. Denial/cancel
     must preserve app state and permit retry; generic password rejection alone
     is not the assertion. Retain both surfaces' required integration cases.
  3. Verify explicit cancel and Escape return to GDM; approval returns after its
     brief confirmation. Keep these expectations distinct from overlay close.
  4. Round-trip remembered choices between kiosk and child overlay for each
     child; verify kiosk and child mute remain independent.
  5. Run shared-form regressions in both modes and update kiosk/form mappings.
- Verification:
  - Run focused local UI checks through `tools/run-ui-tests --timeout <duration>
    <pytest-selectors>`; run cleanup-safety regressions first where needed.
  - Run each complete kiosk form variant once on the guarded VM and correlate
    screenshots with sessions, broker calls, grants, preferences, and logs.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: kiosk selection, approval, shared choices, and every exit
  path have graphical and backend evidence.
