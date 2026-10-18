# 006a — Writable sibling masking

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 005.
Estimate: 30–60 minutes.
Session exception: private-view isolation must survive a host replacement in
the retained kiosk and recover on each installed target.

## Deliverable and route

Extract unrelated writable siblings and post-preparation replacement from 006.
Read the [directory-view contract](../SystemDesign/Kiosk-Confinement.md#native-execution-and-executable-identity),
`tools/kiosk_confinement.py`, native preparation/binding callers and complete
relevant `system_kiosk_confinement.py` functions. Extend canonical variants and
existing host trust/layout tests. Planned selector (unimplemented):
`test_kiosk_writable_sibling_isolation`, area `enforcement`.

Use two unrelated root-owned sibling directories, modes 0775 and 0777, with
one distinct inert canary each. Kiosk entry works; each private view is empty
without mutating host contents. Ordinary users retain original contents/access.
After preparation, mutate/replace one exact owned masked entry on the host;
the retained kiosk must not acquire mutable content through the alias. Restore
only recorded owned mutations. Required native binds and group/world-write
prohibitions, including root-group inputs, remain enforced.

## Work sequence

1. Verify both fixture identities/modes, inert host canaries and ordinary-user
   contents/access before kiosk preparation.
2. Enter the kiosk and independently observe both empty private views, usable
   entry and enforcing execution.
3. Replace the one recorded host entry while retaining the kiosk. Reobserve
   private-view isolation and positive ordinary-user controls before recovery.
4. Restore the exact owned mutation and complete recorded cleanup.

## Acceptance and close-out

Run affected host masking/trust/fixture-cleanup checks, then the complete native
mask/replacement history on both targets. Assert usable entry, enforcing
execution, private-view witnesses and positive ordinary-user controls rather
than accepting a manifest as proof. Record kernel/security mode, exact fixture
identities, restoration and cleanup receipts. Reusable fixtures use baseline
preparation; deliberate mutations stay attempt-owned. Fix generic causes in
shared code, build as required, update existing owners and close only 006a.
