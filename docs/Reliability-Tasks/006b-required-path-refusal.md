# 006b — Required executable ancestor refusal

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 005.
Estimate: 30–60 minutes.
Session exception: native refusal, exact restoration and fresh successful entry
must complete on each target in one owned fault/recovery history.

## Deliverable and route

Extract the required-executable-ancestor branch from 006. Read the
[directory-view contract](../SystemDesign/Kiosk-Confinement.md#native-execution-and-executable-identity),
`tools/kiosk_confinement.py`, native preparation callers and relevant complete
`system_kiosk_confinement.py` functions. Planned selector (unimplemented):
`test_kiosk_required_ancestor_refusal`, area `enforcement`.

Record one required executable ancestor's exact identity and original metadata,
then make only that owned input group-writable. Preparation must refuse before
publishing untrusted execution, including when the owning group is root. Retain
the original refusal, restore the exact mutation and require normal native
preparation/admission, usable kiosk and enforcing execution. Independently
observe unaffected ordinary-user contents/access. Do not weaken required bind
trust to reuse the unrelated-sibling masking behavior.

## Acceptance and close-out

Run affected host trust/refusal and mutation-cleanup checks, then the complete
refusal/restoration/recovery branch on both targets. Use inert finite fixtures,
recorded identities and maintained restoration; reusable inputs belong in
baseline preparation. Retain refusal stage, kernel/security mode, positive
recovery and ordinary-user controls plus cleanup receipts. Repair demonstrated
shared causes, build as required and update existing confinement owners. Close
only 006b; pinned-alias mismatches remain in 006.
