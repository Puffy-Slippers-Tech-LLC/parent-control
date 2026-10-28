# Kiosk usability repair queue

The [master](Kiosk-Usability-Plan.md) owns scope and bounded acceptance.
Order is authoritative. Each row repairs or verifies only its stated fault;
planning and source review alone do not close installed tasks. Estimates cover
one implementation/validation assignment and may use shared continuations.
Installed estimates marked exception retain the complete two-target history
under the master's [sizing boundary](Kiosk-Usability-Plan.md#task-sizing).

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | U01 | Keep approval working with only basic locales | Baseline | Safe native authentication fallback with C/C.UTF-8-only locales | Both targets passed with cleanup; 382 host checks, source/build passed; independent review found no issues. |
| [x] | U01a | Keep approval working when locale discovery fails | U01 | Failed locale discovery falls back without blocking genuine approval | Both targets passed failure/recovery and cleanup; 166 host checks, source/build passed; review finding in fault setup fixed. |
| [x] | U02 | Keep healthy children able to request time | U01a | One unavailable child's extension cannot stop healthy-child kiosk use | Both targets passed isolation, genuine requests, restoration and cleanup; scoped regressions/source/build passed; independent review found no issues. |
| [x] | U03 | Allow entry after brief admission contention | U02 | Bounded handling of transient writer contention without admitting during maintenance | Both targets passed contention, approval/reentry and cleanup; 153 host checks, source/build passed; independent review found no issues. |
| [ ] | U03a | [Restore entry after stale owned admission state](Kiosk-Usability-Tasks/U03a-stale-admission.md) | U03 | Supported repair of one proven owned stale lock/barrier state | 30–60 min (exception) |
| [ ] | U04 | [Recover entry after a temporary identity-check failure](Kiosk-Usability-Tasks/U04-identity-helper.md) | U03a | One transient helper/NSS failure and its recovery without bypassing account authority | 45–90 min (exception) |
| [ ] | U05 | [Restore entry after interrupted configuration](Kiosk-Usability-Tasks/U05-configuration-recovery.md) | U04 | One owned interruption while quarantined, supported retry and usable passwordless reentry | 45–90 min (exception) |
| [ ] | U06 | [Keep entry working after a relevant update](Kiosk-Usability-Tasks/U06-update-reentry.md) | U05 | One supported update touching changed kiosk integration, with correct activation and fresh entry | 45–90 min (exception) |
| [ ] | U07 | [Recover requests after a temporary service outage](Kiosk-Usability-Tasks/U07-service-recovery.md) | U06 | One broker outage, safe unavailable state and recovery without repeating approval | 45–90 min (exception) |
| [ ] | U08 | [Keep requests usable when presentation resources fail](Kiosk-Usability-Tasks/U08-optional-presentation.md) | U07 | One demonstrated optional presentation dependency cannot veto entry or approval | 45–90 min (exception) |
| [ ] | U09 | [Close the scoped usability repairs](Kiosk-Usability-Tasks/U09-closeout.md) | U08 | Reconcile delivered fixes and remaining limits without a general acceptance rerun | 15–30 min |

Use the shared completion policy: short results and normal failure diagnostics
are enough. No automatic report archive, historical-proof renewal or cross-queue
completion. A fixed fault receives its affected checks within its row; an
already working condition needs no speculative implementation.
