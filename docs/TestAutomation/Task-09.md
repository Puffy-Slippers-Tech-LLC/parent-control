### Task 09 — Add executable unit tests for child-extension JavaScript

- Complexity: medium. Testable logic must be separated from Shell-bound actors
  without changing runtime behavior.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Objective: move beyond JavaScript syntax and source-string checks.
- Work:
  1. Extract pure formatting, countdown cadence, estimate preservation,
     validation, retry classification, and display-state calculations into
     side-effect-free ECMAScript modules.
  2. Test platform-neutral modules with Node's maintained built-in test runner.
  3. Test GJS-specific Gio and GLib adapters with the maintained public
     Jasmine-for-GJS approach or a small GJS runner using public APIs. Do not use
     deprecated `jsUnit`.
  4. Cover final-minute seconds, zero, values above one day, transient timer
     failure, busy retries, refresh-after-overlay, and duplicate-overlay guards.
  5. Enable GJS coverage output for the extracted modules and add it to local
     component artifacts.
  6. Update child component requirement mappings.
- Verification:
  - Run Node and GJS tests separately and through `make check-component`.
  - Run `make check` and `git diff --check`.
- Completion criteria: child logic executes in tests, Shell-only code is thin,
  and no test imports private GNOME Shell resources.

