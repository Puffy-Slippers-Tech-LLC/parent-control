# Task 14: deleted selections implemented, VM qualification pending — 2026-09-06

Scope: development host and existing guarded `ubuntu26.04` VM. This session
made code and locally verified collector progress. It does **not** establish an
installed deletion pass, complete-area acceptance or release acceptance.

## Implemented

`tests/system/test_authorization.py` adds one independently selectable case,
`test_deleted_target_and_approver_fail_closed`. It creates two disposable guest
accounts before deleting either, avoiding accidental UID reuse within the case.
Collision checks refuse existing accounts. The retained baseline owns account
and home cleanup; no host account mutation is performed.

The case first establishes eligible target/approver discovery and saves a real
approver selection. It deletes accounts using AccountsService's public
`DeleteUser(xb)` API with file removal disabled. It waits up to ten seconds for
both NSS absence and failure of AccountsService lookup, then confirms a known
account still resolves to distinguish deletion from a dead service.
Persistent parent and kiosk D-Bus connections must refresh discovery exactly,
preserving surviving entries. Nine target read/management methods, a kiosk
request for the deleted target, and both request surfaces selecting the deleted
approver must return the exact broker `InvalidRequest` error. Saved preferences,
limits, grants and app filters of all seven surviving role accounts must remain
unchanged. Stale operations must not recreate or modify the deleted target's
remaining preference record. The existing target settings are restored afterward.

Inspection found that diagnostic collection only redacted current NSS accounts.
`system_guest.retain_identity_for_redaction` now stores pre-mutation account
identity under the guest's private payload, with mode 0600. Collection also uses
those identities after deletion/rename and does not export the identity files.
The new regression exercises actual text and decoded-XML collection after the
account disappears from simulated NSS. No product code, package activation,
host tools or application data schema changed; test changes apply next invocation.

## Verification

- Isolated cleanup prerequisites: **49 passed, 3 subtests passed** (session
  68298, exit 0), covering UI, child preview, host preparation, runner, caller
  and authentication-agent cleanup.
- Focused guest/collector checks: **21 passed**; the final full check also
  includes the tightened public-file inventory assertion added afterward.
- Final `make check`: **1,211 unit/contracts and 17 private-D-Bus components**
  plus syntax, source and stage-mode traceability checks (session 85347, exit 0).
- `git diff --check`: passed.
- Host-safe selection: exactly **five executions**, the new case and four
  installed/reboot prerequisites. No guest fixtures were executed on the host.
- Build/manifest verification passed (session 38458, exit 0).

```sh
make check-system LIST=1 AREA=authorization TEST=test_deleted_target_and_approver_fail_closed
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-deleted-identities
pkexec make -C /Data/Code/PST/parent-control check-system ARTIFACT_DIR=/tmp/onpc-task14-20260906-deleted-identities AREA=authorization TEST=test_deleted_target_and_approver_fail_closed
```

The privileged command (session **59979**) produced no make/controller output
and waited for host Polkit authentication. After a notification and several
minutes without a response, Ctrl-C cancelled that exact owned session; it exited
**130**. No deletion experiment executed, and no new VM result or selected-input
digest was produced. There is no product, collection or cleanup pass to infer.
Final read-only domain inspection returned **shut off**; no command is pending.

## Built inputs

Manifest: `/tmp/onpc-task14-20260906-deleted-identities/artifact-manifest.json`.
Revision `48276e148716e8a126869ac95d9cc7a366d7f433` plus captured working tree,
347 source files. Subsequent edits are documentation only; verify current inputs
before reuse rather than assuming this historical directory is current.

| Input | SHA-256 |
| --- | --- |
| Source | `945356f1fee52e92b5979c1df745e4713545135f4f744e61d8e6dee0915ef82d` |
| Package | `aa2865d84f41f6658656b8b6320f0c188ca7ec2d53be5a91f77906002cdff549` |
| Stable fixtures | `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43` |

## Next session

Complete host authentication and run the exact selection above with verified
current inputs and isolated cleanup prerequisites. Do not redo implementation
or the already-proven root/authentication matrices. Inspect the fixed deletion
stage labels, all five JUnit identities, exported redaction and four aggregate
outcome domains. The helper's real OS lifecycle behavior is still unproven.
After qualification, continue in-flight identity changes and requester
disconnect, then audit the matrix and run complete Task 14 acceptance.

Cost: zero VM preparation/test/cleanup stages; one verified build, two `make
check` runs (the collector fix justified the second), and a host-authentication
wait. No context/usage telemetry was available. See the
[active handoff](../Task-14.md#continuation-handoff--2026-09-06-incomplete).
