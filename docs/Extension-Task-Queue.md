# Extension recovery task queue

The [master](Extension-Plan.md) owns scope, reuse and the sole next-task pointer.
These are system engineering tests, not customer E2E cases.
The new monitor checks are the top to-dos. Table order is execution order;
IDs are stable labels. Unchecked rows remain unqualified on VMs.

Estimates include implementation, both installed targets and owned cleanup.
The complete fault/restoration history stays together; each brief explains its
session exception. Reuse existing system 281/282 assertions rather than adding
duplicate selectors or rerunning unrelated expiry histories.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | Keep parental control active when extensions are disabled | Baseline | Individual/global recovery, repeated disablement beyond the old attempt limit, bounded rate and policy/role isolation | System 295 passed Ubuntu26.04/Fedora44; cleanup done. Retry cleanup, pending ownership and error reporting fixed; Astra re-review clear. |
| [x] | 002 | Keep recovery safe across session and broker changes | 001 | Real user-bus/Shell replacement, ordinary logout, lock contention and owned shutdown | System 296 passed Ubuntu26.04/Fedora44; cleanup done. False startup reports fixed; Astra review clear. |
| [ ] | 003 | [Report extension failures without a crash loop](Extension-Tasks/003-error-reporting.md) | 001, 002 | Actual extension error, one standard report, no automatic send and conservative crash protection | 30–60 min (session exception) |
| [ ] | 004 | [Restore the extension after startup and reboot](Extension-Tasks/004-startup-recovery.md) | 001 | v1.5 broker startup, offline persistence, cold boot and startup failure/isolation deltas | 30–60 min (session exception) |
| [ ] | 005 | [Restore the extension from Parent controls](Extension-Tasks/005-parent-recovery.md) | 001 | v1.5 initial Parent selection, later child changes and first enablement | 30–60 min (session exception) |
| [ ] | 006 | [Restore the extension when kiosk time is approved](Extension-Tasks/006-kiosk-recovery.md) | 001 | v1.5 genuine kiosk approval, verified activation and original transaction/other-child effects | 30–60 min (session exception) |
| [ ] | 007 | [Restore the extension when a child signs in or unlocks](Extension-Tasks/007-login-unlock-recovery.md) | 004 | v1.5 actual GDM login/unlock recovery with positive native time and unchanged grants/policy | 30–60 min (session exception) |
