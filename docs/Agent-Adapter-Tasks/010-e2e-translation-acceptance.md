# 010 — Check E2E and translation workflows with both agents

Acceptance: host

Purpose: qualify the E2E coordinator/helper and translation boundaries without
claiming a customer E2E pass or synchronizing real release notes. Requires task
008 and explicit reactivation; production selection remains disabled.

Read the [master](../Agent_Adapter.md),
[delivery gates](../Agent-Adapter-Design.md#delivery-and-validation),
[role policy](../Agent-Adapter-Design.md#models-roles-and-repository-policy),
applicable workflow contracts in [tests/README.md](../../tests/README.md), and
the [translation owner](../SystemDesign/Localization.md#whats-new-translation-workflow).
Apply the [approval](../Approval-Tools.md) and
[storage](../Mandates/Test-Storage-Mandate.md) contracts. Discover existing
workflow fixtures and inspect complete caller/acceptance paths before changes.

Use finite disposable task/translation fixtures through actual acceptance
engines for both adapters. Exercise adviser and independent-review dispatch,
fresh contexts, configured role/effort pins, join/close discipline, delegation
limits and result ownership; helper messages cannot replace coordinator results.
Exercise finite translator records including malicious embedded instructions,
version/brand/URL/placeholders and intentional failed results. Keep translation
sessions read-only and writes/validation with the launcher. Do not invoke real
`tools/sync-whatsnew` or change release translation assets without its separately
required explicit request; reuse maintained engineering fixture routes.

Acceptance requires unchanged E2E escalation/budget/validation and translation
write/validation boundaries, with both native adapters and meaningful refusal,
denial and malformed-result behavior. No VM or installed customer scenario is
required merely to qualify these agent boundaries. If an actual product check
is needed, first apply its VM/UI/acceptance mandate; a host result never grants
customer acceptance. Do not weaken unresolved native isolation or retirement
requirements. The session exception covers two finite helper/workflow histories.

Add no permanent non-product tests. Finish owned cleanup, run affected existing
checks and links, and record exact qualified scope. Apply the package-build
mandate only when the final edits affect its scope.
