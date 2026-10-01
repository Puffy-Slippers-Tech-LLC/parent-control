# 185oa — Read overlay About and check its license link

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **ABOUT01 and INFO01 overlay information and license link clickability**. Named consumer: task **185o** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **044a** — DESK10 same-desktop window switching.
- **185p** — INFO01 Parent.
- **185l** — Retained ABOUT02/03 entry/return helpers; use the current link-only contract.

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

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_license
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
