# 004 — Check Claude batch results

Acceptance: host

Purpose: establish actual native batch compatibility without enabling Claude.
Requires: task 003 and explicit reactivation from the deferred queue. Funded
model access, authentication and a compatible SDK must already be prepared;
never install or authenticate during preflight.

Read the [master](../Agent_Adapter.md), [native result contract](../Agent-Adapter-Design.md#native-transports-and-common-results),
[foundation limits](../Agent-Adapter-Design.md#claude-transport-foundation),
[approval routes](../Approval-Tools.md) and
[storage mandate](../Mandates/Test-Storage-Mandate.md). Inspect `tools/agent_claude.py`,
`tools/agent_claude_bridge.py`, `tools/agent_adapter.py` and the shared supervisor
in `tools/detached_launcher.py`; discover other sources before reading them.

Use disposable checkouts, shared allocation/retention and the maintained
supervisor for bounded real-agent requests. Record the actual CLI/model pair.
Exercise `plan_response.schema.json`, `write_e2e_response.schema.json`,
`fix_tests_response.schema.json` and `sync_whatsnew_response.schema.json` from
`tools/`, with finite schema-conforming success and deliberate workflow failure.
Use existing workflow validators; a transport fixture is not full workflow
acceptance. Require an attributable coordinator envelope and structured result;
retain failure despite a zero native exit. Do not accept assistant/tool/helper
prose or weaken schemas. Preserve native usage scope and sanitized errors.

Acceptance requires all four native schema paths, fresh-session behavior,
read-only restrictions and failed-result preservation. Refusal, authentication,
rate/capacity and malformed/partial-output paths must fail without fabricated
results; label source/double checks separately from any live observations.
Do not provoke an outage or claim unexercised transient behavior passed.
The session exception covers several finite native schema assignments.

Repair only evidenced transport defects in this scope. Preserve Codex results,
leave the production Claude execution gate in place and add no permanent non-product tests.
Reap owned children and finish shared cleanup before close-out. Run affected
maintained checks and Markdown links; record a short result and unresolved limits
in the queue. Apply the owning build mandate if an edit affects packaging.
