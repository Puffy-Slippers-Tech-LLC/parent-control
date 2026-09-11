# Test VM prerequisites and recovery

This is an environment reference for maintenance or a replacement machine, not
a daily test sequence. The existing VM baseline is already prepared. Ordinary
tests validate and reuse it; they must not rerun account preparation, capture
another baseline, download a new image, or create a replacement domain.

## Fixed resources

| Resource | Contract |
| --- | --- |
| Libvirt connection and domain | `qemu:///system`, `ubuntu26.04` |
| Host/guest preparation checkout | `/Data/Code/PST/parent-control` |
| Disk-chain anchor | `/Data/virt-manager/ubuntu26.04.qcow2`; resolve and validate the actual active chain. |
| Retained product-free baseline | Internal `oh-no-parent-control-baseline` snapshot, captured while off, without VM memory. |
| Controller state | Root-private `/Data/virt-manager/oh-no-parent-control-baseline-state/` |
| Provenance and active attempt | Immutable finalized `phase.json`; separate mutable `system-run.json`. |
| Guest preparation record | Root-owned mode-0600 `/etc/oh-no-parent-control-test-baseline.json` |

The controller binds the domain, disk/backing identities, snapshot metadata and
preparation evidence. Do not substitute preview UIDs for actual guest UIDs.
Fixed test-account definitions live in
`common/oh_no_parent_control_ui/test_identities.py`; real account identities and
roles are verified in the guest. Keep passwords out of records and diagnostics.

Host setup is orchestrated only by `setup.sh`; its scoped dependency module is
`tools/setup_dependencies.sh`. Dependency versions are also recorded in
[../test-tools-ubuntu-26.04.txt](../test-tools-ubuntu-26.04.txt), and
[../ui/requirements.txt](../ui/requirements.txt). Missing tooling is a
prerequisite failure, not permission for a test to install host packages.
Current guest bootstrap installs its required tools inside the guarded guest;
those per-attempt guest writes are distinct from one-time host setup.

For an explicitly requested replacement environment, consult the maintained
`prepare_vm.py` and `prepare_host.py` guards before provisioning. Existing
`./setup.sh --prepare-vm` is guest-only account preparation;
`./setup.sh --prepare-host` is host-only baseline creation/reconciliation, followed
by refreshing helpers with the finalized VM identity. Run ordinary `./setup.sh`
on a replacement host first to install its dependencies and policies. The
Makefile's `prep-vm` and `prep-host` targets only delegate to these modes.
They remain tooling, not daily `test-*`
targets, and are never called automatically to repair a missing accepted
baseline. Guest preparation suppresses Ubuntu's optional welcome/opt-in wizard
for all four test accounts by creating their GNOME Initial Setup first-login
and Ubuntu 26.04 upgrade completion markers, as the respective account. It
does not enroll accounts in optional services. This tooling change activates
on the next login after running `./setup.sh --prepare-vm`; it needs no package activation
or saved product-data migration. An already open wizard must be closed.
Prepare the guest before product installation, then capture and
validate its product-free baseline on the host. Preserve any existing baseline;
replacement of a resource requires a deliberate ownership-reviewed operation.

## Reset boundary and host preservation

For explicitly authorized maintenance, use the
[pinned VM commands](../../docs/TestAutomation/Approval-Tools.md#the-one-test-vm)
(`tools/test-vm status`, `start`, `reboot`, `send-key`, `screenshot`, `stop`,
`reset`). They share this controller's lock and provenance and never accept
another domain, URI, disk, XML or snapshot. A maintenance attempt must be stopped
before starting a system/E2E run. Routine test runs continue through their
existing guarded controllers; raw `virsh` commands bypass these contracts.

Only the guarded runner may perform a normal test reset under its exclusive
lease, outside a complete independent attempt. It restores the retained
baseline, removes writable host shares and transfer channels before boot,
executes real guest operations, collects evidence, restores the baseline/prior
persistent domain configuration, and leaves the VM off. It creates no new
snapshot, overlay or cloned VM. Reboot inside a journey changes the real boot
identity and preserves the preceding steps' state.

The preparation `/Data` virtiofs share is outside VM disk state. A snapshot
restore may reintroduce its saved domain configuration, so every test boot
requires the runner's share-detachment checks. Do not manually restore and boot
the VM using a copied command sequence that bypasses these guards. External
firmware/TPM state outside the recorded snapshot contract is refused.

## Interrupted or invalid state

Preserve `phase.json`, `system-run.json`, snapshot metadata, run evidence and
source logs. Read the stage/category and recorded identities before considering
recovery. Do not delete a journal, force-stop a guessed process, or recreate a
snapshot to make a refusal disappear. The active-attempt record is not the
baseline record and must not overwrite it.

An incomplete prior system run prevents a new run. Use only a supported,
identity-verified recovery path for that recorded attempt; if recovery is not
implemented for its state, diagnose and repair the controller before reuse.
Changed/replaced identities prevent mutation of the replacement. A preparation
interruption may be reconciled by the preparation controller only within its
recorded original operation; this is not permission to recapture an accepted
baseline. Normal test failure cleanup does not turn a failed attempt into a
pass.

For the narrow case of a VNC graphical attempt whose journal is
`cleanup-requested` and whose exact recorded domain instance is still running,
use `pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_recovery`.
It accepts no arguments, runs isolated safety prerequisites, reacquires the
exclusive lock and verifies the journal, live run/domain identity, source layout,
baseline identity and snapshot/backing proof before using ordinary lease cleanup.
It cannot boot, provision, create a baseline, recover another phase, or operate
on an already-off/replaced instance. Recovery evidence is retained separately
under `/tmp/onpc-graphical-recovery-*`; original failure evidence is unchanged.

For the same `cleanup-requested` interruption in an installed-system attempt,
use `tools/run-tests integration check_system_recovery`. It uses the same
exclusive lock and journal/domain/baseline checks, requires the recorded running
SPICE instance, and performs only ordinary lease cleanup. Neither recovery route
can adopt the other display kind. Evidence is retained separately under
`/tmp/onpc-system-recovery-*`. An interrupted suite remains incomplete and needs
a fresh full run after successful recovery. This development test helper
activates on invocation (`none`); it changes no product or saved application data.

Read product logs at
`/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log` and journals without
editing or deleting them. If sandbox access is denied, request the minimum
read-only escalation. See [README.md](README.md) for runtime artifact locations
and [the daily guide](../../docs/Test-Automation.md) for command scope.
