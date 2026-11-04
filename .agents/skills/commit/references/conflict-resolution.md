# Automatic conflict resolution

Read this procedure only when a merge or saved-work restoration conflict occurs.
Follow the [shared propagation contract](../../../../docs/Execution-Plans.md#shared-worktree-propagation).

Use a dedicated GPT-6.1 Sol High subagent for resolution. Give the agent the
affected checkout, pinned source commit, branch/upstream identities, conflict
paths, original staged/unstaged/untracked state, exact backup stash identities
and recovery journal. Scope it to resolving those conflicts and validating the
affected behavior. Keep Git writes serial: the parent waits while the resolver
edits, then reviews the result and owns merge commits, pushes, stash retirement
and journal updates.

The resolver must combine both branches' intended changes and preserve active
work, including partial staging and untracked files. Never choose ours/theirs
wholesale, discard work, commit active destination edits or weaken tests to
obtain a pass. Preserve identity-recorded backups until restoration and push
are verified. Check branch, upstream and ancestry before and after each turn;
inspect interrupted restoration before replaying it. Review the resolved diff
and restored index, confirm no unmerged entries remain, and run the applicable
affected checks before continuing propagation. Continue incomplete resolution
automatically for up to five turns per conflict episode, passing the latest
findings and validation failures to the same agent.

Honor explicit caller restrictions on edits and validation. If they prevent
resolution, report the restriction as the blocker. Otherwise, a conflict,
including overlap with active worktree edits, is not by itself a reason to stop
or request coordinator review. Return to the skill's stop and recovery rules
if automatic resolution cannot complete.
