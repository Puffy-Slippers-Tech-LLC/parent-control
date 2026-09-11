# Task 20 — worker shutdown passes; final source preservation refuses

## Result and scope

Authenticated attempt 11 completes all five VT6 receipts, the nonsecret command
round trip and normal worker shutdown. Backend exit is 0, no fatal artifact is
present, `shutdown_verified=true`, and worker/callback cleanup passes. The outer
attempt still **fails** `smoke:final-provenance-failed` with retained
`provenance:source-changed`. Baseline restoration and host preservation pass.
This proves the worker boundary within a failed attempt, not complete authenticated
qualification, E2E-002 or Task 20 acceptance. All eleven outer attempts remain failed.

Reuse the [worker contract](../../../tests/e2e/README.md#shared-guarded-worker),
[provenance contract](../../../tests/e2e/README.md#controller-owned-provenance),
[VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal) and
[reuse map](../Reuse-Map.md#installation-helper-and-open-limits).

## Correction and local verification

`run_backend` selects 1800 seconds for VT6 authentication: 1200 for the ten
mandatory baseline rechecks (802.363 seconds in attempt 10), plus the existing
600-second smoke allowance including shutdown/exit. Other selections retain
600/960 seconds. `run_distribution` accepts only a finite positive numeric budget
at most 1800 seconds. It now checks the deadline after synchronous
`CallbackServer.serve_once`, before dispatching another observer. An owned stop
finishes; expiration does not renew the budget or authorize another step. No
provenance, recipient, lease, module or shutdown validation was removed.

`test_delayed_shutdown_callback_keeps_finite_deadline_and_requires_off_observation`
in `tests/unit/test_e2e_worker_cleanup_safety.py` models the delayed shutdown:
the old 960-second budget refuses, 1800 permits off observation and validated
exit, and expiration of 1800 still refuses and closes both owners. Invalid
budgets refuse before lease/resource construction. The existing
`test_vt6_worker_uses_existing_finite_extended_budget` owns selection coverage.

The first local run exposed both intended failures and a newly added test's
unserializable mock. Correcting the mock isolated three intended failures:
post-deadline observer dispatch, rejection of 1800, and old VT6 selection.
After the runtime correction, 200 focused cases passed. The first `make check`
then failed one existing budget expectation (7340 passed); its 960 expectation
was corrected and the duplicate new selection test removed. Final `make check`
passed **7336 unit/contracts and 58 components**, plus traceability and common
syntax/source checks. Isolated safety and the dispatcher's separate safety run
each passed **694 tests and 3 subtests**. No test failure was treated as a pass.

## Retained live evidence

Route: `tools/run-tests integration check_graphical_vt6_authentication`.
One live attempt this slice; command handle `38348`, terminal exit **1**.
No package build was needed for this product-free qualification.

| Evidence | Attempt 11 |
| --- | --- |
| Outer result | `/tmp/onpc-graphical-smoke-ab0z5eps/result.json` |
| Qualification checkpoints | `/tmp/onpc-e2e-evidence-q37x8rcd/` |
| Worker result | `/tmp/onpc-e2e-evidence-y6a8_bih/worker-result.json` |
| Source SHA-256 | `322f21cb00e38aefe36657fb23ea3c9f922d7fbc5d139fcaa6b70a4df5b1977e` |
| Baseline SHA-256 | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Distribution SHA-256 | `89ec8a538814c67e0245def05f5f3feeaf79264350a2ad92d15a4f30e142fb11` |
| Total / worker seconds | 1445.427 / 926.879 |
| Preparation / test / cleanup seconds | 383.064 / 993.928 / 68.298 |
| Ten baseline / source rechecks, seconds | 690.364 / 0.961 |

The faster baseline reads put this worker duration below the old budget too;
the live run proves normal shutdown with the corrected selection, while the
delayed-callback regression establishes the larger-budget counterexample.

## Final source refusal and cleanup

Initial status contained no `docs/VersionHistory.md`. Final status shows this new
untracked, nonignored, empty regular file, created at **15:40:16.142 UTC**. The
authenticated command receipt is dated **15:37:12.480 UTC** and the outer result
**15:41:22.724 UTC**. This session made no checkout writes during the attempt.
The addition is sufficient to change `source_paths`/`snapshot`; existing
`test_new_source_file_is_detected` covers that refusal. The full differing
snapshot was not exported, so this does not establish the sole changed field or
explain historical source failures. Preserve the unrelated file; do not delete,
ignore or exclude it to make the old attempt pass.

Lease phase is `complete`; baseline restoration, host preservation and cleanup
pass, source preservation is false. Infrastructure fails; product/collection are
`not-run`. All commands exited, workers/callbacks/display closed, and no recovery,
temporary screenshot export or approval/Polkit denial remains. Raw authentication
artifacts remain private. Only handoff/contract documentation changed afterward.
Final documentation verification checked 314 local links across five documents
with no missing targets; scoped whitespace checks passed and Continuation has
exactly one supported settings line.

## Next bounded result

Task 20 remains earliest ready, with no bypass. Capture fresh inputs including
the unrelated addition, run isolated safety, and qualify the same corrected
route through final source/host preservation. Do not repeat prompt collection or
redesign shutdown. A further source refusal requires evidence of its current
change before another retry; do not weaken the latch. Sudo/notice pixels and the
complete installation/reboot/startup variants remain unaccepted.

All-task VM clearance persists; this new source refusal does not reinstate the
historical writer hold or require another coordination confirmation. The slice
used `gpt-6-astra` / `high`, Standard. Its extended duration completed common
checks, one guarded attempt and cleanup. Next: `gpt-5.6-sol` / `high`, Standard;
the worker boundary now passes and the next result uses unchanged, guarded
helpers with fresh source inputs and explicit acceptance checks.
