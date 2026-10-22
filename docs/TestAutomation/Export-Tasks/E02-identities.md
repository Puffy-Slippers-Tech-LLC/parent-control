# E02 — Resolve stable evidence identities

Acceptance: host
Requires: E01b

## Purpose and delivery

Implement the frozen [specific reference contract](../Export-Design.md#stable-and-specific-references)
using the existing manifest, receipt and accepted-locator reader. Follow the
[master](../Export-Execution-Plan.md). Read complete `evidence_bundle.Selection`,
`verified_record`, `inspect`, `plan_evidence._index`, `_verified_ledger`,
`_verify_index`, `locator`, `onpc-test-artifacts` dispatch and affected tests.

Deliver versioned identities and exact-record resolution bound to owner,
repository, task/check/attempt, target, source/inputs, original member/digest,
verdict and command/cleanup dependencies. Keep logical identities independent of
physical generations. Retain legacy readers and reject ambiguous schema upgrades.
Do not merge distinct claims because their bytes or basenames match. A generic
locator or matching filename alone cannot satisfy a requested result.
Register any new validated helper interface before invocation; no new archive
format, arbitrary extraction or caller-selected privileged write destination.
Apply the [controller compatibility guard](../Export-Design.md#controller-compatibility-guard)
in this introducing task: register changed/new relevant shared dependencies and
validate actual file changes before close-out. E07 does not defer this obligation.

## Validation and close-out

Extend `test_evidence_bundle.py`, `test_plan_evidence.py` and
`test_test_artifacts.py` as applicable with exact resolution, moved generations,
duplicate basenames, distinct attempts/inputs/targets, legacy schemas, wrong
checkout and wrong-but-existing members. Confirm access/integrity refusal remains
distinct from absence, including an unsafe live path with an older archived copy.
Use maintained host selectors with explicit timeouts; no VM or installed-product
checks. Update the owning artifact/plan contracts only for delivered behavior,
check changed links and follow the master's cleanup and close-out.
