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

