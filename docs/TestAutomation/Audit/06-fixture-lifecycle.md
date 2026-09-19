# 06 — Review GUI fixture lifecycle and runtime packaging

**Recommended model: GPT-6 Astra. Effort: high.** Native process lifetime, signal
ownership and packaged runtime correctness need concurrency/ownership review.

**Prerequisite:** [02](02-owned-ui-and-inventory.md); execute after
[05](05-legacy-input-routes.md) for sequential sessions. Apply [shared preflight](README.md).
**Status:** Not started. **Next:** [07](07-focused-unit-verification.md).

## Scope and work

Read [native owner](../../../tests/fixtures/onpc_test_application.c),
[GUI application](../../../tests/fixtures/gui_application.py),
[runtime builder](../../../tests/fixtures/gui_runtime.py),
[application builder](../../../tests/fixtures/build_test_applications.py),
[fixture adapter](../../../tests/e2e/fixture_ui.py), and
[GUI tests](../../../tests/ui/test_fixture_gui.py). Review system-enforcement
consumers and `setup.sh` prerequisite changes only as they affect these fixtures.

1. Verify native executable identity remains visible while its child GUI runs;
   owned fork/wait, exit propagation, termination and Linux parent-death handling
   cover failure/race paths without signaling unrelated or reused identities.
   Check independent primary/secondary instances and cleanup after failed launch.
2. Preserve the separately built `mechanical/onpc-test-application` one-shot
   readiness/exit contract and its system test doubles. `--stay-alive` is not GUI
   acceptance. Do not replace real GUI work with a marker/process-only check.
3. Review runtime dependency closure, offline Python/GTK resources, packaging
   paths and deterministic repeat-build manifests. Native/game, isolated user
   Flatpak and strict core26 Snap payload identities must agree with adapters.
   Missing build/runtime prerequisites fail clearly and belong exclusively in
   maintained setup modes; no installation or fallback copying in test launch.
4. Preserve public instance/control IDs, identified Edit draft focus and normal
   typing, submit/readback, deterministic move results and secondary closure.
   Keep `installed_qualified=false`; unpacked Snap is not snapd/confinement proof,
   and fixture GUI success is not installed App Limits enforcement.

## Verification and completion

Run focused mechanical/ownership units through the launcher:

```sh
tools/run-unit-tests -q 'tests/unit/test_fixture_gui_adapter.py' 'tests/unit/test_test_applications.py' 'tests/unit/test_system_enforcement.py' 'tests/unit/test_build_test_artifacts.py' 'tests/unit/test_fixture_cleanup_safety.py'
```

Include setup-entrypoint units if prerequisite declarations change. Ensure the
existing mechanical-compatibility and deterministic repeat-build checks actually
run. Add targeted regressions only for material uncovered lifecycle/packaging
risks. Do not infer reproducibility from source inspection or a single build.

If this task changes fixture runtime/UI code, run
`tools/run-ui-tests --timeout 1200s -q 'tests/ui/test_fixture_gui.py'` after its
cleanup gate. Otherwise retain the handoff's fixture evidence provisionally;
task 08 will rerun it on final code. Complete with ownership findings resolved,
mechanical compatibility checked and remaining installed qualification explicitly
pending. No package installation, snapd operation or host setup is part of this task.
