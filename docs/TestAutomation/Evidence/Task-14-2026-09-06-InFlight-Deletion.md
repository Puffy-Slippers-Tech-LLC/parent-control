# Task 14: in-flight target deletion qualified — 2026-09-06

Scope: development host and existing guarded `ubuntu26.04` VM. The new
`test_authenticated_request_rejects_deleted_target` passed on its first VM
attempt. Task 14 and release acceptance remain incomplete.

## Implemented and observed

The installed test covers both `RequestOwnAccess` and kiosk `RequestAccess`
in one registered case. It creates separate eligible targets through
AccountsService before either deletion, preventing UID reuse between surfaces.
The existing deletion fixture now shares a guarded creation helper with an
allowlisted role/surface namespace and authoritative eligibility assertions.
Existing case registrations remain intact. The selector advertises the real
password fixture, with a local prerequisite/execution regression.

For each surface, the passing JUnit records this sequence:

1. The real caller starts a request and its Polkit agent shows the selected
   administrator's password prompt.
2. AccountsService deletes the target; NSS and AccountsService both report it
   absent before authentication completes.
3. The system bus still resolves the original caller connection to its UID.
4. The selected parent's real password authenticates successfully.
5. The broker returns exactly `InvalidRequest`, with the caller still connected.
6. All seven surviving role accounts, and the other disposable target while
   present, retain their preferences, limits, grants and filters. The request
   does not recreate/change the deleted target's preference record or restore
   it to managed-account discovery.

This distinguishes target revalidation from failed authentication and requester
disconnect. Both `onpc.authentication` records have outcome `accepted`; both
`onpc.inflight-target-result` records report
`authenticated-invalid-request-state-preserved`. No product code, system
integration, saved-data schema or host account was changed. Helper changes
activate on the next test invocation. Existing unrelated work was preserved.

## Verification and retained evidence

```sh
/usr/bin/python3 -B -m pytest tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_system_caller_cleanup_safety.py tests/unit/test_system_agent_cleanup_safety.py -q
/usr/bin/python3 -B -m pytest tests/unit/test_system_guest.py tests/unit/test_authentication_evidence.py tests/unit/test_system_runner.py -q
make check-system LIST=1 AREA=authorization TEST=test_authenticated_request_rejects_deleted_target
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-inflight-deletion
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-inflight-deletion --area authorization --test test_authenticated_request_rejects_deleted_target
make check
git diff --check
virsh --connect qemu:///system domstate ubuntu26.04
```

- Isolated caller/agent/runner safety: **30 passed**. The dispatcher then ran
  all its isolated cleanup/lease prerequisites: **175 passed, 3 subtests**.
- Focused local checks: **105 passed**. Build and artifact verification passed.
- `make check`: **1,224 unit/contract tests and 17 private-D-Bus component tests
  passed**, plus traceability, syntax and source guards.
- VM evidence: `/tmp/onpc-system-mjyfezgu/evidence`. Exactly **five executions**
  passed: installed package and first-install reboot notice, rebooted package
  and activation, then the new authorization case covering both surfaces.
  No failures, errors or skips. Product, infrastructure, collection and cleanup
  all passed; aggregate category `all-checks-passed`, cleanup phase `complete`.
- Checked all **239 exported guest files** for the two disposable target names,
  four baseline parent/child names and VM hostname: no matches. Private retained
  identities remain outside the public export. This is a scoped redaction check.
- Independently compared all seven selected test/helper file hashes against the
  retained manifest: the passing files still match the checkout. Later handoff
  documentation edits are outside that selected input set.

Owned build session **28662**, VM session **65329**, and `make check` session
**6155** all exited **0**. The read-only manifest command also finished.
Baseline restoration completed; final domain state was **shut off**. No owned
operation remains pending. One expensive attempt was used, with no rerun.

| Input | SHA-256 |
| --- | --- |
| Captured source | `f8d58dda03da06b07ba2e0c1982b07c5be53c97ac57050473ac4c6fead6a90a4` |
| Selected test/helper inputs | `f9add77764043a2eaacacdbf5df35d7e6929f9ca49e71843d4522e3cc04532be` |
| Package | `aa2865d84f41f6658656b8b6320f0c188ca7ec2d53be5a91f77906002cdff549` |
| Stable fixtures | `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43` |

Revision: `48276e148716e8a126869ac95d9cc7a366d7f433` plus captured working-tree
changes. Do not reuse this build directory as the default for changed inputs.

| Preparation | Bootstrap | Install | Reboot | Tests | Collection | Cleanup |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 75.5 s | 52.0 s | 49.0 s | 19.2 s | 39.5 s | 1.7 s | 97.2 s |

The authorization case took **6.2 seconds** including fixture setup. VM stages
totaled about **334 seconds**; preparation/cleanup remain the dominant cost.
Context/usage telemetry was unavailable.

## Next result

Implement and qualify requester disconnect during a live selected-parent prompt
on both request surfaces, using the recorded caller/agent ownership helpers.
Keep disconnect separate from the now-proven deletion case. Remaining identity/
eligibility variants and requirement/method-matrix audit follow, then one full
authorization-area acceptance run. The extracted helper's stale-selection case
was not rerun in this focused selection; full-area acceptance must exercise it.
`ONPC-COMP-BROKER-003` and `ONPC-COMP-BROKER-007` gain partial evidence here;
their complete requirement mapping/acceptance remains pending.

Next settings: **`gpt-5.6-sol` / `high`**, keep both. Proven real-authentication
and deletion helpers keep the model appropriate; disconnect still needs careful
reasoning about cancellation, completed transactions and ownership-safe cleanup.
