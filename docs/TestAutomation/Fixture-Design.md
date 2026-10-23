# Host-owned fixture lifecycle

Build immutable fixtures on the host, transfer only the selected runtime closure,
and verify it before test input. Fixture-only changes must not invalidate product
packages or clean VM snapshots. Existing artifact, retention, transport and VM
owners retain authority. The [support guide](../../tests/support/README.md) and
[environment contract](../../tests/integration/Environment.md) own operational
interfaces and target qualification.

## Scope and simplicity

Use one producer and execution-owned immutable inputs. Reuse existing storage,
authenticated handoff, native-policy APIs and owned VM recovery. There is no
shared version catalogue, cross-journal pin graph, second retention policy,
fixture supervisor or new native-policy acknowledgement protocol. An uncertain
guest mutation fails the attempt and requires normal owned recovery.

<a id="frozen-schema-vocabulary"></a>
<a id="f52-independent-design-review"></a>

Only the manifest, ownership and readiness contracts below define this design.
Legacy schema/review anchors remain for existing links.

## Host authority and minimum guest footprint

Sources, compilers, workspaces, expected results and unused collections stay on
the host. Guests receive selected executables, modules, desktop files and data.
Resolve guest owners from accepted roles; never copy host UIDs. Credentials
never enter bundles.

### Frozen placement inventory

[baseline_assets.py](../../tests/fixtures/baseline_assets.py) and
[native_assets.py](../../tests/fixtures/native_assets.py) own exact membership,
destinations, modes, symbolic ownership, absence controls and native actions.

| Family | Placement and safety boundary |
| --- | --- |
| Native GUI | Selected executables and adjacent GUI/automation modules under `/opt/onpc-test-fixtures/Applications`, with required desktop files. Preserve nested-version and legacy-root controls separately. Executables 0755 and modules 0644 are Jordan-owned; desktop files 0644 belong to their declared child. Intentionally untrusted; Fedora uses exact child/content admissions. |
| Mechanical and pattern | Root-owned declared command, whitespace, wildcard, unrelated-version and retention controls; no unnecessary GUI runtime. |
| Trusted hard/soft and activity | Distinct hard/soft bytes and only required activity modules. Root-owned; trust exact declared files, never whole directories. |
| Catalogue and PATH | Complete selected precedence comparisons, including masked entries, user/system ownership and absence of the fallback executable. |
| Environment | Accounts, pictures, passwords/keyrings, language/desktop settings, SSH, dependencies, backend configuration and distro-specific masks remain baseline-owned. |
| Scenario inputs | Product packages, attachments/documents, future versions, deliberate file/launcher mutations and policy/grants/usage keep independent provenance. Provisioning must not preseed results. |

One `native-runtime` build per target supplies finite subsets (`native`,
`riley-grid`, `activity`, mechanical, trusted-native and catalogue) and their
declared unions. Do not build a version per subset or transfer unused collections.

### Artifact and named-input consumers

[artifact_inputs.py](../../tools/artifact_inputs.py),
[package_inputs.py](../../tools/package_inputs.py) and
[test_storage.py](../../tools/test_storage.py) own input identity/declaration.
Native-runtime, complete artifacts and packages have separate source closures
and provenance. Dispatch declarations must match actual consumers, including
empty and dormant branches. A current digest never silently replaces an older
nonempty failed input.

## Identity and build publication

Build frozen sources in host-side target environments. Record source, toolchain,
OS/release/architecture and runtime dependency inputs separately from output
digests. Verify Ubuntu 26.04/Fedora 44 ABI compatibility; do not relabel host
binaries or compile in a guest. Recheck sources to prevent mixed builds.

Use one versioned manifest, payload and completion marker. Bind every member's
length, checksum, mode, symbolic owner, finite destination ID, subset/absence
control and native action. Derive paths from maintained declarations. Reject
unsupported schemas, malformed/duplicate fields, unsafe members, links/devices,
undeclared bytes and inconsistent lengths before mutation. Independently verify
the completed tree before atomic publication; a path or marker is insufficient.
See the [frozen bundle contract](../../tests/support/README.md#frozen-native-fixture-bundles).

### Execution ownership and retention

Select/register immutable inputs before lifecycle lease acquisition or restore,
respecting the enclosing [central VM checkout](../Mandates/VM-Mandate.MD#central-vm-checkout).
Retain inputs until descendants and owned cleanup finish. The producer lease
owns temporary work; copy verified output into the execution's retained allocation
before releasing it. Each allocation has one deletion owner. Independent
executions may retain independent bounded copies.

Reuse only matching verified inputs already owned by the execution journal.
Privileged consumers authenticate the actual caller and open inputs read-only.
Existing retention limits/recovery apply; incomplete nonempty inputs refuse.
Source edits cannot change an attempt's selection.

## Owned SSH provisioning and readiness

The [shared provisioner](../../tests/support/README.md#attempt-owned-fixture-provisioning)
runs under the exclusive VM lease and guarded, watched SSH, after restore and
transport readiness and before fixture launch or scenario input.

Preflight the complete closure, accepted accounts, existing destinations and
native metadata. Refuse modified/unknown files, unsafe paths, wrong owners and
incompatible inputs before writes. Register private staging with the attempt;
install only declared bytes/owners/modes. Reuse native trust/admission and label
APIs, preserving vendor/product policy and unrelated state. Independently read
back bytes/metadata and exercise a harmless runtime witness.

Readiness binds manifest/subset, actual VM UUID, boot and attempt. Snapshot
records and other attempts' receipts are insufficient. Identical repeats verify
without rewriting matching payloads. Transfer, placement or native activation
failure, or uncertain reply, invalidates the attempt: release no input, retain
diagnostics and restore its recorded snapshot. Do not resume an uncertain
per-file transaction or blindly retry signal/exec.

Fresh attempts start fixture-free. Subset changes need another clean attempt.
Command success and file readback alone do not prove native-policy activation;
trusted/untrusted runtime witnesses must work on the target. Unsupported target
behavior keeps that target unavailable.

## Live refresh and recorded attempts

Live replacement remains proposed; ordinary provisioning allows first placement
and identical read-only repeats. It rejects changed selections and existing
destinations; owned off-state restore resets the generation.

Refresh requires verified retained input and an idle, owned maintenance guest:
no test/fixture worker, fixture-using graphical session or unowned process may
be active. Existing ownership checks must exclude concurrent fixture input/launch;
uncertainty refuses. Add no scanner, kill-by-name path or supervisor.

Keep the same subset/destinations. Verify old closure A against retained input,
preflight B, retain both through cleanup, invalidate A readiness before writes
and publish B readiness only after placement, native activation and independent
byte/runtime checks. Replace only A's verified files and exact native entries.
Never clear latches or delete destinations to bypass guards. Busy guests and
subset changes use fresh preparation.

Success preserves boot/domain and baseline/app snapshot identities, changes no
product service/policy and records a new diagnostic generation. Failure needs
owned recovery; same-boot recovery is not guaranteed. Earlier results remain
bound to their original inputs.

## Runner and snapshot migration

Captures retain dependencies and product provenance but exclude owned movable
payload, source copies and exact admissions. Retire only proven owned files;
never sweep ambiguous directories, hide leaked sources by renaming, or mutate
snapshots in place. Preserve recovery/environment records and account pictures.
Recover existing owners before changing record contracts; never silently adopt
old payloads or rewrite their journals.

Ubuntu and Fedora have [clean snapshot boundaries](../../tests/integration/Environment.md).
Current envelope/target availability belongs to the
[installed runner guide](../../tests/integration/README.md); this design does not
enable unregistered or unqualified branches.

### Runner acceptance matrix

| Envelope | Preparation boundary and subset |
| --- | --- |
| Product-free system | `system_snapshots._run_attempts(installed=False)` and `system_runner.installed_run(already_installed=False)`, including Parent bootstrap; trusted-native hard only, preserving product absence. |
| Installed system | `_run_attempts(installed=True)` and `Suite.prepare_case`; trusted-native hard only. Explicit offline restore needs separate proof. |
| Installed E2E | `InstalledJourney`, `InstalledSetup.provision` and `AssetTransfer.provision_installed`, before stage actions; native subset. Preserve online resume/rebind and explicit offline attachment. |
| Product-free E2E | `InstalledJourney.product_free` and package/upgrade preparations after SSH, before customer package input; native subset. GDM-only uses an empty closure. |
| Standalone transfer | `Qualification.execute` / `AssetTransfer.provision`: transport-only preboot, native provisioning after SSH, separate package-only transfer. |
| Standalone serial | Serial `Smoke`, `check_graphical_serial` and authenticated install/refusal aliases: preserve credential/getty preboot lifetime; native provisioning precedes graphical/customer input. |
| Recorded serial | `controller_qualification.E2E_CASES['gdm-observation']`, `serial_harness.record_serial_journey` and `execution.ScenarioContext`: recorder/stage ordering and native subset; not a standalone serial alias. |

The headless hard witness runs as the accepted child, requiring exactly
`ONPC_TEST_APPLICATION_READY` and exit 0. The native witness reads A and its two
modules, runs A with `--stay-alive`, checks the marker and stops only its recorded
owned process, requiring exit 0. Neither opens a GUI. A marker alone is insufficient
without independent manifest-byte verification.

### Runner integration and qualification

Reuse one post-SSH readiness step and existing attempt/staging ownership. Callers
retain distinct restore, credential, package/upgrade and input guards. Enable only
qualified branches; missing/incompatible inputs refuse before mutation/input.
Empty closures verify absence and acquire no native-input dependency.

Each distinct target/preparation path needs selected-byte/metadata and harmless
runtime proof, no-write repeats, fresh attempt/boot binding and owned cleanup
before customer/worker input. Fedora retains enforcing SELinux and exact
admissions/labels. Qualification stops at readiness and grants no customer/product
acceptance. Preserve scenario mutations and assertions.

### Validation reuse and invalidation

Validate the changed guarantee and actual caller at the lowest effective scope.
Reuse unchanged refusal, corruption, source-edit immunity, uncertain-reply and
ownership/recovery proof. Host composition covers aliases sharing a preparation
path, ordered wrapper/loop overrides and dormant guards. Distinct entry, package,
upgrade and empty-GDM paths retain separate proof.

Renew target proof when provisioning, activation, restore or ownership changes
invalidate it. A new caller, allowlist extension or prose change alone does not
invalidate every envelope. Identify the affected binding and smallest check
before extra restores/reboots/builds or live faults. Missing required proof
remains a blocker; infrastructure qualification never substitutes for customer results.

### Source-backed consumer and alias disposition

System preparation preserves product-free versus installed history and previous
package requirements. Installed journeys provision before stage actions; smoke
membership follows final ordered assignments, including loops. Parent bootstrap
runs after transport readiness; dormant branches stay guarded.

`system_snapshots` partitions lifecycle/removal by `history.start`, first-configure/PAM
as product-free and authorization/enforcement/session as installed;
`fresh_install=True` keeps grouped phases product-free. Parent bootstrap aliases
`check_parent_setup`, `check_parent_input` and `check_parent_standard_input` run
after `Transport.probe_ready` and before `InstalledSetup.run`.
`check_parent_about`, `check_parent_access` and
`InstalledJourney.install_current_package` retain their dormant guards.
`KioskEntryQualification` and transitive subclasses use installed preparation.

The product-free smoke bindings are `check_e2e_gdm_product_free`,
`check_e2e_product_free_entry`, `check_e2e_upgrade_assets`,
`check_e2e_chinese_language_assets`, `check_e2e_desktop_language`,
`check_e2e_package_authority`, `check_e2e_package_command`,
`check_e2e_customer_reboot`, `check_e2e_restart_notice`,
`check_e2e_unrelated_reboot_request`, `check_e2e_package_upgrade`,
`check_e2e_chinese_kiosk_lifecycle` and `check_e2e_chinese_current_install`.
This finite dispatch boundary prevents installed defaults from provisioning or
installing the product in a product-free attempt.

Transfer/serial preserve recipient/credential guards and successful-install reboot
versus refused-install logout/no-reboot results. Recorded serial preserves
recording/stage completion, observations before replies, boot continuity, session
absence and worker shutdown. Asset transfer preserves one-shot phase/attempt
identity, replay/collision refusal and postboot inventory readback.
Upgrade transfer retains account, locale and unrelated-file preservation
witnesses; native `fixture_actions` retain wrong-entry/refusal timing.
Recorded preparation retains HAR09/HAR10 stage obligations and binds fixture input
to recorder provenance before the ready reply; these are compatibility requirements,
not a requirement to rerun complete product journeys for fixture qualification.

Standalone app snapshots default offline; suites and explicit preparation use
online. Preserve installation, verification, reboot and credential publication
in both. Credential/display-only consumers and language-only profiles gain no
movable-fixture dependency. Attachments, document changes, new versions and
launcher mutations remain scenario actions.

## Planned public interfaces

Use existing fixture build/verify, authenticated handoff and owned maintenance
interfaces. Select registered targets/finite subsets; accept no arbitrary guest
command or destination. Planned selectors/refresh remain unavailable until
registered and qualified. No catalogue/cache-prune or quiesce service is needed.

## Acceptance and ownership handoff

Storage, support, VM, approval, environment and runner contracts retain authority.
Host checks protect freezing, membership/ABI, interrupted publication, producer
lifetime, retention and authenticated reads. Target proof covers activation,
clean captures, preparation and any future refresh. Preserve valid exact proof
and owned cleanup; infrastructure readiness supplies no customer acceptance.
