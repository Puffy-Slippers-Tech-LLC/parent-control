# Task 19A shared worker integration — 2026-09-07

This slice extracts the qualified worker loop into `tests/e2e/e2e_worker.py`
and makes the existing guarded graphical smoke call it. It adds verified
distribution staging, continuous lease revalidation, private pre-cleanup/final
reports and failure-safe resource shutdown. It does not complete 19A or make
any of the 156 pending scenario variants runnable.

## Retained real attempt

- Command: `tools/run-tests integration check_graphical_smoke`, outside the
  sandbox through the approved dispatcher. One expensive attempt, passed.
- Outer result: `/tmp/onpc-graphical-smoke-eo6vqp9n/result.json`.
- Worker reports: `/tmp/onpc-e2e-evidence-6htbznxf/worker-before-cleanup.json`
  and `/tmp/onpc-e2e-evidence-6htbznxf/worker-result.json`.
- Run identity: `worker-f1c55cec451e400a81f09a115b9c8bdd`.
- Total 245.328 s: preparation 109.483 s, test 38.697 s, cleanup 97.135 s.
- All four stages completed: observer-ready, GDM, mouse-selected empty prompt,
  Escape dismissal. Three 1024×768 captures have distinct digests in the result.
  Raw captures remain private; no new screenshot export or visual-review claim.
- Infrastructure, collection and cleanup passed; product remained `not-run`.
  Worker and callback closed, source/host preservation passed, and the outer
  lease completed baseline restoration with `lease_phase=complete`.
- The command session was 89067. User interruption made that handle unavailable;
  its already-completed retained result was reconciled through the approved
  artifact reader. No duplicate smoke, VM reset, recovery or process signal was
  issued to recover the lost handle. A shell exit status was not recovered;
  the durable result establishes the completed runner/cleanup outcome.

## Input identity

The result contains the complete input map, backend pins and screen digests.
The two production-code hashes below were checked against the current checkout
after the live attempt; no subsequent runtime edits were made in this slice.

| Input | SHA-256 |
| --- | --- |
| `tests/e2e/e2e_worker.py` | `9ea3f104298c64f061c4d255b0c8a9011320913a46b143cc0100736f90f35b3e` |
| `tests/integration/check_graphical_smoke.py` | `503c3e117ff51ae7c645fbed26bbef68d1e6bfe7b0e0ec956f23ce6d944a689d` |
| `tests/unit/test_e2e_worker_cleanup_safety.py` | `eb6972def9fa95c4c75cee530bf81194ef38486f6dbcb8e3d75b7cf1b20bda73` |
| Staged distribution map | `d7ccdaf1c9eacfd9fedef51ee4f4e939e8b959b6c2734d33e11319d7eba227c2` |
| Accepted baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |

## Host verification and limits

Focused development checks passed 78 tests before removing three redundant
tests of the old cleanup function. Their behavior is covered by the new worker's
combined-failure cases. The final isolated prerequisite selection passed
221 tests and 3 subtests in 1.97 s before live VM use. The dispatcher also ran
its prerequisites before the smoke. `make check` subsequently passed 1,926
unit/contracts (25.65 s), 17 private-D-Bus components (0.34 s), syntax/source
guards and stage traceability; command session 23309 exited 0.
Final `git diff --check` passed after the handoff documentation was updated.

The new module has 33 host-only cases covering success, guarded refusal,
interruption, stale distribution inputs, identity replacement, nonzero exit,
timeouts, report failure and combined worker/callback cleanup failure. The
first local collection failed on a missing test import path and was corrected;
it was not a VM attempt. No backend diagnosis or feasibility rerun is pending.

Approximately 20 minutes of implementation/review and verification, plus the
user interruption/approval interval, completed this bounded worker extraction.
Host preparation and baseline restoration dominate the measured live run; no
extra repetition, cache or new framework was added. Concurrent Make approval
rule changes and their tests were preserved as unrelated work.

Remaining: the inventory-gated public launcher/Make target, full current-input
provenance and verified guest asset transfer, scenario evidence production,
harmless observation smoke, and real secret-safe input/capture integration.
Worker diagnostics do not satisfy `EvidenceContract.validate`. Stable matching
and the complete E2E-001 journey remain Task 19B. Next implementation should
call this worker, not re-extract it or repeat 19P qualification.
