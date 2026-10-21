# F14 — Bridge cache ownership into active executions

Acceptance: host
Requires: F03

## Purpose and scope

Deliver the [cache ownership/session boundary](../Fixture-Design.md#cache-ownership-and-execution-sessions)
without enabling production consumers before F04's build-count/retirement gates.

## Read and implement

Read F03's complete authority, `test_storage.directory` / `recordings_directory`,
`test_retention.Store` and its inherited-token refusal tests, `tools/onpc-test-runner`
caller authentication/dispatch, `regression_session.py`, `vm_artifacts.py` and
the root/host retention handoff. Add the shared authenticated-caller cache lookup
and fixed request/pin validation. Keep all publication/deletion with the host
authority; root opens existing immutable files and version leases read-only.
Bind the root attempt journal before transfer. Preserve the outer execution
token and result journal; do not clear environment state or relax export guards.
Use nonblocking cache access under an existing VM lease and the documented
two-stage stale-pin recovery order. No new daemon or VM operation is required.

## Finite validation and cleanup

With private caller/dispatcher doubles, hold a real execution-retention session
and prove cache hit, miss, publication, pin acquisition and recovery in the same
invocation while ordinary evidence export still refuses. Exercise a second
target reader during production, root lookup through the authenticated caller,
supplied-UID/path substitution, changed checkout/inode/mount, lost host supervisor,
live privileged reader and failed VM cleanup preventing pin release. Prove root
cannot create a privileged cache or mutate the host catalogue, and descendant
leases survive interruption. Use exact registered unit safety selections and
review process/storage/resource classifications before running them. Finish only
owned private transactions, update delivered storage/support/approval APIs and
close through the [master](../Fixture-Execution-Plan.md).
