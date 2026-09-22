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

Set a literal `TEST_ACCOUNT_PASSWORD` in the host checkout's private mode-0600
`.envrc`, then run `tools/prepare-baseline` on the development host with the
product-free Ubuntu 26.04 VM off. Missing, empty, placeholder or unsafe
credentials fail before privilege dispatch or VM access. The old `make prepare-vm`
target, `make prepare-baseline` alias and `./setup.sh --prepare-baseline` mode
have been removed.

Under the shared lease, preparation stages the maintained guest modules and a
temporary root-only password file, then boots the guest with a one-shot systemd
service ordered before the display manager. The guest consumes and removes the
password file, reconciles accounts and tools, records success and powers off.
The host removes the temporary service, independently inspects the guest, and
captures its baseline. The guest log remains at
`/var/lib/onpc-baseline-preparation/preparation.log`; it contains no password.
There is no guest checkout or interactive password prompt to maintain.
Existing virtualization, product-residue, disk, snapshot and ownership guards
still apply. Preparation refuses a running source VM and never adopts a
replacement instance. An interrupted preparation can be retried once the same
guest is off; failures cannot capture an old success record.

Each VM name gets its own controller-state subdirectory. Existing unscoped
baseline records and other VMs' directories remain intact; they are never
silently adopted or retired when the configuration changes. A replaced VM with
the same configured name still fails the recorded UUID check. Ordinary runners
also require the recorded disk identities; explicit preparation can accept a
changed disk chain after manual maintenance on that same VM. All names
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
| Host/guest preparation checkout | The checkout containing the invoked `tools/prepare-baseline`; maintained guest modules are staged privately inside the VM. Installed host helpers retain their checkout pin. |
| Disk-chain anchor | `disk_anchor` in the shared config, currently `/Data/virt-manager/oh-no-parent-control.qcow2`; resolve and validate the actual active chain. |
| Retained product-free baseline | Internal `onpc-baseline` snapshot, captured while off, without VM memory; name defined by `SNAPSHOT` in [prepare_baseline.py](prepare_baseline.py). Runners also accept the previous name defined by `PREVIOUS_SNAPSHOT`; explicit preparation replaces it with `onpc-baseline`. |
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
the host's `tools/prepare-baseline` during its controlled guest boot.
Dependencies are pinned OpenSSH server, pytest, OpenLDAP server/client
and SSSD LDAP/NSS packages, including their package-manager-resolved dependencies.
Preparation normalizes official Ubuntu archive URLs to HTTPS, verifies installed
versions, generates missing SSH host keys, enables SSH and checks public-key
authentication configuration. Repeats with matching packages skip APT refresh
and installation. Failed prerequisites prevent a new success record.
Account preparation is repeatable: existing test accounts retain their UIDs and
homes, and absent administrator-group memberships need no removal. Each run
reconciles and verifies the configured picture, display name, shell, roles and
unlocked status, and sets the shared password from the host's `.envrc` on all
four accounts. Failed runs can be retried after resolving the
reported prerequisite; the product-free guest guards still apply.

Existing login keyrings are preserved under unique
`~/.local/share/onpc-keyring-backup-*/keyrings` directories during preparation.
Their encrypted contents remain available, while GNOME can create an active
keyring matching the new password on the next login. Account UIDs and homes are
retained; missing accounts are created. Repeating preparation without an
intervening login creates no additional keyring backup.

E2E reads the same `.envrc` password, verifies it against the prepared accounts
without writing to the guest, and uses it for login. Missing configuration fails
before build/VM work; a password that differs from the baseline is refused with
an instruction to run preparation again. E2E never rotates account passwords or
resets keyrings. See
[credential staging](../e2e/README.md#credential-staging-and-password-capture-boundary).

LDAP/SSSD remain unconfigured: preparation refuses existing configuration,
requests OpenLDAP's supported no-configuration installation and disables
automatic directory-service startup. Existing configuration is never deleted.
Remote identities are created only by the selected test through
`dpkg-reconfigure` and LDAP's public APIs. Installed NSS libraries alone do not
create remote users. Product installation and its dependencies, run markers, policy mutations, assertions and real installation/
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

**Existing accepted baseline:** `tools/prepare-baseline` explicitly replaces it.
The VM must already be off; preparation fails instead of shutting it down.
Under the shared lease, it deletes the old snapshot without restoring it and
captures the current prepared guest. Ownership checks and incomplete-attempt
refusals still apply, and the old journal is archived. Ordinary `./setup.sh`
never invokes baseline preparation. Tests continue to reuse the accepted baseline.

**Manual snapshot maintenance:** restore any snapshot you manage (such as
`1 - Clean`), perform maintenance, shut down, and delete/retake your snapshot.
Then run `tools/prepare-baseline`. The command uses the current guest disk state
without choosing or restoring any snapshot. A changed active image or backing
chain on the same recorded VM is accepted automatically, provided the chain
still ends at the configured anchor. Only the automation baseline is retired;
manually managed snapshots are preserved. Its previous provenance is archived
before capture. No extra confirmation or replacement flag is required for this
workflow. The VM-off, same-UUID, idle-controller and product-free checks remain
prerequisites.

For an explicitly requested replacement environment, consult the maintained
`prepare_vm.py`, `baseline_guest.py` and `prepare_baseline.py` guards.
Run ordinary `./setup.sh` on a replacement host first to install dependencies
and policies. Baseline preparation remains explicit and is never called
automatically by tests to repair a missing baseline.

Guest preparation suppresses Ubuntu's optional welcome/opt-in wizard for all
four accounts by creating their GNOME Initial Setup first-login and Ubuntu
26.04 upgrade completion markers as the respective account. It does not enroll
accounts in optional services. This test tooling change requires a fresh
explicit preparation before tests; it needs no package activation or product
data migration.

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
restore separates cases. Baseline metadata and targeted offline guest audits bracket the
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
and ordinary tests cannot repair its absence. Retain the disk and journal;
recovery needs the original metadata from a verified backup and reconciliation
with the saved disk proof, or explicit baseline replacement. An
unrelated snapshot is not a substitute for the recorded baseline.

To replace a baseline, prepare and shut down the guest, then run
`tools/prepare-baseline`; manual deletion is unnecessary. Refresh an older
installed setup dispatcher first with `./setup.sh --test-tools-only`.
The retained `./setup.sh --replace-missing-baseline` recovery mode handles an
already deleted baseline without replacing an existing one. It requires unchanged
source identities, no remaining baseline metadata or internal disk record, and no
incomplete test attempt. Under the shared controller lock it retains the original
journal as `retired-<operation>.json` before beginning a new capture. Guest
validation and disk verification still apply. Retries resume the new operation
or preserve its finalized snapshot. Explicit `tools/prepare-baseline` replaces a
finalized snapshot on each invocation. Development activation is on the next invocation after helper refresh;
no product service or saved-data change is involved.

An incomplete prior system run prevents a new run. Use only a supported,
identity-verified recovery path for that recorded attempt; if recovery is not
implemented for its state, diagnose and repair the controller before reuse.
Changed/replaced identities prevent recovery from mutating a replacement.
Explicit preparation after a completed operation accepts manual disk maintenance
on the same VM as described above. A preparation
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
