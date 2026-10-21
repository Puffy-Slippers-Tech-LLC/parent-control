# F02 — Build immutable host fixture bundles

Acceptance: host
Requires: F29

## Purpose and scope

Deliver the [design's build/identity boundary](../Fixture-Design.md#identity-and-build-publication)
for F01's finite inventory. Keep sources, compiler work, expected results and
unused fixture collections on the host; build only declared minimal profiles.
The initial host build profile is `native-runtime`; its guest subsets share one
version per target/ABI under the [working-set contract](../Fixture-Design.md#initial-working-set-and-producer-reservation).

## Read and implement

Read F01's frozen map, `tests/fixtures/build_test_applications.py`, `native_assets.py`,
`baseline_assets.py`, `tools/artifact_inputs.py`, `package_inputs.py`,
`build_test_artifacts.py`, `e2e_startup_cache.py` and complete affected consumers.
Reuse builders, shared disk scratch and F29's single-producer slot reservation.
Implement canonical complete manifests,
frozen source/toolchain/target/ABI keys and separate exact output content identity.
Build native artifacts in maintained host-side target environments and verify
their declared runtime ABI; never compile in the guest or relabel host binaries.
Expose the reviewed host build/verify interface through the maintained fixture
route; this task does not expose a shared published cache before F03/F04.
Preserve existing callers until they migrate. Forward scratch lease descriptors.

## Finite validation and cleanup

Extend the affected builder/artifact unit modules and private fixture tests for
identical build/reuse inputs, minimal closure, fixture-only versus product/dependency
changes, source mutation while freezing and invalid manifest/archive membership.
Exercise actual fixture construction at its reviewed artifact resource limit.
Record both target outputs, simultaneous scratch footprint, allocated blocks and
expanded membership for inspection; there is no fixed fixture-cache byte ceiling.
Verify failure, disk exhaustion and cancellation cannot allocate another build
slot until the original producer/descendant cleanup is reconciled.
Do not run package builds solely to verify fixture source independence. Expected
result: valid bundles identify exact bytes, incomplete or unsafe bundles refuse,
and no guest or snapshot is touched. Use `tools/run-tests unit` with exact affected
modules and, where needed, its existing `fixtures`/`fixture-runtime` routes after
checking help/listing. New tests/selectors remain unimplemented until registered.
Review resource classifications, remove only owned scratch, update support/build
owners with delivered APIs and close through the [master](../Fixture-Execution-Plan.md).
