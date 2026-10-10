# 109p — Prepare the declared Snap fixtures in the baseline

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Snap baseline assets and FIX06 verification**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — shared guarded administrator package-command transport.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the maintained repository-owned Snap payload, fixture builder/artifact
cache and add the finite A/H/S identity declaration. FIX04 transfers bytes only.
Implement the finite
reusable declaration in `tools/prepare-vm`, using the shared package helper
for the supported local installation command and required Snap base. Reconcile
matching state without reinstalling it and bind fixture sources to baseline identity,
preserving manifest/digest verification, any supplied signatures, the fixture's
declared trust, confinement and package-manager checks.
No Snap Store account, publishing/signing service, channel matrix or online
refresh is required. Stop at installed fixture/catalogue identity; command and
app-grid behavior belong to their following tasks.

## Live VM acceptance

Exercise idempotence, owned updates, interrupted retry and invalid manifests in
the existing baseline/ownership host regressions, limited to the added profile.
Reuse unchanged reconciliation qualification. Qualify one real baseline
installation of the declared Snap identities. After restore in a fresh guarded
attempt, verify installed digests, confinement, scope and launcher identities
without installing or repairing anything. Independently observe public Parent
catalogue identities/default rules. Refuse wrong manifests, recipient, stale
baseline or failed installation, with baseline-refresh guidance.
An unpacked launcher or host Snap smoke is not installed Snap qualification.

`build_test_applications._build_snap` currently emits one strict `core26`
package named `onpc-test-application`; it does not supply independently
controlled A/H/S identities. Extend that existing builder and
`baseline_fixtures` only for the recipe's finite roles, then extend FIX06's
read-only verifier. Baseline source identity and actual confinement/launcher
readback remain required. No readiness is claimed by the existing single-payload
host smoke, and workers must not install missing packages.

Qualification selector (planned; implement and register before use). Qualify
independent installed readback and this profile's wrong-scope/owner refusal;
retain shared runtime and cleanup guards without replaying unrelated baseline
preparation histories.

```sh
tools/run-tests integration check_e2e_snap_fixtures
```
