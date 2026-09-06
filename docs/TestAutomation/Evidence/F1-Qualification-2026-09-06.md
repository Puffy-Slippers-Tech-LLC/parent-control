# F1 qualification and acceptance — 2026-09-06

Scope: development host, existing guarded `ubuntu26.04` VM. No product changes
or host tooling changes. **F1 is accepted.** Task 14 retains its known product/helper failures.

## Implemented and checked

`QUALIFICATION_FAILURE=1` / `--qualification-failure` is restricted to
`AREA=authorization TEST='test_method_role_matrix[ListManagedUsers-parent1]'`.
The fixed public pytest call wrapper fails only after the real assertion
succeeds. Its bytes and mode enter selected-input provenance. Qualification
cannot pass as product acceptance, even if the fault is absent. Exact healthy
prerequisites plus the fixed selected failure distinguish the injected
infrastructure fault from real test failures. Collection and cleanup retain
their independent outcomes.

Local verification:

- Initial isolated cleanup prerequisites: 49 passed plus 3 subtests.
- First focused run: 96 passed, two failures exposed pytest's `Failed: ` JUnit
  prefix; corrected before any VM qualification.
- Corrected focused runner/qualification/authentication-export checks: 99 passed.
- After the allowed VM attempt, review found empty XML error/skip elements must
  be tested for presence rather than truthiness. Focused regression checks:
  99 passed, including both inconsistent-counter cases.
- Qualification-stage `make check`: 920 unit/contracts and 17 components passed,
  together with syntax/source/traceability checks. About 14 seconds for pytest portions.
- Before the second VM invocation, isolated controller/caller/agent cleanup
  prerequisites: 35 passed.
- Host-safe listing resolves five executions and labels harness qualification.
  The child-denial selector and `QUALIFICATION_FAILURE=2` both refuse with make
  exit 2 before VM operations. `git diff --check` passed.

## Inputs and allowed sample

Fresh initial artifacts: `/tmp/onpc-f1-20260906-qualification`.
Source SHA-256: `4bef9ec13c40551c66cbea9a71c377810542bc61d31e22e9bf872b9d1bb9088e`.
After the classifier edge-case edit, fresh final artifacts:
`/tmp/onpc-f1-20260906-qualification-final`.
Source SHA-256: `8268b908a6bc632aa47c48a767cb51fe1ebbe2a1a7d6708f016bd387826c9f99`.
The second build took 5.67 seconds. Both verified builds produced identical
package and stable fixture digests:

- Package: `0f7ffa0a388ef6b5ed6d40316968ff22ab64111b7f213cd7069b637087b0055d`.
- Fixtures: `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43`.

The allowed command was:

```sh
pkexec make -C /Data/Code/PST/parent-control check-system \
  ARTIFACT_DIR=/tmp/onpc-f1-20260906-qualification \
  AREA=authorization TEST='test_method_role_matrix[ListManagedUsers-parent1]'
```

It exited 0, with five exact passing executions, all four outcomes passed,
and cleanup phase `complete`. Evidence: `/tmp/onpc-system-qpzqx8ve/evidence`.
Selected-input SHA-256:
`b334f89e828490725e31ac8cdffabf354a6803ee267a6efbfb151067c033c4a6`.
Authorization XML SHA-256:
`35ee0b1e0895e9727c8746bc34c23d0d2257b27ccaded9d5874cbf27673d5c36`.
Read-only exact-identity/XML/outcome audit:
`/tmp/onpc-f1-qualification-audit.py`; retained output:
`/tmp/onpc-f1-qualification-success-audit.jsonl`.

| Recorded stage | Allowed sample seconds |
| --- | ---: |
| Preparation | 2.410155 |
| Bootstrap | 45.716784 |
| Install | 49.463625 |
| Reboot | 19.068982 |
| Test | 33.191079 |
| Collection | 1.566708 |
| Cleanup | 98.928458 |

Timing gap found by inspection: initial `Lease.__enter__` baseline verification
runs outside the preparation timer. These stage sums underreport elapsed time;
the final code now times that boundary without changing baseline validation.

## Completed deliberate sample

The owned invocation (exec session 92498) waited for host `pkexec`
authentication, then completed with the expected make exit 2. The authentication
wait crossed user turns; it was not a failing VM attempt and no duplicate was
launched. The guarded operation completed collection and baseline/configuration
cleanup before further code changes.

```sh
pkexec make -C /Data/Code/PST/parent-control check-system \
  ARTIFACT_DIR=/tmp/onpc-f1-20260906-qualification-final \
  AREA=authorization TEST='test_method_role_matrix[ListManagedUsers-parent1]' \
  QUALIFICATION_FAILURE=1
```

Evidence: `/tmp/onpc-system-_kufc3hb/evidence`.
The fixed `harness:qualification-failure` survived transport and export with all
five exact identities. Collection and cleanup passed; infrastructure records
the deliberately injected fault, and no product acceptance pass is claimed.
Selected-input SHA-256:
`5d90edb5e97ae46e4f2625f67ec959d15128bdb9b4e0acb34ea754318f0e2780`.
Authorization XML SHA-256:
`144cd8f1f7eb4062e46b18801db7acf094119025d6ed336ede38e5ecaa6489c1`.
Audit output: `/tmp/onpc-f1-qualification-failure-audit.jsonl`.

## Final unselected acceptance

The user explicitly requested completing F1 instead of another slice handoff.
After the deliberate sample finished, the baseline verification timing gap was
fixed. Three regressions verify elapsed time on success, proof rejection and
interruption while retaining lock release and no pre-validation VM mutation.
Focused runner/qualification checks: 102 passed. Isolated cleanup prerequisites:
49 passed plus 3 subtests.

The first final local check, invoked with shell output redirection inside the
platform sandbox, produced 922 passes and one isolated Flatpak fixture failure:
`Could not connect: Operation not permitted`. Original output is retained at
`/tmp/onpc-f1-acceptance-make-check.log`. The approved direct `make check` command
was rerun outside that sandbox, without changing product or host configuration:
**923 unit/contracts and 17 components passed**, with syntax/source/traceability.
The pytest portions took 14.29 and 0.36 seconds. This corrected invocation is
recorded separately and does not erase the sandbox failure.

Fresh acceptance artifacts: `/tmp/onpc-f1-20260906-acceptance`.
Build duration: 5.80 seconds. Source SHA-256:
`5584f7fe5f2aa250713f8913b73e61bedad4968e501aa3b0b9c6b5d50722b412`.
The package and stable fixture digests still match both earlier verified builds.
The host-safe inventory `/tmp/onpc-f1-unselected-list.txt` listed 225 executions.

```sh
pkexec make -C /Data/Code/PST/parent-control check-system \
  ARTIFACT_DIR=/tmp/onpc-f1-20260906-acceptance
```

Exec session 54414 completed with make exit 2, preserving
`pytest:failed:authorization`. Evidence: `/tmp/onpc-system-vbx_zcy6/evidence`.
The unselected run contains **225 exact executions: 217 passes and eight known
Task 14 failures**, with zero errors/skips. Package phases each passed two cases;
authorization has 213 passes and eight `agent:unexpected-denied` failures.
Infrastructure, collection and cleanup passed. Product outcome remains failed.

All ten `onpc.authentication` properties are present and associated with the
correct case and attempt. Both surfaces retain the deliberate wrong-password
`pam-authenticate` category followed by valid-password `authority-response`.
The six live-state revalidation cases each retain one `authority-response`
record. These categories establish the diagnostic boundary, not its cause.
No authentication repair or unchanged retry was undertaken, and Task 14's prior
retry budget remains spent.

Read-only audit `/tmp/onpc-f1-unselected-audit.py` cross-checks the pre-run
inventory, expected/reported identities, actual XML, source/package/fixture and
guest selected-input identities, exact known failures, per-attempt diagnostics,
and independent outcomes. All exported XML parses; known fixture account and
credential sentinels are absent. Output with public-file hashes:
`/tmp/onpc-f1-unselected-audit.jsonl`.

Selected-input SHA-256:
`4190cf7792ca1677c7cbe58c62c01469713f315c15860a1ed6960d96f659201d`.
Authorization XML SHA-256:
`5a1457aa56124aa06fbc19329184139f5ade386de3a0845b6785665abec76484`.
Aggregate result SHA-256:
`33dbee3be28192afdaddbbb4cba04208fc9bbe082e44040fab3c521ab623a6be`.

| Stage seconds | Allowed | Deliberate failure | Unselected acceptance |
| --- | ---: | ---: | ---: |
| preparation | 2.410155 | 2.362192 | 74.561157 |
| bootstrap | 45.716784 | 40.355613 | 41.157632 |
| install | 49.463625 | 50.142172 | 50.607015 |
| reboot | 19.068982 | 20.671231 | 20.181522 |
| test | 33.191079 | 33.087543 | 123.587305 |
| collection | 1.566708 | 1.579877 | 2.003849 |
| cleanup | 98.928458 | 98.783447 | 98.197476 |

The first two historical preparation durations exclude initial proof validation;
the final 74.561-second preparation includes its separately logged 72.259 seconds.
Baseline proof and cleanup dominate the measured overhead; a fresh build took
5.80 seconds. Host authentication waits and user interaction are outside these
runner stage totals. Three guarded attempts answered three distinct acceptance
questions; none was an unchanged retry of the known authentication blocker.

Every owned command completed. The controller restored the retained baseline
and original persistent configuration, verified host preservation, and recorded
cleanup `complete`. At 16:23 UTC, the subsequent read-only
`virsh --connect qemu:///system domstate ubuntu26.04` returned `shut off`.
No process or VM operation is pending. Final documentation links/references and
`git diff --check` passed. This is F1 runner acceptance, not a full product or
release pass; graphical/E2E and remaining roadmap work are unchanged.
