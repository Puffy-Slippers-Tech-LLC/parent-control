# Task 19A live finalization qualification — 2026-09-07

This slice completed the previous handoff's live lease/provenance/checkpoint
boundary. It does not complete 19A or execute a registered customer scenario.
All 156 inventory variants remain pending; dispatch remains closed.

## Implemented and verified

- `Lease.__exit__` makes one cleanup attempt, calls a trusted finalizer while
  held even after cleanup failure, then releases. Body, cleanup, finalizer and
  release failures retain their original precedence. No second restore occurs.
- The credential-free `Qualification` controller captures `VerifiedInputs`
  after preparation, rechecks before startup and forwards its source map to the
  existing worker. Root Git reads use invocation-scoped trust for the checkout.
- `recording.save_checkpoint` is shared with `ScenarioRecorder`. The smoke
  records real stage starts and corroborated observations before acknowledging
  the next guest action, worker failures, and before/after outer cleanup.
- Finalization checks host/source/baseline preservation, private report copies
  and provenance before lease release. Raw screenshots/logs stay private;
  checkpoints include safe screenshot dimensions/digests only.

There are 27 new regression cases: 16 lifecycle failure combinations, nine
controller outcomes, one stage-checkpoint/acknowledgement refusal, and one
invocation-scoped Git trust check. The seven-module focused run passed 277 tests.
`make check` passed 2,073 unit/contracts and 17 private-D-Bus components before
the smoke; the final code was checked again after the correction below.

```sh
tools/run-unit-tests tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_system_runner.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py tests/unit/test_e2e_recording_cleanup_safety.py tests/unit/test_e2e_provenance.py tests/unit/test_e2e_worker_cleanup_safety.py -q
make check
tools/run-tests integration check_graphical_smoke
```

The dispatcher passed 276 isolated safety tests and three subtests before VM
use. One live attempt ran; it exited 0 with infrastructure, collection and
cleanup passed, product not-run, and lease phase complete. No expensive failed
attempt or diagnostic rerun occurred. The owned worker and callback closed;
the existing VM was restored and left off, its lease released, and the
controller connection closed. No setup, permission or baseline changes occurred.

## Retained evidence

- Outer report: `/tmp/onpc-graphical-smoke-rbx8bxzj/result.json`.
- Ordered private checkpoints: `/tmp/onpc-e2e-evidence-sjikn4xx/event-000001.json`
  through `event-000012.json`.
- Worker diagnostics: `/tmp/onpc-e2e-evidence-67ukvd6s/worker-result.json`.
- Original command handle: 38410, reconciled to exit 0.

Read private files using `pkexec /usr/local/libexec/onpc-test-artifacts`.
All 12 retained checkpoints were read and their order/timing verified:
attempt-started, inputs-captured, four stage-started/stage-observed pairs,
before-cleanup, after-cleanup. The stages are ready, GDM, selected and dismissed.
The last checkpoint records complete lease and true host/source preservation.
The final controller log establishes that finalization returned while held;
`result.json` accounts for release and connection closure afterward. This is
diagnostic observation evidence, not a new screen-matching qualification or
reviewed screenshot export.

| Measured component | Seconds |
| --- | ---: |
| Total live controller | 569.891 |
| Preparation, including entry proof and input capture | 250.326 |
| Test, including pre-start provenance | 107.364 |
| Worker portion of test | 36.216 |
| Cleanup measurement | 71.773 |
| Remaining elapsed time, predominantly final held-lease rechecks | about 140.4 |

The final callback is not yet attributed to a separate ledger timing bucket;
the last row is subtraction, not a directly measured phase. Repeated retained
baseline proof checks dominate elapsed time. Reuse this successful boundary;
do not repeat it unchanged simply because another session begins. Preserve
required provenance checks when adding timing or addressing this measured cost.

## Input identities and final local correction

The passing live attempt recorded:

| Input | SHA-256 |
| --- | --- |
| Source aggregate | `d9a925d3c11e59ee0bf480681fa52fc40fb6b494374e57229be270ae519ee4eb` |
| Inventory | `c2d2bac4bea5da49be82f41a7de3e8f9e2780fbbee9c2bad09450dda647e35d4` |
| Baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Worker distribution | `d7ccdaf1c9eacfd9fedef51ee4f4e939e8b959b6c2734d33e11319d7eba227c2` |
| Live smoke controller | `67357b92a42ec32e0577b3d71adf06c24a7aba52f4571510ea5b04a1e58de7aa` |
| Lease module | `0cdcfe2e426500f720d6e0d712968c3f68053bbc63ba7e007c7033f58dc59991` |
| Provenance module | `3c520ace44d4ae344c31671e19f594c1af054965c6157172dacb1fda1bdc9ea5` |
| Shared recorder | `c1dd13cd76ff3ead8b93e1c2bbdb62026e9f4360d0ded083e3250a54bd312121` |

Package identity is explicitly null: this is a product-free qualification.

After the live run, a focused correction revoked `preservation.source` if the
last recheck fails, and avoids a later successful check overwriting an earlier
refusal flag. Final smoke digest is
`8e2d3f598c8d5f0a934433466dfbeed912492dc112855ca2008e3e5f55e02fdf`.
This failure-reporting correction passed all 24 smoke safety tests locally;
it was not exercised in the VM. The passing live success path is unchanged.
An initial missing mock run ID and an intermediate refusal-flag assertion
failed locally and were corrected; no failure remains hidden by the live pass.
Final `make check` handle 46929 exited 0: 2,073 unit/contracts in 30.92 seconds
and 17 components in 0.38 seconds, plus syntax and stage traceability checks.
The earlier intermediate make handle 16774 failed on that refusal-flag assertion;
it finished before the final corrected-code run. `git diff --check` also passed.

## Next boundary

Wire verified asset staging/transfer into the guarded E2E transport, retaining
the same lifecycle and diagnostic distinction. Reuse `stage_assets`, asset
verification, `VerifiedInputs`, and existing bootstrap/transport ownership.
Keep provisioning before the journey and observation read-only; prove corrupted
or stale transfers refuse, then one valid transfer on the existing VM.
Authenticated secret/capture transport, harmless console execution and complete
19A acceptance remain afterward. Do not enable E2E-001 or duplicate its inventory
to avoid the 19B matching/console work.

Estimated remaining 19A effort: 3–4 bounded sessions, roughly 1.5–3 hours,
subject to secret/console transport findings. This session removed the live
lifecycle/provenance boundary; the next session must implement asset transfer,
not repeat that solved investigation. Implementation and verification took
about 25 minutes including the 9.5-minute smoke; no usage telemetry was exposed.
