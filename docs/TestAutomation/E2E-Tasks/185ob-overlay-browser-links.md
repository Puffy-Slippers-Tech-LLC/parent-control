# 185ob — Check overlay website and privacy links

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **INFO01 overlay website/privacy link clickability**. Named consumer: task **185o** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **185oa** — ABOUT01 and INFO01 overlay information and license link clickability.

## Read only this context

Read only the delivered block rows and their named callables in the
[catalogue](../E2E-Building-Blocks.md), the selected consumer's recipe clauses,
and the affected safety/adapter tests. Follow the
[scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Use delivered prerequisite scopes; do not open predecessor briefs.

## Implementation

Use the shared clickable-link reader for the offered website and privacy
controls on the owned overlay About surface. Stop at visible/enabled state and
a usable public activation action. Do not activate links, inspect their URIs,
launch a browser or validate destinations. No browser-specific adapter is needed.

Keep targets addressed by owned public automation IDs, with ownership,
ambiguity and freshness guards. Link checks need no external provider binding.
Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

Check both links are clickable without invoking them, close About and compare
the original form choices. Qualify independent entry and
missing/disabled/nonactionable/wrong-owner refusal. No browser availability,
page content, tabs or external close/return behavior is tested.

Use a fresh guarded VM attempt through shared watch intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_browser_links
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **185ob**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
