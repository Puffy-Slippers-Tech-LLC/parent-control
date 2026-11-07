# 007 — Complete Claude workflow integration

Acceptance: host

Purpose: complete the qualified Claude side of shared selection and callers
without prematurely activating production switching. Requires tasks 006 and
014 and explicit reactivation. Task 014 owns the provider-neutral plumbing;
reuse its accepted results rather than repeat that implementation.

Read the [master](../Agent_Adapter.md),
[configuration requirements](../Agent-Adapter-Design.md#configuration-and-scope),
[selection lifetime](../Agent-Adapter-Design.md#reading-and-changing-the-selection),
[integration map](../Agent-Adapter-Design.md#current-integration-map) and
[adapter boundary](../Agent-Adapter-Design.md#adapter-boundary). Inspect complete
affected functions and shared state in the mapped sources before edits; apply
the [approval](../Approval-Tools.md) and
[storage](../Mandates/Test-Storage-Mandate.md) contracts.

Reuse the shared configuration parser, immutable snapshot and fixed adapter
mapping delivered by tasks 013–014. Complete native Claude capability/profile
mapping for every caller without repeating accepted shared checks. Preserve
duplicate-key validation and legacy agent-free documents. For future live
selection, reject missing/invalid/unreadable values before task work. Resolve the
executing checkout after branch/host dispatch, then pin the immutable selection
through turns, helpers, retries and dependent Git transactions. Persist actual
agent/model/effort provenance while reading legacy records as unknown.

Prepare all repair, plan, E2E, translation and Git agent sessions through that
boundary, including helper profiles and readiness. Preserve workflow budgets,
effort ladders, result validators, retry timing and Git ownership. Stop/cleanup,
help, listing and agent-free operations must remain available without agent
readiness. No environment override, provider parameter, executable/import from
configuration, cross-agent fallback or second workflow engine is allowed.

Keep production Claude execution disabled until task 012: qualify the prepared
Claude candidate path in disposable checkouts, without adding a public feature toggle
or hidden environment selection. Acceptance requires finite configuration,
session pinning, retry and caller-routing checks using existing critical shared
regressions and bounded native sessions. Source-only coverage cannot qualify
full workflows. The session exception keeps the shared state/caller boundary
coherent; split independent newly discovered work before execution.

Complete owned cleanup, run affected maintained checks and link checks, and
record readiness limits. Add no permanent non-product tests; run the required
package build if an edit can affect building/packaging.
