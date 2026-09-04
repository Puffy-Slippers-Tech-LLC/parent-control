# Task 19 — os-autoinst end-to-end test distribution

Execute 19A and 19B separately. Reuse Task 13B's baseline validation and artifact
contract; os-autoinst owns its own QEMU guest through its supported backend.

## Task 19A

- Title: Add the guarded os-autoinst worker and console transport.
- Depends on: Task 18B.
- Complexity: very high. Guest ownership, storage, secrets, console transport,
  and cleanup must be correct before any graphical scenario can be trusted.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Add `tests/e2e` with `main.pm`, a small distribution class, public console
     definitions, configuration templates, guest assertion scripts, and launcher.
  2. Pin Ubuntu 26.04's maintained os-autoinst/QEMU tooling through `setup.sh`
     and the test-tool list. Use the stable public Perl API and QEMU backend;
     never attach to the protected domain or use svirt's root-password workflow.
  3. Validate the Task 12 baseline and create a fresh backend-owned disposable
     overlay. Transfer digest-verified assets through supported channels without
     writable host shares. Add `make check-e2e VM_IMAGE=... SCENARIO=...`.
  4. Configure VNC graphics and virtio serial. Keep complex backend checks in
     versioned guest scripts/pytest; reserve graphical input for user actions.
  5. Pass credentials through os-autoinst secret variables and its secret-safe
     password API. Exclude them from screenshots, output, and vars artifacts.
  6. Implement bounded startup, shutdown, interruption, copied-artifact
     collection, and ownership-recorded cleanup. Add guard and cleanup-safety
     regressions, including identity replacement and rejected source disks.
  7. Prove one fresh guest boots, executes a harmless serial command, returns
     evidence, and shuts down. Document console, secret, asset, and helper
     contracts for 19B and later scenarios.
- Verification:
  - Run cleanup-safety regressions in isolation before starting a guest.
  - Run host-safe guard/refusal tests and the fresh-guest serial smoke.
  - Check baseline/source/host preservation and secret exclusion.
  - Run `make check` and `git diff --check`.
- Completion criteria: a guarded outside-guest runner provides working graphical
  and serial transports, owned cleanup, and redacted artifacts.

## Task 19B

- Title: Add stable screen matching and graphical smoke.
- Depends on: Task 19A.
- Complexity: medium. This uses the established runner and console contracts.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Add reusable login/GDM, console-switching, and screenshot helpers and initial
     needles. Match small stable regions/text, use explicit click points, and
     exclude clocks and animation instead of matching entire screens.
  2. Add the smoke scenario: boot a fresh product-free guest, recognize GDM,
     switch to serial, execute a harmless command, switch back, record a
     screenshot, and shut down.
  3. Document helper usage, match deadlines, failure artifacts, and exact smoke
     invocation for later scenario tasks.
- Verification:
  - Run cleanup-safety regressions in isolation, then run the graphical smoke
    three consecutive times on fresh overlays.
  - Review screenshots, video, serial output, secret exclusion, and cleanup.
  - Run `make check` and `git diff --check`.
- Completion criteria: stable public-API graphical/serial automation is ready
  for user journeys, without host-window automation or protected-domain access.
