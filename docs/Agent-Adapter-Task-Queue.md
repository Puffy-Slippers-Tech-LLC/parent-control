# Agent adapter task queue

The [master plan](Agent_Adapter.md) owns the sole next-task pointer. This queue
owns order, dependencies and completion. Historical rows record only their
accepted bounded scope; see the [reference](Agent-Adapter-Design.md) for limits.
Do not rerun completed tasks solely to refresh evidence.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | Accept the agent setting without changing execution | Baseline | Compatibility field accepted as unused metadata; no selection enabled | Complete |
| [x] | 002 | Run existing Codex workflows through the shared adapter | 001 | Bounded extraction, caller/profile integration and accepted finite Codex checks; deferred native isolation and retirement remain unqualified | Complete |
| [x] | 003 | Prepare the inactive Claude transport foundation | 002 | Read-only nondelegating batch/interactive bridge and bounded source checks; no live qualification or production selection | Complete |
| [x] | 013 | Validate the configured agent | 003 | Strict shared parsing and immutable selection preparation, without enabling Claude execution | Complete; 7 focused checks, agent-free inspection and Markdown links passed |
| [x] | 014 | Preserve agent selection across sessions and recovery | 013 | Shared caller/helper/retry/Git selection lifetime and provenance, qualified on Codex; reject unqualified Claude | Complete; available host checks passed; restricted disposable checks skipped by request |
| [x] | 015 | Prepare agent readiness through setup and SSH | 014 | Shared readiness and executing-checkout dispatch, preserving supported Codex startup without paid Claude access | Complete; focused host, shell, source and links passed; no live SSH/full setup; optional internal rules check denied by policy |
| [ ] | 016 | [Show agent provenance and track adapter assets](Agent-Adapter-Tasks/016-watch-assets.md) | 015 | Watch/session presentation, startup reuse, reload/dependency and development asset inventories | 30–45 min; presentation/reload boundary exception |

Tasks 013–016 need no live Claude requests, Claude SDK installation or Claude
policy migration. Each owns affected Codex and agent-free checks. They must
preserve actual-agent provenance and refuse unqualified Claude execution rather
than silently substitute Codex. IDs are stable labels; their numeric values do
not determine scheduling order.

## Deferred future work

### Out of scope

The following unchecked rows are future implementation, excluded from automatic
selection. They are not active blockers or completed tasks. Bring them into
scope only by explicit request, in dependency order, after preparing funded
Claude access, authentication and a compatible SDK separately. Existing native
Codex permission and retirement limitations stay deferred; qualification gates
must report any unresolved requirement without inventing a pass or workaround.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 004 | Check Claude batch results | 003 | Real read-only batch sessions with all four workflow schemas and attributable successful/failed results | 30–60 min; native-session exception |
| [ ] | 005 | Check Claude conversations and cancellation | 004 | Native interactive turns, queued input, interruption, result races, usage scope and owned process cleanup | 60–90 min; indivisible native lifecycle qualification |
| [ ] | 006 | Define Claude roles and permission rules | 005 | Qualified native profiles, role isolation, delegation limits and coordinated policy migration | 60–90 min; coordinated security-policy exception |
| [ ] | 007 | Complete Claude workflow integration | 006, 014 | Add qualified Claude profiles/capabilities to the shared caller path; production activation held until final gates | 30–60 min; native caller integration exception |
| [ ] | 008 | Complete Claude host and skill integration | 007, 016 | Qualify Claude setup/SSH/Watch/skills and native asset portability through the shared environment boundary | 30–60 min; native environment qualification exception |
| [ ] | 009 | Check plan and repair workflows with both agents | 008 | Finite ordinary-plan and repair acceptance, budgets, continuation and failure classification | 60–90 min; paired workflow qualification exception |
| [ ] | 010 | Check E2E and translation workflows with both agents | 008 | Finite adviser/reviewer and translator paths with preserved validators and launcher-owned writes | 60–90 min; paired workflow qualification exception |
| [ ] | 011 | Check Git recovery and agent switching | 009, 010 | Disposable Git transactions, selection switching/restart and preserved edits, journals and budgets | 60–90 min; indivisible recovery histories |
| [ ] | 012 | Enable configuration-driven agent selection | 011 | Activate only after every workflow gate passes; verify agent-free and package boundaries | 15–30 min |

Estimates exclude externally prepared prerequisites. Larger tasks retain their
stated session exception because their native lifecycle or coordinated boundary
must be assessed together. If independent implementation work emerges, split it
before execution under the [plan contract](Execution-Plans.md#plan-format).
