### Task 07 — Automate the Parent App as a local component

- Complexity: medium. Existing controller seams and preview data reduce the
  system dependencies.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Objective: replace acceptance reliance on source-text assertions with
  executable Parent UI behavior.
- Work:
  1. Supply scripted fake-broker responses through constructor injection and
     launch the production Parent window in the hermetic GTK harness.
  2. Test denied startup, broker-unavailable startup, no-child messaging,
     account switching, loading masks, status retries, unavailable status, daily
     presets, custom limits, enable and disable, app search and filters, precise
     and pattern rule editing, auto-save order, save rollback, and revocation
     confirmation.
  3. Prove that controls which conflict with a pending load or save are disabled.
  4. Prove that no Parent surface can grant additional time.
  5. Assert visible text and accessibility state rather than internal widget
     field names.
  6. Update Parent requirement mappings and keep source-contract tests only as
     secondary guards.
- Verification:
  - Run the Parent UI tests three consecutive times.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: every Parent component requirement has a local behavioral
  test or an explicit later E2E mapping.

