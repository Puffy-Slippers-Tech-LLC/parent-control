# F03 — Publish bundles and pin consumers

Acceptance: host
Requires: F02

## Purpose and scope

Deliver a single shared cache authority for
[publication](../Fixture-Design.md#identity-and-build-publication) and durable
consumer pins. Keep the new authority gated from production consumers until F04
enforces its build-count and oldest-retirement gates.

## Read and implement

Read F01's schema/lock map and the complete F02 producer. Reuse
`tools/test_storage.py` and the identity, durability, publication/recovery and
descriptor primitives in `test_retention`; inspect `tests/unit/test_test_storage_cleanup_safety.py`,
`test_test_retention_cleanup_safety.py` and artifact-builder regressions.
Register before writes, verify staged payloads before atomic catalogue/completion
publication, and retain previous committed state on interrupted replacement.
Build requests deduplicate under one producer transaction. Acquire a durable
version pin before returning any consumer path; reader lifetime must survive
transfer/test subprocesses and controller interruption. Avoid dual deletion
ownership when handing existing artifact inputs into this cache.
Implement a separate version catalogue/transaction API: ordinary `Store` run
history and export publication are not the fixture policy. Preserve their
existing limits and inherited-execution-token refusal. Follow the
[cache lock/lifetime design](../Fixture-Design.md#cache-ownership-and-execution-sessions);
F14 separately implements active-session and authenticated privileged-reader
integration before F04 can enable public use.

## Finite validation and cleanup

Run private host regressions for concurrent identical producers, reader versus
publication, manifest/source replacement, abrupt boundaries before/after commit,
lost reply and retry, active pin exclusion, inherited child lifetime and stale
pin recovery only after proven owner release. Cover foreign/replaced paths,
symlinks, mounts and journal identity refusal. No live VM/host service is used.
Use exact registered unit selectors; extend resource inventories before running
new process/resource cases. New cache tests are planned until registered.
Retain failed transaction evidence in its owner, perform only recorded cleanup,
update shared storage/support owners with the delivered gated API and close
through the [master](../Fixture-Execution-Plan.md).
