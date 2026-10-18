# 004b — Implement verified native transaction inputs

Acceptance: host

Requires: 004a.

## Scope and prerequisites

Consume 004a's exact supported pairs; until they are recorded here this task is
blocked, not authorized to invent versions. Implement only their maintained
preparation, verification, staging and ownership, for both DEB and RPM.
Read [004](004-native-dependency-update.md),
[reusable preparation ownership](../../../tests/integration/Environment.md#reusable-preparation-ownership),
[VM baseline rules](../../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline),
[storage allocation](../../Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes)
and [host resource review](../../../tests/README.md#host-test-parallelism-review).
Inspect complete builder/staging/provenance functions and consumers before edits.

Extend existing input routes with finite native pair metadata, native signature
verification, architecture/version ordering, package and measured-file digests,
dependency closure and selected-input binding. Preparation owns reusable native
dependencies/fixtures; the deliberate old/new transaction remains attempt-owned.
Define how an old generation is established before retained admission without
turning a consumer into dependency repair or replacing the normal updated
baseline silently. Preserve unrelated native configuration and policy.

## Acceptance and close-out

Focused host regressions must cover both formats, exact compatible inputs,
missing/tampered/same-byte/wrong-version or architecture refusal, staging
collisions, foreign/symlink ownership, interrupted retry and retention binding.
Cover preparation first/repeat/update/retry and read-only consumer verification
where affected. Review every applicable resource inventory and cleanup owner.
Publish the implemented invocation and manifest contract in its existing
builder/installed-environment owner; mark live qualification still pending.
No new generic package-update framework or alternate storage/installation route.

Run affected host checks, check Markdown/plan, and refresh generated inventory
if collection changes. Product/build-input changes require `make build`; report
missing prerequisites. Mark only 004b complete. Real transaction scripts,
retained mappings and admission recovery remain unqualified until
[004d](004d-native-update-histories.md) passes on both targets.
