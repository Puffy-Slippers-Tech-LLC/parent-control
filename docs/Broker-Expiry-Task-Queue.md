# Broker expiry automation task queue

[Master and acceptance contract](Broker-Expiry-Plan.md).
Planned parameter names are not executable selectors.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 000a | Use safe desktop sign-in in installed checks | Baseline | Reuse guarded graphical entry and credentials within the installed session owner's existing VM lease | Both target credential checks passed; owned cleanup complete; 26 recovery safety checks passed and independent review found no issues |
| [x] | 001 | Observe secure locking without the panel | 000a | Extend shared lock/input, retained-work and graphical-peer observations; declare finite budgets | Complete system-282 passed on Ubuntu and Fedora; strict timing separated from ample functional budgets without added waits; 27 focused safety checks passed; owned cleanup complete |
| [ ] | 002 | [Check native time without the extension](Broker-Expiry-Tasks/002-native-time.md) | 001 | Independent uninterrupted-use reads and native balance calculations, no alternate ledger | 45–75 min |
| [ ] | 003 | [Check native exhaustion locks](Broker-Expiry-Tasks/003-native-lock.md) | 002 | Daily-only and grant-only extension-disabled native lock results | 45–75 min |
| [ ] | 004 | [Check revocation on the active desktop](Broker-Expiry-Tasks/004-revocation.md) | 001, 002 | Foreground zero-daily lock and positive-daily control without switching away | 45–75 min |
| [ ] | 005 | [Reject outdated expiry work](Broker-Expiry-Tasks/005-ordering.md) | 002 | Deterministic authoritative ordering, cancellation and private-service dispatch assertions | 20–30 min |
| [ ] | 006 | [Keep expiry moving during approval](Broker-Expiry-Tasks/006-live-ordering.md) | 004, 005 | Open authentication challenge across original expiry | 30–60 min |
| [ ] | 006a | [Apply the latest time decision at expiry](Broker-Expiry-Tasks/006a-policy-ordering.md) | 004, 005 | Current authoritative renewal/revocation/policy order at expiry | 30–60 min |
| [ ] | 006b | [Keep old expiry callbacks away from new sessions](Broker-Expiry-Tasks/006b-session-effects.md) | 005 | Current ended-session callback and replacement identity isolation | 30–60 min |
| [ ] | 007 | [Check locking across a broker crash](Broker-Expiry-Tasks/007-crash.md) | 003, 005 | Real broker crash across original expiry, reconstruction and pending effect | 30–60 min |
| [ ] | 008 | [Check locking while the broker is stopped](Broker-Expiry-Tasks/008-stop.md) | 007 | Deliberate service unavailability through expiry and supported recovery | 30–60 min |
| [ ] | 009 | [Check locking while the broker stalls](Broker-Expiry-Tasks/009-stall.md) | 007 | Owned real process stall, useful deadline progress and bounded recovery | 30–60 min |
| [ ] | 010 | [Check expiry after the timer restarts](Broker-Expiry-Tasks/010-owners.md) | 005, 007 | Native timer process replacement across original expiry | 30–60 min |
| [ ] | 010a | [Check expiry after the child bus restarts](Broker-Expiry-Tasks/010a-session-bus.md) | 005, 007 | Real child bus process replacement and expiry recovery | 30–60 min |
| [ ] | 011 | [Require confirmed secure locking](Broker-Expiry-Tasks/011-lock-completion.md) | 001, 005 | Delayed/missing acknowledgement and actual protected input | 30–60 min |
| [ ] | 011a | [Check recovery when locking becomes available](Broker-Expiry-Tasks/011a-lock-provider.md) | 001, 005 | Unavailable lock action and lock-provider replacement on live bus | 30–60 min |
| [ ] | 012 | [State the limits of unavailable secure locking](Broker-Expiry-Tasks/012-lock-outage.md) | 011, 011a | Characterize real lock-service/Shell outage; unsupported results block handover | 30–60 min |
| [ ] | 013 | [Check the handover coverage is complete](Broker-Expiry-Tasks/013-closeout.md) | 003, 004, 006, 006a, 006b, 008, 009, 010, 010a, 012 | Registration and cross-plan residual reconciliation; TA readiness, no migration pass | 20–30 min |

## Scheduling exclusions

The [canonical allocation](TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation)
and master's coverage review retain customer, admission/reader, suspend, startup,
game and reliability owners. No corresponding row is copied here. Completed
unchanged coverage stays done; only changed bindings need affected regressions.
This queue neither advances nor reorders the E2E or reliability queues.
