# 012 — Enable configuration-driven agent selection

Acceptance: host

Purpose: activate the single checked-in selection only after all workflow gates.
Requires task 011 and its dependency chain, plus explicit reactivation.

Read the [master](../Agent_Adapter.md),
[selection contract](../Agent-Adapter-Design.md#reading-and-changing-the-selection),
[delivery/completion gates](../Agent-Adapter-Design.md#delivery-and-validation),
[approval routes](../Approval-Tools.md) and the package source/dependency maps
in `Makefile`. Read current queue results and current implementation; do not
reopen expired reports or rerun completed work to refresh evidence.

Confirm every affected workflow and required native policy has its scoped
qualification, and all unresolved limits relevant to activation are addressed.
An excluded Codex limitation remains unqualified; if it violates a preserved
activation requirement, report that dependency rather than enabling selection
or silently weakening policy. Route any additional necessary implementation
through the existing prerequisite/scope-change contract.

Activate the fixed resolver mapping so only the executing checkout's top-level
`agent` field selects `codex` or `claude` for all agent sessions. Preserve pinned
active sessions, no provider options/environment override, no hidden fallback,
and existing public launchers. Keep the checked-in default `codex` unless the
user separately requests changing it.

Acceptance requires finite post-activation checks for both values and invalid
or missing live selection, plus agent-free help/listing/diagnostics/deterministic
Git and cleanup without either CLI. Verify development adapter/SDK assets stay
outside product payload/runtime dependencies and product-only archives. Run the
lowest effective affected existing checks; perform `tools/build_package.py`
after any final build-affecting edit. No new non-product tests are authorized.

Finish owned cleanup and changed Markdown links. Update the queue result and
master status/pointer to reflect actual activation; remove the completed brief
only after its enduring requirements remain with their owners. Do not claim
complete cross-agent support while any consuming workflow still uses another
provider or lacks its required gate.
