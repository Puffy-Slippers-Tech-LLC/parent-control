# Deferred policy-acknowledgement design

**Operator separation — 2026-09-14:** this is product engineering outside the
customer E2E queue. It is not selected by the launcher and is not a prerequisite
for Tasks 21–26. Resume only under a separate explicit product-design/repair
decision. The snapshot below preserves work, failures, qualified scope, artifacts
and unresolved questions; its old next actions, task ordering and settings are
historical instructions, not the current continuation.

## Unresolved product contract and blockers

The existing reload path acknowledges command completion, not the exact active
daemon policy. The candidate generation/decision witness is not established as
sufficient for complete activation, rollback or removal acknowledgement. Native
lifecycle, storage, sender-loss and sandbox qualifications remain valid only at
their recorded scope. Local positive-decision correlation is not a live receipt.
Broker integration, earlier-loss settlement, full-input binding and arbitrary
administrator-rule completeness remain open. Preserve these limits in
[the owning design](../SystemDesign/Applications.md#notification-recovery-and-acknowledgement-limit).

The historical failed reload/creation and cleanup cases below remain evidence;
later scoped corrections do not erase them. A missing internal proof is not
itself evidence that a customer's login or app launch fails. If a customer
scenario actually fails, its handoff must retain the visible reproduction and
link a separate product blocker here when applicable. Do not pass that scenario,
weaken its outcome or expand its E2E assertions into this protocol.

No product source, tests, payloads, installed state or runtime acceptance are
changed by this separation. Existing regressions and safety checks stay intact.
The remaining finite installed enforcement work is described separately in
[Task 15](Task-15.md); neither that work nor this design gates surface-only E2E.

## Historical Task 15 plan and evidence

Execute 15A and 15B separately. Product installation and policy changes happen
only in the [guarded existing VM](../../tests/integration/README.md). The retained product-free baseline is
restored only outside complete attempts; no VM copy, overlay, or intermediate
checkpoint is used. These are real installed-system tests. Their direct OS
calls and deterministic process fixtures cannot replace the graphical customer
journeys required by [E2E-Coverage.md](E2E-Coverage.md).

**Operator clearance — 2026-09-08:** the
[all-task VM clearance](Implementation-Workflow.md#vm-availability-for-all-tasks)
resolves the earlier writer-pause request, including contrary next-action text
in linked historical evidence. Finish the active local slice and cleanup, then
prioritize guarded VM qualification. Carry the clearance into future handoffs.
Runtime acceptance remains pending until the required tests pass.

## Implementation slices

Use the [implementation workflow](Implementation-Workflow.md). These are small
work boundaries within the existing task, not extra acceptance checklists.
Verification below is task acceptance; edits use the smallest affected selection.

| Task | First proof, then expansion |
| --- | --- |
| 15A | One native allow/deny and other-user check; prove Snap/Flatpak helpers next; then fill the route and filename matrix. |
| 15B | One owned-process isolation case; one rollback/partial-failure case; then extend the proven controls to every required identity format. |

## Task 15A

- Title: Test installed catalog and application launch enforcement.
- Depends on: Task 14.
- Complexity: high. A broad kernel-backed matrix can reuse the installed runner
  and deterministic fixtures without redesigning transaction ownership.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Work:
  1. Install the existing deterministic application fixtures for each relevant user. Verify system and
     child-only launchers, selected-child XDG precedence, and exclusion of the
     administrator's substitutions.
  2. Test allowed, hard, and soft policies with screen-time control both enabled
     and disabled. Launch native targets via desktop launcher, file-manager
     activation, and command; launch Flatpak by full identity.
  3. Cover exact paths, spaces, future matching versioned filenames, unrelated
     same-directory files, target refresh after update, missing-launcher rule
     retention, and the specified copied/renamed-target limitations.
  4. Add a deterministic, locally built Snap fixture in the guarded guest
     using maintained public tooling, recording its artifact and tool versions.
     Exercise its public application identity; native/Flatpak coverage cannot
     satisfy the specification's Snap requirement.
  5. Execute the same targets as the selected child and unrelated users to prove
     UID-scoped allow/deny results. Keep launch and backend assertion helpers
     reusable by 15B and Task 25.
  6. Update application-catalog and launch-enforcement mappings only for behavior
     actually executed.
- Verification:
  - Run fixture cleanup-safety regressions in isolation before live fixtures.
  - Run the full launch matrix in a fresh installed testbed, recording source
    and compiled fapolicyd rules, launch results, and per-user evidence.
  - Register and run this task's installed area with F1 and its prerequisite
    closure, then `make check` and `git diff --check` once for acceptance.
    Focused iterations select the affected case; no direct host guest-pytest.
- Completion criteria: native, Snap, and Flatpak launch enforcement has positive,
  negative, and cross-user runtime evidence.

## Task 15A continuation — 2026-09-08

**Current handoff — 2026-09-14: positive rule-decision correlation is locally qualified.**

**Result:** the [new correlation contract](../SystemDesign/Applications.md#rule-decision-correlation-boundary)
records the upstream v1.3.6 syslog interface and its limits.
`tests/integration/system_probe_decision.py::bind_positive_decision` binds one
independently supplied record to the existing `ProbeResult`, compiled fixture
marker and bracketing backend inputs. It rejects stale/foreign/ambiguous records,
changed backend/input identity, missing native settlement and unsupported rule
grammar. It returns correlation coordinates only; neither product activation nor
`ProbeResult.executed` changes. No guest collector/writer is connected yet.
This is test-only (`none` activation), with no new saved-data format.

**Verification:** `tools/run-unit-tests 'tests/unit/test_system_probe_decision.py'
'tests/unit/test_execution_probe_cleanup_safety.py' -q` passed **236**, including
**82** new correlation cases. The first 72-case batch and expanded 82-case batch
also passed; no test failure. Tested SHA-256: helper
`36d8c08eb339727cd292f4d62a1a5c909cff7b85dab818fe5f1a82c0920cb9fb`;
unit module `f853ad9b3899d3f3186f6a400611a8fcc2df44b8e1bd3b39bb51a7286c5cd573`.
These are synthetic journal/backend inputs with real result dataclasses, not
installed decision evidence. Link verification passed **4 documents / 237 links**;
scoped whitespace checks passed, including both new untracked modules (no-index
diff exit 1 denotes new-file differences, with no whitespace diagnostics).
No build, `make check` or VM run this slice;
fresh artifacts remain necessary for the next package-bearing attempt.
Browser source fetches returned 403/cache miss; direct literal upstream reads
succeeded. One guessed launcher source path was absent; the maintained
`tools/run-unit-tests` entry point resolved it. No execution/Polkit denial.

**Next bounded result:** add the guest-only decision collector/fixture and prove
one real positive record plus rule-attributed deny control using the qualified
native lifecycle. Read the new contract/helper/tests, `ExecutionProbe._run`,
`ProbeGeneration.prepare`, `system_enforcement.native_probe_lifecycle` and F1's
enforcement input/selector registration. Prepare the fresh marker before native
dispatch (without spending the gate's admission deadline on compilation), capture
local journal cursors and trusted daemon metadata, and retain exact restoration
ownership. First cover collector ambiguity, bounded reads and restoration locally,
then run the smallest guarded selection with fresh artifacts. Do not repeat
sandbox/loss/storage qualification. This observation still cannot acknowledge
activation: equal snapshots miss an intervening change-and-restoration, source
config does not establish effective mode, and arbitrary administrator-rule
completeness is unresolved. Full-input/writer binding, broker integration,
earlier-loss settlement, rollback/removal and the native/Snap/Flatpak matrix remain
open; 15A is earliest ready and unchecked, none bypassed.

**Cleanup/budget/settings:** the planned 20–30-minute local slice stays at this
boundary. All started commands and unit-runner subprocesses exited; no VM, probe
unit, lease or temporary runtime fixture was created. These local tests require
no guarded cleanup.
All-task VM clearance persists. Activation **2**, composition **3**, storage **1**,
sender-loss **1**, sandbox **1** attempts remain unchanged; retained failures below
remain failed. R1 is **0 charged hours / 0 new attempts**, checkpoint 4 hours,
decision hold none. Actual: **`gpt-6-astra` / `high`, Standard**.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** local positive correlation is proven; connecting journal collection,
pre-dispatch policy preparation and owned restoration still crosses unresolved
daemon causality and lifecycle boundaries.

### Retained sandbox attempt 1 — 2026-09-14

This historical qualification remains valid at its captured input identity;
its next-action/settings recommendation is superseded by the current handoff.

**Verified result:** `system_probe_sandbox.native_probe_broker_sandbox` runs the
existing native lifecycle collector as an unprefixed broker `ExecStartPost`,
without changing its entry point or execution restrictions. Verified transferred
inputs relocate into the existing private runtime root because `PrivateTmp`
hides `/var/tmp`; the worker retains the normal guest guard. Native success,
withheld-admission recovery and fresh success all passed, with effective
capability/seccomp/no-new-privileges comparison, Internet-socket refusal and
exact drop-in restoration. The [owning admission/sandbox contract](../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness)
and [15A reuse row](Reuse-Map.md#installed-and-runner-work) distinguish this
separate start-post process from broker event-loop integration. Test-only
activation is `none`; product code and saved-data formats are unchanged.

**Verification/evidence:** isolated `tools/run-unit-tests` over
`test_system_probe_sandbox_cleanup_safety.py`, `test_system_enforcement_cleanup_safety.py`,
`test_execution_probe_cleanup_safety.py`, `test_probe_bus_client_cleanup_safety.py`,
`test_probe_channel_cleanup_safety.py` and `test_probe_generation_cleanup_safety.py`
(all under `tests/unit/`, `-q`) passed **360**, including **29** new sandbox cases.
The `test_system_enforcement.py` / `test_system_runner.py` unit selection passed
**296**. `tools/run-tests artifacts build` produced `/tmp/onpc-test-artifacts-17ber6vc`.
`tools/run-tests system --artifacts '/tmp/onpc-test-artifacts-17ber6vc' --area
enforcement --test 'test_native_probe_broker_service_sandbox'` passed **1,097
safety tests / 3 subtests** and **all 5 installed executions**, no failures/skips.
Result: `/tmp/onpc-system-t5ira6cj/evidence/result.json`; private JUnit sibling
`../guest-results/enforcement.xml`, exported through the approved artifact reader
to `/tmp/onpc-artifact-export-xr68gnhm/enforcement.xml`. All three stages settled
on systemd `259.5-0ubuntu3.4`, with 4,000,000 µs effective timeout; both positive
stages remained `identity-unproven`, never policy receipts.
Source SHA-256 `83295c4c3933b74ccd7941b154bbd86f2ccffa9d31f35a13b502eb55991d0991`;
selected inputs `58c7d684a13e951b5e9a41135ff2c73be3921a0df33723a56b6234fb851540b6`;
package `113b6a4d309d1cdb0f21466fc577a68c46b57f2361dee30b8748394f35f2d37c`.
The selected-input manifest is retained at `../input/selected-inputs.json`
relative to the result directory; exported copy:
`/tmp/onpc-artifact-export-hyn3oe8i/selected-inputs.json`.
No checkout edits during build/run/collection/cleanup; later documentation
edits require fresh artifacts. Full `make check` and the complete 15A matrix
were not run. Sandbox attempt **1** passed; sender-loss **1**, storage **1**,
composition **3**, activation **2** remain unchanged; retained failures below
remain failed. No R1 recovery or execution/Polkit denial occurred.

**Historical next bounded result:** connect the qualified native witness to the still-open
rule-decision attribution gate. Read the [generation contract](../SystemDesign/Applications.md#generation-witness-design-gate),
its linked kernel-witness audit, `ExecutionProbe.run_native` and the execution-policy
activation caller. Establish the supported decision source and minimal binding
to the exact generation, compiled inputs and daemon invocation; implement its
local fail-closed binding checks before a new installed observation. Do not
repeat sandbox or terminal-loss qualification. Pre-terminal loss settlement,
broker restart ownership/event-loop integration, policy attribution and the
full native/Snap/Flatpak matrix remain open. At reselection, 15A is still
earliest ready and unchecked; none bypassed.

**Cleanup/settings:** every started command exited and evidence was collected.
The fixture restored the broker; outer cleanup and full restored-baseline byte
verification passed. No current owned operation or pending cleanup remains;
all-task VM clearance persists. R1 remains **0 charged hours / 0 new attempts**,
checkpoint 4 hours, decision hold none. Actual settings:
**`gpt-6-astra` / `high`, Standard**.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** native execution now works under the complete packaged sandbox;
binding that witness to an authoritative policy decision remains unresolved
security and cross-service causality work.

### Retained sender-loss attempt 1 — 2026-09-14

Permanent sender loss settles after retained terminal evidence.

**Verified result:** `ExecutionProbe._collect_after_sender_loss` fixes indefinite
cleanup after the dedicated sender disappears despite a copied successful
creation reply and terminal snapshot. It requires the original manager, sender
name absence and unit collection through the surviving read-only observer;
existing channel/client/generation gates finish cleanup. No replay, observer
mutation, process signal or policy receipt is introduced. Earlier loss with only
a native success frame still retains uncertainty and the exact witness. See the
[loss contract](../SystemDesign/Applications.md#settlement-after-permanent-sender-loss)
and [15A reuse row](Reuse-Map.md#installed-and-runner-work). Existing broker
module activation is `process-restart`; no new integration or saved-data format.

**Verification/evidence:** the new local reproduction initially had **6 failed /
1 passed**; after the fix all **154** probe safety cases passed, including
`test_native_closed_sender_settles_only_with_retained_evidence` and
`test_native_sender_loss_before_terminal_retains_uncertainty`. Five-file isolated
safety selection (same paths as retained composition attempt 3) passed **329**;
the subsequently added late/interrupted fault-helper checks passed in the **85**
case system-enforcement safety file. The component category passed **1,068 safety
tests / 3 subtests**, then **14** private-bus cases. Collector/runner unit files
passed **296**. Their first parallel launch was refused by the component
launcher's checkout lease; it exited with code 2, then passed sequentially after
the owner exited. This was a resolved runner refusal, not an execution/Polkit denial.

`tools/run-tests artifacts build` produced `/tmp/onpc-test-artifacts-obgdn6kn`.
`tools/run-tests system --artifacts '/tmp/onpc-test-artifacts-obgdn6kn' --area
enforcement --test 'test_native_probe_permanent_sender_loss'` passed **1,068
safety tests / 3 subtests** and **all 5 installed executions**, no failures/skips.
Result: `/tmp/onpc-system-lejxzgpd/evidence/result.json`; private JUnit sibling
`../guest-results/enforcement.xml`, exported to
`/tmp/onpc-artifact-export-z2j_7u90/enforcement.xml`. Both loss and fresh-success
stages retained native/terminal evidence and completed cleanup on systemd
`259.5-0ubuntu3.4`; the loss stage confirmed its original sender closed and the
observer survived. Effective timeout stayed 4,000,000 µs; `executed` stayed false.
Source SHA-256 `d9665bcaa1adba947690ff22ba96cce51d6ecbf521565efabd389cfedd81abc1`;
selected inputs `e7d3e55d69fd7c71fd8bb319e89192161a3334bcc33da9314b51f053b166a2fc`;
package `113b6a4d309d1cdb0f21466fc577a68c46b57f2361dee30b8748394f35f2d37c`.
Runtime source hashes: `execution_probe.py`
`d951f2226b5853575575c7b8d0ba417f1327907b24381054c4157566f1c77b93`;
`system_enforcement.py`
`4db71ad91e965664531df01b44a140504e20f33f6c86f5491fb856a95c82795b`.
No checkout edits during build/run/collection/cleanup; later documentation edits
require fresh artifacts next time. Four-document link validation passed (**227**
links, none missing), as did the explicitly excluded `git diff --check`.
Full `make check` and 15A acceptance matrix
were not run. Sender-loss attempt **1** passed; storage count **1**, composition
count **3**, historical activation count **2** remain unchanged. Earlier failed
attempts below remain failed. No R1 recovery was performed.

**Next bounded result:** qualify native creation/admission and owned cleanup
under the packaged broker's complete service sandbox. Storage/mount access alone
does not qualify its capability, syscall and address-family restrictions. Read
the [admission/storage contract](../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness),
`data/systemd/oh-no-parent-control-broker.service`, `ExecutionProbe.run_native`
and the installed lifecycle/storage collectors. Design the smallest guarded
invocation with real effective restrictions, no product test API, and locally
verified restoration/ownership before one installed success/refusal/fresh-success
selection. Do not repeat the now-qualified terminal-evidence loss experiment.
Pre-terminal loss settlement, broker restart adoption/in-flight recovery,
policy attribution and the full native/Snap/Flatpak matrix remain open. Task
15A stays earliest ready and unchecked; none bypassed.

**Cleanup/settings:** every command exited and results were collected; current
outer cleanup and full restored-baseline byte verification passed. No owned
operation or pending cleanup remains; all-task VM clearance persists. R1 ledger
stays **0 charged hours / 0 new attempts**, checkpoint 4 hours, decision hold none.
Actual settings: **`gpt-6-astra` / `high`, Standard**.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** terminal-evidence loss settlement is now locally and installed
qualified; executing the adapter under the full broker sandbox still requires
cross-service authorization and ownership reasoning.

### Retained storage attempt 1 — 2026-09-14

Broker mount access and retained storage pass.

**Verified slice:** `system_enforcement.native_probe_storage_lifecycle` creates
a generation inside the running packaged broker's pinned mount namespace,
requires the effective strict/read-only mount boundary, and refuses unsettled
collection. The same fixture-owned generation survives broker stop/start and
restart with exact identity/content; a fresh generation is independent. The
joined worker changes only its own filesystem state and never signals a
discovered PID. See the [admission/storage contract](../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness)
and affected [15A reuse row](Reuse-Map.md#installed-and-runner-work).
This qualifies storage, not broker adoption, its complete capability/seccomp
sandbox, in-flight work across death or policy receipts. Product code is unchanged.

**Evidence/verification:** isolated `tools/run-unit-tests` over the five safety
files named in the retained composition handoff passed **320 tests**; focused
`test_system_enforcement.py` and `test_system_runner.py` passed **296**.
`tools/run-tests artifacts build` produced `/tmp/onpc-test-artifacts-nur__707`.
`tools/run-tests system --artifacts '/tmp/onpc-test-artifacts-nur__707' --area
enforcement --test 'test_native_probe_broker_storage_lifecycle'` passed **1,057
safety tests / 3 subtests** and all **5 installed executions**, no failures/skips.
Result: `/tmp/onpc-system-zk0l5jew/evidence/result.json`; private JUnit sibling
`../guest-results/enforcement.xml`, exported through the approved reader to
`/tmp/onpc-artifact-export-fxzmhr5m/enforcement.xml`. Source SHA-256
`01affab5be9af25aabc423a388aa2d817b63f76f775db65ee59b10d21cf45aa1`;
selected inputs `517d1d93f1f6fbc5bd9946d97005369805af32df4eca9ed99d688b7defd716d4`;
package `1a745d8f27c776ec0ab19324b19451785422180b6bc6fa830778c84614bfc2a9`.
`system_enforcement.py` SHA-256:
`ef8a4900949580fb204e6345657f4a2b95290889470da652bcf135195bd1ba14`.
No checkout writes during build/run/collection/cleanup. Subsequent documentation
edits require fresh artifacts next time, while preserving this result's scope.
Documentation links (**222**, none missing) and explicitly excluded
`git diff --check` passed. Full `make check` and the complete 15A matrix were
not run. Storage attempt **1**
passed; composition count remains **3** and historical activation count **2**;
earlier failed attempts below remain failed. No new runner/Polkit denial or R1
recovery occurred.

**Next bounded result:** qualify permanent loss of the dedicated probe client
after confirmed native creation/admission. Use the retained adapter, bounded
recovery and exact ownership evidence; distinguish provable settlement from
explicitly retained uncertainty, without replay, residue adoption or manager
termination. First read the admission contract's dispatch/retained-reply table,
`ProbeBusClient.close`, `ExecutionProbe.recover` and their cleanup-safety tests;
locally validate the fault and cleanup before one guarded installed selection.
This is an uncovered lifecycle interaction, not another timeout diagnosis.
Policy attribution and the full native/Snap/Flatpak matrix remain required;
15A stays unchecked and earliest ready, with none bypassed.

**Cleanup/settings:** all started commands exited, exported assertions were
collected, both generation owners and worker threads settled, and the current
runner records cleanup complete plus full restored baseline byte verification.
No owned VM operation remains. All-task VM clearance persists. R1 ledger stays
**0 charged hours / 0 new attempts**, checkpoint 4 hours, decision hold none.
Actual settings: **`gpt-6-astra` / `high`, Standard**.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** storage ownership and ordinary native composition are proven;
permanent transport loss still crosses uncertain dispatch/reference ownership
and requires careful failure/settlement reasoning.

### Retained composition attempt 3 — 2026-09-13

Composition attempt 3 passes native
success/withheld-admission/fresh-success, effective timeout and owned cleanup.**

**Verified slice:** the packaged timeout correction now works on real systemd
`259.5-0ubuntu3.4`. Both positive stages retained native witness and terminal
evidence; deliberate admission refusal retained ownership, recovered on the same
adapter and allowed a fresh generation. Every stage reported 4,000,000 µs and
completed cleanup without promoting `executed` to a policy receipt. The
[admission contract](../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness)
and [reuse map](Reuse-Map.md) publish exact scope and limitations; the
[artifact contract](../../tests/integration/README.md#package-and-fixture-inputs)
now records fresh-build/installed use of its source-selection exception.

**Evidence/inputs:** `/tmp/onpc-system-jq_9bl4m/evidence/result.json`, sibling
`../guest-results/enforcement.xml`, and private reader export
`/tmp/onpc-artifact-export-spkf00gg/enforcement.xml`; artifacts
`/tmp/onpc-test-artifacts-j7ve_urb`. Source SHA-256
`5b0a50693de2396f53cc86ec37dfccd6f2fe1ef1313ff21b776cd5886f16feda`,
selected inputs `595270a5d9fbf7daf806c4055dc2d149a926af83fc0e0b99ca8e4c825e57ed3d`,
package `1a745d8f27c776ec0ab19324b19451785422180b6bc6fa830778c84614bfc2a9`.
No source edits occurred during build/run/collection/cleanup. Only documentation
changed afterward, invalidating artifact reuse under current provenance rules
without invalidating this result's recorded scope. Runtime hashes matched the
prior local qualification: `execution_probe.py`
`2e181b491ebd1c64285f4a0692dacd421b94ce10faa0ee1dbcb8ec27244dace4`,
`system_enforcement.py`
`ee998faa0d1a928a6a533469615949a702edc507cd45102a56bc608c1e753ba3`.

**Verification:** isolated `tools/run-unit-tests` over
`test_execution_probe_cleanup_safety.py`, `test_probe_bus_client_cleanup_safety.py`,
`test_probe_channel_cleanup_safety.py`, `test_probe_generation_cleanup_safety.py`
and `test_system_enforcement_cleanup_safety.py` passed **299 tests**. Fresh
`tools/run-tests artifacts build` passed build/verification. Then
`tools/run-tests system --artifacts '/tmp/onpc-test-artifacts-j7ve_urb' --area
enforcement --test 'test_native_probe_systemd_lifecycle'` passed **1,036 safety
tests / 3 subtests**, four package/reboot prerequisites and the selected continuous
lifecycle case; no failures/skips. Direct private JUnit reading was
filesystem-blocked; the approved artifact export succeeded, with no execution or
Polkit denial. Documentation links and explicitly excluded whitespace checks
passed. Full `make check` and the complete 15A matrix were not run.
Composition count is **3**, latest passed; attempts 1/2 below remain failed.
Historical activation count remains two. No unchanged diagnostic rerun is needed.

**Next bounded result:** qualify probe storage writability inside the packaged
broker service namespace and preservation of a retained generation across
stop/restart, without adopting residue. First read the admission contract's
runtime-directory section, `data/systemd/oh-no-parent-control-broker.service`,
`ProbeGeneration`, and `system_enforcement.native_probe_lifecycle` plus its safety
regressions. Extend the guarded installed selection using supported service
interfaces and identity-recorded fixture ownership; prove local refusal/cleanup
before a fresh package-bearing run. Do not infer namespace access from this
guest-root pass or add a product test API. Permanent-loss settlement, causal policy
receipts and full native/Snap/Flatpak acceptance remain open; 15A stays unchecked.

**Scope/cleanup/settings:** 15A remains earliest ready; none bypassed. All-task VM
clearance persists. Every command exited, results were collected and the current
runner records collection/infrastructure/cleanup passed, `cleanup_phase=complete`
and full restored backing-byte verification. No owned operation remains. No R1
recovery: **0 charged hours / 0 new attempts**, checkpoint 4 hours, decision hold
none. Source-selection use does not qualify R1 ownership or validation timing.
Actual settings: **`gpt-6-astra` / `high`, Standard**.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** native manager/admission/cleanup composition is now proven; the next
boundary still requires service-namespace and retained-generation ownership
reasoning across broker stop/restart.

### Retained composition attempt 2 — 2026-09-13

The following records the prior inputs and next-action state; the current
handoff above supersedes its unimplemented-correction and settings statements.

**Prior handoff: composition attempt 2 discriminates an API
PropertyReadOnly rejection; the audited timeout correction is ready for bounded
implementation. Native lifecycle qualification remains open.**

**Result/cause:** the registered `test_native_probe_systemd_lifecycle` passed all
four package/reboot prerequisites and private-root provisioning, then retained
`org.freedesktop.DBus.Error.PropertyReadOnly`. Creation still returned
`create-uncertain`, empty job and no frame/terminal evidence; bounded adapter
recovery failed. Withheld-admission/fresh-success stages did not execute. Systemd
is `259.5-0ubuntu3.4`. The [owning admission contract](../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness)
now records the matching upstream `JobTimeoutUSec` setter fallthrough and public
drop-in/timeout audit. Rejected-property identity is inferred, not directly
observed. Do not treat this API error as authorization denial or settled ownership.

**Next bounded result:** implement/qualify a package-owned
`onpc-execution-probe-.service.d/` drop-in providing `[Unit] JobTimeoutSec=4`;
remove the broken D-Bus setter only with equivalent effective queue-timeout
verification. Preserve service deadlines, AddRef sender ownership, one admission
and uncertain cleanup. `JobRunningTimeoutUSec` alone is not equivalent. Read
module `_properties`, `ExecutionProbe._admission_binding/_snapshot`, the contract's linked
upstream load/parser functions, package install/activation/removal owners and
`system_enforcement.native_probe_lifecycle`. Cover absent/overridden timeout
refusal and package delivery/activation locally, then observe effective manager
timeout plus the continuous success/refusal/fresh-success scenario in one run.
The correction is unimplemented; no upstream/system package or permission was
changed. The reuse map routes consumers to the updated contract.

**Current evidence/inputs:** `/tmp/onpc-system-2vsowz65/evidence/result.json`,
`/tmp/onpc-system-2vsowz65/guest-results/enforcement.xml` and reader export
`/tmp/onpc-artifact-export-h56gnjpx/enforcement.xml`; artifacts
`/tmp/onpc-test-artifacts-ocfffm18`. Source
`1af74054411e4ef686c2a40a9885c243b880fefa30d6b5ff039bcdd862e125e5`, selected inputs
`e42095316422a890c6bf30d070272e3a4394edb44c0c04a0bd8f63178ce0c55d`, package
`2a39dc1145584500658f1a646ce4608bae201e41fb793c265ad84a9552750599`.
Only documentation changed after this run. Original attempt 1 remains failed at
`/tmp/onpc-system-7owbex3p/evidence/result.json` and sibling enforcement JUnit,
with artifacts `/tmp/onpc-test-artifacts-ht2hi8ym`; its result retains exact digests.
Its journal export `/tmp/onpc-artifact-export-yzr4xuw1/service-journal.txt` had no
probe/transient/error match. Neither failure nor private evidence was overwritten.

**Verification/attempt limits:** 320 focused safety tests passed in isolation;
fresh artifact build/verification passed. The guarded runner passed 1,024 safety
tests / 3 subtests and executed exactly five selected cases (four prerequisites
passed, lifecycle failed). Read-only JUnit access was filesystem-blocked; the
approved artifact export succeeded, with no execution/Polkit denial. Historical
238 diagnostic safety, 296 collector/runner and 13 private-bus tests remain prior
local evidence; no runtime edit this slice. Full `make check` and 15A acceptance
were not run. Composition count is **2**, next **3**; historical activation count
remains two. The new error plus source audit meets the discriminator checkpoint,
but another unchanged diagnostic-only run is not justified. After local correction
and isolated safety checks, use `tools/run-tests artifacts build`, then
`tools/run-tests system --artifacts '<new directory>' --area enforcement --test
'test_native_probe_systemd_lifecycle'`. Fresh artifacts are required after edits.

**Scope/cleanup/settings:** 15A remains earliest ready; none bypassed. All-task VM
clearance persists. Namespace writability, stop/restart retention, native lifecycle,
full receipts, permanent-loss settlement and native/Snap/Flatpak acceptance remain
open. Every command exited; current runner collection/infrastructure/cleanup passed
with `cleanup_phase=complete` and full restored backing-byte verification. No
owned VM/process/client survives outer restoration. No R1 recovery was performed:
**0 charged hours / 0 new attempts**, 4-hour checkpoint, no decision hold.
Actual settings: **`gpt-6-astra` / `high`, Standard**.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** the API rejection is now known, but replacing its timeout delivery
crosses package activation and queued-job/admission safety; validate equivalent
bounds and real cleanup before reducing capability.

### Retained packaging and local qualification — 2026-09-13

The following packaging evidence predates the composition attempt above. Runtime
hashes below identify that earlier qualification, not the subsequent diagnostic
field addition. Current probe SHA-256 is
`bac514e573f0d1c1df4e2e49c5e7d5d31049e55e8ed32b293f23ab46b60b535d`;
current installed helper SHA-256 is
`0a89b287a30419e31125e9b549411c865d7f64e1430f5676010ed8579be79a14`.
**Scheduling update — 2026-09-11:** the operator prioritized installed-app
behavior and all independent work before Task 20 in the
[master checklist](Test-Automation.md#unfinished-tasks).
Resume the next 15A action below. Tasks 15A/B do not depend on Task 20's
graphical installation acceptance; installed cases reuse the existing guarded
runner's verified installation/reboot prerequisites. This supersedes the earlier
Task 20-first scope; preserve its recovery plan and ledger for later resumption.
All-task VM clearance persists. The old one-slice intervention stays consumed.

**Result:** the production install map now includes the three probe Python
modules and compiles the fixed gate/witness with Debian hardening flags, installing
them mode 0755. Both executables are `process-restart` activation inputs. The
broker unit declares its private mode-0700 runtime directory with preservation
across stop/restart; no package removal script deletes pending generations.
This is a provisioning declaration, not live systemd qualification. The
[owning admission contract](../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness)
and [removal contract](../SystemDesign/Package-Removal.md#payload-and-reversible-enforcement-cleanup)
record ownership and qualification limits. Boot `run()` and all probe runtime
code are unchanged; `native_verified` remains diagnostic and `executed` false.

**Packaging failure/fix:** the first Debian build succeeded, but inspection found
activation hashes from before debhelper ELF stripping. Its package remains failed
qualification evidence at `/tmp/onpc-15a-prestrip-manifest-20260913.deb`, SHA-256
`ee578f7753da0e04a64f8a2a61bba7742c5113ebf1745b2fdc114152623c2c0c`.
`debian/rules:execute_before_dh_md5sums` now refreshes the manifest after payload
transformations and before dpkg checksums. The
[owning publishing contract](../Publishing.md#package-update-activation) and
[reuse map](Reuse-Map.md#existing-interfaces-to-find-once) record the cause, hook,
regression and archive verification for Task 18 reuse.

**Verification:** final command `tools/run-unit-tests
'tests/unit/test_package_payload.py' 'tests/unit/test_package_activation.py'
'tests/unit/test_package_removal.py' 'tests/unit/test_systemd_unit.py' -q`
passed **88 tests / 7 subtests**. It covers real staged ELF refusal, isolated
installed-module imports, permissions/digests, activation addition/change/removal,
real stripping and hook ordering, and relocated removal preserving witness inode,
mode and content. The first selection failed three variants because an inserted
test displaced an existing assertion (`NameError`); restoring the original test
boundary fixed it. Subsequent selections passed, including the final exact-command
ordering check. No skip or policy denial.

Two `make build` commands exited 0; the second includes the digest correction.
Final package `output/oh-no-parent-control_1.1+ppa1~ubuntu26.04.1_amd64.deb`
has SHA-256 `0491cc5fe5bae8c083e2db86c069294500ce615016f14bb0b7e48de86827b508`.
Its retained extraction `/tmp/onpc-15a-package-bkB4SQ` passes **every** manifest
digest using `jq -r '.files[] | "\(.sha256)  \(.path)"'
'usr/share/oh-no-parent-control/package-activation.json' | sha256sum --check --quiet`
from that directory. Build artifacts are not a `VerifiedInputs` test manifest;
rebuild through the approved artifact category after final checkout edits before
a package-bearing VM attempt. Full `make check` and installed acceptance were not
run. No live activation attempt; the historical count remains two.

Changed-input SHA-256 (later edits are documentation only):

| Input | SHA-256 |
| --- | --- |
| `Makefile` | `505eeeef1f16ab5e531b0ffc71fbdcd4ba36efb6f8d6e15acfb379e1ad7433fb` |
| `debian/rules` | `91f73e13a972b5dbfaccea5420ebbaae7874f39e6eb2bca7ec319c11c7646b23` |
| `debian/package_activation.py` | `475175cde31e93482f4fbc3bcf5bde465f66c74598041dc4db555a08c73a37db` |
| broker service | `008d5a38b76eabf62bb285d8db80b6777b059338aa0939c1ff4c8c37115705bd` |
| `test_package_payload.py` | `e2306489e8f88db36fcb98e8f76a3d38673778a0a9305402ad7d101bc36c0c2c` |
| `test_package_activation.py` | `2156ddb798af3fdc88c2116cf832b8f378f091ece2c6923ef20eff52a73af6bc` |
| `test_package_removal.py` | `800c9c3c6cfcf66fdd166f8858a27c19d3265d588ae6bc5f6e471495d4c6b172` |

**Retained runtime qualification, unchanged this slice:** 568 focused unit tests;
1,011 isolated safety tests / 3 subtests and 80 component tests. These prove
synthetic-manager lifecycle, private-bus dispatch and separate native exec, not
their complete real-systemd composition. Prior collection/logger and fixture
umask failures remain corrected. Retained runtime input identities:

| Input | SHA-256 |
| --- | --- |
| `execution_probe.py` | `b53586fe0a004b29673d78211b2dcd17a32168ed9ae96293e1543fc79a759652` |
| `probe_channel.py` | `6e7a7d405fea722420372a39eeda8046f8393b87ebf4053e8d933240e7bcbdc8` |
| `probe_generation.py` | `c74ab9807a03d8d5013cc7129a67a8dfbd1c867c5af1a2c2ca63ad2cd645a420` |
| `test_execution_probe_cleanup_safety.py` | `24e6571fdec2a94226957cf3fd5365037ccbadfad68b427af74697a184cfd457` |
| `test_probe_bus_client_cleanup_safety.py` | `6c5d24a302cfa0cdcefbc1b54f66ff0dd90c639a88c9b25db08add4d8a787d5a` |
| `test_probe_channel_cleanup_safety.py` | `5930dd60a77bee1b605df14dfe7c84e687840bb9df8fc115667679f5c966f448` |
| `test_probe_bus_client.py` | `b4ee3e48f1a292d01a5de0990df512980201509f60a0cc9b950c90f317a7d254` |
| `test_execution_probe_native.py` | `49b613abe767e5f0071085ed9c099f5a54fb385d4058e722039f6ad0afd3d7d5` |

### Prior native qualification and scheduling history

The current handoff above supersedes the historical next-action/settings text
below; retained runtime evidence keeps its original scope.

**Scheduling correction — 2026-09-08:** preserve this unfinished work while
returning to [19B qualification](Task-19.md#task-19b-continuation--2026-09-08),
then [Task 20](Task-20.md), in master-checklist order. The old 19B writer hold is
cleared; 15A's independent eligibility no longer gives it scheduling priority.
Resume the next boundary below after those tasks are accepted, unless a new
evidenced blocker or explicit user instruction changes selection under the
[workflow](Implementation-Workflow.md#start-with-one-bounded-result).

**15A remains unchecked; corrected command-policy case passed.** Development-host and
existing guarded VM scope persists. The all-task operator clearance in the
[workflow](Implementation-Workflow.md#vm-availability-for-all-tasks) remains valid;
no renewed writer-pause confirmation is due.

**Verified change:** `FapolicydPolicy._reload` compiles with `fagenrules` and then
uses public `fapolicyd-cli --reload-rules`. The former `fagenrules --load` sent
SIGHUP, triggering the trust scan observed in the first failed run. Forward and
rollback paths share the rules-only sequence, bounded subprocesses and PII-safe
stage/error logs. Activation classification remains `process-restart`.

**Verification:** 185 focused tests/four subtests passed; isolated safety and
dispatcher safety each passed 519 tests/three subtests. Fresh artifacts
`/tmp/onpc-test-artifacts-gyyw4imz` qualified
`test_native_command_policy_is_uid_scoped` plus four package/reboot prerequisites.
Handle 31652 exited 0. All ten policy stages and twenty launches passed, including
hard/soft restoration and other-child allowance in both screen-time states.
The journal shows eight live ruleset changes without policy-save trust scans.
[Evidence, digests and commands](Evidence/15A-Rules-Only-Reload-20260908.md).
The first failed runtime remains failed; no mappings promoted.

**Refactor regression update — 2026-09-08:** the user-directed test infrastructure
refactor passed all five currently registered native cases in the full 238-case
installed run, including whitespace, future-pattern, missing-launcher and
selected-child catalog coverage. `make check` also passed 4,942 unit/contract
cases and 17 private-D-Bus cases. See the
[complete results and source identities](Evidence/Test-Support-Refactor-20260908.md#guarded-installed-and-graphical-evidence).
Reuse [shared support](../../tests/support/README.md) and the extracted
`system_assertions`/`system_accounts` guest helpers. Full selection now shares
identical helper declarations while refusing conflicting targets. Baseline
restoration and cleanup passed. These results do not prove the pending active-policy
acknowledgement contract or finish 15A; Task 20 retains checklist priority.

**Next 15A boundary when resumed:** successful notification still does not acknowledge daemon
activation. Establish a supported bounded active-policy acknowledgement, including
rollback failure semantics, before claiming synchronous transactions. Read
`execution_policy.py:_reload/reconcile`, its unit tests, the boot-only
`tools/execution_policy_ready.py` canary and this evidence's upstream references.
Validate locally, then rebuild and qualify the registered native area under the
existing VM guards. Do not substitute launch retries, sleeps or private APIs.
The earlier slice spent two live activation attempts (failure, corrected pass), plus one earlier
safety refusal; no unchanged retry. Fresh inputs are required after this handoff.

**Remaining:** acknowledgement, remaining native routes/update, Snap/Flatpak
and full acceptance. The historical kiosk `make check` failure remains in linked
evidence; the refactor's later broad check passed as recorded above. Preserve unrelated edits.

**Cleanup:** all commands exited; collection and baseline/host restoration passed.
Fresh VM status: state 5, ID -1. No owned process, lease, screenshot or recovery
remains; no approval/Polkit denial occurred.

**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** rules-only reload is qualified, but active-policy acknowledgement
and rollback still require transaction reasoning. Reassess to Sol high for
matrix expansion once that contract is proven; the shared
[model policy](Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff)
supersedes the earlier blanket pin.
**Remaining 15A:** sessions **Unknown**, minutes **Unknown**; the 5.4-minute
selected run does not size acknowledgement and remaining platform work.

## Task 15B

- Title: Test process confinement and execution-policy rollback.
- Depends on: Task 15A.
- Complexity: very high. Process ownership, retained sessions, and irreversible
  termination interact with privileged transaction rollback.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Start identity-recorded blocked and allowed fixtures in every live session
     of one child and as unrelated users. Exercise restrictive policy saves,
     approvals that keep soft blocks, and revocations.
  2. Prove all required child processes stop and every unrelated process
     survives. Verify kernel UIDs and pidfd confinement for native processes,
     kernel Snap labels, and UID-scoped Flatpak instance handling.
  3. Verify approvals allowing soft apps terminate no open process, including an
     already-open hard-blocked target.
  4. Force fapolicyd reload failure at a public OS boundary in the guarded
     guest. Verify atomic rule restoration, reload/read-back, and distinct
     PII-safe failure logs. Cover partial termination: strict filters and prior
     time remain, while terminated processes are not claimed to be restored.
  5. Add ownership/cleanup regressions for every new fixture controller and
     document the supported failure controls for later E2E reuse.
  6. Update termination, rollback, and isolation requirement mappings.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated termination.
  - Run termination and rollback cases in fresh installed testbeds, collecting
    process identities, filters, grants, and redacted logs.
  - Register and run this task's installed area with F1 and its prerequisite
    closure, then `make check` and `git diff --check` once for acceptance.
    Focused iterations select the affected case; no direct host guest-pytest.
- Completion criteria: real enforcement and termination respect user boundaries
  and preserve the specified state after reversible and irreversible failures.
