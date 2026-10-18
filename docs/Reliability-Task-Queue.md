# Real-world reliability task queue

The [master](Reliability-Plan.md) owns the sole next-task pointer and shared
acceptance and the incident-based scope gate. Every active row includes product
root-cause repair when its stated required behavior fails. The audited Scope
cells and briefs supersede earlier cumulative obligations; excluded work below
is outside this plan and receives no acceptance credit.
Estimates cover that row's remaining implementation, checks, acceptance and
cleanup. Installed estimates include both targets. A session exception keeps an
indivisible history together, with its reason in the brief. No row has been
executed by auditing or splitting this plan.

Recovery within a retry budget and restoration after budget exhaustion are
separate complete histories. Renderer qualification targets the startup failure
path; it does not require all native renderer roles. Numbered work sequences in
longer briefs break execution into explicit steps; only the complete row earns
acceptance, including both targets and cleanup where declared.

Host prerequisites further separate child-read retries from query cancellation,
unlock eligibility from authority lifetime, locale-job ordering from Request
composition, and child diagnostic isolation from process-exit/cleanup isolation.
Each consumer names its remaining slice. Independent incident families depend
only on the shared capabilities they actually consume.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 001a | [Broker usage-query retry budgets](Reliability-Tasks/001a-usage-query-budgets.md) | Baseline | Mixed native-error classifications, attempt limits and overdue helper dispatch | 15–30 min |
| [ ] | 001d | [Child estimate-read retry budgets](Reliability-Tasks/001d-child-query-budgets.md) | Baseline | Mixed child estimate-read errors, shared attempt/deadline budgets and terminal categories | 15–30 min |
| [ ] | 001b | [Child timer-query cancellation](Reliability-Tasks/001b-child-query-cancellation.md) | 001d | Mixed child-read budgets, cancellation before dispatch and late replies | 15–30 min |
| [ ] | 001c | [Resume lifecycle cancellation](Reliability-Tasks/001c-resume-cancellation.md) | 001a, 001b | Controller query/replay cancellation, inert late callbacks and preserved replay endpoints | 15–30 min |
| [ ] | 001 | [Timer failure ordering and accounting safety](Reliability-Tasks/001-timer-ordering.md) | 001a, 001b, 001c | Missing deterministic mixed-error, cancellation and operation-specific recovery histories | 15–30 min |
| [ ] | 002b | [Native timer contention within budget](Reliability-Tasks/002b-timer-contention-recovery.md) | 001 | Real Busy release and recovery within original budgets with recorded-use and second-child controls | 30–60 min (session exception) |
| [ ] | 002a | [Native timer contention recovery](Reliability-Tasks/002a-timer-contention.md) | 001, 002b | Real Busy recovery and exhaustion with recorded-use and second-child controls | 30–60 min (session exception) |
| [ ] | 002c | [Native timer owner reactivation within budget](Reliability-Tasks/002c-timer-owner-recovery.md) | 001, 002a | Real owner loss and reactivation within original budgets with recorded-use and second-child controls | 30–60 min (session exception) |
| [ ] | 002 | [Installed timer contention and service recovery](Reliability-Tasks/002-timer-service.md) | 001, 002a, 002c | Real Busy/owner-loss recovery and exhaustion through canonical session tests | 30–60 min (session exception) |
| [ ] | 003a | [Daily-only inactivity accounting](Reliability-Tasks/003a-daily-only-resume.md) | 001 | Daily-only active/inactive balance intervals through native exhaustion | 45–75 min (session exception) |
| [ ] | 003 | [Daily accounting across inactivity and delayed resume](Reliability-Tasks/003-daily-resume.md) | 001, 002, 003a | Daily-only and combined native accounting without premature lock or deadline extension | 45–75 min (session exception) |
| [ ] | 004b | [Trusted unlock sender and eligibility](Reliability-Tasks/004b-unlock-eligibility.md) | Baseline | Trusted sender, parental-lock eligibility and native dispatch admission controls | 15–30 min |
| [ ] | 004a | [Trusted unlock authority lifetime](Reliability-Tasks/004a-unlock-authority.md) | 004b | Deterministic trusted-sender, one-use, expiry and cancellation regressions | 15–30 min |
| [ ] | 004 | [Single-authentication retained unlock recovery](Reliability-Tasks/004-retained-unlock.md) | 004a | Natural exhaustion, real approval and one authorized usable return; stale authority refused | 45–75 min (session exception) |
| [ ] | 005a | [Administrative bridge identity boundary](Reliability-Tasks/005a-bridge-identity.md) | Baseline | Positive verified bridge and negative identity/command PAM controls | 15–30 min |
| [ ] | 005 | [Package triggers with exhausted retained users](Reliability-Tasks/005-package-triggers.md) | 004, 005a | Native administrative user-bus access succeeds while ordinary time/admission restrictions remain | 45–75 min (session exception) |
| [ ] | 006a | [Writable sibling masking](Reliability-Tasks/006a-sibling-masking.md) | Baseline | Mode-0775/0777 private empty views and retained isolation after host replacement | 30–60 min (session exception) |
| [ ] | 006b | [Required executable ancestor refusal](Reliability-Tasks/006b-required-path-refusal.md) | Baseline | Safety control for sibling masking: required ancestor refusal, restoration and native recovery | 30–60 min (session exception) |
| [ ] | 007a | [Renderer mapping permission regression](Reliability-Tasks/007a-renderer-policy.md) | Baseline | Changed dri_device_t mapping grant and unchanged exclusions/transitions at host scope | 15–30 min |
| [ ] | 007b | [Native renderer startup regression](Reliability-Tasks/007b-native-renderers.md) | 007a | Usable enforcing kiosk startup on the incident renderer path with exact device-mapping evidence | 30–60 min (session exception) |
| [ ] | 007 | [Renderer crash and kiosk reentry](Reliability-Tasks/007-renderer-roles.md) | 007a | Owned abnormal app exit, bounded usable GDM return and fresh confined entry | 30–60 min (session exception) |
| [ ] | 008c | [Agent-locale job failure and ordering](Reliability-Tasks/008c-agent-locale-jobs.md) | Baseline | Locale restart/job correlation, failure/retry, queued preparations and callback cleanup | 15–30 min |
| [ ] | 008a | [Request readiness and locale retry](Reliability-Tasks/008a-request-readiness.md) | 008c | Warm-up failure/retry, stale language, supersession and late-callback guards | 15–30 min |
| [ ] | 008b | [Bounded kiosk logout fallback](Reliability-Tasks/008b-logout-lifetime.md) | Baseline | Native exit failure, fallback deadline and owned callback/process lifetime | 15–30 min |
| [ ] | 008 | [Kiosk reliability with enlarged inventory](Reliability-Tasks/008-kiosk-scaling.md) | 008a, 008b | One ordinary and two enlarged-inventory entry/Request/Cancel cycles within existing deadlines and resource bounds | 30–60 min (session exception) |
| [ ] | 009a | [Preference write durability and retry](Reliability-Tasks/009a-preference-durability.md) | Baseline | Write/replace/directory-flush failures with identical and changed retries | 15–30 min |
| [ ] | 009 | [Durable request-state failure and retry](Reliability-Tasks/009-state-durability.md) | 009a | Selector malformed/unwritable fallback followed by reopened normal persistence; preference durability from 009a | 15–30 min |
| [ ] | 010c | [Child diagnostic failure isolation](Reliability-Tasks/010c-child-diagnostic-isolation.md) | Baseline | Failed diagnostic writes/transports preserve child refresh/lock results and callback ownership | 15–30 min |
| [ ] | 010a | [Diagnostic failure isolation](Reliability-Tasks/010a-diagnostic-isolation.md) | 010c | Failed diagnostic writes/transports cannot change refresh, lock or cleanup results | 15–30 min |
| [ ] | 010b | [Timer incident export after recovery](Reliability-Tasks/010b-timer-diagnostic-export.md) | 002, 010a | Already-open reporter, later success and fresh sanitized archive retain timer cause | 45–75 min (session exception) |
| [ ] | 010 | [Diagnostics survive failed and recovered components](Reliability-Tasks/010-diagnostic-recovery.md) | 007, 010a, 010b | Original cause/category survives dead reporter, later success and actual sanitized export | 30–60 min (session exception) |
| [ ] | 011 | [Repeated retained-session recovery](Reliability-Tasks/011-repeated-history.md) | 003a, 004 | Two exhaustion/approval/single-authentication returns without state reset, preserving accounting, work and owned resources | 45–75 min (session exception) |
| [ ] | 012a | [Unattended reliability coverage registration](Reliability-Tasks/012a-unattended-coverage.md) | 001, 002, 003, 004, 005, 006a, 006b, 007a, 007b, 007, 008, 009, 010, 011 | Incident/lesson/condition/selector mapping, suite inclusion and resource classifications | 15–30 min |
| [ ] | 012 | [Reconcile final-candidate regression coverage](Reliability-Tasks/012-final-evidence.md) | 001, 002, 003, 004, 005, 006a, 006b, 007a, 007b, 007, 008, 009, 010, 011, 012a | Active incident regressions, matching proof and affected final-candidate reruns; no release-wide acceptance | 30–90 min (session exception) |

## Scheduling exclusions

These unfinished tasks were removed by the scope audit, not executed or passed.
Their former briefs are removed so they cannot reintroduce superseded scope.
Existing regressions and uncovered requirements remain with their owners.

| Removed ID | Cut from this plan | Existing owner or return condition |
| --- | --- | --- |
| 006 | Standalone native pinned-alias mismatch/refusal qualification beyond the writable-sibling incident | [Confinement design and proofs](SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits); retain existing alias/trusted-package-change tests. Add reliability work only if a demonstrated incident requires another condition. |
| 007c | Standalone notification rendering and native all-resource isolation qualification | [Renderer role contract](SystemDesign/Kiosk-Confinement.md#roles-services-and-dialogs) and existing notification qualification. Task 007a still preserves the changed mapping permission's role exclusions. |
| 011a | New synthetic CPU/disk workload and native cap/interruption qualification | No workload capability is needed by revised 011. Any future demonstrated load-related defect needs its own bounded proposal through [shared support](../tests/support/README.md). |
