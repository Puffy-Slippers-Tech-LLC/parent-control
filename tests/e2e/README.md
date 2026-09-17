# E2E inventory and runner contract

## Functional GUI acceptance

Follow [functional validation](../../docs/TestAutomation/E2E-Building-Blocks.md#functional-validation)
for all new and migrated customer cases. Cosmetic defects (including alignment,
size, color, font, resolution and scale changes) pass while the customer can
complete the action and obtain its expected result. Public accessibility
names/roles/states, normal GUI actions and resulting behavior replace appearance
matching. Fail blocked interactions, wrong targets/results and unavailable
required information. Keep backend probes out of customer acceptance.

Case 151 (`E2E-030/parent`) is the reference migration: functional app-search,
picker, selected settings, About, license viewer, footer and unchanged return
settings. `ui:` stages retain sanitized public accessibility observations as
screen evidence; ordered worker markers alone cannot pass. Existing GDM
recipient needles protect secret input separately. Historical pixel-based
guidance below applies to unmigrated consumers and credential qualification,
not new customer feature assertions. Do not repair cosmetic differences by
continually adding new reference images.

## Customer scope and runtime transition — 2026-09-14

The [current customer contract](../../docs/TestAutomation/E2E-Building-Blocks.md)
requires real customer actions and visible observations only, across all app
surfaces. Internal product probes, transaction witnesses and induced backend
faults are outside customer acceptance. Completed unit/component/system and
harness tests remain unchanged. Mechanical package/system tests retain necessary
internal installation, migration, removal and recovery checks as separate
package/system qualification.

The runtime schema now permits customer families to omit backend and unrelated-
user assertions when those are not visible parts of the journey. E2E-003 and
E2E-030 have reconciled declarations. A customer family cannot become runnable while it
still declares backend product evidence. Other-user customer assertions remain
optional, but when present their assertion evidence must include a screen from
the real other-user surface. Source/package identity, secret protection, VM
ownership, safe evidence and cleanup remain mandatory harness evidence. Pending
legacy declarations are retained and reconciled with their first consumer; do
not fabricate backend fields, rewrite unrelated tests or build a replacement
evidence framework. Pending selectors still provide no customer coverage.

### Parent consumer composition limits

The [building-block guide](../../docs/TestAutomation/E2E-Building-Blocks.md) owns
the reusable APIs, composition recipe and lessons: installed setup and fresh VNC
reattachment, strict recipient qualification, framebuffer-aware matched clicks,
Parent navigation, durable acknowledgements, phase timing and ordered screen
reconciliation. Start there when adding a customer scenario or repairing one of
these boundaries. The thin About worker is
[onpc_parent_about.pm](../integration/graphical_smoke/lib/onpc_parent_about.pm).

Legacy app-grid readiness matches the active Show Apps button and the grid's page
navigation controls at 100%. It excludes app tiles, whose positions and rendered
labels depend on the installed application set. Pixel regressions require all
three controls, allow changed tile contents, and refuse desktop/login screens.
The child dropdown retains both reviewed row renderings for the existing fixture
child, including the two-child list. Its fixed `PARENT_RENDERINGS` alias keeps
the canonical selection tag, exact matched click point and 100% threshold;
another child's label must not match. Selecting a child still requires the
subsequent visible account and allowance controls before the journey advances.

A customer family's `installed-digest-verified-product` prerequisite selects
verified package setup before its journey. Mechanical startup/fault assertions
remain separate. E2E-003/existing-and-new uses a durable controller action to
create one eligible local account only after the existing child is visible.
E2E-003/none uses a bounded action after the administrator finds the launchable
Parent result through normal app search
but before Parent launches to make the two canonical child fixtures ineligible.
It requires that exact eligible set before any mutation, refusing missing,
substituted or additional standard accounts while leaving the package request station
unchanged; outer baseline restoration owns reversal. Its customer uses the
shared functional GDM wrong-recipient refusal and two fresh intended-recipient
checks before secret input. Enter launches Parent only after fixture preparation
is durably recorded. `ui:parent-empty` independently requires the showing empty
explanation and the child picker's `(None)` placeholder; appearance, resolution
and scale do not gate acceptance. Fixture role/collision checks are setup
evidence; only the public UI supplies customer assertions. No time policy is
changed or child-session enforcement claimed. The existing qualification's review
mode acquires only nonsecret observations and never awards coverage or bypasses
mandatory input matches.

## Current implementation inventory

Host-only regressions reuse the [shared support library](../support/README.md)
for evidence, provenance, recording, credentials and private metadata fixtures.
Those synthetic fixtures are separate from the live helpers described below.

The shared worker has guarded live evidence for graphical input, fixture
credentials, asset transfer, GDM authentication and a real serial command.
Standalone qualification reports retain their diagnostic scope. Public ready
Python callbacks use the same worker through `ScenarioRecorder`, the existing
lease bridge and the `EvidenceContract` gate. Listing and pending-case refusal
remain host-safe; a listing is never an execution pass.

## Inspect scope on the host

### Optional live viewing

Run `tools/watch-e2e` from your desktop terminal whenever you want to watch the
guarded E2E VM. Tests remain headless by default: the runner never launches a
window. You can open, close or reopen the viewer during an attempt. Leave it
open across reboot, shutdown, failure cleanup and subsequent attempts; it shows
Waiting between available displays and resumes automatically. Only closing the
window yourself ends it. Automation neither owns nor signals your viewer process.

The title is `[current/total] [ID]: Title`, using the selected invocation's case
count (including the case in progress), numeric coverage ID and inventory title.
The top reserves three lines for the current inventory step description; the
bottom reserves one line for the operation about to run. Long text is ellipsized.
Recorder phase changes clear the previous operation, and disconnected feeds
clear the previous case. Progress is optional display metadata, never acceptance
evidence. Case/step messages are also logged by the recorder, and fixed worker
operation messages remain in the private worker log.

The window is output only. Mouse, keyboard, scrolling, clipboard and window
resizing have no route into the guest, including while the pointer is over the
window. You can continue working on the host. The guest cursor is drawn from
display updates; existing automated pointer jumps and hidden cursors remain
visible as those actions actually happen. Serial-console and SSH setup work
does not become a graphical interaction merely because the viewer is open.

The runner retains its private VNC connection. A separate, lease-owned collector
uses QEMU's public [D-Bus display listener](https://www.qemu.org/docs/master/interop/dbus-display.html)
through libvirt's public graphics FD API, with no host display listener and GL
disabled. It attaches before test input begins and remains attached regardless
of viewer activity. Viewers receive only a sealed, read-only memory copy through
an invoking-user-authenticated local socket under `/run/onpc-e2e-watch`; they
never receive a QEMU/libvirt connection. There is no input or frame-request
protocol. A slow reader cannot build a frame queue or block the writer. The
collector does not advertise GPU/shared-map acknowledgement extensions.

The feed coalesces updates at approximately 30 Hz, with a fixed 2048×2048 pixel
limit and 256×256 cursor limit. Unsupported frames disable viewing. A separate
watchdog revokes a stalled collector's own sockets after three seconds and reaps
only its pinned process. Initial attachment has a five-second deadline. Feed
failure disables viewing for that attempt; it does not fail the scenario or
automatically retry a QEMU attachment during input. The window remains open for
the next attempt. These are bounded failure paths, not a claim of zero CPU,
memory or scheduling overhead: the collector runs even with no open viewer,
and drawing consumes additional resources while viewing.

Host dependencies come from `./setup.sh --dependencies-only`, including
`qemu-system-modules-opengl` (the package containing `ui-dbus.so`), Python GI and
GTK4. Refresh test tools/rules through `./setup.sh --test-tools-only`.
This is development test infrastructure with package-update activation `none`;
it installs no product service, changes no guest saved data and requires no host
session renewal. Direct virt-manager/VNC viewing is outside this contract: its
connection and input behavior do not enforce these boundaries.

Qualification uses `tools/run-tests integration check_e2e_watch` for repeated
client connections, premature closes, rejected input and collector stalls while
the automation VNC endpoint remains responsive. The isolated GTK test is
`tests/ui/test_e2e_watch.py::test_window_survives_stop_reconnect_and_resize`.
For acceptance, run `E2E-030/parent` (verified installation setup, real reboot,
Parent About journey and final shutdown), and select
`tests/ui/test_e2e_watch.py` through `tools/run-ui-tests --timeout 1300` during
its active feed. The live tests close an initial window during automation, then
open another, reconnect its feed repeatedly and retain it through shutdown. The acceptance
window belongs to the private test compositor, so its fixture cleanup cannot
close a manually opened host viewer. Per-run results remain in runner artifacts.

### Listing and execution

Run `tools/generate_test_coverage.sh` to completely regenerate
[Test-Coverage.md](../../docs/Test-Coverage.md) from local test collection and
the runtime inventory. No Codex, network service or VM is needed; use the
development dependencies installed by `./setup.sh`.

Each documented number is one exact variant's persistent `coverage_id`:
`tools/run-tests e2e --list --id 1` inspects it, and
`tools/run-tests e2e --id 1 --artifacts /tmp/onpc-test-artifacts-REPLACE`
executes it using an existing verified package-artifact directory. Pending
cases still refuse execution. `--id 1,3,4` selects a comma-separated list of
one or more numeric IDs. Empty entries, malformed IDs and unknown IDs refuse
the entire selection; repeated IDs run once. `--id`, `--scenario` and `--ready`
are mutually exclusive. Refresh installed dispatchers with
`./setup.sh --test-tools-only` to support multiple IDs.

`tools/run-tests e2e` runs every runnable E2E case and reports pending exclusions.
It does not dispatch other test categories. Execution without `--artifacts`
builds the required package artifacts automatically; an explicit artifact
directory reuses the existing verified inputs. The guarded dispatcher's mandatory
cleanup-safety prerequisites still apply. Explicit pending IDs refuse rather
than silently narrowing the requested list.

From the checkout, these commands only read declarations and print JSON. They
need no root, package artifacts, installed product, graphical tools or VM:

```sh
tools/run-tests e2e --list
tools/run-tests e2e --list --ready
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

`--ready` explicitly selects every ready variant, in inventory order, and cannot
be combined with `--scenario`. Its JSON reports `ready_only: true`, partial
scope and every omitted ID in `excluded_pending_cases`; `pending_cases` describes
the selected cases only. An empty ready selection refuses. Newly registered
ready cases are discovered automatically on the next invocation.

`tools/run-tests e2e --artifacts /tmp/onpc-... --scenario E2E-002` and
`make check-e2e ARTIFACT_DIR=/tmp/onpc-... SCENARIO=E2E-002` fail with
`selection:pending`, before artifact access, privilege checks, cleanup tests,
worker imports or VM operations. Omitting the selector lists the entire
inventory in listing mode and executes all ready cases in execution mode.
`LIST=1` rejects artifact arguments; other nonempty `LIST` values and
all nonempty `VM_IMAGE` values fail. Make forwards selector values through the
environment, so they cannot become recipe shell commands.

Both the unprivileged category launcher and installed dispatcher invoke the
same `runner.preflight`; refresh the latter with `./setup.sh --test-tools-only`
after dispatcher changes. Development activation is `none` (next invocation),
with no product or saved-data changes. Missing/unsafe inventory inputs fail
closed. A fully ready selection requires existing safe artifacts and Python
controller callbacks. The other 153 cases still refuse as pending.
There is no bypass, checkpoint or resume option. Listing
success is declaration inspection, never an E2E pass.

The JSON includes canonical case IDs, owner, status/reason, parameters,
environment, prerequisites, duration bound, ordered phases, assertions,
expected evidence and the SHA-256 of the exact inventory bytes read. This digest
identifies the declaration only. `provenance.VerifiedInputs` separately identifies
current source, requirement mappings, staged packages/assets and the verified
baseline's guest preparation. Execution dispatch must use that capture.

## Run E2E scenarios

Build once after finishing source, test, needle and documentation edits:

```sh
tools/run-tests artifacts build
```

The builder prints `run-tests: output=/tmp/onpc-test-artifacts-...`. Substitute
that exact directory for `REPLACE` below. Keep the checkout unchanged during runs.

```sh
# All currently implemented E2E variants:
tools/run-tests e2e --ready --artifacts '/tmp/onpc-test-artifacts-REPLACE'

# Only the installed Parent About/license customer journey:
tools/run-tests e2e --scenario 'E2E-030/parent' --artifacts '/tmp/onpc-test-artifacts-REPLACE'

# Only dynamic Parent child discovery and selection:
tools/run-tests e2e --scenario 'E2E-003/existing-and-new' --artifacts '/tmp/onpc-test-artifacts-REPLACE'

# Only Parent's no-eligible-children explanation:
tools/run-tests e2e --scenario 'E2E-003/none' --artifacts '/tmp/onpc-test-artifacts-REPLACE'

# Only standard-user denial through the normal app grid:
tools/run-tests e2e --scenario 'E2E-004/app-grid' --artifacts '/tmp/onpc-test-artifacts-REPLACE'
```

Each invocation installs and reboots once, then captures a powered-off
`onpc-[version]` snapshot using the full Debian package version. An existing
same-name snapshot is deleted after restoring `onpc-baseline`, then rebuilt.
Each case gets its own guarded attempt: installed-app prerequisites restore the
version snapshot; installation/removal cases restore `onpc-baseline`. A missing
version snapshot fails immediately without reinstalling. The previous case's
direct restore selects the next case's snapshot, preserving one restore per
transition and the existing boundary-only audits. Final cleanup restores the
clean baseline and deletes the version snapshot, including on case failure.
The invocation stops after the first failed attempt, including evidence or cleanup
failure, and retains the expected case list and pending exclusions in its report.
After an installed snapshot boots, SSH readiness does not imply greeter readiness:
GDM waits for enforcement startup. Public greeter discovery waits up to 300 seconds
for exactly one active local graphical greeter, then retains the owned session-bus
and accessibility checks. Ambiguous identities and failed reads stop immediately.
The controller allows 390 seconds for that observation, within the worker's
420-second checkpoint deadline; no input is replayed or product probe substituted.
The current ready set contains the E2E-001 harness smoke,
E2E-003/existing-and-new, E2E-003/none, E2E-004/app-grid and E2E-030/parent:
**five runnable variants, four customer variants**. Another 152 variants are
pending. Readiness does not certify a passing run.

E2E-004/app-grid composes the shared installed setup, standard-user login,
app-grid search and ordered screen evidence. The
[administrator-only launcher](../../docs/SystemDesign/Broker.md#accounts-and-roles)
is absent for standard users: case 5 uses public accessibility to read the full
product query and web-only suggestion, and independently requires no Parent
launcher or management window over a bounded interval of fresh complete reads.
The `ui:standard-*` checkpoints connect only to the canonical other-child
desktop's owned session bus. Missing/stale UI cannot prove absence; cosmetics
do not gate acceptance. The shared functional GDM gate independently verifies
wrong-recipient refusal and the intended standard account's empty masked field
and focus twice through ordered standard-specific checkpoints before secret
input. One click uses the search field's current public screen extents, followed
by independent focus observation; geometry has no appearance pass/fail authority.
The shared desktop wait handler cancels an identified focused login-keyring
prompt using one normal click derived from Cancel's current public extents.
It proves that exact dialog disappeared before continuing the same observation
or independently qualifying a queued replacement. No action or text is replayed;
unknown prompts cannot authorize input, and no keyring password is read or
submitted. GDM credential checkpoints remain excluded from automatic dismissal.
Normal type-to-search independently verifies the first character before
entering the rest of the query; no uncertain input is repaired or replayed.
Legacy credential needles and their regressions remain intact. Do not press Enter
on the unrelated suggestion. No time policy is changed or enforcement claimed.
Its stale private grant/policy and
other-user-state witnesses are outside customer scope; existing authorization
and isolation regressions retain those obligations. This declaration correction
earns no executed coverage. The terminal variant remains separately pending.
Omitting both `--ready` and `--scenario` requests the whole inventory and still
refuses while any variant is pending. A ready-suite pass is partial coverage.

`make test-all` and `make test-all-verify` both discover every ready E2E variant
through the same selector, after required host/package and installed-system
prerequisites. No Makefile entry is needed for a newly ready scenario. Both stop
the VM sequence on a failed installed-system/E2E attempt. `test-all` skips
backing-file byte scans; `test-all-verify` and direct E2E commands verify them.
All modes retain ownership, provenance, evidence and cleanup checks. These
aggregates also run the other established suites; use the commands above for
E2E-only execution.

## Maintain declarations

Keep each variant's positive integer `coverage_id` unchanged across edits,
reordering and readiness changes. Allocate new numbers above the highest ever
assigned; never reuse retired IDs. Regenerate
[Test-Coverage.md](../../docs/Test-Coverage.md) after changing tests or scenario
titles, steps, variants or readiness. Edit the source inventory, not that document.

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

The shared bootstrap now requires the
[schema-2 prepared guest tools](../integration/Environment.md), with an
independent read-only key/marker verification after the offline edit. It no
longer installs OpenSSH at each attempt. This preparation change has host-safe
coverage; live SSH/graphical qualification on the new baseline remains pending.
Older runtime evidence retains its original baseline and source identity.

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
visible assertions tied to actual journey steps. Runner, fault and environment
qualification also retains backend and other-user assertions. Customer families
may declare an other-user assertion only for an observed customer surface; its
evidence includes the corresponding screen. Pending legacy customer families
may retain backend fields until their first consumer, but the inventory refuses
to make such a family runnable. These typed declarations are not a sandbox for
test code: the launcher must enforce lifecycle, secret and observation boundaries.

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

Expected evidence always includes action trace, screen, continuity, input
provenance, split outcomes and cleanup. Backend and other-user evidence is
required exactly when that assertion kind is declared; runnable customer
families cannot declare backend evidence, and customer other-user assertions
also require screen evidence. Declared faults require intervention evidence,
and external-delivery scenarios require delivery evidence. Missing, extra,
duplicate, skipped, failed or stale required results, unsafe artifacts and
failed cleanup prevent a runtime pass. Future evidence adapters extend this minimum contract
and connects evidence across all layers.

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

The [source-selection contract](../integration/README.md#package-and-fixture-inputs)
defines the shared exact-path exception for supervisor-owned operator output.
Both collectors exclude it before filesystem inspection; synthetic Git tests
prove no reads/copies, matching digests and continued source-change refusal.
Other documentation remains an input. This local qualification does not supply
an owned stable-input window or change any held-lease recheck or failure latch.
Existing manifests retain their original identities; fresh artifacts are required.

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

### Backing-file verification within an attempt

`make test-all` selects development mode: backing-byte scans are skipped, while
ownership, read leases, snapshot metadata, source/assets and cleanup checks stay
active. It records `metadata-only` in verification evidence and never creates a
verified-byte proof. `make test-all-verify` and default direct system/E2E runs
retain the full verification behavior described below.

The normal installed/graphical `Lease` now uses
[BackingVerification](../integration/backing_verification.py) for `chain[1:]`.
The writable top image remains outside this byte proof: guest writes are expected,
while its retained internal-snapshot metadata is checked at every existing gate.
No validation calls, source/asset checks, durable-state reads, authorization
boundaries or checks around acceptance-report writes have been removed.

Before the first full SHA-256 read, the controller opens each backing file through
pinned parents without following symlinks and acquires a Linux read lease.
Only ext4 and tmpfs are admitted; other filesystems, unavailable leases and a
SIGURG handler already in use retain full byte verification at every gate.
These are kernel file leases, separate from the advisory VM controller lock.
[F_GETLEASE](https://man7.org/linux/man-pages/man2/F_GETLEASE.2const.html)
reports a breaking read lease as unlocked before a conflicting open or truncate
can write. Existing writable descriptors and mappings prevent acquisition.
The controller checks that kernel state at every gate and never renews a lease.
It selects normally ignored SIGURG notifications without installing a signal
handler; correctness depends on the synchronous kernel query, not signal timing
or the lease-break timeout.

The first hash is reusable only while every file lease remains valid, the same
controller owns the exact VM-lock descriptor, the attempt and baseline state
match, and pinned file/path identities still agree. Size and timestamps supplement
the kernel proof; they never substitute for it. Replacements, symlinks, hardlinks,
metadata changes and lost ownership refuse. A failed check stays failed even if
bytes are subsequently restored. A healthy proof is retired before VM startup
or shutdown: QEMU's normal auto-read-only block graph can transiently request a
writable backing handle. Startup acquires a new, unverified lease; the first
existing post-startup verification gate must read all bytes before that new
proof becomes reusable. Disk reads never delay serial attachment inside the
power callback. Existing writable handles instead retain full reads.
Any checks between retirement and reacquisition also read all bytes. No cached
digest crosses a disk transition, and a broken proof cannot be retired and retried.
The full backing-byte audit establishes another new proof after outer restoration,
before finalization. Release checks and closes every retained
descriptor before releasing the VM lock, including on interruption or cleanup
failure. Descriptors are never passed to workers, and no proof is serialized or
reused by recovery or a reopened maintenance operation.

Recorded `cleanup-requested` recovery can also audit a powered-off domain whose
inactive XML exactly matches the saved original configuration. It independently
checks the accepted baseline bytes, snapshot, guest contents and configuration
again before completing the journal. This branch never starts, stops, restores
or redefines a domain, and leaves the original attempt failed. Other off-state
configurations still refuse recovery.

This relies on the supported mounted filesystem's kernel enforcement and the
existing trusted-controller boundary; it does not authorize raw block-device
mutation or changes to the kernel or host security configuration. Guest code has
no host share during an attempt. Backing owners and host administrators can
request writes, but those requests invalidate the kernel proof. The accepted
baseline, snapshot and persisted schemas are unchanged. Update activation is
`none`: this test-only behavior takes effect on the next controller invocation.

`baseline:verification` emits fixed fields for boundary, call count, mode, bytes
actually read, elapsed seconds and outcome. Totals are retained in installed and
public E2E results; the ledger now measures finalization separately from cleanup.
The [kernel/refusal regressions](../unit/test_backing_verification_cleanup_safety.py)
also join the automatic isolated safety prerequisites.

### Earlier provenance qualifications

Host tests exercise actual Git trees, artifact/fixture verification and the real
private collector with synthetic scenario records. They do not establish live
VM provenance or customer behavior. E2E-034 supplies separate live public
controller proof; 153 customer/fault variants remain pending.

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

The missing customer-visible notice cannot be added as another match or capture
on the current installation console. `onpc_serial::run_install` selects the
pinned os-autoinst `virtio-terminal`; that console constructs a text-only
`serial_screen`, whose `current_screen` returns no image and whose screen-update
method is a no-op. The VNC `sut` surface remains at GDM during this serial flow,
so selecting it would capture the greeter rather than the package notice.
`onpc_install::run` also seals explicit capture before authentication, and the
controller rejects every screenshot field on install/reboot stages. These are
necessary privacy boundaries, not missing calls to `assert_screen`.

### Visible VT6 installation terminal

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

The joined authentication review found the capture reader's whole-stat defect
also in `vt6_command.READ_MARKER`. A delayed first read on `/tmp` reproduces a
false refusal locally. The guest's `marker_identity` now compares the stable
fields of `provenance.identity` plus UID/GID, excluding read-driven atime and
preserving nanosecond mtime/ctime. The delayed-read regression and per-field
descriptor/path mutations in `test_e2e_vt6_command.py` protect that boundary.
This correction now has completed live command-stage evidence in attempt 10;
normal worker shutdown remains unqualified for that integrated route.

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
still the qualified smoke; the graphical runner owns screen matching and scenario execution.

## Shared guarded worker

`e2e_worker.run_distribution` now runs the qualified, fixed credential-free
distribution for `tests/integration/check_graphical_smoke.py`. Invoke the smoke
through `tools/run-tests integration check_graphical_smoke`; the dispatcher runs
isolated cleanup prerequisites before entering the existing VM lease. This is
worker integration evidence, not an executed E2E-001 variant. The distribution's
Perl sources still live in `tests/integration/graphical_smoke`; this extraction
does not replace its feasibility geometry with the graphical runner's stable matching.

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

Case 3 uses `enter_parent_gdm_password(journey)` from the same helper. Its fixed
controller stages require an independently rejected wrong-account prompt followed
by two fresh intended-account/empty-masked-field/focus observations. The second
durable acknowledgement immediately precedes secret input; review mode, capture,
changed order, failed checks and replay refuse. Only the zero character count is
read from the password interface, never its contents. See the
[functional credential contract](../../docs/TestAutomation/E2E-Building-Blocks.md#functional-validation).

The maintained Perl `lib/onpc_password.pm` also provides `enter_password(role, surface)`
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
The observation-only fixed tag, `onpc-gdm-parent-installed-account`, matches the
reviewed fixture label after installation/reboot. Both retained GDM renderings
can occur after setup; installation state does not uniquely determine label
pixels. The fixed alternatives in `parent_needles.GDM_RENDERINGS` share their
canonical observation or account-input tag. Observation alternatives have no
click point; input alternatives retain the reviewed label, center click point
and 100% threshold. Arbitrary aliases, roles, password extensions and altered
alternative layouts refuse staging. Evidence retains the actual matched needle
name and resolves only these fixed aliases when checking the expected stage.

### GDM readiness and graphical return

Case 1 uses `accessible_ui.py` through `UiObservations` and the shared `ui:`
checkpoint reconciler. It activates the showing, enabled fixture account by
public name/role: navigate Home/Down from the current list order, verify account
focus, then press Enter. It verifies the intended account label and focused password role
with the account list hidden, dismisses with Escape and observes the list again.
After real serial command output and logout, it selects `sut` and requires a
fresh semantic list observation. Ordered evidence cannot reuse the initial
list to prove return. No geometry or image similarity gates these operations;
password text is never read, and these checks authorize no graphical secret.
Serial recipient safety and the smoke's independent harness checks remain intact.
Public logind session metadata resolves the sole active local greeter's account,
including dynamic GDM accounts. The adapter waits for its owned session bus;
missing, ambiguous or wrong-owner connections fail before any UI action.

The following pixel helpers remain for legacy and credential qualification:

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
`onpc-gdm-parent-installed-account` tag at 100%. Its two reviewed renderings
match the same fixture identity; comparing one rendering against the other
alone scores about 87.9%. Only the canonical fixture label and a 16-pixel blur
border enter each asset; other accounts and the clock are blacked out. The
[pixel regressions](../unit/test_e2e_gdm_pixels.py) exercise installed tinycv
against both renderings, bounded position changes, wrong identities, password
screens and the observation/input click boundary. A passing image comparison
does not replace complete live journey qualification.
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
pending customer scenario dispatch or claims full controller acceptance.

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

### Broker startup observation

`ReadOnlyObservations.read('startup-broker')` reuses the fixed guarded observation
transport and [startup probe module](startup_observations.py). The broker's
[`Service`](../../broker/oh_no_parent_control/service.py) exposes the read-only,
role-checked `GetStartupTimings` method after successful object registration.
Real monotonic nanosecond timestamps bracket
registration after completed execution-policy and extension reconciliation and
attempted best-effort session-cap cleanup. Failed mandatory phases produce no
timings/object; failed cap cleanup is safely logged and does not prevent
registration. Diagnostic-write failure leaves readiness and this direct timing
observation unchanged. Automatic diagnostics contain only elapsed phase lengths.

The broker is a static D-Bus-activated service, so one normal read-only
introspection request may activate it after GDM. This tests broker startup
independently; it neither requires nor establishes broker readiness before GDM.
The probe then pins the current unique bus owner/PID and systemd invocation,
requires active/running state without automatic restarts, reads the six exact
timing fields, and introspects that unique owner with autoactivation disabled.
Boot, owner and unit reads bracket collection. Phase timestamps must be ordered
inside the current process start/service activation bounds; systemd comparisons
use microsecond precision. Systemd defines the
[invocation ID](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.exec.xml)
as a distinct unit runtime cycle. Invocation/PID/bus identifiers remain in the
guest; only six timestamps, the canonical boot digest and a success flag leave.
Failure exports a fixed stage and latches the observer's failure.

The reader uses the current pinned service response without reading log files.
Missing, failed, extra-field, malformed or out-of-order evidence refuses instead
of inferring ordering from later availability. This is current-activation
evidence, not continuous history or proof against a privileged actor replacing
the service. It cannot replace E2E-028's independent faults. These guest-only
identity observations remain separate from automatic feedback diagnostics.
For authenticated installation, `gdm-return` now requires both startup probes
to match the actual customer reboot and fresh boot reads; pixels remain separate.

### Customer reboot observation boundary

`ReadOnlyObservations.wait_boot_change(previous_boot_sha256)` reuses
`vm_transport.Transport`'s pinned SSH connection settings, guest guard and
event-driven readiness loop. It requires a boot digest already obtained by this
observer. The fixed `BOOT_SHA256_PROBE`, also used by ordinary `read('boot')`,
hashes the complete kernel boot-id file in the guest; raw identity stays there.

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

The same held domain ID, serial stream and display remain subject to existing
lease guards; no reattachment, replacement adoption or in-journey restore was
added. The installation worker budget is 960 seconds: the existing 600 seconds
plus the 330-second boot wait and return allowance. Other workers retain 600.
The held serial stream returned a fresh login prompt live, and GDM appeared on
the held display. The corrected GDM match and backend return acknowledgement,
final preservation and product readiness still require a passing complete run.
`SerialConsole.step()` preserves partial sends and
backpressure; the existing controller returns to its event loop when input
remains buffered. Incomplete delivery
was a hypothesis, not a demonstrated defect. The new checkpoint records that
gate; it does not prove guest execution. Do not
clear an ordinary observation failure or recreate its observer to reconnect.
Ordinary E2E-001 keeps its unchanged-boot assertion; the installed-system
`Transport.reboot()` route retains its existing behavior.

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
no scenario ID, no inventory override and no customer assertions. The 153 customer/fault variants remain pending. E2E-001 is the canonical
public scenario recorder and terminal invocation smoke, superseding E2E-034.
