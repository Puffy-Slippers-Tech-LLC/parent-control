# Task 20 — capture identity refusal reproduced and corrected locally

## Result and qualification limit

Authentication attempt 7 retained `vt6-auth:capture-changed-refused` at
`vt6-password-screen`. Initial capture freshness, owner, link, size, inode and
timestamp checks, the reference digest and exact pixel comparison all passed.
The post-read whole-`stat_result` comparison failed before recipient recheck or
password authorization. No authenticated shell or command completion is proved.

Local reproduction then identified a defect in that comparison: reading the
fresh PNG advances access time. Whole-stat tuple equality uses integer-second
timestamps, so the original fast tests and a 50-millisecond delay passed. A
1.05-second delayed first read of an installed-tinycv PNG in `/tmp` fails the
original comparison, with the added field discriminator identifying only
`capture-descriptor-atime_ns`. Comparing nanosecond fields also exposed this
read-time change in fast tests. The root filesystem's `noatime` flag does not
apply to the separately mounted `/tmp` tmpfs; the initial contrary inference
was withdrawn. Installed `basetest::_result_add_screenshot` uses
`tinycv::Image::write_with_thumbnail`; local creation confirms a fresh, singly
linked PNG, without a deduplication workaround.

`Authentication._pixels` now reuses `provenance.identity`, with explicit UID/GID
stability checks. It compares descriptor and path identity, mode, links, size
and nanosecond write/change timestamps. Access time does not represent content
or identity changes. All initial freshness checks, exact pixels, directory
identity, worker/source/boot/recipient checks and one-use authorization remain.
Safe fixed predicate codes are checkpointed by `Smoke`/`Qualification` before
the generic worker wrapper; changed stable metadata identifies its field and
descriptor/path boundary without exporting values, paths or exception text.

The **correction is locally tested only**. Attempt 7 ran the diagnostic change
with the original comparison. It did not retain individual stat values, so
atime attribution for that historical run is supported by the local reproduction,
not a recovered live field measurement. The corrected guarded authentication
attempt is still required. No unchanged diagnostic-only rerun is warranted.

## Retained live evidence

- Route: `tools/run-tests integration check_graphical_vt6_authentication`;
  exit **1**, duration 1,179.852 seconds.
- Result: `/tmp/onpc-graphical-smoke-btz4o4l2/result.json`.
- Qualification checkpoints: `/tmp/onpc-e2e-evidence-r5h4c7cy`.
- Worker: `/tmp/onpc-e2e-evidence-02k6b_va/worker-result.json`.
- Source SHA-256: `29a7366a78c36390cf1199ccc0f1846fbfae8d1023261857ecac371605d4bd7d`.
- Baseline SHA-256: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.

Preparation/readback again passed, with effective timeout 600 and matching
recipient diagnostics across 66.710 seconds of password-stage baseline
revalidation. Login-ready and password-ready receipts are durable. Infrastructure
failed; product and collection outcomes remain `not-run`. Normal worker shutdown
is unqualified. Baseline restoration, lease phase `complete`, final source/host
preservation, worker stop, callback closure and display closure all passed.

## Verification and cleanup

- Final focused controller/pixel/cleanup selection: **222 passed** using
  `tools/run-unit-tests tests/unit/test_e2e_vt6_controller.py tests/unit/test_e2e_vt6_pixels.py tests/unit/test_graphical_smoke_cleanup_safety.py -q --tb=short`.
- Regressions: `test_controller_accepts_fresh_installed_tinycv_capture` covers
  the real delayed PNG read; `test_changed_capture_retains_exact_field_without_values_or_authorization`
  covers descriptor/path identity, ownership, link, size and nanosecond timestamp
  changes; `test_vt6_refusal_checkpoint_retains_only_fixed_codes_without_authorization`
  and the capture-refusal publication case cover durable, private refusal.
- Final `make check`: **7,306 unit/contracts and 58 private-D-Bus tests passed**,
  plus common checks. The earlier pre-attempt common check passed 7,270/58.
- Isolated cleanup prerequisites and the dispatcher's repeat each passed
  **667 tests and 3 subtests** before attempt 7. These predate the final local
  metadata correction; run isolated safety again before the next VM attempt.
- Intermediate failures: one new test initially expected the wrong exception
  class (corrected); nanosecond diagnostic instrumentation produced nine local
  failures exposing atime changes; the delayed original-comparison reproduction
  then failed as expected. All final affected checks pass.
- All commands exited. Test-owned temporary directories/PNGs were removed by
  their context managers; no live screenshot was exported. Private originals
  remain retained. No approval/Polkit denial or owned recovery obligation remains.
- Documentation checks: five owning/handoff/evidence documents, 281 local links,
  no missing targets; focused `git diff --check` passed.

The slice exceeded its review budget to finish the one live attempt, guarded
cleanup and the resulting local correction/checks. No second live run started.
Task 20 remains earliest ready, no bypass; 15A remains preserved. All-task VM
clearance persists. Authentication history is seven failed attempts; full Task
20, both E2E-028 faults, sudo/notice pixels and complete install/reboot/startup
remain unaccepted. Reuse the [owning contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [active handoff](../Task-20.md#task-20-continuation--2026-09-08).

Actual settings: `gpt-6-astra` / `high`, Standard. Next: `gpt-5.6-sol` / `high`,
Standard, for the settled correction's guarded qualification using the existing
tested authorization/cleanup chain and retained refusal diagnostics.
