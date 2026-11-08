# Shared test support

Start here before adding fixture code. These are opt-in helpers on top of
pytest, unittest, Hypothesis, Gio, Dogtail and the existing language runners.
Tests own scenarios and assertions; helpers own repeated setup, transport and
cleanup. Helpers and test cases must not import collected case modules; keep
reusable mechanics in support modules.

Temporary storage follows the
[test storage mandate](../../docs/Mandates/Test-Storage-Mandate.md): use the
shared allocation helpers, never a producer-selected `/tmp` or custom root.

## Find an existing helper

| Need | Reuse | Contract |
| --- | --- | --- |
| Temporary storage and retained evidence | [test_storage.py](../../tools/test_storage.py), [test_retention.py](../../tools/test_retention.py) | Launchers configure disk scratch for pytest fixtures. Retained evidence uses a registered allocation in its owning journal; short sockets use `short_runtime` or `runtime_directory`. |
| Fixture producer lifetime | [fixture_producer.py](../../tools/fixture_producer.py) | `Store.producer(transaction_id=..., compatibility_key=..., build_key=...)` owns one unfinished slot. Allocate scratch/staging before writes, pass `Producer.environment()` to build commands and forward `scratch_descriptors()` through every subprocess layer. `Producer.verifying()` records the verification phase. Context exit cleans only recorded allocations after every descendant lease closes; failed cleanup requires exact `Store.recover(transaction_id)` before another reservation. |
| Immutable native fixture construction | [fixture_bundle.py](../../tools/fixture_bundle.py), [fixture_manifest.py](../../tools/fixture_manifest.py) | Use the [frozen bundle contract](#frozen-native-fixture-bundles). Full fixture/package callers retain their separate input contracts. |
| Attempt-owned SSH fixture provisioning | [fixture_provision.py](../../tools/fixture_provision.py) | Use the [provisioning boundary](#attempt-owned-fixture-provisioning). Runner dispatch remains unavailable until target qualification. |
| Guest fixture file receipts and bounded I/O | [guest_files.py](../e2e/guest_files.py) | Fixture provisioning, native readiness and synthetic file operations share `identity`, `read_regular` and `write_exclusive`. Callers keep finite paths, owner/mode/size expectations, exact-content assertions and cleanup receipts; do not copy descriptor/read loops into another suite. |
| Checkout paths and script imports | [paths.py](paths.py), [modules.py](modules.py) | Normal imports use `pyproject.toml`'s `pythonpath`. `load_module(name, path)` loads a fresh standalone script with a unique test-only name; failures restore the registry. |
| Broker configuration and recording adapters | [configuration.py](configuration.py), [broker.py](broker.py) | Fresh mutable state, explicit clocks/callbacks/failures and no OS calls. |
| Unit orchestration without GTK construction | [objects.py](objects.py) | Bind actual class methods to explicit state instead of copying method source. |
| Private D-Bus broker | [dbus.py](dbus.py) | Import `private_service` and call/wait helpers; real Gio serialization on the component suite's private buses, with recording adapters. |
| Preview process lifecycle | [preview.py](preview.py) | `preview_applications` owns only its Popen handles/logs, enables Python's fault handler before startup imports, cleans up failed discovery, attempts every owned child and reports cleanup failures. Fatal Python/native signals leave Python thread tracebacks in the existing preview log; Python 3.14 also emits the current native stack when supported by the runtime build. `tests/ui/conftest.py` owns the compositor, accessibility and `request_display_scale` fixtures; layout/overflow tests discover scaling there instead of importing a collected case. |
| Preview event observations | [events.py](events.py) | `read_events` returns complete JSON-lines records, waits for an unfinished final line, and refuses corrupt complete records. |
| Update-required dialog | [update_required.py](update_required.py) | Parent and request previews replace only the reboot transport with a recording refusal; public modal/buttons remain real and the host is never rebooted. |
| Product UI ownership, inventory and operations | [application_ui.py](application_ui.py), [automation.py](automation.py), [accessible_ui.py](../e2e/accessible_ui.py) | Host previews and installed E2E share the Application UI API facade, owner/PID pins, scoped inventory/node projection, canonical setters and ordinary actions. Cases own finite inputs and independent outcomes. Complete observations expire before input, retries and observer resets; missing/ambiguous owners and unavailable controls refuse. |
| External GUI providers | [public_atspi.py](../e2e/public_atspi.py), [accessible_ui.py](../e2e/accessible_ui.py) | Authentication, real file choosers and supporting desktop tools retain qualified public provider observations/actions and secret-recipient guards. Product controls never fall back to this route after an API refusal. |
| Maintainer-script machines | [package_scripts.py](package_scripts.py), [shell.py](shell.py) | `package_machine` and `Machine` execute real scripts against temporary files and explicit command doubles. `use_real_state_migration` replaces only the migration double with the production state pass under the fixture UID and private paths. `prepared_lifecycle_machine` supplies finite historical PAM/state inputs to the selected lifecycle migration with private ownership, account and policy-tool doubles; it imports no retired confinement implementation. `Machine` binds Ubuntu/Fedora OS, hook, service and account adapters; `run_rpm` executes embedded erase callbacks and the installed abort-remove callback in an isolated shell. Removal/purge cases own their distro/action matrix; Debian package notices and PAM-selection cases stay Ubuntu-only. Path relocation alone is not a sandbox. |
| Trust database concurrency | [trust_database.py](trust_database.py) | `replace_records` commits empty/refilled generations in a pytest-private LMDB database. Its optional `after_refresh` callback runs between committed generations while the writer environment stays open. `live_database` keeps a separate writer process alive through reader assertions, as with the daemon, and bounds startup/cleanup waits. Tests own records and interleavings; bounded, waited reader/writer children exercise production read snapshots without accessing the host trust database. Requires the distribution's liblmdb runtime. |
| Terminal and pipe capture | [terminal.py](terminal.py) | `capture` drains output while the child runs, bounds execution and signals only its owned Popen handle. Return codes and terminal color behavior are retained. |
| Graphical Perl helper probes | [perl.py](perl.py) | `run_perl` supplies the maintained library path, captured streams and a deadline. `run_password_guard` shares scoped proof recording and a secret-free delivery sink around the real credential guard in a fresh process. Tests keep finite bindings, order and assertions locally; do not import runnable customer plans merely to obtain guard inputs. Other probes declare their public testapi doubles and assert secret exclusion. |
| Real needle pixel matching | [needle_matcher.py](needle_matcher.py) | `match_image` reuses the installed os-autoinst matcher for GDM and VT6 regressions. Synthetic mutations test refusals; they do not establish live input qualification. VT6 also requires its [exact pixel gate](../e2e/README.md#visible-vt6-installation-terminal). |
| Simulated VM baseline and lease | [vm_baseline.py](vm_baseline.py), [vm_runner.py](vm_runner.py) | Real temporary files and mocked VM operations. Import both `rig` and `lease_rig` when using the latter. Direct simulated `Lease` constructors instead request the explicitly imported `local_preparation_source` fixture, so they hash archived sources without reading the development checkout. JUnit builders retain selected identities and intentional faults. |
| Disposable guest accounts | [system_accounts.py](../integration/system_accounts.py), [account_fixture.py](../e2e/account_fixture.py) | System and E2E checks share observed AccountsService creation/deletion. `require_logged_out` refuses malformed session reads and any target session before spare-account role changes or deletion. Callers retain the exact registered identities, eligible set and single-use action; snapshot restoration owns reversal. |
| Explicit extension-free engineering setup | [disable_extension.py](../../tools/disable_extension.py) | `apply(transport)` uses the test's existing guarded VM transport and lease, restarts the broker with the unshipped recovery bypass and disables eligible children's extensions. No restore or nested maintenance owner; ordinary attempt cleanup owns removal. See [development gate limits](#development-only-extension-isolation). |
| Synthetic E2E evidence and provenance | [e2e_evidence.py](e2e_evidence.py), [e2e_provenance.py](e2e_provenance.py) | `attempt`, `source`, `assets` and `lease` exercise real validators with declared synthetic inputs. |
| Offline asset transfer | [e2e_transfer.py](e2e_transfer.py) | `GuestFiles` uses pytest-private files for actual upload bytes, metadata, corruption and partial-failure tests. It acquires no VM or cleanup ownership. |
| Recorder and offline credential fixtures | [e2e_recording.py](e2e_recording.py), [e2e_credentials.py](e2e_credentials.py) | Recorder `session` uses an imported evidence `attempt`; opt-in `collector_sync` checks real flushed bytes and collector sync order while dedicated collector tests retain physical sync coverage. Retention sync remains real. Credential `attempt` can be aliased locally. Preserve privacy canaries and cleanup results. |
| Launcher orchestration | [launcher.py](launcher.py) | Opt-in `synthetic_package_identity` retains real named-input option/prefix selection with one private source file and tiny synthetic hashes. Real source-byte identity/refusal remains in the storage regressions. |
| Redacted authentication evidence | [authentication.py](authentication.py) | `collect_local` executes the real collector with account/OS reads replaced. |
| Catalog scope and screenshot metadata | [installed_catalog.py](installed_catalog.py), [screens.py](screens.py) | Temporary real catalog discovery; synthetic PNG headers for metadata validation, not pixel acceptance. |
| Child indicator unit adapter | [indicator.mjs](../child/support/indicator.mjs) | Fresh Node VM context and explicit platform doubles; nested-Shell tests retain real lifecycle/input coverage. |
| External desktop input delivery | [mutter_input.py](../ui/mutter_input.py) | Supporting desktop/provider operations retain their qualified input transport and owned session cleanup. Product panel and GTK controls use the Application UI API facade. |
| Desktop input inside an installed check | [desktop_session.py](../e2e/desktop_session.py) `run_attached` | Reuse the caller's held running VNC lease and guarded transport with an existing journey plan. Credentials are verified read-only before input; the worker closes at the completed controller-stage boundary while the caller retains its session, watch and restoration. Pass the existing fixture context for activity/retained-work operations. Attach before any engineering password mutation; never reset credentials or session state to repair an observed history. This seam claims neither worker-module completion nor customer-journey acceptance. |
| Real elapsed time inside an installed journey | [real_interval.py](../e2e/real_interval.py) | `interval_action(duration)` waits one finite interval; `wait_until(journey, guard, target)` reaches a caller-owned controller-monotonic target in bounded intervals under the same attempt deadline, ownership checks and watch output. Keep the original grant deadline, lead time and independent expiry/suspend-crossing assertions in the caller; elapsed time alone proves no product result. |
| Package changes during a journey | [package_command.py](../e2e/package_command.py) `PackageCommand` | Product and catalogue-fixture commands share single-use submission, disk admission, guarded transport, input rechecks and bounded output. Keep package identity/phase checks and independent completion/version results in their respective readers. Cases own the package-change order and public policy/draft assertions; see the [catalogue update/removal bindings](../../docs/TestAutomation/E2E-Building-Blocks.md#native-launch-denial-qualification). Installed engineering histories retain `system_guest`'s checkout installation through `make install`. |

## Development-only extension isolation

`tools/disable-extension --vm NAME` accepts a registered VM name or ID in an
existing owned, running app-snapshot maintenance instance. It uses the guarded
`test-vm exec` transport, shared reservation and watch infrastructure; it never
adopts a manually started guest, boots, restores or captures a snapshot.
Tests may call `tools.disable_extension.apply(transport)` with their existing
guarded transport and lease; ordinary tests do not invoke it implicitly.

The helper deploys the unshipped [development launcher](../../tools/development_broker.py)
and a root-owned service override, admits that exact launcher through a size/hash
trust entry, restarts the broker with `--disable-child-extension-recovery`, and
disables eligible children's extensions. Administrators and kiosk are excluded.
Identical deployed files are reusable; unknown files, links, unsafe ownership or
differing versions refuse. Partial failures require normal snapshot recovery.
The override survives reboot within that development history; ordinary attempt
cleanup owns its removal. These files are excluded from production manifests.

The launcher suppresses enables at `ExtensionManager.set_enabled`, including
startup, screen-limit, approval and recovery requests, and preserves GNOME's
global extension-disable switch. Disable/cleanup calls still run. Suppression
logs fixed development warnings without account identifiers. Successful callers
do not prove extension readiness; suppressed enables skip per-activation payload
validation. Ordinary launcher migration and trust guards still run.
Timing, admission, session preparation, app policy and native enforcement retain
their current dependencies. This bypass is engineering setup and cannot establish
an unmodified installed-product acceptance result or extension independence.

## Frozen native fixture bundles

`tools/run-tests fixtures build --kind native-runtime --target ubuntu|fedora`
allocates retained host output and constructs one complete movable runtime per
target. Use the returned `native-runtime` path with
`tools/run-tests fixtures verify 'RETURNED-PATH' --kind native-runtime --target ubuntu|fedora`.
The target is Ubuntu 26.04 or Fedora 44 on x86_64. The exact local distribution
or the existing offline rootless target builder supplies compilation; this
route never builds product packages, prepares images or touches a guest.

Construction freezes the finite `artifact_inputs.NATIVE_RUNTIME_SOURCES`, compiles
ten identities with the existing native compiler helper, and assembles in a
fresh interpreter loading only the frozen declarations. Original and frozen
sources are rechecked before atomic publication of the completed child directory.
The configured family's `fixture_path` selects a directory under `tests/fixtures`.
Its nearest ancestor `recipe.json` selects the existing Ubuntu or Fedora builder
with `{"target":"ubuntu"}` or `{"target":"fedora"}`. Standalone target builds
use `common/ubuntu/common` or `common/fedora/common`. Shared sources remain in
their existing locations. A selected directory or its ancestors may override a
finite source by placing it at `files/` followed by its repository-relative path;
each ancestor's `files/` tree is read recursively, and the nearest override wins.
Sibling directories contribute nothing. Unknown source files refuse rather than
being silently omitted: generated runtime destinations remain the finite native
declaration, rather than arbitrary copied input files. Overrides are composed
before compilation and freeze to the same canonical source paths,
so effective byte or mode changes invalidate the input identity and private frozen
copies retain the selected inputs. Links and paths outside the fixture root refuse.
Producer registration, inherited compiler/container leases and exact cleanup
remain with the [storage owner](../../docs/Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes).
Concurrent native builds use `Store.queued_producer()` to wait on a shared build
gate through producer cleanup. The separate nonblocking descendant lease and
exact recovery requirements remain in force; waiting never adopts unfinished work.
An isolated [container helper](../../tools/fixture_container.py) compacts only
the inherited leases and uses Podman's standard `--preserve-fds` route. Build
admission uses the artifact category's two CPU slots, 4 GiB and I/O limits.
Final source, output and both compiler scratch sizes are logged and bounded by
128 MiB; this is final allocation accounting, not a measured peak or byte quota.

If an interrupted producer leaves an unfinished slot, read its exact
`transaction_id` from `output/test-runs/host/fixtures/producer.json`, then run
`tools/run-tests fixtures recover TRANSACTION`. This calls the existing
`Store.recover()` guard: active descendants, changed identities and unknown
allocations still refuse. It touches no VM or completed execution input.

Schema 1 contains `fixture-manifest.json`, deterministic `payload.tar` and
`complete.json`. Build identity hashes source, target, toolchain and dependency
inputs. Content identity hashes exact manifest/archive bytes, including the
separately recorded and independently recomputed native ABI proofs. Verification
checks all declared movable destinations, aliases, literal launchers, symbolic roles,
modes, finite native actions and absence controls without extracting the archive.
It rejects duplicate/unknown fields, unsafe archives, extra/missing bytes and
incompatible ELF64 loader/library/GLIBC requirements. System Python/GTK supplies
the GUI runtime; bundles carry only the two adjacent modules.

`fixture_manifest.select()` returns finite subset unions. Native and Riley-grid
contain 21 and sixteen files; baseline-child adds only Riley's five native launchers;
activity three; trusted-hard/soft one executable each,
with separate optional launcher subsets. Mechanical, command, whitespace,
pattern, retention and catalogue retain their exact comparisons; compatibility
selects the separate legacy S runtime. `legacy` selects the complete declaration.
No subset has a separate build version. Account homes remain symbolic until an
accepted guest account mapping exists. A constructed bundle alone does not
authorize guest input; use the separately guarded provisioning boundary below.

`tools/run-tests fixtures prepare --kind native-runtime --target ubuntu|fedora`
selects an execution-owned input through
[`fixture_execution.prepare()`](../../tools/fixture_execution.py). It registers
an empty allocation in the existing active retention journal, copies independently
verified producer bytes and publishes the completed child atomically before
releasing the producer. A matching input is reusable only within that same run,
after full verification. Product-only edits do not change the fixture key;
incomplete, corrupt, missing or replaced registered inputs refuse without repair
or replacement. Independent executions own separate bounded copies.

When fixture declarations grow, inspect the exact older inventory before changing
baseline compatibility. `baseline_fixtures._compiled_retirement_record` reconstructs
known historical closures in reverse addition order and admits their receipts
only as read-only clean-output witnesses after verifying ownership and absence.
That compatibility supplies no authority to delete a partial or foreign fixture.

Select before acquiring a VM. Pass the immutable `Selection.record()` through
descendants and keep the existing retention environment and
`test_storage.scratch_descriptors()` forwarding. The inherited owner descriptor
protects the original journal until descendants close it; unfinished recovery
continues to block rotation through the existing retention owner. After cleanup,
normal last-three-run retention applies. There is no separate fixture cache,
pin journal or deletion owner.

`fixture_execution.verify(selection)` uses the shared
`test_storage.authenticated_input()` read-only boundary. It authenticates the
actual process/caller, pins the exact registered allocation and journal, holds
the existing writer lock for reading and verifies the selected frozen bundle
through directory descriptors. A privileged consumer never writes caller-owned
inputs or registers them in another journal. Runner integration remains with
the subsequent fixture-plan tasks.

## Attempt-owned fixture provisioning

[`fixture_provision.Provisioner`](../../tools/fixture_provision.py) reads an
immutable execution selection through the authenticated input owner and sends
only the finite selected runtime union through the existing guarded, watched SSH
transport. The caller holds the exclusive VM lease and registers the staging
intent with its existing attempt owner before the first guest write. The
provisioner owns no VM restoration, retention journal or rollback mechanism.

The host account owns its fixture input folder. Privileged controllers read
that folder through the existing authenticated input boundary; SSH copies the
selected files and assigns ownership from accepted guest roles. Host and guest
accounts need no matching numeric IDs or permission synchronization.

System, installed-journey and standalone graphical/serial preparation share
`system_fixture_preparation.provision` for the attempt ID, staging-intent
registration, provisioner construction and immediate readiness check. Callers
first enforce their own qualified target, restored-state, input and subset gates;
the shared handoff grants no additional binding and owns no recovery. Reuse it
instead of assembling another staging/readiness envelope. It retains the same
attempt-local intent file, transport and cleanup owner. Host checks keep their
private files and in-memory doubles, with no new process, display, bus, shared
cache or resource demand; existing unit/cleanup classifications remain applicable.

`provision(selection, subsets, attempt_id=...)` preflights the target, accepted
account roles, complete selected destinations, absence controls and native
metadata. Private staging precedes placement, exact native activation, labels,
independent byte/metadata readback and a harmless runtime witness. A repeated
identical request verifies without rewriting matching state. Failure or an
uncertain reply prevents readiness and leaves staging and diagnostics to the
existing attempt's snapshot recovery; never retry an uncertain command or signal.

Readiness binds the manifest/content, subsets, VM UUID, boot and attempt.
Call `require_ready(receipt)` at the input boundary; a saved receipt by itself
authorizes nothing. Failure and readiness belong to the lease, so constructing
another provisioner cannot bypass them. Subset changes require a fresh clean
attempt. After the existing VM owner has restored its snapshot and verified the
guest off, `reset_after_restore(lease)` retires that generation before the next
prepare. Old objects and receipts stay unusable. Reboot alone grants no reset.
The separate [idle maintenance refresh](../integration/README.md#idle-fixture-maintenance-refresh)
owner may reconstruct a verified persisted generation with `resume_maintenance`
and explicitly `replace` it with authenticated, retained, same-subset input.
It persists pending readiness before fixture use and makes uncertain operations
unavailable until owned recovery. This does not change ordinary provisioning's
immutable-attempt contract.
`wait_environment()` observes native startup before an independent clean audit;
it grants no fixture readiness. The shared guest boundary waits up to 180 seconds
for one activating service invocation to become active, pinning its invocation
and its PID once available. Failed states, changed identities and the deadline
refuse readiness. It then observes that active daemon's current-boot startup
message and update completion after a pre-update journal cursor before exact
database readback. It never resends an update or retries a failed database command.
The `check_fixture_provisioning` engineering selector is qualified on clean Ubuntu
26.04 and Fedora 44 attempts: foreign-destination refusal, a lost reply after real
SSH staging, fresh minimal trusted-hard provisioning, and the installed
native/activity/trusted/mechanical union. The interrupted generation withholds
input even through a replacement facade; the VM owner restores it before fresh
provisioning. Both targets independently prove exact bytes/metadata, trust rows,
all four deliberately untrusted native runtime controls, verification without
writes, preserved vendor/product policy and final baseline restoration.
Fedora additionally proves enforcing SELinux and exact labels, finite content/UID
admissions, source/compiled/public-rule agreement, and actual denial of the
untrusted mechanical control without an admission. Compiled-file and CLI checks
complement runtime outcomes; they grant no concurrent-updater qualification.
Ubuntu's [product-free system preparation](../integration/README.md#ubuntu-product-free-system-preparation)
and the same [Fedora boundary](../integration/README.md#fedora-product-free-system-preparation)
are qualified through the real system attempt and all three Parent bootstrap
alias compositions. Its default selects only trusted-hard after SSH readiness
and before installation input; ordinary histories use the scoped subsets in the
[product-free system contract](../integration/README.md#ubuntu-product-free-system-preparation).
Its dedicated engineering selector also verifies immutable
selection after edits to the actual private producer source checkout, across
two restored boots. Ubuntu's [installed-system preparation](../integration/README.md#ubuntu-installed-system-preparation)
and the same [Fedora boundary](../integration/README.md#fedora-installed-system-preparation)
use that same boundary with the case-required subsets described in the
installed-system contract, after explicit offline app restoration and
fresh SSH bootstrap. Read-only readiness renewal after a session reboot
checks the same selected bytes and native state without resetting scenario
mutations. Renewal permits the native closure, the hard witness alone or
system-282's exact hard/native/activity/baseline-child union; all other subsets
still refuse. The process-update case renews its original native readiness after
the earlier release's required reboot, before verifying its launchers.
Ubuntu's [installed E2E preparation](../integration/README.md#ubuntu-installed-e2e-preparation)
and the same [Fedora boundary](../integration/README.md#fedora-installed-e2e-preparation)
use the immutable native selection by default, and the finite native/activity/
baseline-child union only for the fixed baseline composition and active-grant
disable qualification callers and `E2E-015/child-overlay-cancel`, after online
resume/credential rebind or explicit offline restoration, before setup releases
scenario input. Its
preparation-only selector retains separate proof of both restore branches.
The named app-set qualification selects just native/baseline-child under its
fixed caller, with independent Riley launcher verification before product input.
Ubuntu's [product-free E2E preparation](../integration/README.md#ubuntu-product-free-e2e-preparation)
and the same [Fedora boundary](../integration/README.md#fedora-product-free-e2e-preparation)
provision the native closure after owned SSH readiness and before package-only
scenario transfer. `E2E-027/continuous` adds the existing `baseline-child`
subset there so Riley has the four launchers its lifecycle journey manages.
Entry, package and upgrade retain distinct histories;
GDM-only entry requires no native input or movable payload. Customer input and
product assertions remain outside fixture preparation acceptance.
Ubuntu's [standalone transfer preparation](../integration/README.md#ubuntu-standalone-transfer-preparation)
and the same [Fedora boundary](../integration/README.md#fedora-standalone-transfer-preparation)
use the same native provisioner at Smoke's post-SSH boundary before its first
ready reply, with package-only scenario delivery kept separate. Its preparation
check stops before graphical input. Ubuntu's
[standalone serial boundary](../integration/README.md#ubuntu-standalone-serial-preparation)
and the same [Fedora boundary](../integration/README.md#fedora-standalone-serial-preparation)
retain preboot credential/getty verification and use that same post-SSH step
before serial input. Package-bearing install/refusal aliases retain their own
input and result assertions; the preparation-only proof stops before console
attachment or authentication. Ubuntu's
[recorded serial caller](../integration/README.md#ubuntu-recorded-serial-preparation)
and the same [Fedora caller](../integration/README.md#fedora-recorded-serial-preparation)
use the same readiness step under `ScenarioContext`, durably binding the selected
input and fresh readiness to recorder provenance before the ready reply. Its
preparation check also finishes recorder cleanup without starting a serial worker.
Fedora retains enforcing SELinux and exact native admissions/labels.
Other ordinary runner branches and engineering selectors
require qualification of their actual target and preparation envelope under the
[fixture design](../../docs/TestAutomation/Fixture-Design.md#runner-integration).
Host doubles supply no installed
or customer acceptance. Ubuntu's delivered
[clean-capture check](../integration/Environment.md#ubuntu-clean-snapshots)
supplies snapshot infrastructure acceptance only.

## Host and guest boundaries

Disposable eligible-parent setup must verify eligibility after unlocking; a
successful AccountsService unlock can leave a password-disabled account locked.
`e2e_dynamic_account.prepare_spare_approver` reuses `system_caller.FixturePassword`
to set a private random credential before unlocking, then independently checks
the new account and retained administrator. Reuse that guarded fixture rather
than changing a baseline account or treating command success as eligibility.

For a copied executable, reuse FILE05's `SyntheticFiles` operation and its
[qualified copy binding](../../docs/TestAutomation/E2E-Building-Blocks.md#space-bearing-executable-copy).
`SyntheticFiles.copy_executable(source=..., destination=...)` stages and copies
once, then compares the unchanged source, directory, identical bytes and distinct
copy identity after independent readback. Special-path and versioned callers
keep their finite source keys, destination paths, expected fixture digests and
copy/cleanup order; a source in the parent directory retains its `../` receipt key.
Carry the exact source/copy receipt through independent readback and cleanup;
identical bytes do not authorize adopting a replacement inode. The copied path
also needs its explicit shared launch and live-owner binding: a successful copy
alone does not prove the child can open and use it. Keep policy effects and
original-versus-copy assertions in the consuming case, separate from copy
qualification.

Desktop launch consumers reuse `synthetic_files.desktop_entry_actions(child=...)`
for trusted placement, independent readback and receipt-owned cleanup. Keep the
child visits, launch/use assertions and placement/cleanup order in each plan;
do not import a qualification plan to obtain file mechanics. Actual icon input
uses the [qualified DING operation](../../docs/TestAutomation/E2E-Building-Blocks.md#native-desktop-entry-and-usable-launch),
including its independent keyboard-selection guard.
For a second window, compose `journey_blocks.native_window_app` for the explicit
command-primary and desktop-secondary S endpoints. Keep captures, distinct-window
comparisons and unchanged original work in the caller. The shared
`onpc_app_rows::native_open_desktop` owns the optional panel-cycle navigation
before icon observation; individual workers must not copy that shortcut or use
it as a retry after uncertain input. An icon's accessibility focus does not
establish compositor keyboard focus or DING's selected-file set. Qualify the
route with original work still open, not only on an empty desktop.

For versioned additions under an active child block, `SyntheticFiles` accepts
`administrative=True` only for `native-version-next` and `native-version-nonmatch`.
It uses the existing guarded root transport for ordinary placement/readback,
requires real/effective root, and keeps the same Jordan-owned directory chain,
exclusive creation, file owner/mode/digest and source/copy identity guards.
The selected actor stays with that controller through cleanup. The default
remains child execution; neither mode changes policy, trust or refresh state.
Customer access results still come from the child's single-use launch operation.

Fixture qualifications share `qualification_storage.run_qualification` for
private allocation, result writing and failure reporting. Each caller keeps its
root/target preflight, finite input selection, proof and any named-session options.
The helper reuses `session` and `allocate`; it adds no VM, process or cleanup
owner and reports success only after the proof and retention session finish.
Recovery diagnostics keep their separate `recovery_session` route.

Inventory subprocesses must keep the checkout being documented after environment
sanitization. `generate_test_coverage.capture` uses the launcher's existing
`ONPC_LAUNCHER_CONTROLLER_ROOT` binding; a working directory alone does not
override `run-tests`' configured default branch. Never repair another checkout's
unfinished work to make the current checkout's collection pass.

Snap and Flatpak fixture readers share [PackagedFixtures](../e2e/native_fixtures.py) for
the pinned transport, source rechecks, bounded canonical reply and final guard.
Keep each package's installed identity, confinement and catalogue checks in its
own reader; native provisioning retains its separate selection/readiness route.

When a journey needs concurrent packaged-app work, declare distinct public
instances in the fixture and its exported launcher before baseline capture.
Declare independent-window support there when the fixture provides it. Check
these captured inputs before adding a workaround to the shared launch adapter;
see the qualified [Flatpak grid boundary](../../docs/TestAutomation/E2E-Building-Blocks.md#flatpak-grid-use).

Declare a qualification's `fixture_subsets` and `fixture_caller`, or the case
context's matching fields, before shared attempt preparation when a journey
needs more than the default native closure.
Use the qualified profiles in
[e2e_fixture_preparation.py](../integration/e2e_fixture_preparation.py), including
`ACTIVITY_SUBSETS` for retained native work. Attaching a desktop worker does not
provision extra files; pass that existing fixture context to `run_attached`.
Check both the declared profile and exact caller registration with
`qualified_subsets` before the first live attempt; setting the context fields
alone does not register a new consumer. Check this declaration before diagnosing
a missing activity fixture as a launch or product failure. Preserve the finite
caller allowlist and readiness refusals.

Snap and Flatpak separate-window checks reuse
`ui_observations.compare_app_activity(result='separate')` on their immutable
captures through `JourneyPlan.activity_checks[current] = (earlier, 'separate')`,
as do native temporary-access journeys. Declare both endpoints in the plan
instead of overriding `check_activity` just for this comparison. The shared
controller checks the earlier capture before releasing the worker's reply.
It requires both different processes and different public endpoints;
the caller keeps the capture order and the later original-window preservation
comparison. A replacement check alone cannot establish two distinct windows.
`installed_journey.ACTIVITY_BINDINGS` supplies the common native, Files, Snap
and Flatpak endpoint classification for plan validation and runtime capture.
All use the same replay check, immutable decode and comparison before reply;
new consumers declare their endpoints instead of copying `check_activity`.

`product_logs.py` owns the guest reader and pytest snapshots;
`vm_transport.Transport.capture_product_logs` owns host transfer before shutdown.
Keep host transport imports out of staged guest readers: `guest_inputs.Bundle`
follows function-local imports too. Moving host code into a local import does
not remove it from the frozen guest dependency closure. Preserve the shared
reader, private capture, archive guards and the lease's single-use callback.
Preparation that directly shuts down a guest must first consume
`Lease.collect_product_logs()` while its transport and ownership interval are
live, as in offline app-snapshot capture. A recorded collection failure must
still fail the final verdict after cleanup, even when product assertions pass.

Installed service-outage fixtures reuse `system_guest.runtime_service_mask` and
`remove_runtime_service_mask` for creation and unchanged root-owned symlink
verification before unmasking. Keep invocation checks, stop/start order and
recovery assertions in each test; reboot-spanning or separately journaled faults
retain their own lifetime records. Resolve a D-Bus dependency's actual
`SystemdService` from its activation file and require the declared unit before
masking it. Budget its native stop timeout plus transport headroom: the usage
reader uses `system_guest.run`'s 120-second default rather than racing the
daemon's normal inactivity exit with a 30-second deadline.

Installed ordinary-account checks reuse
`system_wellbeing_qualification.owned_manager` for temporary user-manager startup
and cleanup. It refuses an already active manager, records a new invocation even
when startup fails, and refuses to stop a replacement. Callers keep their account
selection, command environment, finite timeout and product assertions; station
collateral checks retain their separate 75-second budget and diagnostics.

For a fault that needs explicit reversal, persist its exact ownership receipt
before delivering the fault, as in
[system_graphical_expiry.py](../integration/system_graphical_expiry.py)'s
`fault_recorded_broker` callback and `timer_history` mask receipt. Close the attached desktop worker before
reversal in `finally`; restore only that recorded process or mask. This keeps
partial-failure cleanup usable without signalling a replacement service or
adopting changed state. Keep the fault sequence and recovery assertions with
the consuming history.

Native policy workers reuse `onpc_app_rows::fixture_app(role)` for the fixed
Allowed/Hard/Soft fixture app IDs, matching the controller's `MATCH_APPS`.
Do not copy the desktop-ID hashing into another worker. Each consumer retains
its finite role/rule list, edit order, public readbacks and assertions.

Native policy qualifications and cases compose `journey_blocks.app_policy_entry`
and `policy_edits.NativePolicyJourney` for the qualified fresh Parent/Jordan
entry, caller-selected allowance operation, fixture readiness and initial
catalogue comparison. The shared-launcher case supplies its own plan and alias
binding rather than inheriting a qualification's plan or journey. Keep settings,
balances, policy rounds, retained-window endpoints and closure assertions in each
consumer; the shared entry does not qualify other children or allowance bindings.
The existing worker continues to use `onpc_parent::set_allowance` and the shared
native launch/use/close operations. These helpers add no resource or cleanup owner.
Native, Snap and Flatpak launch cases also reuse `app_policy_entry(initial_rows=False)`
when their own saved-rule read supplies the policy result. Keep each case's plan,
fixture actions, child entries and expected settings local; do not derive a
different fixture family's case by filtering and replacing a runnable case's plan.
Use `allowance=None` for the same shared Parent entry without a policy change,
as in Snap grid qualification and limits-off launch. Build each variant directly
from these fragments rather than removing allowance stages from an enabled plan.
Keep authentication invocations bound to the explicit `fresh_desktop` fragments;
a broad `child-` prefix also matches Parent's child-picker stages and must not
turn those reads into desktop authentication invocations.

Flatpak command/grid variants compose `flatpak_app_launch.launch_plan(route=..., limits=..., rule=...)`
and the same `onpc_app_launch::run` worker. Keep the fixed dispatch bindings in
`smoke.pm` together; another rule or limits variant needs no copied worker handoff.
Flatpak denials reuse `journey_blocks.flatpak_blocked_app` and the matching
`onpc_app_rows::flatpak_blocked_app` worker in launch cases, temporary-approval
histories and the standalone grid qualification. The
grid binding keeps both the hidden-launcher read and independent command-policy
denial; it never attempts a hidden grid entry. Callers keep role, route, stage
prefix, policy order, other-child use and retained-work comparisons. The shared
fragment adds no input, process, storage or cleanup owner.
Bind each policy save/read and any allowance checkpoint explicitly to `existing`
in `JourneyPlan.child_bindings`: selecting Jordan in Parent does not bind later
observer calls implicitly. The `flatpak-allowed-command-blocked` operation names
fixture A, not its saved access choice; both Hard and Soft cases reuse that
app-specific command denial and complete window-absence check. Riley's separate
launch and submitted-draft result still prove the rule is scoped to Jordan.

For ordered access-rule transitions, prepare matching once through FLOW19 and
compare its saved value after each tested access save. Repeating a match save
between transitions can conceal which save caused an app to close. Keep the
original matching capture and a separately bound nonmatching window so closure
and preserved work cannot be satisfied by replacement launches.

When several native fixture windows remain open, read each original window's
visibility, owner, endpoint and exact work independently. Foreground focus does
not establish preservation: another owned app can cover a still-visible window.
Use `AccessibleUI.native_app_snapshot` for that observation and retain the
separate guarded Submit and independent result to prove continued usability.
If a later fresh launch uses the same fixture window identity, first finish the
retained-work comparison and normally close that original window. A retained
Allowed window can coexist with distinct Hard/Soft denial probes, but cannot
satisfy a fresh Allowed launch. Preserve the launch's prior-window absence guard.

Choose activity comparisons from the session boundary. App reopening and idle
return can compare the original window and work; logout and reboot end that
session, so verify new usable apps after fresh sign-in instead. Keep saved-policy
and original-grant comparisons across either boundary. The expired persistence
cases in [app_restart_expired.py](../e2e/app_restart_expired.py) share preparation
and recovery while retaining this distinction; do not copy retained-window
assertions into a fresh-session history or replace a retained-work result with
a new launch.

Suspend consumers reuse `InstalledJourney.submit_suspend` and
`Transport.suspend_wake`, including the host-observed asleep interval and single
owned wake. The guest cannot service SSH while asleep, so do not wait for SSH
before waking it. Keep same-boot/session and original usable-work comparisons
in the consumer, with enough grant headroom for guarded unlock and readback.
The [LIFE03 binding](../../docs/TestAutomation/E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries)
owns the required baseline power/graphics settings and qualified target scope;
do not add a consumer-specific wake method or unlock workaround.

Maintenance reproductions share `vm_probe.installed_reproduction_selection`
for clean-input validation and attested running-snapshot binding. Keep each
caller's package/fixture input declaration, journey and stopping point local;
the system expiry history retains its distinct system fixture validation.
Load an unrelated journey only when its diagnostic is selected. Its import-time
plan checks must not block another reproduction; keep those checks on its own route.
Single public reads share `vm_probe.observe_maintenance`, including intention,
recovery session, registered private evidence, guarded transport and final lease
check. Multi-action probes keep their finite order and assertions. These helpers
reuse the existing allocation and maintenance owner; they add no process, VM,
bus or cleanup lifetime. The existing VM-control safety module retains private
pytest state and mocked VM calls in both unit and cleanup inventories.
`tools/test-vm --vm NAME reproduce-snap-grid` binds the existing Snap grid
qualification to that same reproduction owner. It observes Jordan's first
opened window once, closes the worker and retains his desktop for guarded
`exec` probes followed by `stop`; it supplies no acceptance credit.
`reproduce-expired-sign-out` similarly binds `AppRestartExpiredJourney` and
`SIGN_OUT_PLAN` to Riley's completed logout, reads `gdm-returned` once and retains
the greeter without replying to that checkpoint. Inspect that exact greeter's
own session bus through guarded `exec`, then finish with `stop`; the diagnostic
does not continue into expiry or replacement approval and grants no case credit.
Attached reproductions can use `desktop_session.run_attached(stop_before=...)`
to retain an exact completed prefix through `installed_journey.validate_boundary`.
That route closes the worker without replying to the selected stage and returns
`scene-retained`, never a passed journey. The system expiry reproduction uses it
to retain the child's original submitted app before the short measured grant,
then times the same shared observation/activity operations under setup headroom.
Keep the owned guest for guarded probes and finish with `stop`; timing samples
from this diagnostic supply no expiry or customer acceptance credit.

`tools/test-vm --vm NAME reproduce-versioned-appimage-assets` retains the
asset qualification's actual result after one shared Parent `logout` request.
It uses the same clean-input, native fixture and credential guards. Inspect
the retained session through guarded `exec`, then use `stop`;
the retained prefix supplies no copy/use qualification or acceptance credit.

Fixture provisioning qualifications reuse
`system_fixture_preparation.register_staging`, as do system, standalone and E2E
preparation through `system_fixture_preparation.provision`. The shared writer
validates the staging path and exclusively creates and flushes the attempt's
intent before guest writes. Callers retain their finite subsets, failure
experiments and assertions; the existing VM owner retains restoration and cleanup.
After a caller-owned reboot and boot-readiness wait, reuse
`system_fixture_preparation.renew_after_reboot(context)` to update that context's
receipt and check readiness. System histories, maintenance reproductions and
package-update cases share this binding; the provisioner's exact input, subset,
attempt and changed-boot guards remain authoritative. This adds no resource owner.

Parent entry declarations reuse `journey_blocks.parent_management(child=...)`:
the default `child` selects Riley; `existing` selects Jordan and reads Screen
Limits through the existing public operation. Both retain the same checkpoint
names for the shared worker. Approval qualifications use this argument instead
of copying and overwriting the child-selection map. Request choices, allowance
values, recorder phases and assertions stay with their callers.

For selection in an open Parent window, reuse `journey_blocks.parent_selection`
with `onpc_parent::select_child`. Selection preserves the current page;
`screen_limits=True` explicitly reaches Screen Limits before its settings read.
Use it after reopening or switching from App Limits, then let the caller declare
its next page and exact saved-state comparisons. Match-editor qualifications
share the same selection fragment without changing their entry assertions.

Parent and child returns to the greeter reuse
`onpc_desktop_session::switch_user` or `::log_out` with the caller's scoped
desktop receipt. Declare its desktop read, command and independent greeter result
with `journey_blocks.desktop_return(prefix, account=...)`; `action='logout'`
ends the session, while the default switch preserves it. Active/expired
persistence cases, Jordan's daily-access qualification and native/Flatpak
captured-closure qualifications share this declaration;
the next account or station entry stays local.
The declared system operation binds the account; the helper consumes that
receipt, submits the command and independently observes the greeter. Retained
daily-access histories use this same operation for both accounts instead of
spelling out the child switch separately. Session/work comparisons and the
decision to switch or log out remain in each history.
GNOME may spend over a minute waiting for a session client during ordinary
logout. `session_control.LOGOUT_WAIT_SECONDS` and its transport margin cover
that asynchronous result without delaying a prompt completion or submitting
logout again; command success alone does not establish that the desktop ended.

TIME02 minute and final-second consumers reuse `countdown.CountdownSample`,
`check_countdown_progress` and `await_countdown_progress`. Each sample copies the
public countdown, controller monotonic read brackets and boot identity; comparisons
retain both immutable endpoints. `UiObservations.observe` brackets each TIME01
read on the controller, independently of the guest's monotonic freshness marker.
Subtract only timestamps from the same clock and boot. For persistence across a
guest reboot, compare controller read brackets, as in `AppRestartActiveJourney`'s
animation reads; guest uptime restarts and cannot order preboot/postboot reads.
The wait reacquires only public child reads under the original 90-second bound
and TIME03 `interval_action`, retaining attempt ownership/deadline/cancellation.
Unchanged reads supply no separate assertion; the changed endpoint must decrease
consistently with elapsed/read latency, minute-flooring intervals and the caller's
explicit two-second estimate tolerance. Final-second comparisons declare one-second
precision, with an explicit prior precision of 60 only for the transition.
They require distinct decreases, include read latency and never demand each tick.
An independently supplied stage read retains the earlier endpoint/deadline.

Daily-only balance comparisons also need enough time before the guest's local
midnight for the declared allowance and history. Malcontent caps its current-day
deadline at midnight even when Parent reports a larger unused daily allowance.
When those reads differ, compare the guest's timezone, current time and native
deadline before changing elapsed-time tolerances or diagnosing an accounting
defect. Preserve the comparison and use an eligible natural calendar window;
clock changes belong only in disposable maintenance experiments.

When daily time outlasts a grant, a positive child countdown cannot establish
whether that grant survived or expired. Capture Parent's separate daily and
one-time balances before leaving, retain the original grant's controller-clock
expiry bound, then independently read the balances after the wait. An allowance
edit while limits remain enabled must preserve the running grant; it does not
start a new expiry clock. [expired_daily_replacement.py](../e2e/expired_daily_replacement.py)
keeps that history, its departure-before-expiry guard and replacement arithmetic
in the case, using shared allowance, approval, countdown and TIME03 operations.
Do not infer grant expiry from total time or renew the grant to repair navigation
that consumed the case's preparation margin.

Staged expiry histories reuse `real_interval.interval_toward(journey, guard, target_ns)`
for one wait of at most 300 seconds toward the original controller-monotonic
nanosecond deadline. Keep the finite wait stages and worker reply boundaries in
the caller; replacing them with one complete-deadline wait can outlast a worker's
reply budget. Missing-deadline refusals and independent expiry assertions remain
with the history.

For a parent edit after expiry, distinguish the save from the child's later
session entry. Check the action's grant effect against the
[product transaction and session rules](../../docs/System-Design.md#state-ownership-and-shared-constraints)
before choosing the expected app result. Preserve the original Soft work capture,
the parent's save/readback, and the child's return as separate ordered endpoints;
closure observed after return does not establish that Save closed the app.
`daily_soft_expiry.py` shares those mechanics across allowance, toggle and
unchanged-match saves while keeping their different app/grant assertions local.

The daily, grant-only and combined retained-work cases compose
`journey_blocks.countdown_activity` and `journey_checks.CountdownActivityJourney`.
Each case keeps its own profile, progression stages, minute-edge bound, recorder
phases and customer assertions; shared work/lock/countdown mechanics must not
depend on importing another runnable case or inheriting its plan.
`CountdownMinutesJourney` composes the qualified same-user four-minute daily-only
profile with independently supplied child entry and two progression invocations.
The [minute progression slice](../../docs/TestAutomation/E2E-Building-Blocks.md#minute-countdown-progression-qualification)
is qualified on Ubuntu 26.04 and Fedora 44.
`CountdownTicksJourney` / `TICK_PLAN` share that machinery and the worker's
daily-profile/entry composition: four daily minutes, at most three observed
minute edges of 90 seconds each until `00:01`, one 90-second transition
into positive exact seconds, then two successive exact decreases
within 15 seconds of each prior endpoint, always with two-second tolerance.
The [final-second slice](../../docs/TestAutomation/E2E-Building-Blocks.md#final-second-countdown-progression-qualification)
records current four-minute qualification on Ubuntu 26.04 and historical
two-minute qualification on Fedora 44. All three current progressions and owned
cleanup passed; complete consumers keep their own
allowance, time bounds and independent results.

`tools/test-vm --vm NAME reproduce-jordan-daily-access` reuses Jordan's shared
qualification and stops before its balance comparison, retaining the public
countdown and Jordan's actual desktop for native/timer and Parent-status probes.
It uses the same maintenance envelope and guards as the other fixed routes.

`tools/test-vm --vm NAME reproduce-countdown-minutes` reuses `CountdownMinutesJourney`
in the maintenance envelope, stopping before the first progression invocation.
It retains the public boundary read and child desktop for guarded guest probes;
diagnosis supplies no acceptance result. The existing VM-control safety module
uses private pytest files and mocked VM calls for this boundary, without adding
shared storage, processes, sockets, buses, displays or cleanup ownership.

`reproduce-countdown-resume` reuses the qualified child lock/unlock journey,
including native activity and guarded password recipients. Its fixed 20-second
active and 70-second locked intervals use TIME03; public reads before Lock and
after authenticated return are retained in the maintenance allocation. It stops
before the activity comparison and supplies no acceptance credit. Both routes
reuse the existing maintenance lease, worker cleanup and evidence allocation.

TIME04's `natural_expiry_observation.await_natural_expiry` receives an immutable
`CountdownSample` and original `AppActivityObservation`. The existing native
Submit and independent activity capture prove ordinary usable work before the
wait. `child-natural-expiry-wait-lock` then observes only the pinned native
session and qualified Shell curtain/restriction; it reads neither the app nor
the panel and releases no input. Both lock observations must complete within
the initial display's upper bound plus 15 seconds, measured on that boot's guest
monotonic clock. The controller permits three minutes for delayed reply delivery
without extending the measured lock deadline or the attempt deadline. A timed-out
read can be reacquired within the original deadline; ownership/session refusals
remain terminal. This avoids repeated SSH steps and countdown reads in the final
seconds. A whole-guest pause that prevents timely observation supplies no timing
proof. `NaturalExpiryJourney` then obtains a fresh lock recipient proof,
allows one harmless Shift and independently reads the same lock again.
If natural locking crosses the observer's two native lock reads, it reobserves
once with the original account and desktop identity pinned. Other session or
ownership refusals and uncertain input remain terminal; no action is retried.
Reuse `onpc_desktop_session::verify_locked_input` for that proof/input/result
sequence in qualifications, complete cases and installed system histories.
Callers supply their ready/result stage names and keep the lock identity,
expiry and recovery assertions in their existing controller. The helper adds
no wait, retry, resource or cleanup owner.
`tools/test-vm --vm NAME reproduce-natural-expiry` reuses that journey through
the child's original activity capture, stopping before the measured expiry
observer for engineering probes and normal owned maintenance cleanup. It uses
the qualification's exact `ACTIVITY_SUBSETS` and caller through attempt-owned
preparation, not fixtures embedded in a snapshot. It supplies no acceptance
credit. Its fixture inputs use the maintained builder; no reusable prerequisite
is installed during a run.
System-282 reuses the same activity and lock readers through
`natural_expiry.run_system_graphical_expiry` and the installed owner's attached
desktop worker. Its engineering reads omit the panel. The shared
`natural_expiry_observation` owner fixes one-second sampling, a maximum
15-second gap between completed samples and expiry plus 15 seconds for the
dedicated natural-lock observation. A missed or late timed sample fails even if
it eventually observes a lock. The subsequent fresh lock-ready → Shift →
independent same-lock result has a separate 180-second verification budget.
The peer history verifies foreground input/work continuity and protected child
input under expiry plus 180 seconds; it does not claim a 15-second background
lock measurement: switch-user already locks the child before entering Parent.
Recovery has 300 seconds for guarded sign-in and independent
work readback. Setup/recovery grants last 1200 seconds so navigation need not
race their expiry; the measured 45-second and peer 15-second grants stay short.
These implement the [VM timing contract](../../docs/Mandates/VM-Mandate.MD#timing-and-slow-vm-resilience)
through the existing worker and observers. TIME04 keeps its initial sample upper end
plus 15 seconds; foreground-revocation and lock-retry bounds remain 15 seconds.
`SystemGraphicalExpiryJourney.observe_expiry` shares the timed observation and
subsequent input-verification budget across natural, policy-change, broker-crash,
broker-stop, broker-stall and pending-approval histories. Each caller keeps its original deadline, fault
or policy sequence and real-input assertion; the worker uses
`onpc_desktop_session::verify_locked_input` for the actual input challenge.
`SystemGraphicalExpiryJourney._recover_after_outage(expiry_at=...)` shares the
outage-inclusive recovery bound: the earlier of recovery-start plus 300 seconds
and original expiry plus 300 seconds. Pass the original expiry explicitly for broker-stop,
broker-stall and timer-replacement histories; service activation and the recovery
grant cannot restart that clock. Callers retain their original expiry and work
assertions. The broker-stop history uses one grant; broker-stall reuses both
crash histories and applies that bound to each. Only the identity-recorded stopped
process can receive SIGCONT, including the worker's failure cleanup; a recovered
zero-balance reply and original-work readback remain independent assertions.
`TimerReplacementJourney` reuses the single-outage `STOP_PLAN` and its worker.
Its guest `timer_history` pins the actual Malcontent bus owner, process start
and service invocation before stopping that native timer under an owned mask.
The mask remains through original expiry and protected input. Recovery requires
a distinct bus/process/service owner, the real child's native exhausted estimate,
zero balance and unchanged expired grant before any recovery entitlement.
Child work recovery stays within original expiry plus 300 seconds; the same
parent session, input and work are checked before and after. Failure cleanup
removes only the recorded mask. System 310 passed on session-selected
`onpc-Ubuntu26.04-1` in `20261108T075926Z-16e1908b`, including collection,
worker shutdown, owned cleanup and baseline restoration. Fedora remains
unqualified; existing retry and session-replacement owners retain their distinct
stale-work assertions, without a new deliberately held-reply matrix here.
The complete current-production system-282 history passed on Ubuntu 26.04 and
Fedora 44, including both protected-input challenges and original-work recovery.
This qualifies the shared engineering observations, not extension-free locking
or a complete customer scenario.
System 282 observes automatic extension recovery before its separate daily-only
PAM admission check. Starting authentication during that recovery can produce the
broker's valid Busy refusal despite positive remaining time. Reuse
`wait_for_extension_recovery` for this ordering, without a settling sleep or an
authentication retry. System 301 separately isolates authentication-triggered
recovery; keep its attribution and refusal guards intact.
System 304 (`session::test_expiry_during_pending_approval`) reuses that attached
worker through `natural_expiry.APPROVAL_PLAN` / `PendingApprovalJourney` and the
same installed guest owner. Each of its two histories issues a 300-second grant
after agent readiness, then establishes a genuine selected-parent challenge at
least 180 seconds before the original deadline. The owning synchronous SSH
command retains the caller and authentication agent while its existing output
callback runs the shared natural-lock or foreground-peer observer. A fixed
attempt-local finish marker requests cancellation; context cleanup closes both
pidfd-owned processes. No password, detached process or new grant is submitted.
The guest independently verifies that the challenge stayed pending across expiry
and that cancellation preserved the original grant. The caller's explicit
15-minute D-Bus budget accommodates the deliberate wait; it changes no product
authentication deadline. Worker reply waits cover both finite histories without
extending the original natural-lock bound. Protected input, original-work
recovery, unrelated foreground input, collection and baseline restoration passed
on session-selected `onpc-Ubuntu26.04-1`; Fedora remains unqualified. This supplies
no customer-case or entry-exposure credit.
For startup diagnosis, `tools/test-vm --vm NAME reproduce-system-graphical-expiry`
reuses system-282's one-second autologin seed, reboot and fixture renewal, then
records the child session, foreground and read-only public surface before and
after its preparation grant. It retains the owned maintenance guest for `exec`
probes followed by `stop`, without running the expiry worker or supplying
acceptance credit. Native lock hints in these diagnostics are supporting facts.
The seeded startup can expose a protected Shell curtain or restriction while
logind still reports an unlocked hint. Session navigation and lock-read routing
use fresh screen-saver state from the verified fixture's own session bus;
secure-lock acceptance still requires the owned public protected surface and
independent input/readback. Returning to the greeter never relocks that surface.
The natural-expiry host modules use private pytest records, fake clocks,
in-memory UI/transport doubles and bounded waited Perl children. Their reviewed
unit/cleanup classifications add no shared path, process, bus or display owner.

For a pending-timer/session-replacement history, follow
`SessionReplacementJourney.arm_original`: changing displayed countdown text
witnesses a scheduled tick; API seconds derived from the current clock alone
do not. A fresh-entry guard proves the old session is absent, so capture the new
session identity after sign-in before comparing later retained entries. Keep
the original deadline and replacement entitlement separate, as in
`SessionReplacementJourney`; do not reset the clock being tested to gain setup
time. These are engineering witnesses, not extra steps for ordinary child entry.

FLOW13 daily-only composes `journey_blocks.daily_time_profile` and
`onpc_parent::daily_time_profile`; `DailyTimeProfileJourney` owns the exact
zero-grant gate before edits and caller-declared saved balance checks. Reuse that
initial PARENT09 result as the gate; do not add an unchanged balance reread or
silently clear an unexpected grant to reach the desired profile.
FLOW02's short 2/4-minute bindings reuse PARENT06 Custom selection, public text
and validation, then independent saved settings and PARENT09 balances. They
never revoke or approve. `time_profiles_daily.PLAN` / `SAME_PLAN` own separate
fresh-2/same-user-4 qualification histories and finish through DESK03.
Other profiles, children and retained windows remain outside this slice.
For a policy capture before leaving Parent, compose
`journey_blocks.daily_time_settings` / `onpc_parent::daily_time_settings`,
then the caller's capture and shared DESK03 switch. These are the settings
portion of the full profile, with the same zero-grant gate and saved readbacks.
`panel_expiry` uses the accepted same-user ten-minute binding this way; keep its
policy assertion and uninterrupted child history in the case. Do not copy the
profile worker or remove/reinsert stages from a completed profile declaration.
FLOW13 grant-only uses `journey_blocks.grant_only_time_profile` and
`onpc_parent::grant_only_time_profile`, with caller-owned checks in
`grant_only_profile.GrantOnlyProfileJourney`. Reuse the initial zero-grant
read; only explicit `revoke_first=True` permits Confirm, followed by a fresh
zero-grant read before policy edits. The shared request leaves accept finite
120/180/240/600/1200-second arguments. The current standalone declaration and
`GrantOnlyProfileJourney` default use a 1200-second request for both fresh and
retained/revoke-first qualification; both independently restored histories passed
on Ubuntu 26.04, including retained Parent readback and owned cleanup.
The historical 120-second bindings retain their original scope;
later recipes own their finite duration and independent outcomes.
The same declaration/worker accepts `daily_minutes=4` (the worker's final
argument), with zero retained as the default. `grant_only_profile.COMBINED_PLAN`
currently declares fresh four-minute daily/twenty-minute addition preparation
and retained Parent G>D>0 readback, qualified on Ubuntu 26.04. These preparations
finish after readback without waiting for the twenty-minute grant to expire. The historical
four-minute daily/two-minute addition binding passed on Ubuntu 26.04.
Countdown cases 28 and 29 explicitly override the standalone duration with
600 and 240 seconds respectively. Comparisons carry the actual earlier D,
elapsed time and display precision. For a daily-plus-extra-time history, capture
the actual daily remainder after the child leaves and before approval; the
configured daily allowance is not that remainder. Compare the issued grant to
that captured remainder plus the requested addition, then preserve its original
deadline across later policy edits and child visits.
Failed-approval histories reuse `request_composition.GrantAppEffectsJourney`
with caller-owned `negative_estimates` and `policy_reads`. Its default daily
profile is zero; `daily_seconds=1800` supports the positive daily profile used
by child request recovery. A zero grant does not mean zero usable time in that
profile. Keep the before/after refreshed estimate brackets: daily time continues
to decrease during rejection or Cancel, while the comparison must still detect
an accidental extra grant. Do not copy the comparison or change the child's
profile to fit a grant-only assumption. Cases retain their failure order, app
denials, remembered choices and later successful approval assertions.
`request_initial='selected'` requires a saved 75-second, soft-included request,
as supplied by `revocation_entry`; it does not accept arbitrary remembered choices.
Choose this argument from the preceding request history, independently of
whether the Parent window is new or retained.
Existing credential and producer-recovery checks retain private files/in-memory
doubles and bounded, waited children, with no new host module, VM, display, bus
or cleanup owner.
The existing toggle/unit modules use pytest-private evidence, in-memory doubles
and bounded waited Perl children; the accessible-adapter preview uses its
existing private display/process group. No shared path/cache, socket/bus,
external service or additional cleanup owner is introduced; existing unit/UI
parallelism classifications remain applicable.

Synthetic implementation contracts remain separate from product UI operations.
`tests/ui/test_translation_widget_contracts.py` constructs helper GTK objects to
check translation weak-reference/context lifetime and native Pango attributes;
it launches no product frontend and supplies no customer API acceptance. It
reuses the existing private-display bucket without another compositor owner.
Product surface observations and input continue to use the shared Application
UI API under the [UI mandate](../../docs/Mandates/UI-Automation-Mandate.MD#application-ui-api).

Parent inherited About/feedback observations use
`AccessibleUI.parent_dialog_presentation` with explicit surface/language and
public API text/name comparisons. The `synthetic-rtl` body/reply profile remains
bounded synthetic input, read exactly before new input after reopening.
`onpc_text::replace_text` owns its normal Application UI API text operation,
including fresh owner/surface checks. Dialog checks read translated content and retained
draft values without a focus-traversal acceptance sequence.
Closing the dialog permits ordinary Parent Preferences
and reopening of the retained draft, without private translation/draft access.
These operations add no storage, process, bus or cleanup owner. Existing private
unit/cleanup fixtures and private UI preview/display classifications apply.
The fixed Parent English → Hebrew → English dialog binding passed
`check_e2e_parent_dialog_language` on Ubuntu 26.04 in
`20261005T183953Z-3eaae8af`, with all four required regressions, collection and
owned cleanup. The [catalogue](../../docs/TestAutomation/E2E-Building-Blocks.md#parent-inherited-dialog-qualification)
owns exact scope and retained reports; other frontends and complete cases remain separate.

Feedback's wrong-window close qualification distinguishes an indeterminate
negative read from a positively present dialog with `absent_id(...,
incomplete_raises=True)`. Neither releases input. The existing adapter failure
diagnostic retains only finite absence reasons, never UI text, object paths or
raw exception values. Synthetic-tree and isolated-payload regressions cover the
distinction and private-value exclusion; these use existing in-memory/private
child-process resources and do not change scheduling or cleanup ownership.

All named qualification inputs select current package sources by default through
`named_input()`; `package_source=True` remains an equivalent explicit spelling.
Fixture and upgrade consumers also include their fixture source identity.
Snapshot acquisition derives
the version from that package; preparing the current app snapshot does not
refresh an older immutable qualification bundle. The launcher builds missing
source-bound inputs and preserves valid existing bundles. Host launcher checks
cover matching consumer/preparation bindings, failed preparation before VM
dispatch and reuse without replacing inputs.

Native upgrade input qualification uses the baseline-owned `trusted-hard` and
`trusted-soft` variants through `system_enforcement`'s closed fixture/probe
interfaces. `system_trusted_fixtures.verify_trust` validates preparation and
fixture-record binding, exact payload/metadata, native package/tool provenance
and the enabled native backend's configuration/receipt, fixed native service
group, exact trust-fragment metadata and loaded file-trust rows without
mutation. Original untrusted variants remain
separate. Its host regressions use private pytest records and process-local
command/authentication doubles; they create no native trust database, VM, bus,
display or subprocess. Existing enforcement readiness and directly owned
one-shot execution guards remain unchanged. The new host module is compatible
unit work; enforcement's existing unit/cleanup classifications remain applicable.

`journey_blocks.allowance_selection`, `onpc_allowance_selection::select` and
`gui_blocks.select_allowance` share one Parent allowance block.
`AccessibleUI.select_allowance` selects the canonical offered duration or
`custom` through the scoped `parent-daily-limit-selector` API value.
The retained `allowance_keyboard` observation name independently
reads the final saved value or available Custom editor. Existing preset/custom
helpers delegate to that input block; the name does not select keyboard input.
See the
[mandatory sequence](../../docs/Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception).
Cases own desired values and subsequent save/persistence assertions.
Fresh surface/child/selector identity and enabled-state checks remain.
Input errors preserve the
uncertain-input latch; readback never replays input.
Custom result observation waits for its editor to become logically available,
then uses `setText` and `activate` for normal validation and saving.
The adapter retains the same private preview display and VM lifetimes.
Unit probes use existing private doubles and waited Perl;
UI tests use the existing private display. No new process, storage or cleanup
owner is introduced; existing unit/UI parallelism classifications apply.

Ordinary Parent launch prepares the bound GNOME desktop through the public
`org.gnome.Shell.OverviewActive` property. If the overview is open, the shared
launcher requests closure once and independently waits for the closed result
before invoking Parent. This releases GNOME's startup input grab; GTK's active
window state alone cannot establish compositor focus while Overview is open.
Launch preparation retains session/prompt guards and refuses uncertain input
without replay. It introduces no new resource owner or baseline setting.

`AccessibleUI.read_language` reuses LANG01 ownership/choice reads and bounded
public language values. Qualification values and immutable policy
comparisons stay in `ParentRtlJourney`; other surfaces still need live qualification.
These operations add no process, storage, bus or cleanup owner. Unit/cleanup
probes keep private node/recorder fixtures and waited Perl children; GTK coverage
uses the existing private preview/display. Existing classifications apply.
Follow the mandate's no-visual acceptance rule; logical text is no pixel verdict.

Enabled Riley Hebrew policy observations reuse `parent_language_state`,
language-aware `time_explanation` / `duration_projection` and the controller's
complete enabled-state decoder. `ParentHebrewPolicyJourney` declares the fixed
English capture and comparison endpoints through `language_composition.language_policy`.
Chooser round trips share `onpc_parent::language_presentation_roundtrip` with
the RTL qualification; callers retain their policy assertions. These add no
resource or cleanup owner. Source-bound named inputs prepare both the new slice
and its public-time regression without replacing valid inputs.

Overlay About reads reuse `journey_blocks.overlay_license_read`,
`onpc_about::overlay_license` and the shared `AccessibleUI.clickable_link` reader.
The child-owned About scope and close proof precede the ordinary API close request; fresh absence
and active form return precede caller-declared immutable request comparisons in
`KioskRequestJourney`. Host and installed workers never activate these links.
The finite `links='browser-links'` fragment checks website and privacy through
`AccessibleUI.read_overlay_link`, with the same independent entry/return
boundaries; `overlay_license.BROWSER_LINKS_PLAN` declares its comparisons.
The finite `links='information'` binding composes Help, owned About entry and
all five About link readers. `overlay_license.INFORMATION_PLAN` and
`onpc_request_flow::overlay_information` qualify two independent round trips;
the shared fragment and `KioskRequestJourney` retain caller-owned capture and
return endpoints. Help is rechecked before entering About from the open menu.

`AccessibleUI.allowance_preset` owns the PARENT05 observation scope for both
direct preview calls and registered operations. Composed child, control, save
and label checks reuse a complete tree until input or a pending/failed read
invalidates it. Each independent call starts fresh; cancellation discards the
scope and retains any uncertain-input latch. The scope adds no process, bus,
storage or cleanup owner, so existing unit and UI parallel classifications apply.

Shared kiosk/overlay duration selection sets the canonical duration value and
waits for its independent public value readback. An accepted action may still
be completing; every retry reacquires ownership and readiness before the exact
form readback. Missing results, cancellation and ownership changes remain
terminal and never replay the input.

Multilingual request-history bindings use `AccessibleUI.language_history_request`
with explicit child, language, approver and request values. Station operations,
including Jordan's Custom text input, belong to `KIOSK_SESSION_OPERATIONS`;
overlay operations retain their child-desktop account. Qualify account routing
through the standalone observer entry, not only direct calls on a preview reader.
Both surfaces emit the existing form diagnostics, which `UiObservations.call`
decodes separately from its single final reply.

Parent, kiosk and child-overlay entry use
`AccessibleUI.complete_language_setup` through the parent/request wrappers.
It resolves the owned startup
dialog by public ID, activates Continue once and checks fresh closure/readiness.
`Automation.complete_parent_language_setup` and
`Automation.complete_request_language_setup` expose the same operation to UI
consumers. Existing cases therefore retain their original scope. Preview launch
owns the existing process and private bus as before; setup adds no new resource,
storage or cleanup lifetime and leaves the existing parallel classifications intact.

Before setting an account selector, request account selection checks startup
language readiness in its owned snapshot. If setup is pending, it uses the shared
language helper and reacquires the selector after confirmed completion; a selector
that remains disabled still refuses input.
The declared input language can already be Chinese from the child's desktop
setting. Reacquisition must retain that child and language after startup Save;
do not route an already translated form through an English-only account binding.
`kiosk-language-jordan-jamie-chinese` supplies case 254's finite approver input.
After choosing an account, it first confirms the chosen public UID and selector
description in a fresh owned snapshot. A newly
selected child's language dialog may disable the form; this read does not require
enabled controls. Only that proof permits the shared language helper's separate
Continue input. Discard the successful selection snapshot before observing
language readiness: a complete traversal can read the old readiness marker
before the new child's UID and translated description. Missing selection,
language completion or full form readback
keeps the selection terminal and prevents replay.
A complete tree is not a simultaneous view of all widget properties.

The station restoration qualification's return to Parent reuses
`onpc_parent::launch` with the fresh `return-desktop` receipt. Its separate
`return-parent-window` checkpoint uses the existing `switch-parent` observer
to require the owned active window before policy reads and child-picker input.
Shell desktop discovery and readable background controls do not establish
window activation. A failed command or active-window read stops the sequence;
neither is retried through another input route.

For the retained Parent picker after session return, shared child selection
sets `parent-child-selector` to the declared UID through the Application UI API
and independently reads selected-child identity and ready policy controls.
The shared Python recipe and Perl worker expose one selection route. Retained
`open`/`focus`/`selected` stage names mean the canonical setter, selected-UID
readback and ready-policy readback; they do not inject keys.
No popup, semantic focus or native focus proof is required. Failure is terminal
and never falls back to a different input route. Real GTK coverage preserves
policy-page reads both alone and after work in another owned preview window.
`test_parent_child_picker_after_language_policy_reads` in the
[language UI tests](../ui/test_language_settings.py) preserves that preceding
input/return history. Do not reduce this regression to a newly launched window
or infer selected-child success from setter acknowledgement.
The additional preview uses the existing private bus/display and owned cleanup;
UI parallel classification remains private. Unit doubles and waited Perl retain
their existing unit/cleanup classifications. Policy collection explicitly waits
for the public App Limits control before reading its rows.

Account selection acquires its initial complete snapshot through the bounded
read wait. A defunct node discards the whole request observation; the same wait
may reacquire before input or during offered/selected-value readback, retaining
the original deadline. Persistent staleness refuses, and no selector or choice
action runs inside a retry predicate. Fresh ownership, prompt and usability
checks still apply after reacquisition.
The first Custom, text or soft-app input after an overlay command launch uses
that same guarded readiness wait: launch submission alone does not establish a
ready form. Reacquire the complete target read, then deliver the choice once.
Parent wrong-entry qualification uses that same bounded read wait: query errors
and stale trees invalidate the observation, and only a fresh complete surface
refusal passes. Wrong ownership and an actually present request form remain
terminal; the refusal check delivers no input.

Native command launch acquires its session, desktop, window-absence and prompt
proofs inside the shared bounded read wait. A query error discards that complete
observation and retries only the preflight; a complete refusal remains terminal.
Desktop preparation can itself retire an accessibility provider, so
`AccessibleUI.native_launch_command` invalidates its earlier observation and
reacquires the whole preflight after `prepare_launch_desktop`, before submission.
Keep preparation outside the retry predicate too; an earlier successful desktop
read is not a current launch proof.
The launch command runs once outside the wait, with the uncertain-input latch
set before submission and independent window/activity readback afterward.
Native desktop-icon operations use the same bounded complete-read policy for
their window-absence preflight. A retiring unrelated provider discards that
observation; a complete existing-window refusal stays terminal. Focus, Ctrl+A
and Enter are never replayed by the read wait.
Native launch, live-owner comparison and attributed denial reads share
`accessible_ui.NATIVE_EXECUTABLES`. A new path needs its exact finite binding
through all three operations that the consumer uses: Allowed copy/use does not
qualify denial. Keep the denial reader's explicit role subset and its same-unit,
same-executable EXEC error checks; an exit status alone cannot prove policy denial.

Dedicated chooser checks opt out of automatic setup with
`launch_ui(..., complete_language_setup=False)`. The host and future installed
language tests reuse `AccessibleUI.language_scope`, `open_language_preferences`,
`choose_language`, `save_language`, `cancel_language` and
`language_save_completed`; the existing `localization_review.switch_language`
facade delegates to these operations too. They resolve only public IDs and
observe checked choices, readiness and closure independently of input success.
The Parent chooser reader discards a snapshot containing a defunct node and
reacquires through the shared bounded read wait. The original deadline, complete
ownership checks and input guards remain in force; persistent staleness refuses
and reacquisition never replays a language choice, Save or Cancel.
`parent_language_management` projects visible labels from the owned Screen Limits
page separately from the switch's accessible name. Callers compare each against
independent literal expectations; the English title and accessible name use
different capitalization. The read adds no input or resource owner.
`parent_language_state` retains the disabled/zero projection and adds explicit
Riley/Jordan enabled 60-minute English/Chinese bindings. The shared
`time_explanation` / `reach_time_explanation` read the declared language's public
text and durations; `app_rows(include_names=True)` includes bounded public names
in the same complete owned policy snapshot. Page navigation waits for public
App Limits readiness before reading. Callers own per-child immutable policy/name
captures, zero-grant assertions and finite elapsed-time comparisons.
`child_selection` shares the stale-safe closed-picker wait with `selected_child`
and independently resolves the selected UID/name. Parent language selection
bindings use that identity-only proof before their language-aware policy read,
without entering PARENT03's English-only allowance reader.
Normal Parent relaunch starts with the first alphabetically listed child; it
does not restore the closed window's selection. Bind the untouched reopened
state to that child, then select each declared child explicitly and compare
against its own immutable capture. Language persistence must not accidentally
assert child-selector persistence or invoke automatic first-run Save.
`language_fixture.py` supplies preview-only saved/read/save outcomes and tiny
caller-owned release files; it is not a substitute for installed persistence.
`read_kiosk_language` shares the bounded chooser reader while requiring the
dedicated station application. Its untouched first read reuses
`initial_kiosk_child` inside the same owned snapshot as the chooser; the fixed
Chinese first-presentation reader uses that same selected-child/result-child
identity guard. Parent-only child-control helpers do not accept kiosk IDs.
`ChinesePresentationMixin` owns the immutable notice/chooser/form comparisons
without inheriting an upgrade history. `ChineseCurrentInstallJourney` qualifies
the single current-package composition; `PackageCommand.package_identities` and
`observe_current_install` independently bind completion, version, same boot and
pre-existing preservation. The worker's `chinese_desktop_renewal`,
`chinese_initial_notice` and `chinese_initial_form` leaves serve both histories.
These add no live owner beyond the existing guarded envelope.

Installed-snapshot prerequisite checks use an owned installed observation:
`ChineseNativeAuthJourney` verifies assets at the public Parent checkpoint.
The product-free package-command context requires transferred package inputs
that this installed entry does not have. Missing assets must refuse before a reply.

`kiosk_language_form` independently reads button
labels and accessible names plus REQUEST03 values; neither reader performs
automatic startup Save. `kiosk_language_policy` observes the declared child's
settings, balances and application rows through public Parent controls.
Its Save-completion receipt establishes idle controls; `settings` separately
reads the allowance-bearing policy values. The receipt is not a settings snapshot.
`journey_blocks.language_selection` / `onpc_parent::language_selection` share
the chooser fragment across Parent and kiosk recipes. Callers retain literal
language expectations, response order and preservation endpoints. The
`installed-language` preview profile binds only synthetic account names to the
installed reader; it provides no installed persistence or policy evidence and
adds no resource or cleanup lifetime.

`read_overlay_language` and `overlay_language_operation` bind the same chooser
mechanics to the child application and active Riley session, retaining the shared
request IDs. Untouched and reopened reads require the fixed child's public UID;
the station reader continues to refuse child ownership. Shared
`kiosk_language_form(..., overlay=True)` reads translated REQUEST03 fields and
separate visible/accessibility text after independently observed readiness.
`kiosk_language_policy(child=CHILD)` reads Riley's saved allowance and app rows
through Parent; qualification comparisons permit natural daily-time usage.
The overlay preview's `installed-language` account projection and session double
qualify GTK readers only. They establish no installed persistence or policy result,
and add no resource lifetime or parallelism conflict.

Selected-child kiosk LANG01 reads bind `child` explicitly through the selected
public UID on every chooser boundary, including the post-Save/Cancel receipt.
`kiosk_language_form(language, child=...)` reads each child's translated form;
the default remains Jordan. `select_kiosk_account(..., child=..., language=...,
result_language=...)` separately binds the owning child/input language, exact
offered UID set, translated choice meanings and literal account names, then
independently reads the selected UID and resulting language. Approver changes
require equal input/result languages. Unknown selection or chooser effects are
terminal and are never replayed. The Riley operation aliases carry that identity
through registration and decoder validation; policy and per-child preservation
comparisons remain caller-owned. These mechanics add no resource or cleanup
lifetime; the existing preview process/display classification still applies.

Host support never establishes installed or customer acceptance. Guest execution
uses [system_assertions.py](../integration/system_assertions.py) for real-caller
batches, validated broker replies and authoritative account snapshots, and
[system_accounts.py](../integration/system_accounts.py) for the accepted guarded
identity creation/deletion protocol. The latter refuses collisions and identity
replacement and observes both NSS and AccountsService.

Register guest dependencies in `system_runner.AREA_SELECTED_HELPERS` so selected
staging and source provenance include them. Full selections stage identical
source/target declarations once; conflicting target declarations are refused
before copying files. Reuse the
[installed runner contracts](../integration/README.md#reusable-implementation-contracts)
for live ownership/transport/recovery and the [E2E contracts](../e2e/README.md)
for real graphical input, credentials, private collection and evidence gates.
These development helpers activate on the next invocation; there is no product
integration or saved-data migration.

External-provider public snapshots batch live `Accessible.Name` queries for already
discovered nodes. Those values live only within the same observation as the
structural facts and expire on input, retry, reset and snapshot exit. Ordinary
`get_name()` result reads remain uncached; provider `GetItems` names never supply
these observations. Protected descendants are still excluded before querying.

External-provider nodes absent from `GetItems` batch their fallback role and, when constructing
observation facts, state queries with identity/name reads. These fallback states
expire with the snapshot; input guards continue using uncached `get_state_set()`.
Query errors and malformed states still refuse the complete observation, and
every pipeline remains bounded to 64 RPCs.

Product snapshots instead come from the shared Application UI API inventory and
element operations. Their names, text, canonical values and capabilities remain
scoped to the pinned application/surface. Host and guest consumers must not
consult the accessibility tree to fill a missing product value or retry an API
refusal through a provider. Read waits may reacquire observations; input never
runs inside those retry predicates.

The complete `AccessibleUI.nodes` read boundary includes deferred product-label
projection after inventory traversal. If an application exits during either
read, discard the entire observation before bounded reacquisition. Preserve the
catalog's owner pins; an absent owner may disappear from a fresh inventory, but
a replacement owner cannot inherit its authority. Denied or uncertain operations
remain terminal. A complete child desktop is required before accepting overlay return.

`ApplicationUI` opens its own connection to the current
`DBUS_SESSION_BUS_ADDRESS`, preserving isolation between private preview buses
and installed user sessions. Its idempotent `close()` closes only that owned
connection; injected clients/connections remain caller-owned. Preview fixture
teardown closes the catalog alongside its external provider reader. Endpoint
owner/PID pins last for the catalog lifetime and require deliberate rebinding
after a product restart.

## Extend without hiding the scenario

When composing a named-child observer call, inspect the complete controller-to-guest
argument list, including padded optional slots. An empty trace-source slot means
no trace request, as in the named-child Parent toggle; normalize it at the shared
decoder before enabling a trace-bound guard. Preserve nonempty source validation
and child/save guards. Direct helper calls alone do not exercise that dispatch
boundary; use the existing installed consumer for affected validation.

Carry the explicit child binding through nested input helpers too. For example,
`child_countdown_animation(child=...)` passes that child to `set_toggle`; allowing
the inner guard to use its default Riley binding rejects Jordan's valid panel.
Trace both children through the outer read, setter and session guard before a
both-child journey. Keep wrong-account refusal and independent saved-value reads.

Graphical qualification workers must load their helper modules with compile-time
`use`, alongside the existing imports in `smoke.pm`. The loader's temporary Perl
library path is gone when `run` executes, so a runtime `require` can pass direct
module probes and still fail in the installed dispatcher. Exercise the actual
dispatch after removing that temporary path, as in the baseline app-effects
regressions, before starting installed qualification.

Revocation warning/Cancel uses `AccessibleUI.open_revoke_warning`,
`revoke_warning` and `cancel_revoke` in both the host preview and installed
qualification. Separate GTK dialog surfaces use the shared transient-owner
resolver, never a parent-window subtree assumption. `RevokeCancelJourney`
declares a real fixed kiosk grant, retained Parent return and two independent
Cancel entries; the controller validates public settings/time projections and
brackets balance reads before allowing a durable reply. `confirm_revoke` requires
explicit Confirm authority and rechecks the same owned warning; Cancel continues
to refuse confirmation. `saved_revoke_balances` waits for idle management,
reads complete public app rows and exact match values, returns to Screen Limits,
and independently awaits G=0 when requested. `request_composition.RevocationJourney`
accepts caller-declared read comparisons, retained-window pairs and approval
capture endpoints, and retains immutable settings, app rules and controller read
bounds. Consumers import that shared owner, keeping only finite histories and
assertions in their recipes. `RevokeConfirmJourney` / `REVOKE_CONFIRM_PLAN` and
Cancel compose `journey_blocks.revocation_entry` /
`onpc_time_explanation::revoke_entry`, with separate response histories;
Confirm never derives its entry by filtering another response plan. Endpoint
renaming retains the fixed qualified child/15-minute/75-second binding.
Both balance readers use `reload_revoke_settings` to reselect the fixed child
through the public selector after a wrong-entry check. Loading the policy/time
inside the controller read bracket avoids treating Parent's 30-second cached
display as freshly calculated. Before changing elapsed-time tolerances or adding
waits, check when the public status was actually loaded; an independent API read
can still return a cached displayed balance. Reuse the guarded reload inside the
read bracket for this binding. Selector navigation changes neither grant nor
saved policy; elapsed limits and mutation/refusal assertions remain unchanged.
The grant-access cases use `time-explanation-refresh-read` for the same reason.
Retain `UiObservations.read_bounds` for both refreshed endpoints when comparing
grant countdowns. The guest's `observed_monotonic_ns` is stamped after reading
the display, rather than when Parent loaded its status; unequal read delays
must not become grant consumption. Compare against the complete elapsed
interval, retaining the case's precision, daily-balance and original-grant checks.
`tools/test-vm --vm NAME reproduce-daily-soft-balance` reuses
`DailySoftExpiryJourney` and its activity fixtures through Parent's away wait,
then retains the return-balance scene and both controller read brackets before
the comparison. It supplies no acceptance credit; finish with
`tools/test-vm --vm NAME stop`.
For no-grant revocation after an actual soft-app approval, establish G=0 before
opening Revoke and keep that observation separate from Confirm's result. Case
160 uses the qualified limits off/on transition and then reads positive daily
time with G=0. An allowance edit alone preserves the running grant and cannot
prepare this branch. Keep the original Allowed/Soft captures across the
transition so Cancel preservation and Confirm closure refer to the same work.
These operations add no process, storage, bus,
display or cleanup owner. Renamed-endpoint, immutable-window and durable-reply
regressions use the existing private recorder fixtures; existing unit/cleanup/
preview classifications remain applicable. The [catalogue](../../docs/TestAutomation/E2E-Building-Blocks.md#revocation-warning-and-cancel-qualification)
owns qualification status.

Both-child request-transfer histories reuse `request_flow.transfer_allowances` /
`onpc_request_flow::prepare_transfer_allowances` for public allowance setup,
independent child reads and the guarded greeter return. Forward and reverse
cases and qualifications share this pair; keep each consumer's choice values,
visit order and immutable comparison endpoints in its plan. Follow
[composition preflight](../../docs/TestAutomation/E2E-Building-Blocks.md#composition-preflight)
for declaration/worker order and refusal boundaries.

FLOW12 overlay-to-kiosk declarations use `request_flow.overlay_to_kiosk` and
`onpc_request_flow::overlay_to_kiosk`. The caller supplies a fresh source receipt,
child and invocation prefix; the shared operation owns normal Cancel, child
desktop/greeter return, station entry and untouched destination read. Declare
`JourneyPlan.request_transfer_checks={destination: source}` for
`KioskRequestJourney` to compare immutable child-owned duration/custom/soft-app
values while independently validating the local approver. Finite public leaves
in `AccessibleUI.transfer_choices` bind Riley or Jordan through every overlay
reader/input/session guard. Qualification status belongs to FLOW12's catalogue
row. The existing unit owner uses private values/files and bounded waited Perl
children; resource classifications remain compatible with no new cleanup owner.
The wrong-surface refusal reads the complete owner-pinned product API catalogue.
It releases no input and does not traverse unrelated desktop providers; a
disappearing external AT-SPI owner cannot prevent this product-only guard.
Overlay input targets reject a mismatched OS account before discovering UI.
The wrong-child qualification therefore establishes the existing UID refusal
without depending on an unrelated desktop provider remaining alive; matching
accounts still pass the full surface, selection, ownership and input guards.
The `choices='remembered'` declaration selects the recipe's Jordan 75-second /
included and Riley 150-second / excluded values, with Jamie at the station and
the other eligible parent on each overlay. The `remembered-*` operations reuse
those same guarded leaves; complete cases own their order, return visits and
immutable comparisons rather than importing the qualification plan.
Case 58 visits each overlay once and compares both destination reads with the
original captures, then reselects both children in the open kiosk and compares
again. Its persistence/isolation result requires no retained child-desktop login.
Case 59's `choices='remembered-second'` binding swaps the primary child and
finite values: Riley 75 seconds/included, then Jordan 150 seconds/excluded.
Both overlays still use the other eligible parent and the station uses Jamie.
The shared worker follows the caller's declared fresh-entry order and repeats
that order for the kiosk readbacks; the original case and diagnostic plan retain
their order. Host checks cover both bindings, all refusal checkpoints, immutable
comparisons and actual child-account reader/input guards.
The historical full return scene is preserved only as `DIAGNOSTIC_PLAN` for
explicit maintenance probes; it supplies no customer acceptance prerequisite.
The reverse declaration `request_flow.kiosk_to_overlay(..., choices='remembered')`
selects those same recipe values and local approvers, preserving the default
qualification binding. Case 60 uses `remembered_choices.REVERSE_PLAN` and
`onpc_remembered_choices::run_reverse` to seed local overlay approvers, capture
each kiosk source and compare untouched transfer and fresh overlay reentry
results against it. Ordinary logout avoids incidental retained-login requirements.
Case 61's `remembered_choices.REVERSE_SECOND_PLAN` uses the same worker with
Riley/Jordan order for seeds, transfers and fresh revisits, and
`choices='remembered-second'` for Riley 75 seconds/included and Jordan
150 seconds/excluded. Its second station entry uses
`remembered-second-reverse-kiosk-jordan-select-default`, retaining Jamie after
Riley's earlier selector save. Both complete cases declare four immutable
comparisons against the original station captures. The existing private
unit/cleanup resources and preview display classifications remain applicable;
no new resource owner is introduced.
Case 60's second station entry uses `remembered-reverse-kiosk-riley-select-default`:
Riley's untouched default request values must retain the kiosk's Jamie selection
saved during Jordan's visit. Fresh-station seed bindings still require Casey.
Before binding an untouched default read, trace the last selector save for the
requesting OS user through the declared history. Changing the selected child
does not reset the kiosk user's remembered approver. Exercise that preceding
save/child-selection history in the host reader/decoder check before live
acceptance; a fresh-form fixture alone cannot catch a wrong later default.
Kiosk custom/text/soft inputs reuse `AccessibleUI.transfer_choices`, including
the same child, owner, availability and uncertain-input guards. These bindings
introduce no new resource or cleanup owner; existing private unit fixtures and
bounded waited Perl classifications apply.
The qualification and its request-form regressions share VM-specific,
fixture-source-bound package inputs. Their maintained preparation selects DEB or
RPM from the verified baseline and preserves existing immutable bundles. Planning
tests replace allocation with a private double so they cannot leave an empty real
bundle for an installed consumer.

Explicit desktop entry pairs `journey_blocks.desktop_entry` with
`onpc_desktop_session::enter_desktop`. Callers bind account, source, mode,
expected result and an independent invocation prefix. Shared read-only
`session_control.entry_identity` proves fresh absence, retained locked entry,
same-user desktop or actual lock entry before transition/authentication; it
never repairs a mismatched mode. GDM and lock-screen proofs remain separate.
Named worker scopes retain the exact controller acknowledgement prefix, so
lock recipient proofs cannot be borrowed from an unscoped or other invocation.
`retained_entry` supplies Task 044's finite two-child/Parent history and immutable
session/activity comparisons. The [catalogue's both-child scope](../../docs/TestAutomation/E2E-Building-Blocks.md#both-retained-child-desktops-and-explicit-entry-modes)
owns its qualified bindings. Host checks use existing private values/recorder files and
bounded waited Perl children; unit/cleanup classifications remain compatible,
with no new storage, display, bus or VM cleanup owner.

Retained Parent declarations use `journey_blocks.retained_parent_entry`, and
retained activity input/readback uses `journey_blocks.native_activity_resume`
with the existing worker pairs. `journey_checks.RetainedDesktopJourney` owns
immutable Parent page/settings/window and session comparisons. Callers declare
`parent_expected`, `parent_checks`, `window_checks` and `session_checks` endpoints;
the shared engine validates order and account-compatible session operations,
rejects missing/replayed captures and compares before the durable reply.
Keep expected values and comparison endpoints in each recipe, rather than
inheriting another qualifier's checkpoint names. Capture the incoming Parent
page and child before the explicit Screen Limits read; returning to an existing
window must not reselect the child to repair a mismatch. Desktop identity and
window endpoint/PID are independent preservation results.

Retained-child histories use `journey_checks.RetainedSessionJourney` with
caller-declared `session_checks={later: earlier}` endpoints on the existing
`system:child-retained-locked` operation. The shared engine preserves allowance
checks, stores the immutable session identity and refuses changed, missing or
replayed observations before the recorder reply. `desktop_session` supplies
the two denial plans and their finite endpoints; future consumers bind their own
names instead of inheriting a qualification's checkpoint comparison.
This observation requires the greeter to be the sole active graphical session,
as well as an inactive, locked child desktop. If Parent is still using the
computer, complete Parent's shared `desktop_return` and its independent greeter
result before capturing the retained child. A locked child alone does not meet
the entry guard. The replacement-time cases in
[expired_daily_replacement.py](../e2e/expired_daily_replacement.py) use that order
before waiting for the original grant to expire.
Lock declarations/execution already share `journey_blocks.lock_challenge` /
`onpc_desktop_session::observe_lock` and `lock_recipient` /
`onpc_desktop_session::lock_recipient`. The
[qualified lock and denial scopes](../../docs/TestAutomation/E2E-Building-Blocks.md#desktop-and-retained-session-entry)
own their distinct native-lock/GDM results and provider bindings.
The desktop/session regressions exercise both denial recipes and an independent
renamed comparison through the real recorder, including refusal before durable
reply. They use process-local values, private pytest files and existing waited
Perl children; unit and cleanup classifications stay compatible with no new
resource owner.

Personal-language histories use
[`language_composition.language_journey`](../e2e/language_composition.py) with
caller-declared checks. Use `public_language_value` for complete literal chooser
and request-form comparisons, and `language_policy` for named immutable policy
captures and later comparisons. Recipes supply the expected labels, excluded
labels, account values, capture endpoints and elapsed-time budget; the shared
check preserves zero-grant and naturally decreasing daily-balance assertions.
Keep those values in the consumer instead of copying a comparison subclass.
For Parent desktop-entry names that follow the selected language, declare
`app_names_capture` at the first read in that language and `app_names_same` at
its later comparison. Account names, app IDs and rules still compare against
the original policy capture; returning to the original language compares its
names too. Do not remove names from preservation checks or translate the
captured oracle. Case 256 supplies these separate endpoints; the
[language recipe](../../docs/TestAutomation/E2E-Scenario-Recipes.md#e2e-055)
owns its finite values and comparisons.

`public_language_value` also compares declared chooser/dialog presentations and
feedback projections, with optional caller-named `capture`/`same` endpoints.
It copies nested public values and refuses missing or repeated captures before
the recorder reply. Parent dialog visits share `onpc_parent::dialog_visit` for
qualification's separate read, `dialog_use` for a customer visit whose opening
already reads the contents, and `dialog_close` for owned closure. Recipes retain
visit count, language and assertions. Case 256 composes `dialog_use` with the
enabled-policy checks and `onpc_parent::language_save`; it does not copy the
qualification's chooser or repeated-read matrix. Its safety checks use private
files/values and waited Perl children,
compatible in both unit and cleanup inventories; no new live owner is introduced.

`offline_language_actions` reuses the lease's existing Internet isolation and
recovery owner. Bind its stages to public installed-policy observations before
the action. An installed-snapshot history has no transferred installer, so its
connectivity checkpoint must not require a package-command context. Failed
policy observation must refuse before connectivity input; recovery remains
independent. These helpers add no storage, process or cleanup owner.

Continuous package histories use `package_lifecycle.record_lifecycle_journey`
with caller-declared operations, actions and comparison endpoints. Its shared
journey composes the existing package/transfer/recorder envelope and runs public
checks before publishing a reply. `journey_checks.access_choice`,
`policy_projection` and `request_choices` bind literal expectations and immutable
named captures; saved settings/rows are separate from naturally changing usage
and explicitly checked grants. Missing captures, changed results and replay
refuse. Recipes keep values, order, phase boundaries and assertion names.
`journey_blocks.prefixed_stages` and `custom_allowance` pair with
`onpc_journey::scope`, `onpc_parent::named_management`,
`onpc_gdm::named_login` and `onpc_allowance_boundaries::custom_value` for repeated
independent entries and ordinary edits. Prefixes rename checkpoints, not account
identity; declared challenges and independent selection/readback remain required.
These add no storage, process or cleanup owner. The existing private unit and
cleanup classifications remain applicable.

Unrelated-package histories use `package_install.unrelated_journey` with named
clean-entry and independent-result endpoints. Task 305a's completed qualification
reuses that engine and `submit_unrelated` / `observe_unrelated`. The engine copies the
complete public package/preservation witness, refuses changed identity or replay,
and declares verified attempt assets through `AssetTransfer` on installed
snapshots. After restoration and fresh helper provisioning, `provision_installed`
copies the fixed payload with exclusive destination creation, root ownership,
descriptor/digest/tree guards and independent read-only verification before the
setup reply. Offline product-free transfers retain their existing route. The
installed product and activation remain in the snapshot.
`journey_blocks.restart_request_usability` / `onpc_customer_reboot::restart_request_usability`
pair fresh child/station entry, public no-modal usability and normal Cancel/
greeter return. Caller prefixes retain distinct observations and authentication
challenges. The kiosk leaf selects Jamie before its independent Jordan/Jamie
guard. Host checks use private recorder/transfer doubles and waited Perl/title
files; existing unit/cleanup classifications apply with no new live owner.

Package lifecycle declarations reuse `journey_blocks.package_installation` in
case 2 and LIFE04 qualification; LIFE02, genuine upgrade and Chinese lifecycle
plans inherit that same fragment. It declares fresh administrator entry,
submission and separate readback without a reboot or wrong-entry exercise.
Callers retain phase boundaries, assertions and current/previous package binding;
`PackageCommand` and `package_install.submit_release` / `observe_release` own
the guarded command and independent result. The fragment adds no resource or
cleanup lifetime; existing unit/cleanup classifications remain applicable.

Update consumers reuse `package_upgrade.install_previous_release` and
`activated_entry` for the earlier installation and its independently observed
activation reboot. Keep these mechanics in the shared lifecycle owner rather
than importing them from a runnable qualification or copying them into a case.
`upgrade_entry` adds the qualification's replay/artifact refusals around that
same activation operation; consumers retain their own plans, saved settings,
grant comparisons and final outcomes. Check the intended update profile against
the [shipped activation manifests](../../docs/TestAutomation/E2E-Building-Blocks.md#no-action-package-update)
before VM input; a source change or increasing package version alone does not
establish which activation the update requires.
Bind guest package readback to the verified profile's exact pair; the ordinary
historical-release version is not the version of a finite activation profile.
Preserve that historical check for its own inputs rather than relaxing it globally.
For a child's saved preference after reboot, prove freshness with the changed
boot and new public read, as in `ActivationRebootJourney`; guest monotonic values
from different boots cannot establish observation order.

The process and session update cases share `update_process_case` as one finite
test family, with distinct `PLAN` / `SESSION_PLAN` and executable entries.
Keep their saved-rule, original-grant and request assertions together rather
than importing a runnable case from another case module. Their package, desktop,
app, approval and fixture mechanics continue to use the shared owners above.
Both journeys follow the
[session-update preservation boundary](../../docs/TestAutomation/E2E-Building-Blocks.md#session-update).
GNOME's dynamic greeter account can retire during sign-in; do not accommodate
that transition by filtering package account inventories.

`restart_notice.RestartNoticeJourney` adds the three fresh-install modal bindings
over that package fragment and the shared fresh-desktop/station entries.
`AccessibleUI.restart_notice`, `restart_action`, `restart_closed` and
`restart_usable` share the public-ID route with the real GTK modal test.
The notice can arrive before the request's own-account load; the exact application
owner and, for the overlay, active fixture session bind that early read.
Language setup is permitted only in the postboot usability operation.
Fresh-install consumers must declare the prerequisites of each postboot result;
a successful reboot does not enable child controls. Observe the untouched
notices and disabled defaults first, then establish request eligibility through
shared public Parent operations before requiring enabled Request. In this
qualification, after the verified reboot and Parent's missing-modal refusal,
canonical child selection and FLOW02 save enabled 30-minute allowances for
Riley and Jamie before fresh Child App and default kiosk entries. Keep this
setup after the notices; never relax the enabled-Request assertion to accept
the fresh installation's disabled defaults.
`JourneyPlan.modal_reboots` pairs an exact surface read with the adjacent fresh
GDM result. `UiObservations.submit_restart` consumes once; a bounded terminal
stream permits transport uncertainty only after the exact boot/surface readiness
record. Independent boot-change and fresh-GDM observations supply acceptance.
No command reboot fallback or input retry is allowed.
The existing customer-reboot unit/cleanup module retains private fixtures and
waited Perl/isolated-Python subprocesses with bounded timeouts; the existing
error-feedback UI module retains its private display and stubbed reboot callback.
These additions share no VM or product process and add no host resource owner.
The existing unit, cleanup and UI classifications remain applicable.

`journey_checks.restart_instructions(surface, texts)` copies a caller's literal
installation-neutral text oracle and checks the fresh public modal's exact
surface, instructions and blocked-policy result before a durable reply or reboot.
Complete Parent case 257 composes it with `record_package_journey`, the existing
modal submission and fresh administrator entry; its recipe owns stages, values
and seven assertions. The existing clean-install unit/cleanup owner verifies real
worker order/titles, refusal stopping and the recorder's package constructor,
using private evidence and bounded waited Perl children without new resources.

`journey_blocks.restart_reentry` / `onpc_customer_reboot::restart_reentry` share
Close, normal overlay exit and same-boot reopening between qualification and
complete Parent/Child App/kiosk histories. The kiosk binding shares normal
result exit, same-boot GDM and renewed station entry with LIFE07 qualification.
Case 259 retains its own genuine installation, first kiosk notice, single kiosk
reboot, postboot disabled-default Jordan read/public enabled 30-minute setup,
and fresh usable Jordan/Jamie selectors plus Request without the modal.
`journey_blocks.restart_kiosk_usability` /
`onpc_customer_reboot::restart_kiosk_usability` select Jamie with the existing
Jordan/English public account operation before the unchanged final selection
guard. They share this finite input/result with LIFE07; preserved eligible
baseline administrators do not imply Jamie is the initial approver.
The same existing private fixtures and waited Perl children cover the kiosk
worker order, real package recorder entry and independent reentry consumer;
unit and cleanup classifications remain compatible with no new resource owner.
Case 258 retains its own initial child
entry, overlay reboot, postboot Riley disabled-default read, public enabled
30-minute setup and fresh fixed-child request result. The clean-install safety
owner checks both complete worker orders, real recorder construction, literal
modal refusal before reply/input and an independent reentry caller. It retains
pytest-private evidence and bounded waited Perl children, with no new process,
storage, bus or display owner; existing compatible unit/cleanup classifications
remain applicable. No product or host resource lifetime changed.

Native activity transitions reuse `journey_blocks.native_activity_entry` /
`onpc_app_rows::native_activity_entry` for
launch/use/capture and `native_activity_resume` for an independently observed
original window's next submission. Cases 44/45 and overlay qualifications share
the entry operation; callers retain transition, immutable comparison endpoints,
reread and close. Invocation prefixes determine both controller checkpoints and
actual worker titles. The helpers add no process, storage or cleanup owner and
never relaunch during resume. Keep the existing complete-order/failure-stop
checks alongside an independent caller with renamed prefixes.
The resume declaration's `binding='policy-soft'` selects Riley's existing Soft
window and its guarded Submit/readback, using the same worker operation as the
ordinary activity binding. Daily-expiry cases 164–166 and retained replacement
case 135 share it; captures, original-window comparisons and any close stay
with each case.
The default command activity explicitly selects the root-owned trusted activity
fixture. The same entry helper's `binding='policy'` and `binding='unmatched-soft'`
select Jordan's existing A primary and S secondary command activities, including
their independent captures; ordinary APP01 policy and grid launches retain A.
These finite bindings reuse the existing app/owner/input guards, not the trusted
activity fixture's launch. Cases 13/14 keep their six transitions, captures,
nonmatching use and Riley continuity assertions in their case. Journey setup
uses `NativeFixtures(profile='activity')` for read-only source, receipt,
metadata and loaded file-trust verification. Preparation alone admits the
finite executable/runtime inventory. Host regressions extend the existing
private unit/cleanup doubles and existing builder's sequential compiler work;
they add no shared host path, live database, VM, bus or display owner.

Distinct-user retained histories compose `journey_blocks.retained_app_activities`
/ `onpc_app_rows::retained_app_activities` for a finite user/entry list, then
`retained_app_visit` in those same owners for each return. Use
`RetainedDesktopJourney` with caller-declared session comparisons;
`JourneyPlan.activity_entries` requires the earlier capture before entry input,
and `activity_checks` compares the original window and draft before resumed
Submit. Do not copy `retained_app_visits.PLAN` or run its qualification as setup.
The [qualified scope](../../docs/TestAutomation/E2E-Building-Blocks.md#distinct-user-retained-app-qualification)
owns available bindings; same-child multiple desktops remain separate.

Shell authentication declarations reuse `request_flow.overlay_authentication`
for Cancel, fixed approval or rejection, paired with `onpc_request_flow::shell_cancel` /
`shell_approve` / `shell_reject`. Tasks 048c/048d/048f compose this fragment with
`KioskRequestJourney`; form preservation, desktop return, activity endpoints and
assertion phases remain caller-owned. Declaration checkpoint renaming alone
does not parameterize the approval worker or qualify another request/provider
binding; use the [approval scope](../../docs/TestAutomation/E2E-Building-Blocks.md#overlay-approval-and-automatic-return-qualification)
and [rejection scope](../../docs/TestAutomation/E2E-Building-Blocks.md#overlay-rejection-and-cancel-qualification).
The rejection worker accepts renamed endpoints while retaining the fixed request,
two same-challenge recipient proofs, one sealed wrong password and one submission.
Only explicit owned denial and a fresh empty masked retry field release Cancel;
the caller separately compares preserved usable no-error form choices.

`request_flow.overlay_approved_request` / `onpc_request_flow::overlay_approve`
compose fixed overlay FLOW05 with declared automatic or immediate return.
`overlay_rejected_request` / `overlay_reject` compose FLOW07 with an independent
before/preserved form comparison and leave the form open. A subsequent FLOW05
is a deliberate new challenge, permitted only after dismissal and usable form
readback; challenge identities and both secret deliveries remain single-use.
The immediate success observer takes only the owned `kiosk-result-action`
through the Application UI API after explicit success and authentication
absence. The caller still compares the original usable activity. These helpers
add no storage, process or cleanup owner; existing private unit/cleanup resource
classifications remain applicable. Installed qualification is tracked in the
[catalogue](../../docs/TestAutomation/E2E-Building-Blocks.md#overlay-approval-and-automatic-return-qualification).
Case 46 composes that same immediate approval with the existing native activity
entry/resume worker and `KioskRequestJourney` countdown comparison. Overlay
countdown plans may use the finite `estimate` binding: the captured public
estimate is independently bounded against the earlier Parent balance and elapsed
time before comparison. Repeated kiosk approvals after child use or an active
grant also bind each countdown to that request's fresh immutable estimate, as in
`flatpak_temporary_access`. Keep the journey's independent estimate checks;
the initial unused-child balance no longer describes those later requests.
Fresh unused-child kiosk histories retain their explicit numeric expectation.
Host regressions exercise immutable capture, stale/missing/replayed results,
refusal before durable reply and complete worker titles/failure stops. These
extend existing private pytest fixtures and bounded waited Perl children without
new storage, process, display or cleanup ownership; both existing unit modules
retain compatible scheduling classifications.

E2E declaration fragments and worker execution have matching shared owners:
`journey_blocks.parent_reopen` / `onpc_lifecycle::reopen` for LIFE01,
`request_flow.daily_station_entry` / `onpc_request_flow::daily_station_entry`
for the qualified 15-minute preset and station entry, and
`match_rules.match_edit` / `onpc_app_rows::match_edit` for editor replacement and
Save. They preserve caller-owned phase boundaries, expected values and exits;
the [catalogue](../../docs/TestAutomation/E2E-Building-Blocks.md) owns binding
scope and qualification. Reuse these fragments in both cases and qualifications
instead of copying their stage maps or creating a plan-only comparison subclass.

Allowed and blocked native-launch histories compose `policy_edits.policy_edit` /
`onpc_app_rows::edit_policy`, `journey_blocks.desktop_entry` /
`onpc_desktop_session::enter_desktop` and `journey_blocks.native_usable_app` /
`onpc_app_rows::native_usable_app`. Blocked histories use
`journey_blocks.native_blocked_app` / `onpc_app_rows::native_blocked_app`
for the denied child, then the usable operation for the unaffected child.
Bind Jordan's Parent selection with `parent_management(child='existing')`;
retain the caller's `existing-returned` read for initial settings rather than
copying the child-picker operations. Use `AppPolicyJourney` with caller-declared
`settings_checks`, `balance_checks`, `match_checks` and `access_checks` rather
than a case-local comparison class. Keep one family execution function for
the recorder, fixture actions and comparison class; grid callers add only their
qualified fixture context before calling it. Cases 62, 64, 66 and 81–84 share
these operations and one worker; their recipes retain control state, account
order and assertion phases.
The [catalogue](../../docs/TestAutomation/E2E-Building-Blocks.md#application-routes-and-complete-customer-journeys)
owns the exact qualified fixture/route bindings.

The standalone command and grid qualifications in `native_app` and
`native_grid_usable` also compose `journey_blocks.native_usable_app`; their
independent-entry/refusal order and normal close checks remain local. Reuse this
same declaration instead of copying its launch/use stage map into a qualifier.

Files consumers use that same block with `route='files'`; it includes the bound
child's empty-app desktop read before the guarded Files selection and launch.
When retaining another fixture window, declare the appropriate desktop read
locally and pass `desktop_observation=False`, as in `native_files_usable`'s
separate-window history. Keep Files dismissal distinct from fixture-window
closure and preserve each caller's capture/comparison order. Fixture role A
uses `role=None` regardless of its saved Allowed, Hard or Soft policy; denied
Files access uses `native_blocked_app('A', route='files')`. Reuse the
[qualified Files bindings](../../docs/TestAutomation/E2E-Building-Blocks.md#native-files-launch-and-separate-windows)
instead of substituting a command launch to establish a Files result.

For the clean disabled binding, compose `onpc_parent::open_for_child` and check
the selected child's untouched limits-off/zero-allowance result before editing
app policy. The enabled binding instead uses `onpc_parent::set_allowance` and
independent saved settings/balance reads. Do not copy enabled preparation into
the disabled history or enable then disable limits to reach its starting state.
Prove the other child's unaffected access through the same target and route
with its own window/Submit/result, leaving its policy untouched.

Keep expected outcomes, case tables, fault injection and independent oracles in
the owning tests. The broker state-machine model intentionally has independent
state and assertions. Standard `tmp_path`, `monkeypatch`, `unittest.mock` and
`TemporaryDirectory` already supply reusable behavior and need no style wrapper.

For automatic account-removal results, keep the original Parent window and read
its selection or empty state without refreshing or operating the picker. Check
control availability as well as the explanation: visible empty content alone
does not prove stale controls were disabled. If background status polling races
account discovery, inspect both paths; a stale-target error is dismissible only
after a fresh successful eligible-account read confirms that target is absent.
The delivered [account-change cases](../e2e/account_changes.py) retain these
independent results; successful fixture deletion alone supplies no product result.

Build external authentication tree fixtures from the qualified provider's
catalogue and observed message branch, independently of the adapter's expected
strings. Bind the provider version, locale and authenticating/session roles:
Chinese MATE in the kiosk uses the super-user explanation, not its same-user
or multiple-identity explanations. Preserve that distinction and refusal before
secret input. A fixture copied from the adapter's oracle cannot detect a shared
wrong expectation.

Import fixtures explicitly instead of loading every helper as a global plugin.
Include dependency fixtures in the consumer too; aliases can disambiguate names.
Helpers must not import collected cases, mutate the desktop at import time or
infer process ownership from names/environment variables.

`child_shell.run_child_shell` owns a headless GNOME Shell through the shared
lifecycle runner and its subreaper guardian. All consumers share the private
Wayland output, bus, settings, copied extension payload and bounded cleanup.
Use the Application UI API for real panel/overlay reads and input; do not add
an outer desktop, Devkit viewer, screenshots or display-geometry acceptance to
these semantic checks. Interactive child previews keep their separate visible
viewer path in the same orchestration library.

Preserve required product coverage and admitted shared dangerous-action/core
checks during extraction under the [test scope mandate](../../docs/Mandates/Test-Scope-Mandate.md).
Do not preserve or recreate excluded non-product suites merely to retain their
old test names, parameter IDs or matrices. Validate affected callers
at the [lowest effective scope](../README.md#all-established-regressions), retaining
required acceptance and selectors; extraction alone does not require unrelated suites.
Changed dangerous cleanup or ownership boundaries use their existing focused
shared regressions. See [test maintenance](../README.md)
for authorized launchers and evidence boundaries.
