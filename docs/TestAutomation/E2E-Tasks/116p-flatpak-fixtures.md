# 116p — Prepare the declared Flatpak fixtures in the baseline

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Flatpak baseline assets and FIX06 verification**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — shared guarded administrator package-command transport.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the maintained repository-owned Flatpak bundle/runtime and add the finite
A/H/S identity declaration to the existing fixture builder/artifact cache.
FIX04 transfers bytes only. Reconcile the runtime
and bundles through `tools/prepare-vm` in one declared installation scope,
using the shared package helper. Reuse matching state and bind sources to baseline
identity. No Flathub browsing, third-party remote setup, online
runtime search or installation-scope matrix is needed. Preserve real Flatpak
installation and confinement; launching and activity remain in following tasks.

## Live VM acceptance

Exercise idempotence, owned updates, interrupted retry and invalid scope/manifests
in the existing baseline/ownership host regressions, limited to the added profile.
Reuse unchanged reconciliation qualification. Qualify one real baseline
installation of the declared runtime/app identities. After restore in a fresh
guarded attempt, verify runtime/app digests, installation scope, confinement and launchers
without installing or repairing anything. Independently observe the exact Parent
catalogue identities/default rules. Refuse wrong scope, manifest, recipient or
stale baseline, with baseline-refresh guidance.
Host user-installation evidence does not qualify this installed guest route.

`build_test_applications._build_flatpak` currently emits one `APP_ID` and pinned
runtime, not three independently controlled A/H/S identities. Extend that
builder/declaration and `baseline_fixtures` for only the required finite roles,
then extend FIX06 read-only verification. Preserve the real selected installation
scope and confinement; the existing host-only `prepare_flatpak` user installation
is not a guest baseline implementation.

Qualification selector (planned; implement and register before use). Qualify
independent installed readback and this profile's wrong-scope/owner refusal;
retain shared runtime and cleanup guards without replaying unrelated baseline
preparation histories.

```sh
tools/run-tests integration check_e2e_flatpak_fixtures
```
