# Core installation coverage handoff

Task queue: [Ordered task queue](Core-Installation-Task-Queue.md).
Next task: **001 — [Qualify optional PAM installation and confinement](Core-Installation-Tasks/001-native-qualification.md)**.

## Purpose and continuation

The 2026-10-16 installation failure exposed an environment gap: many installed
tests used the same desktop baseline, which did not declare LXC's optional PAM
session module. Widen coverage by environment and lifecycle boundary, following
[core installation coverage maintenance](../../tests/README.md#core-installation-and-runtime-compatibility).
This queue owns engineering qualification, not a second customer E2E queue.

Continue on the full development host with **GPT-6.1 Sol High**. Read this master,
the first unchecked brief and its owning contracts; implement and qualify that
task before advancing. Preserve the checked-in changes and existing results.
Keep every coordinator and subagent on **GPT-6.1 Sol**, choosing effort by scope:
Low for read-only monitoring, Medium for settled implementation and coverage
maintenance, and High or above for diagnosis, security, ownership and independent
correctness review. Follow the [delegation contract](../Execution-Plans.md#execution-and-delegation)
for bounded assignments and disjoint write ownership.
The source/installed target where the fix was developed has no VMs. No installed
acceptance for these changes has run there. Do not install the product on the
full development host; the maintained runners install it in registered guests.

```sh
tools/install-coverage --check
tools/install-coverage --tasks 0
```

The dedicated launcher uses the shared ordinary-plan driver, registered VM
selection and resumable checkpoints. Omit `--tasks` to run one task; use `--stop`
to stop at the next safe session boundary. Existing generic-plan checkpoints
remain available under this master's shared namespace.

Follow [execution plans](../Execution-Plans.md), the
[VM mandate](../Mandates/VM-Mandate.MD) and
[approval tools](../Approval-Tools.md). Current targets are `onpc-Ubuntu26.04`
and `onpc-Fedora44`; confirm their registry and accepted preparation on arrival.
Auto baseline refresh is already authorized through the maintained route.
Product installations, including guest installations, must continue through
`make install` and the existing installation recipe.

## Diagnosis and implemented changes

The installed Ubuntu target's two shared session stacks contain
`session optional pam_cgfs.so -c freezer,memory,name=systemd`.
The confinement inventory rejected that native module. Its old diagnostic
formatter hid the rejection behind `reason=unavailable`. This is a confinement
regression introduced by `eb0b7323` (2026-10-12), rather than the later loader
refactor. The failed configuration left the migration exclusion active, which
prevented broker startup. The reported Child App failure coincided with D-Bus
timeouts; no independent crash trace established a separate Child App regression.

Implemented in this checkout:

- Bounded failure diagnostics identify the reason, source line, OS errno or
  command status and closed module/command categories without arbitrary paths,
  arguments or exception text.
- The reviewed [LXC 6.0.6 callbacks](https://github.com/lxc/lxc/blob/v6.0.6/src/lxc/pam/pam_cgfs.c)
  are admitted. They perform native cgroup bookkeeping. Unknown modules and
  controls that skip the final gate still refuse; the MAC policy is unchanged.
- Twenty host composition cases run the real package script, state migration
  and confinement logic together across both backends. They cover minimal and
  optional-module inputs, includes, vendor aliases, local overrides, preserved
  saved policy, repeat configuration, missing/failing native tools, unsafe PAM
  and pending vendor updates. Failures retain exclusion and avoid activation;
  repaired inputs permit normal retry. Native services/policy tools are doubles.
- Ubuntu's prepared dependency inventory now includes `libpam-cgfs`. The existing
  first-configuration history requires its exact active optional rule in both
  shared stacks before installation, after retry and after reboot. A missing or
  altered profile refuses, rather than silently testing a plain baseline.
- Coverage maintenance now requires review of environment variants and helper
  composition. The new support helper and scheduler isolation are documented.

## Local validation and remaining installation limit

The affected host selection contains 2,775 cases. Its initial run passed 2,771;
four existing inactivity tests had stale doubles after an earlier loader-check
addition. Their repair preserves the inactivity/start assertions and adds the
loader ordering assertion. All 930 cases in that module then passed. The other
affected modules passed, including the twenty new composition cases.

```sh
tools/run-tests unit 'tests/unit/test_package_configuration.py' 'tests/unit/test_kiosk_confinement.py' 'tests/unit/test_prepare_vm.py' 'tests/unit/test_system_first_configure.py' 'tests/unit/test_system_runner.py' 'tests/unit/test_support.py' 'tests/unit/test_support_architecture.py' 'tests/unit/test_regression_unit.py' -q
tools/run-tests unit 'tests/unit/test_system_runner.py' -q
```

The four documentation/inventory consistency modules passed all 313 cases.
Generated coverage was refreshed from collection; it records 45 added host
cases without claiming new installed or E2E passes. Markdown links and the
ordinary-plan structural check passed.

`make build` passed after the final product edit, producing DEB and RPM packages.
These results establish host behavior and packaging, not native PAM callbacks,
MAC enforcement or installed customer acceptance. The attempted local
`make install` stopped at `sudo: interactive authentication is required` before
installation; authentication was not retried. The target's successful repair
and post-reboot Child App result still need an administrator's normal installation
and public product verification.

The subsequent failed-kiosk-manager recovery extension remains unqualified on
both guests. On the current development host, both dispatcher UUID pins are
absent, and automatic preparation refuses the missing/invalid private
`TEST_ACCOUNT_PASSWORD` prerequisite. Restore that credential through the
[environment contract](../../tests/integration/Environment.md#shared-vm-configuration),
then use the maintained preparation and qualification routes; no guest ran.

## Coverage audit and remaining work

| Boundary | Existing protection | Remaining installed qualification |
| --- | --- | --- |
| Optional PAM | Parser/control-flow, ownership, include and restoration checks; new real-helper composition | Task 001 executes the new LXC baseline and native open/close/confinement histories on Ubuntu, plus unchanged Fedora qualification. Task 002 adds native plain/optional/local-vendor variants. |
| Failed configuration | OS gates, unsafe paths, migration schema/retry, service failures, backend/trust checks and native first-configuration interruption/retry/reboot | New native input and its safe recovery need task 001; passing helper doubles alone never established composition. |
| Earlier product versions | Maintained `--previous-artifacts` installation/reboot/upgrade path and old-admission retirement checks | Task 003 requires a genuinely older package, meaningful saved state and post-upgrade enforcement. Same-version reinstall is a different result. |
| Live native dependencies | Native version receipts, synthetic executable replacement, retained mappings and reexec checks | Task 004 qualifies an actual distro package maintenance transaction while an owned session is retained; baseline updates before fresh installation do not establish this. |
| Core customer behavior and startup faults | Component/system checks and some complete installed journeys already exist | Daily/grant enforcement, hard/soft transitions, natural lock/recovery, persistence and multi-session cases still have pending obligations in the existing E2E queue. Registered selectors are not passing evidence. |

The last row remains owned by the
[E2E plan and queue](E2E-Execution-Plan.md), source
[scenario inventory](../../tests/e2e/scenarios.json) and
[generated coverage](../Test-Coverage.md). In particular, real customer update
journeys remain in tasks 135a–140, and startup/recovery engineering obligations
remain in tasks 169–179. Preserve their finite assertions and existing order;
this audit neither duplicates nor closes them. These are coverage risks, not
evidence that each corresponding product behavior is broken.

Close each task only with matching target evidence and owned cleanup. Update
the queue and sole next-task pointer; leave blocked or unexecuted tasks unchecked.
