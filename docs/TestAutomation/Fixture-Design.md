# Host-owned fixture lifecycle: target design

Status: **partially implemented**: producer lifetime, immutable host construction,
execution-owned reuse, the shared SSH provisioner, Ubuntu/Fedora clean snapshot
boundaries, provisioning qualification and product-free system, installed-system
and installed E2E preparation are delivered on both targets.
The other four runner envelopes and live refresh remain proposed.
The [execution plan](Fixture-Execution-Plan.md) delivers this design. Current
VM, storage and preparation rules remain effective until their owning tasks
deliver and document a replacement.

## Scope and simplicity

Build fixtures on the host, transfer only the selected test's runtime files,
verify them before input, and keep fixture-only edits independent of snapshots
and product packages. Reuse the existing artifact, retention, transport and VM
recovery owners.

The first implementation has one producer and execution-owned immutable inputs.
It does not add a shared version catalogue, cross-journal pins, a second retention
policy, a native-policy acknowledgement protocol or a fixture process supervisor.
Interrupted guest mutation fails the attempt and uses existing owned VM recovery.
Live refresh is limited to an idle, owned maintenance guest. Arbitrary refresh
while fixtures or test workers are running is outside this plan.

This replaces the earlier F51/F52 proposal. Their completed reviews remain
historical design work, not acceptance of this simpler implementation. F29's
delivered producer API and safety checks remain intact.

### Frozen schema vocabulary

F51 reviewed the former catalogue/pin schemas, six-slot transitions, native
protocol and clean-schema gates. That proposal is superseded, with its original
review proof retained in the queue's accepted-evidence links. It supplies no
implementation requirement or acceptance for the current design.

### F52 independent design review

F52 independently reviewed that former proposal and resolved two planned native
transition gaps. Its completed record remains historical; the current
implementation still requires its own checks and final F13 review.

## Host authority and minimum guest footprint

Sources, compilers, build workspaces, manifests, expected results and unused
collections stay on the host. A guest receives only the selected runtime closure:
executables, modules, launchers and data actually needed there. Resolve guest
owners from accepted accounts; never copy host UIDs.

### Frozen placement inventory

The exact finite declarations remain
[baseline_assets.py](../../tests/fixtures/baseline_assets.py) and
[native_assets.py](../../tests/fixtures/native_assets.py). The table below keeps
their placement boundaries; implementation must reconcile their complete maps,
including negative controls, rather than infer membership from these summaries.
Roles are Riley (`child`), Jordan (`other`), Jamie (`parent`) and root (`system`).

| Family | Guest closure and ownership |
| --- | --- |
| A/H/S/N native GUI identities | Only the selected executables under `/opt/onpc-test-fixtures/Applications`, their adjacent `onpc-test-gui.py` and `gtk_automation.py`, and launchers actually used. Nested S needs its `Versioned/` runtime pair. Preserve the legacy root-level S as a separate compatibility control when selected. Executables 0755 and modules 0644, Jordan-owned; desktop files 0644 and owned by their declared child. Intentionally untrusted; Fedora retains exact child/content admissions. |
| Mechanical and pattern controls | `/opt/onpc-baseline-assets/onpc-test-application`, declared command/whitespace/pattern/retention targets and required launchers. Pattern comparisons include `Unrelated.AppImage`. Root-owned, 0755/0644, untrusted; no GUI runtime. |
| Trusted-native hard/soft | Selected `/opt/onpc-test-fixtures-trusted-{hard,soft}/native-fixture`, with a launcher only when discovery needs it. Distinct hard/soft bytes, root-owned 0755/0644; exact executable trust only. |
| Activity | `/opt/onpc-test-fixtures-activity/native-fixture` and its two adjacent GUI modules. Root-owned 0755/0644; exactly these three files trusted. |
| Catalogue precedence and PATH controls | The complete selected comparison from `CATALOG_ENTRIES`/`catalogue_files`, including masked entries, system and user ownership, relative/PATH targets and required absence of `/usr/local/bin/onpc-test-catalog-fallback`. Preserve all independently asserted negative controls. |
| Persistent environment | Folder-renamer overrides, Ubuntu APT masks, fixed accounts/pictures/password and keyring preservation, language/desktop settings, SSH and runtime dependencies stay in baseline preparation. Credentials never enter bundles. |
| Native backend | Backend configuration remains environment-owned. Exact fixture trust/admission records travel with runtime provisioning. Preserve vendor trust, product rules and the intentionally untrusted controls; no broad directory trust. |
| Host-only collections | Builders, compilers, standalone copied interpreter/GTK trees, Snap/Flatpak/game packaging work and unused outputs stay host-only. Pending guest capabilities gain no implementation credit. |
| Product and scenario inputs | Product packages retain independent provenance and installation checkpoints. Attachments/documents, future S, rename/save-error/launcher changes, LDAP/SSSD/keyring challenges and policy/grants/usage remain scenario-owned. Reusable provisioning must not preseed their result. |

The original map has 34 native, 33 catalogue and six desktop-setting files, plus
four Ubuntu APT masks or two Fedora admission files: 77 Ubuntu / 75 Fedora
outputs, excluding receipts/backend records. These are original inventory counts,
not a requirement to transfer them all.

One `native-runtime` build per target supplies the finite subsets:
`native`, `riley-grid`, `activity`, mechanical, trusted-native and catalogue.
Use the declarations' exact closures and their union for combined consumers.
Do not create a build version per subset. Future S and unused full-builder output
remain separate host/scenario inputs.

Baseline staging currently retains preparation sources and account pictures.
The snapshot tasks audit `prepare_vm.SCRIPT_FILES`, `baseline_guest.prepare`,
archived input trees and fixture trust records as well as runtime destinations.
Retire only proven owned movable files. Preserve environment/recovery records
and avatar identity; renaming a leaked source tree does not make capture clean.

### Artifact and named-input consumers

Use [artifact_inputs.py](../../tools/artifact_inputs.py),
[package_inputs.py](../../tools/package_inputs.py) and
[test_storage.named_input](../../tools/test_storage.py) as the source of current
identity/declaration behavior. F02/F03 delivered a separate frozen
`NATIVE_RUNTIME_SOURCES` closure and execution-owned native-runtime input.
Legacy complete artifact and package inputs retain their own provenance;
do not infer their identity or lifetime from the movable-runtime selection.

Keep the literal Boolean declarations used by
`test_commands.qualification_input_options` consistent with actual dispatch.
Host composition checks enumerate their alternatives, including empty and
dormant branches. A current source digest never repairs or silently replaces an
older nonempty input after a failure.

## Identity and build publication

F02 delivered the [frozen host bundle contract](../../tests/support/README.md#frozen-native-fixture-bundles)
and validated fixture build/verify routes. It constructs the complete finite
runtime union once per target; selection, reuse and guest handoff remain with
F03/F15 and the target/envelope qualification tasks below.

F02 builds from a frozen source closure with the existing fixture builders and
host-side target build environments. Record source and builder/toolchain inputs,
target OS/release/architecture and runtime dependency contract, separately from
the output content digest. Verify native ABI compatibility for Ubuntu 26.04 and
Fedora 44; do not relabel a host binary or compile in a guest.

Use one versioned manifest, one payload and a completion marker. The manifest
contains the complete member inventory, lengths/checksums, modes, symbolic
ownership, finite destination IDs, subsets/absence controls and exact native
actions. Derive destinations from the maintained declaration, never from
caller-supplied paths or archive scripts. Reject unsupported schema, malformed
or duplicate fields, unsafe members, links/devices, duplicate entries, undeclared
payload and inconsistent individual/total lengths before mutation.

The build identity hashes the recorded inputs; the content identity hashes the
exact manifest/member bytes. Freeze and recheck sources so concurrent edits
cannot publish a mixed build. Verify the completed tree independently before
atomic publication; a path or marker alone is not readiness. Keep package and
fixture invalidation separate, including genuinely shared product sources.

### Execution ownership and retention

F03 delivered execution-owned preparation. Each execution owns its
registered immutable fixture input through its existing retention journal.
Capture/select it before lifecycle-lease acquisition or guest restoration; this
does not move host work ahead of an enclosing
[central VM checkout](../Mandates/VM-Mandate.MD#central-vm-checkout), which precedes
checkout-local activity and controller locks. Hold the input until descendants
and owned VM cleanup finish. Reuse only a verified matching input whose existing
journal already supplies ownership. Never transfer deletion ownership or let two journals
claim one allocation. Independent executions may make independent bounded copies;
cross-execution deduplication is not a prerequisite.

Use F29's producer lease for temporary build work and copy verified results into
the execution's registered retained allocation before releasing it. Keep the
existing retention token and host/privileged split. A privileged consumer uses
the existing authenticated artifact handoff, validates the actual caller and
opens verified input read-only; it never writes a caller-owned input.

Retained inputs follow existing run limits, allocation identities and cleanup.
There is no separate six-build/per-key quota, catalogue, prune command or durable
pin state machine. If the existing handoff cannot support fixture-only input,
extend that shared handoff narrowly with its ownership/interruption tests.
Incomplete nonempty inputs refuse and use recorded recovery; no cache sweep or
silent replacement. Source edits during an attempt cannot change its selection.

## Owned SSH provisioning and readiness

F15 delivered one shared [provisioner](../../tests/support/README.md#attempt-owned-fixture-provisioning)
for runner and maintenance integration. Both targets' provisioning qualification,
product-free system/bootstrap and installed-system branches are delivered;
other dispatch remains unavailable until its target/envelope task passes.
It runs only under the existing exclusive VM lease and guarded, watched SSH.
First provision happens after restoration/transport readiness and before any
fixture launch or scenario input.

Preflight the complete selected closure, accepted account identities, existing
destinations and native metadata. Refuse unknown/modified files, unsafe paths,
wrong owners and incompatible input before changing anything. Stage verified
bytes privately, register staging with the attempt, then install finite members
with their declared owners/modes. Reuse existing native trust/admission APIs and
platform label operations. Preserve product/native vendor policy and unrelated
state. Independently read back all selected bytes/metadata and exercise a harmless
runtime witness before returning readiness.

The readiness record belongs to the current VM attempt and binds the selected
manifest/subset, actual VM UUID, boot and attempt. A snapshot's saved record or
a receipt from another attempt cannot authorize use. An identical repeated request
within that attempt verifies state without rewriting matching payloads.

A transfer/placement/native activation failure or uncertain reply makes the
attempt unusable. Release no scenario input, preserve diagnostics and let the
existing VM owner restore its recorded snapshot. Do not resume an uncertain
per-file transaction, claim atomic rollback, or retry an uncertain signal/exec.
Next attempt restores clean state and provisions afresh. Focused host regressions
protect distinct failure, uncertain-input and cleanup-ownership guarantees under
the [test-scope mandate](../Mandates/Test-Scope-Mandate.md); ordinary consumers
reuse those guards without repeating their complete negative matrix.

Fresh attempts start from fixture-free snapshots. Changing subsets uses another
clean attempt; no arbitrary larger-to-smaller guest contraction is needed.
There is no hot updater in an active scenario. F05/F06 qualify the actual native
activation APIs and successful trusted/untrusted runtime controls on each target;
command exit and a file readback alone are insufficient activation evidence.
Unsupported platform behavior keeps that target unavailable.

## Live refresh and recorded attempts

F07/F08 add explicit fixture refresh to the owned maintenance interface only.
Select a verified execution-owned bundle before borrowing the recorded instance.
Refresh is allowed only at the maintained idle boundary: no test/fixture worker,
fixture-using graphical session or unowned process may be active. Use existing
session and process-ownership checks; uncertainty refuses. Do not add a process
scanner, supervisor, kill-by-name path or concurrent-launch barrier.

Require the same installed subset/destinations for a live replacement; subset
changes or an unsafe/busy guest use normal owned recovery and a fresh preparation.
The maintenance owner excludes its launch/input paths while provisioning. The
same native activation/readback/witness checks run before new fixture use.
If the existing idle boundary cannot exclude other fixture launchers, refuse
refresh there; do not silently weaken it or implement a new supervisor.

F15 currently accepts first placement and identical read-only repeats. It
rejects changed selections and existing destinations; resetting its generation
requires an owned off-state restore. F07 must add an explicit maintenance-only
replacement operation using the shared staging, native and readback mechanics.
Keep ordinary attempt provisioning immutable. Before replacement, independently
verify the complete old closure and its ownership against the retained A input,
then preflight B with the same subset/destinations. Retain both inputs through
cleanup. Invalidate A readiness before the first write; publish B readiness only
after exact placement, native activation and independent byte/runtime checks.
Replace only A's verified files and exact native entries, preserving unrelated
state. Never clear the attempt latch or delete destinations to bypass F15's guards.

A successful A-to-B update keeps boot/domain and baseline/app snapshot identities
unchanged and records a new diagnostic generation. It changes no product service
or policy. Failure marks maintenance unavailable until ordinary owned recovery;
it does not promise same-boot recovery. Existing scenario results stay bound to
their original inputs; refresh never rescues a failing test.

## Runner and snapshot migration

F11/F12 establish fixture-independent baseline/app captures, retaining dependencies
and product provenance. Update the applicable VM/approval/environment owners
only when that target's implementation is delivered. Recover existing owners
before changing their decoding/writer contract. Preserve legacy stop/restoration;
do not adopt old payloads or rewrite their records into a new schema.

Use the authorized preparation route for an explicit one-time refresh. Remove
the complete proven owned legacy movable set before capture, including unselected
payloads, source copies and exact fixture admissions. Refuse ambiguous ownership;
do not sweep directories or mutate a saved snapshot in place. Verify clean
baseline and app captures and keep actual dependency/product invalidation.
Snapshot preparation itself needs no movable fixture runtime.

F11 delivered Ubuntu's schema-4
[clean snapshot boundary](../../tests/integration/Environment.md#ubuntu-clean-snapshots),
including actual baseline/app capture, standalone reuse, legacy retirement and
fixture-independent identities. F12 delivered the same
[Fedora boundary](../../tests/integration/Environment.md#fedora-clean-snapshots),
including enforcing SELinux, authenticated native policy/compiler backups,
standalone reuse and renewed Ubuntu qualification.

Qualify each runner branch once against these clean captures. Unmigrated branches
refuse clean captures before input; an implementation task enables only its
qualified branch/target. No second legacy qualification pass or runtime
qualification-receipt service is required. Shared changes renew affected prior
target checks. This plan supplies fixture infrastructure acceptance only.

F09 delivered Ubuntu's [product-free system preparation](../../tests/integration/README.md#ubuntu-product-free-system-preparation),
including the three Parent bootstrap aliases. Its registered
`check_fixture_system_product_free` selector qualifies the real product-free
attempt on Ubuntu. F10 delivered that boundary and the three aliases on
[Fedora 44](../../tests/integration/README.md#fedora-product-free-system-preparation),
including enforcing SELinux and exact native policy/label readback.
All other matrix entries retain their separate gates.

F16 delivered Ubuntu's [installed-system preparation](../../tests/integration/README.md#ubuntu-installed-system-preparation)
through explicit offline app restoration, fresh bootstrap and the same hard-only
readiness boundary. Its `check_fixture_system_installed` selector exercises the
real installed branch before system input. F17 delivered that boundary on
[Fedora 44](../../tests/integration/README.md#fedora-installed-system-preparation),
including enforcing SELinux, exact labels/native policy and read-only readiness
renewal after a system reboot. Other matrix entries retain their own gates.

F18 delivered Ubuntu's [installed E2E preparation](../../tests/integration/README.md#ubuntu-installed-e2e-preparation)
after actual online resume/rebind and explicit offline Kiosk attachment. The
shared setup boundary provisions the immutable native subset before asset
transfer and worker input, rechecking readiness before the setup reply. Ordered
wrapper/loop composition binds only installed aliases. Independent byte/runtime
proof, input refusals, no-write repeats, fresh readiness and host-edit immunity
passed on both restore branches. F19 delivered the same
[Fedora boundary](../../tests/integration/README.md#fedora-installed-e2e-preparation),
including enforcing SELinux and exact native admissions/labels over two online
and two offline attempts. Unqualified fixture profiles retain their gates;
scenario mutations and customer assertions remain separate.

### Runner acceptance matrix

| Envelope | Actual preparation boundary | Selector suffix / subset (status below) | Ubuntu / Fedora tasks |
| --- | --- | --- | --- |
| Product-free system | `system_snapshots._run_attempts(installed=False)`, `system_runner.installed_run(already_installed=False)`; also the three Parent setup bootstrap aliases | `system_product_free` / trusted-native hard only | F09 / F10 |
| Installed system | `_run_attempts(installed=True)` and `Suite.prepare_case`; qualify explicit offline app restore, rather than assuming the online default | `system_installed` / trusted-native hard only | F16 / F17 |
| Installed E2E | `InstalledJourney`, `InstalledSetup.provision`, `AssetTransfer.provision_installed`; online resume/credential rebind plus host composition of explicit offline qualification alternatives | `e2e_installed` / native | F18 / F19 |
| Product-free graphical E2E | `InstalledJourney.product_free` and asset-bearing package/upgrade preparations before customer input; GDM-only is empty | `e2e_product_free` / native or empty | F20 / F21 |
| Standalone transfer | `runner --qualify-transfer` through `Qualification.execute` / `AssetTransfer.provision`; move reusable fixture upload after SSH readiness | `transfer` / native | F22 / F23 |
| Standalone serial | Serial `Smoke`, `check_graphical_serial`, authenticated install/refusal aliases; retain credential/getty preboot lifetime | `serial` / native | F25 / F26 |
| Recorded serial | `controller_qualification.E2E_CASES['gdm-observation']` through `serial_harness.record_serial_journey` / `execution.ScenarioContext` and recorder | `recorded_serial` / native | F27 / F28 |

`check_fixture_system_product_free` and `check_fixture_system_installed` are
registered and qualified on both targets. `check_fixture_e2e_installed` is
registered and qualified on Ubuntu 26.04 and Fedora 44. The other four matrix selectors
are planned `check_fixture_SUFFIX` names, not executable until registered/listed.
Each invokes the real preparation branch, reads selected bytes
independently, uses a harmless fixture over owned SSH and cleans up before product
or worker input under the qualification contract below. Distinct restore/
preparation branches need their own proof. Preserve all customer assertions and
scenario checkpoints.

The headless trusted witness runs the selected hard executable as Riley, requires
exactly `ONPC_TEST_APPLICATION_READY` and exit 0, and needs no desktop file.
The native witness reads A and its adjacent two modules, runs A with
`--stay-alive` as Riley, checks the same marker and terminates only its recorded
owned process, requiring exit 0. These modes open no GUI. Use existing owned
process helpers; a marker without manifest byte readback is insufficient.

### Runner integration and qualification

F20–F28 reuse a small post-SSH fixture-readiness helper around F15 and existing
attempt/staging ownership. Each caller retains its restore, credential and input
guards. Standalone transfer, serial Smoke and recorded serial share this step;
installed-only restore checks stay with installed callers. Preserve separate
package/upgrade transfer semantics, inventory and preservation witnesses.
Keep runtime subsets finite; add no generic runner framework or case installer.

Each target/envelope task must:

- For a nonempty closure, select and retain its immutable input before
  restoration, provision after guarded SSH readiness, and check current readiness
  before releasing input.
  Enable only the qualified target/branch; unqualified branches refuse.
- Run affected host composition/provenance/ownership checks. Bind all aliases,
  including ordered wrapper/loop overrides and dormant guards, to their actual
  preparation boundary. Check missing/incompatible refusal before guest mutation
  or worker input and selection immutability despite host source edits.
- Exercise each distinct real preparation boundary on its declared target.
  Independently verify selected manifest bytes/metadata and harmless runtime use,
  no-write repeats and fresh attempt/boot bindings with prior readiness refused.
  Product-free branches preserve product absence. An empty closure verifies
  absence of movable payload and gains no dependency on a native input.
- Reuse shared corruption, source-edit, interruption/lost-reply and ownership
  proofs for unchanged contracts. Add or renew focused checks for changed wiring
  or a distinct failure boundary; do not repeat the full shared matrix for each
  alias or copy installed-history implementations. Retain the exact input binding
  in each envelope's evidence. Renew affected earlier-target proof after shared
  changes; Fedora retains enforcing SELinux and exact native admissions/labels.
- Stop before customer/worker input or product assertions. Preserve scenario
  mutations; copy no complete fixture collection into results. Finish watched
  owned restoration and credential/staging/input/transport cleanup, then update
  delivered operational owners and follow the master's close-out contract.

Reuse existing byte/runtime audit and qualification helpers. Host checks protect
shared refusal/immutability guarantees; installed histories prove real boundary
wiring and target behavior. Record which retained shared proof applies. A new or
changed integration path must still establish its own input and readiness guards.
Preparation supplies no customer/E2E acceptance.

### Source-backed consumer and alias disposition

Retain the dispatch distinctions established by F01:

- [system_snapshots](../../tests/integration/system_snapshots.py) partitions
  lifecycle/removal by `history.start`, first-configure/PAM as product-free and
  authorization/enforcement/session as installed. `fresh_install=True` keeps
  grouped phases product-free. Preserve the trusted history's previous-package
  requirement; engineering preparation stops before any phase assertion.
- [suite_lease](../../tests/e2e/suite_lease.py) and
  [execution](../../tests/e2e/execution.py) select installed versus product-free.
  Suite defaults online; the installed-system qualification must explicitly
  exercise offline. InstalledJourney provisions before `plan.stage_actions`.
- Smoke wrapper membership follows the final ordered `qualification_class`
  assignment, including loops. `KioskEntryQualification` and transitive
  subclasses in [parent_setup_qualification.py](../../tests/integration/parent_setup_qualification.py)
  are installed E2E; cover online rebind and explicit offline restore alternatives.
- Product-free smoke exceptions remain `check_e2e_gdm_product_free`,
  `check_e2e_product_free_entry`, `check_e2e_upgrade_assets`,
  `check_e2e_chinese_language_assets`, `check_e2e_desktop_language`,
  `check_e2e_package_authority`, `check_e2e_package_command`,
  `check_e2e_customer_reboot`, `check_e2e_restart_notice`,
  `check_e2e_unrelated_reboot_request`, `check_e2e_package_upgrade`,
  `check_e2e_chinese_kiosk_lifecycle` and `check_e2e_chinese_current_install`.
  GDM-only transfers no movable bytes; other branches retain scenario checkpoints.
- `check_parent_setup`, `check_parent_input` and
  `check_parent_standard_input` use the separate baseline/bootstrap branch
  after `Transport.probe_ready` and before `InstalledSetup.run`. Host composition
  must bind all three. `check_parent_about`, `check_parent_access` and
  `InstalledJourney.install_current_package` retain their dormant guards;
  this plan does not enable them.
- [runner](../../tests/e2e/runner.py) transfer, authenticated install/refusal and
  [check_graphical_serial](../../tests/integration/check_graphical_serial.py)
  retain their distinct preparation, credential and recipient guards. Preserve
  successful-install reboot versus refused-install logout/no-reboot assertions.
- [serial_harness](../../tests/e2e/serial_harness.py) recorded preparation retains
  HAR09/HAR10 recorder/stage completion, observations before replies, boot
  continuity, logout/session absence and worker shutdown. It is not a standalone
  Smoke alias.
- Baseline credential/display/getty-only consumers, host graphical transport/
  worker doubles, recovery/storage and `check_e2e_watch` keep their own owners;
  they gain no native fixture dependency or acceptance credit.
- [app_snapshot](../../tests/e2e/app_snapshot.py) defaults offline; Suite and
  [prepare_appsnapshot](../../tools/prepare_appsnapshot.py) explicitly use online.
  Preserve install/verification/reboot and credential publication in both.
- [vm_control](../../tests/integration/vm_control.py) diagnostics use their actual
  journey branch, maintenance lease and cleanup. Native profiles select the
  declared closure; `chinese` verifies language dependencies and needs no
  movable bytes.

[AssetTransfer](../../tests/e2e/asset_transfer.py) retains one-shot phase/attempt
identity, replay/collision refusal, post-boot inventory readback and upgrade
account/locale/unrelated-file witnesses. Native `fixture_actions` keep their
wrong-entry/refusal timing. Attachments, document changes, new versions and
launcher mutations remain deliberate scenario actions.

## Planned public interfaces

Keep `tools/fixture` as the shared migration-plan launcher. Extend existing
`tools/run-tests fixtures` build/verify for target `native-runtime` input and
`tools/test-vm` with explicit owned maintenance sync/inspection. Select registered
targets and finite subsets; accept no arbitrary destination or guest command.
Expose exact validated options/help in their implementation tasks. There is no
new catalogue-ID, cache inspect/prune or quiesce option.

`check_fixture_snapshots` is registered and qualified for Ubuntu and Fedora; use
`tools/run-tests integration --list` for bindings. `check_fixture_provisioning`
is registered and qualified for both targets' fresh owned attempts. F53 delivered
Ubuntu's native backend environment prerequisite through the
[clean snapshot owner](../../tests/integration/Environment.md#ubuntu-clean-snapshots);
F05/F06 delivered both-target installed provisioning acceptance through the
[shared provisioner](../../tests/support/README.md#attempt-owned-fixture-provisioning).
The two system matrix selectors and installed E2E selector are delivered on both
targets. The remaining four matrix selectors and `check_fixture_live_refresh`
remain **planned and unimplemented** until their own registration/listing;
examples in briefs grant no operation. Other runner dispatch remains unavailable.

## Acceptance and ownership handoff

Each task owns its lowest effective host checks, target proof where declared,
and recorded cleanup. Host checks cover frozen sources, membership/ABI failures,
interrupted build/publication, inherited producer lifetime, retention identity,
authenticated input reads and failed provisioning with no released input.
Provisioning, clean captures, each real preparation envelope and idle same-boot
refresh are independently qualified on both canonical targets.

Update enduring rules in their existing storage, support, VM, approval,
environment and runner owners as delivery happens. F13 independently reviews
the final candidate and exact evidence; it cannot replace missing target checks.
Apply the master's [mandate routes](Fixture-Execution-Plan.md#applicable-mandates)
to every remaining integration and review. Preserve valid proof for unchanged
exact bindings; renew only acceptance invalidated by changed inputs or contracts.
No customer journey, product behavior, pending fixture capability or E2E queue
task receives completion credit from this migration.
