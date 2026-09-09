# Task 15 — Installed catalog, enforcement, and process termination

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
