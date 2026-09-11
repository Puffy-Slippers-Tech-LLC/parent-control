### Task 20 — Automate clean installation, reboot, and startup readiness

Follow [E2E-Coverage.md](E2E-Coverage.md). Audit the existing E2E-002 and assigned
E2E-028 variants before implementing gaps; real customer steps
and declared OS fault controls must have distinct categories and evidence.

## Implementation slices

Use the [implementation workflow](Implementation-Workflow.md). These are small
work boundaries within the existing task, not extra acceptance checklists.
Verification below is task acceptance; edits use the smallest affected selection.

| Task | First proof, then expansion |
| --- | --- |
| 20 | One real clean install/reboot/readiness journey; then separately declared startup failures. |

- Depends on: Task 19B.
- Complexity: high. This is the first complete release-path graphical job.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Model rationale: use Sol for implementation over qualified installation and
  reboot contracts. Use Astra high while missing authentication, private capture
  or boot-continuity boundaries require design or first live qualification;
  the active handoff selects the next slice under the shared model policy.
- Objective: prove a clean supported Ubuntu machine reaches a safe login screen
  after installing the exact release artifact.
- Work:
  1. Start from the before-product baseline and upload the exact `.deb`, fixture
     bundle, and their digests through the controlled asset channel. Provision
     accounts and unrelated fixture apps through supported helpers. Installation
     and reboot are asserted product lifecycle transitions in this task and
     remain real customer operations; other tasks may use verified package
     installation as prerequisite setup without replaying this acceptance case.
  2. Verify the product is absent, install the package through its real package
     path from the guest terminal with real administrator authentication,
     record output, and verify the product-created reboot marker. The last
     printed output must be the red kiosk reboot notice below. A hidden
     preinstalled image or helper installation is not this journey's evidence.
  3. Request an actual reboot through the customer-visible guest interface.
     Verify the boot identity changes and that GDM returns; do not reload VM
     state. Forced-power recovery belongs to a separately declared fault case.
  4. Assert visually that GDM becomes usable only after fapolicyd readiness.
     Independently prove the broker publishes its D-Bus object only after its
     startup reconciliation completes, as specified in the
     [startup design](../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle).
  5. Assert through serial that installed files, ownership, services, D-Bus,
     Polkit, PAM, session descriptors, configuration, extension payload, logs,
     and execution policy match the package.
  6. Prove a broker startup reconciliation failure prevents broker readiness and
     a fapolicyd readiness failure prevents managed graphical login startup.
  7. Collect all startup evidence and complete executable coverage for the
     [startup audit's existing requirement mapping](Evidence/20-Startup-Audit-20260908.md).
     E2E-002's declaration gap is resolved; runtime readiness remains unproven.
     Keep broker and fapolicyd startup
     failures independently asserted even where they share scenario helpers.

### Terminal reboot-notice cases

These are customer-visible package-output assertions, not extra scenario
families. Capable terminals show the notice in red; redirected or `TERM=dumb`
output stays plain text.

- **Install (this task / E2E-002):** after a successful documented package
  installation, the last printed output is
  `*** REBOOT REQUIRED: reboot before using the kiosk session. ***` and is
  red.
- **Uninstall ([Task 18C](Task-18.md#task-18c) / E2E-027):** after a successful
  documented package removal, the last printed output is
  `*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***`
  and is red. This task does not run the removal journey.

- Verification:
  - Run runner cleanup-safety regressions in isolation before live scenarios.
  - Run every clean-install/startup-failure variant once as a complete attempt.
    Repetition follows the workflow's stability rule. Restore the retained
    baseline only outside attempts, never across a journey's reboot.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=E2E-002`,
    package-focused system tests, `make check`, and `git diff --check`.
- Completion criteria: a digest-identified release package passes a real clean
  installation and reboot with visible and backend readiness evidence. Register
  and run the separate E2E-028 startup-failure variants as well.

### Task 20 continuation — 2026-09-08

**Current handoff — 2026-09-11: live command proof reached; normal shutdown
qualification remains unfinished. Task 20 is still earliest ready.**

Attempt 9 passed password authorization and observed authenticated shell lineage,
then refused command preparation. A focused regression reproduced the standalone
controller's late `vt6_command` import failure after its temporary path was
restored. `ReadOnlyObservations` now loads `CommandRoundTrip` with its other
dependencies. Attempt 10 then durably completed all five authentication stages,
including the fresh boot/shell/attempt-bound nonsecret command. It failed
`e2e:deadline` after power-off and before backend exit/off-state verification.
All ten attempts remain failed; normal-shutdown qualification, sudo/notice pixels,
full Task 20 and both E2E-028 startup faults remain unaccepted. See
[attempts, correction, timings and cleanup](Evidence/20-VT6-Command-and-Shutdown-20260911.md).

The [VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal)
now records live capture/shell/marker stage evidence and the import regression.
The [worker contract](../../tests/e2e/README.md#shared-guarded-worker) and
[reuse map](Reuse-Map.md#installation-helper-and-open-limits) own the remaining
deadline limitation: attempt 10's mandatory baseline rechecks took 802.363 seconds;
worker duration was 1036.426 against the 960-second loop budget. Finalization
confirmed the original `e2e:deadline`, while stored worker/outer categories remain
generic. No new prompt collector or generic diagnostic gate is needed.

**Next result:** locally reproduce the deadline across a delayed synchronous
shutdown callback, correct the finite budget for the full required flow, then
run affected checks, isolated safety and
`tools/run-tests integration check_graphical_vt6_authentication` through normal
worker exit and final preservation. Read `run_distribution`,
`CallbackServer.serve_once`, `Adapter`, `Lease.stop` and their existing
timeout/shutdown regressions together. Preserve every provenance/ownership check
and refusal of incomplete shutdown; do not repeat the unchanged budget.

Final checks: **1,988 affected**, **7,327 unit/contracts and 58 components** in
`make check`, plus **2 guarded UI cases**. The shared scaling fixture moved
unchanged into UI conftest, resolving the prior architecture failure. Safety and
dispatcher prerequisites each passed **685 tests/3 subtests** before both runs.
Both attempts exited 1 with lease `complete`, baseline restoration, source/host
preservation and cleanup passed; product/collection stayed `not-run`. Workers,
callbacks and displays closed; all commands exited. No export, recovery obligation
or approval/Polkit denial remains. Only documentation changed after final checks.
Local links and scoped whitespace checks passed; Continuation has one supported
settings line. The authoritative checklist remains unchanged.

**All-task VM clearance persists**, and both attempts preserved source. The
operator's cleared writer deferral stays cleared; no bypass or new coordination
confirmation is needed. Preserve [15A's work](Task-15.md#task-15a-continuation--2026-09-08)
for later selection. This slice used **`gpt-6-astra` / `xhigh`, Standard** and
consumed the renewed one-slice override. Its overrun completed two guarded
attempts and their cleanup; no third attempt began.

**Next-session settings:** `gpt-6-astra` / `high`, Standard; model: keep;
effort: lower. **Reason:** authenticated command behavior now has live evidence;
the remaining finite deadline and synchronous shutdown boundary still require
ownership-aware correction and live qualification, without the prior xhigh override.

### Prior handoff — capture correction before the joined intervention

The following retains the earlier state and its then-next action; the current
handoff above supersedes its scheduling and settings recommendations.

**Earliest ready task; not accepted.** [Task 19B remains accepted](Evidence/19B-Acceptance-20260908.md).
No earlier entry is bypassed; preserve [15A's later work](Task-15.md#task-15a-continuation--2026-09-08).

**Current result — 2026-09-10, capture refusal reproduced and corrected locally:**
attempt 7 retained `vt6-auth:capture-changed-refused` after initial metadata and
exact pixel verification. A delayed first read of an installed-tinycv PNG then
reproduced an atime-only refusal locally. Whole-stat equality's integer-second
timestamps hid this defect in fast tests. `Authentication._pixels` now reuses
`provenance.identity` plus UID/GID checks, preserving stable descriptor/path
metadata and nanosecond mtime/ctime while excluding read-driven access time.
Fixed safe refusal checkpoints survive the generic worker wrapper; changed
stable fields have specific descriptor/path codes. The correction passes focused
and common checks but is not live-qualified. See the
[attempt, reproduction, correction and cleanup](Evidence/20-VT6-Capture-Identity-20260910.md),
the [owning VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](Reuse-Map.md#installation-helper-and-open-limits).
No password authorization or authenticated shell is yet proved. The
[next-slice operator intervention](#operator-live-authentication-intervention--2026-09-10)
now governs the root-cause review and corrected guarded qualification.
No external dependency or approval blocker is identified.

**Prior result — preparation and password readiness qualified:**
attempt 5 identified the offline pre-write boundary; the helper incorrectly
reentered locking disk inventory while its own libguestfs appliance held the
disk. Reusing `mounted_guest`'s full checks before opening and after closing
corrected that placement. Attempt 6 passed preparation/readback and observed
the effective 600-second window, matching recipient diagnostics and durable
password readiness. It then failed at `vt6-password-screen` with only
`e2e:worker-execution-failed` retained. The pre-password PNG is byte-identical
to the pinned reference; pixel-content mismatch is excluded, but the precise
capture/remaining predicate is unknown. No password authorization or shell proof
was issued. See [attempts, correction and cleanup](Evidence/20-VT6-Offline-Guard-20260910.md),
the [owning VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](Reuse-Map.md#installation-helper-and-open-limits).
Attempt 7 and the local correction above supersede that next-action diagnosis.

**Prior result — baseline revalidation exceeds login lifetime:**
attempt 3 observed `login` before the password-stage recheck and `agetty` after
it. Guest util-linux 2.41.3 configures a 60-second login timeout; the baseline
check took 69.027 seconds and source capture 0.091 seconds. Password readiness
again refused before password authorization. See
[retained evidence and correction](Evidence/20-VT6-Revalidation-Timing-20260910.md),
the [VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal),
[provenance contract](../../tests/e2e/README.md#controller-owned-provenance), and
[reuse map](Reuse-Map.md#installation-helper-and-open-limits).
The new fixed diagnostic and component timing preserve every existing guard.
The run's advisory identity-match Booleans are invalid: review found a
string/tuple comparison defect. Its correction and real-reader regressions
pass locally; executable/configuration/timing observations are unaffected.
No live continuity or authentication success is claimed.

**Prior result — fresh-input attempt reaches password recipient:**
authentication attempt 2 passed final source/host preservation, durable getty
authorization and the live negative password needle on the login screen. After
fixture-name input, `vt6-password-ready` failed before password authorization.
The fixed guest traceback identifies the first selected-unit executable check:
the recipient was not `/usr/bin/login`. The 68.995-second request-to-failure
interval supports investigating prompt expiry during revalidation, but the
actual executable, effective timeout and component timing remain unknown.
See [retained result, diagnosis and cleanup](Evidence/20-VT6-Password-Recipient-20260910.md),
the [VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal),
[provenance contract](../../tests/e2e/README.md#controller-owned-provenance) and
[reuse map](Reuse-Map.md#installation-helper-and-open-limits).
No runtime code changed; existing edits were preserved. Live authentication
remains unqualified. Do not repeat this attempt unchanged.

**Prior result — authentication integrated; first live attempt refused:**
implemented the fixed command round trip, private shell pin, fresh capture and
current-worker/source authorization, durable receipts and guarded dispatch.
The first `check_graphical_vt6_authentication` attempt reached GDM dismissal,
then refused at `vt6-login-ready` before the getty read or any VT6 input receipt.
Finalization retained **`provenance:source-changed`**. Worker/callback closure,
baseline restoration and host preservation passed; source preservation failed.
The nine changed runtime-file byte digests still match the captured map; the
differing checkout input or metadata is not identified. See
[integration, failures and cleanup evidence](Evidence/20-VT6-Authentication-Attempt-20260910.md),
the [VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal),
[provenance contract](../../tests/e2e/README.md#controller-owned-provenance) and
[reuse map](Reuse-Map.md#installation-helper-and-open-limits).
Live authentication remains unqualified. No new implementation prerequisite is
identified; the next attempt needs fresh current inputs and the existing guards.

**Prior result — shell lineage verified locally:** added the fixed
`VT6_SHELL_IDENTITY` probe and fourth ordered observer read. They reuse the sudo
observer's detached-login/direct-child semantics and compare the original login
recipient digest after authentication. Foreground ownership, fixture credentials,
standard terminal descriptors and repeated process/boot checks pass locally;
replacements and malformed output latch refusal. See
[shell-lineage evidence](Evidence/20-VT6-Shell-Lineage-20260910.md), the
[owning contract](../../tests/e2e/README.md#visible-vt6-installation-terminal) and
[reuse map](Reuse-Map.md#installation-helper-and-open-limits).
This slice narrowed the combined readiness/lineage scope: foreground Bash can
still run startup code or a builtin consuming input. No command-readiness proof
or password authorization is issued; dispatch remains disabled. The probe is
an immediate observation, not a startup wait. No live attempt was made.

**Prior result — recipient continuity verified locally:** added
fixed VT6 identity programs and an ordered, single-use observer sequence that
pins boot/unit/PID/start-time digests across getty, password and post-capture
password recheck. It reuses the existing recipient predicates and keeps the
recipient digest private. Replaced process/boot, replay, reordering, ownership
loss and malformed output latch refusal. See
[recipient-gate evidence](Evidence/20-VT6-Recipient-Gate-20260910.md) and the
[owning contract](../../tests/e2e/README.md#visible-vt6-installation-terminal).
This slice completed that missing cross-observation boundary; it did not enable
dispatch or issue password authorization. Shell readiness/lineage, capture
provenance and durable authorization remain required before live qualification.
No VM attempt was made; the all-task clearance remains active.

**Prior result — one-shot worker gate verified locally:** added
`onpc_vt6::authenticate(exchange)` with exact stage/boot/boolean receipts,
mandatory needle and exact-pixel authorization, sealing before receipt/secret
access, one password submission and mandatory session/shell completion receipts.
API, proof or partial-input failure seals capture and refuses retries; the
credential-free inspector shares that latch. Late console/policy changes refuse
typing or submission. See [worker-gate evidence](Evidence/20-VT6-Worker-Gate-20260910.md)
and the [owning protocol](../../tests/e2e/README.md#visible-vt6-installation-terminal).
The route remains unselected by `smoke.pm`; no controller authorization or live
input is claimed. The slice ended at the worker boundary because existing
getty/password probes establish identity only within individual observations,
and the [session observer](Evidence/20-VT6-Session-Gate-20260910.md) supplies
neither shell readiness nor continuity from the original login recipient.
Those proofs must be implemented before enabling dispatch. The
[pixel comparator and matcher counterexample](Evidence/20-VT6-Pixel-Gate-20260910.md)
remain applicable. Stage/boot receipts alone cannot distinguish same-stage/
same-boot replay; current capture/input provenance remains mandatory.
No new VM attempt was made.

**Prior result — corrected prompt qualification passed:** the
[sole corrected worker attempt](Evidence/20-VT6-Prompt-Qualification-20260910.md)
passed both VT6 captures, getty/login recipient checks, disabled password echo,
active-VT and unchanged-boot observations. The native 1024×768 login and
selected-fixture/empty-challenge screenshots were directly reviewed. The
[owning VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal)
carries their needle requirements and qualification limits; the
[reuse map](Reuse-Map.md#installation-helper-and-open-limits) links them.
The [original predicate failure](Evidence/20-VT6-Prompt-Readiness-20260909.md)
remains retained. No credentials were provisioned, read or submitted; no needle
asset or password-enabled flow was added. Runtime inputs were unchanged from
the preceding 1,415-test correction result. Reuse `onpc_vt6::inspect_prompt`
and `Smoke.VT6_PROMPT_STAGES`; do not repeat prompt-only discovery or maintenance.

**Prior surface/probe result:** the
[VT6 inspection and probe evidence](Evidence/20-Visible-VT6-20260909.md) establishes
a real VNC-visible kernel terminal on the accepted baseline. A guarded
credential-free Ctrl+Alt+F6 inspection retained and directly reviewed its
1280×800 login screen, then restored the baseline. Fixed VT6 login, installation
sudo and reboot sudo read-only probes now reuse the existing recipient checks,
with repeated active-VT checks and distinct surface/purpose result tokens.
The shared refusal diagnostic follows the selected getty unit. Sudo probes
remain locally tested only; getty/login prompt collection now has the live
qualification above. No VNC password input, executable prompt/notice needle or
complete journey is yet qualified. The [owning VT6 contract](../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](Reuse-Map.md#installation-helper-and-open-limits) carry the durable
solution, regressions and open limits. The earlier
[serial-screen finding](Evidence/20-Graphical-Notice-Boundary-20260909.md) remains
valid: serial replay, controller rendering and post-hoc notice invocation do
not establish customer-visible package output.

The earlier [installed-layout evidence](Evidence/20-Installed-Layout-Observation-20260909.md)
still records a fixed read-only post-reboot observer that reuses the transferred
package inventory and installed package/ownership/PAM/Polkit/session assertions.
Its exact guest program, transport grammar, boundary and callback pass locally;
live qualification remains pending.

**Retained live scope:** the [unblock intervention](Evidence/20-Reboot-Unblock-20260909.md)
proved authenticated reboot, changed boot and held-stream serial return. The
corrected GDM needle matches retained pixels locally; full acknowledgement,
normal shutdown and final preservation of the complete installation journey
remain unqualified. Installation history is unchanged: 21 attempts, three
historical passes and eighteen failures. Preserve those failures; do not reopen
solved serial authentication/probe semantics.

**Next bounded result:** resolve the root live authentication blocker and qualify
one authenticated command-ready shell under the
[next-slice operator intervention](#operator-live-authentication-intervention--2026-09-10)
and existing [milestone checklist](#operator-course-correction--2026-09-10).
Reuse `provision_vt6_login_window`, `mounted_guest`, `Authentication._pixels`,
`provenance.identity`, `VerifiedInputs` and the existing probes. The
[delayed-read reproduction and correction](Evidence/20-VT6-Capture-Identity-20260910.md)
settle the local capture contract; no further prompt collection or unchanged
diagnostic-only run is needed. After isolated cleanup safety, run
`tools/run-tests integration check_graphical_vt6_authentication` with unchanged
inputs through cleanup. The final common checks already cover the correction;
repeat them only if new changes or failures invalidate them. Preserve full
checks, one-use proofs, no-retry input, baseline restoration and host configuration.
If a new refusal occurs, use the retained fixed stage/field code before changing
anything. Pursue its demonstrated correction and fresh guarded qualification
within the slice when the shared attempt/context rules permit; a failed attempt
or a locally passing fix is not authentication acceptance.

**Required milestone review:** live authentication remains the missing proof.
Preparation and password readiness pass live; attempt 7 additionally establishes
that its original post-read stat comparison refused after exact pixels passed.
The local atime defect is corrected and tested. Individual fields were not
retained live, so its historical atime attribution remains supported by the local
reproduction rather than a recovered live measurement. The next result is the
corrected wired live chain. This slice ran one live attempt and exceeded its
review budget to finish restoration, collection and the resulting local
correction/checks; no second live attempt started.
Sudo/notice pixels and complete install/reboot/startup remain after authentication.

**Current verification/cleanup:** actual settings `gpt-6-astra` / `high`, Standard.
Final `make check`: **7,306 unit/contracts and 58 private-D-Bus tests passed**,
plus common checks; **222 focused tests passed**. Isolated safety and dispatch
repeat each passed **667 tests and 3 subtests** before attempt 7; rerun isolated
safety before the next VM attempt because the final local changes came afterward.
Attempt 7 exited 1; inputs, failed intermediate local checks and recovery are in
the [evidence](Evidence/20-VT6-Capture-Identity-20260910.md).
Product/collection remain `not-run`. Source/host preservation, baseline
restoration, lease completion and worker/callback/display closure passed.
No password-input authorization was produced. All commands exited; test-owned
temporary PNG directories were cleaned; no live screenshot export or recovery
obligation remains. No approval/Polkit denial. Only documentation changed after
the final common check.
**All-task VM clearance persists.** Task 20 remains earliest ready, no bypass;
15A stays preserved. Authentication history: seven failures;
prompt and installation histories remain unchanged. Task acceptance and both
E2E-028 startup faults remain unfinished.

**Prior verification/cleanup — attempt 1:**
Focused integration tests: **1,968 passed**, then **128 final worker/controller
tests passed**. Final `make check`: **7,167 unit/contract and 58 private-D-Bus
tests passed**, plus common source/traceability checks. Isolated cleanup and the
dispatcher's repeat each passed **595 tests and 3 subtests**. The evidence
retains the wrong exception expectation, timestamp-race correction, private
directory fixture failures and failed intermediate common check, followed by
passing correction. Live auth attempt 1 failed with source drift; no package
acceptance run. Prompt history stays 2 (1 failure, 1 pass); installation history
stays 21 (3 historical passes, 18 failures).

All commands exited and results were collected. Current live evidence confirms
lease phase `complete`, baseline restoration, host preservation and worker/
callback closure; source preservation remains failed. No screenshot exports or
owned recovery obligations remain. Prior and concurrent workspace edits were
preserved. Documentation edits began after live finalization exited.
No approval or Polkit denial. **All-task VM clearance persists**.
Selection rechecked:
Task 20 remains earliest ready, no bypass; 15A and unrelated frontend edits
remain preserved. Task 20 acceptance and both E2E-028 startup faults remain
unfinished. Historical maintenance/probe failures remain in their linked
evidence; current success is not asserted for those old failed attempts.

**Next-session settings:** `gpt-6-astra` / `xhigh`; model: raise from the previous
Sol recommendation; effort: raise. **Reason:** the operator requests a focused
root-cause intervention after seven failed live authentication attempts. The
remaining wired timing, provenance and authorization path needs review together
and live verification; the locally settled capture correction does not establish
that the rest of the chain works. Standard processing. This override applies to
the next fresh slice only; at its handoff record it as consumed and reassess both
settings under the [normal policy](Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff).

### Operator live-authentication intervention — 2026-09-10

The user requests **`gpt-6-astra` / `xhigh`, Standard, for the next fresh slice
only**, and best effort to solve the root live authentication blocker. This
supersedes the latest Sol/high recommendation, including the recommendation in
the capture-identity evidence. The user will start the slice manually. It creates
no general Astra/high or Astra/xhigh pin; subsequent settings require a fresh
assessment under the normal policy.

**Required result:** pursue one guarded live login with exactly one authorized
credential submission, verified authenticated-shell lineage, and a completed
fixed nonsecret command round trip bound to the current attempt, boot and shell.
Retain normal collection/cleanup, baseline restoration and source/host
preservation evidence. Passing local checks or moving to another refusal is
partial progress, not this milestone or full Task 20 acceptance.

Before the live run, review the remaining wired path as one flow: capture
production/read/sealing and stable identity; freshness and authorization receipt
consumers; recipient-to-shell transitions; and cumulative revalidation/worker
timing through command completion. Reuse the owning contract and retained
evidence; reopen a proven boundary only for a demonstrated mismatch. Distinguish
the locally reproduced atime cause from unmeasured live fields. Fix evidenced
defects in maintained code and exercise realistic timing/order and refusal
behavior locally. Consolidate only missing privacy-safe observations needed to
distinguish plausible failures in that same run.

Run affected checks and isolated cleanup safety, then the existing guarded
authentication route with fresh required inputs, frozen through cleanup. If it
fails, finish cleanup, use its discriminating evidence to correct the cause and
make a fresh qualifying attempt within the slice when the
[shared attempt rules](Implementation-Workflow.md#make-every-expensive-attempt-answer-a-question)
and context permit. Do not repeat unchanged attempts, weaken authorization or
privacy, or add a generic gate merely to move the refusal. Time estimates are
review points: make best effort to complete the fix and live verification rather
than automatically handing off after another helper or local correction.

If live qualification remains unsuccessful, report the furthest proved boundary,
demonstrated cause versus unresolved hypothesis, rejected explanations, and the
specific evidence or design change needed next. Reassess the whole remaining
flow before proposing another slice. Preserve failed attempts and all cleanup
obligations; mark this one-slice settings override consumed and write a fresh
settings recommendation based on what remains. Existing VM authorization and
the milestone checklist below persist.

### Operator course correction — 2026-09-10

The user requested this correction after reviewing Sessions 55–57. Those slices
added distinct tested gates but no live authentication result. Session 58 then
qualified shell lineage locally; command readiness remains unproven. The launcher
was stopped normally after Session 58, with no owned cleanup outstanding. The
user will start it again; this correction governs that next launch and subsequent
handoffs until the milestone below is qualified or explicitly superseded.

**Next observable milestone:** one guarded live VT6 login that submits the
credential once through the authorized worker and reaches a verified
command-ready shell, with capture privacy, recipient continuity and normal
collection/cleanup evidenced. This is intermediate qualification, not Task 20
acceptance. Keep sudo/notice pixels and complete install/reboot/startup work
after this milestone.

Use this finite remaining checklist; update it in place with evidence:

- [x] Complete the fixed nonsecret command round trip, fresh attempt/boot/shell
  completion proof, and timeout/partial-input refusals using the existing lineage
  and session observers. Locally verified in the
  [integrated attempt evidence](Evidence/20-VT6-Authentication-Attempt-20260910.md);
  attempt 10 now supplies [live command-stage evidence](Evidence/20-VT6-Command-and-Shutdown-20260911.md),
  with normal worker shutdown still unqualified.
- [x] Bind fresh capture and exact pixels to current-worker/input provenance and
  durable, ordered, one-use controller authorization; preserve sealing and all
  recipient/replay refusals. Locally verified in the same evidence; attempts
  9/10 above now pass the live capture/authorization stage.
- [ ] Connect dispatch after those proofs pass, run affected checks and isolated
  cleanup-safety prerequisites, then perform one guarded live authentication
  attempt with unchanged inputs through final collection and cleanup. Dispatch
  and checks are implemented; attempt 1 failed before authorization with
  `provenance:source-changed`. Attempt 2 passed preservation and getty authorization,
  then refused the password recipient before password input; see
  [timing and predicate evidence](Evidence/20-VT6-Password-Recipient-20260910.md).
  Both cleanups passed. Attempt 3 then isolated baseline revalidation exceeding
  the configured login lifetime; see [timing evidence and advisory correction](Evidence/20-VT6-Revalidation-Timing-20260910.md).
  Its cleanup passed too. Attempt 4 implemented finite fixture/worker budgets but
  refused offline preparation before worker startup; see
  [preparation failure and diagnostic correction](Evidence/20-VT6-Login-Window-20260910.md).
  Attempt 5 narrowed the offline failure; correcting guard placement let attempt
  6 pass preparation and password readiness, then refuse password-screen capture
  before password authorization. Its PNG matches the reference byte for byte;
  see [correction and retained capture](Evidence/20-VT6-Offline-Guard-20260910.md).
  Both cleanups passed. Attempt 7 retained the post-read metadata refusal; its
  delayed-read atime defect is now corrected locally, with
  [reproduction and verification](Evidence/20-VT6-Capture-Identity-20260910.md).
  Its cleanup passed too. Attempt 8 refused source drift before worker startup;
  the operator cleared that deferral. Attempts 9/10 now advance through password
  submission, the corrected standalone command import and all authentication
  stages, but attempt 10 fails the worker deadline after power-off. See the
  [current evidence](Evidence/20-VT6-Command-and-Shutdown-20260911.md).
  All ten attempts remain failed. Correct the normal-shutdown budget and complete
  guarded qualification before checking this item.

Plan the remaining dependency chain together at the start of the next slice.
Reuse the qualified prompt, pixel, worker, recipient and lineage contracts;
do not rediscover them or create additional generic frameworks. Target the live
milestone in that slice rather than ending automatically after another helper.
Necessary correctness and context boundaries still apply; never enable input
with missing proofs merely to reach the VM.

**Review trigger:** if that slice ends without live qualification, or a new
prerequisite is proposed, explicitly reassess the dependency chain before another
local-only slice. Record the exact missing proof and supporting evidence, why the
existing contract cannot supply it, the smallest supported completion approach
and the remaining path to the live attempt. A failed live attempt must identify
the boundary reached and a changed next experiment; do not repeat it unchanged.
Carry this review and checklist forward instead of merely naming another gate.
Test-count growth alone does not satisfy the milestone. Do not invent an
outside-input blocker or a fresh permission requirement: existing VM clearance,
ownership rules, privacy gates and full Task 20 acceptance requirements persist.

### Reboot unblock intervention — 2026-09-09

The [intervention evidence](Evidence/20-Reboot-Unblock-20260909.md) records the
review of Sessions 42–45, the two corrected runs, executable regressions and
the preserved failures. The three corrections are explicit fresh reboot
authentication, retaining SSH status across ownership checks, and an exact
installed-layout GDM fixture. The latest attempt established an actual reboot
and serial return; the subsequent matcher correction passed against its retained
image. The active handoff above owns the remaining readiness work and qualification
limits. No worker was killed; the launcher remains stopped at a safe boundary.

### Operator follow-up after Session 34

Completed by the [explicit-newline slice](Evidence/20-Install-Explicit-Newline-20260908.md):
one guarded attempt passed and cleanup finished. The active continuation above
owns subsequent work/settings; the instructions below retain this slice's scope.

The user reviewed Session 34 and authorized one further focused slice. Its
guest implementation audit and corrected recipient/echo proof are real progress;
prompt recognition and authenticated installation remain unqualified. Keep
`gpt-6-astra` / `high`, Standard processing, for the remaining authentication
and transport work. Launch with `--max-slices 1` and perform **at most one new
guarded VM attempt**. Finish owned collection and cleanup before stopping for
result review, including after failure; the existing VM authorization persists.

Implement the explicit newline in the supported custom prompt and update the
independent exact argv check. Preserve the qualified recipient/continuity and
character-echo proof, strict prompt recognition, private capture and refusal
gates. A diagnostic marker match must never authorize password input.

Before fresh artifacts and the sole VM attempt:

1. Exercise fragmented input through the maintained serial buffer/parser path
   locally, including command echo, delimiter and suffix split across reads,
   complete valid prompts, and incomplete or private/unknown suffix refusals.
   Tests of complete preselected strings alone do not establish serial delivery
   behavior. Reuse the existing test routes and keep this qualification focused.
2. Prepare consolidated fixed diagnostics that distinguish a marker absent from
   the observed buffer, partial marker/suffix delivery, and a complete marker
   with unsupported framing or suffix. Distinguish command echo from prompt
   output. Keep unavailable or incomplete observations explicit; absence in an
   observed buffer does not establish that sudo never emitted the prompt.
   Export only fixed categories or flags, never raw authentication bytes,
   arbitrary PAM text or secrets. Collect enough evidence during this attempt
   to identify the remaining interface gap if the new prompt still fails.
3. Validate these observations and input refusal behavior locally, build fresh
   source-bound inputs, and run the isolated cleanup-safety prerequisites.

Report the actual boundary reached: recognized prompt, password submission,
authentication outcome and any subsequent installation result separately. If
input still refuses, identify the supported cause or precise remaining evidence
gap and a different next approach. More passing tests or another undifferentiated
prompt timeout alone do not establish a breakthrough. Do not start a second VM
attempt within the slice, and do not expand a generic diagnostic framework.

### Operator diagnostic intervention — 2026-09-08

Completed in Session 34. The [operator follow-up](#operator-follow-up-after-session-34)
governs the next slice; the instructions below retain the completed intervention.

The operator authorized this intervention after reviewing slow Task 20 progress.
The preceding slice stopped normally after its ninth attempt, with collection,
baseline restoration, lease release and worker/callback closure confirmed.
The next launcher invocation is limited to **one slice** with `--max-slices 1`;
within that slice, run **at most one new guarded VM authentication attempt**.
Finish its collection and cleanup even if it exceeds the usual review time.
The ordinary backlog and VM authorization persist; the limit provides a result
review boundary before another run, not a new permission requirement.

Before another expensive attempt, reconcile these assumptions together:

1. Establish the guest's selected sudo executable and package/version using
   supported read-only evidence, then audit the corresponding implementation and
   distribution changes. Host identity and an unrelated upstream implementation
   are insufficient. Keep unknown identity explicit.
2. Explain how the configured custom prompt reaches the serial reader and its
   matcher, including supported wrappers, terminal controls and command echo.
   Prove that recognition rejects command echoes, unrelated/private PAM text and
   malformed or incomplete prompts; avoid a permissive substring fallback.
3. Review password-character protection separately from newline echo. The ninth
   attempt proved ECHO off and ECHONL on; polling does not establish a pre-prompt
   wait. Any corrected terminal predicate needs an explicit safety rationale and
   behavioral success/refusal tests. Preserve exact recipient identity, process
   continuity, authorized prompt, private capture and terminal refusal/retry
   invariants; do not merely remove a failing check to obtain a pass.

Use the smallest supported correction or a consolidated set of fixed, privacy-safe
observations that distinguishes the remaining explanations in the same boot.
If polling remains causally relevant, distinguish terminal input from a service
dependency rather than adding guessed wait symbols. Validate collectors and
parsers locally, including unknown/read-error and identity-loss cases, before
building fresh artifacts and running the isolated cleanup prerequisites.
Do not expand a generic diagnostic framework or repeat full VM preparation for
each additional diagnostic token.

End with a demonstrated cause and qualified correction, including the real
boundary reached, or a precise unresolved evidence/interface gap and a concrete
different next approach. Record rejected explanations, remaining hypotheses,
attempt identity, observed outcomes and cleanup. A larger unit-test count or one
more refusal label alone does not satisfy this intervention's result criterion.
If the live attempt still fails, finish and hand off for review before any further
VM run. Report actual status honestly under the existing schema; the one-slice
limit stops the launcher without inventing an outside-input blocker.
