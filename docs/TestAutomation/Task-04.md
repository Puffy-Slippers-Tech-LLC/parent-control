### Task 04 — Add broker property and state-machine testing

- Complexity: medium-high. The broker's rollback and multi-state invariants need
  model-based reasoning.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: systematically exercise combinations that example-based unit tests
  cannot cover economically.
- Work:
  1. Add Hypothesis tests for remaining-time arithmetic, duration validation,
     usage-interval merging, local-midnight calculations, preference
     normalization, pattern validation, and migration inputs.
  2. Add a rule-based state machine for two children, two administrators, the
     kiosk caller, and an unrelated user.
  3. Model enable, disable, daily-limit change, policy change, request approval,
     denial, cancellation, revocation, account-role change, requester
     disconnect, and adapter failure at every transaction boundary.
  4. Assert after every action that hard blocks remain hard, child state is
     isolated, successful grants are accumulated correctly, unsuccessful
     operations do not relax state, and rollback matches the defined recovery
     state.
  5. Use the broker's injected clocks and adapter protocols. Do not add a
     production test mode.
  6. Update requirement mappings for the properties now exercised.
- Verification:
  - Run the new tests with a committed deterministic Hypothesis profile.
  - Re-run saved failing examples.
  - Run `make check` and `git diff --check`.
- Completion criteria: important broker invariants are checked across generated
  sequences and all failures shrink to reproducible examples.

