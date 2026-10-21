# F29 — Own a single fixture producer lifetime

Acceptance: host
Requires: F52

## Purpose and scope

Deliver single-producer reservation and cleanup before any new fixture build, under the
[working-set contract](../Fixture-Design.md#initial-working-set-and-producer-reservation).
This is shared test-infrastructure support, not product code or VM preparation.

## Read and implement

Read the frozen slot/lock schema and complete shared allocation, scratch
descriptor, retention identity/deletion and maintained builder interfaces. Add
one producer context which durably reserves a build slot and registers its
scratch/staging children before writes. Forward inherited owner/scratch leases
through every compiler and archiver descendant. A surviving child or unfinished
cleanup keeps that same slot occupied; retries resume its recorded transaction
rather than allocate another generation. Expose this lifetime API for F02/F03
and F04's six-slot admission policy; create no independent cache. Use existing
disk scratch and ownership primitives. No byte quota, filesystem sandbox,
quota-specific setup operation or new package prerequisite belongs to this task.

## Finite validation and cleanup

Use private allocations and waited small children to prove serialization,
registration before writes, descriptor forwarding, parent exit with a surviving
child, cancellation and exact retry without slot growth. Inject disk-full write
failure and interruption before reservation, during staging and during deletion.
Preserve committed inputs and unknown/replaced paths; recover only recorded
scratch/process identities after proven descendant exit. There is no quota test
or live VM/host-policy/product installation. Register process/storage resource
classifications and run exact maintained safety checks before protected cleanup.
Update delivered storage/build
owners and close through the [master](../Fixture-Execution-Plan.md).
