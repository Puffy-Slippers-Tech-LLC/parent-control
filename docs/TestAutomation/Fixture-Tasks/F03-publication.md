# F03 — Reuse execution-owned fixture inputs

Acceptance: host
Requires: F02

## Scope and implementation

Deliver [execution-owned inputs](../Fixture-Design.md#execution-ownership-and-retention)
through existing artifact/named-input and retention owners. Read complete
`test_storage.named_input`, `test_retention`, artifact preparation, authenticated
dispatcher handoff and their cleanup tests. Select before VM acquisition; keep
the immutable selection through descendants and VM cleanup.

Copy fully verified producer output into the execution's registered retained
allocation, then publish completion atomically. Reuse only verified input already
protected by its existing journal. Separate product/fixture keys and extend the
shared handoff narrowly if needed. Preserve the inherited retention token and
authenticated caller/read-only ownership checks. Do not introduce shared-cache
catalogues, cross-journal pins, quota/prune policy or dual deletion ownership.

## Acceptance and cleanup

Use private host tests for matching reuse, incomplete/corrupt input refusal,
source edits during use, authenticated/foreign/replaced input, concurrent activity
exclusion and interrupted publication/owner loss. Prove descendants and unfinished
VM recovery retain their input, and normal bounded retention resumes only after
cleanup. Existing nonempty inputs must never be silently replaced. Review affected
resource inventories and leave no unresolved producer/allocation ownership.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
