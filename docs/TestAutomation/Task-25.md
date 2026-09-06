# Task 25 — Graphical application policy and multi-user isolation

Execute 25A and 25B separately. Reuse Task 15's native, Snap, and Flatpak
fixtures, launch assertions, and ownership-recorded process helpers.

Follow [E2E-Coverage.md](E2E-Coverage.md). Expand assigned route, policy, and
multi-user families into explicit variants. Configure policy and establish
ordinary sessions through customer UIs; launch through the actual route under
test, including real terminal input for a command route. No injected filter,
grant, session state, or VM checkpoint replaces those operations. Process
fixtures exercise real OS enforcement but do not prove gameplay; Task 26C
additionally requires a real installed game and continuous customer journeys.

## Task 25A

- Title: Automate graphical launch-route and matching matrices.
- Depends on: Task 24B.
- Complexity: high. The route matrix is broad, but backend enforcement and
  graphical runner contracts are already established.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Work:
  1. Configure distinct policies for two children and verify allowed, hard, and
     soft states with screen time enabled and disabled.
  2. Launch native targets from app grid, desktop launcher, file manager, and
     command; exercise Snap and Flatpak by supported application identity.
     Record visible outcomes as well as backend allow/deny evidence.
  3. Cover precise and version-tolerant AppImage matching, same-directory
     nonmatches, supported copied/renamed limitations, update between display
     and save, and missing-launcher retention.
  4. Verify a matching target remains usable by unrelated users and update
     launch-route and matching mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before fixture execution.
  - Run complete route/matching attempts on the guarded VM with screenshots,
    kernel process identity, filters, rules, and launch results.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: every specified native/Snap/Flatpak route and matching
  behavior has visible acceptance evidence.

## Task 25B

- Title: Prove multi-session termination and grant isolation.
- Depends on: Task 25A.
- Complexity: very high. Multiple retained graphical sessions and irreversible
  partial failure must remain independently observable.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Create simultaneous sessions for two children, an administrator, and an
     unrelated user; open matching fixtures in multiple sessions of the selected
     child. Use explicit recorded fixture identities.
  2. Apply restrictive saves, approve with and without soft apps, and revoke
     while targets are open. Prove every required selected-child app closes and
     all other users' processes and foreground sessions survive.
  3. Exercise partial termination failure: strict blocks remain, prior grant
     time is preserved where required, and no partial success is displayed.
     Declare the real OS intervention and classify it as fault/recovery;
     ordinary save/approve/revoke variants remain independently required.
  4. Prove hard blocks never relax. Verify soft exceptions only for explicit
     grants, complete policy after revocation/screen-time reapplication, and
     expired-grant reconciliation at next session entry. Expiry itself must not
     close retained apps; an active replacement grant must retain its chosen
     policy and open processes.
  5. Update revocation, transaction, and multi-user mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before live termination cases.
  - Run ordinary and partial-failure cases as separate complete attempts.
    Reset only outside attempts. Capture
    per-session screens, kernel UIDs, Snap labels, Flatpak instance IDs, filters,
    rules, grants, and redacted logs.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=<assigned-scenario-id>`,
    `make check`, and `git diff --check`.
- Completion criteria: every required termination/isolation outcome is visible
  and supported by authoritative state.
