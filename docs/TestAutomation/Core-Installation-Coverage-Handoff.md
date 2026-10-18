# Core installation coverage handoff

Task queue: [Ordered task queue](Core-Installation-Task-Queue.md).
Next task: **004b — [Implement verified native transaction inputs](Core-Installation-Tasks/004b-native-transaction-inputs.md)**.

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

Shared work covers both targets in one task. Run independent Ubuntu/Fedora
histories in parallel through maintained runner routes within the registry
concurrency cap, with separate leases, inputs, reports and cleanup. Each VM's
history remains ordered and indivisible. Split out a VM-specific prerequisite
only when a concrete issue is unique to that VM; distro-specific package or
schema expectations alone do not justify separate sequential tasks.

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

Historical suspension, superseded by [final acceptance](#task-003-final-upgrade-acceptance).
Task **003 remained unchecked**. System case **287** registers one continuous
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
or evidence for the new fixture input. Preserve these results and use the
[qualified 002a inputs](#task-002a-trusted-native-fixture-qualification), then rerun
each complete 003 history with the final matching inputs and baselines. Do not
splice phases or remove the failing native control. This suspension closes no
customer E2E task and grants no task 003 acceptance credit.

Handoff recovery corrected 003's Requires to `002, 002a`: the inserted fixture
prerequisite is now explicitly in its dependency chain, retaining the original
dependency. All existing completion states, relative order and scopes remain
unchanged. The retained target receipts above were reread: both record cleanup
complete, successful collection/infrastructure and independent baseline checks
without failures. The public recovery route then reconciled both VM/storage
owners successfully, preserving evidence; public status probes confirmed both
guests powered off. The prerequisite was unexecuted at that recovery; its later
qualification below leaves both complete 003 histories with final inputs required.
Recovery validation passed **465/465** documentation and plan-launcher checks in
`output/test-runs/host/reports/20261018T021657Z-c6d5ade8/report.md`, including the
rejected-unlinked-prerequisite correction and backward-dependency guards. All
35 local links in the four task documents passed; final host recovery completed
after the checks released their owner. This recovery changes documentation only.

## Task 002a trusted native fixture qualification

Accepted on 2026-10-17 (local time). System case **288**,
`test_trusted_native_upgrade_fixtures`, passed **1/1 execution per target with
zero failures and skips**. Each independent history installed and booted the
exact pinned earlier package, verified native file trust and unrestricted
execution for both fixed roles, then proved child-only hard/strict-soft denial,
real authenticated soft approval and unrelated-user execution. The candidate
upgrade was never installed. Task 003 remains unchecked and must select these
qualified variants and run both complete upgrade histories.

The baseline owns distinct `trusted-hard` / `trusted-soft` payloads and exact
native file-trust entries. It preserves the original untrusted payloads and
their absence from native trust. Preparation safely enables the recognized
file backend before publication, refusing unrelated inactive entries. Durable
records bind payloads, native package/tools, enabled configuration, native
service-group metadata and preparation source; retries cover interrupted writes,
publication and native tmpfiles ownership normalization. Consumers only verify.
No distribution execution rule or product behavior was changed. The enduring
contract is in the [installed environment](../../tests/integration/Environment.md#reusable-preparation-ownership).

Reports are under `output/test-runs/host/reports/`; allocations are under
`output/test-runs/privileged/allocations/`. Each allocation retains
`evidence/result.json`, `guest-results/trusted-fixtures.xml`, native rule/command
evidence and `input/selected-inputs.json`.

| Target | Pinned earlier package / source revision | Report / allocation | Native fapolicyd |
| --- | --- | --- | --- |
| onpc-Ubuntu26.04 | `1.2+ppa1~ubuntu26.04.1`, amd64 / `81ffa5c37abeefdc922825bc27b5933b3eff3ba6` | `20261018T032241Z-e981d98b` / `onpc-system-nd46dfaw` | `1.3.6-1` |
| onpc-Fedora44 | `0:1.3-0.1.dev.fc44`, x86_64 / `188be907c46b1cd0dabae06ac898c43e75beb05e` | `20261018T032652Z-80c4c1e1` / `onpc-system-2finpn0d` | `0:2.0.1-1.fc44` |

Earlier package SHA-256 values are respectively
`49f675d9e28605eb38bd9d8a29797cdba9d4a67d5cb4320031a1c81e987c1d28`
and `df0b69f9ca4d8a59a5a1475afff4f5b078cd2f1d0efb49c7fcff5fc81ee29a97`.
Both receipts bind selected inputs
`53c52a57a593f53964c1022874f233cf1e7e77bfd3f5123e72c936f6ac1abacb`
and preparation script
`42d09a01a044ff574e74f2643ad833add5570095738e6e8597eb66f841014fb6`.
The staged qualification helper and native schema match the final checkout.
Native tool/configuration/payload digests remain in each passing JUnit.
Baseline provenance is respectively
`911f00330b638bfdeeaa826a841d1ad46e61502758f7a48a0566d5e0f7796adc`
and `7deb579a3e327db7ec2e416131df7d5bc0e4993feac5b3db73bb5a7d7f4fc12f`.
The verified candidate pair uses revision
`5414b496ca5fe97a51ed7523d0c32978b398d859`, source digest
`68e24deca024e35c36444fcb4217642eeb7a9cfa3276d55e0e12799fe75c4b05`;
its identity supplies input provenance, not upgrade acceptance.

Both results record product, infrastructure, collection and cleanup passed,
`cleanup_phase=complete` and independent baseline verification without failures.
Recording finalization ended; public status probes confirm both guests off.
All workers joined before acceptance. Affected host checks passed **3,272/3,272**;
the final native-group/backend/retry/verifier selection passed **624/624**.
Their retained reports are respectively
`output/test-runs/host/exports/onpc-artifact-export-t9ii5pqi/report.md` and
`output/test-runs/host/exports/onpc-artifact-export-1t15i008/report.md`.
Resource inventories were reviewed; the checks retain private fixtures and
existing lifecycle owners. Generated coverage was refreshed after the final
source change. These edits affect tests/tooling only, so no additional product
`make build` was required. Documentation/plan consistency passed **465/465**;
its retained report is
`output/test-runs/host/exports/onpc-artifact-export-wy3hxyuw/report.md`.
All 151 local links in the seven changed Markdown documents passed. Only 002a
is checked; 003/004 retain their status, order, scope and dependencies.

## Task 002b qualified fixture integration

Case **287** now selects baseline-owned `trusted-hard` / `trusted-soft`
consistently in provisioning, saved desktop/target choices, strict soft denial
before authentication, rule evidence and previous/rebooted child/unrelated-user
launches. Rule evidence requires the hard denial and approved soft allowance for
their exact variants. All policy, grant, identity, migration, real Polkit and
admission assertions remain. Consumers verify prepared trust through the existing
closed interface; they add no trust or distribution rules.

Affected host checks passed **1,391/1,391** in
`output/test-runs/host/reports/20261018T182003Z-99065707/report.md`, including
both platform setup paths, strict denial before approval, both enforcement
checkpoints, closed fixture/provenance guards and complete history staging.
Final consumer, documentation, inventory and plan regressions passed
**408/408** in
`output/test-runs/host/reports/20261018T182120Z-694ec03c/report.md`.
The five added host cases use tiny pytest-private files and in-process doubles;
there is no new process, service, bus, display, socket, shared cache or cleanup
owner. The existing compatible unit classification remains valid, with no
cleanup/UI inventory change. Generated coverage was refreshed. These test and
documentation edits affect neither product package sources nor build tools;
no `make build` is required. No installed qualification occurs in 002b.
Both maintained host runs finished and released their owners; no worker or
VM resource remains from this task. Only 002b was newly completed.

For **002c**, require the staged `system_previous_upgrade.py` SHA-256
`8703b2d4e671598ad3f6dd43c04862231a62b175bee8a1faa8ca1bc0b7c62176`
in each exact `input/selected-inputs.json`. Stage the final checkout's shared
enforcement/trust helpers and payloads, and verify 002a's accepted trusted
baseline provenance and pinned earlier package identities above. Prepare missing
verified current/previous bundles through the existing artifact route; preserve
existing inputs. Each target must run all three case 287 phases in one owned
history and retain matching candidate, input, baseline and cleanup receipts.
The earlier Ubuntu slice and case 288 qualification supply no acceptance for
these final upgrade inputs. Task 003 remains unchecked.

## Task 002c complete upgrade histories

Accepted 2026-10-18. Case **287** passed **3/3 phases per target**, with no
failures or skips, in parallel run `30838700ff2a4a0ca95371d73fdd254f`.
Each target kept `previous-policy`, `installed` and `rebooted` in one baseline
attempt, without an intermediate restore. Reports below are under
`output/test-runs/host/reports/`; allocations are under
`output/test-runs/privileged/allocations/`.

| Target | Native version transition | Report / allocation | Baseline provenance SHA-256 |
| --- | --- | --- | --- |
| onpc-Ubuntu26.04 | `1.2+ppa1~ubuntu26.04.1` → `1.4+local1~ubuntu26.04.1`, amd64 | `20261018T190013Z-06fb3398` / `onpc-system-pn0m4z8t` | `4ff5d2668d9afe71cf6ff0bfc4ab3d25471776016ef5b309cdaebccc0fc481e7` |
| onpc-Fedora44 | `0:1.3-0.1.dev.fc44` → `0:1.4-0.1.dev.fc44`, x86_64 | `20261018T190013Z-480dd9e4` / `onpc-system-8seskbd3` | `dce95ae3b2147179b3f30587faad9e3bfd418d3283fd100f4f8e7e72fdedbbde` |

Each allocation retains `evidence/result.json`, all three phase JUnits under
`guest-results/`, native rule witnesses and exact `input/selected-inputs.json`,
`artifact-manifest.json` and `previous-inputs.json`. Both selected-input digests
are `4e04c09c418daf69ccc743cdebcf3aac60232344f69d0cf5326c9b4b9aba1d5f`;
the staged upgrade helper matches 002b's required
`8703b2d4e671598ad3f6dd43c04862231a62b175bee8a1faa8ca1bc0b7c62176`.
Shared enforcement/trust helpers and fixture payload hashes match the final
checkout. Both histories verify the baseline-owned trusted variants' bytes,
native configuration, provenance and loaded trust through the closed consumer
verifier; they neither add trust nor reuse the historical baselines above.

Candidate source revision is `9162f12d8d92ac78ecbc465280b2b0197f1c4320`, digest
`3847aa39a5c73d6657056bc94e375e56c02c9cd0fa0ed30ec9e836725ee0df29`.
Ubuntu's candidate/prior package SHA-256 values are
`ce10b0b5e36cda0a31b0f822adff12edd7d7ef384e57fe9aabb6ec0e97911a26` /
`49f675d9e28605eb38bd9d8a29797cdba9d4a67d5cb4320031a1c81e987c1d28`.
Fedora's are
`04f31135daa171782d89196c291b49888a9d04b9b3471b72427d484c8aebb50d` /
`ad2b035946db68c6144d8b9b1bf67c034ddd098cbddd084273963abca2aafd93`.
The prior packages retain 002a's exact pinned release source revisions/digests,
native versions and architectures; the rebuilt RPM has its own recorded package
digest. Native ordering verifies that each candidate is genuinely newer.

All policy/request choices, real authenticated approval, identity preservation,
kiosk shell transition, schema 3 → 4 / 4 → 4, exact reboot/removal refusal and
public broker recovery assertions passed. Native hard denial, approved soft
allowance and unrelated-user execution passed before update and after reboot.
The exact grant duration remains **45,420 seconds**. Ubuntu preserves issuance /
expiry `1792350289` / `1792395709`, with remaining seconds
`45418.6455 → 45361.7088 → 45311.3446`; Fedora preserves
`1792350228` / `1792395648`, with
`45418.4276 → 45391.2529 → 45354.6684`.

Both receipts independently pass product, infrastructure, collection and cleanup,
record `cleanup_phase=complete`, and pass acquisition/restoration verification
with zero failures. Public status probes confirm both VMs off. All workers have
joined. Recording finalization completed successfully; the session's
`recordings.json` binds `system-287-Ubuntu26.04-Fedora44.webm` to SHA-256
`745b59220430d4c763b761438144978b27cac6c44c359b661bdcbed7115d818e`.
The combined result is
`output/test-runs/host/allocations/onpc-vm-queue-ru9nhntv/results.json`.

Shared runner infrastructure now supports `system --upgrade-inputs` for any
explicit system selection requiring an upgrade. Each VM worker prepares its own
verified pair and passes the existing current/previous artifact route. Registry
format and pinned baseline must agree; neither format defaults nor case-specific
builders are used. Conflicting explicit paths refuse before allocation.
Affected host checks passed **2,099/2,099**, preserved in the evidence bundle
below under original member
`output/test-runs/host/exports/onpc-artifact-export-pu2p08zh/report.md`.
Final launcher/plan/inventory consistency passed **2,256/2,256** in
`20261018T190834Z-63341d8e/report.md`, including all 1,705 launcher/resume checks;
corrected configuration,
recording-fixture and resource-inventory checks passed **355/355** in
`20261018T190423Z-1e3a4ae6/report.md`.
Mechanical host repairs preserve runtime name-resolution checks and use synthetic
recording labels; acceptance documents may name their canonical targets.
Resource review retains existing unit/cleanup compatibility and adds no owner.
Generated coverage was refreshed. These test/tooling edits affect neither
package sources nor build-tool dependencies, so no additional `make build`
is required. Only 002c is newly complete; 003 remains the final evidence gate.

The verified **788-file** retained bundle is
`output/test-runs/host/exports/onpc-evidence-bundle-sol74eq8/evidence.zip`, SHA-256
`ba828106aa6eeee91e4019f1e687857481f837b9e1a82a032052f2080758722f`.
It preserves both target receipts/JUnits/native diagnostics/input manifests,
host reports, queue results and exported recording/recording receipt. Bundle
inspection verified all bytes and both passing target receipts after publication;
export cleanup completed. Recording files first used the normal artifact export
route because their original lifetime is separate from allocation retention.
Preserve this bundle through 003 using the existing report-retention contract.
All 147 local links in the five changed prose documents passed.

## Task 003 final upgrade acceptance

Accepted 2026-10-18 on **onpc-Ubuntu26.04** and **onpc-Fedora44** using the
complete installed [002c histories](#task-002c-complete-upgrade-histories).
The maintained bundle reader reverified all **788 files**, ZIP SHA-256
`ba828106aa6eeee91e4019f1e687857481f837b9e1a82a032052f2080758722f`, in
`output/test-runs/host/exports/onpc-evidence-bundle-sol74eq8/evidence.zip`.
Original paths below remain bundle member keys after ordinary source rotation.

| Target | Report / allocation | Installed acceptance |
| --- | --- | --- |
| onpc-Ubuntu26.04 | `20261018T190013Z-06fb3398` / `onpc-system-pn0m4z8t` | Case 287: all three phases passed, zero failures/skips; v1.2 → v1.4, schema 3 → 4 |
| onpc-Fedora44 | `20261018T190013Z-480dd9e4` / `onpc-system-8seskbd3` | Case 287: all three phases passed, zero failures/skips; v1.3 → v1.4, schema 4 → 4 |

Each allocation's `evidence/result.json`, three `guest-results/*.xml` files,
`input/selected-inputs.json`, `input/previous-inputs.json` and
`guest-results/attempt-previous-policy/{previous-install,update-activation}.json`
were independently reconciled. The old payload was installed and booted before
policy setup; native package ordering and exact source/package identities match
002c. Both activation receipts explicitly record `same_version_reinstall=false`.
Both pinned earlier releases lack admission protocol 1; the candidate establishes
that protocol, requires reboot and refuses removal before old-worker retirement.
Public policy calls return the exact reboot-required refusal without changing
rules, then work after a genuinely different boot.

Both histories retain the 37-minute allowance, permanent hard and conditional
soft rules, custom 23-minute request choice and real authenticated twelve-hour
approval. Under [grant arithmetic](../SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities),
the exact duration is **45,420 seconds**. Each retains its issuance/expiry and
decreasing balance recorded in 002c; public time status agrees after reboot.
Saved/native policy, child/parent/unrelated-user identities and homes survive;
only the declared kiosk shell changes from bash to nologin. Native launches
prove strict soft denial before approval, hard denial and approved soft allowance
before update and after reboot, with unrelated-user positive controls.

All **36 staged file entries** (33 distinct checkout sources), including the
qualified trust verifier and upgrade helper, match current SHA-256 values.
All **353 package source inputs** are unchanged from the recorded candidate.
Each history verifies its own final baseline's exact trusted fixture provenance,
bytes, native configuration and loaded trust; the old untrusted inputs remain
unchanged. No history is spliced, and no input or assertion is invalidated, so
the brief permits reuse without another live run. Focused ownership, provenance
and history regressions passed **1,027/1,027**, report
`output/test-runs/host/reports/20261018T191447Z-d9a984b3/report.md`.
Final documentation, inventory, composition and execution-plan checks passed
**551/551** in
`output/test-runs/host/reports/20261018T191609Z-f3c3a2c5/report.md`.
All 29 local links in the two changed Markdown documents passed; queue review
confirmed every other row unchanged and 004a as the first unchecked task.

Both installed receipts independently pass product, infrastructure, collection
and cleanup, with `cleanup_phase=complete` and zero baseline-verification failures.
Fresh public status probes confirm both guests off. The combined queue result
and finalized recording receipt remain in the same verified bundle. Final
`tools/cleanup-e2e --vm 'onpc-Ubuntu26.04,onpc-Fedora44'` completed serial recovery
for both targets and host storage, retaining evidence. No subagent or live
attempt remains. Only documentation changes in this final gate; package
sources, inventory and collection are unchanged, so no build or coverage refresh
is required. Only 003 is newly complete; customer E2E tasks remain unchanged.

## Task 004a finite native input review

Accepted 2026-10-18 as **review**, with no declared acceptance targets or VM
mutation. The [004b input plan](Core-Installation-Tasks/004b-native-transaction-inputs.md#004a-reviewed-input-selection)
retains exact authoritative artifact/publication/build sources, package digests,
native verification routes, compatible dependencies/reverse consumers and normal
trigger requirements for both supported distros:

- Ubuntu 26.04: `bubblewrap:amd64` `0.11.1-1` → `0.11.1-1ubuntu0.3`, one DEB.
  Official build logs bind distinct ELF build IDs to `/usr/bin/bwrap`; the
  compiled ptrace fix corroborates changed bytes. This is the native substitution
  source, not the product wrapper visible at private `/usr/bin/bwrap`.
- Fedora 44: `xdg-dbus-proxy.x86_64` `0:0.1.6-4.fc44` → `0:0.1.9-1.fc44`, one
  RPM. Release/update downloads match their signed Koji copies; exact Koji file
  records bind distinct executable SHA-256 values to both packages.

Both pairs have compatible runtime requirements and reviewed current consumers,
without a companion downgrade. Neither package owns runtime maintainer scripts;
normal matching man-db triggers remain required, with independent results and
installed trigger inventory. 004b must implement native cryptographic and payload
verification, exact installed-set/trigger preflight and selected-input binding;
Ubuntu's extracted executable SHA-256 values remain to be measured there.
Those implementation gates do not claim installed transaction success here.

The retained plan resolves old-generation preparation before admission, actual
living executable mappings, retained enforcement, stale-manager refusal, loader
exclusion under a real admission lease, explicit safe reexec, normal owned exit
and reboot recovery. Native maintenance alone neither publishes a new private
generation nor creates a product reboot request. All original 004 obligations
remain required in the later installed histories. Independent source/contract
review passed; all three read-only subagents completed without retained resources.
Final plan, inventory, coverage, composition and launcher consistency checks
passed **551/551**, report
`output/test-runs/host/reports/20261018T192811Z-7080e093/report.md`.
All 52 local links in the four changed Markdown documents passed. Queue diff
review confirms only 004a's completion/link/evidence changed, every Scope and
Requires cell is preserved, and 004b is the first unchecked row. Its temporary
predecessor brief was removed after review; the final 004 gate links here.
The maintained host runner finished and released its owner; no live process,
VM resource or disposable research artifact remains owned by this task.
No package/product/build source or inventory changed, so no build, coverage
refresh or VM cleanup is required. Only 004a is newly complete.

## Coverage audit and remaining work

The remaining work is decomposed in the [queue](Core-Installation-Task-Queue.md).
Task 003's [both-target installed gate](#task-003-final-upgrade-acceptance) is
complete. Task 004a's [finite input review](#task-004a-finite-native-input-review)
is complete; continue with 004b's verified native transaction inputs.

For 004, package-pair feasibility (004a) precedes verified input/preparation
support (004b), history implementation/registration (004c), and independent
Ubuntu/Fedora acceptance in combined task 004d, scheduled in parallel. The native
package pairs are selected; their staging and installed transaction qualification
remain pending, and the selector remains unimplemented. The product
earlier-release builder is not a
native dependency transaction builder. Task 004 retains the original installed
both-target gate. Its existing synthetic replacement tests supply no actual
package-transaction acceptance.

The earlier planning revision itself executed and closed no task. Historical
evidence above is preserved. Task 002c absorbs former 002d, and 004d absorbs
former 004e, retaining both targets' full scope and acceptance; final-gate
dependencies now point to the combined tasks. Each live history remains
indivisible, with no phase splicing or intermediate baseline restore. Final gates
may reuse complete retained reports
only when candidate, helpers, inputs, baselines, assertions and cleanup match;
rerun any invalidated target history in full. Keep reports through final gate
close-out using the existing retention/export route. The longer live estimates
cover required boots/cleanup; they do not combine implementation work.

Task 002a's accepted implementation is recorded in commit `6e1ecfd3`. The
retained launcher originally stopped before recording that commit and this queue
decomposition.
The explicit [manual replan route](../Execution-Plans.md#common-launcher-interface)
has since reconciled that inactive checkpoint with the committed queue, preserving
the accepted evidence and unfinished 003 handoff without new acceptance or renewed
session counts.

The 2026-10-18 run `b7681335a53c4fd78aea4e0ac1de6d01` accepted 002b and
retained its passing response and completed cleanup, then stopped before Git
close-out: `close-out overlaps pre-existing work: docs/Test-Coverage.md`.
Its task limit was unlimited; zero tasks were counted because commit/push had not
finished. The inherited baseline still protected that report even though its
exact captured contents had already been committed. The shared
[close-out guard](../Execution-Plans.md#common-launcher-interface) now releases
such committed baseline contents, including inherited/suspended copies, while
preserving uncommitted and staged work.

Restart `485aee9d3cce41598d937606283aa0a0` exposed the remaining version lock:
002b's changes were committed in `04cf58c5`, including a newer generated report,
so the clean report no longer matched the captured baseline. Close-out now also
releases paths whose working contents, executable mode and index match HEAD,
without requiring the saved report version. It retires clean inherited and
suspended baseline entries before later tasks edit them; pending work remains
protected under the shared close-out contract.

Recovery run `19cc86722dd043bc9c755b682d66cf0b` successfully completed 002b's
retained close-out and pushed `ae115644` (`TA: Completed task 002b`). Its result
records status 0 and one recovered task; no coordinator session was needed.
The active and suspended 003 baselines are empty. Focused launcher, inventory,
documentation and coverage checks passed, and all 34 local Markdown links passed.
The bounded `--tasks 1` invocation stopped at its task limit before starting 002c.

That recovery left the then-current queue, 002c pointer and suspended 003 handoff
intact; it executed no additional queue task or installed history and required no
manual replan. The subsequent consolidation changes task structure and target
declarations. Cancelled run `3f10b5e801564ca2a94b2102263d7c39` predates that revision.
Use the [explicit consolidation route](../Execution-Plans.md#common-launcher-interface)
with the exact old committed queue and the two reviewed mappings:

```sh
tools/install-coverage --reconcile '3f10b5e801564ca2a94b2102263d7c39' --merge-task '002d=002c' --merge-task '004e=004d' --reconcile-base 'd8cfd759310098f04f6b0f2829b3c973b33ae3cb' --check
```

Omit `--check` to adopt after its checks pass; repeat with `--check` to verify
`resume_ready`. The route preserves the original checkpoint, original per-target
briefs/scopes, unfinished 002c/003 handoffs and session counts. It grants no
completion and starts no installed history. After adoption,
`tools/install-coverage --tasks 0` resumes combined 002c under the ordinary guards.

Target upgrade diagnosis belongs to 002c, and native package-pair feasibility
to 004a. These are execution work,
not prerequisites for starting this plan. The retained-unlock investigation stays
in the existing E2E work unless evidence establishes a dependency for one of this
queue's acceptance histories. If a selected task discovers such a dependency,
record the concrete failure and insert a bounded prerequisite through the
ordinary plan workflow before resuming its consumer; preserve the original
acceptance rather than requiring all unrelated investigations to finish first.

| Boundary | Existing protection | Remaining installed qualification |
| --- | --- | --- |
| Optional PAM | Parser/control-flow, ownership, include and restoration checks; real-helper composition; tasks 001–002's accepted LXC, plain, Fedora SSSD and local-override native histories | Finite task 002 PAM variants are qualified on both targets. |
| Failed configuration | OS gates, unsafe paths, migration schema/retry, service failures, backend/trust checks, task 001's native interruption/recovery and task 002's pending-vendor refusal/policy-preserving retry | Finite task 002 environment histories are qualified; future changes still need matching native evidence. |
| Earlier product versions | Maintained released-source DEB/RPM inputs, case 288's qualified trusted witnesses and case 287's saved-policy/grant upgrade history; retained earlier diagnosis above | Task 003 passed both complete matching upgrade histories with qualified witnesses, retirement/refusal and cleanup. Same-version reinstall is a different result; customer update journeys remain pending. |
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
