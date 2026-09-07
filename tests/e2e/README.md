# E2E inventory and runner contract

`scenarios.json` is the versioned starting inventory for
[E2E coverage](../../docs/TestAutomation/E2E-Coverage.md). All 156 variants are
currently **pending**. Inventory validation is host unit coverage; it does not
establish graphical behavior or complete Task 19A. The runtime evidence gate
and private collector have host-only regression coverage. The shared worker now
uses the private collector for diagnostics and has passed one guarded VM smoke.
The inventory-gated launcher and `make check-e2e` now support listing and
explicit execution refusal before privilege checks. Controller-owned provenance
capture and preservation checks now have host regression coverage. Ordered
controller recording and worker failure checkpoints also have host coverage.
The credential-free qualification now wires lease finalization, provenance
and observed-stage checkpoints; scenario execution dispatch remains unfinished.

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

`tools/run-tests e2e --artifacts /tmp/onpc-... --scenario E2E-001` and
`make check-e2e ARTIFACT_DIR=/tmp/onpc-... SCENARIO=E2E-001` currently fail with
`selection:pending`, before artifact access, privilege checks, cleanup tests,
worker imports or VM operations. Omitting the selector checks the entire
inventory. `LIST=1` rejects artifact arguments; other nonempty `LIST` values and
all nonempty `VM_IMAGE` values fail. Make forwards selector values through the
environment, so they cannot become recipe shell commands.

Both the unprivileged category launcher and installed dispatcher invoke the
same `runner.preflight`; refresh the latter with `./setup.sh --test-tools-only`
after dispatcher changes. Development activation is `none` (next invocation),
with no product or saved-data changes. Missing/unsafe inventory inputs fail
closed. Even a fully ready declaration cannot run until the execution controller
is connected: `e2e:execution-controller-unfinished` is an explicit remaining
implementation gate. There is no bypass, checkpoint or resume option. Listing
success is declaration inspection, never an E2E pass.

The JSON includes canonical case IDs, owner, status/reason, parameters,
environment, prerequisites, duration bound, ordered phases, assertions,
expected evidence and the SHA-256 of the exact inventory bytes read. This digest
identifies the declaration only. `provenance.VerifiedInputs` separately identifies
current source, requirement mappings, staged packages/assets and the verified
baseline's guest preparation. Execution dispatch must use that capture.

## Maintain declarations

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
Installation, About and feedback requirement-mapping gaps are explicit pending
work with owners and authoritative contract references. They must be mapped
before those cases become ready. No existing requirement is marked covered.

`pending` requires a reason and a null executable. `ready` requires no pending
reason or requirement gap and an existing `tests/e2e/*.py` or `*.pm` reference
(including subdirectories) plus its unique executable test ID. Validation never
imports or runs those files. Ready means registered for execution, **not passed**;
the future collector must reconcile actual scheduling and completed results
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
collected copies. The controller integration and real acceptance are pending.

| Fields | Required meaning for the collector |
| --- | --- |
| `run_id`, `scenario_id`, `variant_id` | One independent attempt and its exact selected identity; reruns have new attempt IDs. |
| `source_sha256`, `inventory_sha256`, `package_sha256`, `assets_sha256`, `environment_id`, `baseline_sha256` | Current input provenance. A product-free smoke records an explicit null package identity, never an invented package digest. |
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
Task 19A's worker integration must implement and exercise these capture boundaries.

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
later successful worker result cannot clear it. The future controller must
persist this fixed failure code with its other attempt outcomes. Checks detect
changes at these boundaries; they are not a filesystem monitor.

Host tests exercise actual Git trees, artifact/fixture verification and the real
private collector with synthetic scenario records. They do not establish live
VM provenance or customer behavior. All repository variants remain pending and
the launcher remains closed until real scenario collection is connected.

## Verify edits

### Asset transfer qualification

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
This does not complete the remaining authenticated secret/console transport.
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

The outer `cleanup` callback owns `Lease.finish()` and actual host/source/VM
preservation checks, and returns the exact `CLEANUP_FIELDS`. It must retain
the held lease. Call `recorder.validate(verified)` after cleanup and before
release; it requires a complete, held lease and uses `VerifiedInputs.validate`
around the final report copy. Any `acceptance-rejected.json` is a terminal
failure, including if a late input/copy change follows an initial gate pass.
An `acceptance.json` file alone never establishes success. A failed report write
preserves earlier checkpoints and raises the original error; it cannot promise
new durable evidence when storage itself is unavailable.

Live wiring must call cleanup once, validate before lease release, and retain
records on worker/bootstrap/interruption paths. `Lease.__exit__` performs its sole
`finish()` attempt, invokes its trusted `finalize(lease)` callback while held even
after cleanup failure, then releases. The callback must only check and report;
never restore or release again. Earlier errors retain precedence through
finalization and release failures. Scenario dispatch, reviewed screen production
and authenticated transport remain acceptance work. Test-tool
activation is `none` (next invocation); no product data or installation changes.

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
An empty secret registry is appropriate only for this fixed credential-free
distribution; authenticated scenarios need the remaining secret/capture work.

`tests/unit/test_e2e_worker_cleanup_safety.py` covers ownership refusal, stale
inputs, identity replacement, timeout, nonzero status, interruption at each
execution boundary, report failure and combined cleanup/original failures. It
is automatically included in the dispatcher's isolated safety prerequisites.
The [worker integration evidence](../../docs/TestAutomation/Evidence/19A-Worker-Integration-20260907.md)
records the real run. The launcher preflight is now implemented; actual scenario
records and authenticated transport remain unfinished.

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
no scenario ID, no inventory override and no customer assertions. All 156
variants, including E2E-001, remain pending.
