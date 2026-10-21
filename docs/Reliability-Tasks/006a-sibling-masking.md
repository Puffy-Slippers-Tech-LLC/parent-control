# 006a — Tolerate unrelated writable siblings

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: none (Baseline).
Estimate: 30–60 minutes.
Coordination: the [new confinement plan](../Kiosk-Session-Confinement-New-Plan.md#task-boundaries)
owns the compatibility redesign and its installed qualification. Before execution,
require C03/C04's [current test mapping](../SystemDesign/Kiosk-Confinement.md#c04a-installed-engineering-dispositions) from legacy masking assertions to the
[compatibility boundary](../SystemDesign/Kiosk-Confinement.md#compatibility-and-recovery-boundary);
if absent, keep this row unchecked. Review the
[historical baseline](../Kiosk-Session-Confinement-Plan.md#implementation-baseline);
reuse only exact matching scope/candidate/target evidence.
Neither plan closes the other's row, and overlapping work must not run concurrently.
Session exception: usable entry, host replacement, reentry and exact restoration
form one owned history on each installed target.

## Deliverable and route

Reproduce `83d502b3`'s unrelated installed-package directory condition and verify
tolerant entry before and after a host-side replacement. No package transaction or
retained-child approval journey is needed for these filesystem fixtures.
Read the current C03/C04 mapping, complete relevant admission/consumed-input callers and
`system_kiosk_confinement.py` functions. Extend canonical variants and affected
host checks. C04a removed case 290's `test_kiosk_writable_sibling_isolation`
worker and registration; ID 290 remains reserved and pending for usable host
variation under C09/C10. Discover its current binding before execution; if absent,
keep this row unchecked. Historical mask/private-view passes do not prove the
successor contract, and the session-identity census is not confinement proof.

Use two unrelated root-owned sibling directories, modes 0775 and 0777, with
one distinct inert canary each. Kiosk entry and the request form work without
mutating host contents; ordinary users retain original contents/access.
Replace one exact owned fixture on the host during the visit, then require
continued usability and passwordless reentry with the chosen lifecycle.
These unrelated entries must not create a consumed startup/launch route.
Neither empty private views nor retaining the same manager/filesystem image is
required. Actual child-writable consumed-input protection is covered by 006b;
mode bits alone do not establish that risk.

## Work sequence

1. Verify both fixture identities/modes, inert host canaries and ordinary-user
   contents/access and establish that the entries are unrelated to consumed inputs.
2. Enter the kiosk and independently observe usable passwordless entry and the
   actual confinement boundary reviewed by C06.
3. Replace the recorded host fixture during the visit. Observe continued usable
   requests, exit/reentry and unchanged ordinary-user controls before restoration.
4. Restore the exact owned mutation and complete recorded cleanup.

## Acceptance and close-out

Run affected host admission/fixture-cleanup checks, then the complete native
variation/replacement/reentry history on both targets. Assert usable entry,
effective confinement and positive ordinary-user controls rather than accepting
a manifest or successful rejection as proof. Record kernel/security mode, exact
fixture identities, restoration and cleanup receipts. Reusable fixtures use baseline
preparation; deliberate mutations stay attempt-owned. Fix generic causes in
shared code, build as required, update existing owners and close only 006a.
