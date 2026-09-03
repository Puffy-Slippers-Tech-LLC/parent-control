### Task 25 — Automate application policy and multi-user isolation scenarios

- Complexity: very high. Multiple graphical sessions and execution routes must
  remain independently observable.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove end-to-end enforcement rather than merely backend rule state.
- Work:
  1. Create simultaneous sessions for two children, an administrator, and an
     unrelated user using the deterministic Task 11 applications.
  2. Apply distinct policies to both children and launch targets from the app
     grid, desktop launcher, file manager, command, and Flatpak identity.
  3. Verify allowed, hard, and soft states with screen time both enabled and
     disabled.
  4. Verify precise and version-tolerant AppImage matching, same-directory
     nonmatches, supported renamed/copied limitations, target update between
     display and save, and missing-launcher retention.
  5. Approve and revoke grants while matching processes are open across multiple
     sessions for the selected child.
  6. Prove every required selected-child process closes, every other user's
     process remains, the strict filter remains on partial termination failure,
     and time is not granted or revoked partially.
  7. Verify hard blocks never relax, soft blocks relax only for an explicit
     soft-app grant, and soft blocks restore after expiry, revocation, and screen-
     time reapplication.
  8. Update application, revocation, and multi-user requirement mappings.
- Verification:
  - Run the scenario from a fresh installed overlay.
  - Capture per-session screenshots, kernel-reported process UIDs, Flatpak
    instance IDs, filters, fapolicyd rules, grants, and logs.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: every supported application route and isolation promise
  has user-visible and authoritative evidence.

