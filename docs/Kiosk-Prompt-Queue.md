# Kiosk resilience execution queue

The [master](Kiosk-Resilience-Plan.md) owns the target, decision policy, finite
acceptance matrix, historical baseline and sole next-task pointer. All rows
implement the replacement; none is completed by this replan. Old completion
evidence remains in the baseline and Git. There is no legacy or staged queue.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | R01a | [Choose the execution and activation boundary](SystemDesign/Kiosk-Confinement.md#r01a-execution-and-activation-decision) | Baseline | Actual first-exec/search/activation audit and one concrete cross-platform execution boundary | Review passed: actual GDM/manager credentials, closed unit/bus consumers, execution ledger and R02 witnesses; [551 close-out checks](../output/test-runs/host/reports/20261020T053102Z-ea70a1b1/report.md), 169 links valid. No runtime resources; integrated R01 review remains pending. |
| [x] | R01b | [Choose the effective authentication policy](SystemDesign/Kiosk-Confinement.md#r01b-effective-authentication-decision) | R01a | Kiosk-scoped passwordless PAM route, effective denial and ordinary-account preservation | Review passed: preserved effective GDM policy/flags, kiosk-only empty conversation/password guard, session-policy dispatch, ordinary roles and privileged parent approval; shared ledger and R02b/R07 controls. [551 checks](../output/test-runs/host/reports/20261020T054132Z-884621a8/report.md), [313 final consistency checks](../output/test-runs/host/reports/20261020T054350Z-64bb8f8b/report.md), links valid. No product/test-policy change or runtime state; integrated R01 review remains pending. |
| [ ] | R01c | [Settle approval and visit lifetime](Kiosk-Prompt-Tasks/R01c-approval.md) | R01a, R01b | Request/agent/session association and explicit cancellation/commit ordering | 20–30 min |
| [ ] | R01d | [Settle configuration and quarantine ownership](Kiosk-Prompt-Tasks/R01d-configuration.md) | R01b | Capability-based visibility repair, optional provisioning and administrator-safe quarantine ownership | 20–30 min |
| [ ] | R01e | [Settle readiness and activation recovery](Kiosk-Prompt-Tasks/R01e-readiness.md) | R01a, R01c, R01d | Broker prerequisite isolation, lifecycle ownership, activation classes and one readiness deadline | 20–30 min |
| [ ] | R01 | [Review the integrated admission contract](Kiosk-Prompt-Tasks/R01-contract.md) | R01a, R01b, R01c, R01d, R01e | Integrated ledger, legacy-check mapping, finite proof and independent architecture review | 30–45 min; session exception: integrated architecture review/revision |
| [ ] | R02a | [Implement the minimal startup transaction](Kiosk-Prompt-Tasks/R02a-startup.md) | R01 | Runnable production startup/approval/exit/renewal slice with actual caller and cleanup witnesses | 30–60 min; session exception: native startup transaction |
| [ ] | R02b | [Add the unfamiliar PAM proof fixture](Kiosk-Prompt-Tasks/R02b-pam-fixture.md) | R02a | Finite administrator-owned unfamiliar callback with effective ordinary-account and kiosk controls | 15–30 min |
| [ ] | R02c | [Add the automatic-service proof fixture](Kiosk-Prompt-Tasks/R02c-service-fixture.md) | R02a, R02b | Finite unfamiliar automatic activation and external-launch fixture with permitted controls | 20–30 min |
| [ ] | R02 | [Compose the minimal entry proof](Kiosk-Prompt-Tasks/R02-entry-proof.md) | R02a, R02b, R02c | Actual-call proof composition, host/cosmetic variations and registered R03/R04 selector handoff | 15–30 min |
| [ ] | R03 | [Prove the entry design on Ubuntu](Kiosk-Prompt-Tasks/R03-proof-ubuntu.md) | R02 | Early public entry, approval, recovery and actual boundary proof on Ubuntu | 30–60 min; session exception: complete early architecture proof |
| [ ] | R04 | [Prove the entry design on Fedora](Kiosk-Prompt-Tasks/R04-proof-fedora.md) | R02, R03 | Equivalent Fedora proof and changed-input reconciliation before broader implementation | 30–60 min; session exception: complete early architecture proof |
| [ ] | R05a | [Repair visibility by supported capability](Kiosk-Prompt-Tasks/R05a-visibility.md) | R04 | Compatible AccountsService repair without exact-version admission or unrelated metadata loss | 20–30 min |
| [ ] | R05b | [Recover owned account quarantine](Kiosk-Prompt-Tasks/R05b-quarantine.md) | R05a | Interrupted required-setup recovery and owned expiry release preserving administrator policy | 20–30 min |
| [ ] | R05 | [Remove broad admission dependencies](Kiosk-Prompt-Tasks/R05-admission.md) | R04, R05a, R05b | Integrate the proven production boundary/activation; remove obsolete admission code and implementation assertions | 30–60 min; session exception: shared native entry replacement |
| [ ] | R06a | [Renew owned kiosk infrastructure safely](Kiosk-Prompt-Tasks/R06a-renewal.md) | R05 | Bounded dependency waits/renewal, interrupted recovery and live/foreign identity preservation | 20–30 min |
| [ ] | R06b | [Isolate broker readiness by affected child](Kiosk-Prompt-Tasks/R06b-broker-readiness.md) | R06a | Healthy-child requests despite another child's unavailable home/extension, with enforcement-preserving recovery | 20–30 min |
| [ ] | R06 | [Bind approval lifetime through recovery](Kiosk-Prompt-Tasks/R06-recovery.md) | R06a, R06b | Visit/request/agent association through renewal and competing sessions; both approval/commit race outcomes | 20–30 min |
| [ ] | R07 | [Tolerate authentication and session configuration](Kiosk-Prompt-Tasks/R07-pam-session.md) | R06 | Narrow PAM/session coupling, tolerant valid configuration and explicit administrator-policy preservation | 20–30 min |
| [ ] | R08a | [Degrade failed provisioning icons](Kiosk-Prompt-Tasks/R08a-provisioning-icon.md) | R07 | Display-default fallback that completes required setup and safe owned quarantine release | 15–30 min |
| [ ] | R08b | [Keep native authentication usable without translations](Kiosk-Prompt-Tasks/R08b-agent-language.md) | R08a | C-only/missing-catalogue/discovery fallback preserving ready-agent identity and request ordering | 20–30 min |
| [ ] | R08c | [Degrade optional runtime features](Kiosk-Prompt-Tasks/R08c-runtime-fallbacks.md) | R08b | Artwork/font/catalogue/audio/notification/report fallbacks preserving the shared core request form | 15–30 min |
| [ ] | R08 | [Preserve causes through fallback and recovery](Kiosk-Prompt-Tasks/R08-degradation.md) | R08a, R08b, R08c | Original-cause diagnostics, accurate core-unavailable retry/exit and mixed fallback/reentry composition | 20–30 min |
| [ ] | R09a | [Compose compatibility histories](Kiosk-Prompt-Tasks/R09a-compatibility.md) | R08 | Register finite A–C host/resource/caller/PAM histories using delivered mechanics | 20–30 min |
| [ ] | R09b1 | [Compose visit and renewal histories](Kiosk-Prompt-Tasks/R09b1-visits.md) | R09a | Register D repeated-entry, renewal, interruption and competing/live/foreign-session histories | 20–30 min |
| [ ] | R09b2 | [Compose approval lifetime histories](Kiosk-Prompt-Tasks/R09b2-approval.md) | R09b1 | Register D pending-cancellation and both post-authentication commit orderings with independent grant results | 20–30 min |
| [ ] | R09b3 | [Compose cross-child readiness histories](Kiosk-Prompt-Tasks/R09b3-child-readiness.md) | R09b2 | Register E unavailable-child isolation, healthy-child approval and restored-child enforcement/recovery | 15–30 min |
| [ ] | R09b | [Compose transient dependency histories](Kiosk-Prompt-Tasks/R09b-lifetime.md) | R09a, R09b1, R09b2, R09b3 | Register E bounded service/bus/lock recovery and separate permanent-global-failure controls | 15–30 min |
| [ ] | R09c1 | [Compose compatible visibility repair](Kiosk-Prompt-Tasks/R09c1-visibility.md) | R09b | Register F compatible AccountsService repair with public results, metadata preservation and explicit simulation limits | 15–30 min |
| [ ] | R09c | [Compose real update histories](Kiosk-Prompt-Tasks/R09c-updates.md) | R09b, R09c1 | Register F unrelated-package and actual relevant-update histories with activation and restoration | 15–30 min |
| [ ] | R09d | [Compose escape and policy controls](Kiosk-Prompt-Tasks/R09d-boundaries.md) | R09c | Register G reachable-route pairs, actual child-write authority and effective policy controls | 20–30 min |
| [ ] | R09e | [Compose diagnostic recovery and download](Kiosk-Prompt-Tasks/R09e-diagnostics.md) | R09d | Register H original-cause incident/recovery/reboot/Parent-download history with privacy and restoration | 15–30 min |
| [ ] | R09 | [Freeze the complete compatibility matrix](Kiosk-Prompt-Tasks/R09-matrix.md) | R09a, R09b, R09c, R09d, R09e | Register H combinations and freeze complete A–H selectors, inputs and evidence ownership | 20–30 min |
| [ ] | R10a | [Qualify Ubuntu host and optional variation](Kiosk-Prompt-Tasks/R10a-compatibility-ubuntu.md) | R09 | Complete Ubuntu A/B public-entry, fallback, genuine approval and restoration histories | 20–30 min |
| [ ] | R10b | [Qualify Ubuntu integration and escape controls](Kiosk-Prompt-Tasks/R10b-boundaries-ubuntu.md) | R10a | Complete Ubuntu C/G caller/PAM, reachable escape, effective policy and ordinary-role histories | 20–30 min |
| [ ] | R10c1 | [Qualify Ubuntu visits and renewal](Kiosk-Prompt-Tasks/R10c1-visits-ubuntu.md) | R10b | Complete Ubuntu D repeated-entry, renewal, interrupted-recovery and competing/live/foreign-session histories | 30–45 min; session exception: complete repeated-visit and renewal histories |
| [ ] | R10c2 | [Qualify Ubuntu approval lifetime](Kiosk-Prompt-Tasks/R10c2-approval-ubuntu.md) | R10c1 | Complete Ubuntu D pending-cancellation and both approval/commit orderings through reentry and fresh approval | 20–30 min |
| [ ] | R10c3 | [Qualify Ubuntu cross-child readiness](Kiosk-Prompt-Tasks/R10c3-child-readiness-ubuntu.md) | R10c2 | Complete Ubuntu E unavailable-child isolation, healthy-child approval and restored-child recovery | 20–30 min |
| [ ] | R10c | [Qualify Ubuntu transient recovery](Kiosk-Prompt-Tasks/R10c-lifetime-ubuntu.md) | R10b, R10c1, R10c2, R10c3 | Complete Ubuntu E service/bus/lock recovery and permanent-global-failure control; reconcile D/E receipts | 20–30 min |
| [ ] | R10d1 | [Qualify Ubuntu visibility repair](Kiosk-Prompt-Tasks/R10d1-visibility-ubuntu.md) | R10c | Complete Ubuntu F compatible AccountsService repair, public approval and metadata/ordinary-user preservation | 20–30 min |
| [ ] | R10d | [Qualify Ubuntu real update recovery](Kiosk-Prompt-Tasks/R10d-updates-ubuntu.md) | R10c, R10d1 | Complete Ubuntu F unrelated-package and actual relevant-update histories with restored owned state | 30–60 min; session exception: complete package-update histories |
| [ ] | R10e | [Qualify Ubuntu declared combinations](Kiosk-Prompt-Tasks/R10e-combinations-ubuntu.md) | R10d | Complete Ubuntu H's at least three declared A–F combinations with public approval and restoration | 20–30 min |
| [ ] | R10 | [Complete Ubuntu diagnosis and evidence](Kiosk-Prompt-Tasks/R10-acceptance-ubuntu.md) | R09, R10a, R10b, R10c, R10d, R10e | Ubuntu H recovery/reboot/Parent download and final applicability of every A–H receipt | 30–45 min; session exception: diagnostic recovery/reboot/download history |
| [ ] | R11a | [Qualify Fedora host and optional variation](Kiosk-Prompt-Tasks/R11a-compatibility-fedora.md) | R09, R10 | Complete Fedora A/B public-entry, fallback, genuine approval and restoration histories | 20–30 min |
| [ ] | R11b | [Qualify Fedora integration and escape controls](Kiosk-Prompt-Tasks/R11b-boundaries-fedora.md) | R11a | Complete Fedora C/G caller/PAM, reachable escape, privileged authentication and ordinary-role histories | 20–30 min |
| [ ] | R11c1 | [Qualify Fedora visits and renewal](Kiosk-Prompt-Tasks/R11c1-visits-fedora.md) | R11b | Complete Fedora D repeated-entry, renewal, interrupted-recovery and competing/live/foreign-session histories | 30–45 min; session exception: complete repeated-visit and renewal histories |
| [ ] | R11c2 | [Qualify Fedora approval lifetime](Kiosk-Prompt-Tasks/R11c2-approval-fedora.md) | R11c1 | Complete Fedora D pending-cancellation and both approval/commit orderings through reentry and fresh approval | 20–30 min |
| [ ] | R11c3 | [Qualify Fedora cross-child readiness](Kiosk-Prompt-Tasks/R11c3-child-readiness-fedora.md) | R11c2 | Complete Fedora E unavailable-child isolation, healthy-child approval and restored-child recovery | 20–30 min |
| [ ] | R11c | [Qualify Fedora transient recovery](Kiosk-Prompt-Tasks/R11c-lifetime-fedora.md) | R11b, R11c1, R11c2, R11c3 | Complete Fedora E service/bus/lock recovery and permanent-global-failure control; reconcile D/E receipts | 20–30 min |
| [ ] | R11d1 | [Qualify Fedora visibility repair](Kiosk-Prompt-Tasks/R11d1-visibility-fedora.md) | R11c | Complete Fedora F compatible AccountsService repair, public approval and metadata/ordinary-user preservation | 20–30 min |
| [ ] | R11d | [Qualify Fedora real update recovery](Kiosk-Prompt-Tasks/R11d-updates-fedora.md) | R11c, R11d1 | Complete Fedora F unrelated-package and actual relevant-update histories with restored owned state | 30–60 min; session exception: complete package-update histories |
| [ ] | R11e | [Qualify Fedora declared combinations](Kiosk-Prompt-Tasks/R11e-combinations-fedora.md) | R11d | Complete Fedora H's at least three declared A–F combinations with public approval and restoration | 20–30 min |
| [ ] | R11 | [Complete Fedora diagnosis and evidence](Kiosk-Prompt-Tasks/R11-acceptance-fedora.md) | R09, R10, R11a, R11b, R11c, R11d, R11e | Fedora H diagnostic/download history and final-input applicability of every both-platform A–H receipt | 30–45 min; session exception: diagnostic recovery/reboot/download history |
| [ ] | R12a | [Audit final candidate and rejection evidence](Kiosk-Prompt-Tasks/R12a-evidence-audit.md) | R10, R11 | Final both-platform A–H/input/cleanup applicability and every remaining entry-rejection decision | 20–30 min |
| [ ] | R12 | [Reconcile and close the replacement](Kiosk-Prompt-Tasks/R12-closeout.md) | R10, R11, R12a | Reconcile enduring requirements, reliability/proof consumers and final links; close only with accepted audit | 15–30 min |

Estimates include scoped reading, required review/build/checks, cleanup and
close-out; they are provisional allowances, not measured delivery forecasts.
R01 re-estimates implementation from its selected mechanism; R02 and R09 refine
installed rows from registered complete histories and available run timings.
If independent work still exceeds an ordinary allowance, split it before its
consumer starts rather than retaining the label or cutting acceptance. In
particular, native startup, quarantine ownership, broker/approval races and
native-language work must be rechecked against the selected design.

Longer rows name their indivisible review, native transaction or installed
history in both queue and brief. An exception never combines otherwise independent
implementation work. Estimates are not timeout overrides. The breakdown itself
executes no task, rewrites no checkpoint and grants no acceptance; checked rows
record subsequent completed acceptance. Preserve obsolete machinery only until
its proven replacement is ready.
