# Kiosk resilience execution queue

The [master](Kiosk-Resilience-Plan.md) owns the target, decision policy, finite
acceptance matrix, historical baseline and sole next-task pointer. All rows
implement the replacement; none is completed by this replan. Old completion
evidence remains in the baseline and Git. There is no legacy or staged queue.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | R01 | [Settle the admission and confinement contract](Kiosk-Prompt-Tasks/R01-contract.md) | Baseline | Whole-path reachable-threat and allow/recover/reject analysis; minimal design and explicit old-check dispositions | 20–30 min |
| [ ] | R02 | [Build the minimal entry proof](Kiosk-Prompt-Tasks/R02-entry-proof.md) | R01 | One reusable startup slice and host controls for actual entry, approval and escape boundaries | 30–60 min; one native startup transaction |
| [ ] | R03 | [Prove the entry design on Ubuntu](Kiosk-Prompt-Tasks/R03-proof-ubuntu.md) | R02 | Early public entry, approval, recovery and actual boundary proof on Ubuntu | 30–60 min; indivisible installed history |
| [ ] | R04 | [Prove the entry design on Fedora](Kiosk-Prompt-Tasks/R04-proof-fedora.md) | R02, R03 | Equivalent Fedora proof and changed-input reconciliation before broader implementation | 30–60 min; indivisible installed history |
| [ ] | R05 | [Remove broad admission dependencies](Kiosk-Prompt-Tasks/R05-admission.md) | R04 | Production minimal boundary; remove ambient inventory, cosmetic identity and obsolete retained-source requirements | 30–60 min; shared native entry replacement |
| [ ] | R06 | [Recover owned kiosk infrastructure](Kiosk-Prompt-Tasks/R06-recovery.md) | R05 | Bounded transient retry and owned renewal, preserving live/foreign sessions and interruption safety | 20–30 min |
| [ ] | R07 | [Tolerate authentication and session configuration](Kiosk-Prompt-Tasks/R07-pam-session.md) | R06 | Narrow PAM/session coupling, tolerant valid configuration and explicit administrator-policy preservation | 20–30 min |
| [ ] | R08 | [Keep optional failures out of core entry](Kiosk-Prompt-Tasks/R08-degradation.md) | R07 | Optional fallbacks and original-cause/recovery diagnostics without losing core requests | 20–30 min |
| [ ] | R09 | [Compose compatibility and confinement coverage](Kiosk-Prompt-Tasks/R09-matrix.md) | R08 | Register finite A–H matrix, mixed configurations and escape controls; repair only reused supporting mechanics | 30–60 min; shared finite history composition |
| [ ] | R10 | [Qualify resilient entry on Ubuntu](Kiosk-Prompt-Tasks/R10-acceptance-ubuntu.md) | R09 | Final Ubuntu A–H public histories, negative controls, diagnostic download and restoration | 45–75 min; indivisible installed histories |
| [ ] | R11 | [Qualify resilient entry on Fedora](Kiosk-Prompt-Tasks/R11-acceptance-fedora.md) | R09, R10 | Final Fedora A–H histories and final-input applicability of Ubuntu results | 45–75 min; indivisible installed histories |
| [ ] | R12 | [Reconcile and close the replacement](Kiosk-Prompt-Tasks/R12-closeout.md) | R10, R11 | Final rejection/input/evidence audit; remove obsolete requirements; no normal-use rejection waiver | 20–30 min |

Longer rows have session exceptions to keep one native transaction or complete
installed history together. Estimates are not timeout overrides. Split genuinely
independent discoveries under the shared plan contract; do not preserve obsolete
machinery merely to satisfy old tests.
