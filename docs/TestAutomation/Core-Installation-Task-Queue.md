# Core installation engineering task queue

The [master handoff](Core-Installation-Coverage-Handoff.md) owns the next-task
pointer. Unchecked rows require installed work; host passes do not close them.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | [Qualify optional PAM installation and confinement](Core-Installation-Coverage-Handoff.md#task-001-native-qualification) | Baseline | New Ubuntu optional profile; first-configuration interruption/retry/reboot and native confinement on both supported targets | Accepted 2026-10-17: 3/3 executions per target; 888 host checks; restored/off |
| [x] | 002 | [Exercise native PAM environment variants](Core-Installation-Coverage-Handoff.md#task-002-native-pam-variants) | 001 | Finite plain/optional/vendor-local variants with preservation and safe refusal/retry through native installation | Accepted 2026-10-17: 16/16 phases per target; 3,133 host checks; restored/off |
| [ ] | 002a | [Prepare trusted native upgrade fixtures](Core-Installation-Tasks/002a-trusted-native-upgrade-fixtures.md) | 002 | Baseline-owned trusted native witnesses alongside existing untrusted fixtures; prior-release per-user execution controls on both targets | 30–60 min; one shared fixture/preparation change with two native qualifications |
| [ ] | 003 | [Qualify a real earlier-package upgrade](Core-Installation-Tasks/003-previous-package-upgrade.md) | 002 | Earlier package plus saved policy and retained admission state through update/reboot and enforcement | 60–90 min after 002a; retained work and input diagnosis in master; no completion credit |
| [ ] | 004 | [Qualify native dependency updates during retained sessions](Core-Installation-Tasks/004-native-dependency-update.md) | 003 | Actual native package transaction, retained generation, loader/reexec safety and fresh-session recovery | 60–90 min |

Customer E2E implementation and pending startup engineering obligations stay in
their [existing queue](E2E-Task-Queue.md). Do not infer completion there from this
queue's engineering evidence.
