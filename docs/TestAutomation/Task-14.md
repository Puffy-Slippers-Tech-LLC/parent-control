### Task 14 — Test installed broker identity and authorization boundaries

- Depends on: Task 13B.
- Complexity: very high. These are security boundaries that cannot be proven by
  same-UID mocks.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Model rationale: keep the complete method/role matrix with stale-identity and
  real-caller checks; separating inexpensive cells would fragment the security
  argument and repeat sensitive fixture setup.
- Objective: prove real caller identity and role enforcement on the installed
  system bus.
- Work:
  1. In a disposable guest only, expand deterministic accounts to two eligible
     children, two eligible administrators, one locked administrator, the kiosk
     user, an unrelated standard user, and noninteractive/system fixtures.
  2. Invoke every broker method from real processes running under each relevant
     UID and record the allowed or denied D-Bus result.
  3. Verify account discovery after installation, sorting, exclusions, icon
     handling, locked-approver exclusion, and child-owned target derivation.
  4. Verify that front ends cannot read private preference records and cannot
     claim another component in `LogEvent`.
  5. Verify stale-account, changed-role, caller-disconnect, and selected-approver
     revalidation with actual system-bus names.
  6. Exercise interactive Polkit selection later through E2E; this task proves
     all non-graphical policy and broker boundaries.
  7. Update broker and account requirement mappings.
- Verification:
  - Run caller-process cleanup-safety regressions in isolation before integrated
    caller-disconnect tests.
  - Run the authorization matrix in a fresh installed overlay.
  - Inspect redacted broker logs and D-Bus results.
  - Run `make check-system VM_IMAGE=<verified-baseline>`, `make check`, and
    `git diff --check`.
- Completion criteria: every method/role cell in `System-Design.md` has an
  installed-system assertion and cross-account attempts fail closed.
