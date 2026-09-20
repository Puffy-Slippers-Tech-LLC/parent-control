# 09 — Verify child code, static checks and fixture runtime

**Recommended model: GPT-5.6 Sol. Effort: high.** This is bounded category
verification after the code reviews and host UI qualification.

**Prerequisite:** [08](08-host-ui-verification.md) passed; apply
[shared preflight](README.md). **Status:** Complete; all required and applicable
checks passed.
**Next:** [10](10-reconcile-and-close.md).

## Required sequential checks

Run each command only after the preceding invocation has finished and its final
result has been collected:

```sh
tools/run-tests child-node
tools/run-tests static
```

Check that launcher output actually names the requested category. An invocation
may attach to an active/unread session before interpreting new arguments; after
collecting that result, reissue the intended explicit category if it never ran.
Never use a no-argument invocation to obtain status.

## Fixture-runtime decision

Inspect the maintained `fixture-runtime` selection and the fixture-runtime tests.
Run the category if its existing isolated Flatpak/mechanical coverage exercises
the changed fixture payload or lifecycle:

```sh
tools/run-tests fixture-runtime
```

This is the handoff's conditional coverage item. Record the named relevant
consumer and final result, or a concrete reason it supplies no additional
applicable check. If applicable but blocked by missing prerequisites, leave it
outstanding with the exact prerequisite; do not call it unnecessary. Confirm the
route stays isolated, preserves host configuration and runs its cleanup gate.
Do not install packages, use the real host Flatpak configuration, invoke snapd,
or expand to a host/VM aggregate to make it pass.

## Completion

Require final passing results for child-node and static, plus a recorded
fixture-runtime disposition. Preserve failure evidence and follow the shared
regression rules. Implementation fixes require affected task-07 checks and any
invalidated host UI evidence again; do not leave task 08 marked current on stale
code. Record commands, counts where available and runner artifact paths.

## Completion evidence

Final verification on 2026-09-20 used the required sequential commands on the
unchanged implementation:

- `tools/run-tests child-node` passed all **14 tests**. The launcher explicitly
  selected Child Node; its report is
  `docs/TestAutomation/Evidence/test-all-runs/20260920T211919Z-b777aa60/report.md`.
- `tools/run-tests static` passed the complete Static checks command. Its report
  is
  `docs/TestAutomation/Evidence/test-all-runs/20260920T211924Z-3516672a/report.md`.
- `tools/run-tests fixture-runtime` passed its mandatory cleanup gate with
  **1,476 tests and 3 subtests**, then passed the single isolated runtime case in
  **32.49s**. Its report is
  `docs/TestAutomation/Evidence/test-all-runs/20260920T211930Z-ff48aa31/report.md`.

Fixture runtime was applicable because task 06 changed the GUI fixture payload
and lifecycle. Its named consumer,
`tests/fixtures/test_runtime.py::test_flatpak_fixture_installs_launches_and_terminates_with_private_services`,
builds and verifies that payload, exercises its Flatpak launch and owned
termination against private services, and confirms the real user and system
Flatpak paths retain their prior existence state. No host configuration, snapd,
installed product, VM or customer E2E route was used or qualified.
