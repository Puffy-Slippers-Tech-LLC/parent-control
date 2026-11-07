# 005 — Check Claude conversations and cancellation

Acceptance: host

Purpose: qualify native interactive lifecycle behavior. Requires task 004 and
explicit reactivation; retain its prepared CLI/authentication environment and
check the actual compatible SDK with its CLI path pinned.

Read the [master](../Agent_Adapter.md),
[native transport contract](../Agent-Adapter-Design.md#native-transports-and-common-results),
[approval routes](../Approval-Tools.md) and
[storage mandate](../Mandates/Test-Storage-Mandate.md). Inspect the complete
affected paths in `tools/agent_claude.py`, `tools/agent_claude_bridge.py`,
`tools/launcher_chat.py` and `tools/detached_launcher.py` before changing them.

Use shared storage, disposable checkouts and actual `PreparedSession`, supervisor
and `AppSession` boundaries for finite passing and failing results. Exercise
fresh sessions, pending input at terminal completion, multiple queued messages
in order, active-turn follow-up and a late-input race. Queued input must wait
for a terminal result rather than be acknowledged as active-turn steering.
Interrupt an active turn and at its terminal boundary: discard its candidate,
drain result and acknowledgement, finish cleanup, then submit continuation.
Also exercise EOF, bounded shutdown and cancellation with owned descendants.

Acceptance requires correct turn attribution, no stale/partial result acceptance,
preserved input order, per-turn usage separate from cumulative snapshots, and
observed process-tree reaping without unknown-resource signals. Repair evidenced
bridge/protocol defects only; unknown or failed lifecycle behavior remains
unqualified. The session exception preserves complete native turn histories.

Leave production selection disabled. Add no permanent non-product tests. Run
affected maintained checks after repairs; finish all owned cleanup, check changed
Markdown links and leave only short queue results and normal diagnostics.
