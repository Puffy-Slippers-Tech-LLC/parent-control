# Task 14: requester disconnect/cancellation and recovery — 2026-09-06

Scope: development host and existing guarded `ubuntu26.04` VM. The new
`test_requester_disconnect_during_approval` passed on its third VM attempt,
covering both child `RequestOwnAccess` and kiosk `RequestAccess`. Task 14 and
release acceptance remain incomplete. Both failed attempts are retained.

## Implemented and observed

For each surface, the installed test now establishes this sequence:

1. A real selected-parent password prompt is active. An independent kiosk
   connection receives `Busy` from a deliberately invalid-duration request,
   proving that the approval owns the transaction lock. That probe checks
   duration immediately after lock acquisition and cannot authenticate or write.
2. The recorded caller exits using the existing pidfd-owned cleanup helper.
   The actual system bus reports that its original unique name has no owner.
3. The test submits the selected parent's valid fixture password. Polkit reports
   terminal failure for the vanished subject. The test explicitly closes its
   owned authentication agent, then waits for the probe to return exactly
   `InvalidRequest`, establishing transaction completion rather than sleeping
   and assuming it finished.
4. The original request's correlation ID has a terminal broker `denied` record,
   with no usage-query or write-stage records. All seven role accounts retain
   their preference bytes, limits, grants and filters.
5. A fresh real caller with the same UID, selected parent, password and request
   authenticates successfully and receives a real grant. Other accounts remain
   unchanged. This positive control checks credentials and recovery after denial.
6. The grant is revoked, control is disabled, and the real configured cooldown
   elapses before leaving the surface, preserving independence of later cases.

JUnit contains four authentication outcomes: denied/accepted for child, then
denied/accepted for kiosk. Both surfaces record bus-name disappearance, agent
closure, `busy-then-released`, unchanged state, and successful fresh approval.

This qualifies requester process exit followed by explicit cancellation of the
owned test agent. It does **not** claim automatic prompt dismissal with a
surviving session agent, or separately forcing the broker's post-approval
`caller_alive` branch: on this installed Polkit, denial occurs in the authority.
No product code, host account, system integration or saved-data schema changed.
The test/selector changes activate on the next invocation. Existing work was
preserved; the new selector declares its password fixture prerequisite.

## Experiments and verification

| Attempt | Evidence directory | Result and next discriminating fact |
| --- | --- | --- |
| 1 | `/tmp/onpc-system-5bop_fpb/evidence` | Failed `agent:unexpected-denied`: the test incorrectly expected successful authentication after the subject disappeared. Polkit and the broker recorded denial. |
| 2 | `/tmp/onpc-system-o2o7s8q2/evidence` | Failed `authorization:disconnect-transaction-not-finished`: terminal failure was visible, but the lock stayed busy until teardown closed the owned agent. Broker denial was logged at that closure. |
| 3 | `/tmp/onpc-system-8zftfkk4/evidence` | Passed after explicitly closing the owned agent before observing completion; both denial/state assertions and both fresh-approval controls executed. |

The third attempt followed new lifecycle evidence and a concrete correction;
it was not an unchanged or speculative rerun. The earlier failures remain
failed. The session exceeded the initial estimate to finish this correction,
VM verification and cleanup, rather than hand off another pending experiment.

```sh
/usr/bin/python3 -B -m pytest tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_system_caller_cleanup_safety.py tests/unit/test_system_agent_cleanup_safety.py -q
/usr/bin/python3 -B -m pytest tests/unit/test_system_guest.py tests/unit/test_authentication_evidence.py tests/unit/test_system_runner.py tests/unit/test_system_agent.py -q
make check-system LIST=1 AREA=authorization TEST=test_requester_disconnect_during_approval
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-requester-disconnect-v3
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-requester-disconnect-v3 --area authorization --test test_requester_disconnect_during_approval
make check
git diff --check
virsh --connect qemu:///system domstate ubuntu26.04
```

The first two builds used the same output basename without `-v3`, respectively
without a suffix and with `-v2`. All three builds verified successfully.

- Final isolated caller/agent/runner cleanup safety: **30 passed**. Each guarded
  dispatcher also passed **175 tests / 3 subtests** before VM operations.
- Final focused local checks: **146 passed**. The earlier focused selection,
  before adding the unchanged agent regression module, passed **106 tests**.
- Final `make check`: **1,225 unit/contract tests and 17 component tests passed**,
  plus traceability, syntax and source guards. An intermediate redirected run
  hit sandbox socket/Flatpak restrictions (11 failures); it was rerun through
  the approved direct command. Its output is retained at
  `/tmp/onpc-task14-disconnect-check.txt` and is not represented as a pass.
- Final VM run: exactly **five executions passed**, including all four package/
  reboot prerequisites. No failures, errors or skips. Product, infrastructure,
  collection and cleanup all passed; aggregate `all-checks-passed`.
- Compared **all seven selected file hashes** with the retained manifest; they
  match the checkout. Later handoff documentation is outside that selected set.
- Checked **275 public guest files** in the passing run and **96 / 97** in the
  failed runs for the four known parent/child fixture names and VM hostname:
  no matches. This is a scoped redaction check, not an exhaustive PII claim.

| Final input | SHA-256 |
| --- | --- |
| Captured source | `d1d963420caf5ffe347ec36f0484800da51c4c5bbed4151713a7d1c403b4ee43` |
| Selected test/helper inputs | `e5dec75dbb8eb893ba4ae2fd83f30ae2a188f778d7e5e752f7bb5b3559aaaf1c` |
| Package | `aa2865d84f41f6658656b8b6320f0c188ca7ec2d53be5a91f77906002cdff549` |
| Stable fixtures | `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43` |

Revision: `48276e148716e8a126869ac95d9cc7a366d7f433` plus captured working-tree
changes. Each attempt's `result.json` retains its own source/selected-input
digests. Do not reuse these artifact directories for changed inputs.

| Attempt | Preparation | Bootstrap | Install | Reboot | Tests | Collection | Cleanup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 71.4 s | 52.1 s | 49.3 s | 19.1 s | 39.3 s | 1.8 s | 105.4 s |
| 2 | 75.4 s | 44.2 s | 51.0 s | 19.1 s | 49.6 s | 1.6 s | 110.7 s |
| 3 | 71.1 s | 51.6 s | 50.6 s | 20.1 s | 49.8 s | 1.7 s | 99.1 s |

The final authorization case took **19.926 seconds**, including fixtures and
natural cooldowns. Preparation/cleanup still dominate. Context/usage telemetry
was unavailable. Final build session **42128**, VM session **14234**, checks
**90893**, and read-only manifest session **15742** all exited **0**. Failed VM
sessions **30839 / 40412** exited **1** with cleanup complete. All owned commands
finished. Final domain state: **shut off**, retained baseline restored.

## Next result

Close Task 14 through a finite method/role and account-requirement audit. Compare
the existing registered cases with the broker matrix and Task 14's explicit
work, enumerate any concrete missing identity/eligibility assertions, implement
only those gaps as a batch, update requirement mappings, then run one complete
authorization-area acceptance. Preserve the earlier deletion qualifications;
do not repeat focused disconnect or deletion runs just to resume. Full-area
acceptance must include the extracted stale-selection helper and this new case.

Next settings: **`gpt-5.6-sol` / `medium`**; keep model, lower effort. The live
authentication and cancellation uncertainty is resolved; the next slice is
primarily coverage reconciliation and mappings using proven installed helpers.
If the audit finds a new concurrency problem, reassess from that concrete gap.
