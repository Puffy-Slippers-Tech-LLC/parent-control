# Task 15 — Installed catalog, enforcement, and process termination

Execute 15A and 15B separately. Product installation and policy changes happen
only in the [guarded existing VM](../../tests/integration/README.md). The retained product-free baseline is
restored only outside complete attempts; no VM copy, overlay, or intermediate
checkpoint is used. These are real installed-system tests. Their direct OS
calls and deterministic process fixtures cannot replace the graphical customer
journeys required by [E2E-Coverage.md](E2E-Coverage.md).

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
