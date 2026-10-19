# 007 — Qualify Fedora retained ambient changes

Acceptance: installed
Targets: onpc-Fedora44

## First action when selected

Apply the developer-requested [staged split](../Kiosk-Prompt.md#smaller-execution-slices).
Insert only these unchecked prerequisites immediately before this active consumer:

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 0071 | [Qualify Fedora retained ambient changes](0071-ambient-fedora.md) | 006, 007a | Complete Fedora unrelated-change, immutable-view, enforcing-entry and ordinary-account history | 15–30 min |
| [ ] | 0072 | [Qualify Fedora required drift and recovery](0072-required-fedora.md) | 006, 007a, 0071 | Complete Fedora required native/config/policy/privilege drift refusals, exact restoration and reboot/reentry histories | 20–30 min; keep each history intact |

Use queue-relative `Kiosk-Prompt-Tasks/...` links. Add both IDs to this consumer's
Requires, retaining 006 and 007a, the original Scope and every assertion below.
Move Next task to 0071, finish owned cleanup and return `prerequisite_required`.
After they pass, reconcile complete Fedora histories and still-applicable Ubuntu
receipts. Repeat exact invalidated histories before closing this original row;
no partial branch or host pass supplies installed acceptance.

Session boundary: run 007a's canonical retained-view history on Fedora and
reconcile both candidate receipts. Session exception: each mutation and
required-drift/reboot/recovery branch remains indivisible. 007a retains Ubuntu
acceptance; rerun affected branches if a later fix invalidates that receipt.

Follow the [master](../Kiosk-Prompt.md), [005's transition table and admission proof](../SystemDesign/Kiosk-Confinement.md#planned-retained-material-and-immutable-pins) and canonical
confinement/native-update histories. Register a finite engineering selector;
reuse actual public entry/return observations and independent enforcing witnesses.

On Fedora, retain a healthy manager while applying owned inert unrelated
addition, removal and mode/owner changes. Require usable passwordless entry and
the correct immutable private view without an unnecessary reboot. Include the
audited source disappearance/replacement distinction and ordinary-account controls.
Verify actual manager/view identity and native isolation, not only a digest.

In a separate bounded branch, required native/config/policy/privilege drift must
still deny as specified by its actual failing stage. Reuse existing required
dependency update proof where its exact inputs match. Restore owned state and
perform the normal required reboot/reentry recovery; never kill an unowned manager.
Keep indivisible mutation/refusal/restoration histories together, preserve failures
and retain both-target package identities and cleanup receipts.
