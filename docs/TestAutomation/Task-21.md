### Task 21 — Automate Parent App management scenarios

- Complexity: medium-high. The UI is semantic, but it drives several privileged
  transactions.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: execute the Parent component requirements as real user journeys.
- Work:
  1. Log in as an eligible administrator, launch Parent from the app grid, and
     verify the correct children and no ineligible accounts are listed.
  2. Create a new child after installation and verify dynamic discovery.
  3. Select each child and verify independent preferences, status, catalog, and
     loading behavior.
  4. Enable and disable screen time, exercise zero through 1440-minute boundaries,
     change an enabled allowance, and verify extension and live policy results.
  5. Search and filter the selected child's applications, set all three rules,
     select precise and version-tolerant matching, and verify immediate ordered
     auto-save.
  6. Exercise a failed save and revocation confirmation and verify rollback copy
     and restored controls.
  7. Attempt launch as a standard user and attempt broker management methods
     directly as that user; verify both visible and D-Bus denial.
  8. Update Parent and account requirement mappings.
- Verification:
  - Run the Parent scenario from a fresh installed overlay.
  - Verify UI screenshots against broker, AccountsService, fapolicyd, and private
    record evidence collected through root serial assertions.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: Parent management works for an administrator and remains
  inaccessible to standard users through both launcher and direct API paths.

