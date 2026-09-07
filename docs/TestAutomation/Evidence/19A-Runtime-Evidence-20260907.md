# Task 19A runtime evidence slice — 2026-09-07

Host-only implementation evidence, not Task 19A acceptance or graphical coverage.
The starting inventory remains 33 families / 156 pending variants.

Implemented `tests/e2e/evidence.py`, `tests/e2e/private_artifacts.py`, and
`tests/unit/test_e2e_evidence.py`; updated the
[collector contract](../../../tests/e2e/README.md#runtime-gate-and-private-collector).
The passing-result gate checks exact cases, ordered steps, assertions and evidence
links, frozen input identities, bounded timing, independent outcomes and cleanup.
Controller-owned failure history cannot be cleared by a later worker result.
The private collector rejects secrets, unsafe paths/permissions/types/links,
changing sources, replaced directories, modified copies and report overwrites.

| Experiment | Result | Pytest time |
| --- | --- | --- |
| Initial implementation: runtime + unchanged inventory regressions | 236 passed | 0.85 s |
| Added directory/report tampering, filename-secret, source-race and multiple-variant cases | 244 passed | 0.84 s |
| Final controller-owned failure-history integration and regressions | 244 passed | 0.87 s |

Final command (exit 0):

```sh
tools/run-unit-tests tests/unit/test_e2e_evidence.py tests/unit/test_e2e_inventory.py -q
```

This comprises 142 runtime tests and the existing 102 inventory tests.
`git diff --check` passed. No full `make check` or installed suite was needed for
this bounded host-only slice; neither is claimed. Temporary fixtures are separate
ready inventories with dummy executable references that are never executed.
Repository pending cases have not been promoted. Pytest temporary evidence remains
under its normal private temporary root; no privileged artifacts were produced.

Final implementation inputs, SHA-256:

| File | Digest |
| --- | --- |
| `tests/e2e/evidence.py` | `bc253bc24b77a56f203eaf3ea0ad5786a2d72ca85185127e96f381e56c330211` |
| `tests/e2e/private_artifacts.py` | `48fbe9f7d9c5ea506e94a47c1c74c58fbf9c4ab493eb8fa67d11767ae84ad335` |
| `tests/unit/test_e2e_evidence.py` | `6ca61a49a95acd6568cb8ce0d62d459ad32497b491047398ff4db53227d910f2` |
| `tests/e2e/inventory.py` (unchanged) | `1ba73a285cabb96e645bdc2a25b6e99b69946e708fbccb7c460e423f67d4bc44` |
| `tests/e2e/scenarios.json` (unchanged) | `c2d2bac4bea5da49be82f41a7de3e8f9e2780fbbee9c2bad09450dda647e35d4` |

About 15–20 minutes of implementation, review and documentation; three focused
checks totaling 2.56 seconds of reported pytest execution. VM preparation, live
tests and cleanup: zero. Context/usage telemetry was not collected. Every command
exited. No VM query, mutation, process termination or owned operation occurred.
Concurrent setup/permission changes appeared during the session and were preserved;
they are outside this evidence and were not qualified here.

Remaining boundary: connect this contract to the qualified guarded worker and
launcher, independently capture/freeze source and artifact provenance, generate
reviewed evidence from real actions, persist failures before cleanup, and exercise
fresh boot/observation/secret exclusion/restoration. Secret scanning cannot establish
image redaction or find unknown PII; the trusted producer must enforce the capture
policy. No backend feasibility rerun or baseline preparation is needed.
