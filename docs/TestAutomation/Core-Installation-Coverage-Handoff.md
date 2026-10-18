# Core installation coverage handoff

Task queue: [Ordered task queue](Core-Installation-Task-Queue.md).
Next task: **002a — [Prepare trusted native upgrade fixtures](Core-Installation-Tasks/002a-trusted-native-upgrade-fixtures.md)**.

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

The original handoff also lacked dispatcher UUID pins and a valid private
preparation credential. Task 001 found both registered guests' accepted baselines
and pins ready; no manual setup or baseline refresh was needed. The
failed-kiosk-manager recovery extension and optional PAM input now have the
installed qualification recorded below.

## Task 001 native qualification

Accepted on 2026-10-17 (local time; report keys use UTC). Existing system case 4
passed its complete interruption/retry/reboot history, and existing case 267
passed its complete native confinement/refusal/recovery matrix on each target:
three executions per target, with no skips. The optional-module witnesses extend
these existing cases and their shared lifecycle helper; no VM case IDs or
duplicate suite were added.

Reports are under `output/test-runs/host/reports/`; allocations are under
`output/test-runs/privileged/allocations/`. Each allocation retains
`evidence/result.json`, aggregate XML/TAP, phase JUnits in `guest-results/` and
the exact `input/selected-inputs.json`.

| Target | Case 4 report / allocation | Case 267 report / allocation |
| --- | --- | --- |
| onpc-Ubuntu26.04 | `20261018T001146Z-fde699d8` / `onpc-system-0rmz4ma1` | `20261018T001931Z-c3d8d88c` / `onpc-system-cv2leej1` |
| onpc-Fedora44 | `20261018T001146Z-106f25a9` / `onpc-system-7xlr0x4n` | `20261018T001931Z-3ecc56f3` / `onpc-system-c1_shzyu` |

Ubuntu's JUnits retain the exact optional rule witness for both shared stacks
before installation, after retry and after reboot. Both histories observe the
loaded native `pam_cgfs.so` executable mapping, device/inode and SHA-256
`64a95f99a8479f4cc682359b12ff1523826c795367cb18799bfeb55270559cce`.
Native package receipts identify `libpam-cgfs` / LXC `1:6.0.6-1ubuntu1`, PAM
`1.7.0-5ubuntu3.2` and systemd `259.5-0ubuntu3.4`; Fedora records PAM
`0:1.7.2-2.fc44` and systemd `0:259.9-1.fc44` without adding LXC.
Both targets record successful credential/open/close/end histories with retained
post-parent-exit execution denials, quarantine and ordinary-account controls.
Both also record the failed manager reset, exclusion from native trigger
enumeration and successful kiosk-scoped wildcard reload.

Both selections used package source revision
`f0e4dc777f005c611f9dce483f2334edc4592440`, package-source digest
`46dac56e89526e0b9e33675716e7d417567e4f0618a9dac61a7ec08f1262689b`,
DEB SHA-256 `80fe01b91186386ce7300dae84a1816a753c3bbd6eac4d0bf20b1740b6553814`
and RPM SHA-256 `24146667fcff2e5370e43640e6bc322a4e70cf8125e412bafdd2d69a2e8f2ab8`.
Selected-input digests are
`b4e3f81f5aacccbeeb3c6e998e869b4d73256bb89fbaa737c757ef95ebad548f`
for case 4 and
`4c05f166efecf5a0166c329c3c45dab6c0195289bd39c82b6a97f6b227b1b514`
for case 267. Their staged helper hashes bind the task 001 qualification source,
including the optional-module witness. Ubuntu baseline provenance is
`ef0a47e0adc15973ae840c483d5227fa1dd9ba149a28dd9bea0778d78a52a4c9`;
Fedora's is `773a764c5f2173e481aa23adefb37f80d13031cecf1117b7f1741e78b6a343c5`.

All four results report product, infrastructure, collection and cleanup passed,
`cleanup_phase=complete` and independently verified baseline restoration. Final
public status probes confirm both VMs powered off. Focused host regressions for
confinement, first configuration and preparation passed 888/888 in report
`20261018T001217Z-68d58f0f`. The inherited witness changes use existing private
fixtures and owned-process mechanics; their host resource isolation is unchanged.
No product/build input changed during this qualification, so no additional
`make build` was required. Earlier interrupted attempts retain their failed
history and supply no acceptance credit.

## Task 002 native PAM variants

Accepted on 2026-10-17 (local time). Registered system cases **283–286** implement
`test_pam_environment_installation_variants`: plain, distro profile,
administrator override and pending vendor replacement. Each independent baseline
history passed installation, reboot/reconfiguration, configured reboot with
native enforcement/removal, and removal reboot: **16/16 phases per target, no
skips**. No snapshot was restored within a history. Phase JUnits and collected
logs survive each reboot; pre-reboot copies remain in each attempt's
`phase-results/` directory.

Ubuntu's plain input identifies the installed `libpam-cgfs` profile (`cgfs`)
through the native package inventory and disables only its exact optional rule;
all other active security rules remain unchanged. The other Ubuntu variants
retain the reviewed active LXC rule. Fedora's plain input retains its native
`local` profile; its distro-profile input selects the shipped `sssd` profile,
preserves baseline features and required modules, then restores the original
selection and native rules. Both targets prove ordinary-account preservation,
safe kiosk admission, native execution denials and exact saved-policy retention.
Both restore the pre-existing local `systemd-user` override's exact bytes,
ownership, mode and xattrs without changing its vendor source. Pending
`.dpkg-dist`/`.rpmnew` candidates produce the exact native refusal, retain policy,
quarantine and activation exclusion, and permit normal retry after only the
unchanged test-owned candidate is removed.

Reports are under `output/test-runs/host/reports/`; allocations are under
`output/test-runs/privileged/allocations/`.

| Target | Plain: 4 phases, report / allocation | Remaining three variants: 12 phases, report / allocation |
| --- | --- | --- |
| onpc-Ubuntu26.04 | `20261018T003711Z-a6793b00` / `onpc-system-5c_04nnh` | `20261018T004816Z-f29c9233` / `onpc-system-paou8iqc` |
| onpc-Fedora44 | `20261018T003711Z-b15b31e1` / `onpc-system-8z3xgyz4` | `20261018T004816Z-deac6afc` / `onpc-system-m096r55m` |

Plain acceptance is the completed `attempt-pam-plain/guest-results/result.json`
and its four passing JUnits in each earlier allocation. Those overall runs keep
their failed/interrupted status; their unfinished histories receive no credit.
The maintained resume preserved the completed plain histories and ran the other
twelve phases on each target. All staged files except `system_pam_variants.py`
are identical between those inputs; that helper's only later changes add the
Fedora SSSD preparation/restoration branch, which plain never executes. Its
accepted plain path is unchanged. The final staged helper matches the checkout
exactly. No unfinished history was spliced across attempts.

The plain selected-input digest is
`fc2bd81131ede5cbbc7a569fdcc3d2c2c9ee084c682b8ac93fb0e8411c4bcf2b`;
the resumed selection's digest is
`895209516c3b7d76485ced4b15758e4ac7bfba2e4c39bc6271998d04851413d3`.
Their helper SHA-256 values are respectively
`1d7d13243848cf9575fcb3066595634bb822e43083f3c0041186c0cde51cb1b0`
and `566d7bed249be89262832d7f2d30038505e519f2c441259df09ced349a3bf542`.
Package source revision/digest, DEB/RPM hashes and accepted baseline provenance
are unchanged from task 001 above. Each allocation retains its exact
`input/selected-inputs.json`; the resumed `evidence/result.json` files report
product, infrastructure, collection and cleanup passed, with
`cleanup_phase=complete`. Earlier plain allocations also retain successful
cleanup and independent baseline verification. Final public probes confirm both
VMs powered off; recording finalization and all owned cleanup ended.

Affected host regressions passed **3,133/3,133** in report
`20261018T004347Z-884445e2`, including the new input/ownership/refusal guards,
history registration/resume/collection, existing composition/confinement and
parallelism inventories. The new host module uses only pytest-private files and
in-process doubles; it adds no shared resource owner. Generated coverage and
Markdown links were refreshed. These edits change tests and documentation, not
product or build inputs, so no additional `make build` was required. This
engineering qualification does not close customer E2E, earlier-package upgrade
or live distro dependency-maintenance obligations.

## Task 003 retained work and fixture prerequisite

Task **003 remains unchecked**. System case **287** registers one continuous
`previous-policy` / `installed` / `rebooted` history through the existing
`--previous-artifacts` route. Public methods establish a 37-minute daily limit,
hard/soft app choices, custom request choices and a real Polkit-approved fixed
request for twelve additional hours. The oracle preserves exact grant issuance
and expiry while elapsed time reduces its balance. It requires the declared
kiosk shell transition from `/bin/bash` to `/usr/sbin/nologin`, retaining the
other identity/home fields, and schema 3 → 4 migration on Ubuntu (4 → 4 on Fedora).

The maintained builder now supports genuine released-source pairs for both
formats, including native RPM version ordering. Prepare with
`tools/run-tests artifacts prepare --for-vm --upgrade-inputs --vm NAME` and use
the returned `current` / `previous` directories immediately. Inputs and reports
have bounded retention; automatically rebuild missing generated inputs rather
than replacing an existing bundle or changing a version.

| Target | Previous source / native version | Previous package SHA-256 |
| --- | --- | --- |
| onpc-Ubuntu26.04 | v1.2, `81ffa5c37abeefdc922825bc27b5933b3eff3ba6`; `1.2+ppa1~ubuntu26.04.1`, amd64 | `49f675d9e28605eb38bd9d8a29797cdba9d4a67d5cb4320031a1c81e987c1d28` |
| onpc-Fedora44 | v1.3, `188be907c46b1cd0dabae06ac898c43e75beb05e`; `0:1.3-0.1.dev.fc44`, x86_64 | `857fbffbf4b59397abd90dc858f0d6cba63ddfbc3d0c7798afdddf2cc433b1f6` |

Both releases predate admission protocol 1. Their annotated tag objects are
pinned and independently matched to the public upstream; no earlier source or
version was rewritten. Previous source digests are respectively
`d0670fa09d677e72ffcf518f2c0e76559357668be7199a75e630f507c51322b9`
and `898a80018079d1408d1e8a76c46f85994d1b936ee17326c973c1a0c468b8c8ea`.
The current source/package hashes and accepted baseline provenance remain those
recorded in task 001 above. These are test/tooling edits, outside the product
source allowlist and ordinary `make build` dependencies; no product edit or
additional ordinary build was needed. Both actual package pairs built successfully.

Retained evidence is under `output/test-runs/host/reports/` and
`output/test-runs/privileged/allocations/`:

- Ubuntu passed **3/3 phases, no skips**, report `20261018T013516Z-a3b13fde`,
  allocation `onpc-system-4okbc7dl`. Its exact grant duration is 45,420 seconds
  (37 daily minutes plus twelve additional hours); issuance/expiry are unchanged
  and the balance decreases across the update/reboot. Public broker operations,
  native hard denial, approved soft allowance and unrelated-user controls pass.
  Its selected-input digest is
  `74fcd1b88162ae76716620c85ee13a20f38f651c7f3d39d9ef6d31446067cc04`.
- Fedora's repeated old-release checkpoint fails at the **unrelated-user native
  allow control**, before candidate installation. Latest report
  `20261018T014639Z-40dd2825`, allocation `onpc-system-8kbudaoz`, retains
  `guest-results/attempt-previous-policy/regression-failures.jsonl` and
  `stage-n0js4xzv-native-command-previous-upgrade-previous-compiled.txt`.
  The compiled policy contains child-only denies, then the distribution's
  trusted-executable allow and universal execute denial, then the old product's
  fallback allow. The existing fixture has `trust=0`; the actual unrelated-user
  launch reports execution denied. The input lacks a native positive control
  compatible with that earlier distribution policy. This does not establish a
  current-candidate product defect; that candidate was not installed there.
  Its selected-input digest is
  `47cf0a951a3335a2aec8606a52d3f5caf411ec9efc8470425f8dd31b29c7cbbb`.
- Final focused host ownership/provenance/history, agent safety, parallelism and
  documentation regressions passed **3,358/3,358**, report
  `20261018T014636Z-13ff172d`. After prerequisite insertion, documentation
  consistency passed **313/313** in `20261018T015108Z-63662840`; six changed
  Markdown files passed all 60 local-link checks. Generated inventory was refreshed.

Both VM receipts retain collection/infrastructure/cleanup passed,
`cleanup_phase=complete` and independent baseline restoration; Ubuntu's product
result passed, Fedora's did not. Recording finalization ended and both public
status probes report powered off. All workers joined. Ubuntu's witness predates
only the later diagnostic rule-snapshot addition; it grants no task completion
or evidence for the new fixture input. Preserve these results, complete
[002a](Core-Installation-Tasks/002a-trusted-native-upgrade-fixtures.md), then rerun
each complete 003 history with the final matching inputs and baselines. Do not
splice phases or remove the failing native control. This suspension closes no
customer E2E task and grants no task 003 acceptance credit.

## Coverage audit and remaining work

| Boundary | Existing protection | Remaining installed qualification |
| --- | --- | --- |
| Optional PAM | Parser/control-flow, ownership, include and restoration checks; real-helper composition; tasks 001–002's accepted LXC, plain, Fedora SSSD and local-override native histories | Finite task 002 PAM variants are qualified on both targets. |
| Failed configuration | OS gates, unsafe paths, migration schema/retry, service failures, backend/trust checks, task 001's native interruption/recovery and task 002's pending-vendor refusal/policy-preserving retry | Finite task 002 environment histories are qualified; future changes still need matching native evidence. |
| Earlier product versions | Maintained released-source DEB/RPM inputs and case 287's saved-policy/grant upgrade history; retained Ubuntu slice and Fedora fixture diagnosis above | Prerequisite 002a supplies trusted native witnesses; task 003 then requires both complete matching target histories. Same-version reinstall is a different result. |
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
