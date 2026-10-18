# VM reliability task queue

The [master](Reliability-Plan.md) owns the sole next-task pointer and shared
acceptance. Every row includes product root-cause repair when its stated
required behavior fails. Original numeric IDs retain cumulative Scope cells;
their briefs identify the remaining slice after the extracted prerequisites.
Estimates cover that row's remaining implementation, checks, acceptance and
cleanup. Installed estimates include both targets. A session exception keeps an
indivisible history together, with its reason in the brief. No row has been
executed by auditing or splitting this plan.

Recovery within a retry budget and restoration after budget exhaustion are
separate complete histories. Renderer qualification separates the notification
provider from the compositor/request-app pair. Numbered work sequences in longer
briefs break execution into explicit steps; only the complete row earns
acceptance, including both targets and cleanup where declared.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 001a | [Broker usage-query retry budgets](Reliability-Tasks/001a-usage-query-budgets.md) | Baseline | Mixed native-error classifications, attempt limits and overdue helper dispatch | 15–30 min |
| [ ] | 001b | [Child timer-query cancellation](Reliability-Tasks/001b-child-query-cancellation.md) | Baseline | Mixed child-read budgets, cancellation before dispatch and late replies | 15–30 min |
| [ ] | 001c | [Resume lifecycle cancellation](Reliability-Tasks/001c-resume-cancellation.md) | 001a, 001b | Controller query/replay cancellation, inert late callbacks and preserved replay endpoints | 15–30 min |
| [ ] | 001 | [Timer failure ordering and accounting safety](Reliability-Tasks/001-timer-ordering.md) | 001a, 001b, 001c | Missing deterministic mixed-error, cancellation and operation-specific recovery histories | 15–30 min |
| [ ] | 002b | [Native timer contention within budget](Reliability-Tasks/002b-timer-contention-recovery.md) | 001 | Real Busy release and recovery within original budgets with recorded-use and second-child controls | 30–60 min (session exception) |
| [ ] | 002a | [Native timer contention recovery](Reliability-Tasks/002a-timer-contention.md) | 001, 002b | Real Busy recovery and exhaustion with recorded-use and second-child controls | 30–60 min (session exception) |
| [ ] | 002c | [Native timer owner reactivation within budget](Reliability-Tasks/002c-timer-owner-recovery.md) | 001, 002a | Real owner loss and reactivation within original budgets with recorded-use and second-child controls | 30–60 min (session exception) |
| [ ] | 002 | [Installed timer contention and service recovery](Reliability-Tasks/002-timer-service.md) | 001, 002a, 002c | Real Busy/owner-loss recovery and exhaustion through canonical session tests | 30–60 min (session exception) |
| [ ] | 003a | [Daily-only inactivity accounting](Reliability-Tasks/003a-daily-only-resume.md) | 001, 002 | Daily-only active/inactive balance intervals through native exhaustion | 45–75 min (session exception) |
| [ ] | 003 | [Daily accounting across inactivity and delayed resume](Reliability-Tasks/003-daily-resume.md) | 001, 002, 003a | Daily-only and combined native accounting without premature lock or deadline extension | 45–75 min (session exception) |
| [ ] | 004a | [Trusted unlock authority lifetime](Reliability-Tasks/004a-unlock-authority.md) | Baseline | Deterministic trusted-sender, one-use, expiry and cancellation regressions | 15–30 min |
| [ ] | 004 | [Single-authentication retained unlock recovery](Reliability-Tasks/004-retained-unlock.md) | 003, 004a | Natural exhaustion, real approval and one authorized usable return; stale authority refused | 45–75 min (session exception) |
| [ ] | 005a | [Administrative bridge identity boundary](Reliability-Tasks/005a-bridge-identity.md) | Baseline | Positive verified bridge and negative identity/command PAM controls | 15–30 min |
| [ ] | 005 | [Package triggers with exhausted retained users](Reliability-Tasks/005-package-triggers.md) | 004, 005a | Native administrative user-bus access succeeds while ordinary time/admission restrictions remain | 45–75 min (session exception) |
| [ ] | 006a | [Writable sibling masking](Reliability-Tasks/006a-sibling-masking.md) | 005 | Mode-0775/0777 private empty views and retained isolation after host replacement | 30–60 min (session exception) |
| [ ] | 006b | [Required executable ancestor refusal](Reliability-Tasks/006b-required-path-refusal.md) | 005 | Group-writable required ancestor refusal, exact restoration and native recovery | 30–60 min (session exception) |
| [ ] | 006 | [Confinement with heterogeneous filesystem inputs](Reliability-Tasks/006-filesystem-variants.md) | 005, 006a, 006b | Unrelated writable sibling masking plus required-path/alias safe refusals and recovery | 30–60 min (session exception) |
| [ ] | 007a | [Renderer role permission matrix](Reliability-Tasks/007a-renderer-policy.md) | Baseline | Narrow device-mapping grants and every excluded role/permission at host scope | 15–30 min |
| [ ] | 007c | [Native notification-provider isolation](Reliability-Tasks/007c-notification-renderer.md) | 006, 007a | Real notification rendering, provider identity and native enforcing allow/deny controls | 30–60 min (session exception) |
| [ ] | 007b | [Native renderer functions and isolation](Reliability-Tasks/007b-native-renderers.md) | 006, 007a, 007c | Three usable renderer roles and actual enforcing allow/deny scope on both VMs | 30–60 min (session exception) |
| [ ] | 007 | [Native VM renderer roles and crash recovery](Reliability-Tasks/007-renderer-roles.md) | 006, 007a, 007b | Exercised renderer permissions, enforcing isolation and observable crash/reentry | 30–60 min (session exception) |
| [ ] | 008a | [Request readiness and locale retry](Reliability-Tasks/008a-request-readiness.md) | Baseline | Warm-up failure/retry, stale language, supersession and late-callback guards | 15–30 min |
| [ ] | 008b | [Bounded kiosk logout fallback](Reliability-Tasks/008b-logout-lifetime.md) | Baseline | Native exit failure, fallback deadline and owned callback/process lifetime | 15–30 min |
| [ ] | 008 | [Kiosk startup and exit under inventory growth](Reliability-Tasks/008-kiosk-scaling.md) | 006, 007, 008a, 008b | Fixed cold/warm samples, bounded mount/process growth and responsive complete transitions | 60–90 min (session exception) |
| [ ] | 009a | [Preference write durability and retry](Reliability-Tasks/009a-preference-durability.md) | Baseline | Write/replace/directory-flush failures with identical and changed retries | 15–30 min |
| [ ] | 009 | [Durable request-state failure and retry](Reliability-Tasks/009-state-durability.md) | 008, 009a | Real private-filesystem write/flush/replace failures preserve state and permit correct retry | 15–30 min |
| [ ] | 010a | [Diagnostic failure isolation](Reliability-Tasks/010a-diagnostic-isolation.md) | Baseline | Failed diagnostic writes/transports cannot change refresh, lock or cleanup results | 15–30 min |
| [ ] | 010b | [Timer incident export after recovery](Reliability-Tasks/010b-timer-diagnostic-export.md) | 002, 004, 009, 010a | Already-open reporter, later success and fresh sanitized archive retain timer cause | 45–75 min (session exception) |
| [ ] | 010 | [Diagnostics survive failed and recovered components](Reliability-Tasks/010-diagnostic-recovery.md) | 002, 004, 007, 009, 010a, 010b | Original cause/category survives dead reporter, later success and actual sanitized export | 30–60 min (session exception) |
| [ ] | 011a | [Bounded guest workload ownership](Reliability-Tasks/011a-bounded-workload.md) | 008, 010 | Qualified guest resource caps, precise owned identity, interruption and cleanup | 45–75 min (session exception) |
| [ ] | 011 | [Bounded repeated histories under guest load](Reliability-Tasks/011-repeated-history.md) | 003, 004, 005, 008, 010, 011a | Three ordered two-child cycles with intermediate accounting/isolation/resource checks | 60–90 min (session exception) |
| [ ] | 012a | [Unattended reliability coverage registration](Reliability-Tasks/012a-unattended-coverage.md) | 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011 | Executable owner/selector mapping, suite inclusion and resource classifications | 15–30 min |
| [ ] | 012 | [Reconcile final-candidate regression coverage](Reliability-Tasks/012-final-evidence.md) | 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012a | Registered unattended selections, matching evidence and affected final-candidate reruns | 30–90 min (session exception) |
