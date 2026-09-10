# Reuse across the remaining work

Reviewed 2026-09-09 against task documents, the current handoff, executable
inventory and implemented runner interfaces, including 19B acceptance and
Task 20's partial installation qualification.
The [master checklist](Test-Automation.md#unfinished-tasks) owns completion
and [Continuation.md](Continuation.md) owns the next slice. Read only the row
for that slice and follow its relevant contract/limitation links; a whole-map
startup read is unnecessary. Shared fixes are published under the
[reuse workflow](Implementation-Workflow.md#reuse-established-tools-and-bound-harness-work).

The largest plausible token savings come from avoiding repeated investigation,
inventory construction, helper implementation and irrelevant output. No measured
token-saving percentage is available. Apply the [workflow](Implementation-Workflow.md)
and preserve every required case, assertion, safety prerequisite and real
customer operation. Task model defaults remain; reassess a smaller bounded
slice only after its difficult boundary is proven.

Apply the [app scope and prerequisite rules](E2E-Coverage.md#scope-tests-around-the-app)
before expanding a task: reliable supported fixture setup, lowest effective
test layer, and an explicit app risk for each expensive journey. This scope
review changes no task order or completion status.

## Existing interfaces to find once

- Parent remaining-time reads use the existing broker `GetTimeStatus` method:
  [screen-time contract](../SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities).
  Parent UI/time-status work must reuse this path; direct AccountsService grant
  reads require separate Polkit authorization.

- Host-side fixture/double libraries and guest assertion helpers:
  [shared support guide](../../tests/support/README.md). Use explicit support
  imports; do not import another collected case to obtain its fixture. The
  architecture regression enforces this dependency direction for existing and
  future cases. Synthetic evidence remains distinct from live acceptance.

- Installed selection, lease, staging, transport and real-caller assertions:
  [runner contracts](../../tests/integration/README.md#reusable-implementation-contracts).
  F1 and Task 14 are accepted; new areas extend their existing dispatch.
- Graphical declarations, input provenance, evidence gate and private collection:
  [E2E contracts](../../tests/e2e/README.md). The shared public controller and
  canonical E2E-001 smoke have [19B acceptance](Evidence/19B-Acceptance-20260908.md).
  Follow the [GDM/serial reuse record](#qualified-gdm-and-serial-helpers) and
  [installation reuse record](#installation-helper-and-open-limits) for their
  distinct qualification limits.
- Native/Flatpak process and package assets:
  [artifact contract](../../tests/integration/README.md#package-and-fixture-inputs).
  Snap and real-game delivery remain work; sleeping fixtures cannot prove gameplay.
- Approved selected checks, artifact builds, diagnostics and listing:
  [category commands](Approval-Tools.md#category-coverage-and-future-additions).
  Use implemented selectors; do not rediscover permissions or invent a launcher.

### Qualified GDM and serial helpers

Tasks 20–26 extend the [GDM readiness/return contract](../../tests/e2e/README.md#gdm-readiness-and-graphical-return)
and [serial credential/capture contract](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary).
Canonical helpers are [onpc_gdm.pm](../../tests/integration/graphical_smoke/lib/onpc_gdm.pm)
and [onpc_serial.pm](../../tests/integration/graphical_smoke/lib/onpc_serial.pm).
Their regressions cover [readiness refusals](../../tests/unit/test_e2e_gdm_helper.py),
[serial input and terminal framing](../../tests/unit/test_e2e_serial_helper.py),
and [ordered screen evidence](../../tests/unit/test_e2e_matched_screens.py).
[19B acceptance](Evidence/19B-Acceptance-20260908.md) retains the three complete,
reviewed qualifications and earlier fix evidence. Reuse them until an applicable
[invalidation condition](Implementation-Workflow.md#decide-what-invalidates-earlier-verification)
changes. This proves the runner smoke; product UI journeys still need their own
assertions and execution.

### Installation helper and open limits

Task 20 owns the [authenticated installation contract](../../tests/e2e/README.md#asset-transfer-qualification).
Read its [installation findings and reuse record](../../tests/e2e/README.md#installation-findings-to-carry-forward)
for canonical helpers, the prompt/echo and serial-cancellation solutions,
regressions, live qualification links and open executable-resolution diagnostics.
Authenticated installation, deliberate refusal and the exact final red notice
have live qualification. The notice proves emitted serial bytes; it does not
prove graphical rendering or reboot. The current installation console cannot
provide that missing pixel proof: its pinned os-autoinst `virtio-terminal` is
text-only, while VNC remains at GDM and explicit capture is sealed before
authentication. The [owning installation contract](../../tests/e2e/README.md#installation-findings-to-carry-forward)
and [boundary evidence](Evidence/20-Graphical-Notice-Boundary-20260909.md) define
the missing genuine graphical-terminal, reviewed prompt/recipient and notice
contract; replay, controller rendering and a post-hoc notice command are not
acceptable substitutes. The [visible VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal)
now records live baseline surface availability and locally tested fixed VT6
login/sudo recipient probes, their shared diagnostics and regressions. VNC worker
input, reviewed prompt/notice needles and live recipient qualification remain
pending; the [VT6 evidence](Evidence/20-Visible-VT6-20260909.md) does not qualify
authentication or E2E-002. These qualifications do not resolve the
intermittent recipient failure; diagnostics passed locally and were not triggered
in the latest live attempt. The [active Task 20 handoff](Task-20.md#task-20-continuation--2026-09-08)
owns changing attempt details and the next result. The
[customer reboot observation boundary](../../tests/e2e/README.md#customer-reboot-observation-boundary)
has local stale-boot, reconnect and refusal coverage, plus live changed-boot and
held-stream serial-return evidence. Complete graphical acknowledgement and final
preservation remain unqualified. An earlier wired attempt passed
provenance and installation but failed during the 330-second reboot observation;
the owning reboot contract links [retained evidence](Evidence/20-Customer-Reboot-Attempt-20260909.md)
and its missing command-result and probe-category evidence. The existing
pending-input gate already defers blocking observation through partial sends;
the owning contract corrects the earlier handoff's single-pump claim. New local
checks cover a durable drain checkpoint, fixed command outcome and categorized
boot-probe counts. The [instrumented attempt](Evidence/20-Reboot-Command-Result-20260909.md)
proved guest command execution and nonzero return, then stopped before the boot
wait. The [access diagnostic](Evidence/20-Reboot-Access-Diagnostic-20260909.md)
then observed an access-denied token; the exact method/policy cause remains
unknown. The owning contract records its live-qualified fixed reporting and the
locally tested long-form authentication-message extension; the retained zero
authentication flag cannot exclude a challenge. The fixed administrator reboot
now reuses the installer challenge and getty-derived recipient proof through a
separate `reboot-password` acknowledgement. The
[unblock intervention](Evidence/20-Reboot-Unblock-20260909.md) passed that proof,
command return zero, input drain, eleven transient SSH failures, changed boot
and a fresh serial login prompt. The observer now preserves SSH status before
ownership checks overwrite the shared command result. GDM appeared, but its old
needle failed; `onpc_gdm::return_after_reboot` uses a separately reviewed installed
label that matches the retained image at 100% locally. The full live return
acknowledgement and final preservation remain pending; the latest final refusal
did not retain its exact source/asset/baseline cause. The
[provenance contract](../../tests/e2e/README.md#controller-owned-provenance) now
retains a fixed final refusal code with local early/late cleanup coverage;
historical failure causes remain unknown and live reporting is unqualified.
No policy change or arbitrary
argv is exposed. Fold the corrected return into minimum E2E-002 readiness work;
do not reopen solved authentication or probe semantics without new evidence.
The first wired attempt stopped before installation at provenance refusal amid concurrent checkout edits; the
[owning provenance limitation](../../tests/e2e/README.md#controller-owned-provenance)
links retained evidence and regression coverage. Readiness and separate startup faults remain under the
[startup audit](Evidence/20-Startup-Audit-20260908.md).
The new [startup enforcement observation](../../tests/e2e/README.md#startup-enforcement-observation)
correlates the completed canary command, fapolicyd activation and GDM start in
the customer reboot's boot. Guest-program and acknowledgement regressions pass
locally; live qualification remains pending. The independent
[broker startup observer](../../tests/e2e/README.md#broker-startup-observation)
now correlates a product-generated monotonic phase/registration witness with
the current systemd invocation and unique D-Bus owner. Private-bus publication,
mandatory failure and tolerated-cleanup tests plus fixed guest/decoder/controller
checks pass locally; installed qualification remains pending. This includes
normal read-only activation of the static broker after GDM, not a new GDM gate.
Tasks 24A and 26B share this capability's stated current-activation limitation.
The fixed post-reboot installed-layout observer now reuses the transferred
package inventory and installed package/PAM/Polkit/session assertions; its
controller digest binding and callback composition are locally tested and
[recorded here](Evidence/20-Installed-Layout-Observation-20260909.md), but remain
live-unqualified with the complete E2E-002 journey.
Tasks 18A/18C and 26C should extend the applicable package/terminal observations;
other installed graphical tasks may use verified installation as prerequisite
setup under [Task 20's scope](Task-20.md). This helper does not establish
graphical PAM/Polkit approval for 21B–24 or complete E2E-002 acceptance. Changes
must verify affected consumers; keep unresolved limitations linked until closed
with evidence.

## Installed and runner work

| Task | Reuse and opportunity | Quality boundary to retain |
| --- | --- | --- |
| [19B](Task-19.md#task-19b) | Accepted: reuse the [qualified GDM/serial helpers and regressions](#qualified-gdm-and-serial-helpers). E2E-001 supersedes E2E-034; retain one canonical ordinary smoke. | Three reviewed qualifications are retained in acceptance evidence; repeat qualification only for applicable changes. Ordinary runs must not multiply implementation-only qualification. |
| [20](Task-20.md) | Extend the [installation helper and open limits](#installation-helper-and-open-limits), [qualified GDM/serial helpers](#qualified-gdm-and-serial-helpers), [startup enforcement observation](../../tests/e2e/README.md#startup-enforcement-observation), [broker startup witness](../../tests/e2e/README.md#broker-startup-observation), package assertions and asset transport. | Actual authenticated installation/reboot, independent broker and fapolicyd readiness; preserve the startup audit's existing requirement mapping. |
| [15A](Task-15.md#task-15a) | Extend F1 with one installed enforcement area and native/Snap/Flatpak case data; publish launch witnesses for 25A. | Every required platform, route, identity/matching boundary and other-user outcome. |
| [15B](Task-15.md#task-15b) | One owned-process controller and rollback witness set serves later 17B/21B/25B/26A. | Kernel identity, all relevant sessions, irreversible partial termination and unrelated-process survival. |
| [16A](Task-16.md#task-16a) | Share time/grant witnesses across arithmetic and separate clock scenarios. | Real Malcontent/AccountsService, both DST directions and midnight; controlled clocks never replace natural expiry. |
| [16B](Task-16.md#task-16b) | Reuse real-caller/ownership helpers for PAM/session cases; publish observations for 22A. | Authentication/account phases, exemptions, unavailable/corrupt stores, idle/suspend and other-user isolation. |
| [17A](Task-17.md#task-17a) | Audit existing `prepare_own_session` and transaction tests before adding missing races. | Deterministic contention/rollback; an existing method or source contract is not runtime coverage. |
| [17B](Task-17.md#task-17b) | Apply 17A's assertions to real short-grant sequences and reuse them in 22A/26C. | Both soft-app choices, replacement precedence, no termination at expiry, installed failure evidence. |
| [18A](Task-18.md#task-18a) | Build each required activation fixture once per verified build-input set; parameterize assertions and extend applicable [installation observations](#installation-helper-and-open-limits). | All four activation classes, changed/added/removed files, real process/session/reboot transitions. |
| [18B](Task-18.md#task-18b) | Inventory real supported schema steps once, then use data tables for their invalid/retry cases. | Every actual migration path, interruption and fail-closed data boundary; no invented historical releases. |
| [18C](Task-18.md#task-18c) | Extend applicable [package/terminal helpers and regressions](#installation-helper-and-open-limits) for removal/reinstall/purge; publish lifecycle observations for 26C. | Removal has its own final red notice and acceptance; installation qualification does not prove it. Real lifecycle and independent refusal/retry attempts remain required. |

## Graphical work

Use [scenarios.json](../../tests/e2e/scenarios.json) as the current declaration
inventory, inspect only assigned families, and extend gaps instead of creating a
second list or copying changing counts here. E2E-001 has
[19B acceptance](Evidence/19B-Acceptance-20260908.md) and supersedes the historical
E2E-034 harness declaration without duplicate ordinary execution. Declaration
readiness is not runtime acceptance or a final coverage limit. Family `owners`
can name several tasks; each variant's `owner` is its single execution owner.
Related tasks link that execution without copying it. For each graphical row,
reuse the [qualified GDM/serial helpers](#qualified-gdm-and-serial-helpers);
installation prerequisites follow the [installation contract and limits](#installation-helper-and-open-limits).

| Task | Reuse and opportunity | Quality boundary to retain |
| --- | --- | --- |
| [21A](Task-21.md#task-21a) | Provision accounts/input files with supported helpers; keep exhaustive values local and batch representative navigation/validation. | Live discovery of a real newly created account and standard-user UI denial; account-management UI is outside scope; resolve E2E-003 declarations and E2E-005 ownership below. |
| [21B](Task-21.md#task-21b) | Introduce one real kiosk approval helper here for grant setup; share it with 22–24. | Real UI/password flow; selected-child transaction ordering and other-user effects; no injected grant to avoid a later dependency. |
| [22A](Task-22.md#task-22a) | Reuse 16B/17B witnesses and 21B approval; share login/lock observations with 23/26. | Natural expiry, zero-time correct-password denial, retained/new sessions, both replacement choices and other foreground users. |
| [22B](Task-22.md#task-22b) | Reuse established sessions for display boundaries and a separate dependency-loss case. | Actual minute/second transition and recovery; screen evidence cannot be replaced by backend time alone. |
| [23A](Task-23.md#task-23a) | Extend the real approval helper by explicit surface and parent; reuse transaction witnesses. | Each parent, real denial/cancel/retry, both soft-app outcomes and exactly-once grants. |
| [23B](Task-23.md#task-23b) | One exhaustive local form table and representative graphical boundary/flow cases; group compatible values. | Both local form modes, actual overlay exits and per-child preferences; kiosk graphical acceptance remains 24B. |
| [24A](Task-24.md#task-24a) | Extend existing kiosk entry with containment and real agent recovery; reuse the [enforcement](../../tests/e2e/README.md#startup-enforcement-observation) and [broker startup](../../tests/e2e/README.md#broker-startup-observation) observations after live qualification. | Restricted session before/after requests; separate normal approval and fault/recovery attempts. |
| [24B](Task-24.md#task-24b) | Reuse 23's data table and authentication; add kiosk targets, exits and cross-surface round trip. | Both graphical surfaces execute; child/parent eligibility, independent mute and return-to-GDM semantics remain distinct. |
| [25A](Task-25.md#task-25a) | Reuse 15A fixtures/witnesses; audit each of E2E-019's 48 variants for the route/policy/control interaction it protects. | Every supported route and security interaction remains covered; no unrelated setup/password/presentation cross-product or silent case deletion. |
| [25B](Task-25.md#task-25b) | Extend 15B/21B process and transaction witnesses to multiple real graphical sessions. | Every targeted session, unrelated-user survival and separately observed partial failure. |
| [26A](Task-26.md#task-26a) | Reconcile canonical existing faults before implementing only missing races/transitions. | Actual fault synchronization and reversible/irreversible outcomes; retain strong reasoning for adversarial races. |
| [26B](Task-26.md#task-26b) | Use one persistence assertion set across declared restart boundaries and the [enforcement](../../tests/e2e/README.md#startup-enforcement-observation) and [broker startup](../../tests/e2e/README.md#broker-startup-observation) observations after live qualification. | Each required app/session/service/reboot/suspend boundary executes; prior state must arise from real UI use. |
| [26C](Task-26.md#task-26c) | Compose proven helpers and witnesses, including applicable [installation observations](#installation-helper-and-open-limits) and 18C's lifecycle results; preflight real-game and authorized-delivery assets. | Continuous real gameplay, natural expiry, lifecycle and both game modes; independently passing fragments never establish a journey. |

## Evidence and final acceptance

| Task | Reuse and opportunity | Quality boundary to retain |
| --- | --- | --- |
| [27A](Task-27.md#task-27a) | Extend F1/19A schemas and collectors; settle needed shared fields when an earlier runner introduces them. | Safe export, visual secrets, malicious archives, missing/extra evidence and first-failure reconciliation. |
| [27B](Task-27.md#task-27b) | After one adapter passes, batch mechanical mappings to the fixed contract. | Every runner and non-pytest layer, passing/failing artifacts, privacy and cleanup. Reassess model if a schema change is needed. |
| [27C](Task-27.md#task-27c) | Diagnose one measured synchronization issue; reuse unchanged transport qualification. | Bounded waits, justified repetition, complete attempts and preservation of the original failure. |
| [28A](Task-28.md#task-28a) | Compose existing selectors/inventories locally and in CI; deduplicate actual case IDs. | Input continuity, serialized VM, full inventory, fail-closed results and two reproducibility builds; build-input caching needs validated dependencies. |
| [28B](Task-28.md#task-28b) | Use accumulated requirement/case links for the independent semantic audit before the full gate. | Inspect actual assertions and current execution, including architecture/threat gaps; no historical pass or sampling replaces full acceptance. |
| [28C](Task-28.md#task-28c) | Write from verified outputs and link the evidence index. | Check documented commands/links; no product reruns for wording-only edits and no new coverage judgment disguised as editing. |

## Resolve before the affected batch

- **Scope/layer reconciliation:** pending customer/fault declarations are not
  executed coverage. Task 21A must replace E2E-003's OS-UI account creation with
  a recorded supported fixture event and live Parent discovery. Before changing
  case groupings/layers, follow the [matrix rules](E2E-Coverage.md#bound-the-matrix-before-expanding-it)
  and reconcile inventory, assertions and requirement links. This documentation
  review changes no executable declaration or coverage status.
- **21A/21B ownership:** E2E-005's six variants currently belong to 21A, but
  their complete allowance/grant/child-behavior journey crosses 21B's transaction
  boundary. Before accepting 21A, reconcile the pending declarations and task
  split. Prefer assigning the full transaction variants to 21B and retaining
  21A's independently verifiable discovery/validation scope. Preserve all IDs,
  actions and assertions, validate the inventory change, and link the shared
  result; do not create an acceptance cycle or count partial 21A screens as a
  complete E2E-005 pass. This documentation review has not changed the inventory.
- **Requirement gaps:** E2E-030/031 belong to 21A; E2E-032/033 to 26C. Their
  `requirement_gap` fields need actual normative mapping before readiness.
  E2E-002 and the independent E2E-028 startup faults already have the
  [Task 20 startup mapping](Evidence/20-Startup-Audit-20260908.md); implement its
  missing runtime evidence instead of reopening the mapping investigation.
  Check shared E2E-007/028/029 variant ownership at each consuming
  task as well; a family-level owner list is not a request for duplicate tests.
- **External prerequisites:** reuse 19P's [recorded inventory](Evidence/19P-Backend-Preflight-2026-09-06.md#capture-cleanup-and-downstream-prerequisites).
  Verify Snap tooling in 15A, actual schema versions in 18B, and game assets and
  feedback service/recipient/authorization in 26C before their expensive runs.
  Required unavailable capabilities stay explicit blockers. Inventory review
  does not authorize sending feedback or preparing a replacement baseline.
- **Provenance and timing:** document-only handoffs currently change the source
  identity used by package verification; follow the [reuse decision](Implementation-Workflow.md#decide-what-invalidates-earlier-verification).
  The accepted public 19A invocation took 1,520 seconds with a 49-second worker;
  roughly 372 seconds of finalization is outside its stage timing buckets.
  Carry this measured lead into 27C/28A; do not weaken preservation
  checks, cache a baseline proof or redesign the runner simply to shorten a wait.

Maintain decisions in their task/contract when implemented, then remove the
resolved warning here. Keep evidence in its original record. Update this map
when ownership, reusable interfaces or their qualification/limitation links
change, not after every experiment. Keep current task status in the master
checklist and changing attempt details in the active handoff.
