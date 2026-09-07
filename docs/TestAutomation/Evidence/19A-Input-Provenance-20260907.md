# Task 19A input provenance — 2026-09-07

Completed a controller-owned provenance boundary on the development host.
This is host regression evidence, not a graphical scenario or live VM pass.

## Delivered

`tests/e2e/provenance.py` captures current tracked and nonignored untracked
source content/modes, including requirements and runner edits. Its aggregate
matches the artifact builder's digest format; the per-file digest map feeds
the existing worker's verified distribution staging. Source entries use safe
parent opens, regular singly linked files and identity checks around reads.

The capture verifies staged package bytes, fixture manifests and actual fixture
payloads through existing verifiers, rejects a package source identity that
differs from the current checkout, and hashes all staged bytes including the
Flatpak container. It reconciles the held lease's durable baseline state and
retained proof with its recorded baseline identity. Exported environment
identity is a safe digest of verified guest preparation; it does not export
account records or establish the full installed host-tool environment matrix.

`VerifiedInputs.contract` creates the expected evidence gate from controller
inputs. `validate` refuses foreign contracts, checks preservation before and
after evidence reconciliation, and permanently retains detected input failure.
Restoring a changed file cannot clear a failure within the same capture.
The [reusable API contract](../../../tests/e2e/README.md#controller-owned-provenance)
specifies capture after private staging, startup rechecking and final validation
before releasing the lease.

## Verification

| Command | Result |
| --- | --- |
| `tools/run-unit-tests tests/unit/test_e2e_provenance.py tests/unit/test_e2e_evidence.py tests/unit/test_e2e_runner.py tests/unit/test_build_test_artifacts.py -q` | 219 passed in 2.47 s; includes 41 new provenance cases |
| `make check` | Exit 0; 2,006 unit/contracts in 27.56 s, 17 private-D-Bus components in 0.45 s, syntax and stage traceability |
| `git diff --check` | Passed |

New tests use actual temporary Git repositories, current tracked/untracked
edits, real artifact/fixture verifiers and the real private collector with
synthetic scenario records. They exercise stale package source, tampered
fixtures, additions/removals/mode changes/replacement, symlinks/hardlinks/FIFOs,
parent replacement, baseline/state/proof/lease failures, changes during capture
and result validation, secret-safe errors, latched failures and pending refusal.
The initial focused run found three test/format issues (Git excludes untracked
FIFOs, environment tokens disallow dots, and a temporary inventory lacked its
contract document); all were corrected and the final scopes pass.

| File | SHA-256 |
| --- | --- |
| `tests/e2e/provenance.py` | `5012926d7f88eb4a71f477910fcf3a3e5cb51d6cf9177c5bd45efcca07e945a9` |
| `tests/unit/test_e2e_provenance.py` | `f4e8e1dd327201f0a41471c88363e926d67497a40c4c3f08848edec9edaed21b` |

All test command handles exited, including make handle 33684. No VM or worker
attempt was started. No setup refresh, baseline mutation, installation or new
permission grant was needed. Concurrent permission-rule changes in the shared
checkout were preserved; the full check includes that current checkout state.

## Next boundary and limits

Wire real ordered scenario events and original-failure persistence around the
qualified worker, using this capture and its evidence gate. The controller must
still call the gate in a real held lease. Host tests simulate that lease; they
do not prove live baseline preservation. Source capture freezes identities and
detects changes at checks, while the worker separately copies verified source
bytes; there is no filesystem-monitor claim. Missing tracked files refuse as
they do in the current package builder.

Do not repeat source/provenance implementation or worker feasibility. All 156
repository variants remain pending, and execution dispatch remains closed.
Fresh guest asset/observation transfer and authenticated secret/capture transport
also remain Task 19A acceptance work; E2E-001 needs Task 19B matching.
