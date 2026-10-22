# E06a — Capture qualification and E2E collector records

Acceptance: host
Requires: E06

## Purpose and delivery

Migrate the finite standalone qualification, recovery-diagnostic and E2E collector
producer families assigned by E01, under the [master](../Export-Execution-Plan.md) and
[capture design](../Export-Design.md#capture-and-publication). Read complete
`tests/integration/qualification_storage.py`, `tests/e2e/evidence.py`, their
terminal controller/collector handoffs and registered standalone callers. Include
`qualification_storage.recovery_session()`, shared and selected-target
`recovery-diagnostics-*` journals and finalized `tests/integration/vm_probe.py`
producer records. Reuse the discovery/first-export fixes from `c8fbcd58`.

Use the shared finalized-record handoff for exact target/check/attempt records,
input manifests, original result/JUnit/TAP, commands and eventual cleanup.
Capture before source release or rotation, preserve failed/partial attempts and
keep diagnostics distinct from acceptance. Respect existing leases, privilege,
caller identity and host-versus-privileged registration; this task changes only
evidence mechanics, not VM operations, selectors, product assertions or media
policy. Split independent producer families before implementation if needed.

## Validation and close-out

Use private collector/qualification/controller fixtures without a live guest or
product. Exercise standalone and reused sessions, two target identities,
first-use storage, success/failure/interruption, late cleanup, denied helper and
rotation after capture. Assert complete original proof bytes/dependencies and
unchanged original verdicts. Extend existing evidence/qualification-storage
tests including `test_recovery_diagnostic_samples_survive_rotation`,
`test_catalogue_includes_only_selected_targets_host_and_guest_journals` and
`test_host_only_catalogue_without_privileged_storage`. Cover shared/selected-target
diagnostic capture, first export, absent optional storage versus denied access,
and required diagnostic proof surviving later report rotation. Denied access stays
a refusal; diagnostics remain nonpassing. Extend applicable safety tests, review
resource-affecting changes and run maintained scoped host checks. Update their
owning contracts and use the master's close-out.

## Frozen prerequisite insertion

E01b allocation: 150–210 min total; this consumer retains 30–45 min for all-family
composition and the original P06 acceptance. Qualification/system, recovery
diagnostic and collector families have independent finalization owners. Their
briefs preserve every original verdict, cleanup and exact-member assertion here.

When E06a is selected, before implementation insert exactly this contiguous block
immediately before it, with the existing briefs:

Brief navigation: [E06ap-qualification](E06ap-qualification.md), [E06ap-diagnostics](E06ap-diagnostics.md), [E06ap-collector](E06ap-collector.md).
The literal rows below use queue-relative destinations; copy them unchanged.

```markdown
| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | E06ap-qualification | [Capture standalone and system proof](Export-Tasks/E06ap-qualification.md) | E06 | Capture full standalone qualification and system result closure after owned cleanup with exact target provenance | 30–45 min |
| [ ] | E06ap-diagnostics | [Capture recovery diagnostic families](Export-Tasks/E06ap-diagnostics.md) | E06ap-qualification | Capture all shared and target recovery diagnostic producers while preserving partial status, finite tails and true cleanup scope | 45–60 min |
| [ ] | E06ap-collector | [Capture post-cleanup E2E closure](Export-Tasks/E06ap-collector.md) | E06ap-diagnostics | Capture authoritative post-cleanup E2E closure with exact collector inventory, original failures and declared media lifetime | 45–60 min |
```

Exact E06a Requires before: `E06`; after: `E06, E06ap-collector`.
At insertion update this brief's top-level Requires to that same after field.
Each new brief declares `Acceptance: host`, no Targets. No live VM, installed
qualification or product acceptance enters these scopes. Preserve original E06a
Scope/acceptance/assertions and every other row under the
[shared insertion route](../../Execution-Plans.md#execution-and-delegation) and
[frozen guards](../Export-Design.md#frozen-insertion-guard-review).
After owned cleanup, point to E06ap-qualification and return
`prerequisite_required` or valid `continue` with the suspended consumer handoff;
do not run prerequisites or edit checkpoints. After resumption verify all mapped
producer families, first export, absent-versus-denied storage and rotation together.
