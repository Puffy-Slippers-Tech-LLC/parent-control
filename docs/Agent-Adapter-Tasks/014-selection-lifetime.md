# 014 — Preserve agent selection across sessions and recovery

Acceptance: host

Purpose: carry one immutable selection through shared execution and recovery.
Requires task 013. Native Claude execution and policy migration stay out of scope.

Read the [master](../Agent_Adapter.md),
[selection lifetime](../Agent-Adapter-Design.md#reading-and-changing-the-selection),
[caller map](../Agent-Adapter-Design.md#current-integration-map),
[execution contracts](../Execution-Plans.md), [approval routes](../Approval-Tools.md)
and [storage mandate](../Mandates/Test-Storage-Mandate.md). Inspect complete
affected caller, profile/preflight, supervisor, capacity, checkpoint and Git
functions from that map; discover any other paths before reads/edits.

Resolve the executing checkout after dispatch for each independent logical
session. Pass its immutable selection through preparation, profile resolution,
interactive turns, helpers and bounded capacity retries. Dependent Git close-out
and conflict/stash recovery inherit the originating selection until their owned
operation ends. Reattachment uses the live pinned identity; new recovery after
old children/cleanup finish resolves current config without losing its journal.

Update all shared plan, repair, E2E, translation and Git caller paths; preserve
workflow model/effort policy, results, budgets, retry timing and cleanup ownership.
Persist actual agent/model/effort provenance in existing session/usage records;
read legacy unknown provenance without fabricating a provider. Do not substitute
requested config for actual runtime identity. Stop/cleanup, help, listing and
deterministic Git remain agent-free even with invalid new config or missing CLI.

Qualify the coherent shared path on Codex with existing focused core regressions
and finite disposable sessions only where new state/lifecycle changes require
them. Exercise config edits across active/new sessions, retry/helper/Git snapshot
inheritance, legacy restart and early refusal of unqualified Claude. No paid
Claude request, SDK installation, native-role policy change or second selector
is needed. Missing/invalid live selection must fail before agent task launch;
`claude` must receive an explicit unqualified-capability error, never Codex work.

The session exception covers the shared caller/state migration. Split independent
discovered work before execution. Add no new non-product tests; use maintained
affected coverage. Finish owned cleanup, check links and run the package build
only if edits affect its scope. Preserve accepted extraction checks and explicitly
deferred native isolation/retirement limits without rerunning them for renewal.
