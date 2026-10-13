# Kiosk confinement: implementation and independent-review record

This record covers the incident investigation, the preceding partial fix, and
the subsequent development and code-review sessions on October 11–12, 2026.
**The work is unfinished and is not release-qualified.** Source implementation,
host regressions, installed engineering probes and customer acceptance are
different evidence categories below. Passing preparation is not acceptance.

The user requested this file be retained for independent review. This supersedes
the earlier request to delete the original brief after reading it. Keep this
record current as the remaining work is completed; the continuation prompt is
delivered in conversation, not maintained as a second repository task document.

## Current code-review status

**Phases 1 and 2 are complete; Phase 3 is next and has not started.** See the
[phased execution plan](#phased-execution-plan-current).
All three Phase 1 issue fixes and every Phase 1 exit gate pass. Supporting PAM
credential, password-helper traversal and native-profile activation fixes pass
their affected host/build checks. Both final installed confinement matrices,
both strict waiting-session censuses and public cases 50–52 on both targets
pass for the Phase 1 packages. The
[resumed exit-gate record](#resumed-phase-1-exit-gates--final-installed-inputs)
owns the final results and retained evidence; earlier package results remain
historical.
The [Phase 2 issue 1 record](#phase-2-issue-1-execution-record) owns the current
classification adapter's package identities, live and installed recovery checks,
case 50 regression, host results and cleanup. The
[Phase 2 issue 2 record](#phase-2-issue-2-execution-record) owns the bounded distro
integration review, repeatable live/installed qualification and current-package
case 50 results on both targets. Both VMs are stopped with baseline restoration
verified. Phase 2 is **2/2 issues solved**, with its exit gates passed; this
session stops before Phase 3.
The five work groups below remain the complete confinement scope;
group 2 is closed and the remaining obligations are arranged into four phases.
The current plan supersedes historical
continuation orders and upstream-only repair requirements in this record.

**Previous corrective continuation: 5/10 issue groups reported resolved, 5/10 open.**
This progress count describes completed corrective engineering work; it is not
50% release acceptance. That continuation's affected unit scope passed 3,260/3,260.
Its Ubuntu package passed the confinement matrix, but public approval failed
because its authentication agent aborts in the SVG/glycin dependency path.
Fedora qualification was pending at that boundary. Those exact inputs and
results remain in [the previous corrective continuation](#independent-review-and-corrective-continuation-on-october-12).
The [current phase-1 record](#phase-1-execution-record) owns subsequent source,
validation, cleanup and the narrowed issue count; earlier results do not qualify
the new packages.

The accumulated implementation and test changes were reviewed together. The review
corrected these reproducible defects and reduced shared parsing/collection code:

- PAM audits ignored `@include` separated by a tab, including early-success
  rules, pre-gate daemon callbacks and manager credential callbacks hidden in
  that include. A shared logical-line parser now handles spaces, tabs and
  backslash continuations, preserves vendor bytes, rejects unsupported syntax
  and never substitutes vendor input for a dangling local override. Include
  resolution is shared by control-flow, callback and credential audits.
- SELinux type declarations came from an unordered Python set, making generated
  policy and package bytes depend on the interpreter's hash seed. Role ordering
  is now explicit; a regression compares separate generator processes with
  different hash seeds. AppArmor generation also reuses one transition map.
- The RPM installer checked a package-name prefix inside its NEVRA string,
  admitting another package such as `oh-no-parent-control-2-other`. It now
  compares the independently queried package name exactly before invoking DNF.
  Both formats retain literal frozen-artifact paths and reject foreign names.
- A failed pidfd acquisition leaked the final-exec probe's unreaped fork child
  and pipe. Cleanup now owns that child before acquisition, kills/reaps only
  that still-unreaped direct child on failure, and closes its descriptors.
  Empty nested-caller output also produces the explicit missing-result refusal.
- Failure collection was defined only on `KioskEntryJourney` but called by a
  qualification base inherited by other journeys. Those failures raised
  `AttributeError` instead of collecting evidence. The bounded guarded collector
  now belongs to their shared `InstalledJourney` base; entry, duration and parent
  journey regressions exercise that inherited contract.

The Fedora handoff failure has a source-backed and live-probed correction.
Systemd v259's [manager socket setup](https://github.com/systemd/systemd/blob/v259/src/core/manager.c)
creates an `AF_UNIX` datagram socketpair; its
[executor](https://github.com/systemd/systemd/blob/v259/src/core/exec-invoke.c)
writes the handoff timestamp before `execve`. The current-domain PAM transition
changed the writer to `manager-pam`. A new live AVC with dontaudit disabled
identified the inherited socket as `kernel_t`, disproving the earlier `init_t`
assumption. Existing `fd:use` and peer `sendto` grants do not grant socket
`write`. Source now grants only `manager-pam -> kernel_t unix_dgram_socket:write`
for that operation. A second failure required `noatsecure` solely for the private
manager transition, preserving the trusted executor/PAM environment so
libsystemd can read `XDG_RUNTIME_DIR`. With both exact supplemental rules,
manager and native-service startup and normal manager stop succeeded. This
diagnostic experiment does not qualify the final package or all teardown paths.

The GDM save-timing marker has been removed from admission: valid preferences
are read-only checks, wrong preferences are repaired and denied, and the required
final MAC gate enforces the real executable. Phase 2 issue 1 implements an owned
AccountsService classification adapter; both targets pass its live, installed,
reboot and public regression gates in its execution record below.
The final installed/public matrices pass in the resumed Phase 1 record;
earlier package/snapshot digests below are historical.
Current validation is recorded at the end of this document; historical handoff
instructions are superseded by the current findings and remaining-work sections.

## Phased execution plan (current)

**Next phase: 3 — Qualify security and required functions. Not started.**

**Phase 2 is complete: 2/2 issues solved and all exit gates passed.** Issue 1
completed the owned account-recovery workaround. Issue 2 completed bounded
distro review and live/installed qualification, followed by public case 50 on
both targets. Their execution records retain exact inputs, evidence and owned
cleanup. The user requested stopping before Phase 3; no Phase 3 work was run.

- [x] **Issue 1 — Retained-hidden account recovery.** The owned,
  metadata-preserving AccountsService workaround qualifies fresh,
  retained-visible and retained-hidden records, retry/interruption recovery,
  daemon restart and reboot on both targets; current-package case 50 also passes.
- [x] **Issue 2 — Bounded distro integration review.** Exact distro
  executable/WirePlumber/Lua/native-plugin/service-API review and bounded live
  and installed qualification pass without broad executable routes; affected
  host checks and current-package public case 50 pass on both targets.

**Phase 1 closed after all exit gates passed.** Issues 1–3 are **3/3 solved**.
The final native-gate packages pass both installed matrices, both strict real
waiting-session censuses and all six public approval, denial and cancellation
histories. Affected host checks and both package builds passed after the final
product edit. The [final execution record](#resumed-phase-1-exit-gates--final-installed-inputs)
identifies the exact inputs, reports, retained evidence and owned cleanup.
That Phase 1 continuation stopped at its boundary without Phase 2–4 work.

To resume, say **"execute Phase 3 in confinement.md; stop before Phase 4"**.
Read `AGENTS.md`, this
record and the applicable linked contracts, then execute only the phase named
by this pointer. An unfinished phase remains the next phase; an update to this
plan alone never closes it. Record exact current-input results, remaining
limitations and owned cleanup here. Only after every exit gate for that phase
passes, check its row and advance the pointer to the next unchecked phase.
Stop at that boundary so another session can use the same instruction. Preserve
all pre-existing work.

For **"execute next open issue in confinement.md"**, execute only the first
unchecked issue in the active phase's issue checklist, record its validation
and owned cleanup, then stop at that concrete issue boundary. **No unchecked
issue remains in Phase 1 or Phase 2's issue checklists, and their exit gates
pass.** The phase pointer selects Phase 3. Completing an issue checklist never waives its
phase's exit gates.

The user accepts proper product-side engineering workarounds and explicitly
instructed us not to chase upstream fixes. Evaluate a workaround by its supported
interfaces or explicitly owned/versioned integration, bounded changes, metadata
preservation, failure recovery, safe retry and durable restart/reboot behavior.
Do not use unrelated-property toggles, fabricate evidence or weaken enforcement.
Phase 2 must reconcile any older upstream-only requirements in the owning design
before implementing its replacement. No upstream campaign or published upstream
fix is a prerequisite of this plan.

| Done | Phase | Work-group allocation | Required exit gate |
| --- | --- | --- | --- |
| [x] | **1 — Restore authentication** | Group 1's Ubuntu SVG/glycin failure and actual Snap activation source; group 5's Fedora password-helper measurement and any necessary finite pinning/census integration | Passed: actual loader diagnosis/fix, installed Snap suppression, real public approval/denial/cancel (cases 50–52), final-package confinement matrices and strict real waiting-session censuses on both targets; [final evidence](#resumed-phase-1-exit-gates--final-installed-inputs) |
| [x] | **2 — Finish compatibility engineering** | Group 2's retained-hidden-account workaround; group 5 distro executable, WirePlumber/Lua/native-plugin/service-API review | Passed: metadata-preserving fresh/retained-visible/retained-hidden recovery, retry and restart/reboot on both targets ([issue 1](#phase-2-issue-1-execution-record)); exact distro review, live/installed platform qualification and current-package public case 50 on both targets ([issue 2](#phase-2-issue-2-execution-record)) |
| [ ] | **3 — Qualify security and required functions** | Remaining group 1 cases 53–57, 151, 191, 192, 254 and 259; group 3 teardown/namespace/ordinary-user obligations; group 4 feedback/scanner/notifications/Wellbeing | Final current-package live checks on both targets, actual scanner observations, editor/diagnostic download without sending feedback, and complete required ordinary-user/settings behavior; explicitly resolve the unregistered natural-reminder 311/311b obligations rather than counting a preview as acceptance |
| [ ] | **4 — Qualify package lifecycle and close confinement** | Remaining group 3 removal/reboot/reinstall/purge/retry/foreign-state history; group 5 genuine DEB upgrade and final integrated review | Genuine v1.2 DEB upgrade/activation/reboot, complete lifecycle and final affected regressions on both targets; review all tracked/untracked confinement changes and prior partial fix; reconcile every open obligation and limitation before closure |

Phase 1 includes only supporting changes necessary for those authentication
outcomes. Diagnose Ubuntu's terminal loader failure before granting permissions.
Measure Fedora's actual native password helper while the prompt waits, before
password submission, using the exact identity and mount requirements in
[the qualification routes](#continuation-order-and-qualification-routes).
Only measured, independently pinned behavior can justify a finite test-only
helper role. Unknown labels and every `init_t` kiosk thread remain rejected.
No production interpreter exception or census relaxation is authorized.

Use bounded parallel subagents for independent diagnosis/review and the maintained
VM queue within its configured cap. One editor owns shared policy integration;
each VM retains exclusive ownership and ordered operations. Finish maintenance
before qualification. Run affected host checks and `make build` after the final
package edit, then use verified format-specific inputs and normal snapshot
matching. Subsequent product edits require the affected qualification again.
Keep source/host, installed engineering and customer results separate.

**Whole-topic completion:** all four phases must satisfy their exit gates and
all five work groups must be reconciled, with no unresolved confinement defect
or required acceptance silently dropped. An absent genuine prior RPM remains
unavailable historical-upgrade coverage; never manufacture a predecessor or mark
that result passed. Any remaining limitation which prevents required acceptance
keeps closure open until the user explicitly accepts that scope limit. The
implementation remains not release-qualified until final integrated review and
the required current-input checks pass on both targets.

## Scope, repository and starting point

- Repository: `/Data/Code/PST/parent-control`, on the development host.
- HEAD at the original handoff:
  `8c64e1422246df793b9b7b952c6b5c3fecd1126f` (`TA: checkpoint for 181m`).
  That checkpoint contains unrelated countdown-automation work; preserve it.
- Original partial confinement fix:
  `3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc`,
  `Harden kiosk PAM session routing and admission diagnostics`.
  Its parent is `697a4c30` (`TA: Completed task 052a`).
- `7e78a97c` added the previous `docs/confinement.md` brief. Its original contents
  remain available through Git history. The working tree was initially clean.
- The subsequent confinement changes accumulated as tracked and untracked work.
  The progress checkpoint below preserves that complete implementation, test
  and documentation state. Ordinary diff output omits untracked file contents.
- Artifact builders at the original handoff reported revision `3e0f2af6f9c4`;
  that metadata is not a claim that HEAD equals that commit, nor that package
  contents match its committed tree. Inspect frozen input/package hashes.
- No product installation was performed on the development host. Do not return
  to, modify or reinstall the released incident machine.

User requirements are to fix the original routing defect and all confinement
gaps, cover and test both Ubuntu and Fedora, preserve required kiosk functions,
add a one-line v1.4 bug fix, and ultimately supply a detailed independent-review
handoff including the preceding partial fix. The latest execution completes
Phase 1 on both installed targets, including the final censuses, confinement
matrices and public approval histories. The user then requested a progress
commit of all active changes and a reconciled handoff for the next phase in a
new session. Phase 2 had not started at that historical boundary. The broader
confinement work remains
unfinished; the current terminal state and evidence are at the end of this
record. Earlier handoff statements describe their respective historical
boundaries, not current acceptance.

The scope remains that the child can use only the kiosk app and its necessary
services. The user specifically requires live VM probing when failures occur
and live validation of fixes before E2E, rather than treating guests as log-only
black boxes. Reuse the maintained, already-authorized VM routes; no broader shell,
network or libvirt grants are needed for these probes.

The v1.4 entry in [Version history](VersionHistory.md) is already added:

> **Kiosk**: Fixed unintended desktop access by restricting the kiosk account to the request app and its required services.

That entry describes the intended completed fix; it is not evidence of current
acceptance. What's New translations have not been synchronized, as requested by
the repository's explicit-request localization rule.

## Incident and original cause

The incident machine ran Ubuntu 26.04.1, GNOME 50, GDM 50.1 and product
`1.4+local1~ubuntu26.04.1`. The reserved `oh-no-parent-control` account was UID
1002 there. An earlier October 11 boot started GNOME Kiosk and the request app;
a later boot admitted that same account to ordinary Ubuntu GNOME, including
`gnome-shell --mode=ubuntu` and normal desktop applications. Subsequent public
AccountsService reads showed `Session="ubuntu"`, `XSession=""` and
`SessionType=""`.

No relevant product/GDM/AccountsService/GNOME upgrade occurred between those
logins. The user did not know whether someone used GDM's session selector or
whether this was the first login after a reboot. The exact initiating event is
unproven and must not be invented in review or release explanations.

Provisioning a preferred session never enforced execution. GDM 50.1 does not
invoke the legacy PreSession hook, and the old PAM helper admitted any
`gdm-password` login for the reserved account. Those mechanisms were materially
unchanged since v1.0. The evidence supports an original conditional confinement
gap rather than a demonstrated regression introduced after 1.0. A usually
correct preference explains why the gap could remain hidden, not what changed
the preference on this machine.

## Preceding partial fix: review it as part of the whole change

Commit `3e0f2af6` introduced required native PAM account/session checks and a
root-owned, mode-0600, no-follow `/run/oh-no-parent-control-kiosk-login.lock`.
The lock serializes authorization through session opening. A bounded native
helper invocation retains the lock if its PAM worker aborts, reaps its owned
child, and handles closed standard descriptors.

The account stage verifies the dedicated Wayland default, then writes the
AccountsService marker `oh-no-parent-control-verification-pending`. GDM must
replace it with its saved selection before `pam_open_session`. The session
stage requires the dedicated saved selection and actual Wayland transport.
The marker prevents an unsuccessful settings save leaving a stale correct
default that appears to attest a different selection. Incorrect/interrupted
routing is repaired through public AccountsService setters, but that attempt
remains denied; a subsequent attempt may retry. Unverifiable state fails closed.

The fixed-purpose Python helper uses isolated startup (`-I`), a clean environment
and bounded noninteractive system-bus calls. Provisioning sets and reads back
both `Session` and `SessionType`; Ubuntu/Fedora PAM integration was updated.
Fixed-category admission/recovery diagnostics omit usernames, arbitrary session
strings, exception text and command stderr. These are local journal diagnostics,
not a new automatic feedback-export channel.

Principal prior files are [native PAM](../tools/pam_oh_no_parent_control.c),
[login helper](../tools/oh-no-parent-control-login-check) and
[provisioning](../tools/provision.py). Relevant current design owners are
[Lifecycle](SystemDesign/Lifecycle.md) and
[Logging and feedback](SystemDesign/Logging-and-Feedback.md).

The prior fix did **not** implement a final execution boundary or account-wide
sandbox. GDM saves its session before PAM opens but supplies `GDMSESSION` later;
the final selected command can differ after admission. `systemd-user` routing
was intentionally exempt, and existing child fapolicyd policy excludes the
kiosk account. A nologin shell and disabled desktop controls alone are inadequate.

Original validation was 171 selected host cases across kiosk login, PAM runtime
cap, provisioning, Fedora PAM, RPM packaging and regression inventory modules:
170 passed initially; one new fixture incorrectly executed a nonexecutable
checkout source, was corrected to copy identical bytes with executable mode,
and passed narrowly. There was no subsequent full 171-case rerun at that
boundary. Both DEB/RPM `make build` outputs passed, documentation links checked
62 targets with none missing, and `git diff --check` passed. No live GDM or VM
acceptance was completed on the incident machine.

A prior incident-host `make install` stopped at sudo authentication before
package changes and was cancelled cleanly. The user received local installation
instructions, but whether they later ran them is unknown. No reboot/logout/GDM
restart was performed there. Reusing the same version cannot identify whether
that machine received the partial fix.

## Current candidate execution boundary

### Native PAM and prepared executable view

[Confinement integration](../packaging/kiosk_confinement.py) adds an early account
integrity check and a required final session gate to `gdm-password` and
`systemd-user`. The final gate is after vendor callbacks. It executes in the
actual PAM caller, including systemd's parent executor, not only in a helper
that would leave its eventual user manager outside confinement.

[Native confinement](../tools/kiosk_confinement.h) takes an exclusive validated
root-0600 runtime lock, creates and validates the root-0700 runtime directory
in the actual caller's domain, invokes a bounded root preparation helper, constructs a
private recursively read-only mount view, clears PAM-granted ambient
capabilities, and installs the MAC boundary. No subprocess runs after the final
MAC operation. Any failed prerequisite returns a PAM session error.

Ubuntu uses immediate `aa_change_profile` and reads back the enforcing label.
An earlier `change_onexec` approach was rejected because an unconfined caller's
first executable was not checked against the destination policy as required.
Fedora's GDM caller sets and verifies a pending raw SELinux exec context; the
kernel checks the actual next executable's private entrypoint type. Its systemd
caller now clears the vendor pending context and enters a restricted current
`onpc_kiosk_manager_pam_t` domain through `setcon_raw`. The trusted executor is
single-threaded; the kernel must reject an unsafe dynamic transition. The only
exec routes from this domain are the private manager/executor entrypoints.
The forked `sd-pam` child inherits a confined current domain through teardown.
There is no reverse dynamic-transition grant and no census exception for
`init_t`. Later historical packages passed real Fedora entry and the strict census;
the final current package still requires Fedora requalification.

[Preparation](../tools/kiosk_confinement.py) verifies root-owned policy/state,
the package-created account, loaded enforcing policy and a finite native ELF
inventory. It copies independent executable inodes into private runtime storage;
it neither hardlinks nor relabels global distro executables. Inventory identity
uses content and canonical paths, so an identical-byte reinstall is compatible.
Canonical aliases are deduplicated; conflicting roles are refused. Optional
blocked shared libraries may be mode 0644 rather than executable.

The mount tree owns independent directory dentries from `/usr` down to every
protected executable/library/plugin parent. Trusted siblings are pinned with
recursive read-only binds; private copies occupy the owned file entries; the
completed tree is attached over `/usr` last. Native code validates the bounded
binding manifest and pins source/target descriptors before mounting.

This replaces an unsafe earlier design that mounted individual files onto
shared global dentries. Package unlink/rename can detach mounts on those dentries
across namespaces (`detach_mounts`), exposing a replacement. Do not revert to
per-file binds into the shared directory tree. Exact installed versioned
`libsystemd-*.so` private libraries are copied and pinned alongside systemd so
package-triggered manager reexecution remains coherent. The GStreamer plugin
parent is reserved even when `libgstpython.so` is absent.

Limits are four completed generations per boot, 512 MiB of ELF/library input per
generation and 32,768 directory entries. Interrupted owned preparation is
reclaimed under the lock; completed generations remain until reboot. Root-only
runtime storage prevents the kiosk accessing unmounted private copies directly.

GDM admission requires a live user manager with the expected UID, exact enforcing
manager label and the same generation visible through its `/proc/.../root`.
Stale managers deny with reboot-required diagnostics. Configuration never kills
or silently restarts them. The generation includes payload/policy identity, and
admission also verifies successful policy-load attestation rather than trusting
that matching domain names imply current rules were loaded.

### PAM ownership, control flow and pre-gate children

The integration records exact original and generated PAM bytes, follows trusted
distro symlinks, rejects unsafe nonregular/hardlinked files, and verifies the
vendor source of a generated `/etc/pam.d/systemd-user` override. It preserves
foreign edits. Vendor changes require reconfiguration; `.dpkg-dist`/`.rpmnew`
candidates with changed original PAM bytes require explicit reconciliation.
Multiple interrupted vendor refreshes preserve the exact still-published owned
generation, not merely the most recently attempted one.

Session control flow is expanded and validated against early success and jumps
that can skip the final gate. Includes and substacks are separately audited.
Linux-PAM accepts case-insensitive spellings; the parser now refuses
noncanonical `SESSION`/`OPTIONAL` variants instead of silently missing them.

Stock `pam_gnome_keyring.so auto_start` can fork and run a daemon before the
final gate, even without a password. A direct optional vendor keyring callback
now receives this kiosk-only guard:

```text
session [success=1 auth_err=ignore default=die] pam_succeed_if.so quiet user = oh-no-parent-control
```

Ordinary users retain the callback; errors fail closed. Nested/nonoptional
keyring callbacks and unknown session modules are refused. Jumps crossing guard
insertion are rejected using the original expanded positions. Verification
re-renders from recorded original/vendor input every time, so a later included
stack edit cannot start jumping over an existing guard.

The current accepted module inventory includes `pam_selinux`, `pam_loginuid`,
`pam_keyinit`, `pam_limits`, `pam_env`, `pam_unix`, `pam_sss`, `pam_systemd`,
`pam_systemd_home`, `pam_umask`, `pam_succeed_if`, `pam_lastlog2`, `pam_permit`,
`pam_deny` and the product module. The continuation removed `pam_namespace` from
that accepted callback inventory. Direct optional/required/requisite namespace
entries receive the kiosk-only guard on both open and close; nested entries and
jumps crossing the guard are refused. Active namespace configuration and its
init/cleanup scripts are consequently unreachable for the kiosk, while vendor
bytes/options remain effective for ordinary users. Supported `systemd-user`
stacks contain no auth group; new auth/setcred callbacks, including through
`@include`, are refused at configuration and admission. Host coverage passed;
installed open/close and ordinary-user verification remains outstanding.

### Fixed launchers and role policy

[The policy generator](../tools/kiosk_confinement_policy.py) emits separate
AppArmor/SELinux role policies and an executable manifest. Roles cover the final
GDM gate, user manager, GNOME session, necessary native services, fixed request
app/notification/wellbeing/audio launchers, PipeWire, Polkit, diagnostic package
query, locale, bubblewrap, WebKit and its plugin scanner. Generic Python, GJS,
shell, GNOME Shell and arbitrary WirePlumber entry are not granted to the manager
or general service role.

[Native fixed launchers](../tools/kiosk_session.c) reject caller arguments and
clear code-injection environment variables. Their fixed actions include:

| Launcher | Fixed destination |
| --- | --- |
| session | `gnome-session --no-reexec --session=oh-no-parent-control` |
| app | `python3 -I /usr/bin/oh-no-parent-control` |
| notifications | Isolated Python running the installed notification script |
| notification-client | Isolated Python `gnome-service-client` with a fixed tag and native notifications launcher |
| wellbeing | `gjs -m` with the installed wellbeing service script |
| cleanup | `systemctl --user unset-environment` for declared display variables |
| audio | WirePlumber with system-only config/data roots for the kiosk |
| packages | RPM query for the fixed 20-package diagnostics inventory, root-only configuration/macros, `HOME=/` |
| dbus | Fedora `dbus-broker-launch --scope user`, after clearing startup configuration in the service domain |

The audio wrapper preserves the original environment for ordinary users. The
kiosk branch fixes `WIREPLUMBER_CONFIG_DIR`/`WIREPLUMBER_DATA_DIR` and drops user
module/configuration injection. The optional native GStreamer Python plugin
cannot acquire executable mappings in the confined view. The package diagnostics
change preserves useful Fedora feedback information without admitting a generic
RPM interpreter/macro route. The shared request launcher now has an isolated
Python shebang, which also affects the child-overlay entry and needs regression
coverage.

The distro's native foreground Polkit agent replaces Ubuntu's shell launcher;
Fedora's former special-case rewrite is removed. The ordinary authenticated
setuid password helper remains narrowly reachable from the Polkit role. Broker,
D-Bus and Polkit authorization still govern data and administrator authority.
The execution policy does not grant the kiosk parent authority. Compromised
root/kernel policy/administrator credentials are outside the attacker model;
ordinary service APIs and user-manager unit files remain in scope.

### Ubuntu compatibility work and what is not yet proven

Live Ubuntu initially failed starting its manager with `CAPABILITIES`/218:
`pam_systemd` grants regular local/user-manager sessions `CAP_WAKE_ALARM`, while
AppArmor's `capget` masks it from the permitted set. Systemd then tries to raise
the ambient set read after PAM. Clearing all ambient capabilities before the
profile fixes this measured failure. A confined Ubuntu manager and a positive
`systemd-run` of `systemctl --version` subsequently succeeded.

The next measured failure was AppArmor `info="no new privs"` on wellbeing and
PipeWire role transitions. Ubuntu AppArmor cannot use a nonmonotonic profile
transition under `NoNewPrivileges` merely because an exec rule allows it.

Current source gives **only the kiosk manager** this PAM environment entry:

```text
SYSTEMD_UNIT_PATH=/usr/share/oh-no-parent-control/confinement/user-units:
```

The trailing colon retains normal systemd unit search paths. The generated
root-owned Ubuntu drop-ins disable `NoNewPrivileges` for wellbeing, and disable
it plus the measured implicit-NNP settings for WirePlumber:
`LockPersonality`, `MemoryDenyWriteExecute`, `SystemCallArchitectures` and
`SystemCallFilter`. Other users and compatible service hardening remain intact.
This is a deliberate compatibility tradeoff requiring live verification of
effective settings and fixed interpreter entry. No PipeWire override is emitted.

Native PipeWire has its own zero-exec role and stacks with the current manager
or service profile, retaining its vendor NNP/seccomp settings. Bubblewrap enters
normally, then its NNP-protected WebKit payload stacks restrictions, with scanner
execution adding a third profile:

```text
onpc-kiosk-manager//&onpc-kiosk-pipewire
onpc-kiosk-bwrap//&onpc-kiosk-webkit
onpc-kiosk-bwrap//&onpc-kiosk-webkit//&onpc-kiosk-scanner
```

The WebKit/scanner intersection removes bubblewrap's mount/user-namespace
authority. Scanner trusted-read and executable restrictions remain. Bubblewrap's
service transition is limited to `xdg-dbus-proxy` rather than the full native
service inventory. Its mount rules allow the declared WebKit layout while
preserving trusted executable path identities. Policy compilation passes.
Packaged Ubuntu scope `41dc9a30…222ee` passed real entry, the strict census,
wellbeing startup and effective unit-setting checks during this continuation.
**The real WebKit/scanner sandbox and final-source installed/public matrices
remain unqualified.** Do not replace these with broad interpreter
exec or shared unrestricted `ix` rules to make a test pass.

### Fedora compatibility work and what is not yet proven

Before the current `manager-pam` rewrite, the installed Fedora manager reached
`system_u:system_r:onpc_kiosk_manager_t:s0`, but earlier candidates failed to
start their user bus. Iterative owned diagnostics identified required permissions:
`setfscreate`, `setsockcreate`, SELinux `compute_create`/`compute_av`, runtime
socket activation in the eventual service domain, and systemd unit
start/stop/status/reload checks. Runtime copies are on a nosuid mount, so private
exec transitions also need SELinux `process2 nosuid_transition`.

An earlier diagnostic denied creating the bus `sock_file` labelled
`session_dbusd_tmp_t`. Current source limits the executable/library write
exclusion to regular files, allowing non-executable socket objects to use vendor
labels even where those labels also carry executable-type attributes. Manager
activation can create service/PipeWire-labelled Unix stream/datagram sockets.
Further October 12 diagnosis established the separate Fedora object-identity
constraint: the manager's fixed `system_u` SID creates vendor-labelled sockets
carrying `unconfined_u`. Source now gives only the manager
`can_change_object_identity`; it adds no process-identity or executable-file
creation/relabel permission. The service role also needs `security:compute_av`
for D-Bus userspace policy checks. Destination domains need executable mappings
of their own private entrypoint ELF, in addition to `entrypoint`; this adds no
`execute_no_trans` route.

Temporarily exposing dontaudit messages identified lost inherited Unix-stream
socket I/O after transitions, including journal output. Source grants that I/O
under the existing data/IPC boundary. The restored journal/stderr then showed
`dbus-broker-launch` failing in `sd_bus_open_user` with `ENOMEDIUM`: secure
execution makes libsystemd ignore the runtime-directory environment. A new
fixed native dbus launcher clears startup configuration and execs the broker in
the same service domain. No SELinux `noatsecure` permission is granted. Fedora
now receives a kiosk-only unit-path override for this launcher; Ubuntu retains
its two compatibility overrides. These changes have historical packaged positive proof below; current-package
qualification remains distinct.

The next fresh Fedora package started its bus, exposing a userspace SELinux
`dbus:acquire_svc` denial for the manager and wellbeing names. Unmapped names use
the broker's SID as their target; a self-only grant was insufficient. Source now
allows confined domains to acquire names on the confined service-domain bus,
without granting acquisition against arbitrary system-bus service labels.
An owned supplemental-policy probe completed `systemd-run --user` of
`systemctl --version` with status 0 and independently read `SystemAccount=false`.
Its manager and temporary module were cleaned successfully. This is diagnostic
proof of the correction, not acceptance of the subsequently rebuilt package.

Temporary supplemental diagnostic CIL modules were used only in owned Fedora VM
maintenance, named `onpc-confinement-diagnostic`. Each run checked absence first,
recorded its manager InvocationID, and stopped only that instance and removed
the module in `finally`. Subsequent runs also used temporary owned logging
drop-ins. All completed diagnostic runs removed their modules/drop-ins and
stopped their recorded managers. The dontaudit diagnostic restored normal
policy with `semodule -B`. No temporary diagnostic policy qualifies acceptance.
Optional systemd generator and BPF denials were observed and were not blindly
converted into allow rules.

### Packaging, activation and removal

[Makefile](../Makefile) owns compilation/install of native launchers, PAM linking
with `-ldl`, generated per-distro policy, preparation/integration helpers and
system/user units. New sources are in `PACKAGE_SOURCE_FILES`. Debian dependencies
include AppArmor/libapparmor; RPM dependencies include the SELinux runtime and
policy tooling. Both package families share the lifecycle templates.

Display-manager integration wants/orders the confinement-policy load service.
PAM admission still denies if policy is unavailable, regardless of service
startup ordering. Both provisioning paths use a nologin shell. The installed
session desktop file, app/notifications/wellbeing units, wellbeing D-Bus
activation, GNOME Kiosk cleanup and WirePlumber route through the native boundary.

Post-install configures confinement after distro PAM enablement. Native PAM,
fixed launchers, confinement policy/preparation and PAM/login integration changes
classify as **reboot**, because a user manager can survive graphical logout.
Aborted installation/removal paths preserve ownership and restore owned state.
Removal verifies exact PAM ownership and refuses live processes carrying the
package-created UID; it never kills them. It restores original local files,
removes only its vendor-derived override, unloads policy and removes the record
after success. Foreign edits remain and block removal. Completed runtime
generations remain until reboot.

Read [Package removal](SystemDesign/Package-Removal.md) and
[Publishing](Publishing.md) with the code; installed upgrade/removal lifecycle
qualification remains outstanding.

The first current Ubuntu GDM attempt stopped before station selection:
`ui:gdm-account-cardinality` reported a hidden station node. Live Fedora public
AccountsService reads likewise showed `SystemAccount=true`, `Locked=false`
with the new nologin shell. AccountsService classifies nologin accounts as
system accounts. The first implementation used public `CacheUser` and an unrelated pending-session
toggle. Review rejected that toggle as a persistence contract. Current provisioning
preserves a saved visible account, caches a fresh account with verified public
properties, and refuses a saved hidden account before mutation. AccountsService
23.13.9 cannot publicly persist the existing cached classification while preserving
all metadata. The exact limitation and the current owned product-workaround
direction are recorded in [the release blockers](#release-blockers-and-remaining-proof).
Historical reboot-visible and real-entry results do not remove that API limitation.

## Installation tooling correction made during this work

The shared VM setup recipe previously invoked package managers directly,
contrary to the current repository requirement that this checkout install only
through `make install`. It now invokes the frozen checkout Makefile:

```text
make --no-print-directory -C <payload>/install-source install
INSTALL_PACKAGE=<absolute exact supplied package>
APT=apt-get -o DPkg::Lock::Timeout=120 --no-install-recommends -y
DNF=dnf -y
```

Those are separate argv entries, not a shell command assembled from the path.
`INSTALL_PACKAGE` supports the current or previous explicit artifact. Make
exports its literal value through `ONPC_INSTALL_PACKAGE`; identity and extension
are validated before the existing dependency-resolving install/reinstall path.
The normal no-override local build lookup remains supported. Tests include
literal filenames containing spaces and `$(false)` for both formats.

Affected owners are [guest install recipe](../tests/integration/guest_install_recipe.py),
[installed setup](../tests/e2e/installed_setup.py),
[system runner](../tests/integration/system_runner.py) and
[app snapshot identity](../tests/e2e/app_snapshot.py). Frozen inputs include
`install-source/Makefile`, and snapshot recipe identity includes its hash as well
as the recipe closure. Existing customer package-manager acceptance actions
remain their supported apt/dnf workflow; this correction concerns checkout
installation during preparation. Both guests successfully installed through the
new Make entry in the prior completed preparation run.

The continuation also corrected `system_guest.upgrade`, whose update transaction
still used apt/dnf directly. It now calls the same Make recipe after its second
identity guard and retains the prior/new package-file, digest and reboot checks.
The corresponding host expectations now cover Make for initial, prior and new
artifacts on both distributions; same-version choice remains independently
exercised by the Make installer tests.

## Maintained tests added or extended

[Confinement host tests](../tests/unit/test_kiosk_confinement.py) cover PAM
ownership/retry, unsafe files, vendor drift, pending distro replacements,
multiple interrupted updates, control-flow shortcuts, keyring guards, nested
updates, case handling, policy-load identity, executable alias conflicts,
non-executable shared libraries, owned directory skeletons, AppArmor compilation,
the two narrow NNP overrides and fixed launcher argv/environment behavior.
[Kiosk login tests](../tests/unit/test_kiosk_login.py) cover integrity dispatch and
compile/use the actual native PAM source with private fixtures.

Installer, systemd units, package payload/activation, RPM packaging and system-info
expectations were updated to the candidate's actual public paths. Test source
freezing and graphical/package-authority cleanup-safety inventories were updated
for the Make recipe and helper inputs. New host module compatibility is recorded
in [the unit inventory](../tools/regression_unit.py): private filesystem/native
compiler fixtures, no host PAM/policy loads, and parser `-Q` compilation only.

### Installed engineering matrix

[system_kiosk_confinement.py](../tests/integration/system_kiosk_confinement.py)
is called by `test_kiosk_execution_confinement` in
[enforcement tests](../tests/system/test_enforcement.py). It:

1. Starts only an inactive/failed manager, records InvocationID and verifies
   its exact enforcing label. A successful allowed `systemctl --version` via
   the user manager is required before negative tests.
2. Requires exec failure 203 for direct shell, Python, GJS, GNOME Shell,
   GNOME Session and WirePlumber user services.
3. Tries a kiosk-owned copied executable, interpreter alias and a user-owned
   runtime unit with `ExecStart=+/bin/sh`. It uses exclusive creation and checks
   inode ownership before removal; it cleans only its own files/directories.
4. Replaces systemctl and exact systemd private libraries using owned temporary
   backups while retaining their original inodes/labels for restoration. It
   verifies old bytes through the manager's private root before/after the
   supported synchronous user-manager reexec (`Type=notify-reload`, signal 59),
   then requires another positive service.
5. Renames/replaces the plugin parent directory and verifies new gst-python
   input does not appear in the live manager view.
6. Mutates inventory identity and requires stale-manager denial without a
   restart; restores it and verifies the original manager remains.
7. Uses a real native PAM final-session call in a bounded owned fork, then the
   actual exec. It checks a positive GDM entry plus shell/interpreter/desktop,
   explicit ELF loader, already-open FD and memfd negative cases. A pidfd-backed
   75-second bound kills/reaps only that exact spawned test child on timeout.
8. Stops only its recorded manager before policy-loss probes. PAM/vendor drift,
   changed-but-unloaded policy, Ubuntu complain/unload and Fedora global or
   per-domain permissive/module-unload must deny; restored policy must admit.

Review the harness itself before trusting results: negative return values must
represent the boundary under test, not an unavailable manager/bus. Faults and
replacement operations are engineering probes, not customer actions.

### Real GDM process/thread census

[Kiosk-entry qualification](../tests/e2e/kiosk_entry.py) now invokes a guarded
read-only `census` after its public request-form observation and before releasing
the next worker stage. This is the separate engineering qualification, not an
assertion inserted into ordinary customer scenario classes. The helper is frozen
in installed setup inputs and uses the existing guarded transport/watch.

The census checks every process with any UID field equal to the kiosk account,
each surviving thread's MAC label, a private mount namespace and the manager's
generation marker through each process root. It emits only role/thread counts,
not command lines or account data. It requires manager, app, service, wellbeing
and PipeWire roles so absent required services cannot count as success.

Ubuntu passed a strict live census after real GDM entry on package scope
`41dc9a30…222ee`, including wellbeing. This was an engineering probe following
the maintained diagnostic entry action, not a completed customer scenario or
final-source qualification. Exact evidence is at the end of this record.

The previous Fedora waiting-helper exception has been removed from source.
Every surviving kiosk thread must now have an enforcing kiosk current domain;
`init_t` is rejected even for `sd-pam`. A pending SID, parent identity or process
name cannot substitute for confinement. The replacement `manager-pam` domain has historical real Fedora entry evidence;
current-package lifecycle and public workflow proof remain separate. Host census
tests cover both MAC backends, other-user filtering, unconfined threads, the
obsolete PAM domain, process replacement and manager replacement. The lower
test count reflects removal of tests for the discarded exception, not acceptance
of its behavior.

## Review findings and acceptance status

The current unresolved findings are centralized in
[Release blockers and remaining proof](#release-blockers-and-remaining-proof).
Historical failures and package identities below remain causal evidence; they
must not be read as current execution instructions or current acceptance.
In particular, the later timestamp/noatsecure correction supersedes the earlier
Fedora startup blocker, and the new admission barrier supersedes the earlier
removal design. Neither closes the remaining installed/public obligations.

The original controlled routing reproduction remains useful: on a disposable
supported unpatched guest, use public AccountsService setters to seed the known
alternate-desktop preference, then log in graphically. This reproduces the
known gap, not the unknown original incident trigger. The candidate should
deny the wrong attempt, repair the dedicated Wayland preference and permit a
subsequent correct retry. Also exercise the command selected after PAM opens,
alternate login services, concurrent attempts and interrupted/unavailable
dependencies. The isolated native first-exec harness does not by itself prove
the actual GDM selection timeline.

The earlier reviewer agent supplied bounded advice; source review and engineering
checks do not constitute release approval.

## Validation evidence accumulated so far

Report IDs below are under `output/test-runs/host/reports/<ID>/report.md` unless
stated otherwise. Retention may remove older artifacts; do not fabricate missing
detail or treat an old report as proving later edits. Counts are per invocation,
overlap across runs, and must not be summed as unique coverage.

| Report ID | Result and scope |
| --- | --- |
| `20261012T041645Z-9cafa174` | All 130 installed-guest host regressions passed, including ten readiness cases distinguishing early kiosk admission from the required later runtime-cap callback |
| `20261012T041520Z-2695b4e3` | Ubuntu GDM qualification failed 0/1 after station-list/focus; `ui:timeout:station-default-destination`; request form/census not reached; cleanup passed |
| `20261012T041520Z-d809aa6d` | Fedora GDM qualification failed 0/1 after station-list/focus; `ui:timeout:greeter-identity`; request form/census not reached; cleanup passed |
| `20261012T041338Z-af1f3f49` | Fedora installed-matrix attempt failed snapshot-readiness preflight, `pam-runtime-cap`; selected test not executed; baseline restoration completed |
| `20261012T041253Z-18de79e5` | All 120 installed-guest host regressions passed after routing upgrades through Make, preserving digest/reboot/guard refusal matrices |
| `20261012T041008Z-4ae8bb9a` | Both added Debian removal policy-unload assertions passed |
| `20261012T040920Z-83ed19f6` | 206 removal host checks passed: package removal 147 and installed removal assertions 59, including confinement state/policy residue refusal |
| `20261012T040514Z-3f1fbaf2` | 79 confinement host checks passed, including the scoped user-bus name-acquisition rule |
| `20261012T040342Z-bf5111c2` | Ubuntu installed matrix passed 1/1 using artifact `_j3vkob4`, including reboot-persistent account visibility and effective overrides; the subsequent Fedora-only policy correction triggers refreshed final-source preparation |
| `20261012T035539Z-e252403b` | Corrected RPM activation expectation passed 1/1: native PAM and the dbus wrapper require reboot, not session renewal |
| `20261012T035431Z-e603ced7` | Packaging selection: 241/242 passed; one stale RPM activation expectation was corrected and rerun narrowly, not a full 242-case rerun |
| `20261012T035114Z-1d308ce9` | 136 passed: confinement 79, login 45, provisioning 12; includes fixed Fedora dbus wrapper, no-noatsecure policy assertion and public kiosk caching/readback |
| `20261012T034139Z-88bf4642` | Ubuntu GDM qualification failed before selection: hidden station node, `ui:gdm-account-cardinality`; census not reached; owned cleanup passed |
| `20261012T034038Z-e666457a` | 78 passed: confinement including corrected observed Fedora helper cgroup and census mixed-user filtering |
| `20261012T033334Z-8fe5be7d` | 76 passed: confinement before final cgroup/filter/dbus-launcher corrections |
| `20261012T033217Z-3bd02ce6` | Ubuntu qualification refused before acquisition because build inputs changed during preparation; no product result |
| `20261012T033015Z-4cc104f5` | Ubuntu installed confinement matrix passed 1/1, including positive service, all exec denials, replacement/reexec, policy-loss recovery, effective unit settings and removal preflights; later source edits remain unqualified |
| `20261012T032403Z-3feb7e0a` | 379 passed: system runner 161, graphical cleanup safety 191, regression inventory 27 |
| `20261012T032056Z-26e28be9` | 120 passed: confinement 75 and login 45, including namespace guards, manager credential refusal and identity-bound waiting-helper census checks; installed qualification still pending |
| `20261012T014225Z-da2680f0` | 127 passed: kiosk login 39, PAM runtime 28, RPM packaging 60 |
| `20261012T015008Z-7b0bedc2` | 124 passed: confinement 18, login 39, system info 67 |
| `20261012T020105Z-ab0ff54e` | 399 selected packaging checks: 396 initially passed, three mechanical expectation failures corrected; not a subsequent full 399 rerun |
| `20261012T020655Z-e0a31ca4` | 27 passed: affected systemd unit/package payload rerun after those corrections |
| `20261012T021221Z-0633fe4c` | 150 passed: confinement 27 and package activation 123 |
| `20261012T022250Z-91416cce` | 75 passed: directory-skeleton confinement 30 and login 45 |
| `20261012T022723Z-e1eda628` | 161 passed: system runner/frozen input checks |
| `20261012T023941Z-28bb2d2d` | 650 passed: installer, system runner, guest/setup and cleanup inventories, package authority, confinement/login selection |
| `20261012T024103Z-f76ab91d` | 84 passed: confinement 39 and login 45 |
| `20261012T024234Z-f528805f` | 193 passed: installer 32 including literal package path, system runner 161 |
| `20261012T024329Z-f4b96d63` | 40 passed: confinement including changed nested PAM guard flow |
| `20261012T024648Z-91289ffd` | 161 passed: system runner after expanding the engineering helper |
| `20261012T025611Z-7f6c3f93` | 88 passed: confinement 43 and login 45; before the final PipeWire-role/two-drop-in revision |
| `20261012T030128Z-9baa6184` | 90 passed: confinement 45 and login 45, including current policy compilation and narrow override assertions |
| `20261012T030435Z-d472376d` | 352 passed: system runner 161 and graphical cleanup safety 191, including census helper input freezing |
| `20261012T030626Z-cc5c54ce` | 661 passed: kiosk-entry and installed-journey cleanup-safety selection with its maintained dependent checks |

Earlier `check_e2e_kiosk_entry` passes used **old named snapshots**:
Ubuntu `20261012T010038Z-7f587f83` and Fedora
`20261012T010807Z-a190f4be`. They do not validate the new boundary. Same package
version and snapshot name are insufficient provenance. Explicit fresh snapshot
preparation is required before interpreting graphical results.

An earlier completed online preparation built and installed both formats through
the corrected Make recipe. Its artifact roots were
`output/test-runs/host/allocations/onpc-test-artifacts-4iv1e2nh` (Ubuntu) and
`output/test-runs/host/allocations/onpc-test-artifacts-4de92xm3` (Fedora). Installed
probes on those packages established the ambient-capability fix and the Ubuntu
positive manager/service result, plus the Fedora manager label and unresolved
socket denials. Those packages predate the latest AA stacks/unit overrides,
PipeWire role, final Fedora permissions and PAM verification refinements.

The previous handoff preparation used freshly built artifacts:

- Ubuntu: `output/test-runs/host/allocations/onpc-test-artifacts-wxs4d82x`,
  `oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`.
- Fedora: `output/test-runs/host/allocations/onpc-test-artifacts-7cj4yzr7`,
  `oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm`.

Both artifact builds and verification passed. Fresh installation, reboot,
online snapshot capture and restore/SSH/clock readiness completed with status 0
on both guests. These are preparation results, not confinement acceptance.
The real GDM census was added after this package source freeze and affects test
helpers only; it must be freshly staged and remains unexecuted.

The continuation's next completed preparation used artifacts `_j3vkob4` (Ubuntu)
and `guh6zdfc` (Fedora), under the same host allocation root. Both builds,
Make-based installs, rebooted online captures and readiness checks passed. The
Ubuntu matrix above used that exact artifact; Fedora diagnosis found the
bus-name denial described above. Both owned maintenance instances were stopped
successfully before subsequent preparation. The latest paired refresh completed with
`onpc-test-artifacts-t0f8wzar` (Ubuntu) and
`onpc-test-artifacts-uqdt79at` (Fedora). Both artifact builds, Make installs,
reboots, online captures and restore/SSH/clock readiness completed with status 0.
Both maintenance instances were then stopped serially, with successful baseline
verification and completed leases, before the final test attempts.

Both manifests record package-scope source digest
`4c4bfead6a4b38cb092da94d313af377cd07f6f5cfad1a853ca52a5b4d669e53`
over 346 package files. The artifact roots are under
`output/test-runs/host/allocations/`. Exact preparation archives are:

| Guest | Archive SHA-256 |
| --- | --- |
| Ubuntu, `t0f8wzar`, DEB | `e437760d0a1c4fae16c1fcc2fef2101e490040ec7b8a9bd9aa3e33995cbb1343` |
| Fedora, `uqdt79at`, RPM | `e5ce12dd997aba66bcdcda8667060ac36d05414bafbcff3841c00c16be67bc50` |

Read-only `tools/test-vm ... snapshots` at handoff confirmed `onpc-v1.4`
metadata records those archive hashes. The installation recipe digest in both
snapshots is `081345b7e340b7f1d6ab5a6fd287188d80797ac073b4688d6cf3e4df54462045`.
The Ubuntu normalized content digest is
`64a87ff01809dcb2117797088036311ab9305104532da7454b6c8260fb3d5d1e`;
RPM identity currently requires the exact archive hash, with no delivery-metadata
normalization. No later product edit preceded this handoff. Subsequent
`system_guest` readiness changes affect test helpers only. Older allocations
may already have rotated out; their names above are historical evidence, not an
availability guarantee.

`make build` completed successfully for both DEB and RPM after the scoped
Fedora bus-name rule. The newly extended removal engineering history also checks
that a foreign edit to active `gdm-password` makes native package removal fail
without losing payload, settings or the edit, followed by owned restoration and
retry. Removed-state checks now require the confinement record and loaded MAC
policy to be absent. These added installed assertions still require execution.

### Last Fedora matrix preflight and its host-only correction

The final Fedora matrix command selected only
`test_kiosk_execution_confinement` in system area `enforcement`, explicitly using
`onpc-test-artifacts-uqdt79at`. Report `20261012T041338Z-af1f3f49` exited 1
before that test ran. The top-level `command:failed:ssh` is a wrapper category;
the actionable failure is `pam-runtime-cap`, retained in
`output/test-runs/privileged/allocations/onpc-system-2qridp1o/private/command-0027-stderr.txt`.

`system_guest.verify_pam` previously compared the first native product account
callback with Malcontent. Fedora legitimately now has an earlier callback with
the `kiosk` argument. The runtime-cap callback is the later **required,
no-argument** call. The corrected readiness assertion requires exactly one
required Malcontent callback and one required no-argument native runtime-cap
callback, in that order. It still rejects missing, reversed, optional or
wrong-mode runtime callbacks. Ten private-file tests cover both distro layouts;
the complete affected host module passed 130/130. This changes no product PAM
expectation and supplies no installed pass. Rerun the selected Fedora matrix.

### Last real GDM attempts and retained failure evidence

The maintained command was:

```bash
tools/run-tests integration 'check_e2e_kiosk_entry' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
```

Aggregate session `491d95fbb9c145c1a3b9c4338719a737` completed with status 1;
queue results are under
`output/test-runs/host/allocations/onpc-vm-queue-8y47fw5k/`.
Both guests passed ready/setup-detached, public station-list and station-focused
observations. The worker sent Return and requested the `station-branch`
observation, but the controller never accepted that stage. A worker's
`record_info` line announcing the requested observation is not its successful
result. Neither request-form nor the engineering census was reached.

| Guest | Actual failure | Privileged graphical allocation |
| --- | --- | --- |
| Ubuntu | `ui:timeout:station-default-destination`, about 90 seconds; `station-default-entry` performed no tree reads before timeout | `onpc-graphical-smoke-5ytqjfas` |
| Fedora | `ui:timeout:greeter-identity`, 90 seconds; the final session scan still showed a local Wayland greeter but no accepted destination identity | `onpc-graphical-smoke-crpuxq8x` |

These allocations are under `output/test-runs/privileged/allocations/`.
The exact diagnostic files are Ubuntu `private/command-0160-stderr.txt` and
Fedora `private/command-0158-stderr.txt`; each allocation also retains
`worker-private.log`, `result.json` and the unanswered
`station-branch.request.json`. Ubuntu's worker result is under
`onpc-e2e-evidence-wptyckqy/worker-result.json`; Fedora's qualification events
are under `onpc-e2e-evidence-0ojxgnxk/`. Use the maintained private artifact
reader, preserving raw captures and credentials.

Both final results classify infrastructure as
`e2e:worker-execution-failed`, product and collection as `not-run`, cleanup as
`passed`, and lease phase as `complete`. The wrapper's infrastructure label does
not establish whether the underlying cause is product admission/startup or the
UI identity observer. That diagnosis remains open. No timeout was increased,
assertion weakened or failed branch accepted.

Both reports' full test-input source digest is
`abadad224adbb468e17d6a36253a637096ef1da90c3255045477d8cb88830fee`;
this has a different scope from the package-source manifest. Ubuntu's reported
archive matches the refreshed DEB above. Fedora's report instead records
`bc7506491e8de2b0833bcc505dc91210783b1e1c48ca25c383ffc3997216ee58`,
while the inspected snapshot description records `e5ce12dd…bc50`.
The handoff did not establish equivalence or explain which staged archive the
Fedora report describes. Investigate that provenance boundary before reusing
these results as evidence of exact installed source. The failed attempts do
not qualify confinement regardless of that investigation's outcome.

## Operating and evidence routes for continuation

Follow the current [agent instructions](../AGENTS.md),
[System design](System-Design.md), [test documentation map](TestAutomation/README.md),
[Approval tools](Approval-Tools.md), [VM mandate](Mandates/VM-Mandate.MD),
[UI mandate](Mandates/UI-Automation-Mandate.MD) and
[test storage mandate](Mandates/Test-Storage-Mandate.md). These owners govern
operations; this record does not create parallel rules or relax their guards.

Probe live VM for troubleshooting, use live VM to validate fixes before full e2e tests.

The authorized targets are `onpc-Ubuntu26.04` and `onpc-Fedora44`; the registry
permits two concurrent targets. Product installation uses only `make install`;
development setup uses only `./setup.sh`. Root diagnosis is through maintained
`tools/test-vm` in an owned running online maintenance instance. Stop maintenance
before system/E2E runs. Never use raw SSH/libvirt, adopt another owner's VM,
delete ownership journals or signal a process without recorded identity.

Useful maintained command shapes; replace placeholders only with verified current
inputs. Focused `system` execution requires explicit `--artifacts`; Ubuntu DEB
and Fedora RPM allocations are separate. An omitted artifact argument is not a
product failure. Combine categories only with explicit matching-format inputs:

```bash
tools/prepare-appsnapshot --vm 'onpc-Ubuntu26.04,onpc-Fedora44' --mode online --overwrite true --y
tools/test-vm --vm 'onpc-Ubuntu26.04' exec -- python3 -I -c '<bounded guest diagnostic>'
tools/test-vm --vm 'onpc-Fedora44' exec -- python3 -I -c '<bounded guest diagnostic>'
tools/test-vm --vm 'onpc-Ubuntu26.04' stop
tools/test-vm --vm 'onpc-Fedora44' stop
tools/run-tests system --artifacts '<validated-current-format-allocation>' --area 'enforcement' --test 'test_kiosk_execution_confinement' --vm '<one matching target>'
tools/run-tests integration check_e2e_kiosk_entry --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests unit 'tests/unit/test_kiosk_confinement.py' 'tests/unit/test_kiosk_login.py' -q
```

Use launcher `--help`/`--list` for actual selectors and artifact arguments. The
unit launcher does not accept `--timeout 900s`; retain maintained per-command
timeouts rather than repeatedly trying unsupported flag placement. System help
currently requires an explicit `--vm`. Current E2E listing is JSON with a
`.cases` array; narrow it with `jq` instead of dumping the full catalogue.

Ready customer selectors found during inspection include case 50 (restricted
request station approval), 51/52 (denial/cancel), 53–57 (station eligibility
variants), 259 (fresh kiosk restart notice), and 254 (Chinese installed kiosk
lifecycle). Inspect their actual requirements before selection. Several kiosk
feedback submission cases are pending; parent feedback cases 152–155 do not
establish kiosk feedback acceptance merely because their titles are similar.

Privileged evidence is read through the maintained artifact reader from this
checkout, for example:

```bash
pkexec --keep-cwd '/usr/local/libexec/onpc-test-artifacts' list '<returned allocation>'
pkexec --keep-cwd '/usr/local/libexec/onpc-test-artifacts' read '<exact report>' --bytes 8000
pkexec --keep-cwd '/usr/local/libexec/onpc-test-artifacts' tail '<exact log>' --bytes 12000
```

Do not read online snapshot `snapshot.json`: it contains an ephemeral SSH
credential. Preserve raw private evidence; share only reviewed fixed-category
findings. Do not install dependencies as part of tests, modify host product
policy, or invoke translation synchronization without the user's explicit request.

## Primary source routes and independent-review checklist

Previously inspected upstream sources informing the design and open findings:

- [AccountsService classification](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/src/user-classify.c),
  [public CacheUser implementation](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/src/daemon.c)
  and [property persistence](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/src/user.c).
- [D-Bus broker user-bus connection](https://github.com/bus1/dbus-broker/blob/v37/src/launch/launcher.c),
  [userspace SELinux checks](https://github.com/bus1/dbus-broker/blob/main/src/util/selinux.c),
  [Fedora SELinux constraints](https://github.com/fedora-selinux/selinux-policy/blob/rawhide/policy/constraints).
- [GDM 50.1 worker](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-worker.c),
  [settings](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-settings.c),
  [selection/launch](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session.c),
  [Wayland executor](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-wayland-session.c).
- [GNOME Session 50 leader](https://github.com/GNOME/gnome-session/blob/50.0/gnome-session/leader-main.c).
- [systemd v259 PAM setup and lifecycle](https://github.com/systemd/systemd/blob/v259/src/core/exec-invoke.c),
  [pam_systemd ambient defaults](https://github.com/systemd/systemd/blob/v259/src/login/pam_systemd.c),
  [user manager reload protocol](https://github.com/systemd/systemd/blob/v259/units/user%40.service.in).
- [AppArmor stacking](https://www.apparmor.net/advanced/AppArmorStacking/),
  [Linux v6.17 AppArmor transitions](https://github.com/torvalds/linux/blob/v6.17/security/apparmor/domain.c),
  [labels/subsets](https://github.com/torvalds/linux/blob/v6.17/security/apparmor/label.c),
  [capability mediation](https://github.com/torvalds/linux/blob/v6.17/security/apparmor/lsm.c).
- [bubblewrap NNP setup](https://github.com/containers/bubblewrap/blob/main/bubblewrap.c).
- [Linux-PAM SELinux close behavior](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_selinux/pam_selinux.c)
  and [namespace init/cleanup behavior](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_namespace/pam_namespace.c).
- [libselinux current-context contract](https://github.com/SELinuxProject/selinux/blob/master/libselinux/man/man3/getcon.3)
  and [Fedora audit-message interface](https://github.com/fedora-selinux/selinux-policy/blob/rawhide/policy/modules/system/logging.if).

For final independent review, read the original partial fix against `697a4c30`
and then all later confinement changes including untracked files. Do not review
only this prose or only the latest diff. Review at least:

- Actual GDM timing, marker/lock lifetime, failure repair and the real next exec.
- Parent systemd executor, sd-pam forks, PAM includes/control actions/options,
  authentication/close callbacks and ordinary-user preservation.
- Exact enforcing policy attestation, missing/permissive policy behavior,
  namespace/mount/FD lifetimes, private inode labels, shared-library updates and
  stale-manager handling through reexec/reboot.
- Every executable role/transition, fixed argv/environment/import/plugin boundary,
  NNP exceptions/stacks, WebKit mounts and Polkit privilege transitions.
- Public broker/D-Bus/systemd APIs available to the kiosk, including writable
  unit files and command prefixes; root compromise remains out of scope.
- Packaging dependency/activation/removal ownership, pending vendor files,
  interrupted retry, bounds/cleanup, snapshot/package provenance and test
  isolation. Do not silently discard foreign state to recover a test.
- Required public station entry/approval/denial/cancel, notifications, wellbeing,
  feedback/diagnostics, ordinary parent/child behavior and both distributions.
- Evidence quality: positives before denials, actual kernel errors, fresh
  installed bytes, exact retained report scope and honest remaining limits.

Review findings must distinguish demonstrated defects, plausible untested gaps,
test/harness defects and completed evidence. The release note and design text
must not be used as substitutes for executable acceptance.

## Historical handoff boundaries

Earlier handoffs completed owned cleanup and returned Ubuntu and Fedora to
powered-off verified baselines, preserving their then-current version snapshots
and failure evidence. Their package identities and results are retained below
as history. Current priorities and terminal state appear only in the final
handoff section.

The earlier WebKit/scanner planning gap is now implemented as the separate
installed engineering feedback qualifier described in
[Current engineering checks and input identity](#current-engineering-checks-and-input-identity).
It has not yet passed live. Fault injection remains engineering-only; public
error/editor/download actions supply their own observations, and no feedback
message is sent.

### Working-tree review inventory

In addition to tracked edits listed by Git, the following new paths remain
untracked and must be included in review and any eventual commit:

```text
data/systemd/oh-no-parent-control-kiosk-confinement.service
data/systemd/user/org.gnome.Kiosk@wayland.service.d/
data/systemd/user/wireplumber.service.d/
packaging/kiosk_confinement.py
tests/integration/system_kiosk_confinement.py
tests/unit/test_kiosk_confinement.py
tools/kiosk_confinement.h
tools/kiosk_confinement.py
tools/kiosk_confinement_policy.py
tools/kiosk_session.c
```

Tracked scope spans the Make/package lifecycle, activation and dependency files,
native PAM/login/provisioning, shared child/kiosk launchers and diagnostics,
systemd/D-Bus/session files, maintained test installation/qualification/removal
helpers, host expectations/inventories and design/release documentation. Inspect
Git history as well as the current diff so the prior partial fix and unrelated
HEAD work are handled correctly. Nothing was reset, discarded or committed.

## Live diagnosis continuation (October 12 UTC / October 11 local)

This continuation made substantial progress but did not complete installed or
customer acceptance. Both original entry timeouts now have concrete product
failure evidence. Ubuntu reached the maintained kiosk-entry diagnostic boundary
after a controlled live environment experiment. Fedora's positive manager/bus
checks passed, but its final GDM PAM boundary still failed on the last installed
source. The latest fixes described below have host coverage and build outputs,
but **have not yet been installed or validated together in either guest**.

### Fedora matrix after the corrected readiness assertion

The initial attempt refused missing source input because retention had removed
`onpc-test-artifacts-uqdt79at`; it performed no product test. A fresh artifact
preparation and immediate selected installed run avoided that stale-path error.
The package scope was
`4c4bfead6a4b38cb092da94d313af377cd07f6f5cfad1a853ca52a5b4d669e53`
(346 files). These selected Fedora attempts refreshed the app snapshot through
the shared `make install` route, rebooted and passed the corrected PAM readiness
assertion:

| Host report under `output/test-runs/host/reports/` | Staged/installed RPM SHA-256 | Result |
| --- | --- | --- |
| `20261012T043111Z-70868cf9` | `86010a02cf930db9d3cf6c9a0ce05bf2ec3479dfdf1335927d24dc2b98249dd8` | Manager checks passed; positive final GDM exec failed |
| `20261012T045202Z-39380420` | `84a1499f7bc2e94848eb0c364f3acda7dd26f72dc0a115b3506889aef2c9aa7c` | Manager checks passed; final caller probe failed before successful exec |

The second run used the named qualification input allocation
`output/test-runs/host/allocations/onpc-parent-setup-onpc-Fedora44-4c4bfead6a4b38cb092da94d313af377cd07f6f5cfad1a853ca52a5b4d669e53`;
its builder report was `20261012T045057Z-ac719da6`. That path is historical,
not a promise of retention. The installed attempt allocation was
`output/test-runs/privileged/allocations/onpc-system-_543_4sl`, with
`guest-results/attempt-enforcement/` journals/results and the outer enforcement
XML. The first run's allocation `onpc-system-o2e95oqv` was later rotated.

Both runs proved the nologin shell, reboot-persistent station visibility,
the manager's exact enforcing domain, a positive user bus and native transient
systemd service, and refusal of active removal. Shell, Python, GJS, GNOME Shell,
GNOME Session and WirePlumber exec attempts were denied. Writable copied
executables, interpreter aliases and unit input were denied. Replacing the
original executable/private libsystemd, reexecuting the manager and replacing
the plugin directory preserved pinned execution and the positive service path.
A stale manager was refused without restart. Those results do not cover the
later final-exec negatives/faults, which the failed positive prevented reaching.
Preparation/test durations were 167.503/83.321 seconds and 167.200/92.058 seconds.
Owned cleanup and baseline restoration passed for both attempts.

### Correcting the engineering probe's SELinux caller

A live root probe showed that the previous Fedora `first_exec` fixture ran as
`unconfined_t`. Its `(126, {"exec_errno":13})` result had a `nosuid_transition`
denial from that domain to the kiosk gate. Production intentionally grants the
real `xdm_t` and `init_t` callers only. No unconfined transition was added.

`tests/integration/system_kiosk_confinement.py` now maps only `gdm-password` to
`xdm_t`/`xdm_exec_t` and `systemd-user` to `init_t`/`init_exec_t`. It copies the
resolved Python executable into an owned root-private temporary directory,
labels that finite fixture with the vendor entrypoint type and uses `runcon`
to enter the actual caller before invoking the guarded final-PAM probe. The CLI
rechecks guest/caller identity and returns a strict `onpc-first-exec:` JSON
frame. Unknown callers and missing/failed results refuse. Its owned child is
tracked by pidfd, killed and reaped on interruption or timeout; temporary files
are removed. The parent command timeout is 90 seconds and the child limit stays
75 seconds. Fixed positive-exec status/error observations precede assertions.
Host tests cover both callers, success, failure, missing results and cleanup.

The installed fixture still refused `unexpected-pam-admission` while the actual
GDM preparation failed. That refusal is not evidence of a valid positive or an
accepted confinement negative. Revalidate it after the latest product install.

### Fedora live product failures and pending source fixes

The new maintained `tools/test-vm --vm NAME reproduce-kiosk-entry` action reuses
the shared watched maintenance lease and public station-entry mechanics. It
stops before request-form validation and leaves the same owned guest running
for `exec` diagnosis. It supplies no customer-acceptance result. The dispatcher,
shared probe and host ownership/history tests were updated;
`./setup.sh --test-tools-only` refreshed those maintained tools without installing the
product on the host or broadening grants.

Fedora's live reproduction again reached station-list/focus then refused
`ui:timeout:greeter-identity`. Its private allocations were
`onpc-kiosk-entry-diagnosis-aauukq13` and `onpc-e2e-evidence-beroys__` under
`output/test-runs/privileged/allocations/`. Root inspection found successful
authentication/account routing followed by three native execution-boundary
denials; the kiosk session never became active. The positive manager/user bus
remained usable. Live vendor-domain probes then isolated these causes:

1. `xdm_t` could not read the inventory's vendor-labelled
   `/usr/bin/systemd-tmpfiles`. The generated policy now permits that type's
   `read/getattr/open`, without execution of the distribution original.
2. Checking all root-owned private `/usr` skeleton siblings encountered unrelated
   distro labels: AccountsService data, games paths, HTTP modules, kernel
   modules and the zram-generator configuration. The policy adds `getattr`
   only on `file_type` files/directories for `xdm_t`, without content access,
   directory traversal or execution.
3. Live SELinux permission queries showed the root GDM caller lacked
   `sys_admin` for the private namespace/bind tree. That capability is added
   to `xdm_t`, before the gate transition; no kiosk role receives it from this
   grant. These privileged-caller additions remain independent-review targets.
4. After those changes were installed in the paired snapshot described below,
   fixed-stage PAM diagnostics exposed the next failure: `stage=lock`, with
   `xdm_t` denied read/write of the `init_var_run_t` lock created by the manager
   caller. The systemd-user path reported `armed stage=armed`.

The latest, **uninstalled** policy introduces `onpc_kiosk_runtime_t` and named
creation transitions for both real callers on the confinement lock and runtime
directory under `var_run_t`. Both callers receive the necessary operations on
that dedicated type, avoiding broad GDM write access to all init runtime files.
The native header now logs fixed stages `identity`, `lock`, `prepare`, `bind`,
`environment`, `ambient`, `mac` and `armed` without identity data; it preserves
the no-helper-after-MAC boundary.

**Open validation:** compile/install that latest policy, inspect the actual
native preparation subprocess SID and the lock/tree/child labels, and prove
their create/read/write/mount behavior through real GDM and systemd callers.
Direct `runpy` inside an `xdm_t` fixture is not proof that executing the installed
Python helper retains that SID or creates the same labels. The last live tree
was `unconfined_u:object_r:var_run_t:s0`, and the lock was
`system_u:object_r:init_var_run_t:s0`; do not assume their creation domains.
The direct `runpy` diagnostics were isolated from active GDM attempts but did
not hold the production preparation lock; they are cause-isolation evidence only.
Any direct preparation diagnostic must retain the same preparation-lock
serialization as production. Do not add permissions based solely on log noise.
Observed denied vendor generators/BPF and service-to-manager status traffic did
not prevent the already-proven bus/native-service positive.

### Ubuntu live entry diagnosis and positive experiment

Ubuntu's first maintained reproduction failed after station focus with private
allocations `onpc-kiosk-entry-diagnosis-ai8j3r1b` and
`onpc-e2e-evidence-ev867szz`. Root probes showed that native GDM PAM was armed
and the compositor started with Wayland. It then blocked on synchronous GVfs
volume-monitor activation: UDisks2, Afc, Goa and GPhoto each consumed a timeout
because those desktop helpers were correctly unable to execute. The compositor
unit hit its 90-second timeout; the app ordered after it never started.
Separately, the wellbeing launcher was denied the canonical
`/usr/bin/gjs-console` target of Ubuntu's `/usr/bin/gjs` symlink.

To prove the GVfs cause live, the probe required an inactive manager, started
and identity-recorded one owned `user@1005.service` invocation
`93e2077e24c14c259f29bbee384991b7`, then used its public user-systemd bus to set
`GIO_USE_VFS=local`. Repeating the maintained station-entry reproduction passed
its diagnostic boundary. Evidence allocations were
`onpc-kiosk-entry-diagnosis-3kinn8b5` and `onpc-e2e-evidence-abyf196y`.
No product or policy file was edited in the guest for that experiment.

The actual live UID census counted app 1, audio 1, gate 1, manager 2,
`manager//&pipewire` 3, notification-client 1, notifications 1, polkit 1 and
service 12, all enforcing. Compositor/app and WirePlumber were active/running.
WirePlumber's effective settings were `NoNewPrivileges=no`,
`LockPersonality=no`, `MemoryDenyWriteExecute=no`, empty
`SystemCallArchitectures` and `SystemCallFilter=~`. PipeWire and PipeWire Pulse retained the vendor
`NoNewPrivileges=yes`, personality/memory restrictions, native architecture
and seccomp filters. Wellbeing had the effective NNP override but remained
inactive because of the GJS path denial. This was useful live evidence,
**not a strict complete census or final installed matrix pass**.

Latest source fixes, still requiring a fresh installed proof:

- The generated policy includes the finite canonical GJS entrypoint
  `/usr/bin/gjs-console`, reachable only through the wellbeing fixed launcher.
  No generic interpreter exemption was introduced.
- A kiosk-only root unit override sets `Environment=GIO_USE_VFS=local` for
  `org.gnome.Kiosk@wayland.service`. Native fixed launchers also set that value
  after clearing the environment; host tests inject an untrusted value and
  require the fixed local backend. Ordinary audio's early exec path is unchanged.
- The override inventory and lifecycle design describe these boundaries. GIO's
  [official documentation](https://docs.gtk.org/gio/overview.html) supports using
  its local backend for system components to avoid unnecessary D-Bus activation.
  The debug-only `GIO_USE_VOLUME_MONITOR` switch was not used.

The exact owned manager invocation was stopped and its MainPID verified zero,
dropping the transient environment, before maintained VM stop restored the
baseline. No test manager remains active.

### Fedora report versus snapshot archive discrepancy

The earlier `bc750649…ee58` report versus `e5ce12dd…bc50` snapshot mismatch was
real missing qualification coverage: `KioskEntryQualification` accepted a
version-named snapshot without comparing it with the staged package. The report
therefore described staged bytes, not proven installed bytes. Rotated archives
prevent reconstructing equality; the old qualification must not be credited.

The qualification now builds its expected identity from the frozen staged
bundle and uses the shared app-snapshot package/content, baseline, recipe,
mode/age checks before restore. It refuses
`setup:installed-snapshot-stale:<reason>`, rechecks exact snapshot XML for races
and keeps the saved snapshot identity separate from the expected staged inputs
in reports. RPM identity remains exact-archive strict. Debian's established
delivery-metadata equivalence is reported honestly rather than conflated with
archive equality. Bounded private login/MAC/service diagnostics are collected
on kiosk-entry failure. Host regressions cover stale online/offline inputs,
mode/age, XML races, leases, diagnostics and collection ordering.

**Operational limitation:** the new guard detects/refuses a mismatch; it does
not automatically install another package. Graphical qualification normally
uses a named input allocation, while standalone snapshot preparation can build
a different RPM in a random allocation. Ensure the exact frozen RPM used for
the graphical attempt also prepared its snapshot. The maintained named-input
artifact preparation plus focused installed-suite refresh can establish this;
then reuse those same inputs for graphical qualification. Same scope or version
does not establish the exact RPM archive identity. No post-fix successful
graphical qualification has yet exercised this guard in either guest.

### Snapshot provenance and host verification at this boundary

The final paired preparation before the latest fixes completed successfully
through `make install`, reboot and shared snapshot capture. Both packages had
scope `36b29db0a63aa94baaff042b5d29c816222a544982afa58a239c4de2a25827f8`
(346 files):

| Guest | Host artifact allocation under `output/test-runs/host/allocations/` | Snapshot archive SHA-256 |
| --- | --- | --- |
| Fedora 44 | `onpc-test-artifacts-2m9f0ztv` | `5ccbf00f62b2e574f938809d2bf5e15163db224d49f9942f008fc9c2776c527c` |
| Ubuntu 26.04 | `onpc-test-artifacts-qd13pe93` | `aa28d07317a25b9dc47d185596f4fa8671efae81a7419c9b4d82daab6ad35ad5` |

Read-only snapshot inspection at handoff confirms both `onpc-v1.4` snapshots
and those hashes. **Both snapshots are stale relative to the working tree:**
they predate the dedicated runtime type, canonical GJS entrypoint and packaged
local-GIO settings. An intermediate Fedora read-only fix snapshot used scope
`b422ee57e02ca0337f25d01b67bbbf8e667552dc14cf43a1428533c2852f44cc`,
allocation `onpc-test-artifacts-o8p021em` and RPM
`3f21ea8f2f84689a565bf856088d818fe05b118dcd119655be49b3f76cd80ae8`;
it was superseded, and its live GDM denial was not a final result.

Selected host evidence from this continuation, with report IDs relative to
`output/test-runs/host/reports/`:

| Report | Result |
| --- | --- |
| `20261012T044806Z-dccedc34` | Parent-setup/app-snapshot selection: 180/180 passed |
| `20261012T044958Z-c6ad8d74` | Confinement, qualification and graphical-smoke selection: 321/321 passed |
| `20261012T045701Z-e71232e8` | VM/control/privileged-runner/policy selection: 284/286 passed; two fixture import failures |
| `20261012T050047Z-ff219bfb` | Privileged-runner fixture repair: 28/28 passed |
| `20261012T050333Z-a8ebc9f8` | Confinement after first Fedora read fix: 86/86 passed |
| `20261012T051113Z-559d0c6a` | Native PAM/confinement/login after staged diagnostics: 159/159 passed |
| `20261012T051240Z-072f83b0` | Confinement after root GDM capability fix: 86/86 passed |
| `20261012T052130Z-e91ef7c3` | Confinement after dedicated runtime source fix: 86/86 passed |
| `20261012T052826Z-7c0b45c2` | Latest source: confinement 86, kiosk login 45 and PAM runtime 28; all 159 passed |

The two fixture failures imported `test_retention.locked` without freezing its
`test_input_transfer.py` dependency. Adding that helper to the existing explicit
fixture list was a mechanical repair, not a changed behavior expectation. The
28-case rerun passed; no claim is made that the entire 286-case run was repeated.
New unit cases use the existing private fixture/resource boundaries. The new
maintenance action reuses the same exclusive VM lease, observation and guarded
public journey mechanics; no additional host-global resource was introduced.

`make build` passed for both DEB and RPM **after the latest package-affecting
edits**, using owned scratch run `343b68eabdb140e29b922cd65e51e254` and the normal
`output/deb`/`output/rpm` outputs. Those outputs were not installed. Future
package edits require another build. Host passes/builds do not establish that
the generated latest SELinux policy loads or that either complete guest matrix
passes.

Final documentation checks covered eight changed Markdown documents and 153
local link targets with none missing; `git diff --check` passed. No queue,
pointer, brief or scenario inventory was changed by this handoff update.

### Previous handoff terminal state and remaining work (before this round)

Both maintained VM stops completed with verified baseline restoration and
complete leases. Final read-only status is
`{"state": 5, "id": -1, "scope": "pinned-test-vm"}` for Ubuntu and Fedora.
All test/build/preparation/maintenance commands from this session completed.
No supplemental diagnostic SELinux module was installed, no owned test manager
remains active, and no product was installed on the development host. HEAD is
still `8c64e1422246df793b9b7b952c6b5c3fecd1126f`; all pre-existing tracked and
untracked work is preserved. No commit, publication, actual feedback message,
translation synchronization or final independent review occurred.

The outstanding findings and final remaining-work section consolidate this
boundary's execution priorities without closing any acceptance obligation.

## Previous round: supported replacements and clean handoff

This section records the latest installed evidence before the code review. The
user asked whether the changes were hacky, required proper supported
replacements for all brittle approaches recorded here, then requested a clean
handoff after this round. That implementation review and the original acceptance
work remain unfinished. Do not describe the candidate as release-qualified.

### Live findings and changes made in this round

Both previously stale snapshots were refreshed through the maintained install,
reboot and capture route. Ubuntu's first `--overwrite false` preparation reused
its old same-version snapshot; an explicit `--overwrite true` run corrected it.
Fedora's installed runner refreshed from the exact named RPM input.

Ubuntu scope
`41dc9a30f30a788554ce2e483da217b213fbdf2d1980aa16991669c298f222ee`
entered the real kiosk with the packaged GIO/GJS fixes and no transient manager
environment injection. The diagnostic entry allocations are
`onpc-kiosk-entry-diagnosis-qzw5riq5` and `onpc-e2e-evidence-x142coi3` under
privileged allocations. A subsequent guarded root probe ran the strict census
successfully: manager 10, service 64, wellbeing 11, PipeWire 8, audio 9, gate 4,
notification-client 1, Polkit 6, notifications 5 and app 33 confined threads.
There were no waiting-helper exceptions. Compositor, app, wellbeing, WirePlumber,
PipeWire and PipeWire Pulse were active/running. WirePlumber had the intended
NNP/personality/memory/filter overrides; both PipeWire services retained vendor
NNP, personality/memory restrictions, native architecture and seccomp filters.
This establishes those live engineering observations, not approval/denial/cancel,
notification delivery, feedback/WebKit behavior or a completed E2E scenario.

Fedora report `20261012T054803Z-318d3009` refreshed the same scope and passed the
manager label, bus/native-service positive, active-removal refusal, six generic
exec denials, writable-copy/alias/privileged-unit cases, pinned replacement and
reexec checks, plugin-parent replacement and stale-manager refusal. It failed
the required final GDM PAM positive. Its retained allocation is
`onpc-system-euvahnti`; collection and baseline restoration completed.

Owned live diagnosis established two causes of that preparation failure:

1. The manager's preparation interpreter ran as `unconfined_t`, while its native
   parent was `init_t`; GDM's helper and native parent both ran as `xdm_t`.
   The native-created lock had `onpc_kiosk_runtime_t`, but the helper-created
   runtime tree had `var_run_t`. Source now creates and validates the directory
   in the native PAM caller under the existing lock. The helper requires it to
   exist. No `unconfined_t` transition or broad runtime read permission was added.
2. The generation check's public `systemctl show MainPID` needed service-status
   permission for `xdm_t`. A status-only rule moved the failure to the incorrectly
   labelled generation marker. Combining that rule with a temporary, precisely
   restored runtime relabel admitted the positive final executable with status 0.
   Source adds only the status read; actual native directory creation still
   requires a successful final-source GDM proof.

Temporary diagnostic helper instrumentation retained the original inode and
bytes, and was restored in `finally`. Temporary SELinux modules were installed
only after proving their names absent, then removed. Started managers were
checked by InvocationID before stopping. The runtime-label experiment restored
all labels before maintenance cleanup. These experiments are causal evidence,
not package acceptance.

The former Fedora `sd-pam` waiting exception was then replaced in source:

- The trusted systemd executor clears its vendor pending context and uses
  `setcon_raw` to enter `onpc_kiosk_manager_pam_t` immediately. Only the private
  manager/executor entrypoints can leave that domain, through exec to the manager
  role. There is no reverse dynamic transition. This is a candidate integration
  of the documented API, not yet a proven complete lifecycle.
- The census no longer admits an `init_t` process based on name, parent, cgroup
  or pending context. Its tests now require a confined current domain on both
  backends and reject the obsolete PAM domain and identity changes.
- The first installed package reached `outcome=armed stage=armed`, then
  Linux-PAM's audit socket failed. A bounded supplemental-policy experiment using
  Fedora's standard audit-message permission shape let PAM report session-open
  success. That permission is now in source only for `manager-pam`, excluding
  audit control, `nlmsg_write` and TTY auditing.

**Historical blocker, subsequently corrected below.** With that temporary audit permission,
systemd reported `Failed to send handoff timestamp: Permission denied` and
`Failed at step EXEC spawning /usr/lib/systemd/systemd`, status `203/EXEC`.
No successful manager, inherited `sd-pam`, final GDM exec or teardown result was
obtained for the new design. This message precedes successful exec; do not
misreport it as a demonstrated entrypoint-policy denial. Diagnose the actual
handoff descriptor operation before selecting another permission. The audit
experiment's module was removed and MainPID was verified zero.

### Retained validation and snapshot identity

Report IDs below are under `output/test-runs/host/reports/`:

| Report | Exact result |
| --- | --- |
| `20261012T060921Z-bee83114` | Native runtime-creation/status candidate: confinement 86, login 45, PAM runtime 28; 159/159 passed |
| `20261012T061333Z-ee57d3e4` | Initial immediate-domain candidate: confinement 86 and PAM runtime 28; 114/114 passed |
| `20261012T061407Z-7f2c6ae3` | Named Fedora package preparation passed; scope `58bfd26c…e7dea` |
| `20261012T061509Z-86b20b7c` | Fedora installed selection 0/1; manager startup failed before boundary cases; cleanup/restoration passed |
| `20261012T061917Z-7c5f9e1a` | Strict census replacement: confinement 73, login 45, PAM runtime 28; 146/146 passed |
| `20261012T062359Z-a2fb70ba` | Final audit-permission policy regression selection: confinement 73/73 passed |

The latest Fedora failure allocation is `onpc-system-07je61nb`. Its
`guest-results/enforcement.xml` records the failure at `systemctl start` and
only the earlier reboot-persistent station-visibility property. The retained
authentication/service/session journal selection omits the user-manager and
kernel AVC detail needed here; maintained live probes supplied the precise
`224/PAM` and subsequent `203/EXEC` diagnostics. Improve bounded failure evidence
in the maintained engineering runner if necessary, without exporting raw logs
through feedback.

Final package scope is
`420d31cdd392acad8f77f720d1169f6dc1889b930c1acc119b09669b6c32fb2d`
(346 files). `make build` passed for DEB and RPM after the final package edit,
using owned scratch run `18f62cddca594874866281010e836471`; the normal
`output/deb` and `output/rpm` outputs were not installed. The final audit rule
has live supplemental-policy evidence and host coverage, but no installed
final-package pass.

Read-only snapshot inspection at this boundary confirms these `onpc-v1.4`
archives, both **stale relative to final source**:

| Guest | Package scope | Snapshot package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `41dc9a30f30a788554ce2e483da217b213fbdf2d1980aa16991669c298f222ee` | `76b7d9b0ceb743527228f0ca7ca537ca0cfe481442792dcbf90e1752439c186c` |
| Fedora 44 | `58bfd26c169d80fae822667c347cb551061c4042bece1fc7836f4768dc8e7dea` | `c18e42766d624174830a0fa972decec00857efcaa9c337834b2c8a9b55ad1db3` |

Ubuntu's retained `onpc-test-artifacts-wltst9pf` manifest matches that archive;
its delivery-content identity is
`1812f9de660472171c224b1ec2af369ce1bb8d8c8d948267a19db50dc9d34009`.
Fedora's exact archive is in
`onpc-parent-setup-onpc-Fedora44-58bfd26c169d80fae822667c347cb551061c4042bece1fc7836f4768dc8e7dea`.
Both snapshots record recipe
`081345b7e340b7f1d6ab5a6fd287188d80797ac073b4688d6cf3e4df54462045`.
Do not read credential-bearing snapshot state to compare these identities;
the maintained snapshot XML reader and artifact manifests suffice.

### Historical terminal state

Both owned maintenance stops completed with verified baseline restoration and
complete leases. Each guest was off, with status
`{"state": 5, "id": -1, "scope": "pinned-test-vm"}`.
No diagnostic module, instrumentation or owned test manager remained active.
No host product installation, commit, publication, feedback send or translation
synchronization occurred. This boundary predates the subsequent corrections
and does not describe current acceptance.

## Code-review validation and remaining limits

This review revised the active changes described in
[Current code-review status](#current-code-review-status). Final host validation
passed **1,470/1,470 selected unit cases** in report
`20261012T064443Z-89666966`. The selection covers confinement, installer and PAM
behavior; package activation, payload and RPM generation; provisioning; system
units and information; guest/runner/removal contracts; and shared installed
journey/failure-collection ownership. It uses private fixtures and bounded owned
children, without loading host MAC policy or changing host PAM configuration.

`make build` passed for both DEB and RPM after the final package-input edit,
using owned scratch run `0f499260e3ec4aef889ee195a6910a64`. The generated artifacts
remain in `output/deb` and `output/rpm`. Markdown link and whitespace checks
passed. These results establish host regression and build coverage, not a
successful installed confinement lifecycle.

No VM operation, product installation or customer acceptance ran during this
code review. Earlier VM states and snapshot identities are historical; those
snapshots do not contain these revisions. The next installed proof must exercise
the scoped Fedora handoff permission through manager open/wait/close and
post-parent-exit behavior. The GDM routing marker and AccountsService persistence
workaround still require supported replacements or a demonstrated supported
contract. The remaining public workflow and package-lifecycle obligations above
remain open. The implementation is **not release-qualified**.

## Timed continuation on October 12

The user limited this continuation to two hours, ending at approximately
08:52 UTC, with owned cleanup and a clear handoff boundary. All pre-existing
tracked and untracked work is retained. No commit, publication, host product
installation, feedback submission or What's New synchronization occurred.

### Supported-interface and permission review

- **Timestamp socket:** installed Fedora report `20261012T065355Z-15c0342a`
  reproduced manager startup failure after a fresh package/snapshot. Temporarily
  disabling dontaudit exposed a `unix_dgram_socket:write` denial from
  `onpc_kiosk_manager_pam_t` to **`kernel_t`**. The earlier `init_t` guess was
  wrong. Source now permits only this measured source/type/class/permission;
  there is no domain-wide datagram-write grant or census exception.
- **Manager environment:** that single socket rule allowed exec but exposed
  `Failed to determine $XDG_RUNTIME_DIR path: No such device or address`.
  SELinux's secure-execution flag made libsystemd ignore the trusted
  executor/PAM environment. Adding `process:noatsecure` only from manager-pam
  to the private manager made startup, a native `systemctl --version` transient
  service, and identity-checked normal stop succeed. The stock root-owned
  `user@` unit and `systemd-user` PAM stack were inspected. Generic interpreter,
  original distro executable and reverse dynamic-transition access remain
  absent. Every other role transition retains secure execution. Exact policy
  bounds are covered by the generator regression.
- **Diagnostic cleanup:** dontaudit was restored with `semodule -B`; the
  separately named supplemental module was removed in `finally`; the exact
  recorded manager invocation was stopped. The VM maintenance owners completed
  baseline restoration. Supplemental policy proves a diagnosis, not packaged
  acceptance. An unrelated service-status denial was observed and not granted.
- **GDM routing:** upstream GDM's settings save is best effort, not a supported
  PAM attestation of the next executable. Admission no longer writes the pending
  marker when a preference is valid. Both stages check public routing properties;
  wrong or unavailable values still deny, with public repair for a later retry.
  The required final MAC gate owns the real next exec, including alternate
  commands and executable descriptors. Concurrent preference repair retains the
  existing bounded lock. This removes the timing dependency instead of renaming it.
- **AccountsService persistence:** the public `CacheUser` implementation changes
  `SystemAccount=false` but writes cache data only when the file is absent.
  `SystemAccount` is read-only; there is no public save/flush method. Same-value
  session setters do not save, and `UncacheUser` deletes other cached properties
  and icon state. Replacing the toggle with another unrelated setter or writing
  the private cache would not establish a supported contract. The existing
  provisioning toggle is retained as an explicit unresolved limitation; no
  supported replacement has been demonstrated. Reboot visibility checks remain
  necessary, but passing them would not remove this API limitation.
- **Compatibility settings:** local GIO, the distro's canonical GJS executable,
  finite native D-Bus launch, and unit hardening overrides retain their existing
  narrow roles. The `noatsecure` exception above does not apply to D-Bus service
  transitions. Linux-PAM's `pam_succeed_if` evaluates the user predicate on both
  open and close; source/host guard tests preserve ordinary-user namespace
  callbacks. Active namespace configuration and complete teardown still require
  installed evidence. Native-plugin and service-API review is bounded, not an
  exhaustive audit of optional plugins.

Review sources: [AccountsService manager](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/src/daemon.c),
[user persistence](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/src/user.c),
[public user interface](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/data/org.freedesktop.Accounts.User.xml),
[SELinux secure execution](https://github.com/torvalds/linux/blob/v6.17/security/selinux/hooks.c),
and [PAM user predicate callbacks](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_succeed_if/pam_succeed_if.c).

### Validation in this continuation

Focused confinement, login and PAM runtime checks pass **167/167** in
`20261012T070540Z-e896095f`. The initial run's only failure was the obsolete
blanket no-noatsecure assertion; it was replaced by an exact-one-transition
assertion and a retained service-transition denial. Both package formats build
successfully after the product edits (`make build`). Markdown links pass for
the three documents changed in this continuation.

Graphical qualification reports `20261012T070949Z-d96f7021` (Ubuntu) and
`20261012T070949Z-e8e189b7` (Fedora) correctly refused stale snapshot contents
before executing a scenario. Their frozen inputs share package scope
`2f91e492beb754f7a51433e5126447c35202397e2c62fe2de191cd7d6da1c7c7`
(346 files). The matching named allocations are retained for content-aware
installed-matrix refresh and subsequent graphical qualification.

Ubuntu report `20261012T071128Z-5c5c2cc0` passes the complete selected
`enforcement::test_kiosk_execution_confinement` on that source after content-aware
snapshot refresh. It proves the allowed manager/native service and final GDM
ELF, the manager and final-exec negative matrices (including aliases, copied
files, `+` unit prefixes, loader/file-FD/memfd routes), pinned executable/library
replacement with reexec, stale manager refusal, active/inactive removal gates,
and policy/vendor drift faults. JUnit records every sub-result. Baseline cleanup
and restoration pass. This engineering result supplies no public workflow or
active namespace/teardown acceptance. Its DEB SHA-256 is
`c9a5828b6636998f4e2a4df7dc364105f188ae9f6641ae16790e414249101cf6`.

The Fedora caller harness needed three engineering corrections, without product
permissions: prepare its PAM input before entering `init_t`; carry its bounded
result through an inherited private pipe because `init_t` cannot write the
capture file; and retain all guest/run/input guards while requiring the exact
planned `Permissive` state only for the deliberate enforcement fault. Production
admission still requires enforcement. The command owner deduplicates inherited
descriptors and closes only descriptors it owns.

Fedora report `20261012T075934Z-e6f50417` now passes the complete confinement
matrix, including the positive final exec, all nine final-exec denials,
manager/native service checks, copied/alias/`+` unit routes, pinned replacement
and reexec, plugin-parent replacement, stale-manager refusal, active/inactive
removal gates, vendor/PAM drift, policy-generation drift, global permissive mode,
domain permissive mode and policy unload/recovery. Preparation, collection and
baseline restoration pass. Its exact RPM SHA-256 is
`20681a97f400eee3cbe6f99b7d9a02c4e06c50e25b6482190470cf6932aac107`.
This is engineering execution evidence, not complete customer acceptance.

| Selected host validation | Result |
| --- | --- |
| `20261012T073834Z-b066fa62` | Confinement caller-pipe fixtures: 95/95 |
| `20261012T074338Z-6ecb07b0` | Runner, confinement and inventory: 283/283 |
| `20261012T075126Z-9d60a300` | Guest guard and confinement: 225/225 |
| `20261012T075926Z-8a3f6df6` | Installed-journey failure/cleanup checks: 553 passed; five separate snapshot fixtures failed |
| `20261012T080038Z-89ef028c` | Corrected snapshot fixtures and their owner modules: 165/165 |

The snapshot fixtures now include the real private SPICE/VNC/observer layout,
content metadata and both ownership checks. Their dedicated mismatch/race
assertions remain. Generic installed-journey failures now collect the existing
bounded private journal/session diagnostics before restoration, once per attempt;
cancellation skips collection, and diagnostic failure preserves the original
workflow failure. Both unit and cleanup scheduling inventories were reviewed.
Coverage was regenerated; inventory counts are not passing results.

Ubuntu real entry qualification `20261012T073511Z-fb2ec8e8` passes with the
strict census after an earlier greeter-identity timeout. That earlier failure is
retained and was not reproduced by the maintained maintenance journey or the
qualification retry. Public approval case 50 (`20261012T073846Z-c1252d9f`)
reached the real station, restriction checks and prepared request, then failed
`ui:timeout:mate-prompt` after one Request input. Approval was not established;
cleanup/restoration passed. Ordinary E2E failure collection was added because
that attempt lacked the service/MAC journals needed to diagnose the failure.

The new engineering selector `enforcement::test_kiosk_namespace_guard_callbacks`
uses a uniquely owned active namespace configuration, real PAM callbacks and
bounded direct fork workers. Ubuntu report `20261012T075739Z-3e91b9e9` passes
ordinary open/init/close/setcred, the kiosk skip and parent namespace isolation.
Fedora `20261012T080505Z-bfe45f8d` fails ordinary open with PAM status 14;
the retained journal says `Error getting exec context`. The synthetic service
does not set a pending exec context. It now uses Linux-PAM's documented
[`use_current_context`](https://man7.org/linux/man-pages/man8/pam_namespace.8.html)
option for that situation, with no production policy change. Installed retry
is required before claiming Fedora callback acceptance.

### Real Fedora session follow-up in the timed continuation

The passing finite-exec probe did not exercise GNOME's complete public service
API path. Real GDM entry first failed when its native init worker imported the
environment and started the GNOME target, and when the bus/gate queried the
private manager. The generated policy now grants `service` to `manager`
`system:reload/status/start`, `gate` to `manager` `system:status`, and the native
service `xdm_unit_file_t:service start/status` plus
`dbusd_unit_file_t:service stop`. The transient-service start is required by
dbus-broker's normal activation path, including accessibility. Every activated
executable still faces the finite manager execution boundary.

The next retained diagnostic (`onpc-e2e-evidence-ay52llau`) reached GNOME Kiosk,
which crashed after a denied `dri_device_t:chr_file map`. Granting that mapping
only to the native service role permits the compositor to continue. The next
attempt (`onpc-e2e-evidence-uks8ltps`) also exposed the fixed GStreamer scanner's
prepared-library symlink reads and inherited app-pipe I/O. Those grants are
limited to `onpc_kiosk_runtime_t:lnk_file read/getattr` and
`onpc_kiosk_app_t:fifo_file read/write/getattr/ioctl`; scanner regular-file
writes and further execution remain unavailable. Optional IBus, generators,
Spice agent and original child-wrapper execution denials were not converted
into permissions. RTKit scheduling and document-portal mount denials remain
unqualified behavioral limitations.

These follow-up policy edits invalidate the earlier snapshot/matrix source
identity. Focused host checks pass 95/95 (`20261012T082303Z-929fd26a`) and both
package formats build after the latest package-affecting edit. The temporary
diagnostic policy is a development experiment, not installed-source acceptance;
it must be removed before the final maintained package validation and handoff.

The final diagnostic entry succeeds (`onpc-e2e-evidence-n8_kpohn`, retained scene
`onpc-kiosk-entry-diagnosis-xmp8kzv4`). The strict live census passes: app 33,
audio 12, gate 4, manager-pam 1, manager 1, notification-client 1,
notifications 5, PipeWire 3, Polkit 6, native service 66 and wellbeing 11
threads. In particular `(sd-pam)` is confined in the new manager-pam domain;
there is no `init_t` exception. This proves the diagnostic configuration only.
The exact owned temporary module and file were removed successfully before
stopping maintenance and starting packaged-source validation.

The final frozen package-input scope is
`8f800803404ce2f6f35ec05158a0004b36986cb6196b275118c5f03f3d029498`
(346 files). Ubuntu's rebuilt DEB is byte-identical to `c9a5828b…101cf6`, so its
refreshed snapshot remains current. Entry qualification
`20261012T082526Z-65d6a6e2` revalidates that content and passes the real form and
strict census. Fedora qualification `20261012T082526Z-dea0fb42` correctly refuses
the old RPM contents. The maintained installed runner then replaces that stale
snapshot using the frozen RPM
`ac173f217a0ef0a61c5827f1716af5e98a68b0a9284d9bd08518b4dddecd103a`.
The manifest revision field remains `3e0f2af6`; the input digest above, exact
package identity and worktree review establish this continuation's scope.

Failure collection now also reads the bounded private application/Polkit-agent
journals, whose messages need not match the MAC/product grep. Its focused
failure/cancellation/once-per-attempt checks pass 5/5
(`20261012T083154Z-87ed1a41`). This changes test diagnostics only.

Fedora's final packaged matrix passes in `20261012T082745Z-7f801d75`, using
the exact `ac173f21…103a` RPM and refreshed snapshot. The guest JUnit records
all manager/final-exec denials, positive final exec status 0, copied aliases and
`+` units, executable/library replacement and reexec, plugin-parent replacement,
stale manager refusal, active/inactive removal gates, vendor/PAM drift,
unloaded generation, and all three enforcement faults. Test duration is
132.632 seconds; preparation is 167.004 seconds. Collection and baseline
restoration pass. The private guest JUnit is under
`onpc-system-e5j_quqz/evidence/guest/enforcement.xml`; the top-level
`results.xml` is install-smoke only and must not be mistaken for this matrix.

Fedora's active namespace retry also passes in
`20261012T083342Z-9a4336fb` on the final frozen RPM, with ordinary and kiosk
open/init/close/setcred properties both true. Collection, exclusive fixture
cleanup and baseline restoration pass. This closes the previously recorded
synthetic exec-context failure; it does not establish manager execution denials
after the parent has exited or complete every production teardown path.

The later Fedora entry attempt `20261012T083446Z-5fcaa90f` again refuses a stale
archive before a scenario. The original named input had rotated out of the
per-VM last-three-run retention after the matrix and namespace runs; the next
qualification rebuilt it. The supported candidate-reuse path already verifies
existing inputs, but cannot reuse a removed allocation. The rebuilt RPM has the
same source scope and a new archive hash
`be558131a88bc093622fb9da7de74acffd26ace598fb688c7440dc16028918b5`.
This is a provenance/retention limitation, not a product failure or permission
justification. The next matrix refresh and immediate entry qualification must
consume that same retained input without intervening runs that rotate it away.

That repeated final-source matrix passes in `20261012T083805Z-83471f18` with
the exact `be558131…18b5` RPM. Preparation/test durations are
167.114/122.549 seconds; collection and baseline restoration pass. Its guest
JUnit is `onpc-system-o685gtv8/evidence/guest/enforcement.xml`. The next entry
qualification follows immediately using the candidate-reuse interface.

The immediate Fedora packaged entry qualification passes in
`20261012T084343Z-641ea8ab`, reusing that exact `be558131…18b5` RPM without
rebuilding. Snapshot expected/actual package and content identities agree, as
does recipe `efa56178…60806e`. The real form appears and the strict census
passes: app 37, audio 15, gate 4, manager-pam 1, manager 1,
notification-client 1, notifications 6, PipeWire 3, Polkit 7, native service 85
and wellbeing 12 threads. There is no `init_t` exception. Collection, owned
worker shutdown and baseline restoration pass. Both supported targets now have
matching installed snapshots and positive real-entry/census qualifications;
these results still do not supply approval or other missing customer acceptance.

### Historical timed-session boundary

Ubuntu approval retry `20261012T084541Z-992fea3a` failed after the station
restriction checks and approval action; no approval result was established.
Owned cleanup and baseline restoration completed, with no temporary diagnostic
module or maintenance owner left running. This two-hour continuation ended
before the later corrective work. Its repeated task list is consolidated into
[Release blockers and remaining proof](#release-blockers-and-remaining-proof).

## Independent review and corrective continuation on October 12

This continuation reviews `3e0f2af6` against `697a4c30`, the later commits
`7e78a97c` and `8c64e142`, and the preserved staged, unstaged and untracked
work. HEAD remains `8c64e1422246df793b9b7b952c6b5c3fecd1126f`. Earlier
results above belong to their recorded inputs; they do not qualify these fixes.
The following implementation results and outstanding acceptance obligations
supersede the earlier terminal-state descriptions without erasing that history.

### Corrections implemented

- **Removal and in-flight root PAM workers:** the native module now holds a
  shared admission lease for each kiosk PAM handle, beginning before account
  checks or the session-only fallback and lasting through `pam_end` or exec.
  Forked helpers retain that lease. Removal acquires its exclusive counterpart
  and the existing routing/preparation locks before its strict per-thread UID,
  login UID, current/pending MAC and root PAM mapping census. A first upgrade
  from the earlier lease-free implementation requires a completed reboot;
  scanning alone cannot retire a root worker which may fork later.
- **Payload-erasure interval:** removal persists intent and installs standalone
  requisite kiosk denials using the distro PAM module before unloading policy.
  Those denials survive erasure of the product module/helper. The embedded
  finalizer restores exact original stacks only after kiosk-account deletion.
  Recovery reloads policy before restoring admission. On Fedora the same leased
  admission inode is restored to its vendor SELinux label after policy unload,
  while the exclusive lease and durable denials still hold.
- **Btrfs mapping identity:** live Fedora inspection found that `/proc/maps`
  reported device `00:22` for inode `485142`, while both the trusted PAM path
  and its actual `/proc/PID/map_files/RANGE` object reported `00:24` for that
  same inode. The removal census now compares actual mapped-object device/inode
  identity with the trusted module path. Deleted, replaced, unreadable and
  missing mappings still refuse removal; textual superblock/subvolume device
  differences no longer produce a false legacy-generation refusal.
- **Ordinary Wellbeing environment:** the native wrapper preserves ordinary
  users' settings environment, including DConf and GSettings selection, while
  retaining kiosk startup sanitization. Its fixed GJS command is unchanged.
  Private-bus component checks exercise actual backup, suppression, restoration,
  owner loss and shutdown behavior; installed qualification is separate.
- **Failure evidence:** installed-journey failure collection resolves the actual
  kiosk UID and uses explicit journal conjunctions/disjunctions for the private
  application, Polkit and coredump units. It collects once, preserves the initial
  failure and skips cancellation. Hard-coded UID evidence cannot diagnose a
  different account's failed approval.
- **Glycin and Ubuntu activation:** finite ABI-2 native loaders and their
  directory entries are pinned. Decoder roles receive no interpreter or further
  exec route. The private Ubuntu user-manager path masks the optional Snap
  session-agent service/socket; exact private D-Bus Settings/Launcher definitions
  bind direct vendor activation to that masked unit with an inert fallback.
  Ordinary sessions retain their vendor definitions. Host tests exercise a
  real private bus's service-directory precedence, not just generated text.
  Follow-up review also corrects the scanner's inherited pipe access for its
  admitted WebKit parent, matching the existing app-parent protocol. The scanner
  still has no outgoing exec or regular-file-write permission. WirePlumber's
  fixed launcher disables Lua's default module-path fallbacks only for the
  kiosk, retaining its trusted custom searcher and ordinary users' environment.
- **RPM archive identity:** build timestamp, build host, mtime policy and source
  file modes are deterministic. The source timestamp is explicit and cannot be
  replaced by the caller's environment. Actual independent builds of the same
  current scope produce the same RPM SHA-256 below. Retention may still retire
  an input allocation; a rebuild must pass the normal content/snapshot checks.
  No stale-snapshot guard or retention ownership check is bypassed.
- **Genuine upgrade pins:** v1.2 resolves to unsigned annotated tag object
  `f0520a6f36ad43f57357cdc9e8cd9fa1216e73ae`, peeled commit
  `81ffa5c37abeefdc922825bc27b5933b3eff3ba6`. Its source has no genuine RPM
  package definition. RPM-upgrade selection now refuses before allocation/build
  instead of constructing a fictional prior RPM or accepting a DEB substitution.

Immediate Fedora manager-PAM confinement remains mandatory. The strict census
still covers every kiosk thread, including `(sd-pam)`, with no `init_t` exception.
The measured timestamp socket grant remains manager-PAM to `kernel_t`
`unix_dgram_socket:write`. The only `process:noatsecure` permission remains
manager-PAM to the private manager. New compatibility fixes add no other such
permission. Real callback and post-parent-exit qualification is required in
addition to these policy assertions.

### Current engineering checks and input identity

| Report recorded during this continuation | Scope and result |
| --- | --- |
| `20261012T165251Z-57d77dc1` | Ordinary/kiosk Wellbeing wrapper: 4 passed |
| `20261012T165430Z-53430579` | Public provisioning contracts: 42 passed |
| `20261012T165615Z-a3a41f47` | Installed-journey diagnostics and ownership: 554 passed |
| `20261012T165752Z-5c330f0b` | Genuine upgrade input and package guards: 175 passed |
| `20261012T172452Z-52ae4b6e` | RPM/wrapper checks, real private Wellbeing components and two preview UI cases: 18 passed |
| `20261012T173402Z-1b02da40` | Complete corrected PAM/confinement, installer, RPM, removal and resource-inventory scope: 536 passed |
| `20261012T173614Z-45c584e3` | Scanner observation, strict census, D-Bus activation and feedback ownership: 63 passed |
| `20261012T173712Z-7f0742e2` | Existing eligible-choice flow, inventory and actual staged import closure: 91 passed |
| `20261012T173854Z-2527d32b` | New notification/Wellbeing qualifier unit checks: 15 passed |
| `20261012T173935Z-1ebe906a` | Shared public Wellbeing client against the real private service: 3 passed |

These scopes overlap; their counts must not be added as unique regressions.
Normal report/input retention can retire these earlier allocations; their IDs
record the observed historical runs, not a promise of indefinite artifact access.
Final qualification must retain its current report and exact package identities.
The notification/Wellbeing and feedback selectors are separate installed
engineering qualifications, not new completed customer cases. The scanner
observer uses actual executable and parent identity, enforcing per-thread labels,
private namespace/generation and kiosk credentials. A scanner which exits before
observation is explicitly `not-observed`, never positive confinement evidence.
No discovered product process is signalled by that observer. Feedback preparation
and editor/download checks do not submit a report.

`make build` passed after the final product edit for DEB and RPM. The next live
inputs have package scope
`85c7fa61bbcba2cf4b023d57b4aeff5ceb12e8de3cbaf9f3928c932a9f9be34c`
(346 files), with manifest revision `3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc`
identifying the last selected package-source commit, not unchanged worktree bytes.

| Target | Exact candidate allocation | Package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-wgjmo1kg` | `2c6939eecf508ffce21f9ed6e4918ba1a6611709fa94a79f1e942c4f6f0bf392` |
| Fedora 44 | `onpc-test-artifacts-kd8u8ghq` | `578f12ae1bca5dde6c5cc80ebb321cbca6fd446bfc013a01164a1eccf5541355` |

The Fedora archive equals the independent `make build` output. The DEB builders
declare different source timestamps (`1791765925` for the qualification input,
`1791609131` for ordinary Make packaging), so no DEB byte-identity claim is made.
Both installed snapshots were refreshed from these exact inputs. The next
inactive-removal preflight exposed the missing task-directory `map_files` API
on both guests. Fedora root inspection positively verified the correct
`/proc/TID/map_files` alias for a nonleader thread; the source now uses that alias
while retaining per-thread maps and credentials. The snapshots above are
superseded by this correction and the subsequent scanner/Lua edits. They must
not supply current acceptance. A completed refresh is preparation, not customer
acceptance.

### Release blockers and remaining proof

These five work groups own the complete scope; historical task lists above
are superseded. Group 2 is closed, and group 5's bounded platform review is
complete. The reported historical 5/10 progress counts corrective engineering
groups, not release acceptance or individual test cases.

1. **P0 — Public authentication and remaining workflows.** At the previous
   package boundary, Ubuntu case 50 reached Request but MATE's authentication
   agent aborted while GTK loaded an SVG through glycin/bubblewrap. That attempt
   established no usable password prompt, credential entry, parent grant or
   explicit approval result. The current phase-1 record owns its measured loader
   corrections and new proof: cases 50–52 pass on both targets. Preserve required
   approval behavior. Complete ready cases 53–57, 151, 191, 192, 254 and 259
   under their actual contracts. The previous log's repeated denied
   `/usr/bin/snap` attempts came from independent default-target services.
   The [issue-2 execution record](#phase-1-execution-record) now closes that
   activation issue with installed suppression and ordinary-user controls;
   the remaining authentication/workflow obligations keep this group open.
2. **Closed — AccountsService retained hidden accounts.** The owned
   classification adapter preserves existing metadata and qualifies fresh,
   retained-visible and retained-hidden records, safe retry/interruption
   recovery, daemon restart and reboot on both targets. The
   [Phase 2 issue 1 record](#phase-2-issue-1-execution-record) owns its exact
   installed and public results. No upstream fix is a prerequisite, and no
   unrelated setter or destructive uncache/recreate workaround is used.
3. **P1 — Installed security, lifecycle and ordinary users.** Ubuntu's previous
   package passed the real PAM teardown and post-parent-exit matrix denials.
   New package inputs require affected qualification on both targets. Complete current active
   namespace callback tests and the full removal/reboot/reinstall/purge/retry/
   foreign-state lifecycle, including successful inactive removal and account
   finalization. Preserve ordinary parent/child/overlay behavior and settings.
   Host fixture repairs preserve all expectations; no broken session counts
   as successful confinement.
4. **P1 — WebKit, scanner, feedback, notifications and Wellbeing.** Run the new
   installed engineering selectors below and retain actual live observations.
   Scanner `not-observed` is missing proof, not a pass. Exercise editor and
   diagnostic download without sending feedback. Public reminder preview
   proves rendering only; natural-reminder tasks 311/311b remain unregistered
   and unexecuted, with their Wellbeing lifecycle obligations still open.
5. **P1 — Genuine upgrade and bounded platform review.** Build genuine DEB v1.2
   input through the existing qualified route, then test actual upgrade,
   activation and reboot. No genuine prior RPM exists; RPM upgrade acceptance
   remains unavailable rather than using a fabricated predecessor. The
   [Phase 2 issue 2 record](#phase-2-issue-2-execution-record) completes the bounded
   source/package-identity review of the actual distro WirePlumber/Lua builds,
   shipped scripts, native plugin path and service APIs, with live and installed
   qualification on both targets. It does not attest to every optional plugin.
   Phase 1 also closes the Fedora password-helper measurement and finite
   test-only census integration. Genuine DEB upgrade and final integrated
   review remain open in Phase 4.

### Previous-package live validation

That continuation's product source was frozen at package scope
`3ace67f846ac285d6c305e9fe5454554ca2a7a273c43bc38ae8d051b21bf7aaf`
(346 files). Both formats passed `make build` after the procfs, scanner-pipe
and Lua corrections. Its subsequent fixture/documentation edits did not affect
that package scope. The current phase-1 policy edits supersede those packages.
Artifact manifests report revision
`3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc`, which is not the HEAD or a claim
of a clean working tree.

| Target | Exact qualification input | Package SHA-256 | State at handoff |
| --- | --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-4vu9euim` | `2b34988213f9cd6d85690e25b41112a1c0a8553208cd459ac9127a0dc1bc67bc` | Snapshot current; this host allocation has already rotated out |
| Fedora 44 | `onpc-test-artifacts-gva665lt` | `933be1cd0c99ea3108d716cbae8e0fad81c3eeee5e975190d530c593a633b5aa` | Snapshot refreshed successfully; matrix/public acceptance pending |

The Fedora allocation is under `output/test-runs/host/allocations/`; its
`artifact-manifest.json` matches the independent Make RPM byte for byte.
The ordinary Make DEB is
`489750bff0ebc1aefd1be95de47f2412c886ee8e7d78e91e125cf3df0f71044b`.
DEB builders declare different timestamps, so its differing archive is not
claimed identical to the qualification DEB. Shared fixture digest is
`6aa1707b82f35caa902cd048e3c6bb6a37ff034044be2d92ff23b81dbfbbddd0`.
Never reconstruct a retired input directory or bypass snapshot matching;
use the maintained builder and normal content-aware refresh.

Read-only snapshot inspection after final cleanup confirms both
`onpc-v1.4` snapshots with the exact package hashes above and common recipe
`efa56178ccba5202c5dee0b74cfd3f1c6ae51dbcce78a3e0ceec14897360806e`.
Ubuntu's package-content identity is
`42322754c9e1b77c3667025975946ada8824f8de3825e723b5f0d2631538ccb7`;
its baseline is
`62790e23e4afdf7bd727a862075c894231e88730f8c5fb7f2d3cd4b26e3a2908`.
Fedora's package-content identity equals its RPM hash; its baseline is
`e60dabc15971ac9127df84caf9add1c07029adcd20cf53bee2b474f39773dcc8`.
These are preparation/provenance results, not customer acceptance.

The final focused host report
`20261012T180155Z-451a2127` passes **3,260/3,260**, zero skips/failures,
across 37 affected modules. Its inventory and progress files retain the exact
selection. The previous 3,248-pass/10-failure run exposed three fixture defects:
staged-helper inventory omitted the three new qualification helpers; diagnostic
fixtures lacked the now-required seven-field account row and journey plan; and
a nominal no-reboot activation fixture changed native PAM bytes. The repaired
activation fixture independently varies native-PAM and boot-order changes,
preserves the no-reboot case when both are unchanged, and requires reboot when
either changes. No product classifier or required behavior was weakened.

Ubuntu's installed matrix passes in combined run
`20261012T175244Z-e5c795b7`. Guarded allocation
`onpc-system-cx9vs6ui/guest-results/enforcement.xml` is the real matrix;
the top-level install-smoke label is not. Selected guest-input identity is
`6aab0b5890f10ec7449a1b1dbd205e21b78d9ad82b9b427ae27cfc41a661fd20`.
Test/preparation durations are 61.522/212.739 seconds; collection, cleanup and
baseline restoration pass. JUnit records establish-credentials, close-session,
delete-credentials and end statuses all zero, with shell/Python denials after
the executor exits and after every teardown callback. Positive controls,
manager/final-exec denials, copied aliases and privilege prefixes, pinned
executable/library replacement/reexec, plugin-parent replacement, stale-manager
and policy/vendor/enforcement faults pass. Active removal refuses and inactive
removal admits, including the corrected actual procfs lookup. This is Ubuntu
engineering proof, not Fedora proof or complete package removal.

### Previous-package approval failure: exact reproduction and evidence

The same combined run then fails public case 50, `E2E-016/approved`, using the
exact Ubuntu input above. Public Parent enable/save, passwordless station entry,
restriction checks and request preparation succeed. The Request action reaches
`kiosk-mate-open`; the guest observer then reports
`ui:timeout:mate-prompt` after 92.613 seconds and 324 tree reads.
The generic worker/transport classification obscures the retained guest error;
the dependency crash is a product failure, not successful confinement.

Raw allocation:
`output/test-runs/privileged/allocations/onpc-graphical-smoke-4vybw3ga`.
Read `private/command-0069-stderr.txt` for the prompt timeout and
`private/command-0071.txt` for the application/Polkit/MAC journals through
the documented artifact reader. The reviewed export is
`output/test-runs/host/exports/onpc-artifact-export-jdt3xy2b/command-0071.txt`,
lines 49–65. At guest time 11:01:47, agent PID 9957 aborts with GTK
`ensure_surface_for_gicon` because loading Adwaita's
`image-missing.svg` fails. The actual child route is
GTK → glycin → bubblewrap → `/usr/libexec/glycin-loaders/2+/glycin-svg`;
the loader exits 1. Systemd records core-dump/ABRT, Polkit records failed
authorization, then the agent restarts. Nearby AppArmor messages deny
the Polkit role reading `/` and the glycin bubblewrap role checking
`sys_ptrace`/`net_admin`. Capture actual loader stderr and reproduce its
exact native sandbox operation before choosing a permission fix.
Relevant generator entry points are
[the role transition map](../tools/kiosk_confinement_policy.py#L99) and
[AppArmor generation](../tools/kiosk_confinement_policy.py#L332).
No password was entered and no grant/approval result was observed.

Attempt evidence is `onpc-e2e-evidence-ouqithsq`; suite evidence is
`onpc-e2e-evidence-w1h7c7et`. The attempt source identity is
`4028158ad8a4d7fedfa47d431e6f21f0b00c1d29ca82607b8696ec5c7a740cdc`
and inventory identity is
`756bf5176c3b9d8ff96ee382d6ee1b6327bd072960dcddc8dbedfadc3700855b`.
Owned cleanup and baseline restoration pass. Evidence/input retention can
retire historical paths; their absence must be reported, never filled in.

### Continuation order and qualification routes

The [current phased plan](#phased-execution-plan-current) owns execution order
and session scope. These routes supply phase-specific mechanics; they do not
authorize beginning a later phase in a phase-1-only session.

The [phase-1 execution record](#phase-1-execution-record) closes the SVG loader
and Snap activation issues with their exact scoped evidence. Continue with the
native helper issue named by the current pointer. Probe live through owned
online app-snapshot maintenance and preserve public approval as the full-phase
acceptance criterion. Any package-affecting fix requires `make build`, new
exact inputs and affected requalification on both targets.

For Fedora, the existing strict census in
[system_kiosk_confinement.py](../tests/integration/system_kiosk_confinement.py#L86)
rejects the vendor `policykit_auth_t` used by the allowed stock password helper.
The candidate policy's
[finite vendor transition](../tools/kiosk_confinement_policy.py#L326)
is not proof that an arbitrary process in that domain should be accepted.
Measure the real helper while the public approval prompt waits, before password
submission: exact distro package/source versions, canonical root-owned native
setuid ELF, file label, actual per-thread UID tuple/current label, PIDFD/starttime/
task stability, confined Polkit parent, private namespace/generation, executable
inode and independent read-only file bind. Upstream suggests real kiosk UID with
effective/saved/fs root, but this is not a measured distro result. Only after
those checks may a narrowly bounded test-only helper role be justified.
An uncovered nested helper directory cannot be assumed independently pinned.
Keep all unknown labels and `init_t` rejected. At the previous handoff, no such
role or pinning edit had been made and the live helper/WirePlumber/Lua inventory
probe was deferred. The current execution record below owns subsequent changes
and their qualification status.

Focused installed execution requires a verified format-specific allocation:

```bash
tools/run-tests system --artifacts '<absolute current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_execution_confinement' --vm '<matching target>'
tools/run-tests system --artifacts '<absolute current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_namespace_guard_callbacks' --vm '<matching target>'
tools/run-tests system --artifacts '<absolute current DEB or RPM allocation>' --area 'removal' --test 'test_remove_reboot_reinstall' --vm '<matching target>'
tools/run-tests integration 'check_e2e_kiosk_feedback_confinement' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests integration 'check_e2e_kiosk_notification_wellbeing' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests --vm 'onpc-Ubuntu26.04' integration 'check_e2e_upgrade_assets'
```

The last route builds/transfers genuine v1.2/current upgrade assets through
`named_input(upgrade_source=True)`; it has not run. Do not add a new launcher
capability to duplicate it. Earlier `onpc-parent-setup-input` source
`4318ff…` lacks the required release tag and cannot qualify genuine upgrade.
Use returned verified prior/current manifests for the subsequent upgrade test.
For ordinary artifact preparation use a single explicit target per invocation;
the host-category preparation attempted with a comma selector built only the
first target. Do not change or bypass controller ownership to overlap VM work.

### Clean handoff state (previous session)

All started builds, tests and preparation commands have finished. Fedora's final
online preparation completed successfully and its owned maintenance stop then
completed verified baseline restoration. Final maintained status for **both**
guests is `{"state": 5, "id": -1, "scope": "pinned-test-vm"}`.
No test, preparation or maintenance owner remains running; all three subagents
finished. No temporary diagnostic policy or instrumentation was installed in
that previous session. Its version snapshots were preserved at that boundary.

HEAD remains `8c64e1422246df793b9b7b952c6b5c3fecd1126f`; all pre-existing
staged, unstaged and untracked work is preserved, with no staging or commit.
There was no host product installation, publication, feedback send or What's New
synchronization. The document consolidates current blockers and execution state
here while retaining unique historical evidence. Continue with GPT-6.1 Sol High
and bounded parallel subagent tasks; reuse established automatic approvals.
The implementation remains **not release-qualified**.

## Phase 1 execution record

Phase status: in progress; issues 1, 2 and 3 are complete. The latest session was
limited to issue 3 and qualified native helper pinning, Fedora's usable prompt
and both targets' strict waiting-session census against final package inputs.
Exact source, host/build, installed results and cleanup for each issue follow.
The next-phase pointer stays at 1. No phase 2–4 implementation occurred.

Phase-1 progress is reported against three concrete issues, independently of
the historical 5/10 corrective work-group count:

- [x] Ubuntu's actual SVG/glycin authentication-agent crash is corrected,
  including the shared Fedora decoding path.
- [x] Repeated Snap activation is diagnosed at its actual caller and suppressed
  in the installed kiosk without changing ordinary sessions.
- [x] Fedora's real password helper is measured and any necessary finite
  pinning/census integration is qualified without accepting unknown labels or
  `init_t`.

The issue count started at **0/3 solved** and is now **3/3 solved**. Issue fixes
alone do not close the phase: its both-target engineering and public cases
50–52 gates also apply. The narrowed session completed **1/1** issue; the failed
Fedora lifecycle matrix remains an explicit phase exit blocker.

### Issue 1 — SVG/Glycin correction (previous session)

That session was narrowed to the image-loader crash, native decoding on both
targets and a usable Ubuntu prompt. Supporting Snap and helper-pinning edits
were preserved for later qualification. Its exact results remain historical
evidence below; the latest issue-2 results follow in their own subsection.

The initial live diagnosis reproduced the native image-loader abort on both targets.
Ubuntu's actual Glycin trace reports `bwrap: loopback: Failed RTM_NEWADDR`;
Fedora's matching AVC denies `glycin_bwrap_t` routing-message writes. Bubblewrap
configures loopback after creating its private user/network namespaces. The
scoped correction permits only that bootstrap's network administration (SELinux
`cap_userns`, never initial-namespace `capability`) and routing writes. Ubuntu's
Polkit profile also needs `/ r,` for Glycin's library-symlink discovery. The
Fedora retry passed that network boundary and exposed a separate `fs_t`
filesystem-remount denial for the pinned private `/usr` view; only the Glycin
bootstrap receives that measured remount permission. No adjacent `sys_ptrace`
denial has been converted into a grant. Decoder restrictions remain intact.
Subsequent native retries exposed Ubuntu's mount-flag mismatches and Fedora's
regular-file `tmpfs_t` mount targets created by native `--dev`. AppArmor strips
`MS_SILENT` from bind matching while retaining it for propagation/remount, and
native bubblewrap requests recursive binds even for files. The corrected
candidate matches those normalized flags at the existing finite path pairs.
Fedora's Glycin bootstrap alone receives `tmpfs_t:file mounton` and
`fs_t:filesystem { remount unmount }`; native oldroot detach needs the latter
after making oldroot private. SELinux filesystem permissions are type-wide;
kernel namespace/capability checks still apply, and the decoder gains none.
The intermediate confinement/login regressions passed **233/233**, report
`20261012T193436Z-69c89ab1`; final validation is recorded below.

Ubuntu's installed repeated caller is the enabled default-target unit
`snap.snapd-desktop-integration.snapd-desktop-integration.service`, rather than
the already masked session-agent socket. The current finite kiosk-only masks
also cover the observed prompting daemon and firmware-notifier service/timer.
The existing primary D-Bus data-path overrides were already effective. Ordinary
unit and activation definitions are not edited.

The maintained `reproduce-kiosk-approval` route retains the real public prompt
before qualification/password input. `probe-kiosk-approval` reads the retained
form's exact choices, refreshes its estimate through numerically equivalent
public duration input with independent readbacks, then invokes Request once.
This reprobes a failed prompt without resetting or manufacturing scenario state.
Both retain bounded native-agent and Glycin audit evidence in their existing
allocations, including on failure. Both are engineering diagnostics, with no
customer-acceptance credit. Their display maintenance
off/on events only detach/attach observation; they do not restore the VM.

Earlier source/host checks: confinement/login **232/232** passed, report
`20261012T185510Z-11251d9d`; maintained probe/grant checks **425/425**, report
`20261012T185239Z-4b7cee8c`; resource inventories **115/115**, report
`20261012T185333Z-315e03f7`. Both DEB and RPM passed `make build` after the
remount correction, scratch run `824e9a8c26314b398365a9c70a8410a6`.
The final bootstrap correction also permits opening its temporary root before
native bubblewrap's second pivot; the audit and native source identify that
exact descriptor operation. The current policy/login check passes **233/233**,
report `20261012T194047Z-4b830e8c`. Both formats pass the final `make build`,
scratch run `4fc4c14d380b41de99658b1fa2c978bd`.

Controlled native retries now show successful SVG frame decoding on both
targets; Ubuntu's real `kiosk-mate-open` observation also passes. Fedora then
fails in the separate vendor password helper's pipe/runtime access, without
the image-loader abort. Keep that failure in issue 3 and do not broaden its
policy or census in this narrowed session. Temporary policy and `RUST_LOG`
changes were restored before each owned stop. These temporary experiments do
not close the phase; final current-package evidence follows.

Fresh verified inputs share package-scope source fingerprint
`e17fe365fa4208d122eae2066dbda7703a61db92edf6170ff72874ca9b814c13`
(346 files). The policy generator SHA-256 is
`c1eebdb8074ebf2110d2d9203620eeeff92dc6c568cd511aae76d50e3e1ff0db`.
Both online snapshot preparations completed successfully; that is preparation,
not acceptance.

| Target | Current allocation | Package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-7iji3ry8` | `81de4849a7e414074d1396d243b3ef43c18f2b25122860a01d9145032d2c21d1` |
| Fedora 44 | `onpc-test-artifacts-dok_y0ep` | `c659088066eccfabedd20e9b7dba6af11015fb709550103b616da0f66c763156` |

The fresh Ubuntu policy SHA-256 is
`1d024a34fc0b570a7c530f44e054e05c376dc660ccc15a1dc7cfcc6706416db7`;
Polkit, Glycin bootstrap and decoder profiles are enforcing, with no temporary
policy loaded. Its canonical native helper is also
`/usr/lib/polkit-1/polkit-agent-helper-1`, root:root, mode **0755**. Issue 3 must
review its independent pinning too: the current Fedora-only reserved parent
does not qualify Ubuntu, and Fedora's setuid assumptions must not be copied
there. No helper role or census exception has been added.

The fresh Ubuntu DEB's `reproduce-kiosk-approval` completed successfully, retained
the real authentication prompt before password input, and opened/cancelled an
earlier prompt in the same public journey. Allocation
`onpc-kiosk-approval-diagnosis-_vzohulw` records `approval-open` and captures 16
native/audit records. Its retained interval has no image-loader abort; optional
`sys_ptrace` and availability-probe execution remain denied. The maintained
screenshot export
`output/test-runs/host/exports/onpc-artifact-export-fsbkpxgc/screen.png` visibly
shows the authentication prompt, rendered key icon and requested 75-second
grant with soft-blocked applications. No password was submitted by this
engineering route.

The fresh Fedora RPM's initial public reproduction retains a denied form at the
separate helper failure (`ui:mate-owner`), allocation
`onpc-kiosk-approval-diagnosis-yl5pu5ql`. Its guarded retry allocation
`onpc-kiosk-approval-probe-6xrp3klc` captures 256 agent records and 19 exact Glycin
audit records: 11 image-frame returns with file descriptors, six completed
transformations and ten pooled-loader reuses. This bounded trace proves decoding;
loader startup lies before the retained 256-record window. The helper failure
still prevents a usable Fedora approval prompt and belongs to deferred issue 3.
No temporary policy module was used with the fresh RPM. Diagnostic tracing was
restored to its original absence before successful owned stop and baseline
restoration; Fedora then reported `state=5`, `id=-1`.

Final maintained route/duration checks passed **1006/1006**, report
`20261012T192919Z-ce4a841b`; capture, grants and resource inventories passed
**559/559**, report `20261012T194219Z-ee865359`; bounded capture/no-match/failure
checks passed **21/21**, report `20261012T194413Z-1d7a6bca`. Fresh native results
above precede the focused both-target confinement matrix and feasible Ubuntu
case 52.

Ubuntu's final current-package `enforcement::test_kiosk_execution_confinement`
passes, report `20261012T200613Z-490f9c7c`, allocation `onpc-system-pzogl_i4`.
The real `guest-results/enforcement.xml` has one pass, no failures/skips;
establish/close/delete/end statuses are all zero and post-parent/teardown denials
pass. The matrix covers manager/final-exec denials, copied aliases and privilege
prefixes, executable/library/plugin replacement, stale managers and policy/vendor/
enforcement faults. Collection, cleanup and baseline restoration pass.

Fedora's final current-package matching matrix fails, report
`20261012T200801Z-ea09e8c2`, allocation `onpc-system-1y9m49go`. Expected PAM
establish/delete credential statuses are zero; actual statuses are **17/17**,
while close/end are **0/0** and post-parent/teardown execution denials pass.
The failure is `kiosk-lifecycle:credential-teardown-incomplete`; later matrix
checks are unqualified. Cleanup and baseline restoration pass. Keep this
failure explicit and preserve its expectation. Read-only review places it in
the separate group-3 PAM lifecycle work: establishment returns `PAM_CRED_ERR`
before `pam_open_session` installs manager-PAM confinement; the product's
`pam_sm_setcred` returns success, and the image fix changes only Glycin bootstrap
permissions. Retained journals do not identify the failing vendor callback.
The existing no-auth/`other` fallback is a hypothesis, not a proven cause;
continuation requires live lifecycle reproduction and appropriate PAM/audit
evidence. Do not change expectations or implement that separate repair in this
issue-1-only session. The image decoding result does not pass this gate, which
remains part of Phase 1's matrix exit requirement.
Both matrices select guest-test input identity
`6aab0b5890f10ec7449a1b1dbd205e21b78d9ad82b9b427ae27cfc41a661fd20`, separate
from the package-scope fingerprint above. Focused system selections require
explicit format-specific artifacts and therefore ran serially; the attempted
automatic-input queue refused preflight before any VM execution.

Ubuntu case **52**, `E2E-016/cancelled`, passes against the current DEB, report
`20261012T201102Z-6d443c4c`. Its independent attempt
`scenario-ea8fbe84b17f4b64ae727ad3959a73e9` observes native cancellation,
preserved choices, continued Overview/grid/terminal restrictions and usable
sign-in after normal station exit. Product, infrastructure, collection and
cleanup outcomes all pass; there is no first failure. Raw allocation is
`onpc-graphical-smoke-g3d62nhw`, attempt evidence `onpc-e2e-evidence-xlg35ylg`
and suite evidence `onpc-e2e-evidence-mfztviq0`. Attempt source identity is
`41ea2c6c5497ec0ad2323e5221271d1bb0c68c41492de39abb582586e8020e34`;
inventory identity is
`756bf5176c3b9d8ff96ee382d6ee1b6327bd072960dcddc8dbedfadc3700855b`.
The result is partial acceptance of this exact variant. Cases 50/51 and Fedora
case 52 are not qualified here; Fedora's helper failure blocks its prompt flow.

**Issue-1 session close-out: 1/1 solved; Phase 1 was 1/3 solved.** The scoped image
crash is corrected with native sandboxing enforced, independently reviewed
permissions, host regressions, both package builds and fresh native evidence.
Ubuntu's current-package matrix and public cancel flow pass. Fedora's separate
helper failure and failed PAM lifecycle matrix prevent Phase 1 completion;
neither is waived or counted as successful validation. No census rule changed,
and no `init_t`, unknown-label, production interpreter or decoder exception was
added. The whole confinement topic remains **unfinished and not release-qualified**.

All started builds, preparation, diagnostics and tests have finished. Temporary
policy/tracing experiments were restored before owned cleanup. Both final
maintained status checks report
`{"state": 5, "id": -1, "scope": "pinned-test-vm"}` with successful baseline
restoration. Verified version snapshots and all pre-existing work are preserved;
there was no staging, commit, host product install, publication, feedback send
or What's New synchronization.

### Issue 2 — Installed Snap suppression (October 12, 2026)

**Complete: 1/1 session issue solved; Phase 1 is 2/3 solved.** This session
executed only the next open issue. The existing product correction needed no
production edit. Its actual repeated caller is the
enabled default-target unit
`snap.snapd-desktop-integration.snapd-desktop-integration.service`, whose vendor
definition executes `/usr/bin/snap run snapd-desktop-integration` with
`Restart=on-failure` and a two-second retry. The observed prompting daemon has
the same restart policy with a one-second retry. Masking only the session-agent
socket cannot suppress those independent entrypoints.

The installed candidate's six finite masks in the kiosk-only unit search path
cover those callers, session-agent service/socket and firmware-notifier
service/timer. The two private D-Bus definitions route Settings and Launcher
to the masked agent rather than the vendor's direct `/usr/bin/snap userd`.
The owning implementation and behavior remain in
[Lifecycle](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle) and
the [policy generator](../tools/kiosk_confinement_policy.py).

Installed engineering validation used the existing Ubuntu `onpc-v1.4` online
snapshot, restored through `tools/prepare-appsnapshot --vm 'onpc-Ubuntu26.04'
--mode online --overwrite false --y`, then real public station entry through
`reproduce-kiosk-entry` and guarded `exec` probes. The snapshot's DEB SHA-256 is
`81de4849a7e414074d1396d243b3ef43c18f2b25122860a01d9145032d2c21d1`, matching
the preceding issue-1 input. Installed AppArmor policy SHA-256 is
`1d024a34fc0b570a7c530f44e054e05c376dc660ccc15a1dc7cfcc6706416db7`; generator
SHA-256 remains
`c1eebdb8074ebf2110d2d9203620eeeff92dc6c568cd511aae76d50e3e1ff0db`.
The station-entry prefix is retained in
`onpc-kiosk-entry-diagnosis-q5qibn8j`, with worker evidence
`onpc-e2e-evidence-5rtrujoh`.

The real kiosk manager is enforcing `onpc-kiosk-manager` and receives the exact
private `SYSTEMD_UNIT_PATH`; its bus receives the private data path first.
All six units independently report `LoadState=masked`, `ActiveState=inactive`
and the private mask fragment. Explicit starts of all six fail as masked.
Both `StartServiceByName` calls independently return
`org.freedesktop.systemd1.UnitMasked`. During a subsequent **30.15-second**
interval, all four service restart counters stay zero, socket/timer states
stay unchanged, and the kiosk journal contains zero Snap unit or manager
activation records. This exceeds both measured repeating-caller retry periods.

The ordinary-user control started UID 1000's normal user manager through
systemd's public service API. It is unconfined, has no private unit-path entry,
and loads all six unchanged vendor fragments. Desktop integration and prompting
are running, the session-agent socket is listening and the firmware timer is
waiting. On that ordinary user's actual session bus, Settings activation returns
`1` (started), then Launcher returns `2` (already running). Vendor activation
definitions still execute `/usr/bin/snap userd`. This qualifies the ordinary
user-manager and session-bus scope; it is engineering validation, not a new
graphical-desktop or complete customer-journey acceptance claim.

The [existing D-Bus regression](../tests/unit/test_kiosk_confinement.py) now
checks kiosk and ordinary variants with independent execution canaries for
both vendor definitions. Kiosk fallback must reject activation without running
either canary; ordinary activation must execute each one. The first new control
used a successful process which acquired no bus name and therefore timed out;
its fixture now records execution then exits explicitly with status 7, preserving
the activation assertion without waiting for name acquisition. The kiosk's
existing status-1 fallback assertion remains intact. Parallelism review updates
the [existing compatible classification](../tools/regression_unit.py): each
variant owns its private bus, socket, files and bounded reaped child; no host
session bus or shared cache is touched.

Final focused override/activation and inventory checks pass **20/20**, report
`20261012T204416Z-cb81055a`. Only test code, its resource-review comment and this
record changed in this session; none is in the package source/build-tool scope,
so no package rebuild or new package qualification was needed. No Fedora work,
password-helper change, census exception or phase-exit acceptance was attempted.
The earlier accidental product-free maintenance start was stopped cleanly before
online restoration; its refused installed probe supplied no product result.
Final owned stop passes baseline restoration, and Ubuntu reports
`{"state": 5, "id": -1, "scope": "pinned-test-vm"}`. All started commands have
finished, version snapshots and pre-existing changes are preserved, and there
was no host installation, commit, publication, feedback send or translation sync.

At the issue-2 boundary the pointer stayed at **Phase 1**, with the following
continuation order. Issue 3's close-out below supersedes item 1; item 2 remains
the phase-exit work:

1. Finish issue 3: measure the real helper and independently pinned native
   metadata on both targets, respecting Ubuntu 0755 versus Fedora 04755 and the
   strict per-thread census. Do not assume the supporting reserved directory
   alone solves helper access or qualifies a vendor label.
2. Live-reproduce Fedora's PAM credential-lifecycle failure with the relevant
   caller/stack/audit evidence, repair its proven cause and rerun the focused
   matrix. Complete the remaining both-target cases 50–52 and strict real-session
   census against final current inputs. Any package edit requires the affected
   checks again. Only then check Phase 1's row and advance to Phase 2.

Use established automatic approvals and bounded subagents, one owner per VM and
one editor for shared policy. Stop at the completed phase boundary. Continue
with GPT-6.1 Sol High for the unresolved confinement/ownership diagnosis.

### Issue 3 — Native password-helper pinning and census (October 12, 2026)

**Complete: 1/1 session issue solved; Phase 1 is 3/3 solved.** This session
executed only the third issue. Final installed qualification and owned baseline
cleanup pass on both targets. The phase remains open at its remaining exit gates.

The real Fedora prompt initially failed before password input. Its vendor
helper is `/usr/lib/polkit-1/polkit-agent-helper-1`, root:root, mode **04755**,
native ELF, with label `system_u:object_r:policykit_auth_exec_t:s0` and no file
capabilities. Installed packages are `polkit`/`polkit-libs` **127-2.fc44.2**,
`mate-polkit` **1.28.1-8.fc44** and `selinux-policy-targeted` **44.11-1.fc44**.
The initial AVCs identify inherited pipe read/write and private runtime-tree
lookup failures in `policykit_auth_t`. A bounded temporary CIL experiment proved
the exact three permissions now generated by the product:

```text
policykit_auth_t -> onpc_kiosk_polkit_t fifo_file:read,write
policykit_auth_t -> onpc_kiosk_runtime_t dir:search,getattr
policykit_auth_t -> onpc_kiosk_runtime_t lnk_file:read
```

The first experiment, without directory `getattr` and symlink `read`, still
failed. The completed experiment opens the native prompt and retains its waiting
helper before any password submission, allocation
`onpc-kiosk-approval-probe-t1hkucfp`. No `noatsecure`, signal, rlimit, socket,
additional executable or tree-write permission was needed or added for this
helper. The temporary `onpc-helper-probe` module was removed, normal dontaudit
restored with `semodule -B`, absence verified and the owned guest stopped with
successful baseline restoration before package qualification.

The observed Fedora helper has one stable thread with UID tuple
`(kiosk, 0, 0, 0)` and exact vendor domain
`system_u:system_r:policykit_auth_t:s0`. Its live parent is the confined native
Polkit agent. Helper, parent and kiosk manager share the same private mount
namespace and generation; the executable inode matches the manager's private
helper view, with an individual read-only bind at the canonical helper path.
PIDFD, starttime, task, parent and mount observations were bracketed for changes.
This is the measured native exception; it does not justify accepting a whole
vendor domain, unknown label or `init_t` thread.

Ubuntu uses a different supported Polkit 127 route. Its **127-2ubuntu1.1** helper
is root:root, mode **0755**, native ELF with no file capabilities, SHA-256
`8864e9dfa2030b925c2c337760dd49b02a630666d9765c0a84b95c193fd9e7db`.
The live waiting helper is an external root socket-activated system service,
with parent PID 1, all-root credentials and a separate namespace; it is outside
the kiosk UID census. The actual kiosk Polkit agent's ten threads remain
enforcing `onpc-kiosk-polkit` in the private generation and namespace. Original
snapshot measurement, allocation `onpc-kiosk-approval-diagnosis-lw6s347q`, found
only a directory bind and no independent helper file bind. That gap is fixed
on Ubuntu as well as Fedora. Polkit 127's
[session implementation](https://github.com/polkit-org/polkit/blob/127/src/polkitagent/polkitagentsession.c)
owns the socket route and direct-execution fallback; its
[PAM helper](https://github.com/polkit-org/polkit/blob/127/src/polkitagent/polkitagenthelper-pam.c)
owns the native conversation. These source findings explain, rather than
substitute for, the two live measurements.

The final implementation keeps the vendor helper outside the copied executable
inventory. Its canonical path, content hash, exact mode/root ownership and
Fedora label enter the stable generation manifest. Preparation refuses symlinks,
hardlinks, file capabilities, non-ELF input, wrong metadata and in-flight changes.
Its separate inode/size/timestamp/privilege assertion is checked by the native
caller before and after the read-only bind, preserving Fedora setuid semantics.
The directory skeleton owns the helper's mountpoint on both targets. Independent
review caught a later-layout race which could omit the signed binding after
measurement; preparation now requires exactly one regular-file layout entry for
every measured helper before publishing a generation. Same-byte reinstalls keep
stable content generations while refreshing the native identity assertion.

The strict engineering census now proves the finite Fedora helper's per-thread
UID tuple, exact enforcing vendor domain, measured native metadata and hash,
manifest membership, file bind and executable inode, private namespace and
generation, and live confined Polkit parent with its pinned executable. Task
sets, identities and labels are rechecked; the generic census still rejects
unknown and `init_t` kiosk threads. Preparation and census also reject a
permissive vendor helper domain. A safely unlinked old pinned inode may have
link count zero in a live namespace; preparation still requires one link.
Ubuntu's external root helper needs no census exception. Its canonical private
file bind covers the native direct-execution fallback too.

Host regressions cover metadata, file replacement, generation stability, native
signature parsing, parent/thread/namespace/binding proof, domain enforcement and
the three exact permissions. The initial full confinement module had **258
passing, 28 failing**: all failures were a mechanical private-fixture mode error
under the host umask, before their intended assertions. Explicit private
directory mode 0755 corrected the fixture without relaxing product trust checks;
the focused preserved-helper rerun passes **32/32**, report
`20261012T210259Z-2702f1de`. Login/resource-review scope passes **85/85**, report
`20261012T210044Z-a092f4ac`. New resource accounting stays within the module's
compatible private-file/process scope, with bounded native compiler children and
proc/xattr/PIDFD doubles; it adds no host mount, label, policy, PAM or VM operation.

After the final layout-race repair, `make build` passes **both DEB and RPM**,
scratch run `7c12d81f33864a3c94dbcc83c6b221cd`. The final focused helper selection
passes **44/44**, report `20261012T210830Z-6fa0dfc1`: the preceding 32 cases plus
12 preparation cases covering missing, symlink, directory and duplicate layout
entries, preservation of old bindings on refusal, and exact signed binding
publication/reuse for both manager and gate. Fresh installed measurements
against that final source and owned cleanup pass as recorded below.
Cases 50–52, full current-package matrices and Fedora's previously failed
PAM credential-lifecycle gate remain
Phase 1 obligations; these helper diagnostics supply no customer acceptance
credit and do not close the phase.

**Final installed engineering qualification passes on both targets.** Both
online snapshots were rebuilt through the maintained preparation route after
the last package-source edit. Their verified package-scope fingerprint is
`4c25e10de3c20f55b787916aa55ae97365373e5b94529d06ac7d2bf1d780bd05`
over 346 files. These are the final format-specific inputs:

| Target | Frozen allocation | Package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-172oxyig` | `ebc34d0e7f08024c3594ef9da53cc65a99830b7fe8773d05c7c84ed143800fd9` |
| Fedora 44 | `onpc-test-artifacts-rpovy4sv` | `47648f170cbd4ed4c6584dba4c322138c436fd9e7606446fb5c3fe0959732421` |

The final source generator SHA-256 is
`52cb22e22b8442b7d04d4fbaad4118b8ad675afd1951d6ffd9898c1acb7a496a`.
Both installed preparation helpers match source SHA-256
`5ae71842efd035e006f7aa64c40526aac1aba094dfd5ad5b48b266e396c138ca`;
both frozen census modules match source SHA-256
`e3a216bd592cdb76c2b8c1389000f98c0e067350b94864f20170a336f085b8f5`.
Installed policy hashes are Ubuntu AppArmor
`eb927843d115b039dec11565f4ae173efff806a7183bcb95105e8a83b4667a5d`
and Fedora SELinux CIL
`45d31ba994bbe3a91d97c1b30f3a65e65ea692181c0719eac63844a246e17122`.

The final `reproduce-kiosk-approval` route succeeds on each target, closes its
graphical worker and retains `approval-open` before challenge qualification or
password input. Exact retained evidence is:

| Target | Diagnostic allocation | Worker evidence |
| --- | --- | --- |
| Ubuntu | `onpc-kiosk-approval-diagnosis-gydgdjiu` | `onpc-e2e-evidence-lqe6hii8` |
| Fedora | `onpc-kiosk-approval-diagnosis-88ng4mqo` | `onpc-e2e-evidence-1kuckxi2` |

Both `approval-open.reply.json` files independently read
`{"observed":"approval-open"}`. The subsequent read-only census invokes the
frozen installed helper with its existing run, guest, package, transfer-digest
and enforcing checks intact. Ubuntu's census passes every kiosk thread across
12 observed roles; Fedora's passes every kiosk thread across 14 observed roles,
including the one waiting `policykit_auth_t` thread. Required app, manager,
service, Wellbeing and PipeWire roles are present on both.

Fedora's final generation is
`9a2dbaab07585064341f72162770a35445946f0131456c8d167f31c6b4f98576`.
The independently bound helper retains root:root **04755**, vendor label,
no capabilities and SHA-256
`026972c2853aa610480cdf5957dacdf28d7b07059977282cfee0a5d8deb0605a`;
its exact preserved manifest record matches. The waiting helper's executable
matches that pinned inode. Its mixed UID tuple, confined Polkit parent, all-thread
proof, shared private namespace/generation and stable lifecycle all pass the
finite census checks, with no temporary policy installed.

Ubuntu's final generation is
`e8054a4dfa7d8698b256450870dfd1054fb3abc31520e8faf508d0dee76e3d68`.
Manager and native Polkit agent independently show the canonical helper's
individual read-only file bind, same original inode, root:root **0755**, no
capabilities and the vendor hash measured above, matching the generation's
preserved manifest. PIDFD/starttime/task snapshots remain stable. The waiting
external helper still has all-root credentials, parent PID 1 and its separate
system-service namespace. The kiosk agent's ten threads remain enforcing; no
Ubuntu helper census exception is used.

Intermediate packages and Ubuntu replay
`onpc-kiosk-approval-diagnosis-iit8m9b9` predate the layout-race repair and supply
no final qualification. Their owned preparation/replay cleanup completed before
the final snapshots were prepared. One early Fedora preparation refused the
still-held prior cleanup lease; it changed no state and supplies no product
result. A large inline Fedora probe also refused locally before guest execution
because its complex quoting missed the approved launcher prefix. The maintained
encoded-literal transport succeeded without setup, rule or authorization changes.

Final owned stops and baseline restorations pass on both targets. Both maintained
status checks report `{"state": 5, "id": -1, "scope": "pinned-test-vm"}`.
All started builds, preparation, diagnostics, tests and owned cleanup have
finished. Temporary policy experiments were restored before final qualification;
verified version snapshots and all pre-existing work are preserved. There was
no host product installation, staging, commit, publication, feedback send or
What's New synchronization.

**Issue-3 boundary: complete; Phase 1 remains in progress.** There is no unchecked
issue left in its three-item checklist. The next phase execution must diagnose
and repair Fedora's separate PAM credential-lifecycle failure, qualify both
final-package confinement matrices and finish public cases 50–52 on both targets.
This session's strict real waiting-session censuses pass; any subsequent product
edit requires the affected current-input checks again. Only after every Phase 1
exit gate passes may its row be checked and the pointer advance to Phase 2.
No phase 2–4 work was performed. The whole confinement topic remains
**unfinished and not release-qualified**.

### Phase 1 exit-gate continuation — PAM credentials

**Complete through Phase 1's exit gates.** The user continued from the completed
issue checklist into the remaining gates. The sequence below retains diagnosis
and intermediate results; the [resumed record](#resumed-phase-1-exit-gates--final-installed-inputs)
owns final acceptance. No Phase 2–4 work is included in this continuation.

Live Fedora reproduction identifies the credential callback, rather than
attributing the failure to confinement. Installed versions are PAM
**1.7.2-2.fc44**, systemd **259.9-1.fc44** and SELinux policy
**44.11-1.fc44**. The vendor and rendered `systemd-user` stacks have no auth
group. Linux-PAM therefore dispatches `pam_setcred` through the global `other`
auth group, which contains `auth required pam_deny.so`. A guarded root probe
using the installed stack returns **17/17** for establish/delete; direct calls
to that installed vendor module also return **17/17**, with `pam_end=0`.
Linux-PAM's version-matched [dispatch implementation](https://github.com/linux-pam/linux-pam/blob/v1.7.2/libpam/pam_dispatch.c)
selects the fallback when the requested group is absent, and
[pam_deny](https://github.com/linux-pam/linux-pam/blob/v1.7.2/modules/pam_deny/pam_deny.c)
returns `PAM_CRED_ERR` unconditionally. No temporary policy, PAM edit or guest
instrumentation was required to reproduce this cause.

The product now renders an owned manager auth-group prefix. Its fixed native
`kiosk-manager-credentials` callback checks the service and target account,
returns success only for the kiosk's inert credential operations, and always
denies kiosk authentication. Ordinary accounts return `PAM_IGNORE` and continue
through an explicit `auth include other`, preserving their vendor fallback.
Wrong services and extra mode arguments refuse. Added vendor auth callbacks
remain rejected by the existing source audit. The kiosk no longer invokes
global fallback credential callbacks before session confinement or during
`sd-pam` teardown. No executable or MAC permission was added.

The engineering lifecycle observer still checks every real teardown status and
post-parent-exit denial. It now also explicitly requires establishment status
zero, retaining all boundary evidence before refusing either failure. Existing
teardown expectations were preserved, rather than accepting Fedora's 17.

Host validation and inputs at this boundary:

| Check | Result | Retained report / scratch run |
| --- | --- | --- |
| Confinement, native login and PAM runtime | 390/390 pass before the stricter establishment assertion | `20261012T214138Z-06a815d0` |
| Final confinement and scheduling inventory | 326/326 pass, including rejection of failed establishment | `20261012T214219Z-e85d022c` |
| Package configuration, activation and RPM packaging | 287/287 pass | `20261012T214540Z-27cc779f` |
| Coherent confinement checkpoint: affected units, Wellbeing component, source/traceability and static checks | 5,212/5,212 pass: 5,198 units, 12 component cases, source and static categories | `20261012T215845Z-c06c3538` |
| `make build` | DEB and RPM pass after the final package edit | `0c71ecf3d0e045a1af5b9345fdfc5915` |

Real-libpam regressions exercise the generated control expression, both permit
and deny fallbacks, ordinary-user preservation, kiosk authentication denial,
silent establish/delete, wrong service and extra arguments. They reuse the
private compiled module and confdir; no host PAM, account, service, bus, display
or shared cache changes. The existing compatible unit inventory records that
resource review. The preceding live maintenance instance was stopped and its
baseline restoration passed before fresh preparation.

Both online snapshots were rebuilt successfully through the maintained queue.
Their package-scope fingerprint is
`a71d4f761a8b2695997a3e7125bb78bd2b476c69a80bd1d526896b3c53414e6e`
over 346 files. Verified format-specific inputs are:

| Target | Allocation | Package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-tb2_hhvt` | `ee0ff73ac1df162a3fc174e3795023114163f03986a8304d81ab1201c604227f` |
| Fedora 44 | `onpc-test-artifacts-359xv5vt` | `1ef7373c76c47ea4df17b3bc2a6bb493bf4d93ee6c7f0d38ae8a2d57029e503d` |

Fresh `reproduce-kiosk-approval` succeeds on both exact packages, closes its
graphical worker and retains the real `approval-open` scene before password
input. Both independent `approval-open.reply.json` reads confirm that boundary.

| Target | Diagnostic allocation | Worker evidence |
| --- | --- | --- |
| Ubuntu | `onpc-kiosk-approval-diagnosis-immgtryl` | `onpc-e2e-evidence-twqg8oci` |
| Fedora | `onpc-kiosk-approval-diagnosis-j442zonq` | `onpc-e2e-evidence-_3n0nlhb` |

The frozen installed census passes with all guest, run, package, transfer-digest
and enforcement checks intact. Ubuntu observes ten confined roles; Fedora
observes fourteen, including the one waiting `policykit_auth_t` thread. Required
manager, app, service, Wellbeing and PipeWire roles are present on both. Initial
calls supplied the newer maintenance-domain run rather than the saved online
snapshot's guest run and safely refused `run-identity`; the corrected calls use
the independently read snapshot XML identity. No guard or marker was changed.

Both owned maintenance stops and baseline restorations pass before installed
acceptance. Both exact current-package `enforcement::test_kiosk_execution_confinement`
matrices pass, with no failures or skips. Establishment, close-session,
delete-credentials and PAM end each return **0** on both targets; all
post-parent-exit denial assertions pass. Normal manager/final-exec denials,
replacement/reexec, plugin-parent replacement, stale manager, active-removal
refusal, vendor drift, unloaded-policy and unenforced-policy checks also pass.
Both runners complete collection, owned cleanup and baseline restoration.

| Target | Report | Raw allocation | Retained complete JUnit export |
| --- | --- | --- | --- |
| Ubuntu | `20261012T220441Z-527f0db5` | `onpc-system-iykvkesk` | `onpc-artifact-export-rnrcgdxv/enforcement.xml` |
| Fedora | `20261012T220107Z-36b06a68` | `onpc-system-fcjx3n69` | `onpc-artifact-export-rtsi12zu/enforcement.xml` |

Exports use the maintained artifact helper under `output/test-runs/host/exports`;
they preserve complete matrix assertions before later E2E retention can rotate
the raw allocations. Preparation, diagnosis and engineering matrices supply no
customer acceptance. Public cases 50–52 remain in progress on both targets.

Public case 50 fails on both initial corrected packages, with collection,
owned cleanup and baseline restoration completed. Ubuntu report
`20261012T220615Z-a4288a94`, raw allocation `onpc-graphical-smoke-lb90x4m1`,
records `ui:timeout:greeter-identity`: GDM creates the kiosk session, which exits
before the request form becomes available. The retained display-manager journal
does not establish why. Fedora report `20261012T220615Z-eb83263d`, raw allocation
`onpc-graphical-smoke-cqwmd246`, passes station entry and shortcut restrictions
but records `ui:timeout:kiosk-approval-success` after the real password submit.
Its audit evidence shows vendor `unix_chkpwd` in `chkpwd_t` denied search of the
private generation's `onpc_kiosk_runtime_t` directory, followed by PAM
authentication failure. Neither run supplies acceptance.

Failure collection also exposed a mechanical automation defect: guarded
transport returns bytes, but the account parser split it with a string delimiter.
Decode that result before validating the account, and make both unit doubles
return bytes. The existing bounded/identity-guarded collector contract is
unchanged. Its 606 targeted regressions pass in
`20261012T221337Z-1daad3f4`; the missing UID-scoped journal from the earlier
failure cannot be reconstructed from those host artifacts.

Fedora's installed PAM 1.7.2, Polkit 127 and SELinux 44.11 confirm that the
password checker is the vendor setuid ELF `/usr/bin/unix_chkpwd`, labelled
`chkpwd_exec_t`. The generated policy now permits its existing `chkpwd_t`
domain only directory search/getattr and symlink reads on the owned private
skeleton. The vendor PAM/shadow policy and executable routes are unchanged.
The corresponding regression constrains the complete added helper rule set.
Both formats build successfully after this edit in scratch run
`9a57e3190a05406a840c9214876e9d03`. Current-package live gates remain required.
The affected confinement, package configuration/payload and resource inventory
selection passes 663/663 in `20261012T221838Z-bdce6377`. A fresh Ubuntu diagnostic
on the initial package reaches both real station entries and the waiting
approval prompt (`onpc-kiosk-approval-diagnosis-dk2ibw6f`, worker
`onpc-e2e-evidence-_b4bnr51`); it does not explain the earlier intermittent exit
or supply a successful case-50 result. Coverage generation succeeds after the
failed scenario. New preparation precedes final public acceptance.

The post-traversal-fix package-scope fingerprint is
`98787814edc8a9a22b84c066ff379970bec456b644bc4ec6964aedf51c5732ac`
over 346 files. The refreshed inputs are:

| Target | Frozen allocation | Package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-h6bfyp91` | `ee0ff73ac1df162a3fc174e3795023114163f03986a8304d81ab1201c604227f` |
| Fedora 44 | `onpc-test-artifacts-3o7fywif` | `6ba6702b4e829afda7f2b62521f780c61f9ea1db026e7826632ff5044600f77f` |

The Fedora-only generated policy edit leaves Ubuntu's complete package bytes
unchanged. Its preceding matrix and strict census therefore apply to the exact
current DEB; retain their evidence above. Fedora's changed RPM requires a fresh
waiting-session census and installed matrix. Public cases 50–52 remain required
on both targets.

Fedora's post-traversal-fix `reproduce-kiosk-approval` succeeds, closes its worker
and independently records `{"observed":"approval-open"}` in
`onpc-kiosk-approval-diagnosis-d69f2snh/approval-open.reply.json`; worker evidence
is `onpc-e2e-evidence-y3ky44id`. The frozen installed census passes against the
saved snapshot run `bd764b8d647c4e3caf22302095853076`, retaining the guest, run,
package, transfer and enforcing guards. It observes all fourteen confined roles,
including the one qualified waiting `policykit_auth_t` thread and required
manager, app, service, Wellbeing and PipeWire roles. No temporary guest policy
is installed. Owned maintenance cleanup and the final matrix/public cases
remain in progress.

The bounded failure journal now also includes the installed GNOME session
manager/monitor/init/bus-restart units and the kiosk UID's native session leader,
so a repeat of Ubuntu's early exit retains startup evidence before restoration.
The actual Ubuntu vendor unit inventory was read through owned maintenance;
unrelated accounts, services and processes remain excluded. The same five
guarded calls and 300-record journal bound remain. All 606 collector safety
regressions pass after the extension in `20261012T223124Z-5448de5e`.

Both refreshed preparation runs complete successfully, and both owned
maintenance stops restore and verify their baselines before acceptance.
Fedora's final changed-RPM confinement matrix passes without skips or failures,
report `20261012T223259Z-806b4bd9`, raw allocation `onpc-system-y8jl7hvh`.
The complete JUnit is retained at
`output/test-runs/host/exports/onpc-artifact-export-rpq1gi6g/enforcement.xml`.
Ubuntu's identical-DEB matrix and retained JUnit above remain current.
Public cases 50–52 are the remaining Phase 1 exit gates.

Public case 50's post-traversal-fix queue completes with Ubuntu passing and
Fedora failing; both owned cleanups and baseline restorations pass. Ubuntu
report `20261012T223955Z-c2a2481b` reaches approval and the subsequent station
return on the exact unchanged DEB above. Fedora report
`20261012T223955Z-c46df9f4`, raw allocation `onpc-graphical-smoke-o9zh4igc`,
passes station entry, shortcut restrictions and native prompt qualification but
times out at `kiosk-approval-success`. Its root journal now shows
`pam_exec(polkit-1:account)` denied execution of
`/usr/libexec/oh-no-parent-control-login-check` in `policykit_auth_t`; the earlier
`unix_chkpwd` traversal failure is absent. The repaired collector also retains
the UID-scoped startup journal. Coverage generation succeeds after this attempt.

The generic profile redundantly launched that Python helper for every account
before its native kiosk account gate. The native gate already checks service
identity, removal admission, confinement integrity and serialized routing for
the kiosk, while returning success without a subprocess for ordinary parents.
Remove the duplicate `pam_exec` from the shared profile rather than granting
the vendor helper interpreter execution. Fedora's integration verifier requires
both native stages and rejects the legacy helper; removal still detects legacy
references. Regressions exercise real-libpam parent/kiosk `polkit-1` behavior
and migration from an exactly recorded old authselect profile while preserving
vendor bytes and the original selection. The affected 987/987 host checks pass
in `20261012T225418Z-16b8bc37`. Both formats build after this edit in scratch
`15b27d0a7a2743bdb77d9a6b0b12e5a8`. Live owned Fedora diagnosis precedes another
E2E attempt, as requested; these host results do not close the exit gates.

Owned Fedora diagnostic `onpc-kiosk-approval-diagnosis-ezz3_evf` reaches and
retains the real waiting prompt, closing worker `onpc-e2e-evidence-tkafixno`.
A root engineering probe pins that vendor helper with a PIDFD, enters its
private mount namespace and compares the real `polkit-1` PAM account stack
with/without the duplicate line. Both account/end calls return 0 under the
root engineering domain, and the temporary generated PAM edit is restored and
hash-checked. SELinux refuses direct `setcon` entry into `policykit_auth_t`,
so this probe does not claim vendor-domain or public approval acceptance.
No policy exception is added. Owned maintenance stop and baseline restoration
complete before fresh preparation.

Fresh Ubuntu preparation of `onpc-test-artifacts-3ae6rzrd` fails during the
guest's public `make install`, raw `onpc-graphical-smoke-zp3ic8cr`; cleanup and
baseline restoration pass. The previous preparation collector retained only
`command:failed:make`, losing guest-private package command streams on restore.
`InstalledSetup` now collects that existing private directory through the
guarded transfer before restoration, preserves the original failure if guard
or collection fails, skips cancellation and never retries installation.
The same attempt allocation and ownership remain; no extra cleanup owner or
resource class is added. Its 790 affected safety checks pass in
`20261012T230354Z-b840f26b`; source/static/resource checks pass 262/262 in
`20261012T230519Z-2971276a`. Both scheduling inventories record the unchanged
private-fixture review. The failed preparation supplies no acceptance, and
current-package preparation/diagnosis precedes E2E retries.

The repeated Ubuntu failure retains the actual installer streams in
`onpc-graphical-smoke-7yfowx0c/suite-setup/guest-private/stage-aji5joc9`.
Installation reaches product configuration and provisioning, then the Ubuntu
activation verifier rejects the new profile because it still requires the
removed Python line. Update that verifier to require the native `kiosk` account
and session entries and reject an active legacy helper. The private package
fixture now supplies those actual native entries; six refusal regressions cover
missing/optional/commented gates and a retained legacy call while preserving
local PAM bytes and migration exclusion. The affected 542/542 package checks
pass in `20261012T230840Z-bbe8ad2f`. Both formats build after this final package
edit in scratch `04025b426bd64ef18818270cff47e671`. Fedora's native-only package
has already installed, rebooted and prepared successfully; its Ubuntu-only
verifier change requires an independent byte comparison before evidence reuse.

Fedora's native-only RPM is
`e6552fb84651456da511a5dfbaff4053a776c2b71775949a79fdeccd89c4d390`,
frozen allocation `onpc-test-artifacts-47bk0m38`. The real retained prompt in
`onpc-kiosk-approval-diagnosis-nvalvdki/approval-open.reply.json` independently
records `approval-open`, worker `onpc-e2e-evidence-p5rveyd5`. The strict census
passes against saved snapshot run `aa10d5ffc0914faebf73f01814722b51`, retaining
all identity/package/mount/enforcing checks and observing fourteen confined
roles. A second root engineering PAM account probe in that actual helper's
private mount namespace returns start/account/end 0 and confirms the installed
native gate with no legacy helper. It remains an engineering-domain result,
not vendor-domain approval acceptance. Owned maintenance cleanup is in progress.

Ubuntu's final activation-verifier package is frozen in
`onpc-test-artifacts-g8cosspy`, DEB SHA-256
`6272492f3791428359336a8bccae2eb58a76dd069b0123a78f08cc6b861f8600`.
Its installation and verified reboot now pass and the online snapshot is
captured. The final package-scope source fingerprint is
`18bb6a9d9f43725f0f8eccfd5a52fecbf9c8fdfa28da639555ce2eebb50fc848`
over 346 files, revision `8999ce9f66e787e69d317387985852914e3e7a89`.
That revision reflects the user's concurrent version-history commit; the
subsequent approved-rules commits are preserved. The preceding Ubuntu case-50
pass does not qualify this changed DEB. Final current-package censuses, matrices
and all public cases 50–52 remain required. An artifact-format probe attempted
during the owned Fedora diagnostic is refused by its held lease; no guest or
ownership change occurs, and byte comparison waits for normal maintenance stop.
These input values come from the prepared attempt's frozen manifest in
`onpc-graphical-smoke-h_y587_g/suite-setup/input/artifact-manifest.json`
and agree with the restored snapshot XML. An initial attribution to an older
host allocation was corrected before counting any installed result. The saved
Ubuntu snapshot guest run is `63027fc95fa241949ab78db358468a8b`.

Ubuntu's final-DEB diagnostic independently reaches `approval-open` in
`onpc-kiosk-approval-diagnosis-yuq_4uvc/approval-open.reply.json`, closing worker
`onpc-e2e-evidence-1xooa7qb`. Its guarded census passes on that saved guest run
with all ten expected confined roles; no unknown or unconfined kiosk thread is
accepted. Normal maintenance stop precedes its final installed matrix.

Final Fedora artifact preparation passes in `20261012T231808Z-245b39e8`:
`onpc-test-artifacts-l8w79744`, package SHA-256
`1885c38e9b1285798eeb6f2b2899bf49f8dbc039aa6e56c539b5edec18f62e9a`.
Its source fingerprint matches the final Ubuntu input above. The RPM bytes do
change after the Ubuntu verifier edit, so the preceding `e655…` census cannot
qualify the final RPM. The normal installed matrix refreshes that snapshot;
a new real waiting-session census remains required afterward. Neither the
package identity nor the census is relaxed to reuse an earlier result.

### Previous handoff boundary — final Fedora matrix complete

The user requested handoff after the running Fedora matrix and Ubuntu
maintenance cleanup finish. Both operations complete successfully. Ubuntu's
maintenance stop verifies baseline restoration; Fedora's controller also
completes collection, owned cleanup and baseline restoration. Both VMs are
stopped, with no owned VM operation or E2E scenario left running. No further
VM run starts at this boundary. The working tree and the user's concurrent
commits are preserved; this continuation creates no checkpoint commit.

Fedora's final-RPM `enforcement::test_kiosk_execution_confinement` passes
**1/1, with zero failures, errors or skips**, report
`20261012T231949Z-6f990086`, raw allocation `onpc-system-3kjfyaxf`.
Its result records package SHA-256
`1885c38e9b1285798eeb6f2b2899bf49f8dbc039aa6e56c539b5edec18f62e9a`
and the final source fingerprint `18bb6a9d9f43725f0f8eccfd5a52fecbf9c8fdfa28da639555ce2eebb50fc848`.
The retained complete JUnit is
`output/test-runs/host/exports/onpc-artifact-export-xakkt3wt/enforcement.xml`.
Credential establishment, close-session, credential deletion and PAM end all
return **0**; the post-parent-exit denials and all selected confinement
assertions pass. Product, infrastructure, collection and cleanup outcomes pass.
This installed engineering result does not supply public approval acceptance.

| Final input | Frozen allocation | Completed current-input gate | Remaining Phase 1 gates |
| --- | --- | --- | --- |
| Ubuntu 26.04, DEB `6272492f…f8600` | `onpc-test-artifacts-g8cosspy` | Real waiting prompt and strict ten-role census | Installed confinement matrix; public cases 50–52 |
| Fedora 44, RPM `1885c38e…62e9a` | `onpc-test-artifacts-l8w79744` | Installed confinement matrix | Real waiting prompt and strict census; public cases 50–52 |

Use the complete package hashes and source identity above when resuming.
Recover the saved Fedora snapshot's guest run through the maintained snapshot
reader before its new census; the earlier RPM's guest run and census do not
qualify the changed package. Continue live-VM troubleshooting and validation
before E2E retries, as requested. Finish owned maintenance before public tests,
and regenerate coverage after each completed E2E scenario under the existing
contract. Existing unrelated gaps remain deferred. Phase 1 stays open, and
Phase 2 does not start until every remaining Phase 1 gate passes.

### Resumed Phase 1 exit gates — final installed inputs

The resumed execution preserves both frozen packages and the complete working
tree. No product or harness correction is needed for the engineering checks.
The package hashes and package-scope source identity remain those above.

Ubuntu's final-DEB `enforcement::test_kiosk_execution_confinement` passes
**1/1, with zero failures, errors or skips**, report
`20261012T232947Z-e916ca97`, raw allocation `onpc-system-vx1reqeq`.
Product, infrastructure, collection and cleanup all pass; baseline restoration
is verified. The complete retained JUnit export is
`output/test-runs/host/exports/onpc-artifact-export-y4jjhl9m/enforcement.xml`.
All PAM credential/session/end statuses are zero, and the selected execution,
replacement, teardown, removal and policy-loss assertions pass.

Fedora's final-RPM real prompt replay succeeds in
`onpc-kiosk-approval-diagnosis-mff21oz0`, worker evidence
`onpc-e2e-evidence-x8iasgz4`. Its independent `approval-open.reply.json` reports
`approval-open` before password input. The strict frozen census passes against
saved snapshot guest run `d75de92161bd4a45b108c0c8bf410953`, observing all fourteen
confined roles, including one qualified `policykit_auth_t` thread. Required
manager, app, service, Wellbeing and PipeWire roles are present. Run, guest,
package, transfer, private mount and enforcing-label guards remain intact; no
unknown or `init_t` thread is accepted. An independent live read confirms the
final RPM hash `1885c38e9b1285798eeb6f2b2899bf49f8dbc039aa6e56c539b5edec18f62e9a`
and frozen census SHA-256
`bee01235516b68f5d2a5bf75ff7f685ecf3451a506b6a28915813cd3216cc8f4`, matching
the checkout. Owned maintenance stop and baseline restoration pass before
public acceptance. Ubuntu's preceding final-DEB prompt/census evidence remains
retained and current; neither package changed during this continuation.

All six final-package public histories pass through the exact case selectors
`tools/run-tests e2e --id '50'`, then `'51'`, then `'52'`, each using the maintained
two-target queue. The runner's freshly built format-specific inputs are
byte-for-byte identical to the frozen final DEB and RPM above. Approval reaches
the success result and automatic station exit. Denial and cancellation preserve
the request choices, pass all repeated shortcut restrictions, and return to
usable sign-in through the public form Cancel action.

| Case / outcome | Target | Report | Retained scenario evidence allocation |
| --- | --- | --- | --- |
| 50 / approved | Ubuntu | `20261012T233933Z-a2b84790` | `onpc-e2e-evidence-7q9w401n` |
| 50 / approved | Fedora | `20261012T233933Z-afcdb43d` | `onpc-e2e-evidence-wl6lhi46` |
| 51 / denied | Ubuntu | `20261012T234630Z-689a165a` | `onpc-e2e-evidence-51rizg4y` |
| 51 / denied | Fedora | `20261012T234630Z-ad04bf4e` | `onpc-e2e-evidence-edsxh10z` |
| 52 / cancelled | Ubuntu | `20261012T235343Z-999956f8` | `onpc-e2e-evidence-yylojml5` |
| 52 / cancelled | Fedora | `20261012T235343Z-c306c444` | `onpc-e2e-evidence-ymg0rq21` |

Each allocation's complete `acceptance.json` is retained under
`output/test-runs/privileged/allocations/`. Independent reads after the last
scenario confirm zero failures, the exact final package hash, and **passed**
product, infrastructure, collection and cleanup outcomes for every history.
Every cleanup record confirms baseline restoration, stopped owned processes,
preserved host/source, released lease and VM off. Both matrix JUnit exports
above remain retained. Coverage generation succeeds after each case's completed
two-target run; the scenario inventory remains unchanged.

Close-out consistency passes **313/313** in report
`20261013T000154Z-7e2d42ec`, selecting only `test_e2e_plan.py`,
`test_e2e_inventory.py`, `test_coverage_generation.py` and
`test_e2e_case_composition.py`. Markdown link checks pass for this record and
generated coverage. This continuation changes only this record and regenerated
coverage; no product edit requires another package build or installed retry.

**Phase 1 complete: 3/3 issues and every required exit gate pass.** Final pinned
VM status reads show `state=5`, `id=-1` on both targets. No owned operation
remains running, and all pre-existing work is preserved. No checkpoint commit
was created at that phase-closure boundary. The pointer advances to Phase 2,
and execution stops before starting it. Existing Phase 2–4 obligations and
whole-topic release qualification remain open; this phase closure supplies no
acceptance for those deferred functions.

### Progress checkpoint after Phase 1

The user authorized checking in all accumulated changes as staged progress,
accepting remaining imperfections while requiring no regression in product or
automation behavior. This checkpoint preserves the complete product, packaging,
diagnostic, test and documentation work. Phase 1's current-package installed
and public results above support the checked flows; they do not establish
universal regression coverage or close Phase 2–4.

A final coherent affected-host selection passes **5,605/5,605** in report
`20261013T000626Z-0c29fdf6`: 5,591 units covering the changed modules and shared
automation dependencies, 12 Wellbeing component tests, source/traceability and
static checks. All twelve changed Markdown documents pass link validation
(607 links, zero missing), and the complete diff passes whitespace checks.
Checkpoint preparation reconciles this record and removes one trailing blank
line from the feedback engineering journey. No executable behavior or package
input changes, so the retained host checks, final package builds and installed
results remain applicable. The next phase remains
**2 — Finish compatibility engineering**, not started.

At handoff, both pinned VM status reads again report `state=5`, `id=-1`.
Maintained cleanup completes successfully for both targets, reports VM and
privileged storage ready, and retains evidence within the storage limits.
No owned test or maintenance operation remains running.

## Phase 2 issue 1 execution record

The user scoped this session to retained-hidden account recovery and requested
that the remaining distro integration review run in a separate session. Phase 2
remains open until both issue checklists and its exit gates pass. No Phase 3
work is included here.

Initial owned live probes on both online app snapshots confirmed that
`accounts-daemon.service` executes `/usr/libexec/accounts-daemon`, uses
`StateDirectory=AccountsService` with `ProtectSystem=strict`, and serializes its
startup before D-Bus ownership. Both targets have root:root mode `0775` on
`/var/lib/AccountsService`, `0700` on its `users` directory and `0600` on the kiosk
record. Fedora's cache and parents carry
`system_u:object_r:accountsd_var_lib_t:s0`. The adapter must preserve that label
and accept the trusted root-group-writable parent without admitting untrusted
group or world writes.

Ubuntu reports AccountsService package/source `23.13.9-8ubuntu5.2` and daemon
version `23.13.9`. Fedora reports package/source `23.13.9-16.fc44` while its
unaltered daemon reports `26.03.0`; `rpm -V accountsservice` passes. The reviewed
Fedora build initializes a Git tree and the upstream version generator derives
the runtime spelling from the build commit's year/week. This is a version-banner
difference, not a modified installed daemon or a new cache schema. The adapter
requires that exact Fedora package in addition to its banner.

The owned startup integration and preservation/recovery boundaries are now
specified in [Lifecycle](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle).
It replaces the older upstream-only prerequisite. Independent review corrected
precommit metadata-change detection and the engineering fixtures' transaction
slot/marker assumptions. The first `make build` passed DEB but rejected the RPM's
new drop-in as an unpackaged file. The RPM inventory and its regression now cover
the drop-in, and the final `make build` passes both formats. The affected host
selection passes **624/624** in report `20261013T003423Z-307cb957`; close-out units,
source/traceability and static checks pass **315/315** in
`20261013T003840Z-3469bc76`.

Both updated online app snapshots prepared successfully. The first Fedora live
matrix preserved fresh public visibility but rejected a changed cache fingerprint
after daemon restart. Live Ubuntu reproduction with bounded fingerprint diagnostics
isolated the sole change to mode `0644` → `0600`, with identical bytes, owner and
xattrs. Upstream [startup initialization](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/23.13.9/src/main.c)
explicitly applies `0600` to every user cache before constructing the daemon.
The fresh-record assertion now requires that canonical mode while retaining exact
equality of the other fields; all retained-record comparisons remain exact.
This is a source-established fixture expectation correction, with no product
change. Both diagnostic maintenance instances were stopped and their baselines
restored before clean live repeats.

The next clean live repeat passed fresh, retained-visible, retained-hidden and
unsafe-state recovery, then reached systemd's five-starts-per-ten-seconds limit
on the final engineered restart. Live service properties and the Fedora journal
identify `Result=start-limit-hit` after successful daemon starts. Each fixture
group now independently requires a healthy active daemon before resetting only
its synthetic start budget; failed/inactive/activating states refuse without a
reset or another start. No failed product operation is retried or hidden. The
final helper units, source and static checks pass **52/52** in report
`20261013T004753Z-27024617`.

Clean owned live repeats now pass all six pre-reboot properties on **both**
targets: fresh cache/retry/restart, retained-visible preservation, retained-hidden
preservation/retry, unsafe refusal/recovery, durable daemon restart and unchanged
ordinary-account metadata. A real ACPI reboot of each same owned instance then
passes retained-hidden identity/cache/icon preservation, full provisioning retry
and ordinary-account preservation. No temporary MAC policy was installed.

| Live target | Verified package allocation | Package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-_z8hgx9b` | `bb7279b313712c2a18a5a4d51d3908a93b784f604f90793a84e4b3e8b36a9827` |
| Fedora 44 | `onpc-test-artifacts-663mce0u` | `e2ddc426f48ad9ed443cd6c88dc462cd3f0bcb4a6794ddf922a7fa461c320664` |

Both allocations are under `output/test-runs/host/allocations/`. The diagnostic
stdin subset deliberately omits atomic child injections; the installed selector
must still qualify them. An artifact-preparation attempt while Ubuntu was still
maintenance-owned refused at its baseline probe (report
`20261013T004820Z-6395a1a3`); no build or VM mutation occurred. Preparation is
retried only after owned maintenance cleanup. Final system/public validation
and cleanup are recorded below.

The first Ubuntu installed selector passes all nine installed properties,
including precommit failure, abrupt precommit exit and abrupt postcommit exit
with real hook recovery. Its next reboot request is refused by logind with
`Operation denied due to active block inhibitor`; the guarded runner correctly
stops before rebooted acceptance and restores its baseline. Report:
`20261013T005019Z-4658fd36`; retained evidence:
`output/test-runs/privileged/allocations/onpc-system-7cqsrly0/evidence/`.
The exact refusal is in `private/command-0025-stderr.txt` beside that evidence.

Owned live Ubuntu investigation repeats the classification/restart matrix and
reinstalls the same verified package through the public `make install` recipe.
Those operations pass; observed inhibitors include ordinary delays and key-handling
blocks, with no strong shutdown block. A single normal noninteractive reboot
also succeeds. This does not identify the earlier holder or establish
`--no-ask-password` as a fix: reviewed systemd v259 derives inhibitor behavior
independently of that flag. No inhibitor was bypassed, killed or removed, and no
shared reboot expectation was changed. The diagnostic owner is cleaned before
retrying only the incomplete Ubuntu selector.

### Final installed classification qualification

The exact maintained owner is `system` → area `package` →
`test_kiosk_account_classification_survives_reboot`. Both its `installed` and
`rebooted` executions pass on each required target. Ubuntu's clean retry accepts
the normal reboot request and observes the new boot without any transport edit,
inhibitor bypass or changed assertion. The earlier infrastructure refusal remains
retained; its holder was not captured and is not claimed to be diagnosed.

| Target | Matching verified allocation | Passing report | Retained system evidence allocation |
| --- | --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-khh008u5` | `20261013T010107Z-639e68d0` — 2/2 | `onpc-system-lwdjr_lb` |
| Fedora 44 | `onpc-test-artifacts-oj6v5pjl` | `20261013T005732Z-d9d24e24` — 2/2 | `onpc-system-xd5mlqel` |

These format-specific packages have exactly the live-validation SHA-256 values
above. Artifact preparation reports `20261013T004936Z-747ac0c8` and
`20261013T005023Z-35c32e9f` pass. Each final system run records nine installed
properties, then retained-hidden and ordinary-account reboot preservation.
This includes real production provisioning, all three interruption/recovery
boundaries, complete retained cache bytes, ownership/mode/xattrs and custom icon
preservation. Both runs finish collection and owned baseline restoration.
Reports are under `output/test-runs/host/reports/`; system evidence is under
`output/test-runs/privileged/allocations/<allocation>/evidence/` and remains
accessible through the maintained artifact reader.

### Public regression and scoped close-out

After both installed selectors completed, the existing public case **50**
(`E2E-016/approved`) passed on both targets through the maintained two-VM queue.
Each independent journey configures the child in Parent, enters the passwordless
restricted station, verifies ordinary shortcuts remain restricted, prepares the
request, completes native parent authentication and approval, then observes
automatic return to usable sign-in. No Phase 3 case was selected.

| Target | Passing report | Retained scenario acceptance allocation |
| --- | --- | --- |
| Ubuntu 26.04 | `20261013T010528Z-0b036d46` — 1/1 | `onpc-e2e-evidence-8sdq2qa6` |
| Fedora 44 | `20261013T010528Z-b8a1c886` — 1/1 | `onpc-e2e-evidence-e1_9fs8s` |

The two complete `acceptance.json` records independently confirm the same
format-specific package hashes as live and system qualification, zero failures,
and passed product, infrastructure, collection and cleanup outcomes. Cleanup
confirms baseline restoration, owned processes stopped, host/source preserved,
lease completion and VM off. Both final system result records and their complete
JUnit evidence remain retained after this run; the earlier Ubuntu reboot refusal
also remains available. Queue results are retained in
`output/test-runs/host/allocations/onpc-vm-queue-igqgmmr1/results.json`.

Coverage generation succeeds after the completed case on both targets. It adds
the implemented unit and installed-system inventory while leaving E2E case
bindings unchanged; inventory totals do not represent live passing results.

The final coherent affected-host selection passes **958/958** in report
`20261013T011234Z-b5fe94e8`: 956 unit/contract tests covering provisioning,
classification fixtures, system runner/input closure, packaging/activation,
resource inventory and the four E2E close-out modules, plus source/traceability
and static checks. This current report supersedes the earlier rotated host
iterations for retained close-out evidence. Both package formats passed the
final product `make build`; subsequent fixture/documentation changes do not
alter package bytes, as confirmed by the matching live, system and E2E hashes.
All four changed Markdown documents pass link validation (96 checked, zero
missing), and the complete diff passes whitespace checks.

**Scoped session complete: 1/1 issue solved. Phase 2 overall: 1/2 issues solved.**
Final pinned VM status reads report `state=5`, `id=-1` for both targets. All
owned test and maintenance operations have finished their cleanup. The user then
requested committing this validated issue-1 scope. All accumulated work is
preserved. The next session
owns only issue 2's bounded distro integration review and qualification. Phase 2
remains unchecked; Phase 3 has not started. The whole confinement effort remains
unfinished and not release-qualified until its remaining phase gates pass.

## Phase 2 issue 2 execution record

The user requested completion of Phase 2, stopping before Phase 3, with live
diagnosis and validation before E2E. Issue 1's completed recovery work is
preserved. This issue adds bounded platform qualification and evidence; it
changes no product executable, launcher, policy or package integration.

### Exact distro inputs and independent review

Owned live probes and installed qualification use actual package ownership and
source identities. The mapped Lua library is **Lua 5.4.8 on both targets**;
a Fedora specification for a different build does not establish this runtime's ABI.

| Input | Ubuntu 26.04 | Fedora 44 |
| --- | --- | --- |
| WirePlumber executable/library | `0.5.13-1ubuntu1` | `0.5.18-1.fc44` |
| Actual Lua package/source | `liblua5.4-0` / `lua5.4`, `5.4.8-1build1` | `lua-libs` / `lua`, `5.4.8-5.fc44` |
| PipeWire native modules | `1.6.2-1ubuntu1.2` | `1.6.9-1.fc44` |
| systemd | `259.5-0ubuntu3.4` | `259.9-1.fc44` |
| Shipped WirePlumber Lua scripts | 66 | 80 |

Bounded independent reviews cover the finite executable/transition inventory,
fixed launcher argv/environment, user-manager service APIs, WirePlumber's
configuration/data/native component lookup, Lua searchers and shipped scripts,
and the native module/filter-chain/LADSPA loading path. Actual installed package
verification passes. Qualification records executable mapped-file hashes,
process-namespace and `map_files` byte comparisons, trusted storage ancestry,
package/source owners and all shipped script hashes.

Ubuntu's WirePlumber import is
`a4afb5bb7a35f6b6a6a463f86d82b036e4e9cdf8`, with applied source
`42d6441cdf9f84263bccb29cf2d77747fc556c5a`. Its
[patch series](https://git.launchpad.net/ubuntu/+source/wireplumber/plain/debian/patches/series?id=a4afb5bb7a35f6b6a6a463f86d82b036e4e9cdf8)
contains README/privacy cleanup and a Snap permission module using snapd's fixed
socket/service integration, with no reviewed Lua/spawn route. Fedora's matching
[0.5.18-1 spec](https://src.fedoraproject.org/rpms/wireplumber/raw/b70cecc5256d6ad2f68569ab8942dd55408f4a71/f/wireplumber.spec)
has no downstream patch and selects system Lua. Its
[upstream tag](https://gitlab.freedesktop.org/pipewire/wireplumber/-/tags/0.5.18)
resolves to `81606cbb32d29df20147d1b68b662c1082654d81`. Review inspected tagged
source and distro source manifests; it did not independently download and hash
the Fedora source archive.

The reviewed Ubuntu
[Lua loadlib source](https://git.launchpad.net/ubuntu/+source/lua5.4/plain/src/loadlib.c?id=62ec6eef03ab9f47afdd31bc556d2e7c81a618ef)
and matching Fedora
[Lua spec](https://src.fedoraproject.org/rpms/lua/raw/50a1d18ea319352ec3f153ae29e3acad3dec4313/f/lua.spec)
retain the default-path behavior tested against the actual mapped library.
WirePlumber's trusted custom searcher remains usable; its Lua sandbox is not an
independent security boundary. The shipped scripts' eight literal `require`
names resolve to system utilities; no user-field-derived Lua loader or spawn
sink was found in that bounded set. Reviewed native Lua/component, notification,
permission-store, file-monitor and MPRIS paths add no demonstrated generic exec
route. This is not an exhaustive audit of optional codecs, LADSPA/LV2 plugins,
all distro services or every PipeWire module.

The real `sm-objects` interface accepts native `pw-module` requests.
[PipeWire 1.6.2](https://raw.githubusercontent.com/PipeWire/pipewire/1.6.2/spa/plugins/filter-graph/plugin_ladspa.c)
passes absolute LADSPA names directly to `dlopen`;
[1.6.9](https://raw.githubusercontent.com/PipeWire/pipewire/1.6.9/spa/plugins/filter-graph/plugin_ladspa.c)
also supports explicit unfiltered absolute lookup. Mapping policy must hold
independently of configuration-root sanitization. Systemd's
[property API](https://github.com/systemd/systemd/blob/v259/src/core/dbus-execute.c)
and [executor](https://github.com/systemd/systemd/blob/v259/src/core/exec-invoke.c)
apply requested profiles/contexts under the existing kernel transition boundary
before executable entry. Ignoring a profile-setting error does not waive the
executable check. No broader executable route is justified by this review.

### Live diagnosis and repeatable engineering checks

The new selector is `system` → `enforcement` →
`test_kiosk_platform_integrations`, implemented by
[system_kiosk_platform.py](../tests/integration/system_kiosk_platform.py).
The [installed-suite contract](../tests/integration/README.md#running-the-current-installed-suite)
and [Lifecycle](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
own enduring qualification requirements.

Both owned live VMs pass hostile startup environment/configuration inputs,
actual-library Lua cwd positive/empty-path negative controls and real native
module API qualification. The native positive uses a genuine trusted ELF and
observes its missing LADSPA descriptor after successful loading. An identical
user-owned copy first loads as the unconfined kiosk UID, then the same real
audio API must produce an exact enforcing kernel mapping denial. Arbitrary
loader failure or metadata-command success alone never counts. Manager/audio
identities and enforcing labels remain unchanged.

Ubuntu's initial repeatable probe lost the required audit record. In that same
VM, public `wpctl set-log-level D` exposed `failed to map segment from shared
object`; PipeWire reports every `dlopen` failure as ENOENT at normal log level.
Kernel diagnostics independently showed `kauditd_printk_skb` suppressed startup
callbacks. Linux's [audit fallback](https://github.com/torvalds/linux/blob/v6.17/kernel/audit.c)
uses the printk rate limiter. The fixture now reads the existing bounded
`printk_ratelimit` interval and spaces its single negative request accordingly,
without changing a sysctl or retrying a failed request. Fedora's auditd owns
the AVC log, so its bounded log tail supplies the record. Full live repeats
pass on both targets with the original exact denial assertions.

The service API positive executes native `systemctl --version`. Selecting
`unconfined` fails with `231/APPARMOR` on Ubuntu and `229/SELINUX_CONTEXT` on
Fedora. Even the ignore-error property form cannot execute `/bin/sh`: both
return `203/EXEC`. Only the recorded manager invocation, owned metadata key
and planted inode identities are cleaned. Both diagnostic maintenance instances
finish baseline restoration before installed/public qualification.

Host regressions cover exact audit matching, positive-before-denial and
dropped-UID controls, environment isolation, fixture inode/refusal cleanup and
bounded spacing. They use private pytest files and process-local doubles, with
no live service, bus, VM, display, shared cache or child lifetime; their
compatible scheduling inventory is explicitly reviewed. A misplaced unit
assertion initially raised `NameError`; it was restored to its owning test
without changing an expectation. The final affected unit/source/static
selection passes **501/501** in report `20261013T025648Z-5831acbc`.

### Installed and public qualification

Verified format-specific artifacts share package-source digest
`f06b80cb6e496850e47fbb00661054b68cbb205aaff1f53e63a8a674d93ae346` at
revision `2f7bb34d3fe20d1a2b44f0d5903953cc29b8393c`. Artifact preparation
passes in reports `20261013T025428Z-6b21f330` and `20261013T025518Z-a56eb9c1`.
This issue changes only tests, test scheduling and documentation, outside
`PACKAGE_SOURCE_FILES` and build-tool dependencies; no additional `make build`
gate is required for these edits.

| Target | Verified package allocation | Package SHA-256 |
| --- | --- | --- |
| Ubuntu 26.04 | `onpc-test-artifacts-9okrzvu3` | `4a9659a2eeaae3c9e8d3fe5672245c8d3d56f57a1c0608df0fe10ba1868bc064` |
| Fedora 44 | `onpc-test-artifacts-acs8813w` | `e2ddc426f48ad9ed443cd6c88dc462cd3f0bcb4a6794ddf922a7fa461c320664` |

Both installed platform selectors pass, each retaining all 13 platform
properties in `evidence/guest/enforcement.xml`, including the exact live-PID
mapping audit record. Ubuntu observes AppArmor `file_mmap`, `denied_mask="m"`;
Fedora observes an audio-domain file `{ execute }` AVC with `permissive=0`.
The complete `result.json` records independently confirm the package hashes
above, expected/executed selector equality, zero baseline-verification failures,
and passed product, infrastructure, collection and cleanup outcomes.

| Target | Passing installed report | Retained system evidence allocation |
| --- | --- | --- |
| Ubuntu 26.04 | `20261013T025537Z-bb9a8531` — 1/1 | `onpc-system-ksxcv6k3` |
| Fedora 44 | `20261013T025718Z-7cf84428` — 1/1 | `onpc-system-in8168jq` |

Reports are under `output/test-runs/host/reports/`; system evidence is under
`output/test-runs/privileged/allocations/<allocation>/evidence/` and remains
accessible through the maintained artifact reader. Both runs finish owned
baseline restoration before public regression.

Public case **50**, `E2E-016/approved`, passes independently on both targets
through the maintained two-VM queue. Its package hashes match the installed
inputs above; its broader E2E source identity is
`7c2551cc9e344161f430cf3e3a4792c7f64a4b03b551dd0d063d85e7b8c7d8c3`.
The actual public journeys observe the restricted station, password prompt,
credential acceptance, approval success and return to sign-in.

| Target | Passing public report | Retained suite / attempt evidence allocations |
| --- | --- | --- |
| Ubuntu 26.04 | `20261013T030024Z-ec1e55b5` — 1/1 | `onpc-e2e-evidence-o_s9x81n` / `onpc-e2e-evidence-1wt87ltr` |
| Fedora 44 | `20261013T030024Z-7bbde2ad` — 1/1 | `onpc-e2e-evidence-v5qc_d9x` / `onpc-e2e-evidence-8rr1ylmy` |

Both retained attempt records report passed product, infrastructure, collection
and cleanup outcomes, no first failure and complete leases. Each suite verifies
baseline acquisition and restoration with zero failures and passes final
cleanup. Queue allocation `onpc-vm-queue-lzus1n_e/results.json` records status
zero for both targets. Final pinned-VM status independently confirms both are
stopped (`state=5`, `id=-1`). No owned maintenance instance remains.

**Phase 2 closes at 2/2 issues solved with all exit gates passed.** The current
pointer advances to Phase 3, but this session stops here without executing it.
The bounded review limitations above remain explicit; Phases 3 and 4 still own
the remaining confinement obligations, so the whole effort is not yet
release-qualified.
