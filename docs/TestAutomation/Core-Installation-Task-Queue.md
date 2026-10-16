# Core installation engineering task queue

The [master handoff](Core-Installation-Coverage-Handoff.md) owns the next-task
pointer. All rows are unfinished installed work; host passes do not close them.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 001 | [Qualify optional PAM installation and confinement](Core-Installation-Tasks/001-native-qualification.md) | Baseline | New Ubuntu optional profile; first-configuration interruption/retry/reboot and native confinement on both supported targets | 45–75 min |
| [ ] | 002 | [Exercise native PAM environment variants](Core-Installation-Tasks/002-pam-variants.md) | 001 | Finite plain/optional/vendor-local variants with preservation and safe refusal/retry through native installation | 60–90 min |
| [ ] | 003 | [Qualify a real earlier-package upgrade](Core-Installation-Tasks/003-previous-package-upgrade.md) | 002 | Earlier package plus saved policy and retained admission state through update/reboot and enforcement | 60–90 min |
| [ ] | 004 | [Qualify native dependency updates during retained sessions](Core-Installation-Tasks/004-native-dependency-update.md) | 003 | Actual native package transaction, retained generation, loader/reexec safety and fresh-session recovery | 60–90 min |

Customer E2E implementation and pending startup engineering obligations stay in
their [existing queue](E2E-Task-Queue.md). Do not infer completion there from this
queue's engineering evidence.
