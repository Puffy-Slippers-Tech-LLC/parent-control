# Core installation engineering task queue

The [master handoff](Core-Installation-Coverage-Handoff.md) owns the next-task
pointer. Each brief declares its acceptance kind. Host/review prerequisites do
not close installed qualification; 003 and 004 retain their original scope and
both-target acceptance gates. IDs are stable labels, not sort keys.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | [Qualify optional PAM installation and confinement](Core-Installation-Coverage-Handoff.md#task-001-native-qualification) | Baseline | New Ubuntu optional profile; first-configuration interruption/retry/reboot and native confinement on both supported targets | Accepted 2026-10-17: 3/3 executions per target; 888 host checks; restored/off |
| [x] | 002 | [Exercise native PAM environment variants](Core-Installation-Coverage-Handoff.md#task-002-native-pam-variants) | 001 | Finite plain/optional/vendor-local variants with preservation and safe refusal/retry through native installation | Accepted 2026-10-17: 16/16 phases per target; 3,133 host checks; restored/off |
| [x] | 002a | [Prepare trusted native upgrade fixtures](Core-Installation-Coverage-Handoff.md#task-002a-trusted-native-fixture-qualification) | 002 | Baseline-owned trusted native witnesses alongside existing untrusted fixtures; prior-release per-user execution controls on both targets | Accepted 2026-10-17: 1/1 execution per target, no skips; 3,272 affected host checks plus 624 final guards; restored/off |
| [x] | 002b | [Integrate qualified fixtures into case 287](Core-Installation-Coverage-Handoff.md#task-002b-qualified-fixture-integration) | 002a | Select trusted hard/soft witnesses consistently in upgrade setup, policy and enforcement; host regressions | Accepted 2026-10-18: 1,391 affected host checks plus 408 final consumer/document/plan guards; cleanup complete |
| [ ] | 002c | [Run the complete Ubuntu upgrade history](Core-Installation-Tasks/002c-ubuntu-upgrade-history.md) | 002b | Case 287 on Ubuntu with final qualified inputs; all three phases and cleanup | 30–45 min; indivisible update/reboot history |
| [ ] | 002d | [Run the complete Fedora upgrade history](Core-Installation-Tasks/002d-fedora-upgrade-history.md) | 002b, 002c | Case 287 on Fedora with final qualified inputs; all three phases and cleanup | 30–45 min; indivisible update/reboot history |
| [ ] | 003 | [Qualify a real earlier-package upgrade](Core-Installation-Tasks/003-previous-package-upgrade.md) | 002, 002a, 002b, 002c, 002d | Earlier package plus saved policy and retained admission state through update/reboot and enforcement | 10–15 min acceptance reconciliation after complete target histories; rerun invalidated slices only |
| [ ] | 004a | [Select finite native dependency package pairs](Core-Installation-Tasks/004a-native-package-pairs.md) | 003 | Establish supported old/new packages and exact retained-generation expectations per target before implementing staging | 20–30 min; missing pair remains a blocker |
| [ ] | 004b | [Implement verified native transaction inputs](Core-Installation-Tasks/004b-native-transaction-inputs.md) | 004a | Maintained preparation/staging, provenance, baseline verification and ownership for the selected finite pairs | 20–30 min |
| [ ] | 004c | [Implement the retained-session transaction history](Core-Installation-Tasks/004c-native-update-history.md) | 004b | Register one complete history with native transaction, generation/refusal/recovery assertions and host regressions | 20–30 min |
| [ ] | 004d | [Qualify the Ubuntu native update history](Core-Installation-Tasks/004d-ubuntu-native-update.md) | 004c | Complete retained-session native package transaction and recovery on Ubuntu, with owned cleanup | 30–45 min; indivisible transaction/recovery history |
| [ ] | 004e | [Qualify the Fedora native update history](Core-Installation-Tasks/004e-fedora-native-update.md) | 004c, 004d | Complete retained-session native package transaction and recovery on Fedora, with owned cleanup | 30–45 min; indivisible transaction/recovery history |
| [ ] | 004 | [Qualify native dependency updates during retained sessions](Core-Installation-Tasks/004-native-dependency-update.md) | 003, 004a, 004b, 004c, 004d, 004e | Actual native package transaction, retained generation, loader/reexec safety and fresh-session recovery | 10–15 min acceptance reconciliation after complete target histories; rerun invalidated slices only |

Customer E2E implementation and pending startup engineering obligations stay in
their [existing queue](E2E-Task-Queue.md). Do not infer completion there from this
queue's engineering evidence.
