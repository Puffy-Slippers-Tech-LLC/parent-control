# Core installation engineering task queue

The [master handoff](Core-Installation-Coverage-Handoff.md) owns the next-task
pointer. Each brief declares its acceptance kind. Host/review prerequisites do
not close installed qualification; 003 and 004 retain their original scope and
both-target acceptance gates. IDs are stable labels, not sort keys.

Shared qualification tasks run independent Ubuntu/Fedora histories in parallel
within the registry concurrency cap. Keep VM-specific prerequisites separate
only for evidenced issues unique to that target; neither distro's routine
qualification depends on the other's result.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | [Qualify optional PAM installation and confinement](Core-Installation-Coverage-Handoff.md#task-001-native-qualification) | Baseline | New Ubuntu optional profile; first-configuration interruption/retry/reboot and native confinement on both supported targets | Accepted 2026-10-17: 3/3 executions per target; 888 host checks; restored/off |
| [x] | 002 | [Exercise native PAM environment variants](Core-Installation-Coverage-Handoff.md#task-002-native-pam-variants) | 001 | Finite plain/optional/vendor-local variants with preservation and safe refusal/retry through native installation | Accepted 2026-10-17: 16/16 phases per target; 3,133 host checks; restored/off |
| [x] | 002a | [Prepare trusted native upgrade fixtures](Core-Installation-Coverage-Handoff.md#task-002a-trusted-native-fixture-qualification) | 002 | Baseline-owned trusted native witnesses alongside existing untrusted fixtures; prior-release per-user execution controls on both targets | Accepted 2026-10-17: 1/1 execution per target, no skips; 3,272 affected host checks plus 624 final guards; restored/off |
| [x] | 002b | [Integrate qualified fixtures into case 287](Core-Installation-Coverage-Handoff.md#task-002b-qualified-fixture-integration) | 002a | Select trusted hard/soft witnesses consistently in upgrade setup, policy and enforcement; host regressions | Accepted 2026-10-18: 1,391 affected host checks plus 408 final consumer/document/plan guards; cleanup complete |
| [x] | 002c | [Run the complete Ubuntu and Fedora upgrade histories](Core-Installation-Coverage-Handoff.md#task-002c-complete-upgrade-histories) | 002b | Case 287 on both targets in parallel with final qualified inputs; all three phases and per-target cleanup | Accepted 2026-10-18: 3/3 phases per target, no skips; reports 20261018T190013Z-06fb3398 / 480dd9e4; restored/off and recording complete; 6.7 min parallel live run |
| [x] | 003 | [Qualify a real earlier-package upgrade](Core-Installation-Coverage-Handoff.md#task-003-final-upgrade-acceptance) | 002, 002a, 002b, 002c | Earlier package plus saved policy and retained admission state through update/reboot and enforcement | Accepted 2026-10-18: matching 002c installed histories, 3/3 phases per target; 788-file bundle verified; 1,027 focused + 551 final host checks; cleanup complete, restored/off |
| [x] | 004a | [Select finite native dependency package pairs](Core-Installation-Coverage-Handoff.md#task-004a-finite-native-input-review) | 003 | Establish supported old/new packages and exact retained-generation expectations per target before implementing staging | Accepted 2026-10-18: Ubuntu bubblewrap/Fedora xdg-dbus-proxy finite input review; 551 host checks and 52 links passed; cleanup complete |
| [x] | 004b | [Implement verified native transaction inputs](Core-Installation-Coverage-Handoff.md#task-004b-verified-native-transaction-inputs) | 004a | Maintained preparation/staging, provenance, baseline verification and ownership for the selected finite pairs | Accepted 2026-10-18: both real native bundles verified; 3,813 host checks plus 1,012 final composition checks passed; cleanup complete |
| [ ] | 004c | [Implement the retained-session transaction history](Core-Installation-Tasks/004c-native-update-history.md) | 004b | Register one complete history with native transaction, generation/refusal/recovery assertions and host regressions | 20–30 min |
| [ ] | 004d | [Qualify the Ubuntu and Fedora native update histories](Core-Installation-Tasks/004d-native-update-histories.md) | 004c | Complete retained-session native package transaction and recovery on both targets in parallel, with per-target cleanup | 30–45 min at concurrency 2; each transaction/recovery history indivisible |
| [ ] | 004 | [Qualify native dependency updates during retained sessions](Core-Installation-Tasks/004-native-dependency-update.md) | 003, 004a, 004b, 004c, 004d | Actual native package transaction, retained generation, loader/reexec safety and fresh-session recovery | 10–15 min acceptance reconciliation after complete target histories; rerun invalidated slices only |

Customer E2E implementation and pending startup engineering obligations stay in
their [existing queue](E2E-Task-Queue.md). Do not infer completion there from this
queue's engineering evidence.
