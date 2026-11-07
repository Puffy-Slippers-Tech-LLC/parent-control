# Agent adapter execution plan

Task queue: [Ordered task queue](Agent-Adapter-Task-Queue.md).
Next task: none.

Status: the bounded Codex extraction, inactive Claude transport foundation and
shared selection lifetime, setup/SSH readiness and Watch integration are complete.
Live Claude qualification and implementation that
depends on it remain future work under [Out of scope](#out-of-scope), not blockers
in the active queue. Planning does not enable Claude or grant qualification credit.

## Goal and boundaries

Eventually, the checked-in `agent` field in `config/environment.json` should
select the coding agent for every repository-owned agent session. Preserve
workflow acceptance, budgets, ownership, cleanup and Git recovery. Agent-free
operations and the installed product must not require a coding CLI or SDK.

The [design and qualification reference](Agent-Adapter-Design.md) owns the
integration map, future requirements and accepted native results. Preserve its
explicit unqualified and deferred limits; do not reopen completed work to renew
evidence. The [execution contract](Execution-Plans.md) owns planning, delegation,
task validation and close-out. Every task owns its scoped checks and cleanup.

## Running the plan

Validate the active queue without execution:

```sh
tools/execute-plan 'docs/Agent_Adapter.md' --check
```

Run all remaining active tasks:

```sh
tools/execute-plan 'docs/Agent_Adapter.md'
```

No active tasks remain. The launcher excludes rows below `## Deferred future work`. Deferred work requires
an explicit scope change: move the selected dependency-ordered rows above that
boundary, update this sole next-task pointer, and validate before execution.
No new launcher or provider command-line option is needed.

## Models, roles and repository policy

Current Codex goal, native profile, independent review and delegation policies
remain enforced. The proposed [Claude policy migration](Agent-Adapter-Design.md#models-roles-and-repository-policy)
belongs to future task 006; this plan does not authorize policy exceptions.

## Trusted-worktree follow-up

Preserve the [accepted results and native limitations](Agent-Adapter-Design.md#trusted-worktree-follow-up).
Delegated write isolation and explicit helper retirement remain unqualified and
outside the accepted extraction scope. This conversion does not remediate them.

## Out of scope

Live Claude transport qualification, native roles and permission policy,
Claude-specific workflow/host/skill integration, two-agent acceptance and final
Claude activation remain future work. Their ordered briefs are below the queue's
[deferred-work boundary](Agent-Adapter-Task-Queue.md#deferred-future-work).

Strict configuration parsing and the immutable selection API are prepared by
task 013. Task 014's caller snapshots and recovery plumbing are complete with
the available host checks passed. Restricted disposable-session checks were
skipped at the developer's direction and remain unqualified.
Task 015 routes setup readiness and SSH agent admission through the native
adapter while preserving Codex and refusing unqualified Claude. Focused host,
shell and source checks passed; no live remote or full setup qualification was
performed. Task 016 displays recorded agent/model/effort with unknown legacy
provenance, reuses launcher readiness for Watch actions and tracks optional adapter
sources in controller dependency inventories. Focused host/source checks,
JavaScript syntax, independent read-only review, DEB/RPM builds and Markdown links
passed. No live SSH or Claude qualification was performed; no Watch-widget tests
or native Claude policy/skill assets were added.

Paid Claude model access, authentication and a compatible SDK must be prepared
separately before live qualification. Authentication alone is insufficient;
preflight must not install or authenticate prerequisites. Missing access does
not make these excluded tasks active blockers. The [reference](Agent-Adapter-Design.md#out-of-scope)
retains the prerequisite findings and future acceptance gates.
