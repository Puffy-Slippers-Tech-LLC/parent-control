# Task 24 — Dedicated kiosk request scenarios

Execute 24A and 24B separately. Reuse Task 23's shared request-form helpers;
retain kiosk-specific account selection, request method, mute, and logout.

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
  4. Publish kiosk entry/exit and agent-recovery helpers; update session
     restriction and recovery mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated controls.
  - Run the kiosk restriction/recovery cases twice on fresh installed overlays.
    Correlate screens, user units, sessions, broker calls, grants, and logs.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<kiosk-session>`,
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
  2. Reuse Task 23 cases for invalid input, auth cancel, rejected password,
     both approval choices, and duplicate submission. Verify kiosk broker
     targeting and selected-parent restriction with authoritative state.
  3. Verify explicit cancel and Escape return to GDM; approval returns after its
     brief confirmation. Keep these expectations distinct from overlay close.
  4. Round-trip remembered choices between kiosk and child overlay for each
     child; verify kiosk and child mute remain independent.
  5. Run shared-form regressions in both modes and update kiosk/form mappings.
- Verification:
  - Run focused local UI checks through `tools/run-ui-tests --timeout <duration>
    <pytest-selectors>`; run cleanup-safety regressions first where needed.
  - Run the kiosk form cases twice from fresh installed overlays and correlate
    screenshots with sessions, broker calls, grants, preferences, and logs.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<kiosk-form>`,
    `make check`, and `git diff --check`.
- Completion criteria: kiosk selection, approval, shared choices, and every exit
  path have graphical and backend evidence.
