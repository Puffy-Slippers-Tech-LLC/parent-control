# 109p — Prepare the declared Snap fixtures in the baseline

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Snap baseline assets and FIX06 verification**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — shared guarded administrator package-command transport.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the maintained repository-owned Snap payloads, fixture builder/artifact
cache and pinned A/H/S manifest. FIX04 transfers bytes only. Implement the finite
reusable declaration in `tools/prepare-baseline`, using the shared package helper
for the supported local installation command and required Snap base. Reconcile
matching state without reinstalling it and bind fixture sources to baseline identity,
preserving manifest/digest verification, any supplied signatures, the fixture's
declared trust, confinement and package-manager checks.
No Snap Store account, publishing/signing service, channel matrix or online
refresh is required. Stop at installed fixture/catalogue identity; command and
app-grid behavior belong to their following tasks.

## Live VM acceptance

Qualify first preparation, unchanged repetition, owned updates and interrupted
retry through the baseline route. After ordinary restore in a fresh guarded
attempt, verify installed digests, confinement, scope and launcher identities
without installing or repairing anything. Independently observe public Parent
catalogue identities/default rules. Refuse wrong manifests, recipient, stale
baseline or failed installation, with baseline-refresh guidance.
An unpacked launcher or host Snap smoke is not installed Snap qualification.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_snap_fixtures
```
