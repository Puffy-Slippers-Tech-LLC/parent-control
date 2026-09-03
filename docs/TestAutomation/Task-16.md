### Task 16 — Test installed Malcontent, PAM, grants, and session behavior

- Complexity: very high. Time authority is distributed across Malcontent,
  AccountsService, PAM, systemd, and the broker.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove non-graphical time and login enforcement before UI scenarios.
- Work:
  1. Verify actual Malcontent usage recording, overlapping-interval handling,
     daily allowance calculation, zero-minute grant-only mode, and authoritative
     ActiveExtension values.
  2. Grant the minimum supported 0.1 minute and verify fixed-duration accumulation
     against both daily remaining time and an existing later grant.
  3. Verify rest-of-day arithmetic in dedicated disposable boots configured for
     ordinary midnight and both daylight-saving transition directions. Keep the
     entire VM clock coherent and preload all artifacts before time-shifted boots.
  4. Use `pamtester` for positive and negative account-management results and
     for the product's `gdm-password` authentication check. Verify
     administrator, kiosk, and unrelated-account exemptions on both applicable
     paths.
  5. Create real child sessions and verify that runtime caps are cleared only for
     managed children, broker restart clears stale caps, and expiry does not
     terminate the session.
  6. Verify a zero-time child fails the fresh-login account check and retained-
     session unlock authentication check, then verify a grant permits both at
     the backend and PAM levels. Graphical proof remains mapped to Task 22.
  7. Update time, PAM, and session requirement mappings.
- Verification:
  - Run all clock scenarios from fresh overlays.
  - Capture Malcontent replies, AccountsService properties, PAM results, logind
    state, boot IDs, timezone, and clocks.
  - Run `make check-system`, `make check`, and `git diff --check`.
- Completion criteria: real system authorities agree with the broker time model
  and the tests do not change the development-host clock.

