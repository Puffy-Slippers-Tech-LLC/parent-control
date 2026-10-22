# Host-owned fixture lifecycle: target design

Status: **proposed; not implemented**. Implementation and acceptance belong to
the [fixture execution plan](Fixture-Execution-Plan.md). Existing baseline,
storage and ownership contracts remain effective until the queued migration
delivers and updates their corresponding owners.

## Host authority and minimum guest footprint

Keep fixture sources, compilers/build workspaces, immutable bundles, manifests,
expected results and reusable input collections on the host. Host-only doubles,
validators and generators never enter a guest. Transfer only a selected test's
declared runtime dependency closure: executables it launches, runtime modules
they load, launchers they require and documents/data it actually opens there.
Do not transfer the complete repository, all fixture profiles, unused package
formats, builders or a compiler to make a guest self-sufficient. Existing host
qualification evidence and customer assertions retain their present owners.

Baseline preparation keeps unavoidable installed dependencies, fixed accounts,
desktop/service settings and transport prerequisites. It must not cache movable
fixture applications or data in new baseline/app snapshots. Any exception needs
a concrete runtime necessity, named inventory owner and separate compatibility
dependency; convenience is insufficient. Future Snap/Flatpak/game capabilities
remain pending and do not expand this migration's finite delivered inventory.

The F01 inventory below freezes placement and consumer requirements against the
current source. It does not implement them. Scenario mutations stay at their
declared checkpoints; reusable provisioning must not preseed product policy,
grants, usage or an asserted result. F51 owns schema/transition details and F52
owns the subsequent independent design review.

### Frozen placement inventory

The finite declaration is [baseline_assets.py](../../tests/fixtures/baseline_assets.py)
(`native_files`, `catalogue_files`, `desktop_settings_files`,
`automatic_update_files`) plus [native_assets.py](../../tests/fixtures/native_assets.py)
(`native_policy_files`). [baseline_fixtures.py](../../tests/integration/baseline_fixtures.py)
currently builds/reconciles it during baseline preparation. Owner roles below
mean the accepted guest accounts, never a host UID: `child` is Riley, `other`
Jordan, `parent` Jamie and `system` root. Preserve their actual UID/GID and the
existing declaration's modes during migration.

| Family / complete original output boundary | Frozen placement and minimum guest closure | Original ownership / native action | Delivery owner |
| --- | --- | --- | --- |
| A/H/S/N GUI identities: `Exact Fixture.AppImage`, `Path With Spaces.AppImage`, `Versioned/Lunar Client-3.7.17.AppImage`, `PrismLauncher.AppImage` beneath `/opt/onpc-test-fixtures/Applications`; legacy root-level `Lunar Client-3.7.17.AppImage` | Runtime. Select only required executables, their adjacent `onpc-test-gui.py` and `gtk_automation.py`, and launchers actually used. The nested S needs the `Versioned/` runtime pair; other identities use the root pair. Legacy S is an untrusted compatibility control, not the active S launcher. | Executables 0755 and runtime 0644, Jordan-owned. Four role desktop files for each of Riley and Jordan, 0644 and owned by that user. Intentionally absent from file trust. Fedora exact child-UID/content admissions remain fixture-owned. | F02 bundle; F33 imports all original members; F15 contraction; F05/F06 activation; consuming envelope tasks below |
| Mechanical executable `/opt/onpc-baseline-assets/onpc-test-application`; command, whitespace, pattern and retention targets in `baseline_assets.NATIVE`; pattern sibling `Unrelated.AppImage`; corresponding four system launchers | Runtime engineering subset. Each selected command needs its mechanical bytes; the pattern comparison also requires `Unrelated.AppImage`. Include desktop entries for catalogue/launcher consumers. No Python GUI runtime is needed. | Root:root, executable 0755 / desktop 0644, untrusted. Preserve whitespace and unrelated-pattern controls. | F02/F33/F15/F05/F06; system consumers F09/F10/F16/F17 |
| `TRUSTED_NATIVE`: `/opt/onpc-test-fixtures-trusted-{hard,soft}/native-fixture` and `TrustedHard`/`TrustedSoft` system desktop entries | Runtime trusted-native subset: selected headless executable plus a desktop file only when the consumer uses discovery. Distinct hard and soft bytes stay distinct. | Root:root 0755 / 0644. Exact file-trust admission for the two executables; no directory trust. | F02/F33/F15/F05/F06; retained native-transaction consumers through system envelope |
| `/opt/onpc-test-fixtures-activity/native-fixture` and its adjacent two GUI files | Runtime activity subset: exactly these three files. No A/H/S/N launchers or copied interpreter/GTK tree. | Root:root 0755 executable / 0644 runtime; all three admitted to exact native file trust. | F02/F33/F15/F05/F06; activity E2E consumers F18/F19 |
| Catalogue precedence/path set from `CATALOG_ENTRIES` and `catalogue_files` | Runtime engineering subset. Preserve system/child/parent/other Shared, ChildOnly, OtherOnly, ParentOnly and masked desktop entries; Relative, RelativeUnavailable, DesktopPath, SystemPreferred and SystemFallback; their declared mechanical targets, user `.local/bin`/`bin`, `/usr/local/bin`, `/usr/bin` and `catalog/desktop path` witnesses. The consumer selects its complete precedence comparison, including negative/masking controls. | Targets 0755, entries 0644, exact declared symbolic role. Keep root-owned targets distinct from account-owned PATH controls; no trust admission. | F02/F33/F15/F05/F06; system catalogue consumers F09/F10/F16/F17 |
| Folder-renamer overrides for Riley, Jordan and Jamie; Ubuntu four `apt-daily*` service/timer masks | Environment, retained in baseline: six per-user regular files plus Ubuntu's four regular empty system units. They do not belong to a runtime subset and cannot be retired by contraction. | Per-user 0644 overrides; root:root 0644 APT masks. No fixture trust action. | F33 classification; F11/F12 dependency-only preparation |
| Native trust fragment/backend records, Fedora `69-onpc-baseline-runtime.rules` and `89-onpc-baseline-fixtures.rules`, fixture ownership/pending record | Environment backend configuration remains baseline-owned; exact fixture admissions, trust and ownership metadata move with the selected runtime transaction. Preserve original records for recovery, rather than treating them as payload to copy. | Five trusted paths total (hard, soft, activity and its two modules). Trust fragment root:`fapolicyd` 0600; Fedora admission files root:`fapolicyd` 0644. Other fixture outputs retain declared ownership. Fedora rules admit the four active executable hashes and two runtime hashes for the two children, without making them trusted. | F24/F30 original proof; F31/F50 native protocol; F33 import; F15/F05/F06 composition |
| Fixed accounts, pictures, passwords/keyring preservation, welcome/idle/desktop settings, serial getty/login timeout, dependency packages and SSH service/host keys | Environment. Keep the finite [environment inventory](../../tests/integration/Environment.md#reusable-preparation-ownership) and [guest tools](../../tests/integration/guest_test_dependencies.py) in preparation. GTK/Python and native libraries needed by native fixtures are target dependencies, not copies of the host interpreter. | Existing account/tool/console owners and accepted OS package provenance. Credentials never enter a bundle. | F11/F12 split environment ABI; F24/F30 preserve accepted original decoding |
| Builder sources, compilers, native identity intermediates, manifests/checksums, expected results, Flatpak repository/bundle, Snap package and offline-game payload; copied standalone GUI runtime | Host-only. [build_test_applications.py](../../tests/fixtures/build_test_applications.py) currently emits these alongside native outputs; its full output is not the new profile. Snap/Flatpak/game runtime tests remain host-only, and pending guest capabilities gain no implementation credit. Build directories, private Flatpak home and packaging scratch never enter a guest. | Host shared storage/retention authority. No guest install, runtime admission or cache key for these pending guest capabilities. | F29/F02 profile extraction; F03/F14/F04 publication/pins/retention |
| Product packages/current and previous releases; finite native dependency update pairs | Host immutable test inputs, separately identified from fixtures. Transfer only the selected target package(s) at the owning install/update checkpoint. Native old/new package transactions remain scenario mutations, never reusable fixture repair. | Existing artifact manifest, signature/dependency verification and attempt-frozen selection; installation stays on the public installation route. | F02 source separation; F09–F28 envelope provenance; F11/F12 snapshot coupling |
| Attachments, documents, copy/rename/save-error inputs, new versions and launcher removal; LDAP/SSSD configuration/accounts, keyring challenges, policy/grants/usage | Scenario-owned. Only finite bytes actually opened in the guest are transferred, at their existing checkpoint. Attachment sentinels/readbacks remain independently asserted. No reusable profile precreates the requested product result. | Existing scenario owner, mutation guards and cleanup; no added blanket native trust. | F09–F28 preserve checkpoint order; F13 final disposition audit |

The original declaration contains 34 native, 33 catalogue and six desktop-setting
files, plus four Ubuntu APT masks or two Fedora admission files: 77 Ubuntu / 75
Fedora outputs, excluding the separate receipts/backend records. These counts
describe the reviewed original set, not a replacement for its exact file map.
All members, including unrequested launchers and compatibility controls, enter
F33's original-proof classification before any subset is selected.

`native` means `native_assets.sources()` (eight active executable/runtime source
keys plus four launcher keys). `riley-grid` means `riley_grid_sources()` (the same
eight runtime keys and only Riley's A launcher). `activity` means
`activity_sources()` (three keys). Mechanical, trusted-native and catalogue
selections use the exact finite declaration above. A combined consumer takes
the union, deduplicates shared destinations and retains required negative
controls. These are subsets of one `native-runtime` build per target ABI, never
separate build keys. Host-only package formats and complete fixture image roots
must not leak into that union.

Catalogue closure also preserves the independently checked absence of
`/usr/local/bin/onpc-test-catalog-fallback`. A positive inventory alone cannot
replace the PATH fallback assertion in `system_enforcement.provision_catalog`.

### Original preparation source closure

[prepare_vm.SCRIPT_FILES](../../tests/integration/prepare_vm.py) contains these
17 entries. `preparation_digest` hashes their ordered names, lengths and bytes;
its JSON normalization excludes `concurrency`, `backup_root`, per-VM `id` and
`enabled`, retaining the other configuration dependencies.

- `tests/integration/`: `prepare_vm.py`, `guest_test_dependencies.py`,
  `chinese_language_assets.py`, `vm_config.py`, `baseline_guest_entry.py`,
  `test_account_password.py`, `baseline_fixtures.py`, `baseline_console.py`.
- `tests/fixtures/`: `baseline_assets.py`, `native_trust.py`, `native_assets.py`,
  `build_test_applications.py`, `onpc_test_application.c`, `gui_application.py`.
- `common/oh_no_parent_control_ui/`: `gtk_automation.py`, `test_identities.py`.
- `config/test-vm.json`.

[baseline_guest.prepare](../../tests/integration/baseline_guest.py) stages their
union with `REQUIRED_CHECKOUT_ENTRIES` (already included), plus
`test_user_icons/{jamie,casey,riley,jordan}.png`: 21 root-owned 0600 files beneath
the private `/var/lib/onpc-baseline-preparation/checkout`. The temporary service,
link and consumed password disappear; `mode`, `success`, `preparation.log` and
the checkout remain. Successful reboot verification removes `reboot-required`.
F24/F30 preserve accepted marker/capture and raw original proof. F33 classifies
every retained source member as data, retiring movable source/builder copies
only under that proof and preserving environment/recovery records and avatar
identity. F11/F12 change staging and digest together; deleting currently required
digest inputs early would break legacy verification. Capture must inspect this
location and archived copies, not merely `/opt` runtime destinations.

### Artifact and named-input consumers

[artifact_inputs.capture](../../tools/artifact_inputs.py) already separates
package and fixture source/toolchain/runtime identities;
[package_inputs](../../tools/package_inputs.py) freezes the packaging map.
However, [build_test_artifacts](../../tools/build_test_artifacts.py) currently
invokes its fixture builder from the live checkout. F02 must freeze the fixture
closure too, rather than crediting the frozen product source tree for both.
The existing fixture source list includes builder, GUI runtime, native assets,
C/GUI application and shared GTK automation; baseline declarations and native
trust are additional placement/activation inputs with their own identities.
[gui_runtime](../../tests/fixtures/gui_runtime.py) currently constructs a Debian
multiarch standalone runtime. It is not evidence of a Fedora-compatible native
builder; F02 must deliver target construction and actual ABI verification.

The complete builder also emits native default/game/Flatpak wrappers, the future
S `Lunar Client-3.8.0.AppImage`, legacy image-root launchers,
`fixture-targets.json`, Flatpak repository/bundle, Snap package and
`SHA256SUMS.json`. Future S is a scenario update input; the other unused output
collections stay host-only. `system_runner.stage_assets` currently verifies a
Flatpak member even for native consumers; that host verification is not a reason
to transfer it. F02 and F09–F28 separate those dependencies without removing
existing builder/runtime coverage or consumer assertions.

[test_storage.named_input](../../tools/test_storage.py) includes current package
sources by default. `fixture_source` and `upgrade_source` add fixture identities;
`vm_source` binds the selected VM, and platform binding applies to every named
input. Preserve the literal Boolean declarations consumed through AST by
`test_commands.qualification_input_options` and the pre-dispatch preparation in
`qualification_artifact_command`. Current prefixes are `onpc-parent-setup-`,
`onpc-native-fixtures-` and `onpc-upgrade-v1.2-`, with the declared VM/source
suffixes. A current snapshot does not refresh an older immutable input.
F09–F28 migrate these consumers to a single pinned fixture reference alongside
the independently verified product input; F14 supplies cache access within an
active execution session. No failed assertion may trigger input replacement.

The following freezes the current literal named-input alternatives. Names omit
only `check_e2e_`, except explicit `check_parent_*` names; absent flags are false.
These are input-identity groups, **not** envelope aliases: apply the actual
dispatch map below, including its product-free, setup and dormant exceptions.
Each wrapper's declarations must continue to agree under the AST validator.

```text
upgrade_source=True:
  upgrade_assets, chinese_kiosk_lifecycle, package_upgrade
package_source=True, fixture_source=True:
  baseline_journey, baseline_app_effects
vm_source=True, fixture_source=True:
  retained_app_visits, riley_native_grid, native_fixtures,
  choices_overlay_to_kiosk, overlay_valid_choices, retained_unlock_success,
  request_flow, cross_surface, request_exit, kiosk_eligible_choices,
  request_choices, retained_entry, overlay_choices
vm_source=True:
  lock_surface, fresh_child_allowed, window_switch, lock_recipient,
  retained_parent, set_an_allowance_for_a_named_child, retained_unlock,
  challenges, desktop_session, unlock
fixture_source=True:
  app_activity, catalogue_search, match_editor, policy, native_grid_usable,
  match_save_cancel, overlay_license, review_a_rejected_parent_rule_s_report,
  overlay_browser_links, catalogue, native_app, access_choices,
  overlay_approved_exit, policy_legend, natural_expiry,
  read_overlay_about_and_links, overlay_approval
package_source=True:
  kiosk_preferences_confinement, restart_notice, named_child_custom_saves,
  chinese_native_auth, customer_reboot, kiosk_entry, overlay_rejection,
  allowance_presets, feedback_read, feedback_privacy,
  reminder_fullscreen_preference, chinese_current_install, custom_save_trace,
  baseline_auth_pause, parent_language, parent_hebrew_policy, revocation,
  parent_dialog_language, allowance, parent_language_isolation,
  read_parent_information_links, unrelated_reboot_request, overlay_language,
  kiosk_feedback_confinement, kiosk_reminder_binding, overlay_prompt,
  time_explanation, revoke_cancel, kiosk_language_restoration, parent_rtl,
  kiosk_notification_wellbeing, kiosk_approved_flow, kiosk_language, text,
  kiosk_approval, overlay_reminder_editing, shell_panel, allowance_boundaries
named_input() with no options:
  check_parent_standard_input, check_parent_setup, check_parent_access,
  check_parent_input, check_parent_about, operate_public_connectivity_controls,
  license_viewer, app_restart, edit_and_save_an_open_synthetic_document,
  kiosk_no_child, countdown_minutes, auth_result,
  wait_a_bounded_real_interval_under_the_attempt_guard, trace_stable_state,
  document_open, format, gdm_navigation, time_profiles_daily, desktop_keyring,
  shell_search_results, shell_search, parent_save, eligible_kiosk_fixtures,
  kiosk_valid_duration, trace, feedback_block_semantics,
  independent_network_management, save_chooser, approval_flow, mate_prompt,
  set_fresh_thirty_minute_allowance, countdown, chinese_language_assets,
  desktop_language, feedback_length, files, read_restricted_station_about,
  countdown_ticks, diagnostic_export, toggle, parent_support, kiosk_fixtures,
  gdm_product_free, accessibility_input_trace, parent_website, feedback_reset,
  attachments, kiosk_multiple, feedback_link_semantics, feedback_formats,
  auth_prompt, feedback_rejection, parent_save_trace, parent_search_launch,
  product_free_entry, read_an_expanded_time_explanation, terminal_provider,
  gdm_recipient, file_chooser, package_authority,
  set_jordan_thirty_minute_allowance, request_duration, attachment_items,
  operate_the_countdown_context_menu, feedback_states, kiosk_rejection,
  app_row_observations, compose_observation_around_one_caller_input,
  open_a_customer_document_or_archive, fresh_desktop, package_command,
  give_repeated_public_operations_distinct_stages, parent_privacy,
  feedback_collection, attachment_preview
```

### Frozen public route names

The following extensions are **planned and unimplemented**. Current
`fixtures build` / `fixtures verify PATH` still select the legacy complete
builder through [test_commands](../../tools/test_commands.py); current
[vm_control](../../tests/integration/vm_control.py) has no fixture-sync action.
Registration, argument validation, help/listing, grants and applicable ownership
regressions must precede the first use. These names authorize no command now.

| Planned public surface | Finite meaning / owner |
| --- | --- |
| `tools/run-tests fixtures build --profile native-runtime --for-vm --vm NAME` | Resolve the registered target ABI and build the reviewed profile on the host. F02 owns construction/verification; F03/F04 add publication, reuse and bounded admission. |
| `tools/run-tests fixtures verify --bundle ID` | Verify one exact published immutable bundle; F03. Retain legacy `verify PATH` for existing consumers until migration. |
| `tools/run-tests fixtures inspect` | Read catalogue versions, occupied slots, bytes, pins and pending work without allocating a build; F04. |
| `tools/run-tests fixtures prune` | Apply the same bounded oldest-eligible retirement transaction; no arbitrary path, unpin or filesystem sweep; F04. |
| `tools/test-vm --vm NAME fixtures sync --profile native-runtime --bundle ID --subset SUBSET` | Pin an exact bundle before borrowing the caller's recorded running maintenance instance; refuse a foreign owner. Default refuses in-use payloads; explicit `--quiesce-owned` permits only recorded fixture owners/descendants. No implicit restore/reboot or service restart; F07/F08. |
| `tools/test-vm --vm NAME fixtures inspect` | Read the owned instance's generation/readiness and pin provenance without mutation; F07/F08. |

`NAME` is a current registry name/ID; only `onpc-Ubuntu26.04` and `onpc-Fedora44`
gain this plan's target qualification. `ID` names an exact host catalogue bundle,
never a supplied directory or guest destination. `SUBSET` is a finite declared
selection above, not an arbitrary file/command list. F51 freezes its request and
receipt encoding. `tools/fixture` remains exclusively the migration-plan launcher.

Planned engineering integration selectors are `check_fixture_provisioning`
(F05/F06), the seven `check_fixture_*` names in the consumer table below,
`check_fixture_clean_admission` (F48/F49), and `check_fixture_live_refresh`
(F07/F08). The seven clean repetitions use `check_fixture_clean_` followed by
the same envelope suffix. All run through `tools/run-tests integration --vm NAME`
only after registration/listing. They are preparation-only bindings, not new
customer scenarios, and require exact target evidence and normal owned cleanup.

## Identity and build publication

Build from a frozen host source closure through existing builders. Record source,
builder/toolchain, target OS/release/architecture, profile and dependency-contract
identities separately from the resulting bundle's exact content digest. Identical
compatible requests reuse a fully verified completed bundle. Source changes
during capture/build refuse publication. Package sources and fixtures keep
separate keys; a fixture-only edit must not trigger a product package rebuild.
A shared file that really is a product input still invalidates that product.
Use a maintained host-side target build environment for native artifacts and
record their runtime ABI requirements. Labelling a host binary with another
target name does not establish compatibility; no guest compiler is a fallback.

Use a versioned canonical manifest containing the complete finite file inventory,
relative source names, destination roles, sizes, checksums, executable modes,
symbolic owner roles and required trust/activation actions. Resolve actual guest
UID/GID values against the accepted account identity; never copy host UIDs. Bind
archive membership and manifest bytes to the bundle ID. Reject unsafe paths,
links, hardlinks, devices, duplicate entries, oversized/decompression payloads
and undeclared members before guest mutation. Do not execute archive-provided
installation scripts or accept arbitrary destinations/commands.

All host storage uses shared allocation/retention, with registration before the
first write. Reserve a build slot, build privately, verify fully, durably publish a completion receipt
and catalogue entry atomically, then expose the immutable bundle. A partial tree,
empty reservation or catalogue name is never readiness. Recovery resumes only
the recorded staging/publication identity and preserves the previous committed
catalogue, except for separately committed oldest-build retirement needed to
admit production. A failed build does not resurrect those retired inputs.
Share completed bundles across compatible VMs without giving two
journals deletion ownership of the same allocation.

### Cache ownership and execution sessions

One unprivileged authority per checkout owner creates, publishes, pins and retires
fixture bundles. Extend the shared storage allocator with an authenticated-caller
lookup, following `recordings_directory(caller_uid=..., create=False)`: a root
consumer derives the host cache from the dispatcher's authenticated caller and
validated checkout, never from a supplied UID, cache path or guest request. Root
opens existing caller-owned directories and immutable members read-only, with
pinned descriptors, exact ownership/mode/inode/mount checks and manifest readback.
It neither creates a second privileged cache nor writes the caller's catalogue.

The outer host controller builds/selects and durably pins before privileged
dispatch or VM acquisition. Its fixed request binds checkout, caller, host run,
pin, bundle and subset; the privileged controller records that request against
its exact VM/attempt journal before guest mutation. A root reader verifies this
binding and holds a shared version lease through consumption. Host supervision
forwards its pin-owner descriptors to owned descendants; no assumption is made
that `pkexec` forwards descriptors. A lost host leaves a durable pin until both
the host owner and recorded privileged attempt are reconciled. Root returns
cleanup evidence; only the host authority releases or recovers the durable pin.

Implement a fixture-cache transaction API over shared allocation, identity,
durability and deletion primitives. Do not use ordinary `Store.session()` or
`Store.publication()` unchanged: they implement run/export retention, and the
latter deliberately rejects an inherited `ONPC_TEST_RETENTION` token. The cache
API accepts an active execution session without replacing/clearing that token,
changing its journal, exporting its results or weakening that export refusal.
Its version catalogue is independent of the three-run evidence schema.

The producer lease serializes builders but does not hold the catalogue gate
while compiling or transferring. Short catalogue transactions admit/pin/commit/
retire; per-version reader leases protect consumption without blocking unrelated
cache hits. Prepare/pin before taking the VM lease. A consumer already holding
that lease may take only a nonblocking cache read gate for its existing pin;
it never builds or waits on a cache writer. Cache mutation never waits for a VM
or execution-owner lock. Stale-pin recovery reads candidate identities, releases
the cache gate, obtains normal owner/VM recovery proof, then rechecks unchanged
identities under the gate before release. No cache lock spans external recovery.

## Bounded cache and retention

Initial defaults: **6 build slots across the checkout's fixture cache and at
most 3 completed versions per profile/target compatibility key**. An unfinished,
failed or recovery-pending build occupies a slot too. There is one producer;
its scratch, staging and publication/rollback copies belong to its one recorded
slot. They never become separately retained build generations. The global
configured limit must be an integer from 1 through 9; the per-key limit must be
positive and no greater than the global limit. Neither limit can be disabled.
The key is a declared finite profile plus OS/release/architecture/dependency ABI,
not an arbitrary per-run label. Old compatibility keys count toward the global
cap. A cache hit creates no duplicate build or version. These defaults are a
proposed fixture-cache policy; ordinary result retention remains unchanged.
There is no fixture-cache byte quota, per-bundle byte ceiling, producer filesystem
quota or quota-specific setup prerequisite. Report actual allocated bytes for
inspection. Disk exhaustion fails the transaction, preserves committed inputs
and enters recorded cleanup; it grants no fallback storage or extra build slot.
Finite manifest membership, declared transfer lengths and safe extraction still
apply. A count limit bounds retained builds, not the size of an individual build.

### Initial working set and producer reservation

The initial reusable build profile is `native-runtime`, with one compatibility
key for Ubuntu 26.04/x86_64 and one for Fedora 44/x86_64 per dependency ABI. Its
host bundle contains the finite A/H/S/N, mechanical/catalogue and trusted hard/
soft/activity runtime inventory. Guest subsets select exact files from that
bundle; `native`, `riley-grid`, activity and engineering subsets are not separate
cache versions or keys. Scenario documents/attachments remain finite scenario
inputs at their existing checkpoints. Existing host-only Snap/Flatpak builder
coverage stays host-only; pending guest capabilities require a separate profile
review rather than silently enlarging this profile.

Six slots allow three completed versions for each current target while idle.
A cache miss at that occupancy first retires one eligible build and reserves
the released slot before the first producer write. Production therefore runs
with at most five retained completed versions plus one unfinished build, never
a seventh build. Two target consumers may continue using pinned versions while
the single producer works. If the necessary per-key/global eviction candidates
are all protected, the miss refuses before building. A cache hit needs no slot.
Old ABI keys count toward the same global limit. Unsupported architecture/profile
requests refuse before a build. F02 reports actual construction footprint; F04
proves this count-based two-target working set and refusal with injected limits.

F29 owns single-producer slot reservation and descendant lifetime in shared
storage/build support. Reuse scratch descriptor forwarding and recorded cleanup;
do not add a quota backend, mount sandbox or new setup mode for this policy.
Ordinary attempt inputs reference the pinned cache rather than copying full
fixture trees into each result allocation. Any necessary host transfer copy is
registered to the producer/consumer transaction until removed;
accepted reports retain manifests and identities, not another runnable cache.

Use one cache authority integrated with shared retention locks, identities and
safe deletion. Before a miss reserves a slot, automatically retire the oldest
eligible completed builds until both projected global occupancy and the requested
key's completed-version limit fit. Oldest means the smallest durable publication
sequence, with bundle ID as a deterministic tie-breaker; a cache hit does not
change that order. Inspect every applicable pin and acquire the version's
nonblocking exclusive retirement lease before recording deletion intent. No
cache gate is held waiting for a reader. Preserve unknown/replaced entries and
refuse admission rather than selecting deletion by path name or age.
One recorded producer transaction stages at a time; cache-hit readers and
different-VM consumers may proceed with leases. Do not multiply builds through
cumulative catalogues, hidden generations or per-attempt copies. Admission counts
staging, pending publication and recovery before writes; occupied slots never
exceed the global limit. A failed build must finish exact cleanup or continue
to occupy its slot before another build can start. Lowering a configured limit
automatically retires oldest eligible builds, or refuses while protected builds
prevent compliance; it never deletes a pin to force admission.

Active build/transfer/test/maintenance consumers acquire durable version pins
under the cache authority before obtaining a path. Pins identify their exact
owner and bundle and protect input until that owner finishes/reconciles cleanup.
Do not evict active or recovery-referenced bundles. Reclaim stale pins only after
shared owner/VM recovery proves release, never by age or PID/name alone. If
protected versions prevent admission or a lower configured limit, refuse new
builds with an explanation; preserve existing inputs and never exceed caps by
silently ignoring them. Deletion/interruption failures block admission until
identity-bound recovery completes. Unknown/replaced allocations are preserved.

Completed historical reports record exact IDs/manifests and results but do not
pin every runnable build forever. Required accepted proof uses the existing
verified evidence publication; deleting cache entries cannot delete that proof.
Result-export refusal during an active test owner remains governed by the
existing evidence contract; cache publication/pins grant no result-export lock
bypass and do not require exporting running tests before fixtures can be used.
Reproduction of an evicted version rebuilds from an available exact source and
toolchain closure and rechecks its digest, or reports unavailable inputs. Never
replace it with the newest version under the old ID. Inspection lists versions,
bytes, pins, pending work and retirement reasons without allocating a build;
prune uses the same authority, not a filesystem sweep. Finite configurable limits
may tighten/adjust these defaults but cannot disable bounds.

## Owned SSH provisioning and readiness

The host selects and pushes an exact pinned bundle through the existing owned
SSH transport. No guest polling, host artifact server, live host mount or guest
download credential. Borrow an existing attempt/maintenance lease; public
maintenance refuses a foreign owner instead of acquiring/adopting its instance.
Use shared watch and intention-before-action for transfer, activation and waits.

A fixed guest helper preflights the entire selected destination set, accepted
environment compatibility, account roles and owned prior receipt. Transfer into
private staging with declared size bounds, verify bytes/metadata, and update only
proven owned outputs. Preserve unrelated files and refuse collisions, symlink
ancestors, mounts and substituted identities. Journal distributed file updates
before replacement; while anything is pending, readiness is unavailable. Publish
the final receipt only after complete independent readback and required runtime
activation. A lost reply leads to read-only transaction reconciliation, not a
blind repeat of uncertain mutation. Interrupted cleanup is identity-bound.

Trust-sensitive native files retain exact finite admission and intentionally
untrusted controls. Reuse/extract baseline trust reconciliation rather than
adding directory-wide trust or altering product policy. Verify loaded trust and
rule freshness after supported scoped activation; a filesystem receipt alone
cannot claim runtime readiness. Keep Fedora SELinux enforcing and label new
owned outputs correctly. Dependency/configuration changes that require another
baseline or restart report that requirement before mutation; no implicit reboot,
snapshot operation, OS-package install or product reinstall during a sync.

Readiness binds bundle/subset, dependency ABI, baseline provenance, provisioning
helper version, receipt generation, VM UUID and current boot/attempt identity.
After every restore/reboot, establish a fresh bound receipt; old saved receipts
are not current readiness. Guest payload lifetime is the owned attempt or
maintenance instance, with recorded guest cleanup/baseline restoration. Bound
guest storage to the selected active payload and one recorded staging/rollback
transaction; release obsolete owned generations after successful activation.
No guest build archive/history cache is introduced.

### Profile contraction and activation transaction

The destination set is the union of the prior owned receipt and requested subset,
not just the new manifest. Classify unchanged, added, replaced and removed files,
launchers and exact native admissions before writing. The old baseline reconciler's
`previous.files <= desired` rule is not sufficient for this operation. Verify
every removal against its recorded bytes, metadata and filesystem identity;
foreign, modified, linked or mounted outputs refuse the whole update before
mutation. Keep unrelated files and shared runtime members still required by the
new closure.

F33 imports the **complete legacy movable set**, including unrequested payloads,
into one migration transaction before selecting the first subset. Verify the
accepted baseline/capture, original preparation marker and recognized fixture/
trust records together; a caller-supplied digest or matching file bytes cannot
establish ownership. Classify every old receipt member as movable runtime,
environment dependency or scenario-owned state using the original declaration.
The transaction owns retirement of all old movable members outside the request;
it leaves account, desktop-renamer, automatic-update and other environmental
settings with baseline ownership. No unselected movable file remains outside
both the new receipt and the retirement journal. Preserve symbolic owner roles
and current accepted UID/GID values; do not change fixture ownership merely to
simplify the migration.

The same inventory covers `/var/lib/onpc-baseline-preparation/checkout`, which
the current preparation route leaves behind. Treat its source copies as data:
verify their original finite names/bytes against the accepted preparation source
closure before removing fixture sources/builders. Never execute that checkout.
Delete only recorded matching files and subsequently empty owned directories;
unknown files, changed bytes, links or mounts refuse the cleanup. Preserve
environment/recovery records. F11/F12 change the preparation writer together with
the dependency-digest split: new preparation stages only required environment
modules and capture rejects old movable source copies, including archived copies.
F33 supplies the inventory/removal API; it must not remove staged inputs still
needed by the legacy guest preparation digest or change its writer early.
F24 preserves original baseline/fixture decoding; F30 preserves snapshot/owner
decoding; F33 owns this import/removal algorithm before F15 composes provisioning.

Journal bounded rollback identities for the complete set, then replace/remove
under the launch barrier below. Reconcile trust to the exact new set, prove that
removed inputs are absent from loaded admission, and independently read all new
outputs and removed destinations. Publish the new generation only after that
verification. Finish recorded rollback retirement before another update; an
interruption remains unavailable and resumes its exact transaction. A larger to
smaller to disjoint subset history on each target must leave only the requested
payload, with no old launcher or trust admission and no unrelated data loss.

## Live refresh and recorded attempts

In an explicitly owned maintenance instance, build/select a new host version,
stage and verify its selected closure, then rerun the affected diagnostic without
restore, snapshot replacement or reboot for ordinary payload-only changes.
Unchanged sync does no fixture writes. In-use executables/runtime files require
an explicit quiescent boundary: stop/restart only recorded fixture processes or
refuse with their required release. Do not kill by name or restart product/desktop
services as an incidental fixture refresh. Preserve unrelated guest/session data.
Diagnostic refresh records both generations and supplies no acceptance credit.

### Quiescence and launch barrier

Host scheduling closes new fixture actions for the owned attempt. Before checking
processes or replacing/removing any payload, install a separate, journaled,
fixture-only native deny barrier over the union of old/new executable and
interpreted-runtime paths for every declared non-root fixture account. Generate
only fixed finite rules through the supported native compile/reload interfaces;
do not edit product policy or restart its services. Independently prove the
loaded barrier blocks fresh fixture launches and runtime opens before mutation.
Root fixture launches belong exclusively to the closed host action scheduler;
the fixed root provisioner retains readback access. If either barrier or ownership
cannot be proven, refuse live mutation and require normal owned restoration.

Inspect executable/mapping and descendant identities using the current boot,
UID, PID/start identity and pinned process handles. An active or unknown user of
the old closure causes refusal. Explicit quiescence may stop only recorded
fixture owners and their proven descendants, wait for actual exit, and recheck
the entire set while the barrier remains active. This includes the C GUI owner
and its Python child, already-open runtime files and fork/relaunch races; a PID
or executable-name scan alone is insufficient. No product/desktop process is
stopped. A barrier denial is harness state, never a product enforcement result.

Keep the barrier through placement, removal, trust activation and readback. The
durable journal records payload verification before requesting barrier removal;
readiness is withheld until the finite barrier-removal and payload/trust witnesses
below pass. They establish fixture readiness, not a complete arbitrary native
policy generation. Lost replies reconcile these recorded phases without
replaying an uncertain launch or signal. Failure preserves unavailable readiness
and the owned barrier for exact recovery; no new scenario input is admitted.
Cleanup restores the recorded baseline and releases the barrier/pins only after
that recovery is proven. F31 owns native barriers/activation witnesses, F32 owns
process/descendant quiescence and F15 composes these with transactional placement.
F05/F06 qualify the complete boundary before production runner integration.

### Fixture-only native acknowledgement protocol

Use rule-attributed, per-operation witnesses for this finite fixture set, rather
than infer a complete daemon generation from a marker. The
[existing native acknowledgement limits](../SystemDesign/Applications.md#notification-recovery-and-acknowledgement-limit)
remain applicable. This protocol is a proposed fixture implementation with
mandatory target qualification, not a delivered product-policy witness.
The supported native [rule decisions](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/doc/fapolicyd.rules.5)
and [notification interfaces](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/doc/fapolicyd-cli.8)
supply the building blocks; neither command success nor a disk listing is acknowledgement.

F31 implements a separate finite fragment with `deny_syslog` for every declared
non-root fixture UID and old/new executable/runtime content identity. Prefer
representable exact paths plus hashes; for whitespace/comma paths use the finite
hash identity, documenting that identical fixture copies for those UIDs are
also blocked. Never broaden a rule to an unrelated directory. Include both
`execute` and `open` coverage; root readback is outside the deny subjects. F51
records exact fragment ordering against the recognized native rule inventory.
Unknown precedence, unsupported syntax or missing decision-log fields refuses
before any fixture mutation; missing logging prerequisites use normal baseline
preparation, not a daemon restart or configuration repair inside sync.

For each transition journal a fresh transaction nonce, phase, expected rule map,
compiled-input digest, trust-fragment digest and daemon package/executable,
boot, PID/start and service InvocationID. Capture a journal cursor before probes.
Use supervised single-use tracees with recorded PID/start/cgroup and immutable
input identities. Drop to the selected UID and execute the fixed native probe
from a pinned descriptor at a fresh root-private nonce pathname using the
supported descriptor-exec interface; keep its executable identity through the open/exec syscall being
tested. Small probe-specific `allow_syslog` observers match that unique `exe`
pathname, retained tracee PID/UID and exact input; place them after the barrier
and before ordinary native policy. The probe cannot run arbitrary commands or
expose its descriptor to other processes. They never authorize a scenario
process. A positive
nonce witness must return its expected bytes through an independently read pipe
and have the matching attributed allow decision. For every barrier rule class,
UID and permission require its attributed deny decision **and** actual syscall
refusal/no executed witness. A generic failure, another rule's denial, queue
overflow, missing/stale log or permissive daemon cannot satisfy that pair.

Hold the fixture barrier through trust changes. Before unlinking a retiring
trusted file, remove only its exact owned admission and use an exact root tracee
open to require an attributed `trust=0` decision at its still-present original
path. Require `trust=1` for each new trusted path and `trust=0` for intentional
untrusted controls, alongside exact trust-database/fragment readback. Retain
hash-based Fedora admission only for content identities still required by the
new closure; retiring a pathname does not revoke a digest needed by a surviving
identical runtime copy. Remove obsolete digest rules, then prove file absence.

After payload/trust verification, remove the deny fragment, compile/notify and
repeat fresh tracees: every surviving permission/UID class must reach its
probe-specific observer with actual open/execution success; a stale barrier
would deny it first. Require a fresh positive nonce witness as well. Removed
paths must be absent and no longer occur in fixture admission sources; no
arbitrary-policy-generation claim follows from these checks. Settle all tracees
and descendants, close their executable descriptors, prove the nonce executable
has no live mapping and remove its exact private file. Then remove observer
sources and record the final verified fixture fragment map before publishing
readiness. A delayed observer removal cannot authorize a reused PID: its required
unique executable is no longer runnable or mapped. No stale private observer
is treated as proof of a complete loaded ruleset. Verify daemon identity,
compiled inputs and all
non-fixture rule bytes before/after each phase; an external reload, rule change,
daemon restart, partial parse, unmatched decision or uncertain probe retains
unavailable readiness and exact recovery. An unchanged reload of the same
verified fragments cannot relax their barrier. Lost replies read the durable
probe/phase receipts; they never repeat an uncertain exec or signal. A settled
probe may be replaced by a fresh read-only verification with a new identity.

F32 retains process handles before admitting any tracee or fixture action and
tracks descendants through an owned cgroup plus pinned PID/start identities;
name/argv/parent scans alone confer no ownership. The fixed guest supervisor
uses the existing owned-command/systemd lifecycle primitives, with startup,
execution and stop deadlines and recorded ambiguous-start recovery. Direct
untracked fixture launches block live mutation; do not adopt their processes.
An untracked interpreter whose relationship to the old runtime cannot be proven
also refuses refresh. Qualification must cover the C/Python pair, inherited
descriptors/mappings, forks, escaped/reparented children and PID reuse. A failure
to establish this finite native proof on a supported backend blocks activation
of that backend's live-update route; restoration remains the safe recovery.

Recorded tests resolve and pin one immutable bundle/subset before provisioning
and scenario input. Never resolve `latest` again mid-attempt or repair an input
after an assertion has failed. A changed fixture requires a fresh attempt and
new provenance; a long-lived guest may be reused only where the owning test
contract already permits a fresh independent attempt. Expected versus actual
product behavior remains strict. Shared cases verify readiness rather than
installing prerequisites; the outer common attempt envelope owns provisioning.

## Runner and snapshot migration

Extend the existing `tools/run-tests fixtures` builder/inspection route and
owned `tools/test-vm` maintenance interface; exact new options and registered
qualification selectors are frozen by F01 and remain unimplemented until their
own tasks deliver them. `tools/fixture` remains the plan launcher. Use the same
library from system/E2E/qualification envelopes, not independent case installers.
Stop safely on unavailable prerequisites or grants; never bypass a guard by
falling back to an embedded snapshot payload or another VM's bundle.

Separate baseline dependency/provisioning ABI from fixture-only source/content
identity. App snapshots remain bound to actual installed product, baseline and
install recipe; their capture path excludes movable fixture payloads. Provision
after restoration/transport readiness and before scenario entry. Audit prepare-vm,
standalone app preparation, system, E2E, qualification/named inputs and maintenance
consumers, including paths that currently derive fixtures from package bundles.
Future baseline preparation verifies dependencies without compiling movable
fixtures. Capture rejects leaked movable payloads/pending transactions.

### Runner acceptance matrix

Every row is qualified independently on both canonical targets. F01 freezes an
exact registered consumer/selector and required subset for each row; a planned
selector must be implemented/listed before use. A source alias may share delivery
only when host composition tests prove it calls the same preparation branch with
the same lifetime/guards. Different restore or provisioning branches require
their own row and bounded prerequisite, not inferred qualification.

| Envelope | Existing boundary to migrate | Planned selector suffix / engineering subset | Initial Ubuntu / Fedora tasks | Clean-schema Ubuntu / Fedora tasks |
| --- | --- | --- | --- | --- |
| Product-free system | `system_snapshots._run_attempts(installed=False)` and `system_runner.installed_run(already_installed=False)` before installation input; finite `FIRST_CONFIGURE_PHASES` metadata with no installed precondition | `system_product_free` / trusted-native, hard only | F09 / F10 | F34 / F41 |
| Installed system | `_run_attempts(installed=True)` and `Suite.prepare_case`; current Suite default is **online**, while F16/F17 require an explicit **offline** preparation binding; `enforcement` phase and `installed-digest-verified-product` precondition | `system_installed` / trusted-native, hard only | F16 / F17 | F35 / F42 |
| Installed E2E | `InstalledJourney` setup, default **online** snapshot credential rebind and `AssetTransfer.provision_installed`; qualification wrappers also have explicit offline restore | `e2e_installed` / native | F18 / F19 | F36 / F43 |
| Product-free graphical E2E | `InstalledJourney.product_free`, package/upgrade preparation before customer input; GDM-only has no movable input; dormant current-install guard stays host-only | `e2e_product_free` / native for asset-bearing branches, empty for GDM-only | F20 / F21 | F37 / F44 |
| Standalone transfer qualification | `runner --qualify-transfer` → `Qualification.execute` → `AssetTransfer.provision` before boot; move fixture bytes to owned SSH after transport readiness | `transfer` / native | F22 / F23 | F38 / F45 |
| Standalone serial qualification | `Qualification.execute` with a serial `Smoke` worker, `check_graphical_serial`, `runner --qualify-install` and `--qualify-install-refusal` | `serial` / native | F25 / F26 | F39 / F46 |
| Recorded serial E2E harness | `controller_qualification.E2E_CASES['gdm-observation']` → `serial_harness.record_serial_journey` under `execution.ScenarioContext` / recorder ownership | `recorded_serial` / native | F27 / F28 | F40 / F47 |

Suffixes above form the exact planned `check_fixture_SUFFIX` and
`check_fixture_clean_SUFFIX` selectors. For the headless system witness, select
only `/opt/onpc-test-fixtures-trusted-hard/native-fixture` with its exact native
trust admission, independently read its digest, run it without arguments over
owned SSH as the accepted `child` (Riley) account, and require exactly
`ONPC_TEST_APPLICATION_READY` plus exit 0. No desktop file is needed. For native,
independently read A and its two adjacent runtime members, execute selected A
with `--stay-alive` as that same child account (matching Fedora's finite UID
admissions), require the same marker, then send SIGTERM only to its recorded
supervised process and require exit 0. This fixed mode in
[onpc_test_application.c](../../tests/fixtures/onpc_test_application.c) opens no
GUI and changes no product state. Readback must match the pinned manifest;
neither a marker alone nor receipt presence proves selected bytes. GDM-only
proves an empty closure and unchanged product-free entry, not a native witness.
Activity/trusted-native and contraction/trust witnesses remain additional
F05/F06 provisioning obligations, under F50's activation protocol.

### Source-backed consumer and alias disposition

The map is defined by actual dispatch, not selector spelling:

- [system_snapshots.attempts](../../tests/integration/system_snapshots.py)
  partitions lifecycle/removal histories by `history.start`, first-configure and
  PAM histories as product-free, independent authorization/enforcement/session
  as installed, and isolated trusted-fixture qualification as product-free.
  `fresh_install=True` places its grouped phases in the product-free branch.
  F09/F10 and F16/F17 preserve all these predicates and the trusted history's
  real previous-package requirement; a narrow engineering witness stops before
  any phase/product assertion.
- [suite_lease.needs_installed](../../tests/e2e/suite_lease.py) and
  [execution.attempt](../../tests/e2e/execution.py) route registered
  [scenario declarations](../../tests/e2e/scenarios.json) to installed E2E or
  product-free entry. The installed default is online, including the Suite
  constructed by `system_snapshots.create_suite`; current system code does not
  explicitly select offline. F16/F17 must establish and prove their required
  offline binding, rather than assuming that the default already supplies it.
  This is an implementation obligation, not offline acceptance credit.
  [InstalledJourney](../../tests/e2e/installed_journey.py) establishes
  transport, calls `InstalledSetup.provision`, then optional
  `AssetTransfer.provision_installed` before `plan.stage_actions`. F18/F19 and
  F20/F21 own these respective branches, preserving every stage action.
- Among integration wrappers calling
  [check_graphical_smoke.main](../../tests/integration/check_graphical_smoke.py)
  directly or as `smoke`, evaluate each finite literal/loop option alternative
  through its **ordered** `qualification_class` assignments. Exactly those
  whose final class is `KioskEntryQualification` or a transitive subclass in
  [parent_setup_qualification.py](../../tests/integration/parent_setup_qualification.py)
  belong to installed E2E. This dispatch predicate includes every such wrapper
  and loop alternative; it does not merge separate attempts. Its inherited
  `attach_installed_snapshot` sets `online_pending` for online, and explicitly
  restores offline otherwise. F18/F19 composition tests and preparation proof
  must cover both alternatives; one cannot stand in for the other.
- The exact product-free smoke-dispatch exceptions are
  `check_e2e_gdm_product_free`, `check_e2e_product_free_entry`,
  `check_e2e_upgrade_assets`, `check_e2e_chinese_language_assets`,
  `check_e2e_desktop_language`, `check_e2e_package_authority`,
  `check_e2e_package_command`, `check_e2e_customer_reboot`,
  `check_e2e_restart_notice`, `check_e2e_unrelated_reboot_request`,
  `check_e2e_package_upgrade`, `check_e2e_chinese_kiosk_lifecycle` and
  `check_e2e_chinese_current_install`. `GdmProductFreeQualification` has no asset
  transfer; `ProductFreeEntryQualification` subclasses and recorded
  package/Chinese/lifecycle journeys retain their existing offline asset setup
  checkpoint until F20/F21 moves fixture transfer. No package or reboot assertion
  changes.
- `check_parent_setup`, `check_parent_input`, `check_parent_standard_input` use
  `ParentSetupQualification.execute`'s separate baseline/bootstrap branch.
  F09/F10 (clean F34/F41) factor/prove the same product-free-system readiness
  boundary after `Transport.probe_ready`, before `InstalledSetup.run` installs
  anything. Host composition must explicitly bind all three aliases; installed
  snapshot proof does not cover them.
- `check_parent_about` and `check_parent_access` currently reach
  `ParentJourneyQualification` without a setter satisfying the installed guard.
  `InstalledJourney.install_current_package` likewise has no current producer.
  Preserve these dormant guard branches with host coverage; F20/F21 must not
  enable them or claim live fixture acceptance for them.
- [runner](../../tests/e2e/runner.py)'s `--qualify-transfer` calls smoke with
  assets; `--qualify-install` adds credentials, serial and install;
  `--qualify-install-refusal` adds serial and install-refusal.
  [check_graphical_serial](../../tests/integration/check_graphical_serial.py)
  calls `main(provision_credentials=True, serial=True)`. F22/F23 own transfer;
  F25/F26 own serial/authenticated alternatives, retaining successful-install
  reboot versus refused-install logout/no-reboot assertions.
- [serial_harness](../../tests/e2e/serial_harness.py)'s recorded branch stages
  credentials, stock getty and offline assets before
  `Smoke(authenticate=True, serial=True, functional=True)`. F27/F28 preserve its
  HAR09/HAR10 recorder/stage completion, durable observations before replies,
  boot continuity, logout/session absence and worker shutdown checkpoints.
- `check_graphical_credentials`, `check_graphical_vt6_prompt`,
  `check_graphical_vt6_authentication` and bare `check_graphical_smoke` are
  baseline credential/display/getty consumers with no native fixture closure.
  F11/F12 retain their dependency-only guard. `check_graphical_attachment` is VM
  diagnosis without reusable fixture payload. `check_graphical_transport` and
  `check_graphical_worker` remain host mechanics/doubles. Recovery, storage and
  `check_e2e_watch` retain their own owners, without fixture-envelope credit.
- [app_snapshot.prepare](../../tests/e2e/app_snapshot.py) and standalone
  [prepare_appsnapshot](../../tools/prepare_appsnapshot.py) are preparation
  producers, not extra envelope aliases: the library defaults offline, whereas
  Suite and the standalone tool explicitly request online, with
  install/verification/reboot and credential publication. F11/F12
  exclude movable outputs at capture while retaining exact product/recipe and
  original-schema recovery; F30 preserves ownership/credential decoding.
- [vm_control](../../tests/integration/vm_control.py) diagnostic/reproduction
  actions reuse the named journey's actual branch and keep their maintenance
  lease, transport and cleanup. F07/F08 bind their fixture use to an explicit
  immutable pin; their results remain diagnostic. `NativeFixtures` profiles
  `native`, `riley-grid`, `activity` select the closures above; `chinese` verifies
  environment language prerequisites and selects no movable bytes.

For every asset-bearing branch,
[AssetTransfer](../../tests/e2e/asset_transfer.py) retains one-shot
attempt/phase identity, collision/replay refusal, independent post-boot inventory
readback and upgrade account/locale/unrelated-file witnesses. Native
`fixture_actions` retain wrong-entry/refusal timing. Recorded `stage_actions`,
attachment/document changes and launcher/version mutations remain scenario
checkpoints; readiness cannot preseed them. Host alias composition tests must
enumerate actual dispatch alternatives and named-input declarations, including
empty/dormant branches, before the owning task claims the map implemented.

These are preparation-only engineering bindings. Each calls the real shared
envelope through fixture readiness, independently executes/reads a harmless
fixture witness, and performs ordinary owned cleanup before any product action
or assertion. Host composition tests prove real consumer routing. No customer
journey, package install/update assertion, policy/grant action or product outcome
is part of this migration's acceptance. Existing installed product/snapshot
identities are preparation provenance only; their normal preparation route may
establish that starting state separately. Fixture failure injection stays in
engineering coverage and supplies no customer acceptance or E2E completion.

Across each row prove positive use of its selected bytes, missing/incompatible
failure before input, unchanged product-free entry where applicable, a fresh
boot/attempt receipt, one immutable pin through the attempt and complete cleanup.
Register host branch tests for all aliases, reboot boundaries and named-input
declarations. A standalone installed qualifier reuses a row's proof only with
that exact branch mapping; it cannot inherit merely from an E2E feature pass.
Until its row passes, a consumer keeps its explicit legacy preparation gate.
The snapshot cutover has two gates. F09 through F28 first qualify all seven
integration branches on both targets under the existing baseline contract.
F11/F12 then establish clean snapshots **with ordinary new-schema dispatch still
disabled**. F34–F40 (Ubuntu) and F41–F47 (Fedora) repeat the seven real preparation
paths against those clean snapshots, one envelope per task. These checks use
only fixed registered engineering selectors under normal leases/guards; they
provide no general bypass for ordinary consumers. Earlier fixture-bearing proof
cannot satisfy a clean-schema row.

F48/F49 enable ordinary new-schema dispatch for their target only after all
seven matching clean-schema rows pass. They publish a root-owned qualification
receipt bound to the clean-capture schema, dependency ABI, native backend,
provisioner, envelope source identities, selectors and owned-cleanup results.
Each row retains its exact baseline/app capture provenance. Runtime independently
validates the current capture against that qualified environment/recipe contract;
offline and online app captures need not coexist under one snapshot name.
Same-contract capture renewal or a different product package is provenance, not
a request to repeat product checks or certify fixture readiness for a new ABI.
Runtime admission checks the receipt; changed fixture-relevant inputs invalidate it and keep the route
disabled until its affected preparation checks pass again. The qualification
receipt is control metadata in the existing VM state, not a mutable source flag
or a new fixture cache. Its publication changes no tested implementation inputs.
Each enable task verifies ordinary dispatch/readiness/cleanup after publication.
F13 audits these completed gates; it is not the first point at which clean-schema
coverage becomes mandatory. Shared changes renew affected other-target rows
before that target can remain enabled. F07/F08 wait for both target gates.

Use explicit schema migration and accepted provenance for legacy snapshots and
receipts. One separately authorized baseline/app refresh per target may establish
the new clean snapshot contract; never conceal it as live sync or modify a saved
snapshot in place. Keep recorded legacy recovery/restoration functional using
its original contract. After cutover, demonstrate a fixture-only source change,
host rebuild and live use with unchanged baseline/app snapshot identities and
boot ID. Real product/dependency/ABI changes still invalidate their own caches.

### Legacy recovery compatibility

F24 and F30 install version-dispatched read-only codecs before guest-reader/writer
migration or either snapshot cutover. Every later task preserves those routes.
Freeze the following existing formats and their currently accepted variants;
new attempts use new schemas, while recovery uses the accepted original inputs.

| Legacy input | Accepted identity and recovery treatment |
| --- | --- |
| Guest preparation marker | Ubuntu schema 2 / Fedora schema 3; verify the exact marker digest bound by the accepted capture, original dependency inventory, accounts, OS and preparation digest, rather than comparing it to a newly changed dependency declaration |
| Baseline capture | `phase.json` schema 2, original source/directory/operation/proof/script digest; preserve the existing finalized baseline and interrupted preparation recovery routes |
| Baseline fixture receipt | `onpc-reusable-fixtures-v1`, exact recorded file set and `pending` shape; completed receipts support read-only restoration; pending placement remains with the original owned preparation transaction |
| Native trust/backend | `onpc-trusted-native-fixtures-v1` original hard/soft set, recognized activity/backend/metadata extensions, and `onpc-native-file-backend-v1`; preserve existing root-group and absent-Fedora-admission recovery exceptions only under their original byte/metadata/provenance guards |
| App snapshot metadata | Schemas 1 and 2 with existing exact-archive/content-equivalence rules; legacy payload-bearing snapshots are recovery inputs, not new clean captures |
| Online credentials and maintenance SSH | Their schema 1 private records, exact saved XML fingerprint, run, keys and VM identity; no new credential adoption |
| Execution/maintenance ownership | System journal schema 1 and the existing exact `vm-control.json` shape; retain only currently supported phases, instance checks, stop/restoration and explicit `recover-online` startup-gap handling |

Codec selection requires recognized shape/purpose and root-owned accepted
provenance; a recorded arbitrary digest alone grants no new schema or ownership.
Preserve the original accepted dependency inventory, finite fixture declaration
and raw preparation/fixture/trust records in a root-owned versioned recovery
sidecar bound to the capture/baseline identity, before dropping their declarations.
Keep it with the existing VM recovery owner until all referencing owners finish;
ordinary cache eviction cannot retire it. A legacy owner without a sidecar may
use only a recognized original decoder and proof from its accepted snapshot;
missing original proof refuses rather than substituting current declarations.
Never execute archived checkout code to recover, regenerate
missing proof or reinterpret an old receipt as new readiness. Unknown variants
preserve their journal and report the exact unsupported input.

Test pre/post-write and lost-reply phases for current recovery, original-schema
stop/restore after source changes, recognized older native-trust variants and
foreign/replaced-record refusal. Existing unsupported interruption phases retain
their refusal and documented explicit recovery; this migration does not adopt
them. Complete old VM/preparation owners before the separate schema-establishing
auto refresh. New baseline markers separate environment dependency ABI from
fixture content; new app metadata includes that schema/ABI plus actual installed
product/recipe identities. Old receipts never satisfy a new attempt's readiness.
Clean capture audits active, archived `onpc-system-input-snapshot-*`, E2E asset,
fixture, trust, staging, barrier and the retained baseline-preparation checkout
locations; renaming a payload is not removal.

## Acceptance and ownership handoff

F01 review accepted the placement, original-source and consumer maps above.
Source review corrected the pattern subset's required unrelated control,
Fedora admission ownership, the actual online Suite default versus F16/F17's
planned offline binding, standalone online preparation and the serial execution
owner. Witnesses specify exact bytes, account and supervised termination.
Markdown links and plan structure passed; the maintained consistency and
side-effect-free adapter selection passed
[321 host checks](../../output/test-runs/host/reports/20261022T035137Z-f77c5cbd/report.md).
Both read-only helpers finished; no VM, build, setup or product/runtime operation
was performed and no owned live resources remain. This is F01 review evidence,
not F51 schema completion, F52 independent review or installed qualification.

Qualify Ubuntu 26.04 and Fedora 44 independently: first stage, repeat/no writes,
version update, corrupt/missing inputs, interrupted transaction/retry, foreign
owner refusal, exact native trust and untrusted controls, and owned cleanup.
Exercise build-count pressure, disk-full refusal, active pin protection, producer/consumer races and
interrupted retirement at host scope with private fixtures before protected live
work. Preserve independent assertions and process ownership in test doubles.

At each delivered boundary update its existing owner: VM/approval/environment
for prerequisite lifetime; test storage/retention for cache limits and pins;
support/runner guides for shared APIs; fixture/asset provenance and snapshot guides
for version/ABI coupling. The execution queue records delivered proof; this
target design does not become a competing operational policy document.
