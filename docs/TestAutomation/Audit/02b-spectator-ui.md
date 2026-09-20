# 02b — Migrate the owned spectator UI consumer

**Recommended model: GPT-6 Astra. Effort: high.** This newly inventoried owned
surface mixes UI acceptance with mechanical rendering and transport checks.

**Prerequisite:** [02a](02a-owned-identity-closure.md) and
[shared preflight](README.md). **Status:** Not started.
**Next:** [03](03-authentication-surfaces.md), after closing parent task 02.

## Frozen remaining scope

Resolve **O4** in [task 02's inventory](02-owned-ui-and-inventory.md). Read
`tools/e2e_watch_viewer.py`, `tests/ui/e2e_watch_window_probe.py`,
`tests/ui/test_e2e_watch.py`, `tools/regression_ui.py`, and their owned process,
watch protocol and scheduler unit tests. Do not run the live-E2E variants or
inspect/start a VM. Their callable paths still need migration or safe refusal.

1. Publish stable public IDs for the spectator's window and customer-visible
   progress, status, output and close controls. Use the shared scoped adapter
   and recorded preview process ownership for normal UI action/readback. The
   current probe establishes readiness from `app.window`, reads widgets
   directly and closes through `app.window.close()`; replace that functional
   path with public ID-based observations and semantic input.
2. Preserve waiting, live frames, disconnect/reconnect, stopped-window retention,
   resumed same-window behavior, stage/operation timing and bounded output.
   Cosmetic title/layout/color assertions cannot gate functional acceptance.
   Retain useful frame-format, cursor, color-encoding, read-only-terminal and
   resize-isolation obligations as explicitly mechanical unit/component checks
   where appropriate. Do not delete or weaken checks merely to obtain a pass;
   moving checks requires equivalent evidence and suite-inventory coverage.
3. The probe's direct layout line counts, ellipsis, title, texture dimensions and
   default-window-size calls need individual disposition. Normal rendering and
   synthetic frame production are not target selectors; separate those from UI
   readiness/acceptance rather than banning ordinary rendering code. No
   coordinates, image matching or geometry may identify or activate a target.
4. Preserve caller-owned process cleanup and passive spectator behavior. Do not
   add control of the watched VM, install the product, or broaden grants.

## Verification and completion

Run changed watcher/protocol/scheduler and cleanup-safety unit files with literal
quoted paths through `tools/run-unit-tests`. Run only the synthetic non-live
spectator host UI case through `tools/run-ui-tests` after its automatic safety
gate. If a behavioral mismatch appears, preserve evidence and apply the shared
regression rule; do not redefine expected behavior.

Record retained live-variant obligations without claiming their execution. Add
the spectator file to task 08's final host selection with an explicit non-live
scope; update its eleven-file wording/count consistently. Update O4 and the
frozen remaining counts in task 02. Close parent task 02 only when O1–O4 and all
owned verification requirements are resolved; otherwise record the concrete
remaining blocker. Advance the README pointer to 03 and stop. Apply shared
diff/link/index-preservation close checks.
