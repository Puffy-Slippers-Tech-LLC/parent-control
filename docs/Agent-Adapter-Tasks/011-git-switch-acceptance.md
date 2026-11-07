# 011 — Check Git recovery and agent switching

Acceptance: host

Purpose: qualify dependent Git sessions and selection changes across owned
operations. Requires tasks 009 and 010 and explicit reactivation.

Read the [master](../Agent_Adapter.md),
[selection lifetime](../Agent-Adapter-Design.md#reading-and-changing-the-selection),
[delivery gates](../Agent-Adapter-Design.md#delivery-and-validation),
[Git close-out](../Execution-Plans.md#git-close-out-and-recovery),
[propagation/recovery](../Execution-Plans.md#shared-worktree-propagation),
[approval routes](../Approval-Tools.md) and
[storage mandate](../Mandates/Test-Storage-Mandate.md). Inspect affected complete
functions in `tools/launcher_git.py`, `tools/launcher_worktrees.py`, the shared
supervisor and their callers; discover existing Git fixtures and owned harnesses.

Use disposable local repositories/remotes with recorded ownership, never the
developer's actual upstreams or pre-existing work. Exercise each adapter's
pinned commit-helper and conflict-resolver readiness, a finite close-out, merge
conflict and stash-restoration conflict, including staged/unstaged/untracked
edits and interrupted recovery. Preserve normal controller ownership of commit,
push, stash retirement and every configured destination; agent reports alone
cannot finish the transaction. Keep deterministic Git operations agent-free.

In the same isolated fixture family, change only executing-checkout `agent`
configuration between independent sessions. Check in-flight pinning through
turns/retries and dependent Git work; switch only after owned children/cleanup
finish. Check restart after an interrupted operation and legacy unknown
provenance without requiring the old provider or resetting task allowances.
Ignore external selection overrides. Stop/cleanup must work with invalid config
or absent new-provider readiness, and agent failures must not cross-fallback.

Acceptance requires real native helper use and observed recovery preserving
edits, transaction identity, accepted results and budgets for both adapters.
Report unexercised outage/refusal paths honestly; no simulated result can stand
in for a claimed native qualification. The session exception preserves indivisible
conflict and restart histories. Split independent discovered repairs first.

Reap owned children and retire only identity-recorded disposable work through
the maintained cleanup routes. Use existing affected checks without new permanent
non-product tests; check links and any triggered packaging build before close-out.
