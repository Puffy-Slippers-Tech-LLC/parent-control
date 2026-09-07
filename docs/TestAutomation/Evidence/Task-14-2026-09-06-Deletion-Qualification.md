# Task 14: deleted selections qualified — 2026-09-06

Scope: development host and the existing guarded `ubuntu26.04` VM. This session
qualified `test_deleted_target_and_approver_fail_closed`; Task 14 as a whole and
release acceptance remain incomplete. The previous [implementation evidence](Task-14-2026-09-06-Deletion.md)
is historical; its host-authentication blocker is resolved.

## Change and demonstrated result

The first VM attempt reached the new fixture but failed at its initial
`SetParentControl` call with `AccessDenied`, before either account deletion.
Broker logs show rejection before the parent-control transaction started. The
fixture created the target with `useradd` and immediately invoked the broker,
without establishing the authoritative account properties first. A delayed
AccountsService local-account reload is the working explanation; the failed
run did not capture the individual eligibility flags, so it cannot establish
which flag caused rejection.

The fixture now uses the public AccountsService
[`CreateUser` API](https://cgit.freedesktop.org/accountsservice/tree/data/org.freedesktop.Accounts.xml),
installs the private approver password through the existing helper, and calls
`SetLocked(false)`. It checks `AccountType`, `LocalAccount`, `SystemAccount` and
the approver lock state before invoking the broker. It does not retry rejected
product calls or change product authorization. The passing JUnit records the
target as a local non-system standard account and the approver as a local
non-system administrator.

The corrected case passed and retained these observations as JUnit suite
properties, without identities or credentials:

- Target and approver deletion each became visible in NSS and AccountsService.
- Existing manager and kiosk connections refreshed discovery exactly.
- Nine target read/management calls and three request paths rejected the stale
  selections with the exact broker `InvalidRequest` error.
- All seven surviving role accounts retained preferences, limits, grants and
  filters; stale requests did not recreate or modify the deleted target record.

The pre-deletion redaction helper implemented previously was exercised for real.
All 163 exported guest files were checked for the known target, approver,
baseline parent/child and VM identity strings; none remained. Private retained
identity files were not exported. The local text/XML regression also passed.
This is a scoped redaction check, not a claim of an exhaustive privacy audit.

Only the test fixture and its evidence were changed by this session. No product
code, saved-data schema or system integration changed; activation is the next
test invocation. Concurrent development-tooling edits elsewhere in the checkout
were preserved. Each build captured its source tree; the package digest was
identical, and the final seven selected test/helper files were independently
verified to match the passing selected-input digest after completion.

## Commands and verification

```sh
/usr/bin/python3 -B -m pytest tests/unit/test_ui_cleanup_safety.py tests/unit/test_child_preview_cleanup_safety.py tests/unit/test_prepare_host_cleanup_safety.py tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_system_caller_cleanup_safety.py tests/unit/test_system_agent_cleanup_safety.py -q
make check-system LIST=1 AREA=authorization TEST=test_deleted_target_and_approver_fail_closed
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-deletion-qualification
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-deletion-qualification --area authorization --test test_deleted_target_and_approver_fail_closed
# After the fixture correction:
/usr/bin/python3 -B -m pytest tests/unit/test_system_guest.py tests/unit/test_authentication_evidence.py tests/unit/test_system_runner.py -q
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-deletion-accountsservice
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-deletion-accountsservice --area authorization --test test_deleted_target_and_approver_fail_closed
git diff --check
virsh --connect qemu:///system domstate ubuntu26.04
```

Initial isolated prerequisites: **49 tests / 3 subtests passed**. Both guarded
dispatcher invocations ran their own isolated prerequisites first: **175 tests /
3 subtests passed** each. Focused checks after the code change: **104 passed**.
Both builds and the final diff check passed. Task-level `make check` and full-area
acceptance were not repeated for this focused fixture fix; they remain required
when the remaining Task 14 assertions are implemented.

The successful run contains exactly these five JUnit executions, each once,
with zero errors, failures or skips:

| Phase | Case |
| --- | --- |
| installed | `test_installed_package` |
| installed | `test_first_install_requests_reboot` |
| rebooted | `test_installed_package` |
| rebooted | `test_reboot_applies_installation` |
| authorization | `test_deleted_target_and_approver_fail_closed` |

## Retained attempts and input identities

| Attempt | Owned session / exit | Evidence | Result |
| --- | --- | --- | --- |
| Initial fixture | 70367 / 1 | `/tmp/onpc-system-dsmp4rzm/evidence` | Authorization setup failed; original failure preserved |
| Corrected fixture | 28552 / 0 | `/tmp/onpc-system-7c1v_6ac/evidence` | All five executions passed |

The first aggregate reports product failed because guest pytest setup failed;
that classification does not establish a product defect. Its infrastructure,
collection and cleanup passed. The corrected aggregate reports **all four
outcome domains passed**, category `all-checks-passed`, cleanup phase `complete`.
Both attempts restored the accepted baseline. Final read-only domain check:
**shut off**. All owned commands finished; no operation remains pending.

Both manifests record revision `48276e148716e8a126869ac95d9cc7a366d7f433` plus
captured working-tree changes. Documentation edits after the runs are not test
inputs; do not assume these historical build directories match a future tree.

| Input | Initial SHA-256 | Corrected SHA-256 |
| --- | --- | --- |
| Source | `46ea65339b117dbfa455b05b6278e1f61ca606ce26fc80f054f10dfaba5ab76a` | `29d01c09fa44566428ef66f8b9ce6b6c84b0a9c5b5fcb014d40dad08c1f41be2` |
| Selected test/helper inputs | `754149a4a90eeb17022e695f2e38ae31ddcad9e6ad7669961dfc412ddb4ff952` | `9671b1cbf2898649114a995cd2115f2b71b8e6e1346007e39e25f8caf1cac6ca` |

Package SHA-256 (both): `aa2865d84f41f6658656b8b6320f0c188ca7ec2d53be5a91f77906002cdff549`.
Stable fixture SHA-256 (both): `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43`.

| Attempt | Preparation | Bootstrap | Install | Reboot | Tests | Collection | Cleanup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial | 72.2 s | 42.9 s | 49.3 s | 20.1 s | 31.9 s | 1.7 s | 100.6 s |
| Corrected | 73.9 s | 45.1 s | 50.8 s | 19.2 s | 39.9 s | 1.7 s | 104.1 s |

Two VM attempts answered the fixture-readiness question; it is resolved. The
passing authorization phase itself took 7.6 seconds; baseline validation and
cleanup dominate cost. No further repetition is justified for this slice.
Context/usage telemetry was not available.

## Next session

Implement and qualify **in-flight selected-target deletion on child and kiosk
request paths**, with independent per-case accounts and real authentication.
Reuse the qualified helpers; do not repeat this stale-selection case solely
because a new session starts. Remaining identity/eligibility coverage,
requester disconnect, matrix/requirement audit and full-area acceptance follow.
The [active handoff](../Task-14.md#continuation-handoff--2026-09-06-incomplete)
recommends `gpt-5.6-sol` / `high`: keep the model because OS helpers are proven,
and keep effort for the remaining live-request transaction/cleanup boundary.
