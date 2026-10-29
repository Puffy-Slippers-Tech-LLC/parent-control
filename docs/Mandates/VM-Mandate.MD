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
| `tools/prepare-vm` | Same queue selectors | `all`, including disabled entries, in both modes | Registry concurrency cap; isolated workers |
| `tools/prepare-appsnapshot` | Same queue selectors | Enabled queue | Registry concurrency cap; isolated workers |
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
`--vm`. Tests use one pending case queue per selected family: an available VM
atomically claims its next case, so each case executes once per family. The same
pull mechanism serves one or more VMs. Claims cannot overlap on a case identity;
failed or interrupted claims retain their owner through cleanup and recovery.
Stateful histories and system area attempts remain indivisible. Each VM runs
one attempt at a time, retaining its own lease and journals.
Preparation remains per VM: each free slot takes the next registered VM, and
the preparation queue drains even after an individual VM fails.
Baseline helper refresh runs once after preparation workers finish.
Cancellation stops queued work and waits for active cleanup; an active baseline
replacement finishes before returning cancellation because it has no cooperative
stop protocol. Multiple preparation selections are confirmed together before
workers start; apply the mode authorization and `--y` rules in
[baseline preparation](#vm-host-setup-and-baseline).
For either preparation tool, automation and agent sessions use `--y` only for
authorized preparation; interactive work omits it to retain confirmation.
App-snapshot preparation is always online and defaults to overwriting. Every
unattended invocation explicitly supplies `--overwrite true` or `--overwrite false`;
see [the preparation contract](../Approval-Tools.md#one-time-setup).

### Owned maintenance and execution

Operate the selected, individually pinned VM only through maintained
preparation/execution routes and `tools/test-vm` for maintenance. Do not bypass
ownership or create snapshots, overlays or clones outside those routes. Stop
maintenance before system/E2E tests; reset is not a customer journey step.

Request running-guest shutdown and reboot through the shared, owned SSH
transport. Never inject a virtual power-button request: an inactive desktop
can hold its handler and leave the VM running. Independently observe the exact
owned instance off or its changed boot before claiming success. Preserve
single-use input and uncertain-reply guards. Baseline maintenance stages
temporary SSH access through the existing offline bootstrap; initial baseline
guest preparation owns its local service's poweroff before SSH is available.
Before that transport exists, preserve the preparation journal on a host error
instead of injecting a power key. Snapshot restoration remains the existing
guarded reset/recovery operation, outside customer journeys.

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

### Central VM checkout

The shared [VM pool](../../tools/vm_pool.py) is the bookkeeper for maintained VM
preparation, execution, maintenance and recovery. The VM host owns one kernel
checkout per domain UUID in `/run/onpc-vm-pool/`. Repository roots, branches,
worktrees, driver types and the machine initiating a request do not select a
different lock. Remote drivers submit through the VM host's maintained helper;
they must not substitute a lock on the driver machine.

This is advisory coordination for participating tools and drivers. Manual
virt-manager GUI use remains unrestricted and outside the pool. Do not patch or
intercept virt-manager, hook libvirt operations, or change access controls to
enforce checkout. The pool therefore does not promise exclusion against manual
GUI actions; existing driver identity and lifecycle guards still apply.

An occupied VM queues requests automatically until checkin. Other VM UUIDs
remain independent. The manager never expires or steals an occupied checkout.
Existing identity, provenance, unfinished-journal and recovery checks still run
after acquisition; waiting does not authorize taking over an unfinished guest.
Read-only watch observation remains independent and never holds a checkout.

A reservation covers a sequence of commands, including builds and investigation
after failure. Nested commands borrow it; their completion cannot check in the
enclosing driver. Single-VM test/repair and preparation owners retain it through
their workflow. Batch workers reserve independently; a batch controller reserves
no VMs itself. Each worker recovers its own VM before testing, under that same
reservation; one occupied VM must not delay admission of another free worker.
Other drivers and interactive investigation use the shared route:

```sh
tools/vm-pool --vm NAME -- COMMAND ARGUMENTS
```

The command runs as its original user. Its VM commands carry the checkout receipt
through maintained dispatchers. Keep this command/session alive while inspecting
the VM or preparing the next probe. Ending it checks in once its active borrowed
commands also finish. Kernel descriptor lifetime handles exit and crashes; no
stale-file deletion or PID-based lock stealing is needed.

The implementation uses ordinary file locks and a receipt, with no socket
protocol or service to operate. A short admission gate serializes new owners;
the reservation and its commands hold shared lifetime locks. A new owner waits
for exclusive lifetime ownership. Borrowing never takes the admission gate,
so nested commands can finish while the next owner waits.

A reserved driver may attach only to workflows started under its own receipt.
Joining another workflow could wait for a request queued behind that driver.
Such attachment refuses immediately; cancellation remains available so the
driver can stop the queued workflow without checking in first.

One request chain reserves one VM at a time. A nested request for another VM
refuses before waiting: check in first, or use independent workers. This removes
circular hold-and-wait between VMs. Trusted in-process lifecycle stages borrow
their enclosing controller descriptor. Ordering is VM checkout, checkout-local
activity, controller operation, then any archive lock. Package workers do not
reacquire the parent's activity lock. Never stop a foreign VM/process or clear
its journals/locks to make room. A self-conflicting controller refusal is an
infrastructure error to diagnose, never a product assertion or a reason to clear
ownership.

### Host disk queue

The shared [disk admission helper](../../tools/host_disk.py) serializes expensive
disk operations across all participating VMs, users and checkouts on the host.
Actual snapshot creation/restoration, guest product package transactions, host
package builds and disaster-recovery file copies use this same queue. VM
reservations remain independent; other work on a reserved VM can proceed while
another VM owns the disk slot. Manual virt-manager actions remain outside this
advisory coordination.

Root-owned tickets under `/run/onpc-vm-pool/disk/` establish strict FIFO order at
admission. Pending operations wait without expiring or stealing a live ticket.
Kernel locks and inherited command descriptors retain the slot until its last
owned command finishes. Cancelled or crashed requests are retired only after
the kernel proves their ticket unowned. Queue records are ephemeral coordination;
the existing durable journals, recovery and identity guards remain authoritative.

Nonroot builders use the existing privileged test dispatcher as a lifetime
keeper; their build commands still run as the original user. No separate service
or host product installation is involved. Setup refreshes that dispatcher through
`./setup.sh --test-tools-only`; missing admission infrastructure fails explicitly.

Acquire VM checkout, activity, controller and archive ownership before disk
admission. Hold the slot only across the finite disk operation, never while
requesting another VM or waiting for a child controller that needs those locks.
In-process nested work borrows its slot. Spawned commands must inherit both
`host_disk.descriptors()` and `host_disk.environment()` so nested builders borrow
the same lifetime instead of queuing behind their parent. Independent parallel
builders each request their own ticket; cancellation prevents pending builders
from entering. Keep existing command timeouts, private-input filtering and watch
observation, and revalidate ownership and operation inputs after queue admission.

Guest package operations retain admission through owned shutdown when SSH
completion is uncertain. Simultaneous abrupt controller and SSH death can still
leave guest work running after the host descriptor disappears; inherited host
descriptors do not prove remote completion. The recorded VM ownership and
recovery routes remain necessary in that case.

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
- Runner-owned recordings reuse the same watch renderer and shared feeds under
  the [recording contract](../../tests/README.md#vm-watch-recordings). They have
  no input channel or VM lifecycle authority and work without a visible viewer.
- **ONPC: Watch** observes all registered VMs without selecting a mutation target.
  Its VM panels must remain read-only, live and interruption-free.
  The left runner terminal may request its displayed command's cooperative
  cancellation, including the owned cleanup of a VM test; it never sends direct
  input to the VM. Users can
  connect, disconnect and reconnect at any time, including between maintenance
  commands, without affecting VM operations. Viewer lifetime must never control
  the VM, its input, command execution or collector lifetime. Qualify new routes
  for intent-before-action, live screen/SSH visibility and independent viewing.

## VM-host setup and baseline

- All reusable, one-time environment prerequisites belong to `tools/prepare-vm`:
  dependencies and persistent harness
  settings. Runners, cases and app-snapshot preparation only verify them. Missing
  or stale prerequisites fail with baseline-refresh guidance; no on-the-fly
  installation, repair or alternate preparation route is permitted in tests.
  Attempt-specific SSH identities, evidence/transport state, product packages
  under test and deliberate scenario mutations remain attempt-owned. Do not
  preseed product policy, grants, usage or a scenario's expected result.
  Ubuntu 26.04 and Fedora 44 schema-4 baseline and app captures exclude movable fixture
  payloads, admissions and copied fixture sources. Their host-owned inputs use
  the [shared SSH provisioner](../../tests/support/README.md#attempt-owned-fixture-provisioning)
  only after target/envelope qualification; unqualified runners refuse clean
  captures before input. Reusable native, Snap, Flatpak and game
  dependencies remain environment-owned; pending capabilities still require
  shared preparation and read-only verification before use. A package
  change explicitly exercised by a catalogue/update/removal case remains a
  scenario mutation; it is not an on-the-fly prerequisite repair.
- Preparation is an idempotent reconciliation of a finite declared inventory.
  Reuse matching state without rewriting it, update only proven owned inputs,
  preserve unrelated files/accounts/settings, and safely resume partial work.
  Refuse links, foreign ownership, ambiguous state and unexpected collisions.
  Verify bytes, modes, owners and configuration before capture; bind environment,
  runtime dependency and shared lifecycle sources to baseline identity. Legacy
  captures additionally bind their embedded fixture sources. The shared
  [clean boundary](../../tests/integration/Environment.md#ubuntu-clean-snapshots),
  including [Fedora policy verification](../../tests/integration/Environment.md#fedora-clean-snapshots),
  preserves fixture-only independence, exact legacy retirement and old recovery.
  Keep first-run, repeat, update and interrupted-retry behavior safe. Existing
  coverage follows the [test scope mandate](Test-Scope-Mandate.md) at the shared
  dangerous reconciliation boundary.
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
