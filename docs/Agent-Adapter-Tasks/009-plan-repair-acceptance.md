# 009 — Check plan and repair workflows with both agents

Acceptance: host

Purpose: qualify finite ordinary-plan and repair workflows through the candidate
shared boundary. Requires task 008 and explicit reactivation; no production
activation is allowed yet.

Read the [master](../Agent_Adapter.md),
[delivery gates](../Agent-Adapter-Design.md#delivery-and-validation),
[failure policy](../Agent-Adapter-Design.md#remote-execution-watch-and-failure-handling),
[ordinary-plan contract](../Execution-Plans.md) and the applicable repair rules
in [tests/README.md](../../tests/README.md). Apply
[approval routes](../Approval-Tools.md) and
[shared storage](../Mandates/Test-Storage-Mandate.md); discover existing relevant
regressions and fixtures rather than creating a parallel workflow engine.

Exercise finite passing/failing plan and repair assignments for each adapter in
disposable checkouts through actual supervisors and existing acceptance engines.
Use harmless fixtures rather than product installation or intentionally broken
customer behavior. Check implementation/repair allowance preservation,
continuation/restart, explicit overrides, native helper profiles and coordinator
result ownership. Keep refusal/authentication/permission failure separate from
invalid successful responses and transient capacity; account for native retries
without consuming another logical session or changing agents.

Acceptance requires both workflow validators to preserve their existing verdict,
budget and cleanup contracts, with native transport results attributable to the
requested coordinator and selected adapter. Repair evidenced shared defects and
rerun only affected checks. Existing native Codex isolation/retirement limitations
cannot receive passing credit from report-only fixtures. Clearly distinguish
live qualifications from source/double checks. The session exception covers two
finite workflow histories; split independent repairs before execution.

Use existing coverage; add no permanent non-product tests. Complete all owned
children/allocations and required checks before a short queue result. Check links
and perform the owning package build only if affected edits trigger it.
