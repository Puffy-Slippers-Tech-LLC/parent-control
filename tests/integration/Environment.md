# Test VM prerequisites and recovery

This is an environment reference for maintenance or a replacement machine, not
a daily test sequence. Prepare the configured VM before its first test run. Ordinary
tests validate and reuse its accepted baseline; they must not rerun account preparation, capture
another baseline, download a new image, or create a replacement domain.

## Shared VM configuration

[config/test-vm.json](../../config/test-vm.json) is the single configuration for
guest preparation, host capture, installed-system/E2E runners and VM maintenance.
Its `vms` array contains one object per existing VM, each with a unique `name`
and absolute base QCOW2 `disk_anchor`, plus `enabled` as the string `"true"` or
`"false"`. Test and preparation selection follow the
[VM mandate](../../docs/Mandates/VM-Mandate.MD#authority-and-operation): optional
`--vm` accepts names/IDs, lists, `all-enabled`, or `all`, defaulting to enabled
entries except `tools/prepare-vm`, which defaults to `all` in both modes,
including disabled entries. The positive integer `concurrency` limits simultaneous operations,
refilling each free slot immediately. Maintenance still requires one explicit
selector, matching a configured name exactly, including case.
Workers inherit validated selections; there is no
ambient environment override for public commands. Each VM has its own exclusive
lease and retention journal. The guest hostname is the lowercase form of that name
(hostname labels, at most 63 characters). The active image can be a backing-chain
member; capture still verifies that its chain ends at the selected anchor.
Each entry has separate baseline provenance and an individually pinned UUID.
The E2E inventory's `ubuntu26.04` environment label describes the currently
supported guest OS independently of the VM name; adding an entry does not
qualify its OS for Ubuntu-specific baseline preparation or installed tests.

Host/guest clipboard sharing is always enabled in the interactive SPICE console,
including baseline preparation, maintenance and restored app snapshots. There is
no per-VM clipboard option. Baseline preparation configures the SPICE console and
display-agent channel and installs/verifies `spice-vdagent` on both supported
guests. Refresh existing baselines through the preparation route to apply these
prerequisites. App preparation refreshes snapshots with clipboard sharing disabled.
Disabled older layouts remain valid for owned cleanup. The watch panels remain
read-only; clipboard sharing is available through the interactive VM console.

Set a literal `TEST_ACCOUNT_PASSWORD` in the host checkout's private mode-0600
`.envrc`, then run `tools/prepare-vm --vm NAME --mode manual` on the development host with the
product-free Ubuntu 26.04 VM off. Missing, empty, placeholder or unsafe
credentials fail before privilege dispatch or VM access. The old `make prepare-vm`
target, `make prepare-baseline` alias and `./setup.sh --prepare-baseline` mode
have been removed.

The required `--mode` accepts only `auto` or `manual`, with no default. Missing
options or values print help and examples. Help and the red warnings reuse the
same bullet lists of steps. Both modes refuse a VM after checkout
that is not off. Under the shared lease, a red warning describes the selected
workflow and deletion of **all versioned app snapshots**, including release-derived
names with or without the `v` prefix. By default, only an explicit `y` proceeds;
`n` or end of input exits without guest or snapshot changes. `--y` suppresses
the y/n prompt while retaining the warning and every safety check. An omitted
`--vm` selects all registered VMs, including disabled entries, in both auto and
manual modes; multiple VMs are confirmed together before work.
After
confirmation or `--y`, those app snapshots are deleted without recursively
deleting their children.

Under the [VM mandate](../../docs/Mandates/VM-Mandate.MD#vm-host-setup-and-baseline),
auto-mode refresh needed for authorized development or testing is preapproved,
including app-snapshot deletion and baseline replacement. Launchers and sessions
use `tools/prepare-vm --vm NAME --mode auto --y` without asking the developer
again. Manual mode still requires explicit developer authorization; authorized
launcher/session work uses `--mode manual --y`. Manual work omits `--y` to keep
confirmation. Refresh the installed dispatcher with `./setup.sh --test-tools-only`
after adding support for this flag. This standing authorization does not
bypass any VM, ownership, lease or validation check.

- `tools/prepare-vm --vm NAME --mode auto` requires an existing accepted baseline,
  restores it, boots, runs no-app prerequisites, and updates Ubuntu packages.
  If a reboot is required, a second controlled boot verifies a changed boot ID
  before shutdown. The old baseline is replaced only after successful guest
  preparation and independent offline inspection.
- `tools/prepare-vm --vm NAME --mode manual` boots the current guest disk state,
  runs no-app prerequisites, shuts down and creates `onpc_baseline`, replacing
  an existing baseline if present. It does not run the system update step.

Both modes then build the current package as the invoking administrator, prepare
the current online app snapshot through the same implementation as
`tools/prepare-appsnapshot`, and restore `onpc_baseline`. The VM finishes off.
One exclusive per-VM controller lock covers the complete sequence, including
package building and the final restore. Nested controllers duplicate the held
lock descriptor in-process; ending one stage cannot release the outer lease.
Queue workers retain isolated state and the registry concurrency limit. Helper
UUID pins refresh once after the workers finish.

Automatic updates use Ubuntu's scripting interface,
[`apt-get`](https://manpages.ubuntu.com/manpages/resolute/man8/apt-get.8.html):
refresh indexes with errors treated as failures, run a noninteractive
`dist-upgrade` with a bounded package-lock wait, then `apt-get check`. Existing
locally changed configuration files are retained when no package default resolves
the choice. This updates packages from configured repositories within the
current Ubuntu release. `/run/reboot-required` triggers a full power cycle; the
second boot verifies the new boot identity and prerequisite package inventory.
Update, setup or verification failure prevents baseline replacement. App
snapshots already deleted after confirmation remain deleted if later work fails.
Every confirmed invocation repeats its selected workflow, even if the previous
baseline is already current. Auto always checks for and applies available system
updates; both modes rerun no-app setup. After an interrupted attempt, shut down
the same VM before retrying. Existing guest staging and already deleted app
snapshots are safe to revisit. A snapshot created just before an interrupted
final journal write is verified before the full workflow runs again. Genuine
prerequisite, ownership, update and validation errors still fail visibly; auto
continues to require an existing baseline.

Under the shared lease, preparation stages the maintained guest modules and a
temporary root-only password file, then boots the guest with a one-shot systemd
service ordered before the display manager. The guest consumes and removes the
password file, reconciles accounts and tools, performs the selected update step,
records success (or a required reboot) and powers off.
The shared watch display uses CPU frame copies; preparation disables SPICE
OpenGL and guest 3D acceleration to keep that display compatible with QEMU.
Preparation also enables migration for a host-passthrough CPU and disables
`invtsc` so later app snapshots can save memory.
The virtio balloon also enables
[`freePageReporting`](https://www.libvirt.org/formatdomain.html#memory-balloon-device),
allowing unused guest pages to return to the host instead of preserving stale
RAM bytes in online snapshots. Configured maximum/current memory stays unchanged.
The host removes the temporary service, independently inspects the guest, and
captures its baseline. The guest log remains at
`/var/lib/onpc-baseline-preparation/preparation.log`; it contains no password.
When the guest does not record success, preparation retains up to the last
16 KiB of that log in private recovery storage and reports the artifact path.
Read it through the [artifact reader](../README.md#prompt-free-test-artifact-access)
before retrying; console output keeps only diagnostic categories. Missing,
unsafe or unreadable logs and retention errors never replace the original
preparation failure.
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
changed disk chain after manual maintenance on that same VM. Each name has an
exclusive controller lease, so different VMs may prepare in parallel. A shared
compatibility lease excludes older controllers that still own the state root
exclusively. Finish tests and stop maintenance on the same VM before preparation.
Guest identity and snapshot isolation configuration, and loader sources, are included
in the preparation digest. Changing them requires matching guest preparation
before a new baseline can be accepted. Queue `concurrency`, per-VM `enabled`
flags and selector IDs are excluded: changing scheduling does not invalidate
prepared baselines or derived app snapshots.
This is development tooling: activation is the next invocation (installed UUID
pinning is refreshed by host preparation); no product activation or data migration.

## Reusable preparation ownership

`tools/prepare-vm` owns all reusable one-time guest preparation. Tests,
qualification workers and app-snapshot preparation verify readiness and refuse
missing or stale inputs with baseline-refresh guidance. They must not install,
repair or recreate environment inputs during an attempt. Ubuntu and Fedora's
[shared clean snapshot boundary](#ubuntu-clean-snapshots) keeps movable fixture
payloads on the host, with [Fedora-specific policy checks](#fedora-clean-snapshots).
The legacy inventory below remains a recovery contract. Future native, Snap, Flatpak and game dependencies
still require shared environment preparation before use.

| Input | Owner and lifetime |
| --- | --- |
| Fixed accounts, guest dependencies, welcome/idle settings | Baseline account/tool reconciliation |
| Fedora terminal shortcut | `prepare_vm.configure_terminal_shortcut` gives each fixed test account a permanent Ctrl+Alt+T custom binding to `/usr/bin/ptyxis --new-window`, with readback; other custom bindings are preserved. The shared guest dependency inventory supplies Ptyxis. Ubuntu retains its existing shortcut. Qualification only exercises the prepared binding and never configures it. |
| Stable fixture folder names across desktop-language changes | `baseline_environment.desktop_settings_files`: per-fixture `Hidden=true` XDG autostart override and empty regular systemd user-unit mask for the optional GTK folder renamer; the baseline reconciler owns placement and read-only verification |
| Stable Ubuntu package inputs during execution | `baseline_environment.automatic_update_files`: empty regular system-unit masks for `apt-daily.service`, `apt-daily.timer`, `apt-daily-upgrade.service` and `apt-daily-upgrade.timer`; the baseline reconciler owns placement and read-only verification. Fedora has no APT masks. |
| Serial getty and the 600-second console login window | [baseline_console.py](baseline_console.py); attempts only verify |
| A/H/S/N GUI binaries, shared Python/GTK runtime and four child launchers | Legacy captures: [baseline_assets.py](../fixtures/baseline_assets.py), installed by [baseline_fixtures.py](baseline_fixtures.py). Clean Ubuntu/Fedora: host-owned, pending runner qualification. |
| Static native enforcement binaries and catalogue precedence/path witnesses | The same target-specific movable fixture ownership; engineering checks only verify |
| Trusted hard/soft native witnesses | Legacy captures: `baseline_assets.TRUSTED_NATIVE`, fixture reconciler and `native_trust` provenance. Clean Ubuntu/Fedora captures contain neither payload nor exact fixture admission. |
| Supporting screen-time and retained activity | Legacy captures: `native_assets.ACTIVITY_EXECUTABLE` and its two private GUI modules retain exact file-trust identities. Clean Ubuntu/Fedora keep these movable inputs on the host. |
| Product package and installed app snapshot | Existing product-installation lifecycle; the baseline stays product-free |
| Private SSH identity, worker transport and evidence | Per-attempt ownership and cleanup |
| Synthetic attachment/copy/rename/save-error inputs, future binaries and launcher removal | Deliberate scenario mutations at their declared checkpoints; preserve independent-entry and cleanup checks |
| Dynamic accounts, directory-service configuration, keyring challenges and fault injection | Scenario-owned state; reusable dependencies still belong in baseline |

The following fixture reconciliation/trust rules describe legacy captures.
Fixture reconciliation verifies the entire declared set before writing. Matching
files are reused; recorded owned files may be updated atomically. Foreign files,
links, hardlinks, unsafe ancestors and changed ownership refuse. The root-owned
fixture record binds bytes, modes and owners and records interrupted placement.
An unchanged repeat performs no fixture writes; owned updates and interrupted
retries have explicit regressions. Accounts/settings preserve unrelated state.
All declaration, builder and runtime sources participate in the baseline digest,
invalidating stale baselines and their derived app snapshots. Independent offline
inspection verifies fixtures and console configuration before capture.
During an explicit refresh, layout classification accepts a structurally valid
older dependency inventory; capture inspection still requires the current
inventory and installed packages before accepting the refreshed baseline.
Trusted native fixtures additionally bind their exact payload identities, native
package/tool identities and generated trust-fragment digest to the preparation
source and fixture record. First placement uses `fapolicyd-cli --file add` for
each fixed input; owned updates use its scoped `--file update` operation.
Preparation atomically publishes only that finite trust fragment.
Durable intent permits interrupted retry without adopting foreign fragments.
Before publication, preparation enables the native file backend only in a
recognized distribution configuration and refuses unrelated inactive trust
entries. A separate durable receipt preserves the exact original/reconciled
configuration and metadata; interrupted activation is reconciled before trust
publication. The native configuration check must pass. The completed fixture
receipt binds this enabled configuration and its backend receipt as well.
No directory trust is added. On Fedora, the stock policy otherwise rejects the
deliberately untrusted A/H/S/N GUI fixtures. Two finite baseline-owned rule files
admit only their exact prepared executable bytes and the two shared Python
runtime payloads for Riley and Jordan. Runtime open admission follows the
product's early concrete denials and precedes the stock language restriction;
execute admission follows the product's late wildcard guards and precedes the
stock execute denial. These content identities also admit identical copies for
those two fixture users; they confer no future-version or copy/update coverage.
The fixtures remain absent from native trust. Preparation and read-only consumers
refuse unfamiliar native rule inventories or modified stock rule sources, and
verify the exact owned rule bytes, metadata and compiled freshness. No product
policy, provenance, grant or enforcement expectation changes. Running consumers
verify the receipt, exact bytes/metadata and loaded native trust database; they
refuse stale or substituted state rather than repairing it during a test.
Read-only restoration may inspect a recorded older Fedora baseline with neither
admission file, retaining its original preparation binding and every other
fixture check. Both files and their staging paths must be absent. This permits
owned cleanup and refresh; new attempts still require current preparation.
The guest dependency inventory declares the distribution's `fapolicyd` package
on both platforms, so its native trust tools are available on clean baselines.
Native vendor trust sources are inspected without adopting or rewriting them;
their root-owned, nonwritable service-group metadata is valid. [Native tmpfiles](https://raw.githubusercontent.com/linux-application-whitelisting/fapolicyd/main/init/fapolicyd-tmpfiles.conf)
recursively sets `/etc/fapolicyd` to the fixed `fapolicyd` group while preserving
file modes. The owned trust fragment therefore uses root ownership, mode 0600
and that exact native group from first publication; provenance binds its
metadata and the service group independently. Reconciliation of a legacy
root-group fragment requires its exact recorded bytes and all other identity
guards. Other owned fixture outputs retain exact root:root ownership.
Conflicting entries for either new
trusted target or the existing untrusted controls refuse before placement.
The folder-renamer overrides use the supported [XDG autostart precedence](https://specifications.freedesktop.org/autostart/latest/)
and [systemd empty-unit mask](https://github.com/systemd/systemd/blob/main/man/systemd.unit.xml).
They preserve existing folder contents and mappings, account/session languages
and all product-language assertions. Unknown prompts still refuse before input.
Console preparation preserves an existing supported `LOGIN_TIMEOUT` entry or
adds `LOGIN_TIMEOUT 600` when none is active. Duplicate or malformed entries
refuse; test attempts only verify the prepared setting and never add it.

Ubuntu's APT masks prevent restored boots from launching automatic package
transactions while qualification observes executable generations. They are
reconciled offline before baseline capture, without stopping a transaction or
repairing settings in a test. Preparation still performs its explicit APT/DNF
updates through the maintained auto-mode route. The existing fixture ownership,
interruption and stale-baseline checks apply to these four files.

Idempotence does not suppress auto-mode system updates or the documented snapshot
replacement. It does not authorize adopting an unknown file or bypassing the
lease, provenance, ownership or product-free gates. The governing rule is the
[VM mandate](../../docs/Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).

### Ubuntu clean snapshots

Ubuntu 26.04 preparation writes marker schema 4. Its baseline and derived app
captures contain environment dependencies and settings, without movable fixture
binaries, launchers, exact fixture trust entries or copied fixture sources.
The native file backend, account pictures and recovery records remain intact.
Fedora uses the same clean boundary, with its platform-specific checks below.

Ubuntu preparation verifies native readiness in a fresh watched boot after
package updates and the final offline backend reconciliation. It uses the
packaged service to enable persistent startup and initialize its own database,
then requires an active service and a successful read-only native database dump
containing vendor package trust before accepting the capture. It never writes
database files or adds fixture admissions. First preparation, unchanged repeat,
updates and interrupted retries use the same baseline-owned step; qualification
and app preparation only verify the prerequisite.
The packaged daemon reports service startup before finishing trust loading.
Preparation uses a bounded read-only wait that requires the native status
handshake, followed by a fresh database dump before recording success. An old
readable database does not establish readiness. Only the native tool's exact
report-wait timeout is retried within that window; other failures stop immediately.
Native failures retain both output streams; service-start and readiness-timeout
failures also retain bounded journal diagnostics.

The Debian native package requires administrator-supplied rule units, as
documented by its [native policy owner](https://github.com/linux-application-whitelisting/fapolicyd/blob/main/README.md#policies).
Preparation bootstraps only the package-verified vendor `95-allow-open.rules`
unit. This open-only rule leaves execution at the native default and adds no
product policy or fixture admission. A separate durable receipt owns exact
bytes, native-group metadata and interrupted publication. Unknown rules, legacy
policy, unexplained compiler output or changed vendor semantics refuse without
overwriting them. The packaged service owns rule compilation and database files.

An explicit auto-mode refresh restores the accepted old baseline before migration.
Retirement first verifies the complete recorded legacy inventory and source
digest. Durable intents permit exact interrupted deletion and temporary source
staging recovery. Ambiguous, substituted or foreign files refuse; unrelated
files and avatar/recovery data are preserved. Product-free captures refuse
retained installation input trees, including archives with opaque payloads.
Legacy marker inspection and recorded stop/restoration remain supported.

`prepare_vm.preparation_files()` and its source projection bind runtime
dependencies, persistent environment declarations, shared product inputs and
clean lifecycle/backend policy. Fixture declarations, compiled payloads and
fixture-only builder bodies do not invalidate clean snapshots. Dependency,
shared lifecycle, installation recipe and product content changes still do.

App preparation transfers only the product package, installation manifest and
frozen installation-helper closure. It preserves installation, reboot,
verification and private online-credential publication. Unqualified runner
envelopes refuse clean captures before input; environment-only maintenance,
watch and baseline credential/display checks retain their explicit routes.

List registered checks with `tools/run-tests integration --list`.
`tools/run-tests integration --vm onpc-Ubuntu26.04 check_fixture_snapshots`
audits actual clean baseline/app captures, retained checkout and archived input
trees, independent byte readback, source/product invalidation and owned final
restoration. Both restored captures must also have an active native service and
a readable database, preserve vendor trust and contain no fixture trust rows.
Every original vendor row and its count must survive app preparation. Added
`debdb` rows are accepted only for exact files reported by the native package
manager for packages installed or updated by the public app installation; other
additions and package removals refuse. Retained results bind those package versions.
Invoke authorized baseline refresh separately; this check never
refreshes a baseline or grants provisioning, runner or customer acceptance.

`tools/run-tests integration --vm onpc-Ubuntu26.04 check_fixture_provisioning`
qualifies the shared provisioner in three separate watched attempts: refusal of
a foreign destination, a minimal trusted-hard runtime on the clean baseline,
and the native/activity/trusted/mechanical union on the installed app capture.
It verifies exact native activation, intentionally untrusted controls, runtime
use, unchanged vendor/product policy and repeated verification without writes.
Native startup and update completion are observed before database reads through
the [shared provisioning boundary](../support/README.md#attempt-owned-fixture-provisioning).
The completed history restores the baseline and independently leaves the VM off.
This Ubuntu infrastructure qualification enables no ordinary runner envelope
and supplies no customer or Fedora acceptance.

Ubuntu's delivered [product-free system preparation](README.md#ubuntu-product-free-system-preparation)
now provisions its selected trusted-hard witness over owned SSH after a clean
baseline boot. The three Parent bootstrap aliases share that boundary.
Ubuntu's [installed-system preparation](README.md#ubuntu-installed-system-preparation)
explicitly restores an offline app capture before fresh bootstrap and hard-only
provisioning. Other envelopes remain separately gated; snapshot checks
and provisioning checks do not substitute for their runner qualifications.

### Fedora clean snapshots

Fedora 44 preparation and derived app captures now use schema 4 with explicit
platform identity. They share the fixture-independent source projection, lean
product installation closure, exact legacy retirement and recovery boundary
above. Legacy Fedora schema-3 records remain readable for recovery. Preparation
preserves accounts, credentials, desktop settings, native dependencies and
enforcing SELinux; unmigrated runner envelopes still refuse clean captures.

Fedora retains its RPM-authenticated stock native policy rather than Ubuntu's
open-only bootstrap. The packaged compiler and fresh-boot service initialize
the clean baseline. Both current compiler output and its previous-output backup
are audited. Only complete receipt-bound legacy fixture admissions and their
proven generated outputs may be retired before compilation; ambiguous files
refuse. A bounded clean-output witness in the existing retirement record preserves
authenticated stock backups across package updates and interrupted retries.

`tools/run-tests integration --vm onpc-Fedora44 check_fixture_snapshots`
qualifies actual clean baseline/app captures, retained source and archived input
trees, fixture-only identity independence, genuine dependency/shared lifecycle
invalidation, product-package identity and watched restoration. It verifies
enforcing SELinux, active native service, readable `rpmdb` trust, every original
vendor row and exact package-owned additions. Native source bytes, metadata,
compiled output and the public rule-file listing must agree. The listing supplies
no daemon-generation acknowledgement.

For the installed capture, the required canary and final fallback are bound to
the actual RPM's file metadata. Optional generated rule units must contain only
the exact empty-policy header and use the independently resolved broker `wheel`
group or native service group. The early originally-unenforced fallback remains
absent for this active baseline; see the
[product policy owner](../../docs/SystemDesign/Applications.md#live-filter-and-execution-rules).
The RPM identity probe changes a private actual archive byte, matching its
conservative exact-archive identity; that copy is never installed. Ubuntu uses
a valid private DEB repack containing changed product-file bytes.

Fedora and renewed Ubuntu snapshot qualification passed, together with separate
auto-mode refresh, standalone Fedora reuse/stop and owned cleanup. The old Fedora
baseline was restored by auto preparation; no pending legacy execution owner
needed live stop recovery. Host regressions retain legacy stop/restoration coverage.
This supplies snapshot infrastructure acceptance only. Fedora's separate
[provisioning qualification](../support/README.md#attempt-owned-fixture-provisioning)
now passed on these clean captures, including enforcing labels, exact admissions,
untrusted runtime controls and interrupted-stage recovery, with renewed Ubuntu
proof. Fedora's [installed-system preparation](README.md#fedora-installed-system-preparation)
uses explicit offline app restoration, fresh SSH bootstrap and hard-only
provisioning with enforcing labels and exact native readback. Fedora's
[installed E2E preparation](README.md#fedora-installed-e2e-preparation) additionally
qualifies online resume/credential rebind and explicit offline Kiosk attachment,
with the same clean captures and exact native/SELinux verification. Other runner
envelopes remain gated pending their own qualification.

### Verified finite native transaction inputs

The native dependency input route is separate from released **product** upgrade
inputs. Prepare a new retained bundle with
`tools/run-tests artifacts prepare --for-vm --native-inputs --vm NAME`;
reverify it with `tools/run-tests artifacts verify-native 'RETURNED-DIRECTORY'`.
For host input preparation without a baseline probe, use
`tools/run-tests artifacts prepare --native-inputs --package-format deb|rpm`;
this still requires the later installed-baseline compatibility preflight.
The existing baseline probe selects the declared DEB/RPM format without starting,
restoring or changing the VM. Missing or stale baseline preparation refuses.
`--upgrade-inputs` continues to mean earlier/current product packages.
The [builder](../../tools/build_test_artifacts.py) also exposes
`--native-inputs --package-format deb|rpm --output DIRECTORY` and
`--verify-native-inputs --output DIRECTORY` for callers already owning a
registered shared-storage allocation; direct building confers no retention.

[`native_transaction_inputs.py`](../../tools/native_transaction_inputs.py)
owns only the reviewed Ubuntu 26.04 `bubblewrap:amd64`
`0.11.1-1` → `0.11.1-1ubuntu0.3` and Fedora 44
`xdg-dbus-proxy.x86_64` `0:0.1.6-4.fc44` → `0:0.1.9-1.fc44` pairs.
Its finite selection pins download locations, native identities, package hashes
and measured executable identity. No alternate version or companion package is
chosen. `native-inputs.json` schema 1 records that selection, both packages and
their control/dependency inventories, measured ELF SHA-256/size/owner/mode,
native verification receipts and the hashes of all retained input files.
`binding_sha256` identifies its canonical content excluding that field itself.
Ubuntu additionally records each measured GNU build ID and authenticates the
retained Packages index through its signed InRelease and the locally trusted
Ubuntu keyring. Fedora verifies native signatures and payload digests using the
pinned Fedora 44 key in an isolated scratch database; system trust is unchanged.
The retained metadata and key bytes remain part of the verified bundle.

Matching published preparation repeats only verify. An interrupted preparation
or copy can resume only its recorded directory and pending file identities;
foreign files, links, hardlinks, writable or replaced inputs and source changes
refuse. A changed finite declaration requires a new allocation rather than
overwriting a published bundle. Scratch uses the shared storage owner; the
retention session owns bundles, and the attempt owns its frozen copy and receipts.

[`stage_native_assets()`](system_runner.py) freezes the verified pair in an
owned attempt input directory and binds the native manifest to the exact
`selected-inputs.json` digest and accepted baseline provenance. Its durable
applicability intent precedes copying, so interrupted retry cannot adopt another
selection or baseline. `verify_native_assets()` rechecks that binding and the
native bundle without repair. The installed runner's
[retained-session native history](README.md#retained-session-native-dependency-update)
composes these routes with target-specific product inputs.

[`native_transaction.preflight()`](native_transaction.py) consumes a verified
manifest and performs read-only checks against the actual installed package set.
It retains exact providers/reverse-dependency inputs, offline single-package
plans, package health/holds, matching external trigger owners/definitions and
the native completion branches below. Ubuntu simulates baseline → old, then old → new
using a private temporary status view in the caller's owned workspace, removed
after each plan. Fedora tests each complete single-RPM replacement
without resolving or downloading other packages. Unreviewed matching triggers,
missing dependencies, extra changes and incompatible state refuse with baseline
refresh guidance. Its receipt binds both native and selected input identities to
baseline provenance; `verify_receipt()` repeats the native probes and checks the
retained state. Neither API establishes an old generation or runs scripts.

Reusable native packages/tools belong to the normal baseline dependency
reconciler and preparation digest. The accepted baseline still receives its
normal auto-mode updates. The later attempt explicitly owns any deliberate old
transaction **before product admission**, ordinary trigger completion and
configuration/reboot. Product installation stays on `make install`; recheck the
old native identity afterward before retaining generation A. Never silently
downgrade the baseline or repair dependencies in a consumer. Prevent automatic
updates from racing the finite transaction through the prepared settings.
On Ubuntu the measured input is the native `/usr/bin/bwrap` source copied to
private `/usr/libexec/oh-no-parent-control-kiosk-bwrap`, rather than the private
wrapper at `/usr/bin/bwrap`; Fedora measures the direct proxy executable.
Actual transaction scripts/triggers, retained mappings, stale-manager refusal,
lease exclusion, reexec and fresh-boot recovery are qualified by the matching
[installed update receipts](../README.md#core-installation-and-runtime-compatibility).
Input verification alone supplies no installed transaction acceptance; changed
helpers/inputs require the affected complete history again.

#### Fedora 44 reviewed external triggers

The finite proxy payload touches `/usr/bin`, `/usr/lib/.build-id` and
`/usr/share/man`. The accepted baseline's additional owners are
`filesystem-0:3.18-52.fc44.x86_64`, `glibc-common-0:2.43-9.fc44.x86_64` and
`man-db-0:2.13.1-3.fc44.x86_64`. `RPM_TRIGGER_REVIEW` pins the complete native
header arrays, including nonmatching registrations and expanded script bytes;
the existing receipt retains the exact definitions, matching payload paths and
index-to-script associations. Unknown owners, changed definitions, malformed
associations and missing expected actions refuse. Owner names alone grant nothing.

The authoritative sources are Fedora's immutable
[filesystem spec](https://src.fedoraproject.org/rpms/filesystem/raw/cf9061fec83ccac5a1ef2359b7a91e39f0c406f6/f/filesystem.spec)
and [expanded filename table](https://src.fedoraproject.org/rpms/filesystem/raw/cf9061fec83ccac5a1ef2359b7a91e39f0c406f6/f/sbin-filenames),
[glibc spec](https://src.fedoraproject.org/rpms/glibc/raw/8e9e7eb6e4f312296c6fc451b8e0ca1049725391/f/glibc.spec)
and [man-db spec](https://src.fedoraproject.org/rpms/man-db/raw/000ef4d2090cfd61db5320f4eaf04401a0163d6c/f/man-db.spec).
RPM's [file-trigger contract](https://rpm.org/docs/6.0.x/manual/file_triggers.html)
and [native flags](https://github.com/rpm-software-management/rpm/blob/rpm-6.0.2-release/include/rpm/rpmds.h)
define `65536` as install and `262144` as post-uninstall. Registration indexes
select script arrays; the registration and script arrays have different lengths.

- Filesystem uses embedded Lua file triggers at indexes 0/1 for `/usr/bin`.
  Its index 2 and transaction trigger cover other paths and do not match this
  payload. The reviewed branch has `/usr/sbin -> bin` and `/sbin -> usr/sbin`:
  both registered scripts return immediately. The per-package post-uninstall
  iterator skips erase actions for files replaced by the incoming RPM, so
  `/usr/bin/xdg-dbus-proxy` does not invoke that script during either replacement.
  Preflight binds each phase's incoming/outgoing paths and this non-execution
  reason. Require the applicable install script, refuse an unexpected extra
  execution and verify unchanged link identities/targets; unmerged layouts need
  a separate review. RPM's pinned
  [file iterator](https://github.com/rpm-software-management/rpm/blob/rpm-6.0.2-release/lib/rpmtriggers.cc#L288)
  filters skipped per-package file actions; its transaction post-uninstall
  registrations are queued separately from the outgoing header before erasure.
- Glibc-common's embedded Lua transaction triggers at indexes 0/1 have priority
  2000000 and match `/lib`, `/lib64`, `/usr/lib`, `/usr/lib64`. Build-ID files
  therefore match even without a shared-library payload. Both scripts invoke
  bare `ldconfig`. Preflight binds its actual search-path resolution, main glibc
  provider and executable bytes. Completion requires fresh loader-cache
  timestamps within the transaction, a valid `ldconfig -p` result and unchanged
  loader entries. Unchanged cache bytes are valid:
  [glibc's exact cache writer](https://sourceware.org/git/?p=glibc.git;a=blob_plain;f=elf/cache.c;hb=9cda6fc96a)
  still replaces the cache. Inode inequality alone is insufficient across two calls.
- Man-db uses shell transaction triggers at indexes 0/1, priority 1000000.
  They request the cache service through systemd-run. Both the request and
  [service](https://src.fedoraproject.org/rpms/man-db/raw/000ef4d2090cfd61db5320f4eaf04401a0163d6c/f/man-db-cache-update.service)
  mask failures, so native status or service success alone cannot prove completion.
  Bind the exact enabled configuration, service, effective drop-ins and
  `/etc/man_db.conf` mapping of `/usr/share/man` to `/var/cache/man`; require
  bounded fresh PID-1 journal start/done jobs, matched by invocation, job, boot
  and monotonic time, plus a fresh manual-cache database
  and independent `whatis --exact xdg-dbus-proxy -M /usr/share/man` success.
  The two native requests may coalesce or produce two complete executions.
  Reject unmatched, duplicate, extra or failed jobs. Do not require retained
  `ExecMain*` properties after the idle service is collected: systemd explicitly
  [discards that runtime state while preserving journal records](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html#Unit%20Garbage%20Collection).

The current reviewed engine is RPM 6.0.2. All six registration associations remain
pinned; each actual replacement requires five executions, with the filesystem
post-uninstall non-execution bound to the replaced path. The normal single-RPM
transaction uses `-vv` to retain every expected Lua entry and shell start/exec/matching successful
wait, refusing missing, duplicate or additional trigger executions.
[RPM's script runner](https://github.com/rpm-software-management/rpm/blob/rpm-6.0.2-release/lib/rpmscript.cc)
does not log Lua exits; the
[transaction result](https://github.com/rpm-software-management/rpm/blob/rpm-6.0.2-release/lib/transaction.cc)
propagates script failure. Require that result and each independent completion
observation. The receipt also binds rpm, shell, systemd and man-db executable
providers/bytes. Private before-state, native output and completion records use
the existing redacted failure/reboot collector. Safe typed preflight reasons
survive the guest command route without exporting private path/argument suffixes.
These engineering checks alone grant no installed acceptance. Both complete
case 289 histories with matching input/helper bindings passed in the
[accepted update receipts](../README.md#core-installation-and-runtime-compatibility).

## Resources

| Resource | Contract |
| --- | --- |
| Libvirt connection and domain | `qemu:///system`; `name` in the shared config; guest hostname is its lowercase form |
| Host/guest preparation checkout | The checkout containing the invoked `tools/prepare-vm`; maintained guest modules are staged privately inside the VM. Installed helpers validate the invoking checkout at runtime through the [embedded resolver](../../tools/dev_checkout.py), rather than retaining an installation-time checkout path. VM UUID pins remain separately bound to finalized baseline provenance. |
| Disk-chain anchor | `disk_anchor` in the shared config; resolve and validate the actual active chain. |
| Retained product-free baseline | Internal `onpc_baseline` snapshot, captured while off, without VM memory; name defined by `SNAPSHOT` in [prepare_baseline.py](prepare_baseline.py). Runners also accept `onpc-baseline` and `oh-no-parent-control-baseline`; explicit preparation replaces them with `onpc_baseline`. |
| Controller state | Root-private `/Data/virt-manager/oh-no-parent-control-baseline-state/<configured-name>/` |
| Provenance and active attempt | Immutable finalized `phase.json`; separate mutable `system-run.json`. |
| Guest preparation record | Root-owned mode-0600 `/etc/oh-no-parent-control-test-baseline.json` |

The shared config is the sole definition of the VM name. To rename the same
pinned guest, use `tools/test-vm --vm NAME rename --new-name LABEL` while it is off and
idle, then update the config's `name`, refresh test tools, and run auto-mode
baseline preparation. The guarded rename keeps disk paths and snapshot contents,
attests historical snapshot domain names, and moves the existing private provenance tree.
Its rollback records preserve original metadata; unfinished records block tests.

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
the host's `tools/prepare-vm` during its controlled guest boot.
Dependencies are OpenSSH server, pytest, `spice-vdagent`, `fapolicyd`, OpenLDAP server/client
and SSSD LDAP/NSS packages, including their package-manager-resolved dependencies.
Ubuntu additionally declares `libpam-cgfs` so native LXC session callbacks are
present during installation and confined manager teardown. The package's default
`cgfs` profile must remain enabled in both shared session stacks. The
[first-configuration history](README.md) verifies the effective rules before
installation, after successful retry and after reboot; package presence alone
does not establish this coverage. Missing or altered rules refuse that history
with baseline-refresh guidance. Tests never enable the profile to repair their
own prerequisites. This input passed the complete native installation/retry/reboot
and confinement histories on Ubuntu, with Fedora regression acceptance retained;
see [accepted installation receipts](../README.md#core-installation-and-runtime-compatibility).
Other PAM variants use the separate `system_pam_variants.py` histories.
Preparation normalizes official Ubuntu archive URLs to HTTPS, verifies installed
minimum qualified versions, accepts newer security/maintenance versions,
generates missing SSH host keys, enables SSH and checks public-key
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

LDAP/SSSD fixture state remains absent: Ubuntu requests OpenLDAP's supported
no-configuration installation; Fedora preserves the RPM's default configuration
and reserves separate fixture configuration/database paths. Both disable automatic
directory-service startup and refuse active services or fixture collisions.
Existing configuration is never deleted. Remote identities are created only by
the selected test through Ubuntu's `dpkg-reconfigure` or Fedora's `slapadd`
configuration import, followed by the same LDAP public APIs and real SSSD NSS
enumeration. Fedora confines slapd to loopback/LDAPI, preserves enforcing SELinux,
and clones the active authselect profile for the NSS change, retaining its PAM
stack and features; fixture teardown restores the original product profile.
Installed NSS libraries alone do not
create remote users. Product installation and its dependencies, run markers, policy mutations, assertions and real installation/
expiry reboots remain runtime work.

Current preparation records use schema **4** with explicit platform identity and
the expected tool inventory. Readers retain legacy Ubuntu schema **2**, Fedora
schema **3** and earlier Ubuntu schema-4 records for recovery. The source digest
includes the shared inventory module and clean lifecycle/environment projection. Offline inspection
independently verifies the platform's dpkg/RPM installed status and refuses existing LDAP/SSSD
fixture configuration. Missing/wrong-version tools and schema-1 account-only
baselines are refused; lease acquisition checks the preparation source digest
before disk audits, journal writes or VM mutation. Tests no longer repair them
by installing tools. This
test-environment change needs a prepared and accepted product-free baseline;
there is no product-data migration or package activation (`none`).

**Existing accepted baseline:** either explicit preparation mode replaces it.
The VM must already be off; preparation fails instead of shutting it down.
Auto restores the old baseline; manual keeps the current disk state. Both
retain the old baseline until preparation and offline inspection succeed.
Ownership checks and incomplete-attempt
refusals still apply, and the old journal is archived. Ordinary `./setup.sh`
never invokes baseline preparation. Tests continue to reuse the accepted baseline.

**Manual snapshot maintenance:** restore any snapshot you manage (such as
`1 - Clean`), perform maintenance, shut down, and delete/retake your snapshot.
Then run `tools/prepare-vm --vm NAME --mode manual`. The command uses the current guest disk state
without choosing or restoring any snapshot. A changed active image or backing
chain on the same recorded VM is accepted automatically, provided the chain
still ends at the configured anchor. The automation baseline and all versioned
app snapshots are replaced/deleted; other manually managed snapshots are
preserved. Previous provenance is archived before baseline replacement.
The warning requires confirmation. The VM-off, same-UUID, idle-controller and product-free checks remain
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
[pinned VM commands](../../docs/Approval-Tools.md#the-configured-test-vms)
(`tools/test-vm --vm NAME status`, `start`, `reboot`, `send-key`, `screenshot`, `stop`,
`reset`). They share this controller's lock and provenance and never accept
another domain, URI, disk, XML or snapshot. A maintenance attempt must be stopped
before starting a system/E2E run. Routine test runs continue through their
existing guarded controllers; raw `virsh` commands bypass these contracts.

Shutdown and reboot use the shared guarded SSH transport under the
[VM lifecycle mandate](../../docs/Mandates/VM-Mandate.MD#owned-maintenance-and-execution).
Baseline maintenance bootstraps attempt-owned SSH access without installing the
product; its private credentials remain bound to that run, VM and baseline.
Online app maintenance reuses its verified saved identity. Off/boot observations
and final baseline audits remain mandatory after a successful SSH request.

Only the guarded runner may perform a normal test reset under its exclusive
lease, outside a complete independent attempt. It restores the retained
baseline, removes host transfer channels before boot while retaining the private
SPICE display-agent channel for automatic resolution matching and always-enabled
clipboard sharing (file transfers remain disabled),
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

External firmware/TPM state outside the recorded snapshot contract is refused.

## VM disaster recovery

The [`backupvm`](../../tools/backupvm) and
[`restorevm`](../../tools/restorevm) commands read `backup_root` from
[`config/test-vm.json`](../../config/test-vm.json). Run them as the unprivileged
local administrator after ordinary `./setup.sh` on a replacement host, or
`./setup.sh --test-tools-only` to refresh existing development helpers.
They accept the same `--vm` names, IDs, comma-separated lists, `all-enabled`
and `all` selectors as baseline preparation. Their default is **all**, including
disabled entries. IDs resolve from the current registry on every invocation.

```sh
tools/backupvm
tools/backupvm --vm '1,2'
tools/restorevm
tools/restorevm --vm '1'
```

Backup restores each VM's existing accepted baseline, deletes all versioned app
snapshots and the baseline snapshot, then archives the resulting powered-off,
product-free guest. It does not update packages or run baseline/app preparation.
One exclusive VM lease covers restoration, deletion and copying. Shut down selected
VMs completely before invocation; disable their libvirt autostart and finish any
owned maintenance/test attempt. Baseline provenance is verified before mutation
and retained as historical evidence. A durable preparation journal permits retry
after snapshot deletion; snapshot-free archives have no active baseline record.
An unfinished backup blocks ordinary preparation and execution until the same
backup route completes. Retries recheck unfinished test and maintenance ownership
before restoring or deleting snapshots.

Archive copying is strictly serial. Each VM has
one complete backup directly in `backup_root/NAME/`, with independent sparse
disk-chain copies, inactive domain XML, snapshot hierarchy/current snapshot,
referenced persistent network definitions, private baseline provenance and any
saved-memory credential record. `complete.json` binds the manifest checksum.
Copies are checked against their source hashes before
publication. Full payload checksums are specific to disaster
archives; ordinary test disk verification remains metadata-only. A replacement
is built in a private temporary folder directly under `backup_root`, then
atomically exchanged with the VM folder. Partial copies never replace the
previous complete backup. The superseded copy and temporary folder are removed
using recorded filesystem identities; interrupted publication/cleanup resumes
on retry. There are no date/version folders or retained successful generations.
Failed copying cleans its recorded temporary files. Unknown or replaced entries
are preserved and reported as a failure in red, with a nonzero exit status.
Success is reported only after every selected VM completes.

`backup_root` must be a dedicated root-private directory, not a shared folder
containing unrelated backups. The configured default is
`/Data/virt-manager/backups/onpc`; the tool creates it with owner/group root and
mode `0700`, including beneath a setgid parent. Existing shared folders are
refused without changing their ownership, permissions or contents.
Legacy generation archives remain readable by restore; backup refuses to
discard an untracked legacy hierarchy and requires a new dedicated root.

Restore processes selected VMs serially, validating each archive before changing
its VM. Missing libvirt domains and disks are recreated; an existing domain must
have the archived UUID, matching registered disk layout, and be powered off
without autostart or managed-save state. Disk paths must not be shared with
another domain.
Foreign storage references are checked again after staging each payload and
before publishing it, and before redefining the restored domain.
Names/anchors must match the current registry; selector IDs, scheduling flags
and unrelated checkout edits remain current. The archive also
contains the source registry for reference, without overwriting current config.
Changing `backup_root` on a replacement host does not invalidate guest preparation.
Original disk owners/groups must exist on the replacement host; ownership is
mapped by account names. Missing referenced networks are restored; conflicting
existing networks are refused rather than overwritten. An otherwise equivalent
named network on a fresh host keeps its current UUID.

Missing images belonging to other inactive domains do not block serial recovery
after a multi-VM disk loss. Their domain/snapshot XML and every readable backing
link are still checked for shared paths. Missing storage of an active foreign
domain and symlinked paths are refused. Restore journals network creation intent
and UUIDs before defining missing networks; interrupted retries finish their
archived activation and autostart settings. Equivalent pre-existing networks
retain their current runtime settings. A changed network UUID or definition
refuses the retry. Older journals can acquire this plan; in the metadata phase,
an exact archived network UUID/definition is reconciled to its saved runtime
settings. Equivalent networks with another UUID keep their current settings.

Restore retains displaced files and previous domain/snapshot definitions under
its private journal. A matching interrupted restoration resumes the same generation,
UUID and filesystem identities; damaged or superseded recovery journals are retained
before a new transaction begins. Ordinary preparation/execution refuses an
unfinished restore. It recreates snapshot metadata through libvirt's redefine
API without creating/reverting snapshots, rebinds baseline directory/disk inode
identities, verifies the preserved internal baseline proof, and leaves the VM
off. After the entire archive selection succeeds, the launcher calls
`tools/prepare-vm --vm SELECTION --mode auto --y`. Snapshot-free restored guests
first acquire an accepted baseline through the shared reconciliation code, then
receive automatic baseline updates and the current app snapshot. Preparation
keeps one VM lease throughout and finishes with the baseline restored and VM off.
Its queue refreshes helper UUID pins once. Preparation failures are reported
separately from successful archive restoration. No product is installed on the host.
Snapshot-free bootstrap authority binds the restored disk identities and change
timestamps, domain XML and snapshot inventory to the completed restore journal.
Changing that guest before bootstrap refuses automatic preparation; rerun
`tools/restorevm` to establish verified restored state again. Older completed
journals without this binding also require restoration before bootstrap.

For explicit disaster recovery, the verified restored VM and archive are the
authority for local bookkeeping. Corrupt/stale baseline records do not prevent
replacement of registered destinations. Local provenance or saved credentials
absent from the archive are durably moved aside; restored historical test-run and
maintenance-owner records are also retired, never converted into passing results
or adopted as current owners. Their bytes and displaced destinations remain
available for diagnosis. Required archived rename attestations remain available
for snapshot verification. Retirement and baseline rebinding can resume after
interruption. Active domains, held leases, foreign storage references, unsafe
paths and conflicting identities still refuse restoration.

A completed restore binds the exact rebound baseline state to its original logical
hash. Shared preparation, execution and maintenance consumers use this binding,
so preserved app-snapshot/guest-memory provenance survives host inode changes.
Changed baseline state receives a new hash; ordinary disk identity, snapshot proof
and preparation freshness checks remain mandatory. A subsequent archive preserves
the logical hash across repeated recovery.

Preparation-source freshness still applies after recovery and is reconciled by
the automatic preparation follow-up. External snapshot
files, firmware/TPM state and unsupported disk layouts are refused under the
existing VM boundaries. Backups cannot restore host dependencies, arbitrary
unregistered machines or unrelated checkout files. Preserve backup storage
outside any host corruption domain you need to survive.

Host-safe refusal, corruption, interruption/retry and provenance reconciliation
coverage lives in
[`test_vm_backup_cleanup_safety.py`](../unit/test_vm_backup_cleanup_safety.py).

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
`tools/prepare-vm --vm NAME --mode manual`; manual deletion is unnecessary. Refresh an older
installed setup dispatcher first with `./setup.sh --test-tools-only`.
The retained `./setup.sh --replace-missing-baseline` recovery mode handles an
already deleted baseline without replacing an existing one. It requires unchanged
source identities, no remaining baseline metadata or internal disk record, and no
incomplete test attempt. Under the shared controller lock it retains the original
journal as `retired-<operation>.json` before beginning a new capture. Guest
validation and disk verification still apply. Retries resume the new operation
or preserve its finalized snapshot. Explicit preparation replaces a finalized
snapshot after confirmation. Development activation is on the next invocation after helper refresh;
no product service or saved-data change is involved.

An incomplete prior system run prevents a new run. Use only a supported,
identity-verified recovery path for that recorded attempt; if recovery is not
implemented for its state, diagnose and repair the controller before reuse.
Baseline preparation automatically invokes shared recovery for a powered-off
unfinished test attempt before beginning preparation. Recovery revalidates the
recorded identities and preserves evidence. Auto mode also recovers a matching
powered-off maintenance owner through the shared guarded stop path before
preparing the baseline. Manual mode takes the retirement path below, preserving
the current disk state.
Explicit manual baseline preparation can supersede a powered-off maintenance
attempt, including a never-started preparation phase with a null domain ID,
when its private `vm-control.json` matches the journal, UUID, accepted baseline
and snapshot metadata. Disk-chain
identities must still match. An existing baseline must match the owner's exact
snapshot digest and the accepted internal disk proof. A missing baseline can be
replaced only when both its libvirt metadata and internal disk record are absent;
an orphan record is refused. No old disk or configuration is
restored. Only after confirmation, successful guest preparation and independent
inspection are the original run and ownership records archived and the attempt
closed with outcome `superseded`. This supplies no test acceptance credit.
Unproven ownership, changed snapshot proofs and busy controllers still refuse
preparation without discarding the journal. Ordinary runners require completed
journals after their supported startup recovery.
Shared test cleanup also accepts a never-started `cleanup-requested` attempt
with a null domain ID only while the VM is off. It verifies the recorded run,
configuration, source identities and baseline proof before restoring the outer
baseline and original configuration, or auditing an already restored guest.
It never boots or adopts an unrecorded running instance.
Shared preparation recovery also stops matching maintenance owners, including
never-started phases while off. An interrupted online restore with no recorded
instance ID additionally requires the exact private saved-snapshot credentials,
baseline and isolation proof; its observed instance ID is checked again under
the exclusive lease. Replaced instances and changed proofs refuse recovery.
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
use `tools/run-tests integration --vm NAME check_system_recovery`. It uses the same
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
