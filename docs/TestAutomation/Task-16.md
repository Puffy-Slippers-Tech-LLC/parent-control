# Task 16 — Installed time authority, PAM, and sessions

Execute 16A and 16B separately. All clock, account, and session changes are
confined to disposable guests.

## Task 16A

- Title: Test real usage, grant arithmetic, midnight, and DST.
- Depends on: Task 15B.
- Complexity: high. Real time authorities and coherent clock fixtures need
  careful integration, but no new authentication or process-control boundary.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Verify actual Malcontent usage recording, overlapping intervals, daily
     allowance calculation, zero-minute grant-only mode, and authoritative
     AccountsService `ActiveExtension` values.
  2. Grant the minimum 0.1 minute and verify fixed-duration accumulation against
     both daily remaining time and an existing later grant.
  3. Test ordinary midnight and both DST transition directions in separate
     disposable boots. Keep the entire guest clock coherent, preload artifacts,
     and record timezone, boot ID, clocks, and package digests.
  4. Publish reusable guest time/state assertions and update time requirement
     mappings. Never use a production clock hook or change the host clock.
- Verification:
  - Run each clock scenario from a fresh testbed; collect Malcontent replies
    and AccountsService properties with recorded clock context.
  - Run `make check-system VM_IMAGE=<verified-baseline>`, `make check`, and
    `git diff --check`.
- Completion criteria: real system authorities match the documented time formula
  and local-day semantics.

## Task 16B

- Title: Test PAM login/unlock and managed-session lifetime.
- Depends on: Task 16A.
- Complexity: very high. PAM authentication/account phases, systemd scopes,
  broker recovery, and other users' live sessions form one security boundary.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Use `pamtester` to exercise positive and negative account-management and
     product `gdm-password` authentication results. Cover administrator, kiosk,
     unrestricted unrelated-account, and applicable system-account exemptions;
     unknown/malformed limit state must fail closed.
  2. Create real child sessions. Prove runtime caps are cleared only for managed
     children, broker restart clears their stale caps, and expiry does not end
     the live session or another user's foreground session.
  3. Verify zero time denies fresh-login account checks and retained-session
     unlock authentication; a valid grant permits both. Distinguish confirmed
     exhaustion from an indeterminate backend failure.
  4. Record logind/PAM/session evidence and reusable assertions for Task 22.
     Graphical lock-screen and GDM proof remains in that later task.
  5. Update PAM, session-lifetime, and backend login/unlock mappings.
- Verification:
  - Run session-controller cleanup-safety regressions in isolation first.
  - Run fresh-testbed PAM/session cases; collect PAM results, logind state,
    usage/grants, boot IDs, timezone, clocks, and redacted logs.
  - Run `make check-system VM_IMAGE=<verified-baseline>`, `make check`, and
    `git diff --check`.
- Completion criteria: backend login/unlock and session lifetime match the
  specification without disturbing other users.
