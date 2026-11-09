---
name: commit
description: Commit and push changes from the current session, then merge the pushed source commit into every branch configured in config/environment.json and push each destination. Use when the user requests this commit-and-propagate workflow.
---

Commit and push changes from the current session, then merge the exact pushed source HEAD into
every other configured branch and push each destination. Invoking this skill
requests the full workflow, subject to existing execution permissions.

For code changes required by this workflow, follow the coding mandate in AGENTS.md:

> Simple, lean, robust; do not overengineer. Prefer solutions that simplify the resulting codebase as a whole, not merely minimize the patch. Keep refactoring within the task’s scope.

1. Read AGENTS.md, the [Git development contract](../../../docs/Approval-Tools.md#git-development)
   and [shared worktree propagation contract](../../../docs/Execution-Plans.md#shared-worktree-propagation).
   Follow their branch placement, upstream and work-preservation rules. Do not
   start an execution-plan launcher merely to commit.
2. Inspect the current branch, changes, worktrees and remotes. Read
   [config/environment.json](../../../config/environment.json) to resolve the
   source and every destination. Include branches on other hosts regardless of
   their VM scheduling enabled flag; host placement does not authorize SSH.
3. Commit only changes made for the current session's work. Use the session
   history and diffs to identify them; a modified or staged file is not by itself
   evidence that all its changes belong to this session. Stage only the relevant
   hunks, including within files shared with unrelated work. Leave all other
   staged, unstaged and untracked changes intact and out of the commit. Ask only
   when ownership cannot be determined safely. Review the commit's exact scope
   before creating a descriptive commit, or use the existing HEAD when there
   are no current-session changes to commit.
4. Fetch and reconcile remote state without discarding work or rewriting
   published history. Push the source and record its exact successfully pushed
   HEAD. Merge that pinned commit into every other configured destination and
   push each, preserving local and remote work. Do not force-push, invent missing
   branches or alter Git configuration. Reuse an applicable maintained public
   workflow when available; do not invoke private launcher helpers ad hoc.
   For final remote verification, use direct `git fetch --no-tags REMOTE REF`
   commands under the existing Git grant, then check that `FETCH_HEAD` contains
   the pinned commit with `git merge-base --is-ancestor`. Set the command tool's
   working directory to the checkout. Do not substitute `git ls-remote`, global
   `git -C` options, shell loops or interpreter wrappers: these do not match the
   approved network-command prefix and can run inside the sandbox, where SSH
   may report misleading system-config ownership errors. Correct the command
   shape without changing SSH files, authentication or approval rules.
5. Only if a merge or saved-work restoration conflict occurs, read
   [conflict resolution](references/conflict-resolution.md) and delegate automatic
   resolution to a subagent. Overlap with active worktree edits alone does not
   require stopping or coordinator review. Skip this reference and delegation
   when there is no conflict.
6. Stop only when automatic resolution is exhausted, intent or ownership remains
   ambiguous after investigation, validation cannot pass without an unauthorized
   behavior change, configuration or permissions prevent progress, or a push
   fails beyond the shared contract's bounded reconciliation. Honor explicit
   caller restrictions on edits and validation; report such a restriction as the
   blocker rather than treating the conflict itself as requiring human review.
   Preserve recoverable work and report the exact blocker, resolution attempts
   and completed destinations. Resume unfinished propagation with the same
   pinned source commit rather than creating another source commit.
7. On success, leave the source checkout on its original branch. Report the
   source commit hash and each destination pushed. Completion requires every
   configured destination to succeed. This does not publish a product release.
