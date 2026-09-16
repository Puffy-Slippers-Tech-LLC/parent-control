# Test VM prerequisites and recovery

This is an environment reference for maintenance or a replacement machine, not
a daily test sequence. Prepare the configured VM before its first test run. Ordinary
tests validate and reuse its accepted baseline; they must not rerun account preparation, capture
another baseline, download a new image, or create a replacement domain.

## Shared VM configuration

[config/test-vm.json](../../config/test-vm.json) is the single configuration for
guest preparation, host capture, installed-system/E2E runners and VM maintenance.
Set `name` to the existing libvirt domain name and `disk_anchor` to its absolute
base QCOW2 image path. The configured name also becomes the guest's static
hostname, so use a lowercase hostname (letters, digits, hyphens and dots, at most
63 characters). The active image can be a backing-chain member; capture still
verifies that the chain ends at the configured anchor. VM selection has no
environment-variable or command-line override. The E2E inventory's `ubuntu26.04`
environment label describes the supported OS, independently of the VM name.

Use matching source and configuration in the host and guest checkouts; their
filesystem locations may differ. From the checkout root **inside the product-free
Ubuntu 26.04 VM**, run `./setup.sh --prepare-vm` (or `make prepare-vm`), then shut
down the guest. On the host, run `./setup.sh --prepare-host`. Host preparation
captures and verifies the configured domain and refreshes the installed helpers
with its finalized UUID. All existing virtualization, product-residue, disk,
snapshot, share-isolation and ownership checks still apply.

For a guest checkout on a `noexec` shared mount, use `make prepare-vm` or
`/bin/bash ./setup.sh --prepare-vm`. The Make target invokes Bash explicitly;
direct execution of `./setup.sh` is blocked by that mount even with executable
file permissions.

Each VM name gets its own controller-state subdirectory. Existing unscoped
baseline records and other VMs' directories remain intact; they are never
silently adopted or retired when the configuration changes. A replaced VM with
the same configured name still fails the recorded UUID/disk checks. All names
share the existing controller lock in the state root. Finish tests and stop any
maintenance attempt before changing the selected VM. Configuration
and loader sources are included in the preparation digest, so changing them
requires matching guest preparation before a new baseline can be accepted.
This is development tooling: activation is the next invocation (installed UUID
pinning is refreshed by host preparation); no product activation or data migration.

## Resources

| Resource | Contract |
| --- | --- |
| Libvirt connection and domain | `qemu:///system`; `name` in the shared config, currently `oh-no-parent-control` |
| Host/guest preparation checkout | The checkout containing the invoked `setup.sh`; guest preparation requires that checkout's root. Installed host helpers retain their checkout pin. |
| Disk-chain anchor | `disk_anchor` in the shared config, currently `/Data/virt-manager/oh-no-parent-control.qcow2`; resolve and validate the actual active chain. |
| Retained product-free baseline | Internal `onpc-baseline` snapshot, captured while off, without VM memory; name defined by `SNAPSHOT` in [prepare_host.py](prepare_host.py). Previously captured baselines retain the name defined by `PREVIOUS_SNAPSHOT`; preparation and restoration validate their saved proof and preserve them. |
| Controller state | Root-private `/Data/virt-manager/oh-no-parent-control-baseline-state/<configured-name>/` |
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
The shared [guest tool inventory](guest_test_dependencies.py) is installed by
`make prepare-vm` (or `./setup.sh --prepare-vm`) **inside the
source guest, before baseline capture**. The Make aliases only delegate to
`setup.sh`. Dependencies are pinned OpenSSH server, pytest, OpenLDAP server/client
and SSSD LDAP/NSS packages, including their package-manager-resolved dependencies.
Preparation normalizes official Ubuntu archive URLs to HTTPS, verifies installed
versions, generates missing SSH host keys, enables SSH and checks public-key
authentication configuration. Repeats with matching packages skip APT refresh
and installation. Failed prerequisites prevent a new success record.
Account preparation is repeatable: existing test accounts retain their UIDs and
homes, and absent administrator-group memberships need no removal. Each run
reconciles and verifies the fixed roles and prompts for the shared test password
to set on all four accounts. Failed runs can be retried after resolving the
reported prerequisite; the product-free guest guards still apply.

LDAP/SSSD remain unconfigured: preparation refuses existing configuration,
requests OpenLDAP's supported no-configuration installation and disables
automatic directory-service startup. Existing configuration is never deleted.
Remote identities are created only by the selected test through
`dpkg-reconfigure` and LDAP's public APIs. Installed NSS libraries alone do not
create remote users. Product installation and its dependencies, temporary
credentials, run markers, policy mutations, assertions and real installation/
expiry reboots remain runtime work.

The preparation record is schema **2**, including the expected tool inventory;
its source digest includes the shared inventory module. Offline inspection
independently verifies dpkg's installed status and refuses existing LDAP/SSSD
fixture configuration. Missing/wrong-version tools and schema-1 account-only
baselines are refused; lease acquisition checks the preparation source digest
before disk audits, journal writes or VM mutation. Tests no longer repair them
by installing tools. This
test-environment change needs a prepared and accepted product-free baseline;
there is no product-data migration or package activation (`none`).

**Existing accepted baseline:** ordinary `--prepare-host` preserves it; rerunning
that command is not a replacement operation. Do not delete controller state or
recreate its named snapshot to bypass a mismatch. Replacing an accepted baseline
requires a separately authorized, ownership-checked maintenance operation. This
change does not automatically replace the current baseline. Local preparation,
bootstrap and refusal tests cover the new contract; live qualification and
wall-time comparison remain pending a prepared baseline.

For an explicitly requested replacement environment, consult the maintained
`prepare_vm.py` and `prepare_host.py` guards before provisioning. Existing
`./setup.sh --prepare-vm` is guest-only account and test-tool preparation;
`./setup.sh --prepare-host` is host-only baseline creation/reconciliation, followed
by refreshing helpers with the finalized VM identity. Run ordinary `./setup.sh`
on a replacement host first to install its dependencies and policies. The
Makefile's `prepare-vm` and `prepare-host` targets only delegate to these modes.
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
[pinned VM commands](../../docs/Approval-Tools.md#the-one-test-vm)
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

For multi-case E2E invocations, the exclusive lease spans the suite. Each case
still starts from the accepted baseline. The final worker power-off callback
force-reverts directly to its off state; no graceful shutdown wait or second
restore separates cases. Full baseline and offline guest audits bracket the
suite, while live ownership and isolation checks remain active throughout.
Final acceptance requires the closing audit and actual lease release. No
case may continue after a failure. See [suite controller](../e2e/suite_lease.py).

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

`snapshot:metadata-missing` means libvirt has no snapshot matching either
supported baseline name. A finalized journal does not recreate that metadata,
and rerunning preparation cannot repair its absence. Retain the disk and journal;
recovery needs the original metadata from a verified backup and reconciliation
with the saved disk proof, or separately authorized baseline replacement. An
unrelated snapshot is not a substitute for the recorded baseline.

After explicitly authorizing replacement and manually deleting the old baseline,
run guest preparation and shut down the guest, then use
`./setup.sh --replace-missing-baseline`. Refresh an older installed setup dispatcher
first with `./setup.sh --test-tools-only`. The replacement mode requires unchanged
source identities, no remaining baseline metadata or internal disk record, and no
incomplete test attempt. Under the shared controller lock it retains the original
journal as `retired-<operation>.json` before beginning a new capture. Guest
validation and disk verification still apply. Retries resume the new operation
or preserve its finalized snapshot. Ordinary `--prepare-host` never retires a
baseline. Development activation is on the next invocation after helper refresh;
no product service or saved-data change is involved.

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
and [E2E building blocks](../../docs/TestAutomation/E2E-Building-Blocks.md) for command scope.
