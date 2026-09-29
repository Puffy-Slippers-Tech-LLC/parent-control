# 185oa — Read overlay About and check its license link

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **ABOUT01 and INFO01 overlay information and license link clickability**. Named consumer: task **185o** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **044a** — DESK10 same-desktop window switching.
- **185p** — INFO01 Parent.
- **185l** — Retained ABOUT02/03 entry/return helpers; use the current link-only contract.

## Read only this context

Read only the delivered block rows and their named callables in the
[catalogue](../E2E-Building-Blocks.md), the selected consumer's recipe clauses,
and the affected safety/adapter tests. Follow the
[scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Use delivered prerequisite scopes; do not open predecessor briefs.

## Implementation

Read owned About product/version information and use the shared clickable-link
reader for the license control. Require visible/enabled state and a usable
public activation action, then stop. Do not invoke the link, inspect its URI or
require a document handler/content reader. Close owned About and compare the form.

Keep targets addressed by owned public automation IDs, with ownership,
ambiguity and freshness guards. Link checks need no external provider binding.
Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

On a live overlay, capture choices, read product/version, check license link
clickability without invoking it, close About and compare unchanged choices.
Qualify independent entry and missing/disabled/nonactionable/wrong-owner refusal.

Use a fresh guarded VM attempt through shared watch intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_license
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **185oa**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
