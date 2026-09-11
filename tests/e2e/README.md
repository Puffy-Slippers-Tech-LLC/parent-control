# E2E inventory and runner contract

Host-only regressions reuse the [shared support library](../support/README.md)
for evidence, provenance, recording, credentials and private metadata fixtures.
Those synthetic fixtures are separate from the live helpers described below.

`scenarios.json` is the versioned inventory for
[E2E coverage](../../docs/TestAutomation/E2E-Coverage.md): 33 families and
157 variants. `E2E-001/gdm-observation` is registered for public execution;
the other 156 variants remain **pending**.
[Task 19B is accepted](../../docs/TestAutomation/Evidence/19B-Acceptance-20260908.md)
after three complete, visually reviewed public qualifications. This establishes
runner-smoke behavior, not customer acceptance.
[Task 19A is accepted](../../docs/TestAutomation/Evidence/19A-Controller-Acceptance-20260907.md).
Its former E2E-034/serial-controller declaration is superseded by E2E-001,
which retains controller preparation, credentials/assets, command, continuity
and final evidence assertions and adds stable screen proof. Historical E2E-034
results retain their original identities; ordinary suites execute one smoke.

The shared worker has guarded live evidence for graphical input, fixture
credentials, asset transfer, GDM authentication and a real serial command.
Standalone qualification reports retain their diagnostic scope. Public ready
Python callbacks use the same worker through `ScenarioRecorder`, the existing
lease bridge and the `EvidenceContract` gate. Listing and pending-case refusal
remain host-safe; a listing is never an execution pass.

## Inspect scope on the host

From the checkout, these commands only read declarations and print JSON. They
need no root, package artifacts, installed product, graphical tools or VM:

```sh
tools/run-tests e2e --list
tools/run-tests e2e --list --scenario E2E-023
tools/run-tests e2e --list --scenario E2E-023/fullscreen
make check-e2e LIST=1 SCENARIO=E2E-023/fullscreen
```

An omitted selector lists every category, family and variant, including pending
work. An exact family selects all its variants. An exact `E2E-NNN/variant`
selects one case and is partial, even if the family currently has one variant.
Any explicit selection is partial relative to the full inventory. Empty,
unknown, wildcard, prefix and comma-separated selectors fail with exit 2.
The lower-level `inventory.py --require-runnable` command also refuses any
selection containing a pending variant; it still only lists and never executes
anything. Pending cases are never silently filtered to obtain a successful selection.

`tools/run-tests e2e --artifacts /tmp/onpc-... --scenario E2E-002` and
`make check-e2e ARTIFACT_DIR=/tmp/onpc-... SCENARIO=E2E-002` fail with
`selection:pending`, before artifact access, privilege checks, cleanup tests,
worker imports or VM operations. Omitting the selector checks the entire
inventory. `LIST=1` rejects artifact arguments; other nonempty `LIST` values and
all nonempty `VM_IMAGE` values fail. Make forwards selector values through the
environment, so they cannot become recipe shell commands.

Both the unprivileged category launcher and installed dispatcher invoke the
same `runner.preflight`; refresh the latter with `./setup.sh --test-tools-only`
after dispatcher changes. Development activation is `none` (next invocation),
with no product or saved-data changes. Missing/unsafe inventory inputs fail
closed. A fully ready selection requires existing safe artifacts and Python
controller callbacks. The other 156 cases still refuse as pending.
There is no bypass, checkpoint or resume option. Listing
success is declaration inspection, never an E2E pass.

The JSON includes canonical case IDs, owner, status/reason, parameters,
environment, prerequisites, duration bound, ordered phases, assertions,
expected evidence and the SHA-256 of the exact inventory bytes read. This digest
identifies the declaration only. `provenance.VerifiedInputs` separately identifies
current source, requirement mappings, staged packages/assets and the verified
baseline's guest preparation. Execution dispatch must use that capture.

## Maintain declarations

Run the canonical smoke with
`tools/run-tests e2e --artifacts /tmp/onpc-... --scenario E2E-001` using fresh
verified build artifacts. Its callback reuses the qualified serial worker and
records nine acknowledgments before the next guest action: readiness, initial
GDM, selected empty prompt, Escape return, serial password boundary,
authenticated serial session, command output, logout, and graphical return.
The fixed `boot` observation independently hashes the actual kernel boot
identity; all nine must agree. No session identity is fabricated.

E2E-001 retains its stable `step-1`/`step-2`/`step-3` IDs for graphical
readiness, serial interaction and final graphical evidence. Each observation
gets a durable recorder checkpoint even when several belong to one step.
After worker shutdown, the final step validates the completed public module's
ordered needle matches and requires the return match after the recorded serial
logout. It reads only those private PNGs to retain dimensions and SHA-256;
raw captures, terminal output and arbitrary module fields are never exported.
Identical initial/return pixels are allowed: serial does not change GDM.
Post-password explicit capture remains sealed; this uses the automatic private
match result and does not introduce a new screenshot route.

The sole canonical smoke is harness coverage, with no product requirement IDs
or customer acceptance claim. Host/source/baseline preservation and held-lease
terminal evidence remain the existing controller's responsibility. Test-tool
activation is `none` (next invocation); no setup or product data change is needed.
Before a scenario recorder exists, the invocation retains reviewed, fixed
provenance refusal codes through cleanup. Unknown exception text stays private
and produces `execution:attempt-failed`; a later cleanup failure cannot replace
the first refusal. A source-change refusal requires an unchanged checkout for
the next complete attempt, including preparation and terminal collection.
Before lease acquisition, the controller fsyncs a private
`input/selected-inputs.json` containing the source preflight identity, inventory
identity and exact case. The shared SSH bootstrap binds its guest observation
marker to that document's digest. This preparation input is required even for
a product-free case; `VerifiedInputs` still independently verifies the full
source/package/baseline contract under the lease.

Schema version 1 has common family declarations inherited by each explicit
variant. Every variant has a stable ID and one canonical owner from the
family's related tasks. There is no runtime Cartesian expansion or duplicate
execution for related owners. Dimensions enumerate required values;
`full_combinations` names interacting groups whose entire product must appear
in explicit variants. Validation rejects missing values, missing combinations
and duplicate combinations. Independent sequential boundary checks belong in
the ordered steps and the matrix rationale. Owning tasks must audit and expand
this starting matrix before acceptance; declared matrix closure is not proof
that every product requirement or transition has been enumerated.

The first 29 families come from the required coverage table. E2E-030 adds
installed About/license access; E2E-031 covers feedback drafts, validation and
attachment/diagnostic review; E2E-032 covers authorized real delivery; E2E-033
covers retry after a declared real transport fault. Delivery prerequisites are
explicit authorization, a dedicated test recipient and the actual supported
service profile. Inventory registration grants no delivery permission.
About and feedback requirement-mapping gaps are explicit pending
work with owners and authoritative contract references. They must be mapped
before those cases become ready. No existing requirement is marked covered.
Task 20's [startup audit](../../docs/TestAutomation/Evidence/20-Startup-Audit-20260908.md)
maps clean installation to `ONPC-CORE-INSTALL-001` and startup gates to
`ONPC-COMP-BROKER-010`. The retained `startup-enforcement` variant owns the
fapolicyd/GDM failure; `startup-broker` independently owns broker reconciliation
failure. All three Task 20 cases remain pending implementation and execution.

`pending` requires a reason and a null executable. `ready` requires no pending
reason or requirement gap and an existing `tests/e2e/*.py` or `*.pm` reference
(including subdirectories) plus its unique executable test ID. Validation never
imports or runs those files. Ready means registered for execution, **not passed**;
the controller reconciles actual scheduling and completed results
with the selected identities. References cannot traverse outside `tests/e2e`,
including through a symlink.

Each attempt has distinct setup, start, ordered steps, end and cleanup phases.
Provisioning belongs only in setup and the outer reset only in cleanup.
Customer steps are UI actions, read-only observations or real waits. Fault and
controlled-environment operations require the matching category and a declared
intervention with actor, step and expected evidence. Every family declares
visible, backend and other-user assertions tied to actual journey steps. The
runner smoke instead checks host/source preservation without claiming a
customer isolation test. These typed declarations are not a sandbox for test
code: the launcher must enforce lifecycle, secret and observation boundaries.

## Minimum evidence declaration, version 1

The inventory pins required run and step field names. `evidence.py` now checks
runtime payloads against these declarations and `private_artifacts.py` verifies
collected copies. Public controller integration passed the former E2E-034; canonical E2E-001
qualification and customer coverage remain their owning tasks' work.

| Fields | Required meaning for the collector |
| --- | --- |
| `run_id`, `scenario_id`, `variant_id` | One independent attempt and its exact selected identity; reruns have new attempt IDs. |
| `source_sha256`, `inventory_sha256`, `package_sha256`, `assets_sha256`, `environment_id`, `baseline_sha256` | Current input provenance. A smoke without package assets records an explicit null package identity, never an invented package digest. Transferred package bytes have their real digest even when not installed. |
| `started_at`, `ended_at`, `steps` | Actual attempt boundaries and ordered step records, including failure/interruption. |
| `artifacts` | Collected, validated private artifact references with content digests and redaction status; never credentials or arbitrary raw worker output. |
| `outcomes`, `first_failure`, `cleanup` | Separate product, infrastructure, collection and cleanup outcomes; preserve the first failure and record lease/host/baseline restoration. A passing diagnostic retry cannot replace it. |
| Step `step_id`, `phase`, `operation`, `outcome`, `monotonic_seconds` | Actual execution order, declared operation and bounded measured timing. |
| Step `boot_id`, `session_ids`, `assertion_ids`, `artifact_ids` | Real continuity, using safe identity aliases in exported evidence, and links to executed assertions and collected evidence. |

Expected evidence always includes action trace, screen, backend, other-user,
continuity, input provenance, split outcomes and cleanup. Declared faults also
require intervention evidence, and external-delivery scenarios require delivery
evidence. Missing, extra, duplicate, skipped, failed or stale required results,
unsafe artifacts and failed cleanup prevent a runtime pass. Task 27 extends
this minimum contract and connects evidence across all layers.

## Runtime gate and private collector

The guarded controller constructs `EvidenceContract` before executing a selection,
with a fresh `run_id`, the inventory path, selector and independently verified
input identities. Construction refuses pending cases and stale inventory bytes.
The contract freezes the plan and inputs; it never obtains expected provenance
from worker results. The source identity covers requirement mappings, test code
and uncommitted changes through `provenance.VerifiedInputs`. The execution
controller must use its preservation gate after execution. A null package digest is allowed
only when every selected case is a product-free runner smoke.

`validate(records, collector)` accepts one record per selected case in selection
order. Version 1 extends the minimum run fields with `schema_version`, exact
`executable` identity, executed `assertions`, and ordered `failures`. Each assertion
has `assertion_id`, `step_id`, `kind`, `outcome` and nonempty `artifact_ids`.
Visible/backend/other-user assertions require their corresponding evidence kind
on the declared step. Every artifact must be linked from a step, every declared
evidence kind must be present, and the records must exactly match the collector's
manifest. The collector rechecks permissions, directory identity and copy digests
at the gate. Unknown fields are refused, rather than silently discarded.

Step `monotonic_seconds` is elapsed time from the case's setup start, in
nondecreasing order, bounded by its declared duration and actual UTC boundaries
(one second of timestamp rounding tolerance). `boot-N` and `session-N` are
run-local continuity aliases; the controller maintains their mapping privately.
Recording an alias is not proof of a reboot or other-user isolation: the owning
assertion scripts must establish those facts. Customer operations must match the
inventory's exact phase and operation, including the sole outer cleanup reset.

The controller calls `record_failure(case_id, category, code, ...)` immediately
on observing a failure, using fixed safe codes, and obtains result fields from
`failure_state(case_id)`. Its append-only ledger prevents a worker payload from
removing or replacing the first failure. Product, infrastructure, collection
and cleanup remain independent outcomes. Any nonpassing outcome or step/assertion,
recorded failure, or incomplete cleanup refuses acceptance. Cleanup requires
`lease_phase=complete` plus true `owned_processes_stopped`, `vm_off`,
`baseline_restored`, `host_preserved` and `source_preserved` fields.

`PrivateCollector(run_id=..., secrets=[...])` creates a new private
`/tmp/onpc-e2e-evidence-*` directory. Keep it open through validation. Register
all fixture secrets before capture. `add` accepts reviewed bytes; `copy` accepts
one filename in a private source directory. Both require `reviewed=True` from
the trusted controller. This flag attests prior producer review, **not automatic
redaction**. The collector does not OCR images, discover unknown PII, or establish
that screenshots are safe. Producers must exclude authentication captures, raw
worker vars/logs, account names and other PII before collection. Secret scanning
(literal, JSON/URL/base64 and UTF-16 representations) is defense in depth.
The worker integration exercises these boundaries; The canonical smoke exports only capture
metadata, with no new pixel/needle acceptance claim.

Files are bounded to 16 MiB, copied as 0600 into 0700 storage, and identified
by digest, size, kind, run and redaction policy. No path traversal, symlink,
hardlink, FIFO/device, public permission, recursive copy or overwrite is allowed.
Source logs are never modified. Changed files and unregistered directory entries
refuse acceptance. `save_report` retains a controller's redacted structured
diagnostic record once, including failed/interrupted attempts; it does not grant
a passing result. Preserve the original report and allocate a new run/collector
for a diagnostic retry. The launcher must persist failure history before risky
cleanup and retain the gate's fixed refusal code without raw exception output.

The gate returns `outcome=passed`, exact case IDs, inputs and full/partial scope
only after all checks pass. Partial selections remain partial. Host tests use
separate temporary ready inventories and synthetic reviewed payloads. They prove
the contract's acceptance/refusal behavior, not customer execution, screen
redaction, verified input capture, or VM restoration.

## Controller-owned provenance

Construct `VerifiedInputs(lease=lease, assets=staged_directory)` after the existing
`Lease.prepare` and `stage_assets`, before worker startup. The asset directory
must be caller-owned and mode 0700; the outer controller must set this after
staging, since `copytree` retains the builder directory's permissions. Omit
assets only for a product-free smoke. This API has no lifecycle operations and
must retain the existing held lease through its final check.

`inputs` returns copied expected identities; `source_files` supplies the earlier
digest map required by `e2e_worker.run_distribution`. Source enumeration uses
Git's tracked and nonignored untracked paths, hashes current bytes and modes in
the artifact builder's format, and detects edits, additions, removals and file
replacement. Tracked deletions already present before a fresh build are omitted,
matching the builder; deletion or reappearance during an attempt refuses.
Root controller reads scope Git's `safe.directory` to this invocation's
trusted checkout, without changing global configuration. Ignored build outputs
are excluded. The capture rejects symlinks,
hardlinks and special input files, pins parent directory opens and checks file
identity around each read. Source capture records identities; it does not copy
the checkout. The worker still stages verified distribution bytes separately.

Staged package bytes and fixture manifests use the existing artifact verifier;
fixture payload bytes also use the fixture verifier. The package manifest's
source digest must match this checkout's current content identity. The exact
staged tree, including the Flatpak delivery container, is hashed and rechecked.
Baseline identity is independently derived from the held lease's durable state,
retained snapshot proof and verified guest preparation. `environment_id` is a
safe digest alias of that guest preparation, not a claim that the full installed
host-tool/release-environment matrix has been validated. Raw baseline account
records and exception text are never exported.

Use `contract(run_id=..., selector=...)` to create the expected evidence contract,
`recheck()` immediately before startup, and `validate(contract, records,
collector)` after outer cleanup but before releasing the lease. Validation
checks inputs before and after the existing evidence gate and rejects contracts
created elsewhere. Any observed input failure is latched: restoring bytes or a
later successful worker result cannot clear it. The controller persists
failure with its other attempt outcomes. Checks detect changes at these
boundaries; they are not a filesystem monitor.

`Qualification._recheck_final_inputs` now preserves the first fixed
`final_provenance_refusal` in both early and late finalization failure reports.
`provenance.refusal_code` admits only explicit source, asset, metadata and baseline
categories; unknown exceptions become `provenance:recheck-failed`. The preservation
flag stays false, the original exception survives, and outer cleanup still releases
the lease. [Cleanup regressions](../unit/test_graphical_smoke_cleanup_safety.py)
cover both boundaries and private-text refusal; the
[startup observation evidence](../../docs/TestAutomation/Evidence/20-Startup-Enforcement-Observation-20260909.md)
records its initial local scope. The first
[integrated VT6 authentication attempt](../../docs/TestAutomation/Evidence/20-VT6-Authentication-Attempt-20260910.md)
now qualifies live retention of `provenance:source-changed` through failed
finalization and successful guarded cleanup. It refused at the first VT6
authorization stage, before input. All nine changed runtime-file byte digests
still matched the captured map after cleanup; the changed checkout input or
metadata remains unknown. The [second VT6 attempt](../../docs/TestAutomation/Evidence/20-VT6-Password-Recipient-20260910.md)
passed final source/host preservation and the getty authorization, then refused
the password recipient. This does not explain or erase the first source change.
Its 138.845-second getty stage and 68.995-second password-stage failure expose
an unqualified latency interaction: each `Authentication.observe` brackets its
proof with `VerifiedInputs.recheck`, which also calls `baseline_inputs` and
`Capture.verify_snapshot` (including backing-chain digests). Component timing
is now available through `VerifiedInputs.recheck_milliseconds`, including failed
components. The [third VT6 attempt](../../docs/TestAutomation/Evidence/20-VT6-Revalidation-Timing-20260910.md)
isolated 69.027 seconds in baseline verification and 0.091 seconds in source
capture during the password-stage recheck. Guest `login` had a configured
60-second lifetime and the selected executable changed from `login` to `agetty`
across this wait. Full checks remain mandatory; neither caching nor skipping a
check is qualified. Finite fixture login preparation and password readiness are
now live-qualified in attempt 6 under the VT6 contract below. Subsequent
[attempt 10](../../docs/TestAutomation/Evidence/20-VT6-Command-and-Shutdown-20260911.md)
completes authentication/command stages but demonstrates insufficient worker
budget through normal shutdown; the [worker contract](#shared-guarded-worker)
owns its correction and attempt 11's passing worker result. Timing/privacy/failure regressions are in
[test_e2e_provenance.py](../unit/test_e2e_provenance.py) and
[test_e2e_vt6_controller.py](../unit/test_e2e_vt6_controller.py).
Worker wrappers can still collapse the initial error,
and no differing file/snapshot comparison is exported. This does not close
historical provenance failures or qualify authentication. A historical false
source-preservation flag alone cannot identify
the changed input or exclude assets/baseline failure. The [refused reboot-wiring attempt](../../docs/TestAutomation/Evidence/20-Customer-Reboot-Wiring-20260909.md)
retains actual concurrent checkout modifications between artifact creation and
installation preflight, together with the live provenance refusal and successful
guarded cleanup. Preserve that failed result; build fresh inputs for required
work without weakening the latch or restoring the historical VM hold.
[Provenance regressions](../unit/test_e2e_provenance.py) own local source, metadata,
assets and baseline refusal coverage.

[VT6 attempt 8](../../docs/TestAutomation/Evidence/20-VT6-Joined-Flow-20260910.md)
retained `provenance:source-changed` during credential preparation, before worker
startup. New Parent UI changes appeared during the attempt while this session
made no checkout writes. The first differing path/field was not retained, so
the evidence supports current concurrent source activity without attributing a
specific comparison. Baseline restoration and host preservation passed; source
preservation failed. Reuse unchanged-input capture and its existing refusal
latch after that current writer finishes; no source exclusion, digest cache,
permission change or blanket VM hold is warranted.

[Attempt 11](../../docs/TestAutomation/Evidence/20-VT6-Shutdown-and-Source-Preservation-20260911.md)
passes all authentication stages and normal worker shutdown, then refuses final
`provenance:source-changed`. A new nonignored `docs/VersionHistory.md` appeared
after the command receipt and before finalization while this session made no
checkout writes. The addition is sufficient to invalidate `source_paths` and
`snapshot`; `test_new_source_file_is_detected` in the provenance regressions
covers this boundary. No full differing snapshot was exported, so the sole
changed field and historical failures remain unproven. Preserve the unrelated
file and capture fresh inputs. Baseline restoration, host preservation and owned
cleanup passed; complete authenticated qualification still requires final source
preservation. The existing refusal latch remains mandatory.

[Attempt 12](../../docs/TestAutomation/Evidence/20-VT6-Fresh-Input-Refusal-20260911.md)
captured the checkout including that prior addition, then refused during
preparation before worker startup when three new nonignored release-tool files
appeared. Their joint creation after pre-attempt status is sufficient to change
`source_paths`; the controller still does not export a full differing snapshot,
so no sole-field or historical attribution is claimed. Cleanup, baseline
restoration and host preservation passed. Preserve the files, reconcile current
inputs, and reuse the unchanged refusal latch; this attempt adds no worker or
authentication qualification. Release-tool edits continued after cleanup, so a
later preflight must establish a settled input set before another Task 20 attempt.

Host tests exercise actual Git trees, artifact/fixture verification and the real
private collector with synthetic scenario records. They do not establish live
VM provenance or customer behavior. E2E-034 supplies separate live public
controller proof; 156 customer/fault variants remain pending.

## Verify edits

### Asset transfer qualification

The separate `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-<verified-build>`
route qualifies the fixed authenticated installation boundary. It provisions
verified assets and fixture credentials, then uses real serial login, fresh
sudo authentication, package-result verification, customer reboot and graphical return.
Each installation request pumps pending serial input before read-only probes;
safe observations are checkpointed before replies. Capture remains sealed after
authentication. No caller command, package path or scenario override is accepted.
The installation preflight records the guest's selected sudo-rs executable and
installed Ubuntu package version, and refuses revisions outside the audited
0.2.13-0ubuntu1, 0.2.13-0ubuntu1.1 and 0.2.13-0ubuntu1.2 contract. The helper
supplies its own leading newline in sudo's supported custom prompt. The serial
matcher requires that newline, `ONPC-INSTALL-PASSWORD: ` and the complete fixed
`] Password: ` suffix at the buffer end. Command echo, a bare marker, incomplete
or private suffixes cannot authorize input. The independent argv proof requires
the actual newline too; do not depend on the wrapper's earlier framing. The
installation proof's `terminal_echo_disabled` means password-character echo is
off. Newline-only ECHONL is allowed: the password is printable ASCII and Enter
is sent separately. Recipient identity/continuity, prompt, private capture and
terminal failure/retry guards remain mandatory.

A failed login executable resolution also records fixed error, link/target,
selected-process start-time/ancestry, service-leader and probe-privilege categories.
These follow only the already-selected process and fixed login path. They are
observations after the failure: a successful reread cannot authorize password
input, clear the refusal or permit a retry. Raw paths and exception text stay private.

Successful installation additionally requires the exact bold-red reboot notice
immediately before the shell's split success marker. The private serial tail
retains ANSI bytes; no control stripping or arbitrary intervening output is
accepted. Only fixed text/color/final-position flags enter public evidence.
This proves emitted terminal output, not a graphical rendering or reboot.

The sibling `tools/run-tests e2e --qualify-install-refusal --artifacts
/tmp/onpc-<verified-build>` route deliberately submits one fixed non-secret,
non-hex password after the same recipient proof. It requires the first re-prompt,
cancels instead of sending a retry, and then follows only the proved getty/login
lineage to establish that the fixture shell has no installer child. A final
read-only probe also requires the package payload and reboot marker to remain
absent. Authentication capture stays sealed and no arbitrary denial value or
command is accepted.

The successful-install diagnostic now requests a real reboot; the refusal route
still logs out without reboot. Neither establishes complete E2E-002 readiness;
the product selection remains pending. Refresh the installed dispatcher through
`./setup.sh --test-tools-only` when adding this option. Test-tool activation is
`none` (next invocation); no product data migration is involved.

`tools/run-tests e2e --qualify-transfer --artifacts /tmp/onpc-<verified-build>`
runs the existing guarded credential-free graphical worker with package/fixture
delivery. Build current inputs with `tools/run-tests artifacts build` first.
The qualification rejects scenario/list selectors; all pending customer cases
stay closed. This is diagnostic runner evidence, with no product installation.
Refresh the installed dispatcher through `./setup.sh --test-tools-only` when
adding this option. Test-tool activation is `none` (next invocation), with no
product schema or package activation change.

Before acquiring a lease or connecting to libvirt, `preflight_source` compares
the staged artifact's source digest with the current checkout and checks for
changes during that comparison. Stale or unreadable inputs produce a private
terminal diagnostic and refuse without VM preparation. This early check does
not replace `VerifiedInputs` or any held-lease preservation check. Keep the
checkout unchanged from artifact building through finalization; edits after
preflight still invalidate the attempt. Intentional tracked-file deletions
before a fresh build are represented in current inputs by the builder and
provenance scanner; deletions or reappearances during an attempt still refuse.

The controller freezes artifacts with `stage_assets`, makes the staging root
0700, and binds it to `VerifiedInputs`. `AssetTransfer.provision` accepts only
that same held, isolated, never-started lease. After offline SSH bootstrap and
before worker startup, it uses the existing guarded `mounted_guest` and public
libguestfs upload/checksum APIs to copy pinned descriptors into the fresh fixed
`/var/lib/onpc-e2e-assets` directory. Package alias and exact transfer inventory
must match controller-captured digests. Files become root-owned 0644 and
directories 0755 so later real terminal installation can read these nonsecret
assets. Existing destinations, stale inputs, special files, changed copied
bytes, extra entries and a second provisioning call refuse. No package is
installed, no product state is written and no host share is attached.

After boot, `AssetTransfer.observe` uses the guarded SSH transport for a fixed
read-only tree, ownership, mode and digest check. The tree check includes
unexpected empty directories; every directory must be an ancestor of a
transferred file. Only count/digest evidence
returns. A mismatch prevents the ready acknowledgement and latches failure;
later replies cannot clear it. Ordered checkpoints retain transfer start and
successful offline verification. The outer lease owns all cleanup, including
partial transfer failure; the transfer helper never boots, stops or restores.
Authenticated secret/console transport uses the separate contracts below.
Host regressions execute the exact probe against filesystem fixtures, checking
receipt agreement and malformed trees, ownership, permissions, links, special
files and changed/missing/extra payloads. They do not replace live qualification.

```sh
tools/run-unit-tests tests/unit/test_e2e_inventory.py tests/unit/test_e2e_evidence.py -q
```

These tests run automatically in `make check` via ordinary unit discovery.
They cover selection refusal, pending/ready separation, matrix closure,
three-sided evidence declarations, malformed input, executable containment,
phase/intervention categories and host-only CLI behavior. Runtime tests also
cover exact result reconciliation, split outcomes, retained failures, provenance,
private copies, tampering, secret exclusion and file/directory replacement.

### Installation findings to carry forward

Use this record through the selected task's
[reuse-map entry](../../docs/TestAutomation/Reuse-Map.md#installation-helper-and-open-limits).
The canonical implementations are [onpc_install.pm](../integration/graphical_smoke/lib/onpc_install.pm),
[InstallationBoundary](installation_boundary.py), and
[installation observations](installation_observations.py) through
[ReadOnlyObservations](observation_transport.py). Extend these implementations;
keep the linked regressions when adding consumers. Evidence describes the exact
qualified scope; historical next-step instructions are superseded by the
[current handoff](../../docs/TestAutomation/Task-20.md#task-20-continuation--2026-09-08).

| Problem or boundary | Established behavior to preserve | Regression and evidence |
| --- | --- | --- |
| Prompt framing and fragmented serial delivery | Supply the newline in the supported sudo prompt and require the complete fixed suffix. Match through the maintained serial reader; command echo and partial/private suffixes never authorize input. A marker absent from the observed buffer does not prove sudo emitted nothing. | [Helper tests](../unit/test_e2e_install_helper.py), especially `test_installed_serial_parser_reassembles_every_prompt_boundary`; [live prompt qualification](../../docs/TestAutomation/Evidence/20-Install-Explicit-Newline-20260908.md). |
| Password characters versus newline echo | Require ECHO off; ECHONL alone may remain on for the validated printable password with Enter sent separately. Keep independent recipient, argv, process continuity and sealed-capture checks. | [Password tests](../unit/test_e2e_install_password_observation.py), including `test_kernel_newline_echo_does_not_echo_password_characters`; same live prompt qualification. |
| Cancellation on the pipe-backed serial console | The graphical Ctrl+C path failed. `run_refusal` sends the fixed interrupt byte through `type_string` after one rejected password, then proves shell return and installer/package/marker absence without retry. | [Helper tests](../unit/test_e2e_install_helper.py), [refusal observations](../unit/test_e2e_installation_observations.py); [failed attempt and correction](../../docs/TestAutomation/Evidence/20-Install-Refusal-Attempt-20260908.md), [live corrected refusal](../../docs/TestAutomation/Evidence/20-Install-Refusal-Corrected-20260908.md). |
| Exact final reboot notice | `_verify_notice` checks the private serial tail for exact text, bold-red ANSI bytes and final position before the split success marker. This assertion passed live; it establishes emitted bytes, not graphical rendering or reboot. | [Helper tests](../unit/test_e2e_install_helper.py), including fragmented notice and ring-buffer cases; [live notice qualification](../../docs/TestAutomation/Evidence/20-Recipient-Diagnostics-Notice-Qualified-20260909.md). |
| Installed package layout after reboot | `INSTALLED_LAYOUT` reuses the package-derived transferred inventory and checks installed file/symlink ownership, mode and target, package verification, private configuration, PAM hooks, Polkit actions/rule and session descriptors without returning paths or package output. `InstallationBoundary.observe_installed_layout` binds the returned inventory digest to controller-held `VerifiedInputs` and latches every failure. The GDM-return callback composes it with both startup witnesses and an unchanged boot. | [Guest/transport/boundary/controller tests](../unit/test_e2e_installation_observations.py); [local evidence](../../docs/TestAutomation/Evidence/20-Installed-Layout-Observation-20260909.md). Locally tested only; complete live E2E-002 qualification remains pending. |
| Intermittent `getty-*-exe-resolve` refusal — open | Cause remains unknown. Fixed errno, link/target, selected-process/leader continuity and effective-root/ptrace categories distinguish future failures. They are sequential observations after refusal, not atomic causal proof. A successful reread cannot clear refusal or authorize input. Use them if the failure recurs in required work; do not repeat installation solely to reproduce it. | [Resolution diagnostics tests](../unit/test_e2e_install_password_observation.py), [transport refusal/redaction tests](../unit/test_e2e_observation_transport.py); [diagnostic scope and limits](../../docs/TestAutomation/Evidence/20-Recipient-Diagnostics-Notice-Qualified-20260909.md). Diagnostics passed locally; this failure did not recur in that live attempt. |

The missing customer-visible notice cannot be added as another match or capture
on the current installation console. `onpc_serial::run_install` selects the
pinned os-autoinst `virtio-terminal`; that console constructs a text-only
`serial_screen`, whose `current_screen` returns no image and whose screen-update
method is a no-op. The VNC `sut` surface remains at GDM during this serial flow,
so selecting it would capture the greeter rather than the package notice.
`onpc_install::run` also seals explicit capture before authentication, and the
controller rejects every screenshot field on install/reboot stages. These are
necessary privacy boundaries, not missing calls to `assert_screen`.

Task 20 therefore needs a genuine graphical terminal path with a fixed command,
a separately reviewed prompt/recipient and notice-pixel contract, and the same
private artifact handling before graphical visibility can be claimed. Replaying
serial output, invoking the notice helper after installation, rendering ANSI
bytes on the controller, or matching the unchanged GDM display does not prove
that the parent saw the documented package command's final output. The
[boundary evidence](../../docs/TestAutomation/Evidence/20-Graphical-Notice-Boundary-20260909.md)
records the pinned implementation and focused verification. This is an
partially implemented authentication-adjacent boundary; it is not qualified
reuse of the existing GDM capture helper. The fixed VT6 route below now resolves
the launch-surface question; its complete input/pixel path is still pending.

### Visible VT6 installation terminal

The accepted baseline has a real kernel-rendered VT6 login surface on VNC.
One guarded, credential-free maintenance inspection switched with Ctrl+Alt+F6
and retained a reviewed 1280×800 login screen. See the
[VT6 evidence](../../docs/TestAutomation/Evidence/20-Visible-VT6-20260909.md).
This establishes surface availability only: it is not an os-autoinst scenario,
authentication, red-notice or E2E-002 pass. No desktop terminal package, baseline
change, serial replay or controller renderer is needed for the selected route.
[systemd's reserved-VT contract](https://github.com/systemd/systemd/blob/main/man/logind.conf.xml)
describes activation; the live image establishes this baseline's actual behavior.

Reuse the public os-autoinst VNC `sut` console and `send_key('ctrl-alt-f6')`,
then reviewed terminal-specific screen assertions and `type_password`. Keep
`NOVIDEO=1`, capture sealing and private automatic screenshots. `wait_serial`
does not observe this screen. The existing installation/reboot callbacks still
use serial input; they have **not** been switched to VT6 and no new password
surface or generic needle name is authorized by these probes.

[terminal_observations.py](terminal_observations.py) owns the two fixed terminal
contexts. `VT6_PASSWORD` in [guest_observations.py](guest_observations.py) and
`VT6_SUDO_PASSWORD` / `VT6_REBOOT_PASSWORD` in
[installation_observations.py](installation_observations.py) reuse the serial
login and sudo process/command proofs with `getty@tty6.service`, device 4:6 and
`/dev/tty6`. They additionally require the
[kernel's active-VT observation](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-tty)
to remain `tty6` at repeated checkpoints. Only the selected getty/login lineage
is followed; no process scan, guest write or signal is added. The shared
executable-resolution diagnostic now rechecks that same selected getty unit.
It never clears a refusal. Serial constants keep their existing output tokens.

`ReadOnlyObservations.read` exposes only fixed `vt6-password`,
`vt6-install-password` and `vt6-reboot-password` probes. Their exact safe tokens
are distinct from serial and from one another. Wrong tokens, private output,
foreground loss, ownership failure or transport errors latch refusal. Reuse
the [login](../unit/test_e2e_serial_observation.py),
[sudo](../unit/test_e2e_install_password_observation.py) and
[transport](../unit/test_e2e_observation_transport.py) regressions. These probes
have local refusal coverage. The fixed getty and login password probes also
passed live in the [credential-free prompt qualification](../../docs/TestAutomation/Evidence/20-VT6-Prompt-Qualification-20260910.md);
the sudo probes remain **locally tested only**. Repeated foreground checks are
not an atomic observation-to-keyboard guarantee, and this collection pass does
not qualify password input or authenticated session continuity.

**Cross-observation recipient gate — local regressions and live stage evidence:**
`VT6_GETTY_IDENTITY` and `VT6_PASSWORD_IDENTITY` in
[guest_observations.py](guest_observations.py) reuse those same getty/login
predicates. They bracket them with boot reads, then recheck the selected unit's
MainPID, executable, root credentials, process start time and active VT. They
export only an exact probe tag and two bounded digests. The recipient digest
binds boot, fixed unit, PID and start time; the boot digest uses the complete
kernel file including its newline, exactly like `BOOT_SHA256_PROBE`.
[agetty's exec of login](https://raw.githubusercontent.com/util-linux/util-linux/master/agetty-cmd/agetty.c)
preserves the process incarnation; phase-specific executable checks remain
separate from that digest. The
[kernel's proc identity fields](https://www.kernel.org/doc/html/latest/filesystems/proc.html)
provide the start-time and session/foreground observations. This is sequential
corroboration, not an atomic process-to-keyboard guarantee.

After an independent `read('boot')`, [ReadOnlyObservations](observation_transport.py)
accepts exactly `vt6-getty-identity` → `vt6-password-identity` →
`vt6-password-recheck`. The last two freshly execute the same fixed password
program; all three must agree with the initially pinned boot/recipient. The
reader keeps the recipient digest private and returns the existing fixed proofs,
adding `vt6_recipient_continuity_verified` only on the latter two reads. Changed
identity/boot, missing boot, reordered/repeated reads, malformed/private output,
ownership loss or transport failure latch refusal. A later boot read cannot
repin the original recipient. This sequence is single-use per observer. Its
fourth and final read is now `vt6-shell-identity`, described below; it compares
the detached login parent to the same pinned recipient and boot.

Regressions execute the real guest programs in
[test_e2e_serial_observation.py](../unit/test_e2e_serial_observation.py), including
late unit/executable/start-time replacement, credentials, boot changes and
unchanged serial/prompt behavior. [test_e2e_vt6_recipient.py](../unit/test_e2e_vt6_recipient.py)
covers ordered fresh dispatch, proof-only output and all parser/ownership/replay
refusals. [Recipient-gate evidence](../../docs/TestAutomation/Evidence/20-VT6-Recipient-Gate-20260910.md)
records the initial verification. These reads are now connected to `Smoke`
through `vt6_authentication.Authentication`, with the current worker, capture,
provenance and durable-receipt gates below. Matching digests alone cannot
authorize password input or prove empty
invisible input or fresh pixels; do not repeat prompt-only collection to qualify
these missing boundaries.

`VT6_SESSION` now reuses the shared graphical/serial session predicate through
fixed surface adapters, exposed as `ReadOnlyObservations.read('vt6-session')`.
It requires the selected parent fixture's sole active local `login` session on
`tty6`, rechecking active VT before each logind command and immediately before
success. The exact `vt6-session-ready` token maps to fixed role/boolean evidence;
foreign tokens, private output and ownership/transport failures latch refusal.
The canonical regressions are `test_actual_guest_authentication_probe_rejects_wrong_sessions`,
`test_fixed_probe_checks_ownership_before_and_after_output` and
`test_vt6_proofs_refuse_other_surfaces_private_output_and_latch` in the
[transport tests](../unit/test_e2e_observation_transport.py). The
[session-gate evidence](../../docs/TestAutomation/Evidence/20-VT6-Session-Gate-20260910.md)
records local verification, including the unchanged graphical/serial contracts.
This probe has live stage evidence in authenticated attempts 9/10 below; complete
qualification still requires normal worker shutdown. It proves neither shell
readiness nor continuity from an earlier login
recipient. Worker/controller boot and one-shot input gates remain necessary;
repeated active-VT checks cannot make observation and keyboard input atomic.

**Shell lineage — local regressions and live stage evidence:** `VT6_SHELL_IDENTITY`
in [guest_observations.py](guest_observations.py) now reuses the direct-child
semantics of [installation_observations.py](installation_observations.py).
[util-linux login's session fork](https://raw.githubusercontent.com/util-linux/util-linux/master/login-utils/login.c)
detaches the parent terminal and gives the shell a new session. The fixed probe
requires the selected unit's root login parent, its sole direct fixture-owned
`-bash` child in that new session, no shell children, three VT6 standard
descriptors and terminal foreground ownership. It brackets observation with
unit/process/start-time, executable/credentials, boot and active-VT rechecks;
opened terminal descriptors close on refusal as well as success. It follows
only that lineage and performs no guest write, input, signal or process scan.

The SSH observer does not own VT6 as its controlling terminal, so
[`tcgetpgrp`](https://man7.org/linux/man-pages/man3/tcgetpgrp.3.html) refuses its
descriptor with `ENOTTY`. The joined review reproduced this with a real local
PTY; the earlier probe doubles incorrectly returned success. Foreground checks
now reuse the repeated pinned shell's
[`/proc` terminal/session/process-group fields](https://www.kernel.org/doc/html/latest/filesystems/proc.html),
including `tpgid`, before and after the terminal open. `test_e2e_vt6_shell.py`
retains late foreground replacement refusal, descriptor closure and a real
noncontrolling-terminal ioctl regression. No observer session or terminal
ownership is changed. Attempts 9/10 below now exercise this correction live;
their complete qualification remains failed.

The fourth ordered observer read compares the original login recipient digest
and returns only `vt6_login_continuity_verified`,
`vt6_foreground_shell_verified`, `active_vt6_verified` and the boot digest.
It also retains a private shell digest binding boot, terminal, parent and shell
PID/start times for the command round trip. It does **not** return
`vt6_shell_ready_verified` or session/input authorization.
`vt6-session` remains independently required. The probe is an immediate
observation, not a startup wait; an incomplete shell transition currently
refuses. A Bash executable, empty child list, foreground terminal or active
logind session cannot distinguish command parsing from startup scripts or a
builtin consuming input. A fixed nonsecret keyboard command round trip with
fresh boot/shell/attempt-bound completion evidence is the next readiness
boundary; [vt6_command.py](vt6_command.py) now has local regression coverage and
completed live stage evidence in attempt 10 below. Do not replace it with syscall/wait-channel
heuristics or synthesize readiness from the lineage booleans.

[test_e2e_vt6_shell.py](../unit/test_e2e_vt6_shell.py) executes the actual probe
against explicit process/terminal fixtures, including late replacement,
credentials, ancestry, session/foreground, descriptor and cleanup refusals.
[test_e2e_vt6_recipient.py](../unit/test_e2e_vt6_recipient.py) extends its strict
parser, ordering, replay, ownership and privacy cases to the fourth read.
[Shell-lineage evidence](../../docs/TestAutomation/Evidence/20-VT6-Shell-Lineage-20260910.md)
records its original local inputs and verification. No live authentication or
command readiness is qualified by these tests. Dispatch is now connected only
through the guarded qualification described below.

**Command round trip — locally tested; live stage passed in attempt 10:**
`ReadOnlyObservations.vt6_command_boundary`
can be acquired once after the fourth identity read. `CommandRoundTrip.prepare`
rechecks pinned lineage and absence of a fresh nonce-named marker before issuing
the fixed nonsecret command challenge. The worker constructs the command from
that exact 64-hex challenge; it accepts no command text or path. A noclobber
subshell writes only the nonce and original shell PID to a mode-0600 temporary
file. `complete` waits at most 30 seconds for the marker and subshell exit,
then rechecks the complete pinned lineage, foreground VT, boot and stable safe
file metadata/content. The SSH timeout bounds the whole program. No output
capture is reopened. A consumed/partial line, stale marker, replacement, timeout
or ownership failure permanently refuses; typing never retries. These guest
probes only read. Outer baseline restoration removes the visible command's
marker, including in failed attempt 10 below. [Command regressions](../unit/test_e2e_vt6_command.py)
execute the real Bash grammar, marker reader and bounded wait, and cover
transport/ordering/privacy refusals. See
[integrated evidence](../../docs/TestAutomation/Evidence/20-VT6-Authentication-Attempt-20260910.md).

The joined authentication review found the capture reader's whole-stat defect
also in `vt6_command.READ_MARKER`. A delayed first read on `/tmp` reproduces a
false refusal locally. The guest's `marker_identity` now compares the stable
fields of `provenance.identity` plus UID/GID, excluding read-driven atime and
preserving nanosecond mtime/ctime. The delayed-read regression and per-field
descriptor/path mutations in `test_e2e_vt6_command.py` protect that boundary.
This correction now has completed live command-stage evidence in attempt 10;
normal worker shutdown remains unqualified for that integrated route.

The selected fixture echo and empty login challenge now have a
[reviewed image contract](../../docs/TestAutomation/Evidence/20-VT6-Prompt-Qualification-20260910.md#direct-image-review-and-needle-contract).
The maintained `onpc-vt6-parent-password` PNG is the unchanged native 1024×768
capture; do not substitute the 1280×800 maintenance image. Its fixed needle
matches the full frame, the joint selected-login/challenge rectangle
`(0,48,228,32)` and VT label `(198,16,30,16)`, excluding only the cursor cell
`(60,64,6,16)`. `e2e_worker.validate_needles` permits precisely this layout;
generic secret needles still forbid exclusions.

**The needle is not an exact blank-screen proof.** Local installed-matcher
verification found full-frame similarity 1 despite single-glyph changes.
Tight text regions reject the selected-account/prompt mutations, but sparse
extra output can still pass. Authentication must additionally call
[vt6_prompt_pixels.verify_prompt_pixels](vt6_prompt_pixels.py) with a fresh
private capture and provenance-bound reference bytes. This fixed GdkPixbuf
comparison validates the reviewed reference digest, bounds native RGB decoding,
and refuses every pixel difference outside the cursor cell. It exports only a
fixed proof/refusal. The decoder uses existing GTK/GI host prerequisites.
`test_needle_similarity_cannot_replace_exact_blank_screen_gate` retains the
counterexample; [pixel regressions](../unit/test_e2e_vt6_pixels.py) also cover
wrong identity, missing/moved prompts, visible input, cursor blink, stale output,
single-pixel differences and invalid inputs. The
[staging tests](../unit/test_e2e_needle_inputs.py) pin the exception's exact scope.
GDM/VT6 tests share the installed matcher through
[needle_matcher.py](../support/needle_matcher.py).
See [pixel-gate evidence](../../docs/TestAutomation/Evidence/20-VT6-Pixel-Gate-20260910.md)
for the failed initial matcher checks, correction and common-check recovery.

`onpc_vt6::authenticate(exchange)` implements the locally tested worker
side of one-shot parent login and command completion. `smoke.pm` selects it only
for the guarded VT6 authentication qualification; other modes retain their own
routes. The existing
credential-free inspector and this function share a single attempt latch.
Every exception seals explicit capture and returns a fixed error; neither
function can retry after either was attempted. The worker selects `sut`, enters
the fixed fixture name after getty proof, requires the maintained needle, then
takes one private capture through `onpc_password::capture_before_authentication`.
It seals capture before sending that image reference to the controller and
before any secret retrieval. Only the final authorization receipt permits
`type_password` with fixed options and a separate Enter. Console and `NOVIDEO`
checks run again before secret access, typing and submission; partial input
failure never retries. A separate session/lineage/command-preparation receipt
then permits the fixed nonsecret round trip above. The worker first requires
the password needle to reject the preceding login screen, providing a live
negative case when the first receipt is reached.

The authentication callback protocol is distinct from prompt inspection. Each
reply has exactly `stage`, a lowercase 64-hex `boot_sha256` (unchanged after the
first reply), and the following JSON **true booleans**; extra fields, missing
proofs, strings/numbers in place of booleans, reordered stages and changed boot
refuse. Only `vt6-password-screen` carries a screenshot request. The `vt6-shell`
reply additionally requires one lowercase 64-hex `command_challenge`, from which
the worker independently constructs the fixed command.

| Stage | Mandatory controller proofs |
| --- | --- |
| `vt6-login-ready` | `vt6_getty_verified`, `active_vt6_verified` |
| `vt6-password-ready` | `vt6_login_process_verified`, `terminal_echo_disabled`, `active_vt6_verified`, `vt6_recipient_continuity_verified` |
| `vt6-password-screen` | The four password-ready proofs plus `vt6_prompt_pixels_verified`, `vt6_password_input_authorized` |
| `vt6-shell` | `active_local_vt6_session`, `active_vt6_verified`, `vt6_login_continuity_verified`, `vt6_command_input_authorized`; plus the challenge above |
| `vt6-authenticated` | `active_local_vt6_session`, `active_vt6_verified`, `vt6_shell_ready_verified`, `vt6_login_continuity_verified` |

All five authentication acknowledgements have live stage evidence in attempt 10
below. The complete run still failed normal worker shutdown and is unaccepted.
[vt6_authentication.py](vt6_authentication.py) composes the
ordered identity/session/command observers and exact pixels with `VerifiedInputs`.
Before capture it records existing file names/inodes and creates a private
same-filesystem timestamp barrier. Python wall-clock comparison was found to
race filesystem timestamp granularity; the barrier avoids that false refusal.
Only a new regular caller-owned image in the pinned result directory, with
stable identity/content metadata and matching reviewed pixels, can advance. Earlier or renamed
images, links, directory replacement and changed source/boot/recipient refuse.

`run_distribution` supplies the trusted `guarded_observe` hook with a guard
bound to its owned `Worker`, held lease and staged distribution bytes. `Smoke`
requires this guard and a durable progress callback for VT6 auth, persists
source/run/capture identities before publication and rechecks the worker after
the checkpoint. Existing replies and partial publication refuse. The observer,
controller and worker each latch failures. The private working directory and
verified ordered worker code provide input provenance; pixels/timestamps alone
do not prove the absence of invisible input or make observation/input atomic.
A same-stage, same-boot replay cannot be distinguished by the worker protocol
alone; the controller's one-use order and fresh current-attempt capture remain
mandatory. [Controller tests](../unit/test_e2e_vt6_controller.py) cover those
gates and checkpoint failure; `test_input_guard_binds_live_worker_and_staged_bytes_and_always_cleans`
in [cleanup tests](../unit/test_graphical_smoke_cleanup_safety.py) covers current
worker/distribution refusal and resource closure.

The fixed route is `tools/run-tests integration check_graphical_vt6_authentication`.
Its [first guarded attempt](../../docs/TestAutomation/Evidence/20-VT6-Authentication-Attempt-20260910.md)
passed GDM stages, then refused with `provenance:source-changed` at the first
VT6 receipt. No getty identity read or VT6 fixture/password/command input was
authorized. Outer baseline restoration and host preservation passed, while
source preservation failed and normal worker shutdown was not qualified.
The [second guarded attempt](../../docs/TestAutomation/Evidence/20-VT6-Password-Recipient-20260910.md)
passed source/host preservation, the first durable getty authorization and the
negative needle on the login screen. It submitted the fixture name, then
refused at `vt6-password-ready` before password authorization. The retained
guest traceback maps to the first selected-unit executable check: the recipient
was not `/usr/bin/login`. Its actual executable and transition cause
were not retained in that attempt; cross-observation continuity, password input,
capture/command proofs and normal shutdown remain unqualified. Its 68.995-second
request-to-refusal interval motivated the discriminator below. Reuse the existing
recipient probes and provenance contract; do not weaken checks, repeat unchanged,
or restore the old VM hold. The earlier failed attempt remains failed.

The [third guarded attempt](../../docs/TestAutomation/Evidence/20-VT6-Revalidation-Timing-20260910.md)
now qualifies the bounded executable/configuration/timing discriminator:
`VT6_LOGIN_DIAGNOSTIC` observes only the selected unit and fixed login config,
never terminal content, argv or account records. `ReadOnlyObservations` validates
its exact safe output, retains no new recipient pin, and cannot advance the
authorization sequence with a diagnostic. `Authentication` obtains early/late
reads around the full recheck; `Qualification.progress` retains these and fixed
component durations as `terminal-diagnostic` checkpoints, never completed proof
steps. The guest was running util-linux 2.41.3 with `LOGIN_TIMEOUT=60`; the
executable changed from `login` to `agetty` across 69.027 seconds of baseline
verification. This supports prompt expiry during revalidation; no exit signal
was traced. Source/host preservation and outer cleanup passed, but password
authorization and live authentication remain unqualified.

Both `matches_pinned_recipient` Booleans in that run are **invalid**: the initial
parser compared a digest with the stored `(boot, recipient)` tuple. The corrected
parser compares with its recipient member; the digest already binds the boot.
The correction cannot qualify continuity retroactively. Attempt 6 below now
qualifies its matching branch live; the replaced/false branch is locally tested.
The old run's executable/configuration/timing fields are unaffected.
[test_e2e_vt6_diagnostic.py](../unit/test_e2e_vt6_diagnostic.py) executes the fixed
guest program and covers malformed/private output, late ownership loss, no gate
advancement, and both matching/replaced digests pinned through the real reader.
Controller and [cleanup regressions](../unit/test_graphical_smoke_cleanup_safety.py)
cover durable diagnostics without authorization and checkpoint refusal.

**Finite fixture login window — preparation and password readiness qualified:**
`fixture_credentials.provision_vt6_login_window` now reuses the existing
held-lease/offline `system_runner.mounted_guest` path to change only the attempt
disk's existing `LOGIN_TIMEOUT=60` to 600 (an already prepared 600 is idempotent).
It validates root-owned, singly linked regular-file metadata, preserves
unrelated bytes and identity/mode, and verifies readback before allowing the
worker. Missing, duplicate, malformed or unexpected settings refuse. Outer
restoration preserves the accepted baseline and host configuration even after
partial preparation. `run_backend` selects its existing finite 960-second
worker limit for VT6 auth; other modes are unchanged. No authentication, retry,
provenance, recipient or capture guard is relaxed. The
[login manual](https://raw.githubusercontent.com/util-linux/util-linux/v2.41/login-utils/login.1.adoc)
documents this configuration; the measured revalidation cost motivates it.

The [fourth attempt](../../docs/TestAutomation/Evidence/20-VT6-Login-Window-20260910.md)
failed with `credential:login-window-failed` during preparation, after credential
verification and before worker startup or any authentication input. Exact cause
and partial-write state are unknown because the first wrapper discarded the
specific error. Baseline restoration and final source/host preservation passed.
After cleanup, the helper was corrected to retain a finite allowlist of its
fixed predicate codes, otherwise only a fixed operation-boundary category;
private exception text is never published. This diagnostic correction is locally
tested at that point. Neither the new budgets nor live authentication/advisory continuity
are qualified by that old run. Do not rerun the old timing experiment or relax a
configuration/ownership guard without evidence. The
[cleanup regressions](../unit/test_graphical_smoke_cleanup_safety.py) cover
preservation/idempotence, unsafe/partial preparation, closure/interruption,
worker gating, outer restoration and exact safe error categories. The
[active handoff](../../docs/TestAutomation/Task-20.md#task-20-continuation--2026-09-08)
owns the next discriminating integrated attempt and milestone review.

The [fifth and sixth attempts](../../docs/TestAutomation/Evidence/20-VT6-Offline-Guard-20260910.md)
resolve preparation: the helper's redundant in-mount `Lease.guard` invoked
locking `qemu-img info` against its own libguestfs writer. Reuse the established
`mounted_guest` full checks before opening and after closing the appliance;
do not call disk inventory while it holds the disk or weaken disk locking.
Pre-write/readback metadata validation remains. The cleanup regressions now
exercise occupied-disk refusal of incompatible guard placement, pre-write
metadata replacement and post-close guard loss. Attempt 6 passes readback,
observes effective timeout 600 and matching `login` identity across full baseline
revalidation, and issues durable login/password-ready proofs. Full worker-budget
adequacy, credential submission and command readiness remain unqualified.

Attempt 6 then refuses at `vt6-password-screen`; its generic worker wrapper
retains no exact predicate. Its pre-password PNG is byte-identical to the pinned
reference. The [seventh attempt and local correction](../../docs/TestAutomation/Evidence/20-VT6-Capture-Identity-20260910.md)
now qualify safe durable `vt6_refusal` checkpoints: `Authentication.refusal`
retains a finite controller-owned code, and `Qualification.progress` validates
`REFUSALS` before saving a rejected stage without an authorization reply.
Unknown exception text, paths and metadata values are never exported.
Attempt 7 reaches `capture-changed-refused` after the initial metadata and exact
pixel checks. It passes outer cleanup and preservation, but still authorizes no
password. The generic worker failure remains a failed infrastructure outcome.

**Stable capture identity — corrected; live stage proof in attempts 9/10:**
The installed `basetest::_result_add_screenshot` calls tinycv's
`write_with_thumbnail`, which locally produces a fresh singly linked image.
A delayed first read on `/tmp` reproduces the original whole-stat refusal:
access time advances while identity/content metadata remains stable. Whole-stat
tuple equality uses integer-second timestamps, hiding the change in fast tests.
The separate `/tmp` tmpfs is not covered by the root filesystem's `noatime` flag.
The live run did not retain individual fields; this local reproduction supports
its atime diagnosis without retroactively claiming a live field measurement.

`Authentication._pixels` now reuses `provenance.identity` for both descriptor and
path, adding explicit UID/GID stability. Device/inode, mode, links, size and
nanosecond mtime/ctime remain invariant; read-driven atime is excluded. All
initial freshness, directory, reference/pixel, worker, source, boot and recipient
gates remain. A changed stable field retains its fixed descriptor/path predicate.
[Controller regressions](../unit/test_e2e_vt6_controller.py) cover the installed
writer with a 1.05-second first-read delay, every stable field on both views,
single-use refusal and publication ordering. The
[cleanup regressions](../unit/test_graphical_smoke_cleanup_safety.py) validate
fixed-code checkpoints and reject private or malformed diagnostics.
Attempts 9/10 below pass the corrected capture stage, and attempt 10 completes
the authenticated command stage. Attempt 11 below also passes normal worker
shutdown; complete qualification still requires final source preservation.
Sudo/notice pixels remain unqualified; no new prompt collection is needed for
the corrected worker deadline.

**Joined review and attempt 8 — historical source drift:**
The [joined-flow evidence](../../docs/TestAutomation/Evidence/20-VT6-Joined-Flow-20260910.md)
records the marker atime and noncontrolling-terminal ioctl reproductions and
corrections above. Attempt 8 then refused `provenance:source-changed` during
credential preparation, before worker startup or any VT6 input. New Parent UI
changes appeared during the attempt while this session made no checkout writes.
The exact first differing source path/field was not retained. Baseline restoration,
lease completion and host preservation passed; source preservation failed.
This attempt does not qualify either correction, the earlier screenshot fix,
password submission or shell/command readiness. Current source-bound live work
needs unchanged checkout inputs; do not weaken provenance or reinstate the old
VM-authorization hold. The operator subsequently cleared that deferral; the
active Task 20 handoff records current selection. That failed attempt remains failed.

**Attempts 9/10 — command proof reached; normal shutdown hit the deadline:**
The [command and shutdown evidence](../../docs/TestAutomation/Evidence/20-VT6-Command-and-Shutdown-20260911.md)
records fresh stable inputs, both failures and completed outer cleanup. Attempt
9 passed password authorization and observed authenticated session/shell lineage,
then refused command preparation. The standalone controller had restored its
temporary E2E import path before `vt6_command_boundary` tried to import
`vt6_command`. Pytest's permanent path/cache concealed this late dependency.
`ReadOnlyObservations` now imports `CommandRoundTrip` with its other module
dependencies. `test_command_boundary_survives_launcher_import_path_restoration`
in [command regressions](../unit/test_e2e_vt6_command.py) reproduces the old
`ModuleNotFoundError` and passes after correction without a transport/path fallback.

Attempt 10 durably records all five stages, including command authorization and
fresh boot/shell/attempt-bound completion. This is live evidence for the capture,
shell and marker corrections, not a complete qualification: it then fails
`e2e:deadline` after power-off, with no backend exit status or `status-off` event
and `shutdown_verified=false`. Its ten baseline rechecks consume 802.363 seconds;
the worker finishes its failed attempt after 1036.426 seconds against a 960-second
loop budget. The [worker contract](#shared-guarded-worker) owns the subsequent
deadline correction and shutdown proof. Both attempts pass baseline restoration, source/host
preservation and owned cleanup; product/collection remain `not-run`. Do not
repeat the unchanged budget, rediscover prompt gates, skip provenance checks or
use this failed run as accepted authentication infrastructure. The active
[handoff](../../docs/TestAutomation/Task-20.md#task-20-continuation--2026-09-08)
owns the remaining guarded qualification.

**Attempt 11 — worker shutdown passes; final source preservation fails:**
The [retained evidence](../../docs/TestAutomation/Evidence/20-VT6-Shutdown-and-Source-Preservation-20260911.md)
records all five VT6 receipts, backend exit 0, no fatal artifact, ordered off-state
observations and verified worker shutdown with the corrected 1800-second budget.
Worker duration is 926.879 seconds. The outer attempt still fails final
`provenance:source-changed` after a concurrent source-file addition; see the
[provenance contract](#controller-owned-provenance). Baseline restoration, host
preservation and cleanup pass. This is passing worker evidence within a failed
qualification, not accepted authentication infrastructure or E2E-002. Reuse the
corrected flow with fresh inputs through final preservation before installation.

The canonical worker regressions are
[test_e2e_vt6_authentication.py](../unit/test_e2e_vt6_authentication.py), executing
the actual Perl helper with public API/controller doubles. They verify sealing
before receipt/secret access, all mandatory proofs, malformed/reordered receipts,
changed boot, API/credential failures, partial-input refusal, late console/policy
changes, and the shared inspector/authentication no-retry latch. See
[worker-gate evidence](../../docs/TestAutomation/Evidence/20-VT6-Worker-Gate-20260910.md).
These local regressions supplement the live stage evidence above. Identical stale pixels, the excluded
cursor cell and invisible input still require independent input and capture
provenance. Complete the integrated controller's final source-preservation qualification
before using this worker for installation. Sudo challenge and final
red-notice pixels remain uncollected. A prompt image alone
cannot identify the password consumer. Only after that boundary is qualified
should E2E-002 type the documented package/reboot commands on this surface and
combine their real notice pixels with the installed-layout/startup observers.

The existing credential-free collection route is
`tools/run-tests integration check_graphical_vt6_prompt`. It reuses
`onpc_vt6::inspect_prompt`, `Smoke.VT6_PROMPT_STAGES` and `VT6_GETTY`; it cannot
provision/read passwords or combine with authentication/installation. Boot and
independent recipient checks bracket the two private captures; capture seals
on completion/failure. It produced the retained reviewed pixels; no new
maintenance or collector is needed. Regressions are
[test_e2e_vt6_prompt.py](../unit/test_e2e_vt6_prompt.py) and the login/probe tests
above. These checks establish local ordering/refusal behavior. The retained
prompt pass qualifies live collection, not secret input.

The [first worker prompt attempt and correction](../../docs/TestAutomation/Evidence/20-VT6-Prompt-Readiness-20260909.md)
records refusal at `vt6-ready`, specifically the getty canonical/echo predicate,
before fixture text or terminal capture acknowledgement. The preceding active-VT,
agetty identity and device checks passed. Individual live flag values remain
unknown. `VT6_GETTY` now permits both supported agetty prompt modes: canonical
input/kernel echo or raw input/userspace echo; mixed pairs refuse. This applies
only before the fixed nonsecret fixture name. The later canonical/no-echo
login password proof is unchanged. The correction passes local raw/canonical
fixtures and refusal regressions. The
[corrected guarded attempt](../../docs/TestAutomation/Evidence/20-VT6-Prompt-Qualification-20260910.md)
passed both recipient-bound captures, with directly reviewed login/challenge
pixels, normal worker shutdown, baseline restoration and source/host preservation.
The original failed attempt remains failed. Individual getty flag values remain
unknown; this pass establishes acceptance by the corrected predicate, not which
allowed mode was observed. No credentials were provisioned/read/submitted and no
needle asset was added. Reuse the retained pixels and collector for authenticated
VT6 implementation; do not repeat credential-free discovery without new evidence.

The complete readiness journey and two independent startup-fault cases remain
unfinished; the [reboot observation boundary](#customer-reboot-observation-boundary)
has live changed-boot and serial-return evidence. Its complete graphical-return
acknowledgement and final preservation still require a passing complete run.
See the [startup audit](../../docs/TestAutomation/Evidence/20-Startup-Audit-20260908.md).
Ordinary E2E-001 smoke requires an unchanged boot. Installation qualification
does not prove graphical PAM/Polkit approval or complete E2E-002 acceptance.
Tasks 18A/18C and 26C can extend the relevant package/terminal assertions;
other installed graphical tasks may use verified installation as prerequisite
setup under [Task 20's scope](../../docs/TestAutomation/Task-20.md).
Reopen a solved boundary only for an applicable change, contradictory evidence
or uncovered case under the [verification reuse rules](../../docs/TestAutomation/Implementation-Workflow.md#decide-what-invalidates-earlier-verification).
Fresh artifacts may still be required after documentation edits; retained
qualification evidence never permits bypassing current provenance checks.

## Ordered controller records

`recording.ScenarioRecorder(contract, collector)` consumes the frozen plan and
inputs exposed as copies by `EvidenceContract`. Only ready declarations can
construct that contract. There is no pending-case override or worker-result
import. The current host tests use a separate temporary ready declaration;
the existing graphical feasibility smoke is still not E2E-001 execution.

`run_case(case_id, execute=..., cleanup=...)` invokes trusted controller
callbacks in selection order. Scenario callbacks enter `step(step_id)` at the
actual operation boundary. The recorder persists its start before yielding,
then records the measured result. `continuity(boot=..., sessions=...)` translates
private observed identities to run-local aliases; a reused session identifier
after a reboot receives a new alias. `artifact` accepts only reviewed bytes
through the private collector. `assertion` requires its declared step and
corresponding evidence kind; missing assertions fail at step completion.
Neither a returned worker success nor an omitted action creates passing records.

Checkpoints are fsynced, uniquely numbered `event-NNNNNN.json` files. They retain
only the current case snapshot and fixed event names, including action start,
assertion, failure and `before-cleanup`. An uncatchable termination leaves the
last durable action start incomplete; it is not resumable or acceptable.
After a caught failure, only real executed records remain; outer cleanup may
run despite missing journey steps or an expired action deadline. Cleanup and
report errors are added without replacing the original exception or failure.
No raw exception message, account identity or authentication capture is exported.

`run_worker(verified, directory, lease, ledger, observe=..., validate=...)`
rechecks the independently owned contract and inputs before starting the
qualified worker. It forwards `source_files` and connects worker failures to
the recorder before worker cleanup. The trusted observation callback still
must record actual stages/assertions. Worker guard refusals are also retained;
a failed checkpoint cannot prevent worker or callback-server cleanup.
The optional `credentials=...` and `serial=True` use the same provisioned
`FixtureCredentials` instance as the worker. Before startup, the bridge checks
its same-lease provisioning and requires every worker secret in the scenario
collector's original registry. `PrivateCollector.require_secrets` only checks
that frozen registry; it cannot add a secret after earlier reports were written.
Unregistered, foreign, unprovisioned and invalid credentials refuse and latch
scenario failure before worker construction.

For the actual lease lifecycle, use
`leased_recording.LeasedScenario(recorder, verified, cleanup=...)` inside the
already prepared, held lease. Each independent attempt has one exact selected
case and one declared outer cleanup step. Construction refuses an existing
finalizer and stale inputs. `execute(callback)` records the scenario's actual
actions, persists `before-cleanup`, and starts the cleanup step before returning
to the owning lease context. It rechecks identity and provenance before calling
scenario code. A worker success alone supplies no steps or assertions.

`Lease.__exit__` remains the sole owner of `finish()` and release. Its finalizer
checks the original lease/run/domain identity, completed restoration, actual
off state and preserved inputs. It then calls the trusted, read-only `cleanup`
callback with `(recorder, lease)` to check host/source/worker preservation and
return the exact `CLEANUP_FIELDS`. The callback may copy reviewed cleanup
evidence through the active cleanup step; it must never restore or release.
The adapter ends that step and the case, then calls `recorder.validate(verified)`
while held. The gate uses `VerifiedInputs.validate` around the final report copy.
After leaving the lease context, call `attempt.result()`; it also refuses
release failures recorded in the original lease ledger. The outer controller
must still include connection-close failures in its final invocation outcome.
The existing synchronous `recorder.run_case` remains available for controllers
whose cleanup already completes before their callback returns.

Any `acceptance-rejected.json` is a terminal
failure, including if a late input/copy change follows an initial gate pass.
An `acceptance.json` file alone never establishes success. A failed report write
preserves earlier checkpoints and raises the original error; it cannot promise
new durable evidence when storage itself is unavailable.

Host regressions execute the real recorder, collector, evidence gate and
`Lease.__exit__`, substituting only VM operations/provenance observations.
They cover real private copies, action interruption, replacement identities,
checkpoint errors, cleanup failure, late validation and release failure.
The serial transport has separate live qualification, and E2E-034 now proves
this adapter within the public controller. Public dispatch and preparation/
terminal failure reporting are connected as described below.
E2E-001 public stability qualification is accepted in
[Task 19B evidence](../../docs/TestAutomation/Evidence/19B-Acceptance-20260908.md).
Test-tool activation is `none` (next
invocation); no product data or installation changes.

### Public execution and terminal reporting

`runner.main` imports `execution` only after host-safe preflight selects entirely
ready cases. The installed category dispatcher still owns privilege checks and
isolated safety prerequisites. `execution.main` requires root and the pinned
checkout. Each selected case gets one new private raw directory, collector,
connection and complete lease attempt. Cases run serially; the first failure
stops further cases, leaving their expected identities visibly unexecuted.
All attempts must match the first attempt's full independently captured inputs.
One public libvirt event loop serves these separate connections for the process.

Raw attempts use `/tmp/onpc-graphical-smoke-<run>` with mode 0700, matching
the existing screenshot export helper's fixed scope regardless of `TMPDIR`.
After terminal cleanup, selected nonsecret `testresults/<image>.png` captures
can be inspected through `pkexec /usr/local/libexec/onpc-export-screenshot`
with a new `/tmp/onpc-<name>.png` destination. Remove review exports through
`tools/cleanup-screenshots`; retain private raw evidence. The helper's ownership,
path and file checks still apply. Older `onpc-e2e-attempt-*` captures remain
outside this export scope and must not be moved or aliased to bypass it.
This controller-only storage change activates on the next invocation (`none`);
it requires no installed-helper refresh or product data migration.

The controller stages and verifies artifacts before VM acquisition, prepares
the existing lease and observation bootstrap, then captures `VerifiedInputs`.
The inventory digest and exact case declaration must still match preflight.
It registers fixture secrets before any reports, including preparation reports.
Failures before a recorder exists retain invocation diagnostics and use only
the entered lease's restoration/release. No synthetic scenario actions are
invented for failed preparation.

A ready Python module defines `E2E_CASES = {'<test_id>': callback}`. The loader
checks its bytes against the frozen source map before executing them and
rechecks provenance before calling `callback(recorder, context)`. Module code
is trusted checkout code; it is not a guest-supplied script or a CLI command.
The callback return value never supplies acceptance. Record actual ordered
actions, reviewed artifacts and assertions through the recorder. Use
`context.run_worker(observe=..., validate=..., authenticate=False, serial=False)`
once; its actual worker/transport/shutdown result supplies cleanup proof.
Callbacks may use the existing bounded asset and credential provisioners with
the context's verified inputs, guestfs, credentials, commands and lease, inside
their declared setup steps. Credential provisioning and serial-getty setup
must precede authenticated worker startup. The fixed worker distribution is
still the qualified smoke; 19B owns stable screen matching and scenario work.

`invocation-*.json` checkpoints retain preparation and post-restoration outcomes
alongside the recorder's separate `event-*.json` stream. Host preservation and
connection close run even after an earlier failure. Collection verifies the
exact recorded artifact manifest, including failed-attempt copies. Errors use
fixed codes, never exception text. The invocation collector retains expected
case IDs, each completed attempt, and a terminal candidate. Per-case
`acceptance.json` and terminal-candidate files are **not standalone passes**:
the final JSON output and successful controller exit are required after all
collector closes. A close or output/report failure cannot return success;
storage failure may leave only earlier checkpoints. Host tests establish the
failure behavior; the [19A acceptance audit](../../docs/TestAutomation/Evidence/19A-Controller-Acceptance-20260907.md)
retains the separate live success and preparation-failure evidence.

## Shared guarded worker

`e2e_worker.run_distribution` now runs the qualified, fixed credential-free
distribution for `tests/integration/check_graphical_smoke.py`. Invoke the smoke
through `tools/run-tests integration check_graphical_smoke`; the dispatcher runs
isolated cleanup prerequisites before entering the existing VM lease. This is
worker integration evidence, not an executed E2E-001 variant. The distribution's
Perl sources still live in `tests/integration/graphical_smoke`; this extraction
does not replace its feasibility geometry with Task 19B's stable matching.

The outer controller supplies its previously recorded source digest map. The
worker freezes distribution bytes, rejects changed/extra/missing inputs and
unsafe source entries, and writes only those verified bytes into a fresh private
distribution directory. Its fixed generalhw variables and command expose no
caller-selected backend, schedule, checkpoint, guest command or password input.
`Adapter` must validate the prepared lease before callbacks or worker creation,
and revalidates its identity on every poll, including worker completion. The
trusted observation and validation callbacks remain in the outer controller;
worker exit zero cannot substitute for their stage/module assertions.

The fixed command preserves isotovideo's normal backend exit policy instead of
deriving exit status from module results. Any `base_state.json` entry rejects
success, including empty, malformed or non-file entries; its potentially private
message is neither parsed nor exported. After module/stage validation, the worker
requires a recorded power-on, subsequent power-off and later off observation,
adapter phase `stopped`, and a fresh `lease.guard(off=True)`. Reports retain only
fixed lifecycle events, backend exit status, fatal-artifact presence and shutdown
verification. These checks supplement the outer restoration/evidence gate.

At the end of a complete smoke, `console('sut')->disable()` closes VNC through
the public console API before `power('off')` delegates shutdown to the lease.
Require `check_shutdown(0)` to succeed; `assert_shutdown` also captures a screen.
Leaving VNC active after display revocation allows its background stall handler
to attempt reconnection to a stopped guest. Graphics ownership must still refuse
that request. Disabling the console ends observation; it does not change VM state.

**VT6 finite budget and delayed callbacks:** [authenticated attempt 10](../../docs/TestAutomation/Evidence/20-VT6-Command-and-Shutdown-20260911.md)
completed every authentication/command receipt and reached `poweroff`, then
failed with the original `e2e:deadline` at finalization. Its worker report retains
the generic `worker-execution-failed`, null backend status, no `status-off` event
and false shutdown verification. The 960-second `run_distribution` budget was
insufficient for that joined execution: ten mandatory baseline rechecks used
802.363 seconds, and the worker report reached 1036.426 seconds. Synchronous
`CallbackServer.serve_once` work can cross the outer loop deadline before another
poll/off observation; preserve that fact when correcting the finite budget.
Outer baseline restoration and source/host preservation passed; that failed
attempt did not establish normal worker shutdown.

`check_graphical_smoke.run_backend` now selects 1800 seconds for VT6 authentication:
1200 for the ten full rechecks plus the existing 600-second smoke allowance,
including synchronous `Lease.stop` and backend exit. Other selections retain
600/960 seconds. `run_distribution` accepts only finite positive numeric budgets
at most 1800; no callback renews the deadline. After `serve_once` returns, it
checks expiration before another observer dispatch. Owned shutdown completes
even if it crosses the deadline; expiration still fails and closes both resources.
All lifecycle, module, lease and final preservation checks remain required.

`test_delayed_shutdown_callback_keeps_finite_deadline_and_requires_off_observation`
in [worker cleanup regressions](../unit/test_e2e_worker_cleanup_safety.py) covers
the old-budget refusal, delayed success with actual off observation, exhausted
new-budget refusal and both closes. Invalid budgets refuse before resources.
Reuse `test_timeout_refuses_and_cleans_up`, `Adapter`, `Lease.stop` and
[public shutdown regressions](../unit/test_e2e_shutdown.py); the existing
`test_vt6_worker_uses_existing_finite_extended_budget` in
[smoke cleanup regressions](../unit/test_graphical_smoke_cleanup_safety.py) covers
selection without changing other flows.

[Attempt 11](../../docs/TestAutomation/Evidence/20-VT6-Shutdown-and-Source-Preservation-20260911.md)
passes the worker with exit 0, no fatal artifact, all authentication receipts,
off observations and `shutdown_verified=true`. Its 926.879-second worker duration
also fits the old budget because baseline reads were faster; the local regression
supplies the delayed-budget counterexample. The outer attempt fails final source
preservation after a new source file appeared. Baseline restoration, host
preservation and cleanup pass. Normal worker shutdown now has live evidence;
complete integrated qualification still requires final source preservation.
No new generic diagnostic layer, prompt collection or shutdown redesign is needed.

Private `worker-before-cleanup.json` and `worker-result.json` reports contain
only fixed diagnostic fields, distribution digest, timing, failure history and
worker/callback cleanup status. The first is persisted before closing resources;
the worker closes before its callback server, and each close is attempted even
after another fails. Failure reports exclude raw exception text. Collection or
cleanup failure prevents return of success and preserves the original error.
The reports use `FailureLedger` and `PrivateCollector`; they are explicitly
credential-free worker diagnostics, **not** `EvidenceContract` scenario results
or proof of outer VM/host restoration. The outer smoke result owns those checks.
Raw vars/logs/screens stay private and are never copied as reviewed artifacts.
An empty secret registry is appropriate only when no fixture credentials are
provisioned. The credential qualification supplies the same frozen registry to
the outer collector, worker collector and variable staging.

### Credential staging and password capture boundary

`SecretVariables` freezes controller-supplied fixture passwords for the fixed
`parent`, `child`, `other-parent` and `other-child` roles. It accepts only 1–256
printable ASCII characters, rejecting control characters that could submit a
command or change fields. The mapping has a redacted representation. Supply its
`registered_secrets` to `PrivateCollector` **before** staging or starting a worker;
use that same frozen instance for `stage(directory, public_variables)`. No CLI,
environment or command argument carries the passwords. The worker accepts only
a successfully provisioned `FixtureCredentials` belonging to the same held,
isolated, never-booted lease; arbitrary password mappings are refused.

Staging creates `vars.json` once as 0600 beneath a descriptor-pinned, caller-owned
0700 directory, refuses symlinks/existing entries and caller-supplied secret
variable names, syncs the write, and checks directory identity afterward. A
failed/interrupted write stays private and cannot be retried over that file.
Every fixture password uses an `_SECRET_ONPC_*_PASSWORD` name. os-autoinst's
secret-filtered saves omit those names, but its initial vars and automatic
backend output can still contain secrets: **never export raw vars/logs/captures**.

The maintained Perl `lib/onpc_password.pm` provides `enter_password(role, surface)`
for fixed `gdm`, `polkit` and `lock` surfaces. It requires `NOVIDEO=1`, a registered
variable, and a successful public `assert_screen` for the fixed
`onpc-<surface>-<role>-masked-password` tag immediately before public `type_password`.
Callers cannot override the password API's `secret` option. The needle contract
must prove the selected fixture identity together with its empty, focused and
masked password field; no generic password-field tag, coordinate or terminal
fallback exists. The helper does not submit or assert authentication
success. Unknown inputs and any API failure permanently refuse subsequent input.

The credential-free smoke now routes explicit screenshots through
`capture_before_authentication()`. Capture failure prevents later input, and
starting any password operation permanently closes that helper's capture route,
including on prompt failure. Exceptions crossing this boundary contain fixed
codes only. This does **not** disable automatic os-autoinst screenshots; all raw
captures remain private and unapproved for export. Trusted distribution code
must use the helper; this is not a sandbox against code calling testapi directly.

`FixtureCredentials` generates independent random passwords for the four
canonical fixture roles. The baseline does not retain its manually supplied
setup password. Provisioning uses the maintained
[virt-customize password-file interface](https://libguestfs.org/virt-customize.1.html)
on the exclusively held offline disk, with networking disabled. It validates
fixture UIDs and shells against accepted baseline records, stages 0600 files in
a pinned 0700 directory, and refuses repeated provisioning. Only these four
password hashes may change: password aging, unrelated shadow entries (including
root), and the entire passwd file must remain identical. The pinned OpenSSL
verifier receives each password on stdin and returns its hash only in memory.
Failures expose fixed codes, invalidate worker access, and leave restoration to
the outer lease. Private password files and raw backend output are not exportable
evidence; their values are registered before provisioning and capture.

Run `tools/run-tests integration check_graphical_credentials` for its guarded
qualification: provision and verify all four passwords, stage the worker secrets,
select the fixture parent by its reviewed label, reject the parent password
needle on both the account list and the other fixture parent's prompt, then
authenticate the intended parent through the secret-safe password API. The
controller requires an independently verified active local GDM session for the
canonical fixture before accepting the `authenticated` stage. It refuses explicit
post-password screenshot uploads. The outer owner restores the baseline.
This route has no arguments and does not open customer scenario dispatch.
The [authentication evidence](../../docs/TestAutomation/Evidence/19A-Authentication-20260907.md)
records the complete positive/negative live pass. The earlier
[credential/transfer evidence](../../docs/TestAutomation/Evidence/19A-Fixture-Credentials-20260907.md)
remains available with its original input identities.

Distribution staging now accepts strictly paired PNG/JSON needles under
`needles/onpc-<surface>-<role>-{account,masked-password}.*`, with matching tags, bounded
dimensions/rectangles and 99–100% match thresholds. Both files enter the same
source digest map and frozen copy as Perl sources. Missing pairs, extra fields,
generic tags, links and changed bytes refuse before backend startup. Structural
validation does not establish visual meaning. Reviewed GDM parent/other-parent
account labels and the parent password prompt now have live evidence at 100%.
The password needle jointly matches the fixture identity, empty field/visibility
control and focus outline, excluding the blinking caret. Retain a small surrounding
pixel margin: the matcher's blur reads neighboring pixels, so masking exactly
at a match rectangle can reduce even an identical region's score. Only reviewed
fixture pixels are retained in these assets; unrelated identities and clocks
remain outside them. Other roles/surfaces still require reviewed needles and
live positive/negative qualification before input. No coordinate fallback exists.
The sole additional fixed name, `onpc-gdm-parent-installed-account`, matches the
reviewed fixture label after installation/reboot. It has no click point and is
used only for graphical return; arbitrary installed variants and password/click
extensions refuse staging. Its retained-image checks are described below.

### GDM readiness and graphical return

`lib/onpc_gdm.pm` shares the existing reviewed GDM needles. `wait_list(90)`
allows the initial display handoff to finish; later matches use 30-second
deadlines. The smoke explicitly selects `sut` first: backend display activation
alone does not set the public current-console identity. It requires that console
and an actual account-label match. `select_parent()` matches/clicks that account and recognizes its empty,
focused password prompt, then deliberately checks that the account-list needle
refuses the prompt. `dismiss_prompt()` sends Escape and requires the list again.
The serial helper calls `return_from_serial()` only after independently observed
logout; it selects `sut` and requires a fresh account-list match before success.
The successful installation path instead calls `return_after_reboot()` after
changed boot and a fresh serial login prompt. This uses the separately reviewed
`onpc-gdm-parent-installed-account` needle at 100%. The old label failed against
the retained post-reboot image at 87.9%; the new label matches that same image
at 100%. Only the canonical fixture label and a 16-pixel blur border enter the
asset; other accounts and the clock are blacked out. The
[pixel regressions](../unit/test_e2e_gdm_pixels.py) execute installed tinycv against
bounded position changes, the other parent, the password prompt and the original
rendering. The correction is locally verified against real failure pixels;
a complete live return acknowledgement remains pending. The
[unblock evidence](../../docs/TestAutomation/Evidence/20-Reboot-Unblock-20260909.md)
retains the original failure and inspection scope.
There is no fixed ten-second render delay or whole-screen stillness gate in
this graphical/serial smoke path. The separate credential qualification retains
its settling check at the other parent's negative-prompt boundary.

Account needles have a single matched region and an explicit public
`click_point`, relative to that region and strictly inside it. Staging rejects
out-of-region points, extra point options, and password-needle click points.
The [public test API](https://github.com/os-autoinst/os-autoinst/blob/master/testapi.pm)
documents `assert_screen`, `assert_and_click` and console selection; the installed
pinned API is also checked locally. Existing pixels, 100% thresholds, clock and
animation exclusions remain unchanged.

Each public match retains its screenshot and match details in the private
`testresults/result-smoke.json`; missing screens fail at the declared deadline
and leave private failure artifacts. Post-authentication explicit captures stay
sealed, including after graphical return. Never export automatic captures or
terminal logs as reviewed evidence without inspecting and redacting them.
Run `tools/run-tests integration check_graphical_serial` for the smallest live
helper qualification. Its live result is already retained; do not repeat it
to resume implementation. E2E-001 now records the complete ordered evidence;
Task 19B's three complete public qualifications are
[accepted](../../docs/TestAutomation/Evidence/19B-Acceptance-20260908.md).
The [helper qualification](../../docs/TestAutomation/Evidence/19B-GDM-Matching-20260908.md)
retains the corrected live success, deliberate negative match, original failure
and source identities; do not repeat it merely to resume implementation.

Host regressions execute the real Perl helper with stubbed public testapi calls,
and cover provisioning ownership, password verification, private storage,
secret-scanned evidence, needle inputs and interrupted staging/worker cleanup.
GDM parent password input and the serial-command qualification have passed. Test-tool
activation is `none` (next invocation); product data and accepted baseline are
unchanged. `setup.sh` installs the pinned OpenSSL dependency on clean hosts.

### Public serial console qualification

Run `tools/run-tests integration check_graphical_serial` through the existing
guarded dispatcher. This fixed qualification takes no arguments. It reuses
fixture credentials and GDM checks, then performs serial login, a harmless
`printf`, real logout and public graphical-console selection. It never opens
pending customer scenario dispatch or claims full 19A acceptance.

`graphical_serial.SerialConsole` connects the lease-validated running VM's
existing `serial0` through libvirt's public `openConsole` and a nonblocking
stream. `VIR_DOMAIN_CONSOLE_SAFE` requires exclusive attachment; no force flag
or direct host PTY access exists. The controller pumps bounded buffers through
two private, inode-checked FIFOs; the maintained public `virtio-terminal`
console uses these through `add_console`. The generalhw SOL grabber remains
disabled. Initial off-state assertions preserve prepared pipes; actual shutdown,
ownership loss and callback cleanup close the serial resources. No extra
process or host listener is introduced. Offline preparation enables only the
stock password-authenticated getty in this attempt, then outer restoration
removes that preparation along with the fixture passwords.

`onpc_serial::run` is currently a fixed qualification flow, not an arbitrary
command/password interface. It requires the selected fixture's exact terminal
echo followed by the password prompt. The read-only `serial-password` probe
independently verifies the standard login executable and argv without autologin,
process/session/terminal identity and start time, and canonical no-echo flags.
The standard login program wipes its username argument: do not recover account
selection from argv or loosen the terminal echo check. Match the public
`wait_serial` return normalization for getty's CRCRLF output. Diagnostic prompt
records contain only a match boolean and line-ending counts.

Only after those checks does public `type_password` receive the registered
fixture secret. The `serial-session` probe then verifies the real fixture UID
and sole active local `login` session on `ttyS0`. Wait for the shell prompt
before commands: logind activation can precede shell readiness. Split the
expected output marker across command arguments so echo cannot pass its
assertion; allow terminal controls preceding output and bounded CR/LF endings.
Controller observations pump pending serial input and defer while `pending_in`
is nonempty before blocking on SSH. The
[reboot boundary](#customer-reboot-observation-boundary) adds a durable drain
checkpoint and fixed command outcome; stream acceptance alone cannot prove
guest command execution.
All explicit post-authentication captures remain sealed and raw worker output
stays private. These helpers activate on invocation (`none`), with no product,
host setup or saved-data migration change.

The [retained serial result](../../docs/TestAutomation/Evidence/19A-Serial-20260907.md)
proves the command. The subsequent
[shutdown qualification](../../docs/TestAutomation/Evidence/19A-Shutdown-20260907.md)
also proves clean backend completion, truthful off-state checking and restored
baseline with the stricter worker outcome gate. E2E-034 subsequently passed
public scenario dispatch and evidence integration. These selected harness
qualifications are not customer coverage.

### Startup enforcement observation

`ReadOnlyObservations.read('startup-enforcement')` uses the fixed
[startup probe](startup_observations.py) through the existing guarded transport.
It reads systemd's completed `ExecStartPost` result for the exact packaged
readiness helper, requiring its fixed argv, non-ignored normal exit zero and a
completed execution. Systemd provides execution and activation monotonic
timestamps through its [public D-Bus properties](https://raw.githubusercontent.com/systemd/systemd/main/man/org.freedesktop.systemd1.xml).
The probe requires policy start ≤ canary start ≤ canary completion ≤ policy
active ≤ display-manager start ≤ display-manager active. Journal receipt time
is unsuitable for this ordering because collection can lag activation.

Boot-file bytes, both unit invocations and the command result must agree across
the read. Both services must be active/running without automatic restarts.
Only the boot digest and six timestamps leave the guest; failure exports a fixed
stage. Canonical serialization, timestamp types/order and the observer's existing
failure latch reject malformed or premature evidence. Boot hashing includes the
kernel file's newline, matching `BOOT_SHA256_PROBE`.

For authenticated installation only, `Smoke` now requires this proof in the
`gdm-return` acknowledgement, correlated with the observed customer reboot and
fresh boot reads. The reviewed pixel match remains independently required.
The original smoke and deliberate installation refusal do not use this probe.
[Executable guest/decoder tests](../unit/test_e2e_startup_observations.py) and
[acknowledgement regressions](../unit/test_graphical_smoke.py) cover success,
denial, changed boot/invocations, stale canary and premature GDM. They use OS
fixtures and real GLib variants; live qualification is pending. The proof
describes the current activation pair, not a monitor of every earlier unit start
or continuous enforcement. It cannot replace the independent E2E-028 fault
case. The independent [broker observer](#broker-startup-observation) is locally
tested. Complete installed-layout checks and customer graphical notice rendering remain unfinished under
[Task 20](../../docs/TestAutomation/Task-20.md#task-20-continuation--2026-09-08).
Tasks 24A and 26B may reuse this probe after live qualification; it does not
establish their session/recovery acceptance.

### Broker startup observation

`ReadOnlyObservations.read('startup-broker')` reuses the fixed guarded observation
transport and [startup probe module](startup_observations.py). The broker's
[`Service`](../../broker/oh_no_parent_control/service.py) writes a fixed
`startup-witness` record through its existing `DailyLogWriter` only after
successful object registration. Real monotonic nanosecond timestamps bracket
registration after completed execution-policy and extension reconciliation and
attempted best-effort session-cap cleanup. Failed mandatory phases produce no
witness/object; failed cap cleanup is safely logged and does not prevent
registration. Diagnostic-write failure also leaves product readiness unchanged
and causes the observer to reject missing evidence.

The broker is a static D-Bus-activated service, so one normal read-only
introspection request may activate it after GDM. This tests broker startup
independently; it neither requires nor establishes broker readiness before GDM.
The probe then pins the current unique bus owner/PID and systemd invocation,
requires active/running state without automatic restarts, finds exactly one
matching record, and introspects that unique owner with autoactivation disabled.
Boot, owner and unit reads bracket collection. Phase timestamps must be ordered
inside the current process start/service activation bounds; systemd comparisons
use microsecond precision. Systemd defines the
[invocation ID](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.exec.xml)
as a distinct unit runtime cycle. Invocation/PID/bus identifiers remain in the
guest; only six timestamps, the canonical boot digest and a success flag leave.
Failure exports a fixed stage and latches the observer's failure.

The reader inspects at most the last 512 KiB of each of ten retained daily broker
logs, rejecting symlinks, nonregular/non-root-owned or group/world-writable
files. Missing, truncated, rotated-away, duplicate or malformed evidence refuses
instead of inferring ordering from later availability or wall-clock log time.
This is current-activation evidence, not continuous history or proof against a
privileged actor altering logs. It cannot replace E2E-028's independent faults.
For authenticated installation, `gdm-return` now requires both startup probes
to match the actual customer reboot and fresh boot reads; pixels remain separate.

[Private-bus tests](../component/test_broker_startup.py) execute the real object
registration boundary with successful startup, mandatory phase failure,
tolerated cap failure, registration failure and logging failure. They replace
the former source-order assertion. [Guest-program and decoder tests](../unit/test_e2e_broker_startup_observations.py)
use actual log files and GLib variants; [controller tests](../unit/test_graphical_smoke.py)
exercise stale boot and failed broker proof. These checks are local, with
[retained slice evidence](../../docs/TestAutomation/Evidence/20-Broker-Startup-Witness-20260909.md);
live qualification remains pending. Tasks 20, 24A and 26B share this contract
after that qualification. The requirement remains planned until installed and
fault evidence pass. No D-Bus interface or service dependency was added.

### Customer reboot observation boundary

`ReadOnlyObservations.wait_boot_change(previous_boot_sha256)` reuses
`vm_transport.Transport`'s pinned SSH connection settings, guest guard and
event-driven readiness loop. It requires a boot digest already obtained by this
observer. The fixed `BOOT_SHA256_PROBE`, also used by ordinary `read('boot')`,
hashes the complete kernel boot-id file in the guest; raw identity stays there.

`Transport._probe_ready` captures the SSH exit status before the post-probe
ownership check. The real `Lease.guard` calls `Capture.revalidate`, whose
`qemu-img` calls use the same `Commands` object and overwrite `last_returncode`.
Reading that mutable field afterward misclassified a disconnect as successful
empty output, and could accept valid-looking output from a failed guest command.
The [transport regression](../unit/test_vm_transport.py) exercises guard-induced
status replacement with both empty and valid-looking output. Ownership checks
still run before accepting or retrying a probe; only SSH status 255 is transient.
The corrected wait passed live in the
[unblock intervention](../../docs/TestAutomation/Evidence/20-Reboot-Unblock-20260909.md):
eleven SSH-255 probes preceded the changed boot and fresh confirmation. That
attempt later failed graphical matching and final preservation; it remains failed.

The missing case was SSH answering from the old boot after customer input.
The new wait accepts neither initial SSH readiness nor an old boot as reboot
evidence. Old-boot responses and SSH status 255 share a 330-second deadline.
Malformed output, guest guard failure, ownership/configuration loss and
interruption stop the observation. Every probe checks ownership before and
after execution; reconnection cannot repin a key or adopt a replacement VM.
A fresh ordinary boot observation must agree with the changed readiness digest,
rejecting another boot change between those two observations. Failure latches
the observer against both subsequent reads and a second wait. Only fixed failure
codes and digest fields leave this capability.

`Smoke` now checkpoints `reboot-ready` only after the installed digest, identity,
reboot marker, unchanged boot and real serial session are verified.
`onpc_serial::run_install` then submits exactly
`/usr/bin/sudo -k -p $'\nONPC-REBOOT-PASSWORD: ' -- /usr/bin/systemctl --no-ask-password reboot`
in that authenticated local shell,
followed by a split `printf` marker of its exit status.
The fixed explicit-newline sudo-rs challenge must match in full before the new
`reboot-password` acknowledgement. `installation_observations.REBOOT_PASSWORD`
reuses the installer's getty-derived recipient, exact argv, foreground terminal,
process-continuity and disabled-character-echo proof. Its separate output marker
cannot be replaced by an installation proof. The controller checks provenance
and the unchanged boot around that observation before acknowledging one fresh
password submission. A repeated password prompt is a terminal refusal. Fixed
`reboot-failed-stage` evidence distinguishes prompt, recipient, password, command,
boot and graphical-return failures without exposing private text.
The command retains normal inhibitor checks, with no force, cached authentication,
policy change or host lifecycle action. The helper privately waits up to
15 seconds for the marker and records only `returned-zero`, `returned-nonzero`
or `unobserved`. A nonzero return fails without a second command or boot wait;
missing output stays unknown and still requires the changed-boot proof.
On nonzero return, `_reboot_failure_diagnostic` inspects only that private
matched tail and emits seven fixed Boolean token observations: authentication
required, access denied, inhibitor, other session, combined session/inhibitor
refusal, shell permission denied and missing executable. Unknown output yields
all zeroes, not an invented reason. Diagnostic failure cannot change the terminal
command failure. No extra serial read, guest action or raw terminal export is
added. [Serial regressions](../unit/test_e2e_serial_helper.py) cover known/unknown
messages, command echo, private canaries and diagnostic failure. The
[instrumented access diagnostic](../../docs/TestAutomation/Evidence/20-Reboot-Access-Diagnostic-20260909.md)
live-qualified fixed access-denied reporting: the command returned nonzero and
that token was observed; the other six flags were zero. The exact denied method,
Polkit action and policy cause remain unknown. The classifier cannot distinguish
a wall-message warning from the reboot method's error. Its original short-form
authentication match also missed a possible longer systemd challenge message.
The final helper recognizes both forms (including `requires interactive
authentication`); that extension is locally tested only. The retained zero
authentication flag cannot exclude a challenge. No raw private tail was inspected
to infer the missing detail, and no second command was submitted.
[Upstream systemd's local precheck](https://github.com/systemd/systemd/blob/v259/src/systemctl/systemctl-logind.c)
can reject inhibitors or other sessions before logind authorization; nonzero
status alone therefore cannot identify Polkit as the cause.
`reboot-observed` pumps submitted input and defers while bytes remain pending;
it records `reboot-input-drained` before waiting. Only its durable acknowledgement
allows the fresh serial login-prompt match and GDM return. The final greeter probe
requires the same new boot; capture stays sealed. Any controller exception latches
failure, including checkpoint failure, so it cannot authorize a retry.

The same held domain ID, serial stream and display remain subject to existing
lease guards; no reattachment, replacement adoption or in-journey restore was
added. The installation worker budget is 960 seconds: the existing 600 seconds
plus the 330-second boot wait and return allowance. Other workers retain 600.
The held serial stream returned a fresh login prompt live, and GDM appeared on
the held display. The corrected GDM match and backend return acknowledgement,
final preservation and product readiness still require a passing complete run.
`SerialConsole.step()` preserves partial sends and
backpressure; the existing controller returns to its event loop when input
remains buffered. The prior handoff overlooked this gate: incomplete delivery
was a hypothesis, not a demonstrated defect. The new checkpoint records that
gate; it does not prove guest execution. Do not
clear an ordinary observation failure or recreate its observer to reconnect.
Ordinary E2E-001 keeps its unchanged-boot assertion; the installed-system
`Transport.reboot()` route retains its existing behavior.

Live changed-boot evidence is linked above; [transport regressions](../unit/test_vm_transport.py)
cover transient versus terminal failures, old boot, deadline and ownership loss;
[observation regressions](../unit/test_e2e_observation_transport.py) exercise the
real readiness loop, kernel digest probe, stale/mismatched identity, second boot
and failure latching. [Retained evidence](../../docs/TestAutomation/Evidence/20-Reboot-Observation-20260909.md)
records the observation checks. Stage/input regressions are in
[smoke controller tests](../unit/test_graphical_smoke.py) and
[serial helper tests](../unit/test_e2e_serial_helper.py), including failed proofs,
input-pump invocation, checkpoint refusal, missing new prompt and no retry. Wiring is
locally tested; [the first wired live attempt](../../docs/TestAutomation/Evidence/20-Customer-Reboot-Wiring-20260909.md)
refused provenance before installation input. No customer reboot occurred in
that attempt. Its concurrent
checkout changes and reporting limitation are under the
[provenance contract](#controller-owned-provenance).
The [next live attempt](../../docs/TestAutomation/Evidence/20-Customer-Reboot-Attempt-20260909.md)
passed provenance and installation, submitted customer input and entered
`reboot-observed`, but failed 330.085 seconds later without an acknowledgement.
Source/host preservation and outer cleanup passed. This does not establish
whether the command was denied or followed by lost SSH readiness. That attempt
lacks fixed command results, drain checkpoints and old-boot versus SSH-255
counts. Cause remains unknown. The existing transport now reports these probe
counts and one allowlisted terminal outcome through `on_diagnostic`, including
unknown error and interruption without raw exception/guest text. `Qualification`
validates and checkpoints the report without completing a stage. Observation
failure still latches. Local transport, observer, controller and Perl regressions
cover these diagnostics, nonzero/unknown command results and checkpoint refusal;
[next instrumented attempt](../../docs/TestAutomation/Evidence/20-Reboot-Command-Result-20260909.md)
passed installation and matched a nonzero command-result marker, then failed
without entering the boot wait. This live-qualifies the command-result refusal
and proves execution in that attempt; its rejection reason remains unknown,
and it does not retrospectively establish the previous timeout's cause.
The drain/probe checkpoints were not reached in those nonzero-command attempts.
The subsequent unblock intervention passed explicit administrator authentication,
command return zero, complete input drain, changed-boot observation and a fresh
serial login prompt. The installed serial parser is also exercised locally with
every prompt split, and a missing-result timeout retains the new login prompt
for the subsequent changed-boot acknowledgement. Both fixed sudo commands run
through the same process/terminal refusal regressions; wrong-purpose markers,
extra force options, cached authentication and private output refuse.
The remaining GDM matcher correction passes locally against the retained failed
image at 100%; its live acknowledgement, final preservation and readiness remain
unqualified. The original attempt has `preservation.source=false`; the final
source/asset/baseline refusal's precise cause was not retained. No checkout edits
were made by the intervention worker during that run, so do not attribute it to
that worker or infer a particular concurrent editor without evidence.
No sudo-cache assumption, force or ignore-inhibitor option, policy change or
host reboot is a supported shortcut.
Do not infer authorization from session activity or clear the failure latch. The
[active handoff](../../docs/TestAutomation/Task-20.md#task-20-continuation--2026-09-08)
owns attempt counts and the next result. Include the corrected return in the
minimum complete readiness journey instead of rerunning installation solely to
refine a failure label. Preserve the original failed outcomes and rebuild inputs.
Tasks 20, 18A/18C and 26C can reuse this boundary when implementing their distinct
customer lifecycle actions. Test-tool activation is `none` (next invocation);
no host setup, product integration or saved-data migration changed.

### Read-only observation capability

The graphical controller keeps initial SSH readiness in its provisioning boundary,
then exposes `ReadOnlyObservations` to stage/asset observation code. `read()`
accepts the fixed asset, session, boot, installation-layout, password-recipient
and startup-readiness probes used by the maintained controller. The versioned programs in
`guest_observations.py` are fixed: scenarios cannot supply shell commands,
paths, stdin, timeout overrides, package operations, policy writes or resets.
Adding a probe requires maintained code, explicit output validation and tests;
there is no guest-selected helper or dynamic command registration.

Each read checks the pinned transport configuration and the existing lease
guard before execution and before accepting output. Asset output must be the
canonical count/digest receipt; greeter/session output must be its exact success marker.
The parent-session probe resolves the canonical fixture's real guest UID and
requires exactly one active local graphical `gdm-password` session. Wrong users,
inactive/remote/TTY sessions, duplicates and other user sessions cannot pass.
Only the root SSH observer session is exempted from the other-user gate.
Only validated fields return to the controller. Unknown probes, malformed output,
transport/ownership failures and interruption latch failure for that observer.
Public diagnostics contain fixed codes, never raw guest output or exception text.
Raw command diagnostics still belong to private controller storage, not reviewed
evidence. This is a capability boundary for trusted Python scenario code, not
a sandbox against code that deliberately imports the provisioning transport.

The existing GDM/serial and boot probes have retained guarded live evidence;
the customer reboot wait now also has live changed-boot evidence, with the later
graphical matching and final-preservation limits above. Host tests cover program
logic, routing, refusal, output and interruption behavior. This SSH observation
interface corroborates the public serial-command smoke; it does not establish full
scenario evidence/capture acceptance. The helpers are development-only,
activate on next invocation (`none`), and change no product data or setup policy.

`tests/unit/test_e2e_worker_cleanup_safety.py` covers ownership refusal, stale
inputs, identity replacement, timeout, nonzero status, interruption at each
execution boundary, report failure and combined cleanup/original failures. It
is automatically included in the dispatcher's isolated safety prerequisites.
The [worker integration evidence](../../docs/TestAutomation/Evidence/19A-Worker-Integration-20260907.md)
records the real run. The launcher, actual scenario recording and public
execution now have E2E-034 live acceptance.

The smoke's `Qualification` controller captures `VerifiedInputs` after offline
bootstrap, rechecks before worker startup, and supplies its `source_files` map.
It uses `recording.save_checkpoint`, the same fsynced snapshot envelope as
`ScenarioRecorder`, for actual stage starts/observations, worker failures, and
before/after outer cleanup. A stage observation must be durable before its
reply permits the next guest action. Screens are represented only by dimensions
and digests; raw captures remain private and unapproved for export.

Finalization checks source/baseline and host preservation while the completed
lease is held, writes the diagnostic report, verifies its private copies and
rechecks provenance before release. A `finalization-rejected` event is terminal,
including after an earlier candidate pass. The final `result.json` also accounts
for release/connection errors. These reports have diagnostic qualification scope,
no scenario ID, no inventory override and no customer assertions. The 156 customer/fault variants remain pending. E2E-001 is the canonical
public scenario recorder and terminal invocation smoke, superseding E2E-034.
