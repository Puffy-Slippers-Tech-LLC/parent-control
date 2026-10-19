# 006e — Qualify native bootstrap permissions on both backends

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Current execution boundary after the requested breakdown

Requires 006d, 006e1, 006e2 and 006e3. The queue now separates
[host completion](../Kiosk-Prompt.md#bootstrap-host-repairs--006e1), the complete
[Ubuntu history](006e2-bootstrap-ubuntu.md) and complete
[Fedora history](006e3-bootstrap-fedora.md). This original consumer remains
unchecked and keeps its Scope and all six per-target assertion families below.
It is suspended without installed acceptance credit.

006e1's host acceptance is complete. Its reference records exact probe/package
inputs and the remaining Ubuntu policy and Fedora logging observations. Resume
006e2, then 006e3; all six assertion families below remain required on both targets.

After those prerequisites pass, reconcile their complete installed receipts
against the final exact package, policy, selected test inputs and every assertion.
Reuse only applicable passing histories with completed cleanup; a source review,
host pass, partial probe or unrelated package hash is insufficient. Repeat any
invalidated full target history through the registered selector before closing
this task. Preserve the finite acceptance below and 006's full original scope.

## Purpose and prerequisites

Requires 006d. Supply the real-policy permission witnesses still required by
[006](006-generation-implementation.md) and the
[reviewed admission proof](../SystemDesign/Kiosk-Confinement.md#planned-retained-view-admission-proof).
The development host has AppArmor but no SELinux kernel enforcement. Existing
native fixtures double MAC, labels and system-bus observations; generated rules,
offline compilation and API doubles cannot establish these permissions.

This is a finite installed engineering prerequisite, not the ambient-change or
required-drift customer histories owned by 007a/007. Passing it preserves all of
006's original host acceptance and supplies only its exact bootstrap/reexec
policy evidence. It grants no completion credit to the suspended consumer.

## Reading and implementation route

Read AGENTS.md, the [master](../Kiosk-Prompt.md), the admission proof above and
only applicable [test ownership](../TestAutomation/README.md),
[VM](../Mandates/VM-Mandate.MD),
[storage](../Mandates/Test-Storage-Mandate.md) and
[installed-runner](../../tests/integration/README.md) contracts.

Extend the existing native/PAM owner
[`system_kiosk_confinement.py`](../../tests/integration/system_kiosk_confinement.py):
`first_exec()`, `pam_caller_command()`, `manager_boundary()`, native positive
services and `require_service_denial()`. Extract only the owned reexec/control
part of `verify_updates()` if needed; do not run its package/plugin replacement
matrix or the native-update/upgrade/public-station workflows.
Use the production fresh and retained coordinators, actual copied ELF inputs,
the exact attested installed policy and their existing one-child/deadline rules.

Add one bounded `verify_bootstrap_permissions(record)` and an enforcement case
in [`test_enforcement.py`](../../tests/system/test_enforcement.py). Append its
next unused persistent ID in
[`system_case_ids.py`](../../tests/integration/system_case_ids.py), verify ordinary
enforcement phase/input-closure routing, and update applicable host registration,
ownership and resource tests. Reuse the runner's candidate app snapshot, guarded
transport, watch, lease, evidence collection and restoration. Product installation
uses only `make install`; never install the product on the development host.

Registered selector, persistent system case **292** (ordinary `enforcement`
phase; registration alone supplies no acceptance):

```sh
tools/run-tests system --vm 'onpc-Ubuntu26.04,onpc-Fedora44' --area 'enforcement' --test 'test_kiosk_native_bootstrap_permissions'
```

## Finite acceptance on each target

1. Bind the package, boot, frozen selected inputs, native dependencies, current
   config/policy and successful-load attestation to the exact candidate. Require
   enforcing AppArmor profiles or enforcing SELinux with no relevant permissive
   domain. No label, bus, policy API or kernel-operation doubles are accepted.
2. Wait for natural kiosk inactivity and start only this attempt's manager unit.
   Independently retain its invocation, PID/starttime/pidfd, executable, role,
   task set, root/namespaces and actual M/V/ready/copy/source identities. Exercise
   the actual manager-side PAM bootstrap and gate-side final-session PAM call;
   Fedora uses the existing real `init_t` and `xdm_t` caller routes.
3. Prove successful production gate admission traverses actual proc/task/exe/
   root/namespace reads, pidfd acquisition, bounded native system-bus queries and
   recursive clone acquisition. Independently check the private read-only view's
   required mounted inodes and nested coverage against the original manager.
   Require unchanged manager dentries and completed records; a successful PAM
   status alone is insufficient.
4. Execute both selected copied entrypoints, `/usr/lib/systemd/systemd` and
   `/usr/lib/systemd/systemd-executor`, through the real `manager-pam → manager`
   and `manager → manager` policy routes. Observe actual enforcing roles and
   private namespaces with parent-owned proc/pidfd observations. Bounded native
   `--version` probes may establish these finite entrypoint permissions; they
   cannot replace the following live manager reexec witness.
5. Reuse the supported owned manager notify-reload reexec. Require unchanged
   invocation, PID/starttime, enforcing role, private namespace, M/V and source
   objects, an allowed native service, and a fresh prohibited-shell execution
   failure with its exact enforcing kernel denial. Prove the manager cannot
   write or replace measured executable/library sources, the skeleton or
   completed records, or gain mount, namespace or unconfined escape authority.
6. Verify setup-descriptor closure and preservation of caller-owned descriptors
   through the existing PAM fixture. Retain bounded failure diagnostics and
   independently confirm unchanged policy/PAM state.

Do not load a weaker probe policy, enable permissive mode, modify vendor
executables, broaden payload permissions or accept a test executable in place
of either selected ELF. Do not signal a pre-existing manager. A missing supported
mechanism must be diagnosed and repaired within this finite boundary, with the
original expectations preserved.

## Validation, cleanup and close-out

Session exception: the first implementation and the same finite permission
history on both backends may take 35–60 minutes. This adds no package-update,
ambient-change or public-form history to the prerequisite.

Run focused host/native registration and ownership regressions, documentation
checks and `make build` after any final packaged edit, then the exact registered
case on both targets. Preserve first failures and exact candidate/input evidence.
Use only existing private fixture allocation and recorded child/unit identities;
reap all children, close descriptors and stop only the invocation this attempt
started. Preserve foreign/replaced state. The installed runner owns collection
and final VM restoration; finish its cleanup before recording either target pass.

Record concise per-target receipts and source applicability in the master/queue,
remove this temporary brief when appropriate, and resume unchecked 006. Its full
composition matrix, cumulative host selection and final build remain required;
007a/007 retain their complete public installed histories.

## Implementation checkpoint — acceptance still open

Case 292 is registered and implemented. Its first installed attempt on both
targets refused the root-owned, mode-0600 account marker because the broker's
administrative group differed from the executable-source group. The narrow
private-state proof now binds that exact group; executable, ancestor, alias,
owner, mode, digest, link-count and capability checks remain strict.

The next attempt passed that boundary. Ubuntu exposed a legacy test marker
assumption; case 292 now explicitly observes the current retained-view marker.
Fedora exposed its package builder's duplicate-file hardlinking of the kiosk
launchers. The RPM disables that optional pass, preserving all other processing
and the runtime one-link requirement. Both formats rebuilt successfully; the
RPM now records distinct launcher inode identities.

The third installed attempt reached the same process-authority assertion on
both targets. Owned maintenance observations found the exact expected UID/GID,
role and namespaces, with zero effective/permitted/ambient capabilities but
inheritable `CAP_WAKE_ALARM`. That candidate cleared ambient capabilities only.
The shared native repair now clears both sets, verifies unchanged caller
effective/permitted authority and retains the original deadline. Its independent
review found no blocker; **1,857/1,857** affected native/PAM/confinement/resource
checks passed in `20261019T204948Z-f74061cb`, including 19 added capability
controls, and both package formats rebuilt successfully. The full registered
installed case remains required on both targets. No installed acceptance has
passed yet.

Host receipts: **2,835/2,835** native/registration/resource checks in
`20261019T202047Z-7bbe3b8a`, **313/313** documentation checks in
`20261019T202527Z-50ccdfab`, **60/60** RPM packaging checks in
`20261019T203625Z-4c789fed`, and **1,340/1,340** confinement checks in
`20261019T203711Z-64f5ee15`. The later native/observer edits passed the 1,857-case
selection above. The verified
[1,103-file cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-0v50uz9y/evidence.zip)
retains the earlier host history, all three installed failures, exact package and
selected-input manifests, and completed cleanup receipts. SHA-256:
`2e5535deac51fac35b1c25d27f0f1d219a6657cb1ae92cf475d75aa41a7eabeb`.
Third-attempt results are `onpc-system-509n0k98` (Ubuntu) and
`onpc-system-jg77agr1` (Fedora), under the maintained privileged allocations root;
both runner restorations passed. Subsequent owned maintenance managers and VMs
were stopped through the maintained route; restoration passed on both targets.
All subagents finished before the fourth installed run acquired VM resources.

The fourth installed attempt confirmed zero effective, permitted, inheritable
and ambient capabilities on both targets, then exposed two engineering oracle
issues. Fedora completed fresh production PAM admission but added libc's lazy
logging socket beside the admission lease. The fixture is being prepared to
pin that actual caller-owned socket before its strict descriptor comparison;
unknown extras remain failures. Ubuntu rejected six root:root mode-0777 service
mask symlinks whose exact `/dev/null` text matched the receipt. Owned maintenance
confirmed those objects; the observer now distinguishes symlink modes from
file/directory write permissions, with ten focused controls and independent
review. The owning native proof already makes that distinction. These fixture
corrections still require host checks and the complete installed case. The
logging fixture now eagerly opens the actual libc socket, verifies its connected
Unix peer against the independently observed public logging endpoint, preserves
its exact descriptor and keeps the one-admission-lease-only addition rule.
Fifteen private socket controls cover that setup and its failure cleanup.

Fourth-attempt reports are `20261019T205513Z-ddef791f` (Ubuntu,
`onpc-system-com9n4_g`) and `20261019T205513Z-2479f924` (Fedora,
`onpc-system-22ip0a3s`); both runner restorations passed. The verified
[1,205-file cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-0v50uz9y/evidence.zip)
now includes them and the earlier bundle's full history. SHA-256:
`48064ff93e14a5f1c9d7ed75d08249fb4f5d7bb19327fe52acf924218b392b74`.
The later Ubuntu maintenance diagnostic stopped only its recorded manager;
all subagents joined and its maintained VM stop/restoration passed. No VM or
worker remains owned. No installed acceptance has passed.

## Fifth attempt and developer-requested suspension

The fifth complete registered attempt failed on both targets. Ubuntu passed
the previous source-trust and descriptor checks, completed fresh production
PAM admission, then actually admitted `unshare(CLONE_NEWUSER)` under its
enforcing manager profile. The private retained pytest log identifies
`kiosk-bootstrap:authority-not-denied:user-namespace`; the generic parent EOF
was a consequence, not the cause. The AppArmor compatibility ABI does not
mediate this feature merely because an allow is absent. Explicit audited user
namespace denials now cover non-sandbox roles and the nested password profile;
the two native sandbox grants and unrelated ABI behavior stay unchanged.

Fedora failed `kiosk-bootstrap:logger-receipt-mismatch` after successful fresh
production PAM admission. That candidate recorded its valid pre-PAM connected
logging socket but asserted before retaining the independent post-PAM table,
so the exact changed field remains unproved. The later fixture records both
tables, both logger receipts and the independently observed endpoint before
asserting. Its post-PAM socket probe uses only the known borrowed FD and an
owned duplicate, without a proc census. Only a logger demonstrably introduced
by this fixture may renew at the same independently verified FD/type/peer/
endpoint; all original caller descriptors and the one-native-lease-only
addition remain strict. Twelve new private controls cover this boundary.
This correction has no installed pass yet; do not claim reconnect as the cause.

Latest reports: `20261019T211139Z-21e18541` / `onpc-system-fpjvm_mz` (Ubuntu)
and `20261019T211139Z-5b4fa977` / `onpc-system-o8slnz68` (Fedora). Both runner
restorations and cleanup passed. Their frozen selected inputs are
`ab51363e74547369a0246c0daa4af662bb5548360618e7c9049c979417f8c96c`;
package-source digest is
`6fb9d53695fd5fd4b2dc6725f2ef62e23bede13156126c7b4d93334bf927f994`
(369 files, revision `af43bfcbc43a91067e070034de5b30e4ece1724e`).
The newer policy/logger edits are outside those installed receipts.

After the developer requested smaller tasks, all subagents finished and the
current consumer was suspended for unchecked 006e1/006e2/006e3. No later VM run
was started. The final policy/logger/confinement and execution-plan/resource
selection passed **2,175/2,175** in `20261019T212338Z-29e12a40`; the earlier
socket/link/registration selection passed **2,619/2,619** in
`20261019T211006Z-ed2d4cc6`. Both package formats rebuilt after the final
packaged edit. 006e1 must reconcile this host checkpoint, the observer's fresh
skeleton-link semantics and final inputs; 006e2/006e3 must each complete every
original installed assertion. All VM, fixture, child and worker ownership is
closed. This checkpoint and its commit grant no acceptance.

Final checkpoint archive: the verified
[1,332-file cumulative bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-0v50uz9y/evidence.zip),
SHA-256 `deb29c21587c0275cd0ce0368f54b03c3d61b027f1c8de6a42948a6ecd3dfce0`,
contains all five installed attempts, selected-input/package manifests, latest
2,175-case host pass, the **313/313** documentation pass
`20261019T212605Z-310f0a0f`, earlier carried-forward history and cleanup journals.
It also retains Ubuntu's exact private pytest log establishing the user-namespace
failure. The intermediate 2,619-case report was retired before export; its
observed pass is historical only, not a reusable retained acceptance receipt.
The later host selection retains all changed confinement controls. Current
RPM build-input source SHA-256 is
`0c60e1de6a5bb63c5f916d9153be61a2b849fd68ffa4fecf5e760c4cb1eb3ce7`;
it includes the final AppArmor repair and has no installed acceptance yet.
Earlier archive links above now point to carried-forward contents; their
historical counts/hashes still describe the original exports.
