# Installed-system runner

**Scope — 2026-09-14:** preserve established installed, unit/component and
runner regressions. Mechanical installation, upgrade, migration, removal and
startup recovery still require their internal checks in package/system qualification.
Customer E2E instead follows the
[surface-only contract](../../docs/TestAutomation/E2E-Building-Blocks.md) and is
prioritized in the [E2E building blocks](../../docs/TestAutomation/E2E-Building-Blocks.md).
Accepted installed setup can provision its prerequisites; internal product
assertions and the deferred policy probe are not customer dependencies.

Use the [E2E building blocks](../../docs/TestAutomation/E2E-Building-Blocks.md) for command scope and the
[test contributor guide](../README.md) for local layers and safety prerequisites.
This document retains the implemented runner and artifact contracts. Initial
setup tasks, historical test counts, and dated acceptance directories are not
instructions for a new run.

For host-only runner regressions, use the [shared fixture library](../support/README.md).
Installed areas share real broker calls and snapshots through
`system_assertions.py`, and guarded identity creation/deletion through
`system_accounts.py`. Keep their staging registrations in
`system_runner.AREA_SELECTED_HELPERS`; guest execution must never import host mocks.

## Environment and ownership

Installed-system tests use the real package and operating-system services on
the existing VM selected in [config/test-vm.json](../../config/test-vm.json).
They do not install the product or change
accounts, PAM, Polkit, services or policy on the development host. An existing
host product installation is preserved. Detailed identity, baseline and
recovery requirements are in [Environment.md](Environment.md).

The runner exclusively leases the VM, validates the finalized baseline and
recorded disk/domain identities, restores only outside a complete attempt,
detaches transfer channels before boot, and leaves the VM
off with its prior persistent domain configuration restored after cleanup.
It reuses a current E2E version snapshot, refreshing missing or stale inputs, and creates no
new VM, disk copy or overlay. A real reboot within an
attempt preserves guest state and must produce a new boot identity.

The host and guest tooling sources are `setup.sh`,
[../test-tools-ubuntu-26.04.txt](../test-tools-ubuntu-26.04.txt),
and the [prepared guest tool inventory](guest_test_dependencies.py). Record actual runtime
versions in each result; do not use a dated development-workstation package
table as evidence of the installed guest's environment.

## Package and fixture inputs

`tools/build_test_artifacts.py` builds without installing the product on the
host. Its API and CLI require an explicit `deb` or `rpm` package format.
For VM qualifications, use the maintained runner, which derives that choice
from pinned baseline provenance and prepares the declared input automatically:

```sh
tools/run-tests --vm NAME integration 'check_e2e_riley_native_grid'
```

Replace `NAME` with the registered VM name or ID from
[config/test-vm.json](../../config/test-vm.json).

For an independent host build, `tools/run-tests artifacts build` explicitly
uses the Debian builder; `tools/run-tests artifacts prepare --for-vm --vm NAME`
selects the registered VM's required builder. Direct Make builds require
`PACKAGE_FORMAT=deb` or `PACKAGE_FORMAT=rpm` and a new registered test output.
See [qualification preparation](../README.md#scripted-repair-loop) for declaration
and cache validation rules. Output contains
`artifact-manifest.json`, the selected package in `package/`, and
deterministic native/Flatpak fixture assets in `fixtures/`. The manifest records
source revision/content digest, source date epoch, architecture, build inputs,
tool versions, and package/stable-fixture digests.

**Source selection (2026-09-13):** `build_test_artifacts._source_paths` and
`e2e.provenance.source_paths` bind all tracked/nonignored inputs, including
documentation, to current bytes/modes. Both readers use NUL-delimited paths
and the same Path ordering.

`tests/fixtures/build_test_applications.py` supplies real long-running native
executables, path/space/version-pattern variants, desktop entries and a minimal
Flatpak runtime/application bundle. `make check-test-fixtures` tests the builder
and identity-recorded processes with private temporary Flatpak state, never the
developer's actual installation. It runs isolated cleanup prerequisites first,
then the portable builder tests and `tests/fixtures/test_runtime.py` against an
owned private system bus. The runtime check requires unprivileged kernel
namespaces; it remains mandatory release acceptance on the prepared host, while
Launchpad's restricted build chroot runs bundle validation and native-launch
tests through `make check`. No runtime failure is skipped or treated as a pass.
`make build-test-fixtures OUTPUT_DIR=...`
retains a payload for focused fixture work. These are enforcement targets, not
proof of real-game behavior. Later Snap and game assets must use the same
verified input discipline.

`make verify-test-artifacts FIRST_OUTPUT=... SECOND_OUTPUT=...` performs two
isolated builds and compares package bytes, contents/metadata, recorded inputs
and the stable fixture payload. Both outputs must be new. Flatpak delivery
containers can carry host-clock metadata; their stable payload digest is
distinct from the exact-byte hashes verified during transfer. Do not claim
byte-identical delivery containers when only their payloads were compared.

The builder records `DEB_BUILD_OPTIONS=nocheck`: current controller tests require
the fixed development checkout and run through host checks separately. A
successful build alone therefore does not establish passing tests. Test the
current source/package inputs; previous acceptance artifacts are not defaults.
Future `test-system`/`test-e2e` prepare inputs automatically, and `test-all`
coordinates host results and VM artifacts for the same source content.

### Ubuntu product-free system preparation

On clean Ubuntu 26.04 and Fedora 44 captures, `system_snapshots._run_attempts(installed=False)`
and `system_runner.installed_run(already_installed=False)` use the
[shared fixture provisioner](../support/README.md#attempt-owned-fixture-provisioning)
after guarded SSH readiness, before uploading installation inputs or running a
system phase. The launcher selects the execution-owned immutable input before
VM acquisition. Only `trusted-hard` is provisioned; readiness binds the selected
manifest, VM UUID, actual boot and unique attempt. Missing or incompatible
selections release no input. Other unmigrated
envelopes retain their refusal.

`check_parent_setup`, `check_parent_input` and `check_parent_standard_input`
use that same boundary after `Transport.probe_ready` and before
`InstalledSetup.run`. Their explicit package-only staging and provenance retain
the package, installation metadata and frozen helpers, without the legacy
fixture collection. `package-input.json` has its own schema and verifier;
it never claims to be a full artifact manifest. System histories retain only
their finite scenario comparison inputs: the mechanical file, or six files for
trusted histories. Each attempt drops comparison files needed only by other
histories. Exact package, prior-release, source, version and architecture checks,
first-configuration/PAM dispatch and `fresh_install` grouping remain enforced.

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_system_product_free
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_system_product_free
```

This engineering selector executes the actual product-free system preparation
twice, stopping before installation input or any phase. It independently reads
the single manifest member, runs the headless hard witness as Riley without a
desktop file, verifies no-write repeats, and rejects the prior restored
generation's readiness. Its host producer selects from a registered private
source checkout and edits that same checkout after selection; authenticated
source proof and runtime inputs stay pinned through VM cleanup. Both boots
preserve product absence, selected bytes and unrelated native policy. Watched
baseline restoration, producer and transport cleanup are required. This grants
no system-phase, customer or E2E acceptance.

### Fedora product-free system preparation

Fedora 44 uses the same product-free boundary and engineering selector above.
Its selection must match the restored Fedora guest and RPM package format.
Independent readback additionally checks enforcing SELinux, exact labels and
unchanged native admission sources, compiled rules and public rule listing.

### Ubuntu installed-system preparation

On clean Ubuntu 26.04 and Fedora 44, `system_snapshots._run_attempts(installed=True)` explicitly
selects the offline app-snapshot mode through `Suite.prepare_case`. Creating a
new app capture installs, restarts, verifies and shuts down the guest before
taking its disk-only snapshot. Both capture modes keep post-restart package,
configuration and service verification. The restored
app is bootstrapped with fresh attempt credentials; an online resume cannot
qualify this branch. After SSH readiness and system startup completion,
`system_runner.installed_run` uses the
same immutable input and trusted-hard provisioner before uploading system input.
Installed-product verification and all system assertions remain in their
original order. A session reboot requires read-only readiness renewal for the
new boot after system startup completes, without replacing fixtures or resetting
scenario state. Startup waiting never restarts services; native checks still
require an active daemon and its current-boot initialization event.

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_system_installed
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_system_installed
```

This engineering selector exercises two actual offline app restores. It stops
before system input or product assertions, independently checks the selected
manifest bytes and Riley's headless runtime witness, and proves input refusals,
fresh readiness, no-write repeats and unchanged selection after producer-source
edits. Results retain package metadata and frozen helpers, without the complete
fixture collection. Watched baseline restoration and owned credential, staging,
input and transport cleanup remain required. Other unmigrated envelopes remain
gated. This supplies no customer or E2E acceptance.

### Fedora installed-system preparation

Fedora 44 uses the same explicit offline app restore and installed-system
selector above. Independent readback also requires enforcing SELinux, exact
labels, finite native trust and unchanged native admission sources, compiled
rules and public rule listing. Read-only readiness renewal after a session
reboot preserves the selected bytes and scenario mutations.

### Ubuntu installed E2E preparation

Clean Ubuntu 26.04 and Fedora 44 installed E2E attempts select their immutable `native`
runtime input before VM acquisition. After app-snapshot restoration, guarded
SSH readiness and fresh credential binding, `InstalledSetup.provision` uses the
[shared provisioner](../support/README.md#attempt-owned-fixture-provisioning)
before scenario asset transfer and input. `InstalledJourney` and the
installed qualification aliases share this boundary. Online resume and explicit
offline restore retain their own preparation proof; an online result alone
cannot qualify the offline branch.
The offline attachment requires the exact validated inactive domain settings in
its shut-off disk snapshot, then applies the lease's isolated settings before
boot. Online captures retain their private-console and sharing checks.

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_e2e_installed
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_e2e_installed
```

This preparation-only check stops before worker or product assertions. It
independently checks selected manifest bytes and harmless native use as Riley,
missing/incompatible refusal, fresh attempt readiness, no-write repeats and
unchanged selection after actual producer-source edits. Results retain package
metadata and frozen helpers rather than the complete fixture collection.
Scenario asset mutations remain separate. Watched baseline restoration and
owned credential, staging, input and transport cleanup are required.
Standalone transfer and serial retain their separately qualified preparation
boundaries; unqualified fixture profiles remain gated. This supplies no customer or E2E acceptance.

### Fedora installed E2E preparation

Fedora 44 uses the same installed boundary and preparation-only selector above.
Its immutable input must match the selected VM and restored guest. Two online
resume/rebind attempts and two explicit offline Kiosk attachments independently
verify the native runtime, enforcing SELinux, exact finite admissions and labels.
Fresh attempt readiness, prior-generation refusal, unchanged selection after
producer-source edits and watched restoration remain required on both branches.

### Ubuntu product-free E2E preparation

Clean Ubuntu 26.04 product-free graphical attempts select their immutable `native`
input before VM acquisition. `InstalledJourney.product_free` and the asset-bearing
package/upgrade preparations share a post-SSH setup boundary: provision and verify
fixtures, then transfer package-only scenario inputs, then recheck readiness before
releasing customer input. No reusable payload or customer package is uploaded
before SSH readiness. Upgrade transfer keeps its current/previous package identity,
account/locale preservation and wrong-attempt, collision and replay refusals.
GDM-only entry selects an empty closure, requires no native input and transfers
no movable payload. Dormant install-current-package and Parent About/access smoke
guards remain unavailable. Scenario installation/update and all customer
checkpoints remain unchanged.

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_e2e_product_free
```

This preparation-only selector runs distinct entry, package, upgrade and empty
GDM histories through their actual context preparation. The native histories
independently read all 12 selected files, run A harmlessly as Riley, verify input
refusals, no-write repeats, fresh attempt/boot readiness and unchanged selection
after actual producer-source edits. Every history proves product absence and
stops before customer package input, worker input or product assertions. Ordered
host composition binds all 13 declared smoke exceptions to their real boundary.
Watched baseline restoration and owned producer, credential, staging, input and
transport cleanup remain required. Other envelopes retain their own gates.
This supplies no customer or E2E acceptance.

### Fedora product-free E2E preparation

Clean Fedora 44 graphical attempts use the same
[product-free preparation boundary](#ubuntu-product-free-e2e-preparation),
including distinct entry, package, upgrade and empty GDM histories. The selected
VM must explicitly declare its package format in [the registry](../../config/test-vm.json);
Fedora declares `rpm`, with no default or fallback. Upgrade preparation verifies
the pinned earlier Fedora release and current RPM sources, versions, architecture
and exact bytes. Native provisioning preserves enforcing SELinux, exact finite
admissions and labels. GDM-only entry has no native input dependency or movable
payload. Dormant guards and customer checkpoints remain unchanged.

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_e2e_product_free
```

The same independent readback/runtime, refusal, no-write repeat, fresh readiness,
source-edit immunity and product-absence checks apply. Stop before customer or
worker input and product assertions; finish watched baseline restoration and
owned cleanup. This supplies no customer or E2E acceptance.

### Ubuntu standalone transfer preparation

Standalone `runner --qualify-transfer` selects its immutable `native` input
before VM acquisition and uses the product-free baseline. Preboot work stages
only SSH transport prerequisites. `Qualification.execute` defers asset delivery;
Smoke provisions the selected runtime after guarded SSH readiness, transfers
package-only scenario assets separately, and rechecks readiness before its first
ready reply. Package/upgrade inventory, collision and replay guards remain owned
by `AssetTransfer`.

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_transfer
```

This preparation-only selector exercises that real controller and Smoke boundary
once, independently reads the selected native files, runs A harmlessly as Riley,
and verifies product absence, no preboot payload, no-write repeats and current
attempt/boot readiness. Focused host checks protect input refusal, immutable
selection and ordering; unchanged shared uncertain-transfer/recovery proof is
reused. It stops before graphical or customer input. Watched baseline restoration
and owned staging, input and transport cleanup remain required. Fedora standalone
serial and all recorded serial aliases retain their separate gates. This
supplies no customer or E2E acceptance.

### Fedora standalone transfer preparation

Fedora 44 uses the same standalone controller and Smoke readiness boundary,
with package-only RPM delivery after the selected native runtime is ready.

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_transfer
```

The same independent 12-file readback, harmless Riley runtime, input refusals,
no-write repeats, product absence and no-preboot-payload checks apply. Fedora
also preserves enforcing SELinux, exact native admissions and labels. The check
stops before graphical or customer input and finishes watched baseline
restoration and owned cleanup. It supplies no customer or E2E acceptance.

### Ubuntu standalone serial preparation

`check_graphical_serial` and `runner --qualify-install` / `--qualify-install-refusal`
select the immutable native input before restoration. The real standalone
`Qualification.execute` retains credential verification and the stock serial
getty check before boot. It bootstraps SSH only, then reuses Smoke's shared
post-SSH native readiness step before the first reply. Package-bearing aliases
defer their separate package-only transfer until that runtime is ready; bare
serial needs no package input.

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_serial
```

This preparation-only selector exercises one actual serial credential/getty
history, independently reads the native selection, runs A harmlessly as Riley,
and checks product absence, no preboot payload, no-write repeats and current
attempt/boot readiness. It stops before attaching a serial console or releasing
graphical, authentication, installation or worker input. Focused host checks bind
the aliases and retain recording seals, fresh secret recipients, single-use
input, successful-install reboot and refused-install logout/no-reboot assertions.
Watched restoration and owned credential/staging/input/transport cleanup remain
required. Recorded serial has a [separate Ubuntu qualification](#ubuntu-recorded-serial-preparation). This
supplies no customer or E2E acceptance.

### Fedora standalone serial preparation

The same standalone serial preparation and authenticated install/refusal
preparation aliases select Fedora's immutable native input before restoration.
Credential/getty preboot checks and the shared post-SSH Smoke readiness step
retain the Ubuntu ordering and input guards.

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_serial
```

One real preparation history independently verifies native bytes, harmless Riley
runtime use, enforcing SELinux, exact native admissions/labels, input refusals,
no-write repeats and current attempt/boot readiness. It preserves product absence
and stops before console attachment, authentication, installation or worker input.
Host composition binds the aliases and preserves successful-install reboot versus
refused-install logout/no-reboot assertions; it grants no package/login acceptance.
Recorded serial has a [separate Fedora qualification](#fedora-recorded-serial-preparation).
Watched restoration and owned cleanup are required;
this supplies no customer or E2E acceptance.

### Ubuntu recorded serial preparation

`controller_qualification.E2E_CASES['gdm-observation']` uses
`serial_harness.record_serial_journey` under the real `execution.ScenarioContext`
and recorder. It selects Ubuntu's immutable native input before restoration,
preserves credential/getty setup before boot, and reuses Smoke's post-SSH
readiness before the first reply. Separate package-only delivery remains deferred
until native readiness. The recorder saves the selected input and its manifest,
VM, boot and attempt binding in a durable observation before acknowledging ready.

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_recorded_serial
```

This preparation-only check runs the actual recorded caller once, independently
verifies the 12 native files and harmless Riley runtime use, and checks missing
or incompatible inputs, no-write repeats, product absence and fresh readiness.
It stops before starting a serial worker, attaching a console or releasing input.
The full scenario deliberately remains incomplete and rejected; no HAR09/HAR10,
login/logout, product or customer acceptance is claimed. Host checks preserve
those stage, private-seal, recipient, continuity and owned-shutdown guards.
The check requires recorder/collector closure and watched
baseline/credential/staging/input/transport cleanup. Its child owns the ordinary
result and command-log allocation; no proof archive is required.

### Fedora recorded serial preparation

The same recorder/`ScenarioContext` preparation selects Fedora's immutable native
input before restoration, preserves credential/getty setup before boot and binds
the input and fresh readiness durably before the ready reply.

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_recorded_serial
```

One actual recorded preparation independently verifies the 12 native files,
harmless Riley runtime use, enforcing SELinux and exact native admissions/labels.
Input refusals, no-write repeats, product absence and current attempt/boot readiness
pass through the same shared helper. Recorder/collector closure and watched
baseline/credential/staging/input/transport cleanup are required.
The check stops before worker or serial input and deliberately rejects the
incomplete full scenario. It supplies no HAR09/HAR10, login/logout, product or
customer acceptance. Unchanged Ubuntu preparation and shared safety proof remain
applicable; host composition preserves the recorder's stage, seal and shutdown guards.

## Idle fixture maintenance refresh

Ubuntu 26.04 and Fedora 44 support a dedicated product-free maintenance guest with
the fixed `trusted-hard` subset. Select either registered target:

```sh
tools/test-vm --vm onpc-Ubuntu26.04 start --fixture-maintenance
tools/test-vm --vm onpc-Ubuntu26.04 sync-fixtures
tools/test-vm --vm onpc-Ubuntu26.04 stop
```

Use `onpc-Fedora44` in the same commands for Fedora. Refresh preserves enforcing
SELinux, exact file labels and the finite native trust entries; vendor and product
policy remain unchanged.

The first sync builds and retains authenticated host input A. After fixture source
edits on the host, repeat sync to build and retain B in the same host owner,
verify A and B, and replace only the
same selected destinations and exact native entries. An unchanged selection
only verifies; it does not rewrite payloads or native policy. Refresh does not
rebuild product packages or snapshots.

The exclusive maintenance owner proves an idle login-session boundary before
fixture use. Only the greeter, root/greeter service managers and the owner's
root SSH observation are allowed; other or unknown sessions refuse. A bounded
wait permits prior owned root SSH sessions to close. Foreign owners and active
workers refuse. Arbitrary guest commands, probes, reboot or keyboard input retire
refresh eligibility before acting. Read-only status, screenshot and domain or
snapshot observations preserve it.

Readiness binds the exact VM UUID, boot, run, input and diagnostic generation.
The owner persists pending state before fixture use and publishes readiness only
after byte, native activation and runtime verification. Uncertainty makes the
maintenance generation unavailable until normal owned stop/recovery. Both inputs
remain retained through cleanup. Interrupted record cleanup after completed
recovery requires independent exact off-state, configuration, snapshot and guest
audits. This route does not refresh active scenarios, change subsets, promise
same-boot rollback.

`tools/run-tests integration --vm onpc-Ubuntu26.04 check_fixture_live_refresh`
qualifies this engineering boundary on Ubuntu; select `onpc-Fedora44` for Fedora.
Its two phases use A before editing/building
B on the host, then independently verify/use B in the unchanged boot/domain,
preserve baseline/app snapshots and unrelated state, and repeat without writes.
A real staged lost reply on Ubuntu proves unavailable readiness and owned recovery.
Fedora reuses that unchanged failure/recovery proof and independently qualifies
its same-boot replacement, native activation, enforcing labels and no-write repeat.
Focused host checks cover busy/session/worker, foreign-owner, corrupt-input and
different-subset refusal before writes. The watch starts before each phase's
report owner so its retained storage cannot hold the next phase's report lock.
This supplies no customer or E2E acceptance credit.

## Retained-session native dependency update

Stable ID **289** is pending and has no executable binding for the rebuilt
session. Its old private-manager, generation and loader-refusal history is
retired. The required real dependency update, continued permitted use, normal
exit and fresh-entry outcome remains with C09c1 and final C10 mapping in the
[C04a dispositions](../../docs/SystemDesign/Kiosk-Confinement.md#c04a-installed-engineering-dispositions).
Historical receipts retain their original inputs and cleanup; they grant no
current-candidate qualification.

The [finite native input builders](Environment.md#verified-finite-native-transaction-inputs)
and independent integrity checks remain available. Preparing their package pair
does not make this pending selector runnable or provide an installed result.
The runner refuses the pending history before collecting cases or preparing
inputs. Renew the complete history through a registered current composition
before consuming it.

## Running the current installed suite

Cases have permanent numeric IDs shown by `tools/run-tests system --list`.
Use `system --id N[,N...]` or the existing area/name selectors; combining the two
selector forms refuses. IDs cover parameter variants and remain the same across
lifecycle phases. VM watch recordings use these IDs under the
[shared recording contract](../README.md#vm-watch-recordings).

`package` → `test_pam_environment_installation_variants` selects four independent
baseline histories (IDs 283–286): plain, distro profile, administrator override
and pending vendor replacement. Each keeps initial installation, reboot, saved
policy/reconfiguration, administrator-denial and restored-input retry, another
reboot with native enforcement, removal and the removal reboot together. The
controller collects each phase before reboot and restores only after the whole
history. Ubuntu's plain input disables only the optional LXC profile through
`pam-auth-update`. Fedora's plain input retains its baseline stack; its profile
input uses `authselect` to select the shipped SSSD profile while preserving
baseline features and required modules, then restores the original selection
and native rules after removal.
The administrator case records its original local `systemd-user` bytes for exact
removal restoration. Its temporary `gdm-password` authentication and account
denials remain authoritative; restoring the unchanged owned file permits a fresh
empty-token authentication/account call. The pending-vendor case preserves the
unused vendor candidate and the effective service files across successful
reconfiguration, then retries after removing only its own unchanged candidate.
Unselected valid vendor text does not veto configuration. Current finite distro
PAM readiness replaces private attestation, and removal uses the shared current
lifecycle restoration checks. These ported inputs still need installed
qualification; host composition and historical receipts do not qualify them.
These are engineering histories, not customer UI journeys.

```sh
tools/run-tests system --vm NAME --area package --test test_pam_environment_installation_variants
```

For implementation, use the [E2E building blocks](../../docs/TestAutomation/E2E-Building-Blocks.md).
The current controller executes the registered installed/reboot/removal/authorization/
enforcement/session scope when unselected. F1 can list the registered `package`, `removal`, `authorization`, `enforcement`, and `session`
cases and their explicit prerequisite closure without artifacts, root access,
or VM operations:

```sh
tools/run-tests system --vm NAME --list --area authorization
tools/run-tests system --vm NAME --list --area authorization --test 'test_real_selected_parent_authentication[child1]'
```

Bare `tools/run-tests system --vm NAME` builds its required package input automatically;
combinations including `host` reuse host's qualified input when its format matches
the verified VM baseline. Fedora selects RPM inputs; Ubuntu selects DEB inputs.
`tools/run-tests artifacts prepare --for-vm --vm NAME` prepares the same inputs
for focused `system --artifacts PATH --area AREA --test CASE` runs. Format
selection uses the pinned baseline's read-only probe; it never infers the OS
from the VM name. RPM preparation builds fresh; DEB retains verified cache reuse.

Installation/reboot package checks start from `onpc_baseline`. The controller
passes the explicit phase to the package check: before reboot, broker activation
must succeed while `ListManagedUsers` must return the exact `RebootRequired`
D-Bus error; after reboot, that method must succeed. A transport error or another
refusal never satisfies the reboot gate. Diagnostics-only activation must preserve
generated policy state before reboot; policy generation is required afterward.
Authorization,
enforcement and session checks restore the retained `onpc-v<release>` app snapshot
before each area, using the same shared preparation as
`tools/prepare-appsnapshot --vm NAME --y --overwrite false` and E2E. A missing version snapshot
is installed, rebooted and captured once. Existing snapshots are reused only when
their recorded package digest, baseline identity and installation recipe match;
otherwise shared preparation refreshes them automatically. Test-only edits do
not invalidate the installed snapshot. Guest Python dependencies are discovered
from imports and transferred in a fresh, verified payload for each attempt.
Each restored area refreshes its guarded helpers and verifies installed package
readiness before its tests, without reinstalling. Completed app snapshots remain
available after tests; final cleanup still audits and restores the outer baseline.
Partial post-install selections no longer run fresh-install assertions as
prerequisites. Full runs retain all explicit package lifecycle checks.

Kiosk-derived graphical qualifications also compare their frozen package,
baseline and installation recipe before restoring an app snapshot. A mismatch
refuses entry; the version name is insufficient. Their reports keep the saved
snapshot identity separate from the staged input archive identity. The kiosk
entry qualification retains bounded private login and MAC diagnostics on failure.
For live diagnosis before acceptance, `tools/test-vm --vm NAME reproduce-kiosk-entry`
uses the existing owned maintenance envelope and public station-entry mechanics,
stopping before request-form validation. Inspect that same running instance with
`exec`, then finish with `stop`; this route supplies no acceptance result.

`package` → `test_kiosk_account_classification_survives_reboot` keeps native
admission/confinement and real GDM entry in its fresh-install/reboot attempt.
Before the installed phase's deliberate metadata/fault fixtures, the shared
[`observe_activation`](../e2e/kiosk_entry.py) leaf focuses the exact station
through the public greeter adapter, freshly checks its keyboard recipient and
submits Enter once under the same VM lease and boot guard. Before reboot it
requires the owner-scoped restart modal with policy controls unavailable; after
the real reboot it requires the usable public request form and no restart modal.
The first entry renews the installation's existing product-free greeter in the
same boot, refusing renewal if a personal graphical session is present. The
rebooted entry follows the complete native matrix and retained-metadata checks.
Both phases census every kiosk process/thread with the full required role set,
then exit through public controls and independently observe usable sign-in.
The runner retains `gdm-installed.json` and `gdm-rebooted.json` beside the native
JUnits, binds the exact host observer/transport source hashes, and checks boot
and execution-rule continuity around entry. No app snapshot replaces either
phase. This system history supplies no general customer E2E completion.

`package` → `test_first_configuration_interruption_retry` starts from the
verified product-free baseline in its own attempt. Its `first-configure` phase
owns fresh installation, failures after visibility publication and after current
PAM activation but before configuration commit, the already-passwordless owned retry, and successful
configuration. Native account admission must remain denied while configuration
is incomplete; ordinary-account controls precede the denials. The controller
also verifies that successful retry clears the kiosk's failed user manager,
excludes it from native package-trigger enumeration and permits a kiosk-scoped
wildcard reload without starting a user manager or requiring its bus. The controller
then reboots normally and runs `first-configure-rebooted` against the same
identity, routing and enforcing execution boundary. Both phases retain exact
JUnit identities and raw diagnostics. An app snapshot or previous-version input
cannot supply this initial state; resume replays the whole unfinished history.
On Ubuntu the history now requires the baseline's real LXC `cgfs` session profile
in both shared session stacks before installation, after retry and after reboot.
Its fixed compatibility receipts prove that the optional module was active;
absence, comments, duplicate entries or changed controls/options cannot become
a compatibility pass. The earlier implementation's native mapping and confined
callback witnesses and its installed acceptance, including failed-manager
recovery, are historical under
[the accepted installation receipts](../README.md#core-installation-and-runtime-compatibility).
The port retains case 4 and the complete reboot endpoint; its changed inputs
still need installed qualification. Current fault inputs use owned wrappers
that refuse only the exact `install -o root -g root -m 0644` publication from
`/usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules` to
`/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules`, and the exact
`systemd-sysusers malcontent-timer-extension-agent.conf malcontent-timerd.conf malcontent-webd.conf`
invocation after distro PAM activation. Neither command executes at its selected
pause. Private command witnesses prove the actual fault was reached; an unrelated
package failure or absent completion marker alone cannot count. Mount identity,
native empty-token authentication/account results and retained expiry are
independent observations. Ubuntu's vendor account stack maps expiry to its
requisite denial. After Fedora PAM activation, GDM and systemd-user reach vendor
expiry while login/sshd receive the shared service-boundary denial. The installed
lifecycle's read-only expiry reader keeps shadow credentials out of the recorder.
No product test hook or second installation route is used.
Ubuntu dependency configuration can enable newly unpacked default profiles
before the product's explicit activation. For the first interruption only, an
owned wrapper delegates those default updates to the real `pam-auth-update`
with public `--disable` flags for the two product profiles. The test verifies
their absence at the pause; the product's later explicit `--enable` call and
all final admission assertions remain intact. This engineering fixture ensures
the missing-shared-gate interval is actually exercised.
As in removal recovery, DEB retries finish the verified already-unpacked
configuration through native `dpkg --configure`; APT cannot reinstall its
half-configured same-version state. Payload installation and RPM retries use
the frozen checkout's `make install`. Both retain the original activation
comparison and require the restart request before the controller's real reboot.
Identity continuity reuses the existing fresh AccountsService startup oracle:
the native daemon makes a new cache private at startup while all cache bytes,
ownership and extended attributes remain exact. The broker's native private
state-directory group normalization likewise preserves the marker inode,
root ownership, private mode and bytes; every other identity field stays exact.
The reboot endpoint checks selected session/PAM composition and both ordinary
roles' real execution and scope controls with Fedora SELinux enforcement enabled.
It supplies no removed private-policy or execution-fence proof. Deliberate reachable
escape-route checks remain with their independently allocated histories.

`enforcement` → `test_kiosk_login_admission` checks the installed
`gdm-password`, `login` and `sshd` account stacks through libpam's `pam_start`
and `pam_acct_mgmt`, with individually bounded workers and `pam_end` readbacks.
Ordinary-account controls and dedicated kiosk admission precede exact kiosk
permission denials. Public AccountsService changes exercise an installed
alternate session and invalid saved transport; each refused attempt must repair
the dedicated default and permit a fresh retry. Effective SSH configuration
must select PAM and the tested service. The test opens no session and changes
no authentication credentials or shell. It qualifies installed account/routing
admission, combined with the separate final-exec matrix; it does not establish
graphical login, session-stage transport checks or customer-journey acceptance.
Fedora's kiosk GDM workers reuse the final-exec matrix's private interpreter
fixture in the real `xdm_t` caller domain and verify that domain before libpam.
This preserves the native named transition for the admission lock after reboot;
an unconfined synthetic caller must not create that inode with a different type.
The fixture changes no policy or runtime-lock label and cleans up its own
interpreter after success or failure.

The [current engineering disposition map](../../docs/SystemDesign/Kiosk-Confinement.md#c04a-installed-engineering-dispositions)
owns cases 267–271 and 289–294. Only 267 (installed session composition),
268 (account/routing admission) and 271 (ordinary-role controls) retain runnable
bindings in this family. Cases 269/289/290/291/293/294 are pending with explicit
surviving behavior and receiving tasks; 270/292 are retired private-mechanism
witnesses. Numeric IDs and original evidence remain reserved.

The shared census now observes session/service identity only and explicitly
reports that confinement is unqualified. Public form, approval, Preferences
and feedback results remain independent. Optional notification/agent services
do not veto the form. Private namespace, generation, retained-view, ambient-mask,
global material and continuous native-library assertions are removed together
with their workers and host doubles. Registration and host checks supply no
renewed installed qualification.

`test_kiosk_shared_integration_scope` retains both ordinary account roles,
finite current distro-PAM readiness, ordinary vendor processes/services and
usable shell/Python/GJS controls. It stops only its recorded manager invocation.
It does not authenticate graphical login or certify vendor/administrator denial
variants. Those installed histories remain separate obligations.

The `removal::test_remove_reboot_reinstall` selector starts product-free and
keeps installation, configuration,
refused removal of an edited owned integration, retry, erase, reboot, health
verification, reinstall, package-delivered purge and a fresh reinstall in one
guarded attempt on either distribution.
The same case executes across five explicit lifecycle phases; a failed phase
stops later transitions. Package checks are its installation prerequisites.

`removal::test_aborted_cleanup_rollback_retry` is the focused aborted-cleanup
rollback and owned-retry history. List it with
`tools/run-tests system --area removal --test test_aborted_cleanup_rollback_retry --list`,
then execute that same selection with `--vm NAME` and without `--list`.
It starts from the accepted product-free baseline, installs and reboots in one
guarded attempt, and preserves the independently measured original PAM oracle
in `before.json`. It has six package prerequisite executions and two recovery
executions. The logical phases `rollback-installed`, `rollback-rebooted`,
`rollback` and `rollback-rearmed-rebooted` keep progress, JUnit and result
identities distinct; package assertions
receive the established `installed` and `rebooted` semantics.
After native rearming, a real reboot retires cached native PAM workers before
the same history verifies restored protection and finalizes removal.
This focused route accepts the current package only; combining it (including
unfiltered removal/system selection) with `--previous-artifacts` refuses before
VM acquisition because upgrade does not preserve its independent original PAM
oracle.
An unfiltered removal/system run gives this history its own baseline attempt,
so earlier erase/purge phases cannot supply its initial state. Failure stops
later phases and uses the shared lease cleanup and evidence collection.
`tools/run-tests --resume` preserves the original selector and replays the whole
unfinished focused history, including its installation/reboot prerequisites;
completed independent histories retain their passes. App-snapshot bootstrap
retires its old payload, including `before.json`, so this original-PAM history
does not start from an app snapshot.

`removal::test_interrupted_finalization_retry[denial-publication]` and
`[account-finalization]` are separate continuous focused
histories with the same baseline and six package prerequisites. Each uses its
variant name for the first recovery phase and `<variant>-retry-rebooted` for
the second; package phases are `<variant>-installed` and `<variant>-rebooted`.
Selection, frozen inputs, JUnit identities, failure stopping and complete replay
use the same controller metadata as rollback. Quote the full parametrized case
when selecting it. Previous-package and app-snapshot starts refuse.
The historical `denial-publication` label now interrupts the exact native
account-expiry command after the current lifecycle saves its quarantine journal.
The second history interrupts native account finalization after real payload
erasure. Owned mount identities and exact native-command witnesses must match;
unrelated command failures supply no interruption proof. The surviving-account
interval requires native account-expiry denial through both service stacks,
successful ordinary-account controls, unchanged vendor service files and the
exact UID-bound recovery journal. Fresh installations publish no private MAC
policy or service-level removal denial. Case 10 (`mac-unload`) is retired and
reserved; its surviving quarantine/finalization outcomes remain in cases 9/11.
Legacy migration and its standalone PAM barriers remain covered separately by
the package configuration/removal and embedded-finalizer host regressions.
Across reboots, home identity uses the filesystem UUID, Btrfs subvolume when
applicable, inode, owner and mode. Same-boot fault cleanup still requires the
exact device, inode, pinned descriptor, mount namespace and mount inventory.
Only native owned retry may restore original PAM after account deletion.
`removal::test_ownership_refusal_retry` selects all seven finite ownership
histories in one retention session; a full bracketed selector selects one.
The variants are `systemd-user-edit`, `gdm-password-link`, `systemd-user-link`,
`gdm-hook-link`, `confinement-record-owner`, `confinement-record-link` and
`confinement-record-uid`. Each retains its own baseline installation/reboot
prerequisites and continuous conflict/refusal/resolution/reboot/removal attempt.
The historic variant labels retain cases 12–18. Their current targets are the
distro PAM selection authority (edit/link), child-trust ownership record (link),
generated fallback rule (link), and the real lifecycle-created account-expiry
journal (owner/link/UID). The journal is created through lifecycle preparation,
then released through verified rollback after exact conflict restoration; no
legacy record is invented for a fresh installation.
Native refusal must preserve the exact conflict inode, metadata, bytes or link
text and referent, recovery records, enforcement and ordinary-user access.
Fixture cleanup restores only that recorded conflict; full owned integration
verification precedes reboot and successful native finalization. Family resume
replays each unfinished history from its baseline without splicing phases.
Fedora's account-finalization history uses normal reinstall, reboot and removal;
the separate failed post-erase/repeated packaged-purge history below retains its
additional native transaction. These engineering faults do not replace customer UI acceptance.
The finite `system_removal.py exercise-live-finalization VARIANT` diagnostic
dispatch calls the same first recovery function in owned maintenance. It supplies
no acceptance; finish maintenance cleanup before a fresh installed history.

`removal::test_rpm_posterase_recovery` is Fedora-only. Its six fresh package
prerequisites and two phases, `rpm-posterase` and
`rpm-posterase-reinstalled-rebooted`, form one continuous baseline attempt.
The packaged purge action must fail in real RPM post-erase cleanup with the
payload erased, native account-expiry denials and exact recovery records
retained. A pinned self-bind on the kiosk home and a foreign-owned sentinel
remain through normal `make install` recovery. A joined observer independently
requires restored native enforcement and a denied child launch while the
UID-bound quarantine journal remains.
Only then does the fixture resolve its exact conflict. A real reboot precedes
the repeated packaged purge, owned account/home deletion, exact original PAM
and authselect restoration, and ordinary-user checks under enforcing SELinux.
An explicit selection on another package format refuses before VM work; broad
selections omit this Fedora-only case there. Frozen inputs, failure stopping,
whole-history replay and owned cleanup use the same focused controller contract.
The finite `system_removal.py exercise-live-rpm-posterase` maintenance diagnostic
calls the same first phase and supplies no acceptance credit.

The five-phase selector's assertions cover cleared live restrictions/grants,
removed payload
and generated integrations, retained preferences/logs, unrelated account
preservation, native execution, GDM and password-login health, reinstalled
readiness, and fresh policy/request defaults after purge. Ordinary erase retains
preferences/logs; the explicit installed `oh-no-parent-control-purge --yes` action
deletes them through the native package manager and shared guarded cleanup.
Before the first installation, the guest independently measures the exact
`gdm-password` and `systemd-user` bytes, modes and local-versus-vendor selection.
Every removed/purged endpoint, before and after reboot, must match that witness;
the matching hashes and disposition are retained in each phase's JUnit.
After the activation prerequisite's public GDM exit, the removal fixture waits
for the identity-checked kiosk manager to become inactive before starting its
own manager for the native refusal check. This bounded read-only wait never
stops or adopts the preceding manager; a persistent or unknown state refuses.
Foreign-edit refusals verify the retained package version, payload digests and
policy before resolving the edit. If Debian's refused abort-remove leaves
configuration pending, the fixture restores only its unchanged owned edit and
finishes that already-unpacked configuration through native `dpkg --configure`.
Strict configured-package and unchanged-policy checks must then pass before the
successful removal retry. Payload installation and reinstallation use `make install`.
The same continuous history also holds a successful installed `gdm-password`
account handle in a bounded root worker before any kiosk credential handoff.
Ordinary PAM/native controls precede native removal's exact
`kiosk-admissions-active` refusal. The same live root holder, inactive kiosk
manager, payload, service/shared PAM stacks, authselect selection/profile,
account/home ownership, lease inode, recovery records and effective ordinary-user
access/child enforcement must survive. Loaded confinement must remain enforcing;
Fedora also checks its real `xdm_t` caller domain. Controller EOF releases the handle
through normal `pam_end`; a successful removal preflight and admission gates
precede the history's existing successful removal/finalization and reboot phases.
For focused engineering diagnosis, `system_removal.py exercise-live-refusals`
reuses the same finite hook/PAM checks and leaves the package installed. It records
native configuration status before and after recovery. Feed the current helper
and its matching `system_guest` dependency through the maintained
[maintenance stdin route](../../tests/README.md#live-diagnosis-before-another-repair-attempt),
preserving the original guest/input guards. Stop maintenance before the complete
registered history; this diagnostic supplies no acceptance credit.
Debian's reboot notice conffile intentionally survives ordinary removal.
Automatic GDM login
and API policy setup are engineering fixtures, not completed customer E2E
acceptance; the public removal/reinstall journey retains its own queue and
qualification requirements.

Ordinary removal and retained-state reinstall preserve the other account's full
preference and native-policy witness. Purge deletes every product preference
record, including personal-only language choices created during GDM entry, as
required by the [saved-data contract](../../docs/SystemDesign/Package-Removal.md#remove-purge-and-retry).
The other account's native policy must still match its independent original
witness after purge and fresh reinstall; its erased preference record must not
be replayed. Saved-data deletion and policy preservation are separate assertions.

The `session` area runs installed PAM expiry checks, then a one-shot GDM
autologin fixture across a second reboot. It observes real scope creation,
expiry locking, extension recovery, PAM admission and authenticated broker
requests. The fixture is a runtime diagnostic; API requests do not establish
GUI interaction coverage. A separate fixed local-VT fixture checks another
account's foreground session across child expiry; it does not claim a graphical
Switch User journey. PAM password probes run in individually bounded, owned
processes with credentials supplied only on stdin. Native module status is
recorded before its assertion. The observer records public ScreenSaver and
logind lock state and screen-lock settings. After successful or failed session
diagnostics, the owning controller wakes the display with a fixed non-text
Shift modifier and retains a private screen capture, checking ownership around
both operations. Capture failure preserves the original test failure.

For an explicit update check, add `--previous-artifacts '<prior-artifact-allocation>'` alongside
`--artifacts '<current-artifact-allocation>'`, using the maintained builder's
returned paths. Both inputs pass the same artifact and source
verification. The controller installs and boots the prior package, requires its
payload unchanged and its platform reboot marker cleared, then uses the frozen
checkout's `make install INSTALL_PACKAGE=<exact-package>` recipe for the selected
new payload. Make owns APT/DNF dependency resolution and same-version reinstall.
Both artifacts must use the same package format. Fedora compares exact
RPM name, epoch, version, release and architecture, and keeps SELinux enforcing.
Identical package digests are refused. The update
must request a new product reboot, and normal installed/reboot assertions run
against the new bytes. Explicit updates keep their selected post-install checks
in the same baseline-based attempt, so restoring a cached app cannot bypass the
upgrade under test. `update-activation.json` records both package digests and
the same-version reinstall observation. Neither package is installed on the host.

`package` → `test_previous_package_policy_preservation` (ID **287**) adds a finite
genuine earlier-release history to that route. Prepare its owned input with
`tools/run-tests artifacts prepare --for-vm --upgrade-inputs --vm NAME`, then pass
the returned bundle's `current` and `previous` directories as `--artifacts` and
`--previous-artifacts`. Ubuntu pins released v1.2; Fedora pins released v1.3's
existing RPM recipe. The builder verifies the annotated tag/commit, exact source
digest, package version and architecture and native strictly increasing version
order. The focused selector refuses a missing prior input or a fabricated release.
Ordinary current-package suites omit this optional history.

For a parallel selection, shared runner infrastructure prepares and binds each
VM's independent pair before invoking that same `--previous-artifacts` route:

```sh
tools/run-tests system --vm 'NAME,OTHER_NAME' --id 287 --upgrade-inputs
```

`system --upgrade-inputs` applies to any explicit system selection needing a
real package update. It cannot accompany explicit artifact paths. Each worker
requires its registry `package_format` and verifies that format against the
pinned baseline before building; there is no DEB/RPM default or case-specific
builder. Preparation failure prevents that worker's installation. Existing
explicit current/previous input paths remain supported for one target.

One baseline attempt installs and boots the old package, then runs
`previous-policy`, `installed` and `rebooted` without restoration between them.
Public broker calls save a 37-minute daily allowance, hard and soft app rules,
custom request choices and a real Polkit-approved fixed request for twelve
additional hours.
The grant's exact issuance/duration must survive; its remaining wall-clock time
must decrease across update/reboot, following [grant arithmetic](../../docs/SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities).
Before reboot, policy activation returns the exact reboot-required refusal and
the legacy admission receipt refuses removal. After reboot, public policy/time
queries, session preparation, hard-app denial, approved soft-app execution,
unrelated-user execution and saved identity/policy preservation must pass.
The exact declared kiosk-shell change from the pinned releases' `/bin/bash` to
current `/usr/sbin/nologin` is required; UID, group, home identity and every
ordinary account remain unchanged. Ubuntu also requires schema 3 → 4 migration;
Fedora retains schema 4. Saved language/default language remains intact.
Each phase is collected before crossing its next lifecycle boundary. Resume
replays the entire unfinished history; earlier phase passes cannot be spliced
into another restored guest. This engineering case supplies no customer GUI
update-journey acceptance.

`package` → `test_trusted_native_upgrade_fixtures` (ID **288**) separately
qualifies the trusted inputs for an earlier-release history. It uses the same
verified current/previous artifact pair and an isolated product-free baseline
attempt. The runner installs and boots only the pinned earlier package, then
runs `trusted-fixtures`; the candidate is never installed in this qualification.
Both fixed children first execute the independently named trusted hard/soft
fixtures without restriction. Public old-broker policy operations then require
child-only hard denial, strict soft denial and real authenticated soft approval,
with unrelated-child execution at every stage. Source and compiled rules are
retained. The fixture receipt, native package/tool identities, exact file-trust
database rows and unchanged original untrusted bytes/trust state must match
the prepared baseline. Placement and trust admission belong exclusively to
[`tools/prepare-vm`](Environment.md#reusable-preparation-ownership).
The selector is explicit and isolated; ordinary current-package or upgrade
selections do not add it. Its passing result qualifies inputs, without granting
candidate-upgrade or customer GUI acceptance.

`test_native_whitespace_policy_is_uid_scoped` runs the same transitions and
other-child assertions using a fixed executable filename containing a space.
Its quoted desktop entry must resolve to that exact target. Each deny stage
requires the executable's current SHA-256 identity in both source and compiled
rules; intervening allow stages require that denial to be absent. The launch
probe accepts only maintained fixture variants and uses
direct `execv` after credential verification. Private rule filenames and public
property names include the variant to retain both cases in a combined run.
Inspect its retained-app-snapshot prerequisite with
`tools/run-tests system --vm NAME --list --area enforcement --test test_native_whitespace_policy_is_uid_scoped`.
Host regressions cover the scenario and failure witnesses; the full installed
run linked above also passed this case.

`test_native_future_pattern_is_uid_scoped` extends these transitions with a
saved same-directory `Versioned-*.AppImage` pattern. A second matching version
is created only after the first hard policy's source/compiled rules are captured.
Its selected-child denial and other-child allowance must occur with those rules
unchanged, without an exact denial for the future path. An existing unrelated
executable remains allowed for both children. Each blocked stage requires the
unrelated file's allowance before the directory denial in both rule files;
restored stages reject retained pattern rules. The launch probe selects only
the fixed `pattern`, `pattern-future`, and `pattern-unrelated` targets, preserving
the same guest/credential checks and owned one-shot process. Fixture setup
refuses existing paths; files remain in the guest for outer baseline cleanup.
Inspect the case and its retained-app-snapshot prerequisite with
`tools/run-tests system --vm NAME --list --area enforcement --test test_native_future_pattern_is_uid_scoped`.
Host regressions establish scenario behavior, catalog parsing and rule witnesses;
the full installed run linked above also passed its kernel enforcement checks.

`test_native_missing_launcher_retains_policy` removes its dedicated native
launcher after witnessing the initial hard policy in source and compiled rules.
The guest guard and captured file identity must match before unlinking the
fixed launcher; replacements, changed files, links and unexpected directories
are refused. The executable remains present. The broker catalog must omit the
launcher while preferences retain its policy, including after a public
`SetPreferences` save reconciles the missing catalog entry. Both rule files must
still deny the selected child, and command launches must witness child denial
and other-child allowance. The shared transitions continue through soft policy,
screen-time enablement and policy restoration with the launcher absent. The
outer baseline cleanup owns remaining fixture files. Inspect its prerequisite
closure with
`tools/run-tests system --vm NAME --list --area enforcement --test test_native_missing_launcher_retains_policy`.
Host regressions use real catalog parsing, broker preference reconciliation and
rule rendering with substituted OS boundaries. Installed execution passed in
the full run linked above.

`test_native_catalog_is_selected_child_scoped` uses the same prerequisite
closure and reads the installed broker catalog as the parent while selecting
child, other child, then child again. Distinct system/child/administrator
targets prove launcher precedence; role-only launchers and a hidden child
override prove scope membership. A shared system launcher with a relative
command resolves to the selected child's `.local/bin` or the other child's
`bin`, with a lower-priority child copy and administrator substitutions present.
An administrator-only relative command must remain absent from both catalogs.
An absolute desktop `Path` containing a space wins over child and system copies.
Separate commands prove `/usr/local/bin` precedence and `/usr/bin` fallback,
with administrator copies present. The fallback's higher-priority candidate
must be absent before provisioning. No fixture is written through `/bin`, which
may alias `/usr/bin` on the guest.
Its provisioner refuses existing fixture
files and symlinked directories, preserves existing account/system directory modes
and ownership, and leaves fixture cleanup to the outer guest baseline.
Host tests exercise real filesystem discovery and deliberate assertion faults;
the full installed run linked above also passed this case.

For fixed harness qualification only, add `QUALIFICATION_FAILURE=1` to
`make check-system` with `AREA=authorization` and
`TEST='test_method_role_matrix[ListManagedUsers-parent1]'`. `LIST=1` also accepts
this option. Every other scope is refused before VM mutation. The qualification
plugin is frozen in selected-input provenance and loaded only for the selected
authorization phase. Its [public pytest call wrapper](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html#hook-wrappers-executing-around-other-hooks)
injects `harness:qualification-failure` only after the real assertion succeeds;
existing assertion, setup and skip outcomes remain intact.

Qualification retains a failing exit status and labels the result
`harness-qualification`. The controller attributes the fixed fault to
infrastructure only when all five exact executions are collected, prerequisite
cases pass, and the selected case has only the fixed failure. Missing or unsafe
evidence and cleanup failures remain separate outcomes. Even if the hook fails
to inject its fault, qualification cannot become a passing product result.

One expensive attempt should collect the safe observations needed to distinguish
the current hypothesis on success and failure. Check parser/collector handling
locally first. After two attempts on the same blocker, improve the evidence or
justify a new discriminating experiment before another boot; carry that history
across handoffs. Never leave a VM running or restore an intermediate state to
save conversation context. A completed attempt's failure remains preserved.

When changing a cleanup implementation, explicitly run the applicable
[isolated cleanup-safety regressions](../README.md#cleanup-safety-prerequisites),
including persistent-caller cleanup if that helper changes. These are development
regressions, not automatic startup work. After building and
verifying the input, invoke the host controller from a root shell:

```sh
make check-system ARTIFACT_DIR=/tmp/onpc-test-artifacts/run-input
make check-system ARTIFACT_DIR=/tmp/onpc-test-artifacts/run-input \
    AREA=authorization TEST='test_method_role_matrix[ListManagedUsers-child1]'
```

From an administrator's active local graphical session, use the installed
argument-validating dispatcher. Its development Polkit rule avoids an
authentication dialog for local `sudo`-group members:

```sh
pkexec /usr/local/libexec/onpc-test-runner system \
    --artifacts <verified-directory>
```

Do not authorize or invoke `pkexec make` for this purpose; `make` is a general
execution engine and bypasses the dispatcher's argument boundary.
The command resets guest disk changes since the retained baseline. Never run
it on an unleased VM containing work that must be kept. `VM_IMAGE` is refused.

Preparation checks all directly invoked host tools, including `dpkg-deb` and
`dpkg-query`, and names a missing tool without logging command arguments.
Missing, inaccessible, or otherwise unavailable artifact sources report distinct
`assets:source-*` categories before run storage or VM access. These input errors
do not establish a missing executable; verify the supplied artifact directory
in the same privileged host context as the runner.

Both Makefile and direct controller paths suppress Python bytecode writes.
Default host pytest collection excludes `tests/system/`; guest pytest uses
its own configuration and disables plugin autoload. Do not invoke guest tests
as host pytest or bypass the controller merely to select a test.

After guarded offline bootstrap, the guest verifies its root-private run marker,
machine identity distinct from the host, DMI domain UUID, supported Ubuntu
release and package/transfer digests. Only then does
APT install the exact package. The runner waits for systemd boot completion
before service assertions; SSH alone is insufficient. A degraded boot does not
skip the service assertions. Readiness waits never retry installation or a
failed test assertion.

## Reusable implementation contracts

- `system_runner.Lease`: the existing controller lock spans validation, outer
  reset, bootstrap, the whole attempt and cleanup. Cleanup is bound to the
  recorded UUID, live domain identity, run marker, disk identities and snapshot
  metadata. It must not affect a replacement or unrelated VM.
- `stage_assets`: freezes the package/fixture manifest, verifies canonical
  fixture digests, and hashes exact transferred bytes, including variable
  Flatpak containers. `stage_selected_inputs` separately freezes the resolved
  executable test/helper closure and binds its files to the selected case IDs.
- `vm_transport.Transport`: pinned-key SSH, safely quoted argument transport,
  constrained archive extraction, bounded readiness and real reboot. Every
  readiness probe revalidates identity; a guest guard failure is not retried as
  a transient SSH error. The first phase's evidence is retrieved before reboot.
  Its separate `wait_boot_change` observation reuses that loop for customer
  reboot input: valid old-boot replies and SSH status 255 wait under one deadline,
  with ownership/configuration checks before and after each probe. It never
  requests a reboot. The existing `reboot()` and ordinary readiness behavior
  remain unchanged. This addition is locally tested, not live-qualified; see
  the [E2E contract and regressions](../e2e/README.md#customer-reboot-observation-boundary).
- `owned_commands.Commands`: pins directly spawned host/guest processes and
  bounds interruption cleanup. No guessed process discovery or ownership.
- Private namespace callback case 270 is retired. The current
  [disposition map](../../docs/SystemDesign/Kiosk-Confinement.md#c04a-installed-engineering-dispositions)
  keeps ordinary PAM/callback outcomes with their actual current consumers.
- `test_kiosk_account_classification_survives_reboot`: the package area exercises
  fresh caching, retained-visible no-op retries, retained-hidden disk/live-state
  disagreement and unsafe-state refusal/recovery. Its complete cache-byte oracle
  permits only a fresh cache's initial `0600` or `0644` mode to become exactly
  `0600` at daemon restart; every other fresh fingerprint field and the entire
  immediate retry fingerprint must remain unchanged. This models
  [AccountsService 23.13.9 startup](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/raw/23.13.9/src/main.c),
  where `on_bus_acquired` enforces user-cache permissions before constructing
  the daemon. All retained-record fingerprints remain exact. The oracle
  preserves unknown user keys, comments, extension groups and custom icon state,
  including file ownership, mode and xattrs, through the full production kiosk
  provisioning function. Both declared ordinary administrator and standard-user
  roles' complete cache and icon fingerprints must also survive every restart
  and the final reboot without any fixture write to those accounts. Each witness
  requires the baseline UID/role and a declared icon route; bounded diagnostics
  identify only the fixed role and changed metadata fields. Daemon restarts are
  independently observed. Bounded child-only injection tests a precommit I/O failure and
  immediate exits before and after the exact atomic replacement while the real
  daemon is stopped and activation is masked. It checks the owned pending slot
  and committed xattr marker before normal restart exercises real hook recovery.
  A private witness verifies the final retained-hidden migration
  after the controller's real reboot. Runtime fixture masks are removed only
  while their recorded identity still matches. The outer baseline owns all
  fixture recovery. This engineering check changes no ordinary-user cache and
  resets the daemon's synthetic rapid-restart budget before each owned masked
  fixture group only after independently observing an active daemon. It refuses
  failed, inactive or transitioning services without clearing their failure or
  retrying their start. This keeps the bounded engineering restart sequence
  within systemd's start limit. The check
  also verifies exact installed-package readiness in both phases, the product's
  pending/cleared reboot request, and the complete native confinement matrix
  within that same fresh-install/reboot attempt. Before reboot, routing admission
  mutations run before the retained-metadata witness; nonmutating installed
  account-gate checks follow the final AccountsService restart and the new boot.
  Ordinary controls precede dedicated kiosk admission and exact terminal/SSH
  denials. Native positive execution precedes the execution, stale-generation,
  missing-policy and unenforced-policy denials and recovery. Append-only fault
  probes restore original bytes and nanosecond timestamps through the opened
  inode, preserving strict package verification after reboot. The final preboot
  broker check still requires the exact `RebootRequired` error and unchanged
  generated execution-policy state. The selected case stages all shared helpers;
  it never restores an app snapshot between its two phases. This supplies native
  activation evidence, not real GDM entry, restart-modal presentation or a real
  waiting-session census; those require a separate fresh lifecycle history.
  The check provides no customer UI acceptance. Select it with
  `tools/run-tests system --vm NAME --artifacts '<verified-format-allocation>' --area package --test test_kiosk_account_classification_survives_reboot`.
  Before that system run, owned maintenance can feed the same helper through
  `tools/test-vm --vm NAME exec --timeout 180 --input-file 'tests/integration/system_kiosk_accounts.py' -- env 'PYTHONPATH=/var/tmp/onpc-system-input' 'ONPC_EXPECTED_RUN=RUN' /usr/bin/python3 -B - exercise-live`.
  Replace `RUN` with the current owned guest marker's nonsecret run identity;
  keep the guest/domain/input guards. After a real maintenance reboot, the same
  command with `verify-reboot` checks its witness. This stdin diagnostic subset
  omits only the three atomic subprocess injections whose source must be staged
  in the frozen system-test payload. It does not complete the system selector.
- `system_guest`: validates the guest/attempt boundary and drives real APT and
  installed pytest phases. Package assertions account for actual packaged
  permissions, including the restricted Parent launcher and fapolicyd's
  tmpfiles-managed configuration ownership.
- `system_caller.py`: drops real/effective/saved credentials, opens a fresh
  system-bus connection and verifies the bus-reported UID. Structured replies
  and private-state assertions stay in private diagnostics, without exposing
  account contents in public assertion errors. The guarded batch protocol accepts
  UID 0 only with literal `allow_root: true`; `call`/`batch` expose that explicit
  keyword for root method coverage. The same kernel and bus identity checks apply.
  Ordinary callers, persistent callers and authentication agents still reject UID 0.
- `system_caller.PersistentCaller(uid)`: context-managed real caller connection
  with `name`, `call(method, signature, args)`, and separate `send(operation)` /
  `receive(timeout)` operations. EOF closes it; bounded context cleanup signals
  only its directly spawned pidfd. It is not an authentication agent and does
  not by itself prove password handling or approval.
- `system_caller.TextAgent(caller)`: guarded real `pkttyagent --process` attached
  to the persistent caller's pinned PID and kernel start time, with registration
  readiness on its inherited notification pipe. Polkit resolves the broker's
  real bus-name challenge to that process. Startup failure reports only a fixed
  category and child exit status; terminal bytes are never exported.
  The wrapper runs the guest guard and establishes its controlling terminal,
  then drops real/effective/saved credentials to the persistent caller's verified
  UID before executing `pkttyagent`. Polkit binds the authentication session to
  the subject user; registering a root agent for an unprivileged subject can
  prompt successfully but its helper response has the wrong UID.
  `prompt(selected_uid, other_uid)` checks the
  selected identity and waits for terminal echo to be disabled;
  `authenticate(password, succeeds=...)` drives the real PAM challenge. Terminal
  contents remain in memory; unexpected acceptance, denial or cancellation
  fails immediately with a fixed category instead of waiting for a timeout.
  Denied challenges also report an allowlisted helper failure stage (PAM or
  authority response, or `unclassified`); arbitrary helper stderr and terminal
  contents are never exported, and the category alone does not prove the cause.
  Known authority responses are further reduced to fixed session-lookup,
  authenticated-identity, response-caller, or D-Bus transport categories. Unknown
  responses retain `authority-response`; a diagnostic never substitutes for the
  actual grant or denial assertions.
  `FixturePassword` generates distinct temporary
  credentials and sets them through guarded guest stdin without diagnostic
  export. Agent cleanup signals only its directly spawned pidfd; run
  `test_system_agent_cleanup_safety.py` before integrated use. This text-agent
  coverage does not replace graphical authentication journeys.
- `tests/system/test_authorization.py`: reusable `batch`, `call`,
  `account_property` and `account_state` assertions. Account state compares
  private preferences and public limit/grant/filter state without printing
  private values. Keep phase expectations aligned with actual collection;
  fixed historical pass counts are not coverage definitions.

Current bootstrap requires the [prepared schema-2 baseline](Environment.md).
Its two sequential libguestfs appliances replace the previous three: a guarded
offline edit adds the attempt's public key to OpenSSH's `authorized_keys` file
and writes the private run marker; after sync/close, an independent read-only
open verifies the marker, key contents, ownership/modes and server public key.
Symlinked or unsafe key destinations are refused. OpenSSH/pytest installation
and archive normalization now belong to guest preparation, so bootstrap has no
`virt-customize` or package-manager transaction. Per-attempt share removal and
input/identity validation remain. Host key pinning and all disk-proof gates
remain required. Host-safe regressions cover failures and both system/E2E
composition; real transport qualification awaits a newly prepared baseline.

`test_remote_accounts_are_excluded` provisions real RFC2307 LDAP users through
`system_remote_accounts.py` only after the guest guard and restored-app readiness
checks. It refuses fixture configuration and UID/name collisions and verifies
prepared OpenLDAP/SSSD packages. Ubuntu configures the dormant OpenLDAP package
through `dpkg-reconfigure --frontend=noninteractive` and adds SSSD to the existing
passwd/group NSS sources. Fedora creates isolated slapd configuration and
database directories under `/var/lib/ldap`, preserves the RPM defaults and
SELinux enforcement, and enables SSSD through a clone of the active authselect
profile with its existing PAM stack and features. Both routes use LDAP's public
`cn=config` interface with root peer credentials and enable NSS enumeration.
The LDAP server runs on guest loopback; credentials and remote login are not
needed for this identity/authorization test. No local passwd records or private
AccountsService files are created for these identities. Public `CacheUser` and
property reads establish nonlocal, interactive, unlocked standard/admin roles
before exclusion assertions. The Fedora fixture restores the exact original
authselect selection after the test; the retained baseline restores dormant
services and removes fixture configuration and accounts after the attempt.
No host tool installation is required. This test integration activates on the
next invocation (`none`);
the broker's local-administrator enforcement is `process-restart`, with no
saved-data migration. Package versions and predicate/denial observations are
retained in JUnit; APT catalog/command diagnostics follow the existing collector.

## Evidence and failure recovery

Every attempt retains a unique `/tmp/onpc-system-*/` directory. Public
`evidence/` contains aggregate `result.json`, xUnit `results.xml`, TAP
`results.tap`, redacted guest logs, and the applicable guest phase XML
(`installed.xml`, `rebooted.xml`, `authorization.xml`). The authentication journal
collects Polkit service and PAM helper messages through the same redaction pass;
a failed authentication-journal command fails collection explicitly.
Authentication tests also retain `onpc.authentication` JUnit suite properties
using pytest's public xunit2-compatible fixture. Each JSON value names the
registered `case_id`, its one-based `attempt`, `expected` and actual `outcome`,
and an allowlisted `helper_category` (null for accepted/cancelled outcomes).
Recording precedes the outcome assertion, so an unexpected denial retains its
category and remains a test failure. Attempt numbers restart for each case;
credentials, account identities and terminal contents are excluded. JUnit
redaction operates on decoded XML values before serialization, preserving valid
XML even when a traceback contains a password assignment.
Raw diagnostics and
temporary SSH credentials remain root-private. Use only validated redacted
exports; read source logs and journals without modifying them.
For local privileged inspection of any run artifact, use the
[`onpc-test-artifacts` helper](../README.md#prompt-free-test-artifact-access)
instead of general `pkexec` readers. Its Codex and Polkit grants apply across
all run names and file formats. Private local copies are not redacted evidence.

Results record package SHA-256, stable fixture digest,
`selected_inputs_sha256`, and `baseline_provenance_sha256`. The selected-input
digest is distinct from package/fixture identity and changes with either the
resolved execution closure or any staged test/helper byte. The baseline digest
hashes finalized provenance, not the writable active QCOW2. Cleanup independently
checks disk identities, snapshot metadata, product-free offline
inspection and host product/PAM fingerprints, including after failure.

The aggregate result also records monotonic accumulated seconds for preparation,
bootstrap, install, reboot, test, collection, and cleanup. Its `outcomes` object
reports product, infrastructure, collection, and cleanup independently. Each
domain retains its first fixed failure category; later collection or cleanup
failures remain visible without replacing the aggregate run's original category.
An outcome is `not-run` when the attempt ended before that boundary could be
established, rather than being inferred as a pass.

An incomplete `system-run.json` prevents a new attempt. Preserve it and its
evidence for [identity-verified recovery](Environment.md#interrupted-or-invalid-state).
Never delete controller state or rebuild the baseline to conceal an error.
Normal cleanup retains a failed outcome. Missing/skipped/failed phases cannot
be called a complete pass; a later diagnostic success does not erase an earlier
failure. The pending shared evidence/aggregate work adds executable
scenario/variant/step reconciliation; current file-level requirement validation
alone cannot establish that stronger claim.

Existing tests for controller guards, transport and guest assertions remain
ordinary regressions, even though the original runner implementation task is
complete. Repeated live smoke qualification belongs to harness changes or
diagnosis, not every daily run. No documentation cleanup authorizes deletion
of historical evidence or logs.

## Graphical adapter under development

The runner has controller plumbing in `graphical_lease.py`: public generalhw
lifecycle command variables, a private Unix callback service, and revocable
graphics descriptors from a `Lease(..., graphics_type='vnc')`. The final owned
power-off callback force-restores the accepted off baseline after the worker's
last product assertion, without waiting for ACPI shutdown. The outer lease
still audits the baseline and restores the original domain configuration.
All callback processing stays in the controller thread and revalidates lease
ownership.

Graphics FD RPCs use a short-lived, separate libvirt connection. Its URI, UUID,
domain instance and exact XML must match the guarded lease before attachment,
and ownership is checked again afterward. A graphics connection failure cannot
close the lifecycle connection needed for normal baseline cleanup.

On a development host launched from the classic VS Code snap, `pkexec` retains
the `snap.code.code` AppArmor label. `setup.sh` installs the versioned
`config/apparmor/onpc-graphical-tests` rule in the managed section of
`/etc/apparmor.d/local/usr.sbin.libvirtd`, preserving other site rules. The
installer compiles the proposed whole profile before writing and reloads only
libvirtd's profile. The rule permits anonymous Unix stream send/receive with
that exact peer label; it grants no named-socket, ptrace or additional QEMU
permission. Libvirt authentication and the exclusive VM lease still apply.
This development-only integration activates immediately on profile reload
(`none` for product packaging); it changes no application data or product package.

The fixed non-booting diagnostic is
`pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_transport`.
It requires the existing domain to be off and sends only an impossible graphics
index. A normal libvirt refusal with the connection still alive proves outgoing
FD RPC transport; a disconnected RPC is a failure. A separate owned fixture
runs under libvirtd's existing AppArmor profile with `aa-exec`, sends one socket
back, and requires usable bytes and no truncated ancillary data. Neither test
starts a guest or attaches a usable display. These probes distinguish basic
directional FD transfer from the live graphics RPC; their pass does not prove
`openGraphicsFD` or graphical compatibility. Raw fixture diagnostics and the
result are retained under root-private `/tmp/onpc-graphics-transport-*`. Use
this cheap probe before another boot when diagnosing descriptor receipt. The
dispatcher runs its safety regressions automatically.

`graphical_worker.Worker(directory, callback_path, run, command)` now launches
trusted backend commands inside private network/PID/mount namespaces. The
bridge listens on `127.0.0.1:5900` only there, acquiring the lease-issued display
FD lazily when the backend connects. Supply `GENERAL_HW_VNC_IP=127.0.0.1` and
`GENERAL_HW_VNC_PORT=5900` in the backend variables alongside
`graphical_lease.lifecycle_variables()`. The worker does not create those vars
or a distribution; its command is an internal controller API, not a privileged
arbitrary-command CLI.

Service callbacks from the lease owner's thread through `worker.run(server,
timeout=...)`, or `worker.poll()` plus `server.serve_once()`. Close the worker
in `finally` before closing the callback server and finishing the lease. Its
pidfd/start gate, controller EOF, and `unshare --kill-child=KILL` bound backend
descendant lifetime without process discovery. Kernel namespace cleanup also
covers orphaned backend children. This contains trusted tooling; it is not a
security sandbox for hostile root code. Working files and raw backend output
remain root-private and are not safe evidence exports.

The fixed live feasibility invocation is now
`pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_smoke`.
It accepts no arguments and uses the same isolated safety prerequisites and
exclusive baseline lease. Before acquiring the lease it uses the documented
`_EXIT_AFTER_SCHEDULE=1` mode to load the distribution without starting a backend.
The pinned CLI overrides its early exit status with 1; the preflight requires
both exact schedule/completion diagnostics, and rejects an ordinary compile
failure. The actual graphical run uses `--exit-status-from-test-results` and
also requires an `ok` module result with no failed/soft-failed details.
`graphical_smoke/main.pm` loads one credential-free
generalhw test: await guarded greeter observation, capture GDM, select the first
large user tile, and dismiss the resulting credential prompt with Escape,
requiring both screen changes. It explicitly selects the backend's documented
32-bit VNC depth. The default 16-bit path can decode QEMU's initial full frame
but the pinned client's ZRLE decoder rejects a subsequent changed rectangle.
The large fixed-baseline tile proves input transport without depending on small,
theme-sensitive status icons; the graphical runner owns credential-recipient matching helpers. The
controller independently checks the active greeter and absence of logged-in
user sessions through fixed read-only SSH observations at each stage. Bootstrap
uses the existing offline SSH provisioning with `observation_only=True`; no
product package or guest pytest is installed by this smoke.

Raw screenshots, backend logs, command diagnostics, SSH keys and working vars
stay in its root-private `/tmp/onpc-graphical-smoke-*` directory. Only fixed
stage labels, dimensions, digests and classified outcomes appear in the summary.
Retaining private images does not approve them for export or prove their
semantic content; reviewed/redacted screen evidence remains an acceptance
obligation. No credentials are entered, serial capture is disabled, and no
customer E2E claim is made. Runner artifacts retain live qualification
status. These are development-only test changes, activated on next invocation
(`none`); no host tools, product services or saved-data schema change.
