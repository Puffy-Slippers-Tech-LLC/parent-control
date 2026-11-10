# VM mandate

This mandate owns VM target selection, observation, leases, preparation
lifetime and timing resilience for VM tests.
[Approval tools](../Approval-Tools.md) owns command grants;
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

Select from [the VM registry](../../config/environment.json) using the tool's supported
selector. A VM is eligible only when both its own `enabled` and its host's
`enabled` are the string `"true"`. Otherwise it is offline: every queue selector,
including explicit lists and `all`, skips it. An empty selection or direct
maintenance of one offline VM refuses before access.
Already-owned stop/recovery retains its guarded cleanup route after a flag is
disabled; it does not authorize starting new work on that VM.
The [host configuration](../../tests/integration/Environment.md#shared-vm-configuration)
owns transport availability and the tracked/private configuration boundary.

Each VM may specify `owning_branch`: omitted or `""` allows any branch; a nonempty
value reserves that VM for the exact Git branch name in the invoking checkout
(including linked worktrees). Automatic queues and `all` omit branch mismatches;
explicit names/IDs refuse them before checkout. Detached HEAD or unavailable Git
can use only unrestricted VMs. Branch restrictions also apply to new shared-pool
reservations, regardless of `enabled`. Existing reservations may finish their
owned work and cleanup after a branch change; read-only registry discovery is
unfiltered. Direct maintenance also checks the branch before mutation, while
observations and owned `stop`/`recover-online` remain available for inspection
and cleanup.

| Tool | Explicit selector | When omitted | Scheduling |
| --- | --- | --- | --- |
| `tools/run-tests`, `tools/fix-tests` | Name/ID, comma-separated list, `all-enabled`, `all` | Enabled queue for VM work | Registry concurrency cap |
| `tools/prepare-vm` | Same queue selectors | `all` online entries, in both modes | Registry concurrency cap; isolated workers |
| `tools/prepare-appsnapshot` | Same queue selectors | Enabled queue | Registry concurrency cap; isolated workers |
| `tools/backupvm`, `tools/restorevm` | Same queue selectors | `all` online entries | Archive work is serial; preparation after restore uses registry concurrency |
| `tools/write-e2e` | One registered name or ID | Enabled queue | Registry concurrency cap |
| `tools/cleanup-e2e` | Same queue selectors, or `--host-only` for no VM access | Enabled queue | Serial; stops on a cleanup failure |
| `tools/test-vm` maintenance | One registered name or ID | Refuses maintenance without an explicit target | One owned target |
| `tools/disable-extension` | One registered name or ID | Refuses without an explicit target | Existing owned running maintenance target; no restore |

Duplicate aliases execute once, in first-selected order; invalid selectors fail
before work starts. Every `--vm` and Make `VM=` name/ID resolves from the current
JSON on invocation. Names are case-sensitive; IDs are unique positive decimal
strings or integers. Renumbering requires no tools refresh or baseline replacement.
Controllers retain canonical names for leases, UUID pins and active-run ownership,
never a saved ID mapping. Queue selectors do not imply that every Make entry
point accepts a queue; use the public launcher's help.

The host's positive integer `concurrency` caps parallel queue operations with or without
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

Explicit blank-VM provisioning uses
[`tools/newvm`](../../tools/newvm) and the
[creation contract](../../tests/integration/Environment.md#creating-a-blank-vm).
It defines a fresh powered-off VM and registers it disabled, without booting
or creating snapshots. Explicit red confirmation may replace an existing registry
entry and, separately, recreate a powered-off libvirt VM and erase its disk under
the creation contract's layout, reference and recorded-state guards. Replacement
holds the host's shared UUID checkout through the finite operation; the fixed
`pool-provision` helper grants only that checkout, with no guest execution or
lifecycle authority. This provisioning route may target a disabled host or VM;
it is separate from registered maintenance and requires no running-guest display
observation. Subsequent guest work uses
the normal selection, observation and ownership rules below.

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

During a test, `tools/test-vm --vm NAME probe memory` requests a fixed read-only
sample from that VM's active owner. It acquires no checkout or controller lease,
opens no retention session and receives no SSH credentials or reservation receipt.
Only the installed authenticated helper for the owner's caller may request it.
The owner serializes probes using separate command state and guarded SSH; returns
bounded memory, swap, page-fault, OOM and memory-pressure counters with run,
domain-instance and boot identity; and publishes the result through shared Watch.
Known lifecycle operations drain the probe before changing or releasing the VM.
Guest-initiated transitions can make a sample unavailable; successful samples
identify their observed boot and are instantaneous observations, not guarantees
of future readiness. Missing owners/transports and probe failures refuse without
starting, restoring or repairing the guest or changing the test verdict.
Arbitrary `exec`, test cases, preparation and recovery retain exclusive access.

Probing every eligible registered VM has standing authorization. Offline entries
must first be enabled together with their host. Direct `tools/test-vm` guest commands, including guest shells
and interpreters, require no additional command approval or developer confirmation.
The installed helper's Polkit grant is automatic for the active local administrator
or the explicitly configured [headless automation account](../Approval-Tools.md#one-time-setup);
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
Launcher shutdown uses a nonwaiting checkout for final recovery: an occupied
VM is left with its current owner and recovery is deferred to the next run.
Already owned nested work still finishes cleanup before the launcher exits.
Read-only watch observation remains independent and never holds a checkout.
Owner-serviced fixed diagnostics likewise grant no checkout or execution authority
to their requester; they run under the existing owner's lifetime.

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
Each physical host has its own FIFO queue and admits one operation at a time.
Operations on different hosts proceed independently; the controller must not
reserve its own disk slot for work performed on an SSH host.
Actual snapshot creation/restoration, guest product package transactions, host
package builds and disaster-recovery file copies use this same queue. VM
reservations remain independent; other work on a reserved VM can proceed while
another VM owns the disk slot. Manual virt-manager actions remain outside this
advisory coordination.

The local package Make targets (`build`, `updateversion`, `build-rpm`, `srpm`,
`rpm-source`) are reserved for humans and explicitly skip disk admission.
Agents and automation invoke `tools/build_package.py` directly in its default
queued mode, or use existing queued build APIs/test launchers. Terminal
availability does not identify a human caller; this is an entry-point contract.
The human route does not release an inherited slot or bypass VM ownership,
storage or package validation guards.

Root-owned tickets under `/run/onpc-vm-pool/disk/` on each executing host establish
strict FIFO order at admission. Pending operations wait without expiring or
stealing a live ticket.
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
In-process nested work borrows its slot. Acquire admission on the machine doing
the disk work: host-side snapshot helpers use their own host's queue, and local
builders use the build host's queue. Do not wrap remote helper dispatch in a
controller-local reservation. Descriptors cannot be inherited across SSH;
remote helpers acquire their own tickets. Spawned commands on the same host must inherit both
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

## Timing and slow-VM resilience

Design VM tests to tolerate a substantially slower guest or controller without
rushing input in the last seconds of a countdown. Apply this during planning,
implementation, qualification and repair, including engineering histories and
customer E2E. Use existing shared waits and observers; cases own their finite
inputs and assertions. Do not add a timing framework or a per-task copy of these
rules.

- **Prepare with ample headroom.** Complete fixture, application, session and
  observer readiness before starting a short measured interval wherever the
  required history permits. Use a comfortably long attempt-owned setup or
  recovery grant when its expiry is incidental. Authentication must have room
  for prompt discovery, a fresh recipient check, password delivery, submission
  and independent result observation. For example, a 20-minute kiosk grant with
  authentication begun about five minutes before expiry avoids the race through
  the last 30 seconds. These values illustrate margin, not required
  durations, waits or a literal slowdown multiplier. Do not wait for an
  incidental grant to expire; use the scenario's authorized next action or
  owned cleanup.
- **Separate measured behavior from test overhead.** Preserve the specified
  product response bound and its original trigger, grant or expiry. Give
  navigation, authentication, transport, retained-work checks and recovery
  their own ample finite budgets when they do not measure that bound. A timely
  lock observation and a later functional input challenge are different
  assertions; neither a late lock nor successful input proves timely locking.
  A history that enters an already locked session cannot prove natural lock
  onset. Keep genuinely timed expiry intervals short after preparation; do not
  extend the behavior under test to hide a slow test.
- **Control ordering instead of relying on speed.** For a required crossing
  such as expiry during authentication, establish the genuine challenge and
  ready the observation with comfortable lead time before the original
  boundary. Use supported public readiness/order gates where available. Do not
  assume a policy write is possible while authentication owns a transaction,
  or substitute an internal state injection in customer acceptance. If the
  available route cannot establish the required order reliably, report that
  concrete gap rather than accepting a lucky pass.
- **Allow long load pauses.** A heavily loaded VM can stop responding for one
  or two minutes. Finish ordinary app input and recipient preparation with
  enough headroom for that pause; do not make successful input in a countdown's
  final seconds a prerequisite for observing expiry. Arm read-only observation
  early and leave transport/reply margin around the complete wait. When timing
  matters, retain same-boot guest observation times so a delayed reply does not
  become product latency. An unobserved interval cannot prove timely enforcement;
  preserve that uncertainty rather than infer a timely lock from a later state.
  For a calendar deadline, project the original guest observation bracket
  directly through the same-boot clock bracket. Combining an initial sample
  interval with an elapsed interval counts their shared endpoint's uncertainty
  twice. Keep the original product bound and measured uncertainty; do not widen
  the bound to compensate for that arithmetic.
- **Wait for state and return promptly.** Replace arbitrary settling sleeps,
  repeated full discovery and unrelated checks with the required scoped
  observation. Retain every fresh input-recipient guard and independently
  observe the result under the [UI mandate](UI-Automation-Mandate.MD#input-and-independent-results).
  Evidence must remain tied to the original VM, boot, account, session,
  challenge and work as applicable. Increasing a failure timeout must add no
  normal-path delay; use bounded polling or the existing event observation and
  finish as soon as the result is established.
  Session numbers can repeat after reboot: compare them only within a verified
  boot. Across reboot, prove the changed boot and the required fresh usable
  desktop or app instead of requiring a different session number.
- **Budget the complete sequence.** Account for observation and transport
  costs, not just input time. Keep one monotonic deadline per bounded sequence;
  nested waits consume its remaining time and read-only retries cannot renew
  it. Leave transport margin around guest waits, including the worker's wait
  for a controller reply during natural expiry, and sufficient outer-worker
  time for the finite history and owned cleanup. A longer controller deadline
  alone cannot extend the worker's reply deadline. Do not stack fresh per-step
  timeouts, renew the measured grant, replay uncertain input or rerun until a
  favorable schedule passes. Diagnose which bound failed before changing it;
  preserve actual product timing failures under [failure handling](../../tests/README.md#handling-test-failures).

Choose and review margins from the complete history and observed slow stages,
not the last successful runtime alone. Use normal runner timings to report the
measured boundary and functional budget separately. A pass with only seconds
to spare is a reason to review the design, not evidence of resilience. Broad
headroom should keep ordinary execution fast; no artificial slow-VM matrix,
extra repeat runs, evidence archive or new tests of these policy rules are
required. Task-specific values and unavoidable boundary constraints belong in
the existing case or unfinished brief, linked here.

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
  Developer host/guest shared folders are outside that inventory. Preparation
  and tests ignore their guest mount configuration, contents and directory ownership,
  including ancestor directories; do not configure, mount, relabel or take over
  them. Test inputs use the existing private staging and transfer routes instead.
  Existing VM isolation and snapshot provenance guards still detach or refuse
  host filesystem devices in disposable test configurations.
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
  host user's private `~/.onpc-config/.envrc`; E2E never changes passwords.
