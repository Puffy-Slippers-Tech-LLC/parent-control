# Ubuntu 26.04 integration harness

## Scope

This contains the H-00 reproducible baseline, captured on 2026-09-01, and the
H-50 disposable-VM harness.  The machine that captured the baseline is a
development workstation, not an Oh No! Parent Control installation.  Nothing
in this document authorizes installing the product, creating accounts,
changing PAM or Polkit, or changing system services on a development
workstation.

The supported deployment target is a clean Ubuntu 26.04 Desktop VM.  The
exact platform and dependency versions below let the harness distinguish
package drift or an absent dependency from a regression in the product.  All
product installation and account/service changes happen over SSH inside a
marked VM.

## Captured platform

| Component | Package or command version | Installed | Enabled | Usable | Notes |
| --- | --- | --- | --- | --- | --- |
| Ubuntu Desktop | `ubuntu-desktop` 1.570.2; Ubuntu 26.04 LTS | yes | n/a | yes | Kernel: 7.0.0-30-generic. |
| GNOME Shell | `gnome-shell` 50.1-0ubuntu1.2; `GNOME Shell 50.1` | yes | n/a | yes | Desktop component; no product extension was installed. |
| AccountsService | `accountsservice` 23.13.9-8ubuntu5.2 | yes | yes | yes | `accounts-daemon.service` was enabled and active. |
| Malcontent | `malcontent` 0.14.0-0ubuntu1.1 | yes | yes | no | `malcontent-timerd.service` was enabled but inactive; no managed product account or live session was created on this development machine. |
| fapolicyd | package and executable absent | no | no | no | `fapolicyd.service` was not found. |
| Flatpak | `flatpak` 1.16.6-1; `Flatpak 1.16.6` | yes | n/a | yes | Client command is available; no test application was installed. |
| PAM | `libpam0g:amd64` 1.7.0-5ubuntu3.1 | yes | n/a | base library only | `pam_malcontent.so` and its `libpam-malcontent` package were absent. |

The absence of fapolicyd and the Malcontent PAM module is expected for this
development-only baseline.  They are required dependencies for a deployment
or destructive integration VM and must not be silently mocked or substituted.

Re-capture this table on a clean supported VM before changing the supported
platform.  Use these read-only commands:

```sh
. /etc/os-release && printf '%s %s\n' "$PRETTY_NAME" "$VERSION_ID"
uname -r
dpkg-query -W -f='${binary:Package}\t${Status}\t${Version}\n' \
  ubuntu-desktop gnome-shell accountsservice malcontent fapolicyd flatpak \
  libpam0g libpam-malcontent
gnome-shell --version
flatpak --version
fapolicyd --version
dpkg -S '*/pam_malcontent.so'
systemctl is-enabled accounts-daemon.service fapolicyd.service \
  malcontent-timerd.service
systemctl is-active accounts-daemon.service fapolicyd.service \
  malcontent-timerd.service
```

## Test inventory

## Requirement traceability

`tests/requirements.json` maps every stable `ONPC-...` ID in
`docs/Specification.md` to its responsible component, required test layer, and
runtime evidence. Maintain the mapping when a requirement or executable test
changes. Test references are repository-relative existing files under `tests/`;
source-contract checks may be recorded as supporting references but never as
acceptance evidence.

During the staged rollout, run the host-safe structural check with:

```sh
python3 tools/verify_test_traceability.py --mode stage
```

Only mark a requirement `covered` after the referenced executable test runs the
behavior. The final release gate uses `--mode final`, which rejects planned
coverage and records without executable evidence.

### Host-safe unit and source-contract tests

`make check` is the required host-safe baseline command.  It does not install
the product or modify users, services, PAM, Polkit, AccountsService, or the
host app filter.  It runs:

- JavaScript syntax checks for the child extension;
- Python unit tests in `tests/unit/` covering broker core, generated broker
  properties and state-machine transactions, adapters, preferences and
  migrations, execution-policy rendering, catalog,
  extension lifecycle, logs, kiosk and parent clients/UI, provisioning,
  installer, package activation, systemd unit, and PAM limit helper;
- Python and XML parse checks; and
- source-contract checks that reject private GNOME Shell APIs and verify that
  child requests use the broker action without retained or implied privileges.

Run it from the repository root:

```sh
make check
```

Pytest markers make the test intent selectable. Every current test is marked
`unit` or `contract`; the remaining markers are reserved for the component and
guest layers added later in this plan:

```sh
make check-marker MARKER=unit
make check-marker MARKER=contract
```

The full marker vocabulary is `unit`, `contract`, `component`, `ui`, `system`,
`e2e`, `slow`, and `guest_mutating`. Source/configuration assertions are
`contract` tests and are never runtime acceptance evidence. Generate local
branch-coverage artifacts for the broker, parent, kiosk, common, and tools
packages with:

```sh
make check-coverage
```

This writes HTML and XML reports under the ignored `artifacts/coverage/`
directory. Coverage is reported by security boundary rather than forced into a
misleading repository-wide percentage: broker caller/target validation,
transaction rollback, preferences, migration, execution-policy activation, and
UID-confined process ownership are the review boundaries. Use the report's
missing-lines section to identify blind spots; no blanket threshold is applied.

Maintained static checks are available separately and remain host-safe:

```sh
make check-static
```

This runs ShellCheck using `.shellcheckrc` and GJS's public module loader for
the child modules; the existing Node syntax check continues to cover the
Shell-bound entry point. The Ubuntu archive dependencies are listed in
`tests/test-tools-ubuntu-26.04.txt`.

Broker generated tests use the committed, deterministic `onpc` Hypothesis
profile. Re-run them, including committed regression examples, with:

```sh
make check-unit
```

### Deterministic application fixtures

`tests/fixtures/build_test_applications.py` source-builds a static
long-running native target, deterministic AppImage-style copies and desktop
entries, plus a local Flatpak repository and bundle. `make check-test-fixtures`
builds and launches them in an unprivileged temporary directory with a private
Flatpak user installation. It cannot access the development user's real
Flatpak installation or the system installation. `make build-test-fixtures`
requires an explicit empty output below `/tmp` and creates only a payload; it
does not install the fixtures. A later guest-mutating task must copy that
payload only after the guest guard validates the disposable VM marker.

### Reproducible system-test artifacts

Task 13A defines the package input for later installed-system tests. Build it
without installing the product on the development host, using an explicit empty
directory outside this checkout:

```sh
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-test-artifacts/first
```

The directory contains `artifact-manifest.json`, the named Debian package at
`package/`, and the Task 11 payload at `fixtures/`. The manifest records the
source revision and digest, `SOURCE_DATE_EPOCH`, architecture, tool versions,
package digest, and fixture-bundle digest. Task 13B consumes this manifest and
copies only its digest-verified files into a guarded guest.

To establish repeatability, use two new empty directories:

```sh
make verify-test-artifacts \
  FIRST_OUTPUT=/tmp/onpc-test-artifacts/first \
  SECOND_OUTPUT=/tmp/onpc-test-artifacts/second
```

The command builds from isolated temporary source copies, then compares the
package file name and SHA-256, package metadata and contents, fixture digest,
and recorded source/build inputs. It leaves the product uninstalled. Its
manifest records `DEB_BUILD_OPTIONS=nocheck`: the Task 12 host-controller
checks require the fixed development-checkout path and run separately through
the required `make check` validation. The fixture digest covers its stable
application and runtime payload. Flatpak's generated delivery summary and its
bundle container carry a host-clock timestamp, so the builder verifies the
bundle is present without treating that container timestamp as package input.

### Source-VM account preparation

The existing `ubuntu26.04` source VM exposes this development checkout at the
fixed path `/Data/Code/PST/parent-control` through its `/Data` virtiofs share.
That writable share is a preparation convenience. Its host files are outside
the VM snapshot and are not restored by a baseline reset. Automated test runs
must detach it before booting the existing VM for testing.

Before product installation or baseline capture, open a terminal inside that
VM and run the following from the fixed checkout:

```sh
cd /Data/Code/PST/parent-control
make prep-vm
```

The launcher requests root privileges through sudo when needed, which may prompt
for your sudo password. This is separate from the shared test-account password
prompt below. Running as root skips sudo.

The command accepts no VM, image, UUID, checkout, or output arguments. It first
verifies root, virtualization, Ubuntu 26.04, hostname `ubuntu26.04`, the complete
fixed checkout, and the absence of every product installation/residue category.
It then prompts exactly once for a shared test-only password and prepares the
two shared parent preview identities as local administrators and the two shared
child preview identities as standard users. The
password is sent only to `chpasswd` on standard input and is not stored in the
preparation record.

This command prepares accounts only. It does not install Oh No! Parent Control,
change libvirt state, capture an image, or run product tests. It must never be
run on the development host. Repeating it in the guarded source VM reasserts the
same account properties and changes only the shared password. The resulting
root-owned mode-`0600` record is
`/etc/oh-no-parent-control-test-baseline.json`.

This test-only preparation adds no packaged system integration, so its package
update activation classification is `none`. It changes no product saved-data
schema, so no data migration applies.

### Reusable baseline snapshot on the existing VM

`make prep-host` creates the libvirt-managed internal snapshot
`oh-no-parent-control-baseline` on the existing `ubuntu26.04` VM at
`qemu:///system`. It stores the saved disk state inside the VM's current QCOW2.
It does not copy the VM, convert its image, create an external overlay, or
define another domain. Normal testing writes to the existing VM; reverting
the named snapshot restores the clean baseline repeatedly.

The exact operator sequence is:

1. On the development host, run `./setup.sh` if the pinned tools are missing.
2. Inside `ubuntu26.04`, run `make prep-vm` from
   `/Data/Code/PST/parent-control`.
3. On the development/libvirt host, enter a root shell, change to that checkout,
   and run `make prep-host`.
4. Let the controller shut down the VM cleanly, inspect it read-only, and create
   the snapshot. Do not start the VM or change its storage concurrently.
5. Start the same VM for testing. Preserve the named snapshot.

The controller resolves the active disk and verifies its QCOW2 chain ends at
`/Data/virt-manager/ubuntu26.04.qcow2`. Existing backing files and unrelated
snapshots are supported. The shutdown deadline is 180 seconds; it never
force-stops the VM. Offline libguestfs inspection explicitly uses read-only
QCOW2 access and verifies the preparation marker, accounts, and absence of the
product in the guest. An installed product on the host is allowed and ignored.

Plain `make prep-host` accepts no resource overrides and installs no packages.
Dependency diagnostics do not connect to libvirt or write files:

```sh
/usr/bin/python3 tests/integration/prepare_host.py --help
/usr/bin/python3 tests/integration/prepare_host.py --check-tools
```

The controller stores only its private lock and atomic `phase.json` under
`/Data/virt-manager/oh-no-parent-control-baseline-state/` (root-owned, directory
mode 0700 and files mode 0600). The record contains the domain and disk
identities, preparation evidence, backing-chain digests, snapshot creation
identity, and recovery phase. Libvirt owns the snapshot metadata; there is no
separate baseline image, image checksum sidecar, or copied provenance artifact.
Files left by an earlier copy-based workflow are not used or deleted.

Phases are validation, shutdown requested, source off, snapshot requested,
and finalized. After interruption, rerun `make prep-host`. If libvirt already
created the snapshot, the controller validates its recorded operation identity,
domain layout, and internal disk snapshot before finishing. A partial or
unrelated same-name snapshot is refused and preserved for inspection.
If the fixed controller directory exists but is empty with guest-mapped
ownership or an incorrect mode, the host controller repairs it to host-root
ownership and mode `0700`; any directory containing an entry remains refused
and unchanged for inspection.
Completed runs verify and preserve the original baseline even while the VM is
running or has the product installed for testing. They neither recapture nor
revert it. Missing/replaced snapshots and changed backing files are refused.
Diagnostics contain categories, not raw account records or credentials.
The libvirt event loop remains active throughout hashing, offline inspection,
and disk checks so server keepalives are answered during long operations.
An absent baseline is discovered by listing snapshots and is a normal creation
case. Progress distinguishes source hashing, offline inspection, and disk checks.

To restore the baseline between tests, first shut down the test guest cleanly:

```sh
virsh --connect qemu:///system shutdown ubuntu26.04
virsh --connect qemu:///system domstate ubuntu26.04
```

Wait until the state is `shut off`. Then restore and boot the same VM:

```sh
virsh --connect qemu:///system snapshot-revert ubuntu26.04 oh-no-parent-control-baseline
virsh --connect qemu:///system start ubuntu26.04
```

Revert discards guest disk changes made since the baseline, including test
installations. The saved snapshot remains available for the next reset. The
host's shared `/Data` files are outside the VM disk and are not restored.
Automated test runners must detach that writable host share while the VM is
off before booting a test run; reverting restores the saved domain definition,
so runners must repeat that step after each reset. The snapshot also does not
cover external firmware NVRAM or TPM state; such devices are refused.

This tooling is development-only: activation classification is `none`, and no
product saved-data migration applies. Task 12C verifies the actual snapshot;
later runner work uses this existing VM with serialized baseline resets.

### Reusable integration guards and evidence

The previous cloud-image setup command has been removed.
`tests/integration/harness.py` retains the existing identity guards, SSH
transport, redaction, archive validation, and explicit owned-VM cleanup for
later runners. These helpers are not another supported baseline path.
Later runners must use the existing VM and restore its named baseline between
runs. The retained disposable-VM helpers do not yet implement that lifecycle.

The guest guard requires root, virtualization, Ubuntu 26.04, the exact
hostname, and a root-owned mode-0600 marker whose random token also matches
the controller's private state. Artifact collection redacts tokens,
credentials, and private keys before checksumming. Extraction rejects links,
devices, and path traversal. Existing owned-VM cleanup requires matching
name/confirmation, token, domain description, and exact recorded disk paths.

The host-controller regressions use mocked libvirt, inspection, and image
operations; they require neither a running VM nor root:

```sh
python3 -m pytest tests/unit/test_prepare_host_cleanup_safety.py -q
python3 -m pytest tests/unit/test_prepare_host.py -q
make check
git diff --check
```

Public tool contracts: [libguestfs Python API](https://libguestfs.org/guestfs-python.3.html),
[libvirt event API](https://libvirt.org/html/libvirt-libvirt-event.html),
[libvirt snapshots](https://libvirt.org/formatsnapshot.html),
and [qemu-img](https://www.qemu.org/docs/master/tools/qemu-img.html).
