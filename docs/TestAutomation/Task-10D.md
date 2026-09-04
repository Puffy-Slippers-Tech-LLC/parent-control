### Task 10D — Verify reload, preserve artifacts, and finish integration

- Complexity: medium-high. The runtime foundation exists, but reload generation,
  artifact durability, and traceability must be made deterministic together.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: complete the nested-Shell component suite with controlled source
  reload, reviewable evidence, stable command integration, and truthful
  requirement mapping.
- Work:
  1. Add a reload test that changes only a controlled temporary extension copy.
     Detect the source change, restart or reload through Task 10A's supported
     preview lifecycle, wait for a new observable generation, and prove the
     extension returns active with the updated observable marker. Assert that the
     repository source tree and developer extension installation were untouched.
  2. Capture each automated preview's complete nested Shell log and a PNG of the
     nested Shell through GNOME Shell's published Screenshot D-Bus interface.
     Place stable success artifacts under the ignored `artifacts/` tree and
     preserve per-test diagnostics on failure. Never capture the host desktop.
  3. Apply the attributable warning, critical, and JavaScript-error scan to
     initial startup, interaction, reload, and shutdown. Keep messages redacted
     and include lifecycle stage and error category without user or host data.
  4. Finalize `make check-child-shell` and `make check-component` integration,
     development dependency setup, pinned tool documentation, and README command
     and artifact documentation.
  5. Update only the child requirement records that this component environment
     executes truthfully. Nested preview evidence may strengthen
     `ONPC-COMP-CHILD-003` and `ONPC-COMP-CHILD-004`; requirements whose declared
     layer is `system` or `e2e` must remain planned until those later tasks run.
  6. Keep Task 10A's interactive preview behavior and all Task 10B/10C tests
     passing.
- Verification:
  - Run the complete automated nested-Shell preview suite in three consecutive
    fresh processes through `tools/run-ui-tests --timeout <duration> ...` and
    confirm that each run produced its required log and PNG artifacts.
  - Run `python3 tools/verify_test_traceability.py --mode stage`.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: reload is proven from an isolated temporary copy; startup,
  interaction, reload, and shutdown produce reviewable logs and screenshots; the
  stable component command passes three consecutive times; and traceability
  claims no stronger layer than the test executes.
