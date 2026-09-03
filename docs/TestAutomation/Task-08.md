### Task 08 — Automate the shared kiosk and child request form locally

- Complexity: medium-high. The same widgets have different caller identity,
  mute storage, and exit semantics.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: prove shared behavior once and mode-specific behavior twice.
- Work:
  1. Parameterize one semantic request-form suite over kiosk and child-overlay
     modes.
  2. Test loading, no-child, no-approver, control-disabled, predefined duration,
     rest-of-day, custom range and precision, approver selection, soft-app
     selection, duplicate prevention, denial, cancellation, service failure,
     approval, and redacted error copy.
  3. Test fixed child identity and overlay close behavior in child mode.
  4. Test child selection, return-to-login action, and logout behavior in kiosk
     mode.
  5. Test shared remembered choices and separate kiosk/child mute values.
  6. Test Escape while idle and while an authentication request is active.
  7. Update request-station and child-overlay requirement mappings.
- Verification:
  - Run both parameter values explicitly and together three consecutive times.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: every shared behavior runs against both modes and every
  differing behavior has a mode-specific assertion.

