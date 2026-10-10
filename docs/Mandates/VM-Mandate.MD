# VM mandate

This mandate owns VM target selection, observation, leases and preparation
lifetime. [Approval tools](../Approval-Tools.md) owns command grants;
[test maintenance](../../tests/README.md#all-established-regressions) owns runner
scheduling and [E2E execution](../TestAutomation/E2E-Execution-Contracts.md#live-verification-contract)
owns task acceptance. A documentation-only reconciliation performs no VM work
and supplies no live qualification.

## Authority and operation

Apply the repository-wide [approval contract](../Approval-Tools.md) to all VM
work. Run authorized work unattended through its existing grants and validated
tools. Reuse session and category-wide authorization; do not broaden libvirt
grants or bypass a missing prerequisite or grant.

### Target selection

Select from [the VM registry](../../config/test-vm.json) using the tool's supported
selector. The enabled default means entries whose `enabled` is the string
`"true"`; an explicit name/ID or `all` also includes disabled entries.

| Tool | Explicit selector | When omitted | Scheduling |
| --- | --- | --- | --- |
| `tools/run-tests`, `tools/fix-tests` | Name/ID, comma-separated list, `all-enabled`, `all` | Enabled queue for VM work | Registry concurrency cap |
| `tools/prepare-vm`, `tools/prepare-appsnapshot` | Same queue selectors | Enabled queue | Registry concurrency cap; isolated workers |
| `tools/backupvm`, `tools/restorevm` | Same queue selectors | `all`, including disabled entries | Archive work is serial; preparation after restore uses registry concurrency |
| `tools/write-e2e` | One registered name or ID | Enabled queue | Registry concurrency cap |
| `tools/cleanup-e2e` | Same queue selectors, or `--host-only` for no VM access | Enabled queue | Serial; stops on a cleanup failure |
| `tools/test-vm` maintenance | One registered name or ID | Refuses maintenance without an explicit target | One owned target |

Duplicate aliases execute once, in first-selected order; invalid selectors fail
before work starts. Every `--vm` and Make `VM=` name/ID resolves from the current
JSON on invocation. Names are case-sensitive; IDs are unique positive decimal
strings or integers. Renumbering requires no tools refresh or baseline replacement.
Controllers retain canonical names for leases, UUID pins and active-run ownership,
never a saved ID mapping. Queue selectors do not imply that every Make entry
point accepts a queue; use the public launcher's help.

The positive integer `concurrency` caps parallel queue operations with or without
`--vm`. Each free slot immediately takes the next VM; the finite execution or
preparation queue drains even after an individual VM fails. Tests within each VM
remain ordered. Baseline helper refresh runs once after preparation workers finish.
Cancellation stops queued work and waits for active cleanup; an active baseline
replacement finishes before returning cancellation because it has no cooperative
stop protocol. Multiple preparation selections are confirmed together before
workers start; apply the mode authorization and `--y` rules in
[baseline preparation](#vm-host-setup-and-baseline).
For either preparation tool, automation and agent sessions use `--y` only for
authorized preparation; interactive work omits it to retain confirmation.

### Owned maintenance and execution

Operate the selected, individually pinned VM only through maintained
preparation/execution routes and `tools/test-vm` for maintenance. Do not bypass
ownership or create snapshots, overlays or clones outside those routes. Stop
maintenance before system/E2E tests; reset is not a customer journey step.

Disaster recovery uses the scoped `tools/backupvm` and `tools/restorevm`
routes described in [the environment guide](../../tests/integration/Environment.md#vm-disaster-recovery).
Both retain exclusive per-VM leases and shared observation. Backup restores the
existing accepted baseline, deletes baseline and versioned app snapshots, then
archives that powered-off baseline guest under the same lease. It does not run
guest setup or updates. Archive work runs one VM at a time and stops on failure.
Restore verifies complete checksummed generations,
refuses active domains, held leases and foreign storage references, retains displaced files and definitions, and
reconciles filesystem identities with archived evidence. Archive restoration
does not boot a guest or substitute preparation for missing backup evidence.
After successful restoration of the selection, the launcher invokes
`tools/prepare-vm --mode auto --y`. For snapshot-free archives, that route first
reconciles the verified restored guest through the shared baseline implementation,
then performs automatic preparation and app capture, ending powered off.
An unfinished restore blocks ordinary preparation/execution and helper pinning
until restoration completes. Explicit restore treats the verified restored guest
as the authority for local bookkeeping: it preserves and retires stale controller
records and superseded/damaged restore journals rather than adopting their owners
or fabricating successful results. Matching interrupted transactions resume with
their recorded identities; ordinary controllers retain their existing refusals.

Root OS investigation uses `tools/test-vm --vm NAME exec -- COMMAND [ARG ...]`
in an owned running online app-snapshot maintenance instance. Arbitrary command
arguments and root privileges apply only in the guest. Reuse its private SSH
identity, guarded transport, exclusive lease and observation; never restore the
guest to inspect it or adopt another controller's running instance.

Probing every registered VM has standing authorization, including entries disabled
for test scheduling. Direct `tools/test-vm` guest commands, including guest shells
and interpreters, require no additional command approval or developer confirmation.
The installed helper's Polkit grant is automatic for the active local administrator;
unavailable authorization fails without an authentication dialog. Retain all
identity, ownership, lease and observation checks.

Each VM has an exclusive preparation/execution lease and separate evidence journals.
New controllers also hold a shared legacy root lease, excluding older controllers
that still require it exclusively. Existing unfinished legacy journals refuse new
execution until recovered; evidence is never discarded to enable parallelism.

- **Controller contention:** Checkout activity locks do not reserve the VM
  across every category transition or exclude work from another checkout.
  For `state:busy-controller` or a launcher ownership refusal, inspect the
  retained failure location and current runner/owner through authorized
  read-only diagnostics. A refusal before acquisition is infrastructure
  contention, not a product assertion. Attach only to a matching run in the
  current checkout; otherwise let the foreign owner finish its normal cleanup.
  Do not stop its VM/processes, clear locks/journals, or refresh the baseline
  to make room. Recheck readiness through the maintained route after release,
  then retry only the affected selection. If the owner cannot finish without
  external action, report that concrete blocker and preserve completed results.

## VM observation mandate

- Every VM operation, experiment, qualification, setup, maintenance and test must
  use the shared `watch` infrastructure, regardless of its caller or whether it
  is E2E. Start display observation through the shared VM lease; route host/SSH
  commands through the guarded command transport and publish a nonsecret intention
  through `watch_activity.operation` (or its `observed` decorator) before performing
  work. Keep that intention in the viewer footer throughout the operation,
  including waits and cleanup; nested operations restore the enclosing intention
  when finished.
- Reuse the existing display collector, authenticated command transcript and
  progress interfaces. Do not add per-workflow viewers, SSH tails, capture loops
  or alternate intention channels. A missing integration must be fixed in this
  shared infrastructure before adding its consumer. Preserve private-input
  filtering and the existing VM ownership/identity checks.
- `tools/watch` observes all registered VMs without a VM parameter.
  Its VM panels must remain read-only, live and interruption-free.
  The left runner terminal may request its displayed command's cooperative
  cancellation, including the owned cleanup of a VM test; it never sends direct
  input to the VM. Users can
  connect, disconnect and reconnect at any time, including between maintenance
  commands, without affecting VM operations. Viewer lifetime must never control
  the VM, its input, command execution or collector lifetime. Qualify new routes
  for intent-before-action, live screen/SSH visibility and independent viewing.

## VM-host setup and baseline

- All reusable, one-time guest prerequisites belong to `tools/prepare-vm`:
  dependencies, fixed fixture applications and launchers, and persistent harness
  settings. Runners, cases and app-snapshot preparation only verify them. Missing
  or stale prerequisites fail with baseline-refresh guidance; no on-the-fly
  installation, repair or alternate preparation route is permitted in tests.
  Attempt-specific SSH identities, evidence/transport state, product packages
  under test and deliberate scenario mutations remain attempt-owned. Do not
  preseed product policy, grants, usage or a scenario's expected result.
  This includes reusable native, Snap, Flatpak and offline-game fixtures once
  implemented. Their pending capability tasks must add preparation and read-only
  verification to the shared routes before consumers can use them. A package
  change explicitly exercised by a catalogue/update/removal case remains a
  scenario mutation; it is not an on-the-fly prerequisite repair.
- Preparation is an idempotent reconciliation of a finite declared inventory.
  Reuse matching state without rewriting it, update only proven owned inputs,
  preserve unrelated files/accounts/settings, and safely resume partial work.
  Refuse links, foreign ownership, ambiguous state and unexpected collisions.
  Verify bytes, modes, owners, launchers and configuration before capture; bind
  fixture sources to the baseline identity so stale baselines and derived app
  snapshots cannot pass. Cover first run, repeat, update and interrupted retry.
  Auto mode still applies available system updates and replaces snapshots as
  documented; idempotence never weakens the lease, provenance or product-free gate.
- `./setup.sh` is the sole public VM-host setup entry point. Modes must be
  retryable, preserve unrelated configuration and fail on missing prerequisites.
  Tests and builds report missing prerequisites; they do not install them.
- Baseline preparation is an explicit destructive operation through
  `tools/prepare-vm --vm NAME --mode auto` (restore and update) or
  `tools/prepare-vm --vm NAME --mode manual` (prepare the current state). Auto-mode
  refresh is preapproved when needed for authorized development or testing,
  including deletion of all versioned app snapshots and replacement of
  `onpc_baseline`. Do not ask the developer for confirmation; launcher/session
  work uses `tools/prepare-vm --vm NAME --mode auto --y` to suppress the
  y/n prompt. Manual mode still requires explicit developer authorization;
  authorized launcher/session work uses `--mode manual --y`. Interactive invocation omits
  `--y` to retain confirmation. For both preparation tools, `--y` suppresses
  warnings and confirmation. Both baseline modes require the VM off and retain
  all tool safety checks; see
  [VM prerequisites](../../tests/integration/Environment.md).
  Both modes then prepare the current online app snapshot using the standalone
  app-snapshot implementation and restore the powered-off baseline. One exclusive
  VM lock covers baseline work, package building, app preparation and final restore;
  nested stages borrow that process's lock without releasing the enclosing lease.
  Ordinary setup and E2E runners never prepare or replace it implicitly; invoke
  the preapproved auto-mode preparation separately when needed.
  Baseline preparation and E2E require the literal `TEST_ACCOUNT_PASSWORD` in the
  host's private `.envrc`; E2E never changes passwords.
