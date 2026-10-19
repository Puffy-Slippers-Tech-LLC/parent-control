# 006 — Integrate retained-view native admission

Acceptance: host

## Staged prerequisites before this consumer resumes

The developer requested the [staged smaller-task breakdown](../Kiosk-Prompt.md#smaller-execution-slices).
The following prerequisite block was inserted immediately before 006 in the
queue; completed rows now link to their retained acceptance:

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 006f | [Finish manager lifetime composition witnesses](../Kiosk-Prompt.md#manager-lifetime-composition--006f) | 006e | Complete only the manager-identity and exit/reexec rows of the original finite composition table | Host passed: 593 checks, 138 paired transactions; exact map and owned cleanup retained |
| [x] | 006g | [Finish writer and host-source composition witnesses](../Kiosk-Prompt.md#writer-and-host-source-composition--006g) | 006f | Complete only concurrent-writer and original-host-after-attachment witnesses from the original table | Host passed: 672 checks, 19 added controls; exact map and owned cleanup retained |
| [ ] | 006h | [Finish receipt, publication and closure witnesses](006h-publication-composition.md) | 006g | Complete only source/invocation receipt, publication-cut and owned-closure witnesses from the original table | 20–30 min; reuse existing composed controls |

006's Requires now includes 006f, 006g and 006h, preserving every original
dependency and Scope. The master now points to 006h after
[006g's host acceptance](../Kiosk-Prompt.md#writer-and-host-source-composition--006g).
The insertion itself granted no acceptance credit. After all three pass,
resume 006 by auditing every original table row and exact input applicability,
then finish cumulative host checks and the final build. Keep this consumer
unchecked until its whole original acceptance passes; split progress grants no
credit. Do not reinsert this already queued block on resumption.

## Current execution boundary after the integration split

The real-policy probe passed in
[006e](../Kiosk-Prompt.md#bootstrap-permission-reconciliation--006e), before this
consumer's staged composition prerequisites, with complete candidate-bound histories on both registered
targets. Those receipts qualify actual bootstrap permission and both production
entrypoint routes; host fixtures alone still cannot establish those permissions.
Recheck their exact package/policy/frozen-input applicability after later edits.
Task 006 remains unchecked and keeps every original acceptance obligation;
resume its combined matrix and final host/build checks after 006f–006h pass.

The five sessions below made substantive component progress; they did not reach
complete production integration. This is a sizing split, not a failed approach
or task acceptance. The [queue](../Kiosk-Prompt-Queue.md) records the accepted
[006c fresh-manager transaction](../Kiosk-Prompt.md#fresh-kiosk-startup--006c) and
[006d retained reuse and paired production dispatch](../Kiosk-Prompt.md#retained-kiosk-reuse--006d).
Resume this task at the remaining composition matrix below. Preserve all existing implementation,
tests and retained evidence; do not restart the design or recreate the helpers.
Unfinished checkpoint commit `2f728697` preserves the existing implementation
without acceptance. The unrelated proof-document edit remains outside that
commit and protected by the retained run's ownership baseline.

Task 006 remains the original consumer and owns final composed acceptance:
independent native exit/reexec/concurrency, source-identity and publication-cut
witnesses; both bootstrap-policy checks; cumulative affected host checks and
the final build. Its original queue Scope and acceptance remain unchanged.
Prerequisite passes may be reused only for unchanged inputs and exact assertions;
006 must close every remaining row in the design's finite composition table.
No component count or prerequisite close-out completes 006 or installed 007a/007.

Start from the actual `kiosk_confinement()` production dispatch delivered by
006d and map each required witness to the full initial or gate transaction.
Use deterministic barriers at acquisition, post-clone, binding, ready and final
proof/MAC boundaries. Cover manager exit before/after the decision, compatible
and incompatible reexec, competing admission/configuration/loader writers,
replaced locks, required host drift after attachment, wrong/missing recursive
sources and interrupted publication/cleanup. Prove original manager records and
dentries stay unchanged, setup descriptors close, and only identity-owned state
is released. Keep the existing absolute deadline and four-generation bound.
Verify trusted bootstrap access and both reexec paths on both policy backends
at this host scope; generated text or doubled enforcement alone supplies no
actual native permission proof. Installed histories remain 007a/007.

Reuse the existing native/PAM fixture and resource owners. Add only missing
composed assertions, run their focused tests plus the affected cumulative
maintained selection and documentation consistency checks, then `make build`
after the final packaged edit. Preserve failures and exact restoration/cleanup.
Close only 006 after all its original obligations pass; advance to 007a under
the shared close-out contract. If an independent missing mechanism is discovered,
use a bounded prerequisite rather than expanding this final acceptance task.

The historical checkpoints below describe the implementation at each session's
boundary. Their instructions to continue all integration inside 006 and their
then-current Next task statements are superseded by this allocation. The fifth
checkpoint is the starting inventory for 006c/006d, not composed acceptance.
Historical bundle links below now point to their complete carried-forward
contents carried forward by the latest accepted prerequisite; original counts
and hashes remain historical. The 006d master receipt records the final candidate,
exact host selection and focused passes available for applicability review.

## Combined-witness checkpoint before 006e

The existing fresh/retained native fixtures now contain **63 additional composed
controls**: 24 fresh and 39 retained. Fresh coverage includes independent open-file
lock contention, replaced lock/lease identities at selection/ready/pre-MAC,
record and ready durability cuts, atomic publication, clone/bind/attachment/
detach faults, three/four-generation bounds and same-byte foreign record
replacement with exact completed membership. Retained coverage adds acquisition/
post-clone/final manager/credential/task/namespace/role/executable refusals, real
thread churn, same-inode FD reexec, after-decision manager exit, and actual
foreign/shallow recursive-clone refusals. Independent tree, inode/content,
read-only mount, borrowed-FD, original-deadline and cleanup witnesses remain.

The first focused run, `20261019T194243Z-f205cc12`, passed **114/115**. Its
wrong-clone fixture selected the correct manager tree after namespace entry.
The first repair pinned the wrong host directory, but Linux refused cloning
that cross-namespace directory before the intended source-identity check
(`20261019T194555Z-7ebbbcf0`: three strengthened publication cases passed,
wrong-clone failed its applicability assertion). The final fixture prepares a
real foreign detached recursive tree before namespace entry, independently proves
its root/mount identity, then transfers it through the ordinary clone result.
Its unchanged expected source-clone refusal passed **1/1** in
`20261019T194716Z-3b8b717b`. These were proven fixture-selection defects; no
production behavior or assertion was changed to accept them.

The intermediate [723-file cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-6j3t0moh/evidence.zip)
retains all 701 previous files and both failed development runs, including the
three strengthened publication passes. SHA-256:
`f4f1b75f9d2ec42718b6196725b95baa1c83f6682cc2a9174f0e7b0c68f0828e`.
The final affected selection passed **3,283/3,283** in
`20261019T194737Z-19dcdf21`, informational source-input digest
`35c24d6e7b65aba471218e03365b136e5309fd7d754ec7eca21fd654e62fe1d6`.
Its exact 31 `tools/run-tests unit` module selectors, with `-q`, are the 24
listed in the master's 006c receipt plus the seven added in its 006d receipt.
This includes all **55 fresh** (45 complete transactions and 10 SELinux API
controls), **60 retained** transactions, both resource inventories and the
maintained **313 documentation** cases. The same final test inputs passed;
no product assertion failed. Final documentation verification/export follows
below before handoff.

No packaged input changed from 006d/HEAD `af43bfcbc43a91067e070034de5b30e4ece1724e`.
The two test-file SHA-256 values, fresh then retained, are
`297a72a00f86a7eea841b16f71a998862690168120c3f7a780e866d1e5ba5c98`
and `facc1b4dc4ae9cd0ac84cbc24ffe0abf7113ea71c512823f3787dcee38d31522`.
Resource review retains compatible private files, namespaces, bounded owned
children and one joined pipe-held thread; no live MAC/bus/service/UI/VM owner
was introduced. All subagents finished before cumulative verification.

No build is required for this checkpoint's test/documentation/comment-only edits:
they are outside `PACKAGE_SOURCE_FILES` and build dependencies. The accepted
006d build remains unchanged-input historical evidence; 006's final build stays
an explicit obligation after prerequisite execution and final input review.

Task 006 remains unchecked. First execute 006e through both real-policy passes
and cleanup. Then audit the whole finite composition table against exact final
inputs, finish any remaining composed assertion, rerun affected checks where
inputs changed and perform the final build/host acceptance. Existing component
or installed receipts may be reused only for their unchanged exact assertions.
The original acceptance, deadline, generation bound, other queue scopes and
007a/007 public histories remain intact. No task acceptance is claimed here.

Post-handoff documentation checks passed **313/313** in
`20261019T195047Z-c35b2061`. The verified final
[756-file cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-6j3t0moh/evidence.zip)
contains every prior receipt, both fixture-selection failures, the final
wrong-clone pass, cumulative 3,283-case pass and documentation pass. SHA-256:
`14900f5f8579ccdbc357622dceda0e324decc8a56e8951edcc33b04dfb1efcc8`.
All runner/fixture/export cleanup finished; all subagents are complete. No
installation, VM, live-policy/service change, staging or commit occurred. The
unrelated proof document and every other queue row's completion/order/scope/
dependencies are preserved. The master points to unchecked 006e and retains
unchecked 006 as its consumer. Continue with GPT-6.1 Sol High at 006e, then
resume this task's original acceptance after its declared prerequisite passes.

## Original cumulative integration obligations

Integrate native attachment/manager admission with 006a's owned immutable sources
and 006b's material selection. Reuse earlier primitives and receipts; cumulative
scope retains every original availability/drift assertion.

Implement only [005's reviewed design](../SystemDesign/Kiosk-Confinement.md#planned-retained-view-admission-proof) through existing Python/native preparation
and binding owners. Read the [master](../Kiosk-Prompt.md) and complete affected
callers, callees and shared state before edits.

Unrelated installed-app additions, removals and mode/owner changes must not
unnecessarily deny a retained healthy station. Preserve required-material drift,
manager identity/lifetime, enforcing MAC, immutable source and privilege-helper
checks. Handle disappearance, PID reuse, reexec, concurrent lifecycle writers,
interrupted publication and stale/replaced views without fallback to untrusted
host sources. Keep useful bounded diagnostics and existing size/time limits.

Add meaningful host/native tests with independent identity, mount-source and
publication witnesses; do not accept a self-consistent manifest as proof.
Update all applicable resource classifications and owner contracts. Run the
lowest effective affected maintained checks and `make build` after final
packaged edits. Restore exact private mutations and finish owned cleanup.
Record candidate and results; 007 owns the real installed histories.

## In-progress implementation checkpoint

Task 006 remains unfinished. The queue row and master pointer stay on 006;
these guard checks grant no composed admission or installed acceptance.
The pre-existing `docs/Kiosk-Confinement-Proof.md` edit is unrelated and preserved.

Implemented but deliberately unwired:

- [Native manager proof](../../tools/kiosk_manager_admission.h): bounded native
  system-bus observations, pinned proc/pidfd/task/root/namespace/executable
  identities, selected marker binding, exit/reexec and task-set refusal, shared
  transaction deadline and owned descriptor cleanup. Use `acquire_until()` with
  the already-started transaction deadline. The expected executable and marker
  descriptors still need independent receipt/content/role verification.
- [Original-host proof](../../tools/kiosk_host_proof.h): separately pinned `/`
  and `/usr`, component/alias closure, eight-field file assertions, native hashes,
  capabilities/labels, final named-edge checks, aggregate byte bound and shared
  absolute deadline. Use `roots_open()` before attachment and `capture_until()`;
  fixture-supplied roots do not establish actual host-root authority.
- `RetainedSourceProjection` in [preparation](../../tools/kiosk_confinement.py)
  adapts one natively verified clone to selection with constant descriptor use.
  Every component retains original inode provenance. Eligible ambient local-open
  errors narrow only the fresh invocation; no host source is reopened.
- `kiosk_pin_acquire_policy()` in the [native owner](../../tools/kiosk_confinement.h)
  separates retained ambient inode/topology provenance from current bind trust.
  Its ambient vector must come from the attested required closure. Strict
  acquisition/attachment remains strict, including required ancestors.
- Closed [native receipts](../../tools/kiosk_view_receipt.h) and
  [Python encoding](../../tools/kiosk_view_receipt.py) provide canonical M/V/I
  hashes, source classes/slots, full assertions, links, separate nested coverage
  and invocation narrowing. They require an independently constructed native
  expected closure; canonical M hashing is not a semantic material decoder.
- `InitialPreparation` plans the complete runtime/payload skeleton, freezes
  original ambient provenance and creates verified supporting copies under the
  existing owned scratch contract. `source_index` is a global layout slot;
  `index` identifies a class-local copy/input. Native copies are explicitly
  pending. No completed realization or ready record is produced.
- The [native descriptor channel](../../tools/kiosk_preparation_channel.h) and
  [Python receiver](../../tools/kiosk_preparation_input.py) bind closed ordered
  descriptor slots, role/backend/M/V and original absolute deadline. Actual
  helper launch, reaping and native verification of its results remain unwired.

Use `kiosk_pin_acquire_policy_until()` for composed acquisition. It checks the
original deadline within clone/coverage/topology work and failure reaping;
an unresolved worker retains its pidfd for explicit owned recovery. Standalone
recovery is separate from the failed admission and grants no acceptance.

The live legacy path additionally rechecks preparation's exact named lock inode
after locking and before MAC, and rechecks an existing PAM admission lease before
reuse. Private real-PAM controls restore the exact owned inode after each fault.

Still required before task acceptance:

1. Construct native expected authority from semantic M and independent original
   source/link/mount observations. Map selection's source indices to canonical
   receipt slots, including original masks. Compose receipt parsing and hashing
   with actual binding outcomes, required coverage and nested submount witnesses.
   Parser comparison alone supplies none of that authority.
2. Publish initial native copies with the supporting runtime/payload copies and
   complete skeleton. Integrate the unwired APIs; existing `prepare()` and v1
   binding still use the legacy whole-layout digest and absolute host sources.
3. Compose the ordered native transaction, explicit checked helper descriptor
   channel, recursive acquisition, fresh gate skeleton, final original-host and
   manager checks, ready publication, MAC and identity-owned cleanup. Keep one
   bounded preparation child and one shared deadline; do not renew it per phase.
   Include new headers in package sources when wiring their production caller.
4. Verify actual trusted bootstrap permissions on both policy backends and reexec paths,
   add independent complete binding/publication/concurrency/exit witnesses, and
   run the affected maintained selection and final package build. Then perform
   actual task close-out; do not count these unwired guard checks as acceptance.

Generated-policy controls verify both manager reexec entrypoints, restricted
bootstrap routes and effective common-attribute grants. They do not establish
loaded policy or real PAM namespace-entry permission. Receipt tests independently
observe real inodes/links and coverage records, but their nested objects are not
actual submounts. Channel tests use real anonymous SCM_RIGHTS and independent
kernel identities; no product helper or session is launched.

Host fixtures double the system-bus service, security roles and namespace
separation. The manager tests use actual proc/pidfd/exec/thread objects; the host
lookup tests substitute descriptor trees rather than mount over `/usr`. Existing
native pin fixtures use real private mounts. None qualifies real PAM/MAC access
or public installed admission. Final receipt references and cleanup are retained
in the session handoff until full acceptance.

First checkpoint validation: all **2,115/2,115** selected cases passed in
`20261019T111445Z-41128fbc` (1,802 affected checks plus 313 documentation checks).
Both `make build` package formats passed after the final packaged edit.
Package-source SHA-256: `33781c6d7572f9c18a1947c29801908c33849ec4b379ac65ba8f490c9aec3445`.
DEB SHA-256: `6bb5a3b10bd0c83783f5032154c08e7de8bbcddbed735e2debc976b68bb2dcae`;
RPM SHA-256: `c87f98a7916de92aa2f368ae6ebd01c00079bc98e79682c7c796e376b4be08ad`.
The new headers remain outside the package-source map until their caller is wired.

The first cumulative checkpoint bundle retained that run, available diagnostic
failures/retries and all carried-forward 006a/006b host evidence (221 files).
Its contents are carried forward in the current bundle below. Original SHA-256:
`a42f943fbc04b90f1b82a4e2c152b62a2bca701bbbcb54e90b8039a17159ad02`.
The first broad 006 report, `20261019T110952Z-34d54ad9`, rotated during diagnosis
before export; it is unavailable. The retained one-case diagnostic and six-case
retry record the same group-writable fixture executable refusal and correction.
The earlier 25 fixture-root failures are retained separately in the bundle.
Both fixture defects came from the developer umask; explicit safe fixture modes
preserve production assertions. The fresh complete pass replaces no lost failure
receipt and establishes no composed admission acceptance.

Independent GPT-6.1 Sol High review accepted only these unwired guards after
the named-edge/deadline corrections. All subagents joined; runner, build and
bundle cleanup finished. No product installation, VM, service or shared mount
changed. All other queue rows and the Next task pointer are unchanged. Continue
006 with GPT-6.1 Sol High; do not close it from this checkpoint.

### Second checkpoint validation

All **2,351/2,351** affected host cases passed in
`20261019T113059Z-012460fd`, including the 313 maintained documentation cases,
both scheduling inventories, all earlier affected confinement/PAM/material/pin
callers and the new initial-plan, receipt and descriptor-channel modules.
Native receipt tests enforce required copy metadata and reserve zero-link
renewal for retained vendor helpers. These are bounded engineering checks;
the composed native binding/ready/MAC acceptance remains unrun.

Independent GPT-6.1 Sol Medium review found acquisition's renewed cleanup wait
and unbounded-in-time coverage/topology walks. The original deadline now reaches
those paths. Deterministic mid-walk and cross-namespace worker-expiry controls
passed all 45 native-pin cases, with the original manager-like owner untouched,
no renewed admission wait and explicit pidfd-owned recovery. Final review found
no remaining blocker in that bounded correction. Static policy controls cover
effective generated grants and both reexec entrypoints, without loaded-policy
or real PAM bootstrap credit. All workers joined before final validation.

`make build` passed both formats after the final packaged edit. Source SHA-256:
`e1c08e6f35270806fb24a00a9084517437e2b40729f60bb2302d746096f534ff`.
DEB SHA-256: `09aa6699310b19cab6e85acae7c74f7dbca5f33624837caec8cf69f9bb3a16aa`;
RPM SHA-256: `859c1e97a4d396e20b02fa90efc1b2934999e92f9f80472e417eada4deb62287`.
The eight-file implementation checksum stream (in order: `kiosk_confinement.h`,
`kiosk_confinement.py`, `kiosk_host_proof.h`, `kiosk_manager_admission.h`,
`kiosk_view_receipt.h`, `kiosk_view_receipt.py`, `kiosk_preparation_channel.h`,
`kiosk_preparation_input.py`, all under `tools/`; `sha256sum` output hashed again)
has SHA-256 `bb35e93dfe9305184402604c5c9da532e617d3fce04ada28257ca04f8fd540f3`.
Unwired headers/modules still need package/install/dependency entries when their
production callers are connected; their contents are outside the package digest.

The second checkpoint bundle, now carried forward in the
[carried-forward cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-6j3t0moh/evidence.zip),
contained all 293 retained files, including the first checkpoint bundle's complete
contents, the 2,351-case run, narrow development passes and final **313/313**
documentation pass `20261019T113334Z-98d82122`. Original bundle SHA-256:
`70b9db6f0f6675e5fafa955b4a12970f6039f9746d108892273c5c6e0808fb0b`.
No test assertion failed in this second checkpoint. The rejected relative
artifact-reader request and unsupported unit timeout option ran no tests; the
correct absolute reader and supported launcher invocation passed.

Runner, build and export cleanup finished. No installation, VM, service or
shared mount changed. Unrelated proof edits are preserved; task 006 remains
unchecked with the Next task pointer on it. Continue with the four integration
obligations above, retaining all source/manager/host guards and cumulative proof.

### Third implementation checkpoint

Task 006 is still unfinished. This checkpoint resolves more of the original
integration prerequisites, without claiming the composed admission transaction.
The queue row remains unchecked and the Next task pointer remains on 006.

- [Semantic native material authority](../../tools/kiosk_material_authority.h)
  decodes closed M/config schemas, binds exact attested payload bytes, derives
  required classes/roles/content and full lexical/target proofs, and exposes the
  original-host specification. `kiosk_material_verify_host_until()` must follow
  capture and final revalidation: matching hashes alone do not prove source
  sizes, ELF content or native execution modes. It checks these through the
  original `/usr` root and the captured inode/edge assertions under the same
  deadline. Optional candidate absence and complete declared library membership
  remain independent native caller obligations. Library glob aliases retain
  their lexical routes and canonical sources; aliases cannot cross a different
  substitution source. None of these APIs acquires a view or publishes ready.
- `InitialPreparation` now makes and verifies real independent native copies
  alongside runtime/payload copies in the same identity-owned scratch. Native
  files use `native-N`, retain class-local indices and expose copy assertions in
  `plan()['native']` and each native source. Cleanup tickets cover those exact
  inodes. Supporting-only publication still refuses extra native members;
  combined publication requires full native composition and verification.
- Retained selection accepts the native-verified original `source_slots` table,
  including original masks, absences and gaps. Late ambient loss cannot renumber
  another source. The original V rows must still be retained when native creates
  I; coverage owner ordinals are separate from these source slots.
- [Preparation-child ownership](../../tools/kiosk_preparation_child.h) now
  supplies atomically acquired child pidfd ownership, fixed role/arguments,
  explicit channel/lock/lease duplicates and isolated standard descriptors.
  It carries the original deadline, closes all other setup descriptors before
  exec, rejects a renewed budget, and keeps an unresolved pidfd for explicit
  cleanup. The production `--native-channel` helper entry and two-phase
  measurement/selection protocol are **not implemented**; do not switch the
  existing caller to this launcher before completing that protocol.
- Attachment, staging topology scans, completion and ready publication now have
  `_until` APIs using the original transaction deadline. Retained source staging
  has an explicit provenance-only ambient vector. Final invocation completion
  and publication stay strict. Deadline-cut tests cover coverage, move, staging
  detach and atomic-ready boundaries; standalone wrappers remain compatible.

Independent reviews corrected native source-format/mode/size validation,
reserved-directory alias escape, lexical library-alias compatibility and
substitution-source alias crossing. Another review closed a helper descriptor
leak when setup opens occupied closed standard descriptors. The native-copy,
slot, child and deadline controls use private real inodes/processes/mounts and
independent witnesses; they do not compose real PAM/MAC admission.

The first focused run, `20261019T114114Z-aa832e4a`, retained 90 passes and nine
SELinux fixture failures before copy creation. The fixture expected no vendor
label while its private inode supplied `lib_t`; the local configuration now
declares that label before attestation, preserving production checks. The fixed
focused selection passed **202/202** in `20261019T114329Z-11d6623d`.
The cumulative affected selection then passed **2,454/2,454** in
`20261019T114850Z-4a0bb781`, including both scheduling inventories and the 313
documentation cases. The last alias-source correction and its additional case
followed that run and require the final focused material verification below.

`make build` passed both formats after the final packaged edit. Package-source
SHA-256: `20a92fe44c25831f4e0723dfff277881d21868354fec66048dcd7c9f4fd115e2`.
DEB SHA-256: `01549e558eb6d8fb67cd47da11feb9767b0011593a18a6f1b8fed83c9c6f6a8b`;
RPM SHA-256: `d878eb8327e1e928f1d19b7d9afef88ba69d316b91e88173adf513113125ba41`.
Unwired headers/modules remain outside the package map. Add their source,
dependency and install entries when wiring production callers.

The intermediate cumulative bundle `onpc-evidence-bundle-0frmuk77/evidence.zip`
contains all 329 retained files from the prior bundle and these three runs.
SHA-256: `aa516b2aa8a38c58d8be09601ff0f9b96e1031a6e1006d1bdd754de053ce847b`.
Final material/document verification and cumulative export follow below.

Remaining work is the actual production composition: one two-phase preparation
child; independently attested native M and current-host route completeness;
live manager/executable/marker selection and verified recursive source clone;
fresh skeleton, actual binding outcomes and independently verified V/I coverage;
combined no-replace copies/ready publication, final original-host and manager
proof, descriptor closure and MAC. Use the original deadline throughout. Add
the finite composed exit/reexec/concurrency/publication witnesses and verify
both bootstrap policy backends. The existing `prepare()` and v1 bindings still
use the legacy digest/absolute-host route. No composed acceptance is supplied.

Final focused material verification and the maintained documentation selection
passed **366/366** in `20261019T115109Z-8a04eec4` (53 material cases and 313
documentation cases), after the last alias-source correction. All other source
and test inputs from the 2,454-case run are unchanged. The ten-file checksum
stream (the second checkpoint's eight files, followed by
`tools/kiosk_preparation_child.h` and `tools/kiosk_material_authority.h`, in that
order; `sha256sum` output hashed again) is
`e8c71214d4d6ad3b157d829081246818cf0d5323aded58809471f9deefc26be3`.

The third checkpoint bundle, now carried forward in the
[carried-forward cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-6j3t0moh/evidence.zip),
contained all **341** retained files, including every prior checkpoint receipt,
the nine fixture failures, their passing retry, cumulative pass and final focused
verification. Original bundle SHA-256:
`cb89874ad40ebd1b9cc6e4fdbef1e7faef874b5efeee0fd4bf88bf18758a958f`.
Changed Markdown links and whitespace checks passed. All subagents finished
before final verification/export; runner, build and bundle cleanup finished.
No installation, VM, service or shared mount changed. Unrelated proof edits and
all queue statuses/order/scope/dependencies are preserved. Continue with
GPT-6.1 Sol High at the remaining production composition above; no task
acceptance or close-out is claimed by this checkpoint.

### Fourth implementation checkpoint

Task 006 remains unfinished and unchecked; the master pointer remains on 006.
The native PAM caller still uses the legacy `prepare()`/v1 binding route.
No composed admission acceptance is claimed by the work below.

- The [duplex channel](../../tools/kiosk_preparation_channel.h),
  [Python exchange](../../tools/kiosk_preparation_input.py) and
  [child owner](../../tools/kiosk_preparation_child.h) now carry ordered
  measurement, native selection and intended-result phases through one child.
  Every phase binds role/backend/M/V, original absolute deadline and independently
  observed descriptor identities. Measurement is discovery only: its M/config
  descriptors still require native semantic/attestation verification before
  selection. Invalid ordering or binding poisons the attempt for owned recovery.
- The [preparation service](../../tools/kiosk_preparation_service.py) measures
  current material, receives only native-selected sources, builds fresh parents
  through the target descriptor and returns an intended plan. Its gate path
  keeps the complete original V slot domain, including absences and masks.
  A single helper alarm bounds legacy work by the original remaining budget;
  native's pidfd/deadline remain authoritative. It writes no V, I or ready.
- `--native-channel ROLE 3 DEADLINE_NS` in
  [preparation](../../tools/kiosk_confinement.py) checks the exact inherited
  preparation/admission lock identities and anonymous socket, marks 3/4/5
  close-on-exec, and explicitly compiles checked installed support source bytes.
  It neither changes import search nor consumes cached bytecode. Opened-file
  trust and full named identities are checked before/after reads. Initial
  results include the exact cleanup ticket and copy-directory descriptor;
  `InitialPreparation.detach()` transfers that incomplete scratch only after
  a successful send and final verification. Native must receive the result,
  require a clean reaped helper, then independently verify named copies before
  binding/publication. Failed sends retain Python cleanup ownership.
- `kiosk_material_verify_routes_until()` in the
  [native material owner](../../tools/kiosk_material_authority.h) independently
  checks every optional candidate and exact declared library membership through
  the original lookup roots, with the original deadline and aggregate scan bound.
  A declared library directory always needs a complete required proof, even for
  an empty optional glob. Unknown ancestry of an absent optional route confers
  no source authority and does not become an ambient trust prerequisite.
- [Package sources and support installation](../../Makefile) now include all
  new native headers and preparation modules. Installed support is under
  `/usr/libexec/oh-no-parent-control-kiosk-support`; the activation manifest
  includes it in the existing kiosk reboot boundary. The new service/entry
  modules are reviewed compatible units with private files/descriptors and
  process-local alarm/import state; no cleanup/UI inventory owner was added.

Independent GPT-6.1 Sol High review found the support-loader replacement/trust
gap and the unselected-optional-ancestor availability regression. Both are fixed;
the relevant independent native/file controls pass. The final focused native
channel/child run passed **98/98** in `20261019T120046Z-7d665c35`, material authority
passed **80/80** in `20261019T120202Z-01c7c24e`, and entry/initial-copy/inventory
checks passed **200/200** in `20261019T120233Z-fcc27d15`. Service's earlier
**15/15** run was `20261019T115836Z-f81581ef`; its assertions are also selected
for cumulative verification. These are component/preparation checks, not the
composed binding/ready/MAC history.

The first material-route development run (`20261019T115722Z-e2f63632`) passed
74 cases and refused one new fixture's mode-0775 intermediate directory; the
fixture now explicitly sets its intended safe mode. Its one-case retry passed
in `20261019T115751Z-726c5d6c`. Those two raw reports and earlier narrow service/
channel reports rotated before export; they are unavailable and are not claimed
as retained evidence. The final focused 80-case run retains the corrected
assertions. The later unmatched broad-selection request launched no tests;
the corrected selection uses the maintained documentation owner names.

`make build` passed both formats after the final packaged edit. Package-source
SHA-256: `d3222126ff1780d361b0deeceb8c2234f0ff54147d16a3f003315134d70dd30c`.
DEB SHA-256: `424bf4fdee25eded2d7f02895da5057a260430df7327c93629cc343b15eb571e`;
RPM SHA-256: `e460277b24455fd9acb1fb32e686d5c14e176866f05d946ea458fa16a1192f03`.
The new guards are now in the source-package digest; their production native
callers remain to be wired.

Remaining work: compose the production native transaction, independently attest
measurement and verify its plan/copies; acquire/select the actual live manager,
completed receipt and recursive clone; derive required source/link/nested mount
coverage from native authority; bind checked sources into fresh parents and
construct actual V/I; combine no-replace copies/receipt/ready publication; repeat
original-host, route, enforcement and manager proofs; close every setup descriptor
and apply MAC while retaining lock ownership. Add complete composed exit/reexec,
concurrent-writer and publication-cut witnesses and both bootstrap-policy checks.
Use the same original deadline throughout. Do not switch the PAM caller to the
new child before these obligations are complete. 007 still owns installed history.

The intermediate cumulative bundle `onpc-evidence-bundle-tagdxv3_/evidence.zip`
retains all 341 previous files and the three final focused reports above
(367 files). SHA-256:
`c65c2164bb019fe406a8a9d841a54cdbe1072b877bf2bd58aebd91bdafe9804d`.
Final cumulative verification/export and cleanup are recorded below.

The final affected selection passed **2,690/2,690** in
`20261019T120556Z-d333385a`, including every earlier affected module, all four
preparation modules, material-route completeness, activation and both scheduling
inventories, plus the maintained **313** documentation checks. All subagents
finished before this run. No product test assertion failed on this candidate.
This run verifies the implemented components only; native production composition
and its required witnesses remain unrun.

The post-checkpoint documentation selection passed **313/313** in
`20261019T120809Z-aea7856e`. The
[carried-forward verified cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-6j3t0moh/evidence.zip)
contains all **391** files from the intermediate bundle and these two final
reports. SHA-256:
`707662e101bf5865870d4de9a9769ca60ef8a4b2900d113865bd019f186d89bc`.
Earlier bundle links now refer to their complete carried-forward contents.
Runner, build and export cleanup finished; all subagents are complete. No
installation, VM, service or shared mount changed. The unrelated proof edit and
every queue row's status/order/scope/dependencies are preserved. Continue with
GPT-6.1 Sol High at the remaining native transaction above; no acceptance or
queue close-out is claimed.

### Fifth implementation checkpoint

Task 006 remains unfinished and unchecked. The master pointer remains on 006;
the production PAM caller still uses `prepare()` and v1 binding. The new native
owners below have bounded component coverage, not composed admission acceptance.
The pre-existing proof-document edit is preserved.

- [Native intent verification](../../tools/kiosk_preparation_plan.h) decodes the
  closed helper result, derives required classes/roles/trees from semantic M,
  checks exact independently observed copies and ticket members, and preserves
  the full original V slot/origin domain for a gate. Native M owns the permitted
  tree parents; a helper cannot invent a deeper ambient-source allowlist. Initial
  late ambient changes can carry frozen intent to binding, which must either
  independently prove the original source or narrow it. That grants no source
  authority. Retained foreign inode/type and all required changes still refuse.
  The native caller must bind the ticket's parent to its own opened runtime root.
- [Native realization](../../tools/kiosk_native_realization.h) verifies the fresh
  skeleton and descriptor-relative sources, observes actual binds and recursive
  mount coverage, and constructs V/I from actual outcomes. Fresh I retains V's
  slots/origins while private masks/absences narrow only eligible ambient owners.
  Safe source assertions remain exact through binding; initial changed sources
  are never bound as replacements, and retained foreign provenance refuses.
  The separately checked private marker is excluded from receipt hashing and
  included, with actual private masks and nested coverage, in native pin inventory.
  Attachment uses a recursive clone and strict recursive read-only verification;
  the caller still owns staging completion, publication and final proof/MAC.
- [Native policy authority](../../tools/kiosk_policy_authority.h) independently
  binds current config/policy bytes to the owned successful-load record, captures
  their original-host named identities and repeats them and enforcement without
  a post-attachment process. Its SELinux handle is preloaded. Final MAC operations
  still need preloading by the actual coordinator. Host policy fixtures double
  kernel enforcement and establish no actual PAM bootstrap permission.
- [Native completion records](../../tools/kiosk_view_publication.h) provide
  closed pin-inventory encoding and ready parsing, exact flat membership,
  no-replace record/directory publication, boot/source/marker binding and
  retryable owned incomplete cleanup. Completed records survive refused
  post-ready work. The caller must independently verify completed mounts and
  bind the M/V/pin records and copies before writing ready; flags or parser
  agreement confer no mount/manager authority. This is not yet the composed
  initial or gate publication transaction.

The four headers join package sources. Their unit modules are reviewed compatible:
private files/descriptors, bounded waited compilers/probes and private user/mount
namespaces only; no live policy, bus, service, VM or cleanup/UI owner is added.

Remaining production work is unchanged in scope: replace the middle of
`kiosk_confinement()` only after composing the one-child measurement/selection
exchange, native policy/M/current-host verification, completed-record and
supporting-copy reuse checks, actual manager/executable/marker selection and
recursive acquisition, V-derived ambient vector, actual realization, combined
M/V/pins/copies/ready publication, final original-host/routes/policy/manager proof,
all descriptor closure and MAC. A completed ready reader must bind hashes,
boot/root/marker/source objects and full membership to the actual manager; the
new ready parser supplies syntax only. Gate I must remain invocation-private and
allocate no completed generation. Keep the same original deadline throughout.
Preserve unresolved preparation/clone pidfds until explicit owned recovery,
and do not reclaim helper scratch before successful reaping. Add the complete
exit/reexec/concurrency/publication-cut witnesses and verify real trusted
bootstrap permission on both backends. 007 retains the installed histories.

Validation and retained receipts for this checkpoint follow below.

The final affected selection passed **3,031/3,031** in
`20261019T123009Z-3d171fd1`: all previous affected confinement/PAM/material/pin/
preparation callers, the four new native modules, both scheduling inventories
and the maintained 313 documentation cases. All workers finished before this
run. Final focused intent verification passed **75/75** in
`20261019T122729Z-835a87c9`; native realization passed **27/27** in
`20261019T122857Z-095069fe`, including real nested mounts, actual V-to-I
derivation and independent preservation of the original manager-like tree.
Final completion-record verification passed **49/49** in
`20261019T122302Z-64f657bc`. Policy's 34 cases also pass in the cumulative run.
These remain bounded engineering results, not the required complete transaction.

Independent review corrected missing gate-source assertions, invented ambient
tree authority, late initial source handling, ambient nested trust loss,
recursive attachment, excluded-marker coverage and retry after partial owned
cleanup. The 68-case development run `20261019T122200Z-6df2ce63` retained six
fixture-order failures: new children changed a directory after its eight-field
assertion was captured. Fresh assertion capture after complete fixture setup
preserves the production checks; its retry and the final 75-case run passed.
An earlier fixture-only compiler warning failure, first policy/intent passes and
earlier narrow realization/publication reports rotated before export and are
unavailable. They are not claimed as retained receipts. An export raced that
rotation and refused without publishing; the corrected finite export succeeded.

`make build` passed both package formats after the final packaged edit.
Package-source SHA-256:
`09a1b528c7a3ef17d4df5148503f120ac66298dc6c32b1468d5e3ef0bc9c343b`.
DEB SHA-256:
`424bf4fdee25eded2d7f02895da5057a260430df7327c93629cc343b15eb571e`;
RPM SHA-256:
`0d8ab01fa440cfcd686203f58f8419553dbedd2de30d75ac3997d51bfd64853c`.
The new headers remain unwired: the unchanged DEB hash is consistent with no
new production caller. The package-source map now includes their contents.

The verified intermediate
[449-file cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-6j3t0moh/evidence.zip)
contains every file from the prior 419-file bundle, including the six fixture
failures, plus the final intent, realization and affected-suite reports.
SHA-256: `b1a910eaf94f91c3d49b65dde16444a9fafc9dad1430c74f4d04d541e5567572`.
Final documentation verification/export and cleanup follow below. Queue state,
order, scope and dependencies remain unchanged; no acceptance credit is claimed.

Post-checkpoint documentation verification passed **313/313** in
`20261019T123312Z-00b1e4e4`. The verified final
[461-file cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-6j3t0moh/evidence.zip)
contains all 449 intermediate files plus that report. SHA-256:
`53076e7482ab2e589a725bb39ae9aaa84cdfeb8c786235ebee9603dca5e8b5c5`.
Runner, build and export cleanup finished; all subagents are complete. No
installation, VM, live service or shared mount changed. Changed Markdown links
and whitespace checks pass. Task 006 and its master pointer remain unfinished;
every other queue row and the unrelated proof edit are preserved. Continue with
GPT-6.1 Sol High at the production composition above. The new APIs are ready for
that integration; no complete admission acceptance or queue close-out is claimed.
