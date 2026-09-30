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
3. Use FIX04 to transfer the verified payload, then one fixed preparation helper
   over the existing guarded administrator SSH transport to copy only the declared
   executables, shared GUI files and desktop entries to their guest destinations.
   Set executable modes and selected-child ownership explicitly, and read back
   file digests, modes and launcher targets. Reuse shared file operations; keep
   the source/destination set finite. Do not copy the whole image-root or its
   hardcoded home directory into the guest.

Native fixture preparation is ordinary file/launcher placement, not an APT/DNF
installation. Do not add a fixture package, package-manager completion notice,
reboot, new installer framework, vendor download or store UI. Reuse available
guest Python/GTK prerequisites and report any missing dependency. Keep fixtures
outside the shipped app, prepare them afresh in each owned attempt and let the
existing baseline restoration remove them. Stop at catalogue identities/default
rules; launch and usability belong to their following slices.

## Live VM acceptance

In a fresh guarded installed VM attempt, stage the declared assets and prepare
the finite native files/launchers through the shared guarded SSH route. Require
successful preparation/readback before opening Parent's App Limits, then
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
