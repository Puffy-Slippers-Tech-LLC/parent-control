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
| [x] | U03a | Restore entry after stale owned admission state | U03 | Supported repair of one proven owned stale lock/barrier state | Existing same-inode 0640-to-0600 repair passed on both targets, with genuine approval/time/reentry and cleanup; 9 focused host checks passed. No product change needed. |
| [x] | U04 | Recover entry after a temporary identity-check failure | U03a | One transient helper/NSS failure and its recovery without bypassing account authority | Both targets passed helper failure/restoration, ordinary login, genuine approval/time/reentry and cleanup; 50 host checks/source passed; review found no issues. No product change needed. |
| [x] | U05 | Restore entry after interrupted configuration | U04 | One owned interruption while quarantined, supported retry and usable passwordless reentry | Both targets passed interruption/retry, genuine approval/time readback, reentry and cleanup; no product change needed. Ubuntu's expected injected-failure notice is handled narrowly; temporary diagnostics removed. |
| [x] | U06 | Keep entry working after a relevant update | U05 | One supported update touching changed kiosk integration, with correct activation and fresh entry | Both targets passed genuine prior-release update, activation, approval/time readback, reentry and cleanup; shared test binding repaired, focused host/source checks passed. No product change needed. |
| [ ] | U07 | [Recover requests after a temporary service outage](Kiosk-Usability-Tasks/U07-service-recovery.md) | U06 | One broker outage, safe unavailable state and recovery without repeating approval | 45–90 min (exception) |
| [ ] | U08 | [Keep requests usable when presentation resources fail](Kiosk-Usability-Tasks/U08-optional-presentation.md) | U07 | One demonstrated optional presentation dependency cannot veto entry or approval | 45–90 min (exception) |
| [ ] | U09 | [Close the scoped usability repairs](Kiosk-Usability-Tasks/U09-closeout.md) | U08 | Reconcile delivered fixes and remaining limits without a general acceptance rerun | 15–30 min |

Use the shared completion policy: short results and normal failure diagnostics
are enough. No automatic report archive, historical-proof renewal or cross-queue
completion. A fixed fault receives its affected checks within its row; an
already working condition needs no speculative implementation.
