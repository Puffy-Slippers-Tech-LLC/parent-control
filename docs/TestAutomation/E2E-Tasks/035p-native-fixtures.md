# 035p — Install the declared native app fixtures

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FIX04 native assets and launcher preparation**. First scheduled consumer: [E2E-041, case 184](../E2E-Scenario-Recipes.md#e2e-041).
Read only the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope) and that consumer's selected recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — existing guarded administrator SSH command route; its product package installation is not fixture preparation.
- **077a** — PARENT12; UI13 complete public app-row observations.

Use maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

These are repository-owned mock programs, not product components or third-party
AppImages. The required product result is their discovery in Parent's App Limits.
Use one preparation route:

1. Bind A/H/S/N to a finite table of native executable paths, desktop IDs, visible
   names/descriptions and expected default match fields. Reuse the existing GUI
   fixture source and builder/artifact cache; add only the missing identities and
   launchers. A/H/S/N name later test roles: preparation leaves every app allowed.
2. Keep independently controlled role executables different in content using a
   small build-time identity in the existing source. The current native layout
   copies one binary under several names; a whitespace-path block uses content
   matching and could therefore block the unrelated control too. Identical copies
   belong only to a later case that explicitly tests that behavior.
3. Install the finite reusable declaration only through `tools/prepare-baseline`.
   Reconcile the declared executables, shared GUI files and desktop entries to
   their guest destinations idempotently; reuse matching files, update proven
   owned files and safely retry interrupted preparation.
   Set executable modes and selected-child ownership explicitly, and read back
   file digests, modes and launcher targets. Reuse shared file operations; keep
   the source/destination set finite. Do not copy the whole image-root or its
   hardcoded home directory into the guest.

Native fixture preparation is ordinary file/launcher placement, not an APT/DNF
installation. Do not add a fixture package, package-manager completion notice,
reboot, new installer framework, vendor download or store UI. Reuse available
guest Python/GTK prerequisites through baseline and report missing dependencies.
Keep fixtures outside the shipped app. Attempts independently verify baseline
files through guarded SSH and never install or repair them. Baseline restoration
restores the accepted reusable set. Stop at catalogue identities/default
rules; launch and usability belong to their following slices.

## Live VM acceptance

First prepare the baseline and verify unchanged repetition, owned updates and
interrupted retries with scoped safety regressions. In a fresh guarded installed
VM attempt, independently verify the native files/launchers through the shared
guarded SSH route. Require successful readback before opening Parent's App Limits, then
independently observe each declared launcher and its default access/match fields
through PARENT12/UI13. Reopening the catalogue must show the same fixture set.
Do not count a manifest entry or copied file as an observed catalogue row, or
seed app policy. Missing supported assets or public catalogue identities block
this consumer.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_native_fixtures
```

The selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract).
Require independent valid entry, wrong-entry refusal and owned live VM cleanup.
Host checks and a diagnostic slice do not establish complete scenario coverage.

## Close out

### Remaining acceptance

`check_e2e_native_fixtures` failed at `native_fixtures.check_catalogue()`'s
`native:catalogue-defaults` comparison in `20261001T013104Z-7f771800` on
`onpc-Ubuntu26.04`. Expected: the four declared public IDs, all Allowed, with
precise A/H/N and pattern S match defaults. Actual: the complete Allowed row
projection did not match that declaration; the failing row values were not
persisted. Diagnose missing identities versus differing match defaults without
changing expectations. Guarded readback of ten native files, independent readback,
wrong-entry refusal, worker shutdown, owned cleanup and baseline restoration
passed. Reopening/refusal checks after the initial rows and collection did not run.

All five affected enforcement selectors passed independently on the same VM:
`test_native_command_policy_is_uid_scoped` (`20261001T012425Z-6fe43b31`),
`test_native_whitespace_policy_is_uid_scoped` (`20261001T012528Z-7d3ebc75`),
`test_native_future_pattern_is_uid_scoped` (`20261001T012631Z-39fb526c`),
`test_native_missing_launcher_retains_policy` (`20261001T012740Z-95877d40`) and
`test_native_catalog_is_selected_child_scoped` (`20261001T012844Z-b9cc122c`).
Their launchers returned success after collection, owned cleanup and restoration.
Focused system execution required explicit `--artifacts`; the verified shared
input was `output/test-runs/host/allocations/onpc-test-artifacts-qfs995fx`.

The first failed attempt and early enforcement reports expired under the
launcher's three-run retention. The repeated qualification reproduced the same
comparison failure; preserve its separate bounded exports before further exports
or runs rotate them:

- [Failure report](../../../output/test-runs/host/exports/onpc-artifact-export-_nccy_yt/report.md)
- [Detailed runner output](../../../output/test-runs/host/exports/onpc-artifact-export-bduvt33l/category-001.log)
- [Worker failure locations](../../../output/test-runs/host/exports/onpc-artifact-export-_6tx3fai/worker-result.json)

Keep 035p unchecked, FIX04 native qualification pending and the pointer here.
Resume close-out only after catalogue/defaults, independent reopening and
collection pass with owned cleanup and baseline restoration.

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **035p** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
