# F02 — Build immutable host fixture bundles

Acceptance: host
Requires: F29

## Scope and implementation

Implement [host construction](../Fixture-Design.md#identity-and-build-publication)
for the finite inventory. Read the complete fixture builders/declarations,
`tools/artifact_inputs.py`, `package_inputs.py`, `build_test_artifacts.py` and
affected callers/tests. Freeze fixture sources before building; keep actual
product inputs separate. One `native-runtime` build per target supplies all
declared subsets, without host-only collections or a copied interpreter tree.

Reuse the existing target builders and F29 producer lifetime. Verify native
runtime ABI for both declared targets on the host. Record source/toolchain/target
inputs separately from exact output bytes. Implement one complete manifest and
payload verifier, including finite destinations/roles and absence controls.
Expose validated build/verify options through the existing fixture launcher;
preserve legacy callers until migrated. No shared cache is required.

## Acceptance and cleanup

Run the affected registered builder/artifact unit selections and actual fixture
construction at its reviewed resource limit. Prove complete minimal membership,
both target ABI checks, frozen-source mutation refusal, malformed/unsafe archive
refusal and separate fixture/product/dependency invalidation. Record output and
scratch sizes; apply existing storage limits. Preserve producer descendant leases
and cover build failure/interruption/disk exhaustion with exact owned cleanup.
Do not build packages solely to demonstrate fixture independence.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
