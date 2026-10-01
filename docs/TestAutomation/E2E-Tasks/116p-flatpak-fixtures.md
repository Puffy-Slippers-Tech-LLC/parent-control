# 116p — Prepare the declared Flatpak fixtures in the baseline

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Flatpak baseline assets and FIX06 verification**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — shared guarded administrator package-command transport.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the maintained repository-owned A/H/S Flatpak bundles, pinned runtime and
fixture builder/artifact cache. FIX04 transfers bytes only. Reconcile the runtime
and bundles through `tools/prepare-baseline` in one declared installation scope,
using the shared package helper. Reuse matching state and bind sources to baseline
identity. No Flathub browsing, third-party remote setup, online
runtime search or installation-scope matrix is needed. Preserve real Flatpak
installation and confinement; launching and activity remain in following tasks.

## Live VM acceptance

Qualify first preparation, unchanged repetition, owned updates and interrupted
retry through the baseline route. After ordinary restore in a fresh guarded
attempt, verify runtime/app digests, installation scope, confinement and launchers
without installing or repairing anything. Independently observe the exact Parent
catalogue identities/default rules. Refuse wrong scope, manifest, recipient or
stale baseline, with baseline-refresh guidance.
Host user-installation evidence does not qualify this installed guest route.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_flatpak_fixtures
```
