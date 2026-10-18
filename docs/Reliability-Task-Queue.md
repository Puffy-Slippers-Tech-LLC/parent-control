# VM reliability task queue

The [master](Reliability-Plan.md) owns the sole next-task pointer and shared
acceptance. Every row includes product root-cause repair when its stated
required behavior fails. Estimates cover bounded implementation/qualification;
indivisible installed histories may span coordinator sessions without lowering
acceptance. No row has been executed by creating this plan.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 001 | [Timer failure ordering and accounting safety](Reliability-Tasks/001-timer-ordering.md) | Baseline | Missing deterministic mixed-error, cancellation and operation-specific recovery histories | 30–45 min |
| [ ] | 002 | [Installed timer contention and service recovery](Reliability-Tasks/002-timer-service.md) | 001 | Real Busy/owner-loss recovery and exhaustion through canonical session tests | 45–60 min |
| [ ] | 003 | [Daily accounting across inactivity and delayed resume](Reliability-Tasks/003-daily-resume.md) | 001, 002 | Daily-only and combined native accounting without premature lock or deadline extension | 45–60 min |
| [ ] | 004 | [Single-authentication retained unlock recovery](Reliability-Tasks/004-retained-unlock.md) | 003 | Natural exhaustion, real approval and one authorized usable return; stale authority refused | 45–60 min |
| [ ] | 005 | [Package triggers with exhausted retained users](Reliability-Tasks/005-package-triggers.md) | 004 | Native administrative user-bus access succeeds while ordinary time/admission restrictions remain | 40–60 min |
| [ ] | 006 | [Confinement with heterogeneous filesystem inputs](Reliability-Tasks/006-filesystem-variants.md) | 005 | Unrelated writable sibling masking plus required-path/alias safe refusals and recovery | 40–60 min |
| [ ] | 007 | [Native VM renderer roles and crash recovery](Reliability-Tasks/007-renderer-roles.md) | 006 | Exercised renderer permissions, enforcing isolation and observable crash/reentry | 40–60 min |
| [ ] | 008 | [Kiosk startup and exit under inventory growth](Reliability-Tasks/008-kiosk-scaling.md) | 006, 007 | Fixed cold/warm samples, bounded mount/process growth and responsive complete transitions | 40–60 min |
| [ ] | 009 | [Durable request-state failure and retry](Reliability-Tasks/009-state-durability.md) | 008 | Real private-filesystem write/flush/replace failures preserve state and permit correct retry | 30–45 min |
| [ ] | 010 | [Diagnostics survive failed and recovered components](Reliability-Tasks/010-diagnostic-recovery.md) | 002, 004, 007, 009 | Original cause/category survives dead reporter, later success and actual sanitized export | 40–60 min |
| [ ] | 011 | [Bounded repeated histories under guest load](Reliability-Tasks/011-repeated-history.md) | 003, 004, 005, 008, 010 | Three ordered two-child cycles with intermediate accounting/isolation/resource checks | 45–60 min |
| [ ] | 012 | [Reconcile final-candidate regression coverage](Reliability-Tasks/012-final-evidence.md) | 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011 | Registered unattended selections, matching evidence and affected final-candidate reruns | 30–45 min |
