# Task 22 — Child countdown, expiry, lock, and login

Execute 22A and 22B separately. Reuse Tasks 16B and 17B's backend assertions.
Expiry and session-entry behavior must follow the current specification:
expiry locks without closing apps, and a current replacement grant wins over
an earlier expired grant during session preparation.

## Task 22A

- Title: Prove lock, retained-session unlock, and fresh-login enforcement.
- Depends on: Task 21B.
- Complexity: very high. GNOME Shell, PAM, logind, active-user isolation, and
  broker reconciliation must agree across retained and new sessions.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Configure the child through Parent, log out, and log in as the child.
     Verify packaged extension activation in the real Shell.
  2. Let a real short grant expire. Verify lock, preservation of the child
     session and its running apps, and no disruption to another foreground user.
  3. Attempt zero-time unlock and verify the GDM time-limit explanation and
     `gdm-password` denial. Use public `loginctl` orchestration separately to
     expose a retained desktop without time and prove immediate relocking.
  4. Verify expired-grant session preparation restores canonical blocks before
     blocked-app termination. Correlate screens with Task 17B's real-caller
     assertions; no child-side grant authority or timer hook is permitted.
  5. Grant replacement time before unlock, testing both soft-app choices.
     Verify unlock succeeds and preparation preserves the policy/process state
     established by that current grant, including all open apps when allowed.
  6. End the retained session, prove fresh GDM login is denied at zero, then
     prove a fresh login succeeds during a valid grant.
  7. Publish reusable login/lock/session-state helpers and update time, login,
     reconciliation, and isolation mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before session/process controls.
  - Run the lock/login cases twice from fresh installed overlays. Correlate
    screenshots, logind sessions, PAM results, usage, grants, filters, processes,
    and PII-safe logs.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<child-lock-login>`,
    `make check`, and `git diff --check`.
- Completion criteria: zero-time login/unlock denial, lock without logout,
  replacement-grant precedence, and other-user isolation are proven graphically.

## Task 22B

- Title: Automate countdown display, visibility, and estimate recovery.
- Depends on: Task 22A.
- Complexity: medium. Established session helpers isolate panel presentation
  from the security-boundary implementation.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Verify minute countdown and final-minute seconds with the minimum real
     grant; do not add a production clock hook.
  2. Verify the control appears only on the unlocked managed child's desktop
     while usable time remains, never on GDM or the lock screen. Assert no
     independent child settings or custom lock-screen controls.
  3. Use established guest service controls for temporary Malcontent read
     failure; verify the last verified estimate remains and refresh recovers.
  4. Update countdown, visibility, and estimate-recovery mappings.
- Verification:
  - Run the display cases twice from fresh installed overlays with bounded
    screen waits and backend time evidence.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<child-countdown>`,
    `make check`, and `git diff --check`.
- Completion criteria: display and recovery requirements have visible evidence
  without duplicating lock/login transaction infrastructure.
