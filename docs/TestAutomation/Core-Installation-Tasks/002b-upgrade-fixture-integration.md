# 002b — Integrate qualified fixtures into case 287

Acceptance: host

Requires: 002a.

## Scope and route

Finish only the consumer change left after
[002a qualification](../Core-Installation-Coverage-Handoff.md#task-002a-trusted-native-fixture-qualification).
Read [003's complete requirements](003-previous-package-upgrade.md),
`tests/integration/system_previous_upgrade.py`, the closed variant interfaces
in `system_enforcement.py`, `system_trusted_fixtures.py`, and their host tests.
Use the [shared fixture ownership contract](../../../tests/integration/Environment.md#reusable-preparation-ownership).

Replace `command` / `whitespace` consistently with the qualified `trusted-hard` /
`trusted-soft` variants in provisioning, saved target/desktop choices, strict
soft denial before authentication, native rule evidence, and pre/post-upgrade
child/unrelated-user launches. Preserve all policy, grant, identity, migration,
real Polkit and admission assertions. Do not change distro policy, add trust in
the consumer, modify the earlier releases, or remove the unrelated-user control.
Inspect existing work before editing shared fixture files.

## Acceptance and close-out

Run focused `test_system_previous_upgrade.py` regressions plus affected closed
fixture-interface, provenance and history tests through `tools/run-tests unit`.
Assert consistent variants in setup and both enforcement checkpoints, including
the strict soft denial before approval. Review unchanged resource ownership;
follow [host parallelism review](../../../tests/README.md#host-test-parallelism-review)
if helpers/resources change. Refresh generated coverage if collection changes;
check Markdown links and the plan. No installed qualification occurs here.

Record the final helper/input requirements for 002c/002d in their existing briefs
or the master. Mark only 002b complete and advance the sole pointer. Leave 003
unchecked; the older Ubuntu result supplies no acceptance for these final inputs.
