# Refactor E2E case 1 without changing its behavior

This is an implementation session. Code changes needed for this refactor are
authorized. Refactor **case ID 1 / E2E-001/gdm-observation** into the building
blocks in [E2E-Building-Blocks.md](E2E-Building-Blocks.md), starting with its
[stage contract](E2E-Building-Blocks.md#case-1-stage-contract). Case 1 already
works; preserve its complete passing behavior and all existing safety checks.
The other ready cases **3, 4, 5 and 151** must continue to pass.

Read [AGENTS.md](../../AGENTS.md), [System-Design.md](../System-Design.md), the
building-block guide and the current case-1 declaration in
[scenarios.json](../../tests/e2e/scenarios.json). Inspect the working tree and
preserve all existing unrelated edits. Use the approved launchers and existing
guarded VM; do not replace its baseline or broaden permissions.

1. Establish a passing baseline for case 1 **before editing implementation**.
   Run the required isolated cleanup-safety prerequisites, build verified
   artifacts with `tools/run-tests artifacts build`, then run
   `tools/run-tests e2e --id '1' --artifacts '<actual-builder-output-directory>'`.
   Retain the full result and cleanup evidence. If the baseline cannot pass,
   report the concrete prerequisite/failure and do not describe a refactor as
   preserving a pass that was not observed.

2. Read the actual implementation before extracting anything:
   [controller_qualification.py](../../tests/e2e/controller_qualification.py),
   [check_graphical_smoke.py](../../tests/integration/check_graphical_smoke.py),
   [smoke.pm](../../tests/integration/graphical_smoke/tests/smoke.pm),
   [onpc_gdm.pm](../../tests/integration/graphical_smoke/lib/onpc_gdm.pm),
   [onpc_serial.pm](../../tests/integration/graphical_smoke/lib/onpc_serial.pm),
   [accessible_ui.py](../../tests/e2e/accessible_ui.py) and
   [ui_observations.py](../../tests/e2e/ui_observations.py). Reuse their current
   credential, asset-transfer, observation, recorder and worker services.

3. Implement only case 1's dependency set in catalogue order. Its recipe is
   **FLOW00**: HAR01(initial `sut`) → GDM02(parent, prompt) → GDM09 → HAR05 →
   HAR06 → HAR07 → HAR08; after normal worker finish/shutdown, HAR10 → HAR09.
   Extract UI11/UI13/UI14 and GDM01/02/09 only as needed, reuse GDM08 and ready
   primitives, and split serial login, command, logout and graphical return
   into the documented smaller operations. Extract only UI19's existing serial
   binding. Leave the serial one-attempt latch and capture seal intact.
   A wrapper around the old entire scenario is not the requested decomposition:
   composite operations must call their declared reusable leaves/composites,
   with explicit inputs and observations, without duplicating scenario logic.

4. Preserve the exact ordered stages:
   `ready`, `gdm`, `focused`, `selected`, `dismissed`, `serial-password`,
   `serial-authenticated`, `serial-command`, `serial-logout`, `gdm-return`.
   Keep phase transitions, durable observation-before-reply, fresh UI evidence,
   unchanged boot, asset receipt and all three assertion IDs:
   `visible-result`, `backend-result`, `other-user-result`. There must be exactly
   one successful logout before fresh graphical return. Preserve the actual
   command-output check; command echo and worker exit zero cannot prove success.

5. Keep this a behavior-preserving extraction. Type no graphical password.
   Preserve serial identity/no-echo proof, fixed secret API options, prompt
   bounds and line endings, deadlines, no input replay, private evidence,
   terminal failure latches, owned shutdown and baseline/host restoration.
   Keep existing serial installation/refusal callers compatible. Do not add
   repeated authentication, product probes, arbitrary commands/regexes, a new
   runner, new wire protocol, image-based customer acceptance or installed
   product setup for this product-free harness. Do not migrate the other ready
   workers or implement unrelated pending blocks in this slice.

6. Run meaningful affected regressions through `tools/run-unit-tests`, including
   the real Perl GDM/serial helpers, public-UI adapter, graphical smoke and
   controller reconciliation/cleanup tests. In particular retain the coverage in
   [test_e2e_gdm_helper.py](../../tests/unit/test_e2e_gdm_helper.py),
   [test_e2e_serial_helper.py](../../tests/unit/test_e2e_serial_helper.py),
   [test_graphical_smoke.py](../../tests/unit/test_graphical_smoke.py) and
   [test_e2e_controller_qualification_cleanup_safety.py](../../tests/unit/test_e2e_controller_qualification_cleanup_safety.py).
   Qualify independently supplied block entry states and refusal of missing,
   stale, duplicate or reordered evidence. Failed observation/storage/ownership
   must prevent the next input; wrong recipient, changed boot, missing command
   output, early return and cleanup failure must still refuse. Run required
   cleanup-safety checks in isolation before host-integrated validation.

7. Record actual callable names and qualification scope in the catalogue; mark
   only qualified bindings `ready` and update its counts. Preserve all five
   scenario IDs, ready statuses and assertions. After finishing **all** source,
   test and documentation edits, build fresh artifacts. On that unchanged
   checkout run `tools/run-tests e2e --id '1,3,4,5,151' --artifacts
   '<actual-builder-output-directory>'`. Require complete passes, including
   terminal collection and cleanup. If an implementation fix is needed, rebuild
   and rerun affected cases on final inputs; never mask failure with a skip,
   relaxed assertion or stale artifact.

Finish with the block/callable mapping, baseline and final artifact references,
regression results, all five final scenario outcomes and cleanup results.
Do not claim success from unit tests, partial stages or inventory readiness.
If an external prerequisite prevents completion, report it precisely and retain
the failed evidence. Use existing runner artifacts and the maintained guide;
do not create a separate incident report.
