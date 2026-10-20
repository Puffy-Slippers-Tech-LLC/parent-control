# 007a — Qualify Ubuntu retained ambient changes

Acceptance: installed
Targets: onpc-Ubuntu26.04

## Staged prerequisites

The developer-requested [staged split](../Kiosk-Prompt.md#smaller-execution-slices)
has been applied. These prerequisites were inserted immediately
before this consumer:

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 007a1 | [Implement canonical retained-view histories](../Kiosk-Prompt.md#canonical-retained-view-histories--007a1) | 006 | Register and host-validate the shared finite ambient and required-drift histories without installed acceptance | Host passed; no installed acceptance |
| [ ] | 007a2 | [Qualify Ubuntu retained ambient changes](007a2-ambient-ubuntu.md) | 007a1 | Complete Ubuntu unrelated-change, immutable-view, enforcing-entry and ordinary-account history | 15–30 min |
| [ ] | 007a3 | [Qualify Ubuntu required drift and recovery](007a3-required-ubuntu.md) | 007a1, 007a2 | Complete Ubuntu required native/config/policy/privilege drift refusals, exact restoration and reboot/reentry histories | 20–30 min; keep each history intact |

Requires 006, 007a1, 007a2 and 007a3. 007a1's host implementation passed;
007a2 is next, and the split grants no installed acceptance credit. Resume this consumer only after all
three prerequisites pass. This installed consumer reconciles the complete
applicable Ubuntu histories and cleanup; repeat invalidated histories before
close-out. Keep the original row unchecked until its entire acceptance passes.

Read the [master](../Kiosk-Prompt.md), [reviewed transition table and admission proof](../SystemDesign/Kiosk-Confinement.md#planned-retained-material-and-immutable-pins), canonical
confinement/native-update mechanics and applicable installed/public-observation
contracts. Implement/register the finite canonical history and reuse shared entry.

Retain a healthy manager during owned unrelated addition/removal and mode/owner
changes. Require usable passwordless entry without unnecessary reboot, correct
immutable private views, actual manager/view identity, enforcing isolation and
ordinary-account controls. Include the audited disappearance/replacement distinction.

In a separate bounded branch, required native/config/policy/privilege drift still
refuses at its actual stage. Reuse existing exact required-update proof where
valid; restore owned state and require normal reboot/reentry recovery. Do not kill
an unowned manager or count attestation failure as generation-stage evidence.

Session exception: complete finite mutation/refusal/restoration/recovery histories
and first-target implementation can take 35–60 minutes. Split independent new
mechanics first. Run affected host/build checks, retain first failures and exact
package/fixture/cleanup receipts; 007 owns Fedora and both-target reconciliation.
