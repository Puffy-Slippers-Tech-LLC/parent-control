# 116p — Install the declared Flatpak fixtures

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FIX04 Flatpak assets; LIFE04 fixed Flatpak installation profile**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — LIFE04 install only.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the maintained repository-owned A/H/S Flatpak bundles, pinned runtime and
fixture builder/artifact cache. FIX04 transfers bytes only. Bind their local
installation commands and one declared installation scope in the shared
administrator SSH package helper. No Flathub browsing, third-party remote setup, online
runtime search or installation-scope matrix is needed. Preserve real Flatpak
installation and confinement; launching and activity remain in following tasks.

## Live VM acceptance

In a fresh guarded attempt, install the declared runtime and app bundles, read
real command completion and independently observe the exact Parent catalogue
identities/default rules. Refuse wrong installation scope, manifest or recipient.
Host user-installation evidence does not qualify this installed guest route.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_flatpak_fixtures
```

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the callable and exact qualified scope in the
[catalogue](../E2E-Building-Blocks.md), check **116p** only after acceptance and
cleanup, advance to the following unchecked row, and delete this brief after
enduring context is maintained. The complete scenario stays in its own task.
