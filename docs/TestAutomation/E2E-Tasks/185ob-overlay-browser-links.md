# 185ob — Check overlay website and privacy links

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **INFO01 overlay website/privacy link clickability**. Named consumer: task **185o** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **185oa** — ABOUT01 and INFO01 overlay information and license link clickability.

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

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_overlay_browser_links
```
