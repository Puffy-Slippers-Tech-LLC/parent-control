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

- shell syntax validation for `install.sh`;
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

### Disposable VM integration tests

Do not run `sudo ./install.sh` on a development workstation.  Running
`make check` does not create or start a VM.  The VM exists only if an operator
explicitly invokes the `setup` command below.

The controller uses the system libvirt connection and requires these existing
host tools: `virsh`, `virt-install`, `qemu-img`, `cloud-localds`, `ssh-keygen`,
`ssh`, `scp`, and `curl`.  It reports missing tools and stops; it never installs
host packages.  The libvirt `default` NAT network must already be available.
The default guest is a sparse 80-GiB disk with 8 GiB RAM and four vCPUs.

The base is Canonical's official, pinned Ubuntu 26.04 release image
`release-20260823/ubuntu-26.04-server-cloudimg-amd64.img`.  Before use, the
controller downloads the release's `SHA256SUMS` over HTTPS and verifies the
image digest.  Guest setup installs the supported Ubuntu Desktop environment,
then the test run requires the exact reviewed versions in
`expected-packages.tsv`.  Package drift fails with an instruction to review
and recapture the supported matrix; it is never silently accepted.

Choose a unique name with the required `onpc-h50-` prefix and repeat that
literal name in every command:

```sh
sudo python3 tests/integration/harness.py setup \
  --name onpc-h50-clean-20260901
sudo python3 tests/integration/harness.py run \
  --name onpc-h50-clean-20260901
sudo python3 tests/integration/harness.py collect \
  --name onpc-h50-clean-20260901
sudo python3 tests/integration/harness.py destroy \
  --name onpc-h50-clean-20260901 \
  --confirm onpc-h50-clean-20260901
```

`setup` creates only that libvirt guest.  Cloud-init creates the administrator
as UID 2000, and the guarded guest setup deterministically provisions the child
(2001), kiosk (2002), and unrelated standard user (2003).  Test passwords are
random per VM and remain in the root-only file
`/var/lib/oh-no-parent-control-integration/VM_NAME/credentials.json` on the
host.  The product is not installed until `run` transfers the current worktree
and invokes its real `install.sh` inside the guest.  `run` first executes
`make check`, performs a clean install, reboots, and verifies services,
AccountsService roles, D-Bus access, PAM account results, and fapolicyd rules.

Every guest command begins with the same fail-closed guard.  It requires all
of the following before any mutation:

- effective UID 0 inside the guest;
- a root-owned, mode-`0600`, regular
  `/etc/oh-no-parent-control-integration-vm` marker;
- the marker's exact purpose and selected VM name;
- a VM reported by `systemd-detect-virt --vm`;
- Ubuntu `VERSION_ID=26.04`; and
- a hostname equal to the selected VM name.

The host controller additionally compares the marker's random identity token
with its root-only state before uploading or invoking guest code.  Merely
copying a guest script onto a development host therefore cannot authorize it.

`collect` retrieves a timestamped directory under
`tests/integration/artifacts/VM_NAME/`.  It contains package/platform versions,
service status and journals, D-Bus replies, fapolicyd source and compiled rule
snapshots, PAM/login results, `make check` and clean-install output, and the
product logs from `/var/log/oh-no-parent-control/`.  The guest removes marker
tokens, password-like values, bearer values, and SSH/private keys before
creating `SHA256SUMS`; the controller rejects archive links, devices, and path
traversal during extraction.

`destroy` requires `--name` and an identical `--confirm`.  It then compares the
saved random token with the libvirt domain description and requires the domain
to reference exactly the saved qcow2 disk and cloud-init seed.  Only after all
checks pass does it stop and undefine that domain and remove those two named
images and that VM's state.  The checksum-verified shared Ubuntu image cache is
retained.  No wildcard, default VM name, or `--remove-all-storage` operation is
used.

H-50 adds no packaged product integration, so its update activation is `none`.
It changes no application-owned saved data, so no migration is required.
