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

