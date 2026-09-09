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
records local scope. This diagnosis has not run live. Worker wrappers can still
collapse an earlier provenance error, and no differing file/snapshot comparison
is exported. A historical false source-preservation flag alone cannot identify
the changed input or exclude assets/baseline failure. The [refused reboot-wiring attempt](../../docs/TestAutomation/Evidence/20-Customer-Reboot-Wiring-20260909.md)
retains actual concurrent checkout modifications between artifact creation and
installation preflight, together with the live provenance refusal and successful
guarded cleanup. Preserve that failed result; build fresh inputs for required
work without weakening the latch or restoring the historical VM hold.
[Provenance regressions](../unit/test_e2e_provenance.py) own local source, metadata,
assets and baseline refusal coverage.

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
