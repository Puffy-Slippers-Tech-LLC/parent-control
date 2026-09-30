# 109p — Install the declared Snap fixtures

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FIX04 Snap assets; LIFE04 fixed Snap installation profile**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — LIFE04 install only.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse the maintained repository-owned Snap payloads, fixture builder/artifact
cache and pinned A/H/S manifest. FIX04 transfers bytes only. Bind the supported
local installation command in the shared administrator SSH package helper,
preserving manifest/digest verification, any supplied signatures, the fixture's
declared trust, confinement and package-manager checks.
No Snap Store account, publishing/signing service, channel matrix or online
refresh is required. Stop at installed fixture/catalogue identity; command and
app-grid behavior belong to their following tasks.

## Live VM acceptance

In a fresh guarded attempt, stage and install the declared Snap fixtures and
independently read real bounded command completion and their public Parent catalogue
identities/default rules. Refuse wrong manifests, recipient or failed installation.
An unpacked launcher or host Snap smoke is not installed Snap qualification.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_snap_fixtures
```

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the callable and exact qualified scope in the
[catalogue](../E2E-Building-Blocks.md), check **109p** only after acceptance and
cleanup, advance to the following unchecked row, and delete this brief after
enduring context is maintained. The complete scenario stays in its own task.
