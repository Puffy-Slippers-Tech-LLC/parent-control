# 185o — Complete overlay support and legal links

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Check remaining offered support/legal links are clickable and compose overlay
information observations. Reuse 185oa/185ob for license, website and privacy
controls; no external link is invoked.

Reuse the delivered scope of tasks **185oa**, **185ob** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **ABOUT01 and INFO01 overlay**. First scheduled consumer: [E2E-042, case 191](../E2E-Scenario-Recipes.md#e2e-042).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **044a** — DESK10 same-desktop window switching.
- **185p** — INFO01 Parent.
- **185l** — Retained ABOUT02/03 entry/return helpers; use the current link-only contract.
- **185ob** — INFO01 overlay website/privacy link clickability.

## Implementation

Complete the overlay UI owned-information/clickability matrix, sharing Parent's
information-route operations. Installed acceptance owns each clickable control
and unchanged form return; it does not repeat local layout or content permutations.

Bind overlay About and the offered information controls. Reuse the shared About
and clickable-link readers; retain the request form's earlier observation.

Start at `AccessibleUI.overlay_about_scope`, `open_overlay_about` and
`read_overlay_link` in `tests/e2e/accessible_ui.py`. License and website/privacy
use the finite `journey_blocks.overlay_license_read` /
`onpc_about::overlay_license` binding (`links='license'` or `'browser-links'`).
`overlay_license.PLAN` and `BROWSER_LINKS_PLAN` in
`tests/e2e/overlay_license.py` declare the entry, independent read and immutable
`KioskRequestJourney.request_checks` return endpoints;
`onpc_request_flow::overlay_license` / `overlay_browser_links` qualify them.
Extend the shared finite reader/fragment for the remaining links rather than
copying entry/close mechanics. Relevant host owners are
`tests/unit/test_e2e_overlay_license.py`,
`tests/unit/test_e2e_overlay_valid_choices.py` and
`tests/ui/test_request_form_component.py::test_overlay_about_license_shared_reader_and_unchanged_form`.

Resolve each control afresh on the owned child-session surface. Stop at
visible/enabled state and a usable public activation action. Do not invoke
links, inspect their URIs, validate handlers or read external destinations.
Close only owned About and compare the unchanged form.

## Live VM acceptance

On the live child overlay, read product/version and check every offered
information link is clickable without invoking it. Close About and compare
the original form choices before editing. No external handler is required.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_read_overlay_about_and_links
```
