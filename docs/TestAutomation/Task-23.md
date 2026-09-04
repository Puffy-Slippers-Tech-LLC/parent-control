# Task 23 — Child-overlay request and approval

Execute 23A and 23B separately. The child and kiosk use one GTK form: shared
helpers must accept an explicit surface and preserve differences in account
selection, broker method, mute preference, and exit behavior.

## Task 23A

- Title: Automate real authentication and atomic child approval.
- Depends on: Task 22B.
- Complexity: high. Real Polkit challenges and policy/time transactions are
  demanding, but installed authorization and isolation helpers already exist.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Open the overlay from the child panel; verify the child is fixed and only
     eligible parents appear. Select each parent and prove the real system
     prompt is restricted to that identity and shows child/duration/soft choice.
  2. Use secret-safe password entry. Exercise authentication cancel, rejected
     password, and successful retry without lost choices or a consumed repeat
     interval. Credentials must remain confined to the system prompt.
  3. Approve without soft apps: prove all blocked child apps close across
     sessions before time becomes active and unrelated apps survive.
  4. Approve with soft apps: prove no open app closes, hard launches remain
     blocked, and soft launches work. On expiry, prove lock without immediate
     termination; verify reconciliation at session entry and replacement-grant
     precedence using Tasks 17B/22A's contract.
  5. Exercise rapid duplicate submission and prove exactly one grant. Verify no
     reusable Polkit authorization or child management access afterward.
  6. Publish shared surface-aware authentication/approval helpers for 23B/24B
     and update identity, authorization, and transaction mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before process fixtures.
  - Run denial/cancel and both approval cases in separate fresh overlays.
    Correlate screens, correlation IDs, processes, AppFilter, grants, and logs.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<child-approval>`,
    `make check`, and `git diff --check`.
- Completion criteria: real child approval preserves identity, atomicity,
  isolation, and least authority.

## Task 23B

- Title: Automate shared form validation, choices, and overlay exit.
- Depends on: Task 23A.
- Complexity: medium. This is a bounded UI matrix using the established
  surface-aware authentication and state assertions.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Cover predefined, rest-of-day, minimum, maximum, fractional, and invalid
     custom durations. Prove invalid input never invokes Polkit.
  2. Verify at most one overlay, Escape, explicit cancel, success confirmation,
     automatic close, and post-close countdown refresh.
  3. Verify remembered duration, custom value, selected parent, and soft-app
     choice are stored per child in shared preferences; child mute is separate
     from kiosk mute. Task 24B supplies the cross-surface graphical round trip.
  4. Parameterize shared form cases for both modes and run the existing local
     shared-GTK regressions in both modes for any form/helper change.
  5. Update validation, overlay lifecycle, and choice-persistence mappings;
     leave kiosk exit/selection evidence pending for 24B.
- Verification:
  - Run focused shared-form regressions through
    `tools/run-ui-tests --timeout <duration> <pytest-selectors>`.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<child-form>`
    from a fresh overlay, `make check`, and `git diff --check`.
- Completion criteria: overlay form behavior is proven and shared cases are
  ready for the dedicated kiosk without duplicating authentication logic.
