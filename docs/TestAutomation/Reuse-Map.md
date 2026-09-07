# Reuse across the remaining work

Reviewed 2026-09-07 against all task documents, the current handoff, executable
inventory and implemented runner interfaces. This review accepts no additional
task: the [master checklist](Test-Automation.md#unfinished-tasks) owns completion
and [Continuation.md](Continuation.md) owns the next slice. Read only the row
for that slice; this map is not another mandatory whole-document startup read.

The largest plausible token savings come from avoiding repeated investigation,
inventory construction, helper implementation and irrelevant output. No measured
token-saving percentage is available. Apply the [workflow](Implementation-Workflow.md)
and preserve every required case, assertion, safety prerequisite and real
customer operation. Task model defaults remain; reassess a smaller bounded
slice only after its difficult boundary is proven.

## Existing interfaces to find once

- Installed selection, lease, staging, transport and real-caller assertions:
  [runner contracts](../../tests/integration/README.md#reusable-implementation-contracts).
  F1 and Task 14 are accepted; new areas extend their existing dispatch.
- Graphical declarations, input provenance, evidence gate and private collection:
  [E2E contracts](../../tests/e2e/README.md). `ScenarioRecorder` and the shared
  worker exist; authenticated scenario dispatch is unfinished. Reuse the
  [19A handoff](Task-19.md#task-19a-continuation--2026-09-07) for current limits.
- Native/Flatpak process and package assets:
  [artifact contract](../../tests/integration/README.md#package-and-fixture-inputs).
  Snap and real-game delivery remain work; sleeping fixtures cannot prove gameplay.
- Approved selected checks, artifact builds, diagnostics and listing:
  [category commands](Approval-Tools.md#category-coverage-and-future-additions).
  Use implemented selectors; do not rediscover permissions or invent a launcher.

## Installed and runner work

| Task | Reuse and opportunity | Quality boundary to retain |
| --- | --- | --- |
| [19A](Task-19.md#task-19a) | Connect staging, worker, provenance and recording already present; finish asset, secret/console and controller boundaries as coherent slices. | One lifecycle owner; transfer integrity; read-only observation; real failure/cleanup evidence; dispatch stays closed until its contract works. |
| [19B](Task-19.md#task-19b) | Add needles/readiness to the proven backend; retire feasibility geometry once replacement is qualified. | Three complete qualification smokes for the changed harness; actual input, screen and console evidence. Ordinary runs execute the smoke once. |
| [20](Task-20.md) | Reuse package assertions and asset transport for E2E-002 and startup faults. | Actual authenticated installation/reboot, independent broker and fapolicyd readiness; resolve installation requirement links. |
| [15A](Task-15.md#task-15a) | Extend F1 with one installed enforcement area and native/Snap/Flatpak case data; publish launch witnesses for 25A. | Every required platform, route, identity/matching boundary and other-user outcome. |
| [15B](Task-15.md#task-15b) | One owned-process controller and rollback witness set serves later 17B/21B/25B/26A. | Kernel identity, all relevant sessions, irreversible partial termination and unrelated-process survival. |
| [16A](Task-16.md#task-16a) | Share time/grant witnesses across arithmetic and separate clock scenarios. | Real Malcontent/AccountsService, both DST directions and midnight; controlled clocks never replace natural expiry. |
| [16B](Task-16.md#task-16b) | Reuse real-caller/ownership helpers for PAM/session cases; publish observations for 22A. | Authentication/account phases, exemptions, unavailable/corrupt stores, idle/suspend and other-user isolation. |
| [17A](Task-17.md#task-17a) | Audit existing `prepare_own_session` and transaction tests before adding missing races. | Deterministic contention/rollback; an existing method or source contract is not runtime coverage. |
| [17B](Task-17.md#task-17b) | Apply 17A's assertions to real short-grant sequences and reuse them in 22A/26C. | Both soft-app choices, replacement precedence, no termination at expiry, installed failure evidence. |
| [18A](Task-18.md#task-18a) | Build each required activation fixture once per verified build-input set; parameterize assertions. | All four activation classes, changed/added/removed files, real process/session/reboot transitions. |
| [18B](Task-18.md#task-18b) | Inventory real supported schema steps once, then use data tables for their invalid/retry cases. | Every actual migration path, interruption and fail-closed data boundary; no invented historical releases. |
| [18C](Task-18.md#task-18c) | One continuous package lifecycle supplies reusable observations for 26C. | Real removal/reinstall/purge and independent refusal/retry attempts; mocked scripts remain supporting evidence. |

## Graphical work

Use `tests/e2e/scenarios.json` as the starting inventory, inspect only assigned
families, and extend gaps instead of creating a second list. The review found
33 families / 156 pending variants, not 156 completed tests or a final coverage
limit. Family `owners` can name several tasks; each variant's `owner` is its
single execution owner. Related tasks link that execution without copying it.

| Task | Reuse and opportunity | Quality boundary to retain |
| --- | --- | --- |
| [21A](Task-21.md#task-21a) | Batch compatible navigation/validation; use Task 14 witnesses for backend denial. | Real discovery/account creation and standard-user UI denial; resolve E2E-005 ownership and About/feedback requirement gaps below. |
| [21B](Task-21.md#task-21b) | Introduce one real kiosk approval helper here for grant setup; share it with 22–24. | Real UI/password flow; selected-child transaction ordering and other-user effects; no injected grant to avoid a later dependency. |
| [22A](Task-22.md#task-22a) | Reuse 16B/17B witnesses and 21B approval; share login/lock observations with 23/26. | Natural expiry, zero-time correct-password denial, retained/new sessions, both replacement choices and other foreground users. |
| [22B](Task-22.md#task-22b) | Reuse established sessions for display boundaries and a separate dependency-loss case. | Actual minute/second transition and recovery; screen evidence cannot be replaced by backend time alone. |
| [23A](Task-23.md#task-23a) | Extend the real approval helper by explicit surface and parent; reuse transaction witnesses. | Each parent, real denial/cancel/retry, both soft-app outcomes and exactly-once grants. |
| [23B](Task-23.md#task-23b) | One shared form case table; compatible invalid/boundary values can share a declared journey. | Both local form modes, overlay exits and per-child preferences; kiosk graphical acceptance remains 24B. |
| [24A](Task-24.md#task-24a) | Extend existing kiosk entry with containment and real agent recovery. | Restricted session before/after requests; separate normal approval and fault/recovery attempts. |
| [24B](Task-24.md#task-24b) | Reuse 23's data table and authentication; add kiosk targets, exits and cross-surface round trip. | Both graphical surfaces execute; child/parent eligibility, independent mute and return-to-GDM semantics remain distinct. |
| [25A](Task-25.md#task-25a) | Reuse 15A assets/launch witnesses and one graphical route implementation per route. | Preserve the interacting matrix: E2E-019 currently has 48 variants. Sharing code does not collapse required executions. |
| [25B](Task-25.md#task-25b) | Extend 15B/21B process and transaction witnesses to multiple real graphical sessions. | Every targeted session, unrelated-user survival and separately observed partial failure. |
| [26A](Task-26.md#task-26a) | Reconcile canonical existing faults before implementing only missing races/transitions. | Actual fault synchronization and reversible/irreversible outcomes; retain strong reasoning for adversarial races. |
| [26B](Task-26.md#task-26b) | Use one persistence assertion set across declared restart boundaries. | Each required app/session/service/reboot/suspend boundary executes; prior state must arise from real UI use. |
| [26C](Task-26.md#task-26c) | Compose proven helpers and witnesses; preflight real-game and authorized-delivery assets before their attempt. | Continuous real gameplay, natural expiry, lifecycle and both game modes; independently passing fragments never establish a journey. |

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

- **21A/21B ownership:** E2E-005's six variants currently belong to 21A, but
  their complete allowance/grant/child-behavior journey crosses 21B's transaction
  boundary. Before accepting 21A, reconcile the pending declarations and task
  split. Prefer assigning the full transaction variants to 21B and retaining
  21A's independently verifiable discovery/validation scope. Preserve all IDs,
  actions and assertions, validate the inventory change, and link the shared
  result; do not create an acceptance cycle or count partial 21A screens as a
  complete E2E-005 pass. This documentation review has not changed the inventory.
- **Requirement gaps:** E2E-002 belongs to 20; E2E-030/031 to 21A; E2E-032/033
  to 26C. Their `requirement_gap` fields need actual normative mapping before
  readiness. Check shared E2E-007/028/029 variant ownership at each consuming
  task as well; a family-level owner list is not a request for duplicate tests.
- **External prerequisites:** reuse 19P's [recorded inventory](Evidence/19P-Backend-Preflight-2026-09-06.md#capture-cleanup-and-downstream-prerequisites).
  Verify Snap tooling in 15A, actual schema versions in 18B, and game assets and
  feedback service/recipient/authorization in 26C before their expensive runs.
  Required unavailable capabilities stay explicit blockers. Inventory review
  does not authorize sending feedback or preparing a replacement baseline.
- **Provenance and timing:** document-only handoffs currently change the source
  identity used by package verification; follow the [reuse decision](Implementation-Workflow.md#decide-what-invalidates-earlier-verification).
  The latest 19A smoke also exposes unbucketed finalization time and repeated
  proof reads. Carry this measured lead into 27C/28A; do not weaken preservation
  checks, cache a baseline proof or redesign the runner simply to shorten a wait.

Maintain decisions in their task/contract when implemented, then remove the
resolved warning here. Keep evidence in its original record. Update this map
only when ownership or reusable interfaces change, not after every experiment.
