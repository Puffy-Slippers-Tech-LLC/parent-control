# R05b — Recover owned account quarantine

Acceptance: host

Required tasks: R05a — capability-based required visibility setup.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md#allow-recover-and-reject), R01's
accepted [ownership decision](../SystemDesign/Lifecycle.md#r01d-configuration-and-quarantine-decision)
and [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract quarantine ownership/release from R05. Read full package-configuration,
provisioning, expiry capture/write, interruption/retry and completion callers.
Implement R01d's separate durable native configuration gate, distinct from removal
denial, so interrupted owned setup recovers after required setup succeeds. Verify
effective native gate coverage through the installer's setup-only bootstrap before
fresh creation, independently of generated configuration and final MAC setup.
Use the recorded creation nonce/UID/GID, staged-home inode and fixed-account
absent-only native-record completion to close the creation-to-ownership-marker
crash window. Follow the owner's state/authority matrix: native creation is not
atomic across passwd/shadow/group/home, present credentials/expiry are never
rewritten, and a product-only lock cannot protect an absent-only write from
administrator changes. Verify public libc locking/serialization against both
supported native account tools, including both ordered administrator-write races.
Bind only proven owned identity before visibility. Bootstrap an existing owned shipped
account into a closed first record under lifecycle exclusion, never into readiness.
Cover ordinary accounts, live admission
leases, failed-open/teardown and reboot. Preserve captured prior native expiry by
leaving it untouched; later administrator expiry/credentials, including same-value
writes, remain authoritative. Initialize the empty credential only during proven
fresh creation or its locked, absent-only completion before binding; never
re-delete an existing password. Migrate legacy v1 records without
guessing a shadow restore; differing current/prior expiry retains the record and
requires explicit administrator reconciliation/acknowledgement bound to the exact
record and current state, allowing the administrator to retain a denial without
forcing restoration of the old expiry. That legacy outcome is no
automatic availability pass. Equality alone proves no writer ownership.
Never release before required enforcement or overwrite ambiguous/foreign state.
R08a separately makes icon failure optional; provide the required/optional setup
boundary it will consume.

## Acceptance and close-out

Run finite host lifecycle/provisioning tests for bootstrap interruption, partial
native records/home publication, creation/binding/comment and configuration/ready
publication, native-lock/administrator-write ordering, successful retry/release, required-setup
failure, explicit prior/later administrator expiry and credential lock, same-value
writes, legacy ambiguity, independent removal denial and unowned metadata
preservation. Keep removal's identity-checked record cleanup consistent. Keep failure and bounded
recovery diagnostics precise. Apply master product review/revision, resource
review where applicable and `make build` after the final packaged edit. Update
the existing lifecycle/ledger and pass exact inputs to R05/R08a/R09a; complete owned
cleanup. Actual pre-GDM public-entry acceptance remains installed A/B/C coverage.
