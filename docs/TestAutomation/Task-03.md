### Task 03 — Establish test categories, static checks, and coverage reporting

- Complexity: low-medium. This is runner configuration and targeted cleanup.
- Recommended Codex model: `gpt-5.6-luna`
- Recommended reasoning effort: `medium`
- Objective: make test intent and blind spots visible without imposing a
  misleading repository-wide percentage target.
- Work:
  1. Register the markers `unit`, `contract`, `component`, `ui`, `system`, `e2e`,
     `slow`, and `guest_mutating` and apply them to current and new tests.
  2. Add coverage reporting for broker, parent, kiosk, common, and tools Python
     modules with branch coverage enabled.
  3. Record per-security-boundary coverage expectations for broker validation,
     transactions, preferences, migration, execution policy, and process
     ownership. Do not set a blanket 100-percent repository threshold.
  4. Add maintained ShellCheck and GNOME-compatible JavaScript lint entry points.
     Keep syntax checks in place.
  5. Reclassify source-text assertions as `contract`. Keep valuable architecture
     guards while ensuring traceability never counts them as runtime acceptance.
  6. Document commands for selection by marker and for producing local coverage
     artifacts.
- Verification:
  - Run each host-safe marker selection.
  - Generate HTML and XML coverage reports.
  - Run `make check` and `git diff --check`.
- Completion criteria: every current test has an understandable layer, coverage
  reports name the important unexecuted paths, and static tools use maintained
  configurations.

