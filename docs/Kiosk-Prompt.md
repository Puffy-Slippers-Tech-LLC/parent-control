# Kiosk entry and unexpected password prompt

Task queue: [Ordered task queue](Kiosk-Prompt-Queue.md).
Next task: **006a — [Implement owned immutable-view primitives](Kiosk-Prompt-Tasks/006a-pin-primitives.md)**.

## Outcome

Selecting the request station must reach its usable confined form without a
kiosk password. Unrelated installed software must not become a prerequisite for
entry or invalidate a healthy retained station. Genuine authentication-policy,
required-input, ownership or enforcement failures must remain closed and leave
enough sanitized evidence in customer feedback to identify the failed boundary.

Use the shared [execution infrastructure](Execution-Plans.md),
[approval routes](Approval-Tools.md), [test ownership map](TestAutomation/README.md)
and [failure handling](../tests/README.md#handling-test-failures). Product behavior
belongs to [the specification](Specification.md#2-component-specifications) and
[kiosk confinement](SystemDesign/Kiosk-Confinement.md). This plan does not promise
exhaustive protection against every future dependency or weaken an intentional
security refusal to suppress GDM's fallback presentation.

## Symptom boundary and stop condition

This is a kiosk-entry repair plan. Its customer path starts when the dedicated
account is selected at GDM and ends at a usable confined request form, or an
intentional refusal followed by restoration and successful reentry. It covers
the observed ambient-directory rejection, the reviewed alias/name defects,
retained-manager rejection after unrelated filesystem changes, effective
passwordless authentication and diagnostics for these entry failures.

Discovery must account for the existing authentication-to-form failure stages,
but a stage map does not require a new test or redesign for every stage. Reuse
valid existing coverage. Add implementation or installed acceptance only for a
demonstrated cause of this entry symptom, or a direct safety regression risk
introduced by changing that entry mechanism. Every added task must name the
concrete source dependency, finite failing/control condition, exact selector
and affected targets. Unrelated discoveries go to their existing owner and do
not expand this queue or add acceptance gates. Failures in mandatory checks for
changed code still follow their owning failure/acceptance contract.

Required safety controls remain: required-input drift still refuses, omitted
ambient data stays outside the private view, confinement stays enforcing and
ordinary-account authentication/access is unaffected. These are targeted
regression controls for the entry fix. This plan does not qualify child time/app
limits, request approval/revocation, all kiosk escape scenarios, every desktop
service/plugin, all package lifecycle variants or the full feedback UI/transport.
Parent feedback is exercised only to collect and validate entry-failure evidence.
Mandatory checks for code actually changed still follow their owning contracts.

Do not add graphics, geometry, coordinate-based input or coordination-specific
test automation for this work. Reuse existing semantic operations and result
observers. GDM acceptance concerns refused entry, safe session state and usable
reentry after restoration; exact screen appearance, prompt layout and error-message
wording are diagnostic observations, never acceptance assertions or new adapter
prerequisites.

Close the plan when its entry regressions and those direct safety controls pass
on both declared platforms, the original failure remains diagnosable after
recovery, and all owned state is restored. No general product acceptance gate
may be added to that stop condition.

## Incident and initial audit

On 2026-10-18 at approximately 22:07–22:08 local host time, native authentication
explicitly accepted the kiosk's blank password, and account/session routing
passed. Both manager and GDM preparation then failed at `directory-layout` with
`unsafe-directory-entry`. The installed helper matched the checkout before this
work. The unrelated `/usr/share/eusoft-eudic` directory was user-owned, mode 0755.
Commit `83d502b3` had handled root-owned writable directories such as VS Code's,
but left the ownership rejection in place. Source history introduces that check
with the confinement helper in commit `eb0b7323` on 2026-10-12. Neither the v1.0
nor v1.3 tag contains that helper. The observed late-rejection cause is therefore
a compatibility regression from the newer confinement work, retained by the
October 17 partial fix; it is not established as a bug present since v1.0.
This source/history attribution and the actual incident journal do not constitute
a live comparison of the same host configuration against those older releases.

The initial read-only audit found these distinct work items. Task 001 must
verify the complete paths and coverage against the execution checkout.

| Boundary | Evidence and remaining gap | Owner in this queue |
| --- | --- | --- |
| Ambient entries | `directory_layout()` rejected non-root siblings; unrelated files, links, special types, unusual names and metadata races need a generic classification with required-input controls. A candidate is already in the checkout. Required lexical alias ancestors are missing from its required set: a post-inventory non-root symlink parent is omitted as a sibling. Three private review cases reproduced this (`20261019T053221Z-e4ed23a4`); their expected refusal did not occur. A separate private publication probe reproduced `UnicodeEncodeError` for a non-UTF-8 sibling filename (`20261019T053414Z-0ce83392`); include such names through publication, not only tab/newline checks. | 001b, 002a, 003a, 003 |
| Customer evidence | PAM/preparation records previously stayed outside feedback; native bind failures expose only `stage=bind`. A bounded admission-export candidate is already in the checkout. Actual host manager/gate producer metadata matches its reviewed parser. | 002b, 002, 010a, 010 |
| Late denial and greeter | Healthy empty-token PAM and healthy GDM entry do not prove what the user sees after preparation/binding fails, or usable recovery afterward. | 004a, 004 |
| Retained generation | `prepare()` hashes the complete ambient layout. Unrelated additions/removals or kind changes can stale the manager. Removing layout from the digest alone does not safely reuse its pinned mounts. | 005a through 007 |
| Authentication policy | Fedora explicitly refuses `without-nullok`; Ubuntu's module-presence checks do not themselves prove effective empty-token authentication. This is a separate hypothesis, not the observed incident. | 001a, 008a, 008, 009a, 009 |
| Affected existing entry evidence | Review existing account-classification, first-configuration, upgrade or native-update evidence only when a changed entry dependency affects it. A config-drift test named stale-manager reaches attestation first; do not count it as generation-stage proof. No blanket lifecycle campaign is required. | 001, 011a, 011 |
| Session launch and usable form | Native `armed`, a live manager, compositor startup and broker bus ownership are separate milestones. Required launcher/import/unit loss can end the session before paint; initial broker reads can fail after paint. Healthy public form witnesses exist, but they do not inject each startup failure. The session/readiness map below records these distinctions. | 001; changed-view consumers at 005a/005; affected public entry at 003/004/007 and final allocation at 011a |
| Post-confinement evidence | The startup collector recognizes a narrow renderer/app-exit chain on the current boot, not every missing runtime dependency or compositor cause. Failed frontend log delivery during a broker outage is not replayed. These are existing observation limits, not established causes of this incident. | Separate startup/recovery owners; Reliability 007/010 where applicable; no added kiosk-prompt acceptance gate |
| Report collection after recovery | Admission history is queried across retained boots; startup crash history is current-boot only. Both need a functioning broker export route and live authorization. An independent collector does not promise a public archive while configuration is invalid. | 002 host composition/clipping; 010a/010 actual restored-entry/reboot/Parent archive |

The existing 32,768-entry, four-generation, 512 MiB and preparation-timeout bounds,
required native inputs, lexical aliases, privilege helpers, MAC enforcement,
ownership locks and package quarantine retain their safety contracts. Enlarged
inventory and timing work remains with [Reliability 008](Reliability-Tasks/008-kiosk-scaling.md).
New gaps that pass the symptom-boundary test need finite prerequisite briefs
before their consumers under the shared plan contract. Other discoveries remain
with their existing owners; they do not authorize a release-wide campaign.

## Execution and acceptance

### Authentication and account audit — 001a

Reviewed against the execution checkout on 2026-10-19 UTC. This is the finite
authentication/account portion of the entry map; it grants no new installed
acceptance. Expected public behavior remains the
[dedicated request station](Specification.md#2-component-specifications), with
the [lifecycle admission boundary](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
and [diagnostic contract](SystemDesign/Logging-and-Feedback.md#kiosk-admission-diagnostics)
as owners. A successful password check, account callback or saved preference
alone does not prove a usable confined form.

Read-only incident verification used the maintained journal reader for
2026-10-18 22:07:40–22:08:05 America/Los_Angeles. At 22:07:46 the native
`gdm-password:auth` record explicitly accepted the blank password, followed by
allowed account and session routing records (`dedicated`, `wayland`, native
status 0). At 22:07:47 manager preparation and at 22:07:48 gate preparation
reported `directory-layout/unsafe-directory-entry`, followed by native
`execution-boundary/prepare` denials. Repeated attempts in that window show
the same separation. These are retained host incident observations, not a test
of this plan's candidate or proof of the greeter's exact fallback appearance.
No password was entered and no authentication state was changed for this review.

Source history independently confirms the attribution above:
`git log --diff-filter=A` first adds `tools/kiosk_confinement.py` in
`eb0b7323b1aff906d75dba8218d4c80464c444a1`, dated 2026-10-12 17:12:21 -0700.
That revision's complete `directory_layout()` rejects any immediate child with
non-root ownership as `unsafe-directory-entry`. The v1.0 and v1.3 trees contain
neither that preparation helper nor its native header/integration helper.
`83d502b3` masks root-owned writable sibling directories but retains the earlier
ownership rejection. This establishes a newer late-session regression, not an
authentication failure or a live historical comparison with those releases.

The selectors below are current registered system selectors, confirmed through
the read-only `tools/run-tests system --list` and
[persistent case assignments](../tests/integration/system_case_ids.py).
Coverage means the assertions implemented by the named owner; it does not claim
a fresh passing execution. Host tests use private fixtures rather than the host's
authentication configuration.

| Boundary / trigger | Intended public result and source route | Existing coverage and remaining allocation |
| --- | --- | --- |
| Effective empty-token authentication | Selecting a supported station reaches the confined form without a kiosk password. An incompatible administrator policy must remain intact and cause the settled configuration/admission refusal. [Shared postinst](../packaging/lifecycle/postinst.in) validates the owned identity before `passwd --delete`; this creates an empty credential, not an authentication bypass. The [time-limit profile](../data/pam-configs/oh-no-parent-control-session-limits) skips only the product's time check for the station; vendor authentication still runs. | `package / test_first_configuration_interruption_retry` (4) calls [empty_authentication_probe()](../tests/integration/system_kiosk_admission.py#L312): real `pam_authenticate` with an empty-token conversation, then a separate `pam_acct_mgmt` result, including after retry and reboot. `test_kiosk_login_admission` (268) calls account management only and cannot establish empty-token authentication. Effective incompatible-policy cases remain with 008a/008/009a/009; their selectors are not yet registered. |
| Distribution authentication policy | [Fedora preflight](../packaging/fedora.inc) refuses selected `without-nullok`; [fedora_pam.configure()](../packaging/fedora_pam.py#L90) also refuses it before creating a new owned profile, uses `authselect check` without force, preserves original features and refuses changed selections/owned bytes. [Ubuntu activation](../packaging/ubuntu.inc) preserves local configuration and checks product module/rule presence, but does not evaluate effective GDM auth include/control flow or empty-token support. | [test_nullok_policy_is_not_weakened](../tests/unit/test_fedora_pam.py#L173) asserts refusal without profile creation/selection. [Ubuntu activation regressions](../tests/unit/test_package_configuration.py#L976) reject missing/optional/commented kiosk rules and legacy helpers; they do not cover an otherwise integrated stack rejecting empty tokens. The read-only Ubuntu host sample routes GDM to `common-auth`, where `pam_unix.so nullok` succeeds past SSSD/deny into permit and the kiosk time-check skip. That sample and the incident prove no policy matrix. 008a must settle the finite supported/refused composition, 008 its validation/rollback and closed reason, 009a/009 actual incompatible-policy/refusal/restoration/public-reentry histories. |
| Account ownership, privilege, home and visibility | [provision.account()/main()](../tools/provision.py#L322) reject root or `sudo`/`adm`/`wheel` membership, a wrong reserved home and unsafe home ownership. [Postinst](../packaging/lifecycle/postinst.in) refuses a missing/substituted/mismatched UID marker before changing existing credentials. `accounts_service_cache_kiosk()` verifies public visible/saved state and durable cache; retained classification repair uses the owned versioned start-pre adapter and preserves other metadata. Refusal must not expose another desktop or alter ordinary accounts. | [test_provision.py](../tests/unit/test_provision.py) owns identity/cache/version/transaction refusals; [test_package_configuration.py](../tests/unit/test_package_configuration.py) owns unowned-account ordering. `package / test_kiosk_account_classification_survives_reboot` (5), through [system_kiosk_accounts.exercise()/verify_reboot()](../tests/integration/system_kiosk_accounts.py#L331), covers fresh/retained visibility, unsafe cache refusal, interruption/retry, daemon restart, reboot and both ordinary roles' exact retained metadata. Its [runner-owned public activation](../tests/integration/system_runner.py#L1573) is distinct from these internal checks. Review affected receipts at 011a; do not reopen unrelated lifecycle histories. |
| Expiry and incomplete package configuration | [configure_account_access()](../tools/provision.py#L391) journals the original expiry in a private UID-bound record, expires fresh accounts at creation and requarantines owned retries before other configuration. It refuses changed ownership/expiry/records, survives interruption/reboot and restores only the captured expiry after shared PAM verification and final confinement integration. Home setup drops credentials directly. Incomplete configuration must leave entry closed even if the account is visible and its password empty. | [KioskConfigurationAdmissionTests](../tests/unit/test_provision.py#L245) covers original expiry values, interrupted writes/release and unsafe or foreign records; [package ordering tests](../tests/unit/test_package_configuration.py#L119) cover provisioning/setup/PAM/confinement/release failure. [system_first_configure.verify_quarantine()/exercise()/verify_reboot()](../tests/integration/system_first_configure.py#L189), case 4, keeps two configuration interruptions, the owned empty-password retry, denied manager startup, ordinary account controls, successful retry and reboot together. Ubuntu's account expiry maps to PAM status 7 while empty-token authentication separately succeeds; Fedora preserves expiry or an earlier product permission denial. A numeric account denial is not evidence of a failed password. |
| PAM service scope and control flow | [Native account/session callbacks](../tools/pam_oh_no_parent_control.c#L236) admit the station only through `gdm-password` and `systemd-user`; ordinary accounts avoid the routing helper/lock. The manager's `kiosk-manager-credentials` path permits credential setup/deletion, always refuses station authentication and preserves ordinary `auth include other`. [Integration rendering/verification](../packaging/kiosk_confinement.py#L194) audits logical includes/substacks, session jumps, supported callbacks and owned/vendor bytes; unsafe flow or pending vendor replacement refuses configuration. These guards supplement authentication, not replace it. | [test_kiosk_login.py](../tests/unit/test_kiosk_login.py#L395) exercises real private libpam handles for manager credentials, wrong services, integrity and callback ordering. [test_kiosk_confinement.py](../tests/unit/test_kiosk_confinement.py) owns parsing/final-gate composition. `enforcement / test_kiosk_login_admission` (268) verifies native `login`/`sshd` permission denials, effective SSH PAM routing and ordinary account controls. `package / test_pam_environment_installation_variants[plain,distro-profile,administrator-override,pending-vendor]` (283–286) owns the four independent install/configure/reboot/removal histories; these session/environment variants are not incompatible empty-token auth tests. Final execution/control-flow crossings pass to 001b; preserve the existing histories and ordinary callbacks. |
| Admission lease and login serialization | [kiosk_admission()](../tools/kiosk_confinement.h#L40) checks the private root-owned single-link admission inode, holds a shared lease through the PAM handle and refuses a writer/removal barrier. [kiosk_account_check()/run_kiosk_check()](../tools/pam_oh_no_parent_control.c#L91) separately serialize GDM routing through a no-follow private login lock. Busy/unsafe locks deny; failed account state is cached and session opening without a successful bound account check refuses. PAM teardown closes descriptors without unlinking the lock. A helper retains the lock if its worker aborts. | [Native private-fixture regressions](../tests/unit/test_kiosk_login.py#L429) cover unbound/failed/repeated callbacks, contention, unsafe paths, abort, inherited lease and bounded helper exit. These are engineering coverage, not installed graphical acceptance. Journal markers distinguish `lock=unsafe/busy`, `session=unbound`, helper failure/timeout and `removal-barrier`. 001b must reconcile preparation/lifecycle locks with the final native boundary; no new speculative lock acceptance campaign is allocated. |
| Saved route, actual transport, repair and timeout | [verify_session()/main()](../tools/oh-no-parent-control-login-check#L66) check integrity first, then the dedicated saved session; account stage checks saved Wayland while session stage checks PAM's actual `XDG_SESSION_TYPE`. A wrong route/transport is repaired through public setters and read back, but that attempt stays denied. Unknown identity, malformed/unavailable metadata, failed repair or timeout denies. Each bus call is noninteractive (4-second bus / 5-second process limit); the [native wrapper](../tools/pam_oh_no_parent_control.c#L91) bounds the whole helper at 25 seconds, kills/reaps its own child and records failure. Saved routing and `GDMSESSION` cannot attest the next executable. | [Routing tests](../tests/unit/test_kiosk_login.py#L193) cover valid no-write checks, changed/unset defaults, actual transport, failed repair and sanitized unavailable/timeout categories. The native private-fixture tests cover helper timeout and session failure/retry. [system_kiosk_admission.verify()](../tests/integration/system_kiosk_admission.py#L363), case 268, tests alternate saved session/transport denial, repair and fresh account retry; it opens no session and proves neither actual session transport nor a usable form. 001b owns final execution; 001 owns session-to-form/readiness and 004a/004 the demonstrated late-refusal/public-recovery gap. |

**Diagnostic coverage and limits.** The complete
[_admission_marker()/collect_kiosk_admission_diagnostics()](../broker/oh_no_parent_control/dependency_diagnostics.py#L297)
path and its [export caller](../broker/oh_no_parent_control/service.py#L761)
recognize the exact native blank-password success marker, account/session
statuses, service/lock/unbound/helper/removal-barrier refusals and the helper's
closed routing/recovery/reason categories. Producer provenance is checked before
projection; raw identities, metadata, messages and exception text are excluded.
The collector runs before snapshot even in diagnostics-only mode and without
kiosk configuration or a live manager. Its 24-hour, 200-record read and 20-marker
export are bounded; unavailable/partial observations are explicit.
[test_diagnostics.py](../tests/unit/test_diagnostics.py#L301) covers synthetic
authentication → routing → denial → recovery archive round-trip, spoofing,
numeric bounds, malformed/empty/oversized input, timeout and clipping. It is
host fixture coverage, not an actual Parent report from the incident.

There is no reviewed general vendor authentication-failure or native account
expiry marker in this projection; absence of the blank-password success marker
does not establish authentication failure. Package ownership/quarantine failures
also have local package evidence rather than a distinct exported admission cause.
001 must classify these limits against the symptom boundary and combine 001b's
native map; discovery alone creates no new test requirement. 008a/008 own the
specific incompatible-auth-policy reason. 002 already owns the demonstrated
clipping loss of authentication/routing/recovery context under repeated denials;
010a/010 retain actual Parent-archive proof after recovery/reboot. Existing
unaffected branches remain with their current owners. No arbitrary PAM matrix,
host authentication change or installed run belongs to 001a.

001a review acceptance passed: the authentication/account map, incident journal
sequence, source-history attribution and current selector limits were checked;
remaining gaps have the owners above. No VM, product installation, process,
temporary fixture or authentication mutation was created, so no owned runtime
restoration remains. Markdown links passed before queue close-out; the maintained
four-module documentation consistency selection recorded 313/313 in run
`20261019T063757Z-1fe129b7`. That original report subsequently rotated under the
runner's three-run retention policy during 001. The same selection passed again
for 001's final documentation in run `20261019T065201Z-bbb76ba6`, whose report
also rotated during 002a handoff correction. The fresh matching selection is
retained in [002a's correction report](#classification-prerequisite-discovery--002a);
this is documentation validation, not a recovered original receipt.
Only documentation changed, so no package build or installed check was required.

### Preparation and native admission audit — 001b

Reviewed against `93e2a66d064e81e7366730567d2e3ff357c3f2f1` on 2026-10-19 UTC.
The pre-existing proof-document edit was preserved. This review continues 001a
at the final PAM caller; it supplies no installed acceptance. Expected results
remain in [confinement](SystemDesign/Kiosk-Confinement.md#native-execution-and-executable-identity)
and [lifecycle](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle):
healthy entry reaches the confined form, unsafe required inputs deny entry,
and unrelated software must not invalidate a healthy station. A refusal alone
does not prove the greeter result or subsequent usable recovery; 004a/004 own
that public history, and 001 owns session-to-form readiness.

**Consumed roots and trust scope.** The finite
[policy inventory](../tools/kiosk_confinement_policy.py#L22) measures native
entrypoints, selected systemd libraries, WebKit/scanner/Glycin paths and the
blocked optional GStreamer Python plugin. Policy generation reserves the
distribution's systemd and GStreamer library directories; the preserved Polkit
helper contributes its own parent. Preparation builds skeleton parents under
`/usr`, including the confinement payload, and binds other accepted immediate
siblings. This is not a recursive trust measurement of every sibling subtree.

The [fixed launchers](../tools/kiosk_session.c#L17) actually consume
`/usr/bin/oh-no-parent-control`, `/usr/bin/gnome-service-client`, the installed
`/usr/lib/oh-no-parent-control/{kiosk,common}` Python roots, and the extension's
`wellbeingService.js` under `/usr/share/gnome-shell/extensions`. Audio explicitly
uses `/etc/wireplumber:/usr/share/wireplumber` and `/usr/share/wireplumber`, with
empty default Lua search paths. General XDG roots are `/etc/xdg`,
`/usr/local/share` and `/usr/share`; the manager additionally consumes the owned
payload's `user-units`, and Ubuntu D-Bus uses its `session-data` prefix.
`/etc` is outside the `/usr` overlay; `/usr/local` and accepted share/library
siblings can expose nested runtime data through a shallow directory bind.
Trust of their immediate directory does not establish ownership, immutability
or a content digest for all nested scripts, configuration or plugins. This is
a source-reviewed limit, not a demonstrated nested-input exploit or a new
qualification campaign. 005a must classify these actual consumers when defining
material identity; 001 must distinguish an unavailable consumed runtime input
from an unrelated sibling and map its later readiness failure. No new root or
general desktop-service obligation is inferred from an arbitrary policy read rule.

The following selectors name current code and registration, not fresh passes.
Host selectors below are in `tests/unit/test_kiosk_confinement.py` unless stated
otherwise; installed case 267 is
`enforcement / test_kiosk_execution_confinement`.

| Boundary / trigger | Intended result, source and current witnesses | Remaining allocation / diagnostic limit |
| --- | --- | --- |
| Identity, attestation and enforcement | [prepare()](../tools/kiosk_confinement.py#L486) verifies the recorded non-root account, successful-load attestation and exact config/policy digest pair before enforcement and inventory. Missing, changed or non-enforcing inputs refuse, without adopting unpacked bytes. `test_preparation_refuses_snapshot_changed_after_verification_before_inventory`, `test_payload_drift_requires_native_and_boot_refusal_before_exact_recovery` and case 267's `verify_payload_attestation_faults()` / `verify_admission_faults()` distinguish drift, native denial and exact restoration. | Intentional refusal; reuse unaffected proofs. Preparation has distinct identity/attestation/payload/enforcement stages. AppArmor must be enforcing; SELinux additionally checks every generated role and the preserved vendor helper domain. Missing dependencies after this boundary pass to 001. |
| Native inventory and alias trust | [trusted() / inventory()](../tools/kiosk_confinement.py#L92) check original lexical ancestors, every resolved target, root ownership, prohibited write bits, native ELF bytes, roles and substitution source/destination identity. Systemd's selected library directory contributes its finite installed native libraries. Host `test_native_inventory_validates_lexical_alias_and_every_target_path`, `test_native_inventory_refuses_relative_symlink_cycles` and substitution tests cover measurement; case 267's `verify_admission_faults()` covers an installed alias refusal/restoration. | Measurement-time trust does not cover later layout drift. All three retained lexical-parent/intermediate-target failures remain open at 002a; none may become an ambient omission. Local stages distinguish executable/privileged inventories. |
| Layout, required completeness and races | `directory_layout()` constructs the finite owned skeleton, masks unsafe unrelated directories and omits unsafe files/links/special entries or unsupported names. Required inputs must refuse. `test_directory_skeleton_preserves_links_without_following_them` and `test_writable_sibling_contents_never_enter_private_generation_or_bindings` cover private layout/empty placeholders; signed-helper tests require exactly one preserved destination. | The required set lacks full lexical alias ancestry, and completeness currently covers preserved helpers rather than every measured native destination. The retained missing-destination probe demonstrates acceptance despite that absence. 002a owns required ancestry/completeness, metadata/readlink/disappearance controls and actual manager/gate non-UTF-8 publication. 003a/003 own native isolation; host placeholders do not prove it. Aggregate classifications omit names/paths. |
| Drift after layout | Native binding reopens and checks source/target metadata, refuses unowned/writable input and checks the preserved helper's measured device/inode/size/timestamps/mode/UID/GID before and after mounting. Host `test_native_preserved_identity_checks_every_python_assertion_field`, `test_native_preserved_identity_refuses_real_post_measurement_file_changes` and `test_native_binding_detaches_only_its_staging_mounts_after_readonly_clone` cover these branches. | An accepted ambient source disappearing or becoming unsafe before binding still aborts entry. This is the existing source-reviewed availability gap at 002a, not permission to weaken native checks. Required drift stays closed; an independent safe mechanism, if needed, requires its own bounded prerequisite there. Native failures currently collapse to `stage=bind`; 002b owns cause production. |
| Generation and manager identity | `prepare()` hashes config/policy, measured native/preserved records and the whole ambient layout. Gate [manager_generation()](../tools/kiosk_confinement.py#L418) obtains systemd's manager PID, pins it with a pidfd, checks all four UIDs, enforcing label and `/proc/PID/root/usr/.../generation`, then checks exit. A mismatch refuses without killing/replacing the manager. The retained ambient-addition model reaches `manager-generation-stale` despite unchanged required material. | 005a/005 and 006a/006b/006 own material/pin selection and admission composition; 007a/007 own actual retained-manager histories. Production does not independently recheck MainPID, every thread or namespace identity; the stronger engineering `manager_boundary()` observer does. 005 owns that retained-view proof. Removing layout from the digest alone supplies no safe source lifetime. Preparation projects stale-manager/reboot-required separately. |
| Runtime ownership and interrupted publication | [reclaim_interrupted() / prepare()](../tools/kiosk_confinement.py#L451) and `verify_tree()` require private root-owned runtime/generation metadata, independent copied inodes, exact records, hashes/modes/labels and uncontaminated placeholders. Only owned incomplete generations are reclaimed; mounts, hardlinks, unknown files or foreign ownership refuse, with only expected private-tree symlinks allowed. Completed generations survive until reboot; four generations, 32,768 layout entries and 512 MiB remain bounds. Bindings publish through an owned temporary file and atomic replacement. | Existing preserved-helper preparation/reinstall tests cover stable reuse, changed assertions and exact signed publication. Binding text encoding still fails on a surrogate filename after escaped JSON succeeds; the retained probes exercise publication for both roles. 002a owns that repair. The preparation stages distinguish runtime, recovery, generation-create/verify and bindings; unrecognized exceptions become `verification`. |
| Mount attachment, replacement and staging detach | [bind_kiosk_executables()](../tools/kiosk_confinement.h) validates the private manifest, creates a private mount namespace, binds through checked descriptors, recursively attaches the skeleton over `/usr`, makes the clone recursively read-only, then detaches only its recorded staging mounts. Any failure refuses before MAC. The host detach selector above checks ordering/failure controls; case 267's `verify_updates()` checks private dentries across actual executable/library/plugin-parent replacement and manager reexec. | A retained namespace keeps its inode pins after host unlink/rename, but detached staging placeholders are not reusable mounted source trees. Existing replacement safety does not prove admission availability after a changed ambient layout. 005a/005 must specify immutable source lifetime; 006/007 must witness it. Native manifest/namespace/mount/read-only/detach causes remain 002b/002. |
| Admission, preparation and lifecycle serialization | [Native admission](../tools/kiosk_confinement.h) keeps the shared admission lease on the PAM handle and holds the no-follow exclusive preparation lock across runtime creation, helper, binds and MAC. Lifecycle configuration takes shared admission then exclusive preparation; loader/removal barriers take exclusive admission/routing/preparation. Unsafe metadata, missing barriers or contention deny. Host `test_install_refuses_native_preparation_before_policy_or_record_mutation`, `test_install_preserves_existing_admission_and_excludes_preparation_through_attestation`, private PAM tests in `test_kiosk_login.py` and case 267's held-admission loader control cover the crossings. | Intentional refusals with existing ownership; no new lock campaign. Routing's separate login lock and bound account/session state remain as recorded in 001a. Preparation lock errors have only the native stage; detailed bind causes are scoped to 002b. |
| Bounded helper, environment, capabilities and final MAC | Native preparation has a 60-second whole-helper deadline and reaps its own child; integration verification and the manager query each have five-second deadlines. Failed helper exit, runtime setup, manager-only unit environment, ambient-capability clearing or MAC denies. Ubuntu immediately verifies AppArmor; Fedora verifies pending GDM exec context or immediately confines the manager PAM caller. No subprocess follows final MAC. Case 267's `verify_execution_boundary()` performs an allowed actual exec before forbidden final-exec controls and verifies the manager boundary. | Intentional closed failure; helper success or `outcome=armed` does not prove app readiness. Native records separate identity/admission/lock/runtime/prepare/bind/environment/ambient/mac/armed, but generally lack a cause. Existing routing timeout coverage remains separate from preparation timeout. 001 owns post-boundary startup/readiness projection. |

**Evidence applicability and remaining proof.** The historical
five-failure review (`20261019T061016Z-d39f14ad`; its export has retired under normal retention)
contains `alias-directory`, `alias-link` and `target-link` controls that expected
refusal but did not raise, a publication `UnicodeEncodeError`, and the ambient
generation mismatch. The historical follow-up report
`20261019T061847Z-d1c50a84` (export retired under normal retention during 003a)
recorded missing required destination, manager/gate encoding and ambient digest
failures. Their temporary probes were removed; those names are historical
engineering receipts, not maintained runnable selectors or installed races.
Commit `83d502b3` handled root-owned writable directories only; it retained the
non-root-owner rejection, did not solve alias ancestry or encoding, and did not
remove ambient layout from generation identity. The current candidate handles
more ambient classifications but still has the demonstrated gaps above.

The config append in case 267's `verify_execution_boundary()` is not reattested:
it reaches payload-attestation refusal before manager comparison. It supplies
no generation-stage acceptance. The separate
[stale_admission()](../tests/integration/system_native_update.py#L743) requires
the specific generation reason. Its only caller is `retain_upgrade()`, dispatched
by [test_install_smoke.py](../tests/system/test_install_smoke.py#L52) and registered
as case 289, `package / test_native_dependency_update_retained_session`.
That complete two-phase history checks retained mappings/manager/generations,
enforcement, loader exclusion, safe reexec, public exit and reboot recovery;
the helper alone is not an independent public-entry history.

The [retained case 289 receipts](../tests/README.md#core-installation-and-runtime-compatibility)
are Ubuntu `20261018T221414Z-71987d6a` and Fedora
`20261018T221414Z-ffdaf92b`, in `onpc-evidence-bundle-imeub3ps/evidence.zip`
(SHA-256 `fdbf8cf7e9732308ceee22a720fdaf5df6d0d1b6c0f4b2d5e1916beacbe37df1`).
Read-only bundle inspection confirmed both native-update phases and product
revision `9162f12d8d92`. Current `directory_layout()` classification, required-set
and diagnostic inputs differ from that revision. Those are historical
generation-stage receipts; no current-candidate receipt was established here.
001 and 011a/011 must allocate matching input comparison or the affected complete
history, rather than reuse a test name or source link as proof.

The [diagnostic parser](../broker/oh_no_parent_control/dependency_diagnostics.py#L294)
recognizes these preparation/native stages only with reviewed root producer
provenance. It exports closed categories and bounded errno/status/source lines,
not arbitrary exception text. Native bind has no detailed cause yet; 002b/002
own production/projection. The existing 20-marker clipping defect can displace
authentication/routing/recovery context under repeated denials; 002 owns it,
and 010a/010 own actual Parent-archive recovery/reboot proof. No new independent
prerequisite is needed to finish this review: the demonstrated entry gaps
already have finite owners. Session/readiness reconciliation remains task 001.

001b review acceptance passed: preparation/native stages, consumed roots,
required-input/race controls, exact selectors and historical generation receipts
were checked. Both read-only workers finished before acceptance. No product,
VM, fixture or persistent process was created or changed, so no runtime
restoration remains. Only documentation changed; no package build or installed
check is required by this review brief. Changed Markdown links passed, and the
required four-module documentation consistency selection passed 313/313 in run
`20261019T064419Z-1aad8930`. That original report subsequently rotated under
the runner's three-run retention policy during 002a discovery. The same selection
is included in the fresh discovery validation below; it does not recover the
original receipt or repeat the completed source review.

### Session, readiness and diagnostic reconciliation — 001

Reviewed against `443b248a1ad07044dfe22c0dd3f9f59469446b69` on 2026-10-19 UTC,
with the pre-existing proof-document edit preserved. The 001a and 001b tables
above remain the cumulative authentication/account and preparation/native maps;
this section completes their session-to-form and feedback crossings. Review
acceptance supplies no installed acceptance for a later row.

**Classification of the earlier stages.** Effective incompatible authentication
policy is a hypothesis with finite owners 008a/008/009a/009, distinct from the
incident's successful blank-password authentication. Identity, account expiry,
package quarantine, unsafe routing, wrong service/transport, unbound PAM state,
lock contention, failed integration, required inventory/alias/type drift,
attestation/policy loss, unsafe runtime/recovery/publication, native environment/
capability/MAC setup and helper deadlines are intentional refusals with the
specific coverage limits in 001a/001b. Their allowed/armed markers prove only
their own stage. The reproduced ambient classification, lexical-alias ancestry,
required-destination completeness and non-UTF-8 publication defects are in-scope
gaps at 002a; post-layout ambient disappearance/trust drift remains there too.
The whole-layout digest and retained source-lifetime gaps belong to 005a–007.
Native bind cause production, projection and causal-context clipping belong to
002b/002. Generic vendor authentication/account-expiry and package-ownership
cause export remain separate-owner observations; 008 owns only the settled
incompatible-policy reason. No absence of an authentication marker is itself a
failed-password result. These classifications preserve the original incident
and `83d502b3` attribution, the exported failing probes and their exact limits.

**Post-boundary failure/coverage map.** The selectors here identify current
maintained functions and their assertions, not executions in this review.
`unit`, `ui` and `component` selectors use their full file/function names below;
variant descriptions are input selections, not invented collected node IDs.
Installed system selectors retain the area/test names and IDs in 001a/001b.

| Boundary / finite trigger | Intended public result and diagnostic producer/collector | Exact existing coverage, classification and remaining owner |
| --- | --- | --- |
| Fixed session launcher setup/exec fails, or caller supplies arguments | [Native session main()](../tools/kiosk_session.c) fixes `gnome-session --no-reexec --session=oh-no-parent-control`, clears injection variables and rejects arguments. Failure exits closed with `onpc.kiosk session startup outcome=failed`; it must not expose another desktop. This marker is not recognized by either admission or startup-crash projection. | `unit tests/unit/test_kiosk_login.py::test_session_entry_fixes_command_and_removes_startup_injection` and `::test_session_entry_rejects_alternate_arguments_without_executing` cover fixed command/environment and argument rejection in compiled private fixtures. Missing real `gnome-session`/exec recovery is source-reviewed missing proof, not those tests' assertion. Separate lifecycle/runtime-compatibility owner unless changed entry inputs affect it; 004a/004 still own only the plan's required-input late-refusal history. |
| Required compositor/app unit cannot start, compositor exits, or app exits before paint | The [session target](../data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf) requires compositor target and app. The [app unit](../data/systemd/user/oh-no-parent-control-app.service) is `Type=simple`, `Restart=no`; both success and failure lead to session shutdown. Admission must remain confined; a session exit returns to sign-in. Unit activation is not usable-form readiness, and there is no product startup watchdog that bounds all compositor/app construction. | Healthy public `e2e --id 47` (`kiosk_cancel.py / kiosk-cancel`) and 50–52 (`restricted_station.py / approved, denied, cancelled`) reach the form and ordinary exit. They do not force compositor/pre-paint failure. No dedicated installed negative selector was found for those faults. `collect_kiosk_diagnostics()` recognizes app exit/status, core dump, OnFailure shutdown and session-target stop, but no compositor-specific cause. Separate lifecycle/Frontends observation; Reliability 007/010 own applicable abnormal-exit/recovery work, without a new gate here. |
| Missing Python/GI/GTK/shared module, library or actual runtime data after native admission | [Installed Python entry](../kiosk/oh-no-parent-control) reports fixed `onpc.runtime startup failed` on import failure and exits 1; main imports dependencies before installing app exception hooks. A missing consumed input cannot be classified as harmless unrelated software. Generic loader/import text is not exported by the narrow journal parser; an app exit may identify the boundary without the dependency cause. | `unit tests/unit/test_package_payload.py::test_production_modules_import_without_preview_files` proves positive isolated imports from staged production roots, including notifications; it does not inject missing installed dependencies. Native missing-required-ELF refusals remain in 001b. Other missing-input branches are source-reviewed missing proof with the runtime-compatibility owner. 005a already owns deciding which actual view consumers affect material identity; 011a allocates only receipts invalidated by changed inputs. |
| Broker fails before publication or disappears after confinement | [Service construction/register/main](../broker/oh_no_parent_control/service.py) requires policy and extension reconciliation before object publication; cap cleanup/log failure does not prevent readiness. [Broker launcher](../broker/oh-no-parent-control-broker) enforces migration/trust prerequisites; its unit has a 180-second startup budget. Broker failure is deliberately not a separate GDM gate. The form must report unavailable operations rather than grant access; system-bus acquisition can fail before the request window is built. Structured service/runtime errors exist only when their logging route survives. | `component tests/component/test_broker_startup.py::test_startup_witness_tracks_real_publication_and_required_failures` covers policy, extensions, caps, registration and logging inputs over a private bus. It is not installed GDM/outage/reentry proof. The feedback-confinement qualifier described below injects an outage only after readiness. General broker-outage recovery is a separate lifecycle/diagnostic observation, not an incident fix established here. |
| Initial child/approver/preference read fails or times out after app start | [RequestWindow load/callback and error paths](../kiosk/oh_no_parent_control_kiosk/main.py) issue `ListKioskUsers`, `ListApprovers` and selected-child `GetPreferences` with 30-second call deadlines. Failures log `kiosk.017`, `.019` or `.022` and show a fixed unavailable result with reporting/exit; controls remain gated on successful loaded inputs. Exception hooks/reporting-only fallback start only after imports. Frontend `LogEvent` delivery is asynchronous and can be lost with the broker. | `ui tests/ui/test_request_form_component.py::test_shared_loading_keeps_controls_disabled_until_preferences_arrive` covers delayed successful preferences for kiosk and overlay. `::test_service_failure_shows_only_redacted_public_copy` and `ui tests/ui/test_error_feedback.py::test_request_error_review_restrictions_and_submission` fail Request **after** readiness. No dedicated maintained UI negative selector was found for initial list/preferences failure or the true 30-second timeout. This is missing proof with Frontends/runtime compatibility, not a new plan defect or test requirement absent an affected entry dependency. |
| Initial language read fails; lists are empty; selected child has controls disabled | Language failure exposes its error state and Preferences retry; empty child/approver sets and disabled limits have intentional explanations and disabled requests. These states are not evidence of failed authentication. `form-painted` waits loaded inputs/language and no pending modal/transition; it is an observational witness. `form-presented` records frame feedback separately, with a two-second observation timeout; neither marker alone certifies customer readiness. | `ui tests/ui/test_language_settings.py::test_failed_startup_read_is_reported_and_preferences_retries` covers kiosk/overlay/parent. `ui tests/ui/test_request_form_component.py::test_kiosk_no_child_explains_how_to_continue`, `::test_no_approver_explains_why_request_is_unavailable` and `::test_control_disabled_never_submits` cover intentional unavailable states. `unit tests/unit/test_e2e_kiosk_entry.py::test_station_refuses_incomplete_form_even_when_required_controls_exist` and `::test_form_checks_fresh_language_completion_before_outer_deadline` protect observer completeness, not installed product failure/recovery. Existing covered behavior; no new scope. |
| Estimate or optional notification/authentication service is unavailable | Estimate failure logs `kiosk.023`, reports the error and retains request availability when its required inputs are otherwise valid. The target only Wants notification/Polkit-agent services; their availability is not a mandatory first-paint gate. Later authentication failure must not grant access. | `ui tests/ui/test_request_form_component.py::test_footer_special_cases_keep_requests_available`, with estimate-unavailable inputs for both modes, checks enabled submission after closing the report; it does not submit during a real outage. Public 50–52 cover later administrator approval/denial/cancellation, not an absent-agent startup fault. Existing optional-service/request owners; no new audio/notification/approval qualification in this entry plan. |
| Product reboot guard, retained live manager or previously failed manager | Diagnostics-only broker mode permits checked presentation/export reads and returns `RebootRequired` for policy operations; station shows the restart explanation. A mismatched live manager is refused without replacement (001b). [Successful configuration](../packaging/lifecycle/postinst.in) resets only the verified account's failed unit after confinement and broker activation; query/reset failure retains retry records. It never starts/stops/restarts a live manager. | `component tests/component/test_broker_startup.py::test_pending_reboot_exports_customer_evidence_over_private_bus` and `::test_other_reboots_leave_frontend_startup_available`; `ui tests/ui/test_error_feedback.py::test_product_update_modal_reboot_and_dismissal`; `unit tests/unit/test_package_configuration.py::test_configuration_retires_only_the_owned_failed_kiosk_manager`, `::test_kiosk_failed_state_recovery_preserves_configuration_retry`, `::test_failed_manager_recovery_refuses_unowned_kiosk`. System case 5's [public activation](../tests/e2e/kiosk_entry.py#L72) distinguishes pre-reboot notice from post-reboot form/cancel/census. Intentional covered branches; historical receipts need exact changed-input comparison at 011a. Ambient retained-manager regression stays with 005a–007. |
| Enforcing renderer denial / Vulkan mapping failure / Mesa crash before paint | The [startup collector](../broker/oh_no_parent_control/dependency_diagnostics.py#L467) recognizes only reviewed renderer/unit provenance, exact enforcing GPU-map denial, Vulkan mapping markers and correlated Mesa segfault, followed by app exit/shutdown. It exports source UTC time, closed reason and bounded numeric exit fields; raw messages, identities, paths and traces are discarded. This can support a renderer diagnosis, not prove every crash cause or a usable restored session. | `unit tests/unit/test_diagnostics.py::test_kiosk_pre_paint_crash_chain_survives_feedback_without_machine_access` proves a synthetic eight-marker archive/privacy round trip. `::test_kiosk_collection_preserves_failures_and_bounds_history` covers query/identity/budget/malformed/clipping limits. Source-reviewed collector coverage, not installed renderer fault acceptance. Broader renderer/recovery work remains separate; no demonstrated connection to this incident's earlier layout refusal. |
| Feedback collected after denied entry, recovery or reboot | [Export worker/delivery](../broker/oh_no_parent_control/service.py#L761) collects admission, startup and dependency observations before snapshot and rechecks the caller before releasing it. [Frontend collection/download](../common/oh_no_parent_control_ui/feedback.py#L347) prepares a fresh archive asynchronously; a visible prepared attachment alone does not prove the saved bytes. Failure offers retry/feedback without logs. Dedicated kiosk forbids the chooser; 010a/010 require Parent's real download. | `unit tests/unit/test_diagnostics.py::test_kiosk_admission_failure_survives_reboot_recovery_and_feedback_archive`, `tests/unit/test_service_contract.py::test_reboot_mode_collects_real_report_and_rechecks_role` and `tests/unit/test_service_contract.py::ServiceContractTests::test_export_collects_extension_evidence_before_snapshot_and_survives_failure` cover private composition/authorization and sanitization. Existing `check_e2e_kiosk_feedback_confinement` restores its post-ready broker outage **before** collection and proves editor/privacy/census only, without Send; it cannot establish collection during outage or an incident archive. In-scope clipping/archive repair remains 002; actual recovered/rebooted incident archive remains 010a/010, with selectors to be registered there. |

**Consumed roots, not a recursive audit.** The finite 001b root map applies to
these actual launch/import consumers. Native entrypoints and selected systemd
libraries are measured; the fixed launcher then reaches packaged kiosk/common
Python, system Python/GI typelibs, GTK libraries/assets and the named service
scripts. The private manager unit path and Ubuntu session D-Bus data are consumed
too. The XDG and WirePlumber roots recorded above can supply nested runtime data;
`/etc` remains outside the `/usr` overlay. Accepted sibling directory binds do
not recursively measure those nested scripts, modules or configuration. Neither
an immediate root-owned directory nor a broad policy read permission establishes
that all contents are immutable, safe or even consumed. This is the existing
005a material-identity design input; missing consumed dependencies must be
distinguished from unrelated siblings while preserving required-input refusal.
No nested-input exploit was demonstrated and no recursive package/plugin audit
or additional runtime campaign is allocated by this review.

**Evidence applicability.** Admission queries are independent of a surviving
manager and of loading kiosk configuration, across retained boots for 24 hours,
200 matching entries and 20 exported markers. Startup crash queries instead
require the configured kiosk UID and use `--boot=0`, 24 hours, 200 entries and
20 markers per source within one five-second budget. Reboot can therefore remove
the crash chain from a fresh query; it does not remove already-persisted validated
events automatically. Neither collector recovers rotated history. Additionally,
[public export authorization](../broker/oh_no_parent_control/core.py#L621) itself
loads configuration, and frontend broker log handlers have no journal fallback
or delivery replay. Collector independence is not proof of a downloadable archive
while configuration or the broker is unavailable. The plan's 010 histories restore
the incident input and working export route before collecting; they must use
fresh actual Parent bytes, not a stale prepared attachment or synthetic archive.

The retained installed receipts in 001a/001b remain historical, with the recorded
source/package/helper identities and cleanup, not passes for this checkout's
changed classification/diagnostic inputs. In particular, case 289's specific
`stale_admission()` generation reason cannot be replaced by case 267's earlier
attestation refusal. 011a must compare the actual final entry consumers and
producer/parser/catalogue/native inputs before reusing an affected receipt, or
allocate its affected complete history and target. A package hash difference
alone does not invalidate unrelated assertions. Planned incident histories at
003/004/007/009/010 still require their own canonical registration and all named
target acceptance; a similarly named existing selector earns no such credit.

The cumulative map is complete for the shipped authentication-to-form stages.
Demonstrated in-scope defects and direct safety controls have finite existing
owners; source-only post-boundary limits and missing negative proofs remain
explicit separate-owner observations. No new prerequisite is needed for 001,
and no later row is completed by this review.

001 review acceptance passed: the coordinator reviewed the complete collector/
export path and combined 001a/001b with an independent read-only startup,
readiness, runtime-root and selector review. The reviewer finished before
acceptance. The four-module documentation consistency selection passed 313/313
again after queue close-out in run `20261019T065201Z-bbb76ba6`. That report
subsequently rotated under normal retention during 002a handoff correction;
the fresh matching selection is retained below. This does not repeat the source
review or recover the original receipt.
Changed Markdown links and whitespace checks passed. No product, VM, fixture or
persistent process was created or changed; runner-owned cleanup finished and
there is no runtime restoration remaining. Only documentation changed, outside
`PACKAGE_SOURCE_FILES` and build-tool dependencies; this review brief has no
Targets and requires no package build or installed check.

### Classification prerequisite discovery — 002a

002a remains unfinished, with no acceptance credit. Coordinator and independent
read-only review confirmed that `directory_layout()` observes sources before
`prepare()` publishes pathname bindings and exits. The native
`bind_kiosk_executables()` has no required/ambient distinction: a later source
open, metadata or trust failure aborts entry. Another Python recheck cannot
close that interval. The existing native refusal/detach selector passed all
11 controls in run `20261019T065448Z-a85e1232`. That report rotated under normal
retention during 002aa; its recorded historical pass is not fresh native evidence.
Those expected refusals preserve safety; they do not prove ambient availability,
disappearance handling or the remaining classification/publication repairs.

The brief's explicit independent-mechanism condition therefore applies.
002aa/002ab precede 002a to design and implement only the preparation-to-bind
ambient lifetime boundary. Simply skipping an ambient file bind leaves an
empty file rather than omission; unlinking its target mutates the shared tree
checked by `verify_tree()`. Retrying full preparation can change the layout
digest and fail manager matching. The prerequisites must settle these cases
without bypassing required checks or moving the between-admission material/pin
work from 005a–007. All original 002a obligations remain required on resumption,
including fresh reproduction of the alias and publication defects before repair.

No product or test source was edited during discovery. The private-fixture run
finished, its runner-owned cleanup ended, and the read-only reviewer finished
before handoff. No VM, installation or persistent process was created. The
pre-existing proof-document edit is preserved. Only plan documentation changed;
no build or installed acceptance is supplied or required for this insertion.
The four-module documentation consistency selection and shared plan-launcher
regressions passed 551/551 in run `20261019T065643Z-b3e25743`. That discovery
report rotated under normal retention during 002aa. Its historical result is
preserved here; 002aa's fresh documentation selection below does not repeat the
shared launcher regressions.
This validates supporting contracts, not 002a's unexecuted acceptance. The
prerequisite block preserves all existing completion, order and scope, and adds
only its backward dependencies to 002a's existing Requires chain.

Handoff correction retained each prerequisite's single acceptance declaration
(`review` for 002aa, `host` for 002ab), renaming only the duplicate prose labels.
All required results and validation remain unchanged. The four-module
documentation consistency selection passed 313/313 in
run `20261019T065936Z-69697932` (subsequently retired by normal retention).
Markdown links and whitespace checks passed; runner-owned cleanup finished.
This correction executes neither prerequisite nor 002a acceptance.

### Post-layout ambient binding design — 002aa

Review acceptance passed on 2026-10-19 UTC. The enduring
[phase-local design](SystemDesign/Kiosk-Confinement.md#planned-post-layout-ambient-binding)
uses an invocation-private tmpfs skeleton and manifest, explicit producer-derived
required/ambient roles and required alias/root proofs. Native descriptor rechecks
separate eligible final-source omissions/masks from strict target, protocol,
mount, read-only and detach failures. The shared tree and full layout digest stay
unchanged; exact manager matching and 005a–007's retained-material work remain.
The owner allocates five finite, still-unimplemented selector families to 002ab,
including actual manager/gate publication-to-native consumption, independent
required drift, subsequent preparation/reuse and identity-owned cleanup.

The coordinator read the complete named Python/native functions, fixtures and
callers, with their unit-resource rationale. Independent GPT-6.1 Sol High review
accepted the final design after clarifying the producer-authoritative inventory,
native structural/proof checks and generation-marker comparison, plus SELinux
filesystem versus inode labels and their creation order. The reviewer finished
before acceptance with no resources owned. The maintained four-module
documentation consistency selection passed 313/313 in
run `20261019T070750Z-93b75ae5`.
The same 313/313 selection passed after queue/pointer/brief close-out in
run `20261019T070859Z-59031128`. Both reports subsequently retired under normal
retention; these identifiers preserve the accepted review history, not recovered
receipts. Changed Markdown links and whitespace checks passed.

Only documentation changed; no product, installation, VM or persistent process
was created. Runner-owned cleanup finished, and no runtime restoration remains.
The pre-existing proof/master/queue work is preserved. No package input or build
dependency changed, so no build is needed. This review brief declares no Targets
and earns no native or installed credit. Only 002aa closes; 002ab and every
later row keep their acceptance obligations.

### Post-layout ambient binding implementation — 002ab

Host acceptance passed on 2026-10-19 UTC. The
[phase-local mechanism](SystemDesign/Kiosk-Confinement.md#planned-post-layout-ambient-binding)
now uses an invocation-private bounded tmpfs, a versioned producer-derived
protocol, complete declared-root proofs and descriptor-based source decisions.
Unsafe ambient files are absent and directories remain empty; required, target,
protocol, mount, read-only and identity-owned detach failures refuse. Shared
generation bytes/tree/digest and exact manager matching remain unchanged.

Before repair, `test_post_layout_source_drift` reached the existing native source
checks: all 20 ambient variants failed availability and all 20 independent
required controls passed in `20261019T071142Z-bc17fb2a`. Its exported failure
report subsequently retired under normal retention during 003; this identifier
preserves the historical failure, not a recovered receipt. The five registered
`test_post_layout_*` families plus preserved identity and detach controls cover
341 cases, including both actual manager/gate publications, real descriptor-time
substitution, subsequent preparation/reuse, bounds, labels and owned child cleanup.

The exact final affected selection was `tools/run-tests unit` with
`tests/unit/test_kiosk_confinement.py`, `tests/unit/test_kiosk_login.py` and
`tests/unit/test_regression_unit.py`, retaining the fixtures' 5/30-second native
probe/compiler deadlines. Its historical report, `20261019T074024Z-1036c546`,
subsequently retired under normal retention and
records 1,218 passes and one private copy-fixture mode failure. After setting that
test's newly created parent directories to 0755, its exact selector
`test_preparation_swaps_independent_bubblewrap_copies_only_in_private_tree`
passed in `20261019T074140Z-e9b376b5` (also retired under normal retention).
Only that case's parent-mode setup changed after the full selection; product,
native/protocol fixtures and all other assertions are identical. Together these
receipts supply all 1,219 required passes, including the 341 finite controls,
66 PAM caller checks and 27 unit partition/resource checks.

After queue, pointer and brief close-out, the maintained plan, inventory,
coverage-generation and case-composition checks passed all 313 cases in
`20261019T074338Z-ad82f160` (subsequently retired under normal retention).
Changed-document links passed with 196 checked and none missing; the final
whitespace check passed.

Tested source and final fixture SHA-256 identities:

| Input | SHA-256 |
| --- | --- |
| `tools/kiosk_confinement.h` | `5fbc00f5983a929af882efe4d80ec4445e45af8547d4f395244b78eee27c85f9` |
| `tools/kiosk_confinement.py` | `243e4d92cb45686f820cc1cded9ce9476874c7c16cea070457d0e61c052aa6be` |
| `tools/kiosk_confinement_policy.py` | `eb93e6c4ce407c93a477933d6f23f52cbebe66cf07c4bc3179b565867a1b7cca` |
| `tests/unit/test_kiosk_confinement.py` | `cc31a2920804193f3ea9c494e5a4460fbb52b471c0bc0dc370497b7a40425389` |

`make build` passed for both formats after the final packaged edit. Product
package SHA-256: DEB `8a40d57a45a55b99f64502e42eabd408ccc44e6dd5216873a71ac4f38c24e479`;
RPM `8f928090eee5a3a3f3662e136bb366c31059197317cb29f5d437f6bf5057c590`.
The producer and native workers finished, including independent protocol/label
review, before acceptance; the coverage worker also finished before final checks.
Private mode-drift fixtures now restore directory access in `finally` after
their child exits. The recorded leftover fixture modes were restored and
`tools/cleanup-e2e --host-only` completed; subsequent runner startup and cleanup
passed. No installation, VM or persistent process remains. The pre-existing
proof-document work is preserved. This task declares no Targets and supplies no
installed credit. Only 002ab closes; 002a resumes with every original assertion,
and 003/004/007 plus 011a retain their installed obligations.

### Ambient classification and required-input controls — 002a

Host acceptance passed on 2026-10-19 UTC. Required layout closure now includes
lexical alias ancestors, intermediate target chains and reserved roots. Inventory
retains selected optional aliases; all measured native destinations, including
substituted executables, require unique intended private placeholders before
manager matching or generation writes. Directory aliases use concrete skeleton
nodes and explicit lexical proofs. Final publication refuses changed required
types/link text. Unsupported UTF-8 names, controls and link text are omitted only
for ambient entries; masked directories remain empty. No rejected source is bound,
no ambient contents are read and diagnostic failure leaves admission unchanged.

Before repair, all five permanent reproduction cases failed in
`20261019T074857Z-fc49bc5b`: three late alias ancestry/target ownership changes
did not refuse, and both caller roles raised `UnicodeEncodeError` during actual
publication. Its exported failure report subsequently retired under normal
retention during 003; the run identifier preserves the historical failures.
Subsequent fixture repairs made
the private generation marker explicitly 0644 and mapped current Python's direct
`Path.exists()` queries to the private tree; these preserve those original failures
and expectations. Existing executable-parent/copy-limit fixtures now supply their
real private required destinations, preserving their original refusal/bounds checks.

The final affected selection was `tools/run-tests unit` with
`tests/unit/test_kiosk_confinement.py`, `tests/unit/test_kiosk_login.py` and
`tests/unit/test_regression_unit.py`, retaining the native probes' 5-second and
compiler's 30-second deadlines. Its
historical report `20261019T075434Z-fd0e91fe` (retired under normal retention
during 002b) records all 1,302 passes: 1,209 confinement checks (including 83 new classification
cases and every original post-layout/required-input control), 66 PAM caller checks
and 27 resource/partition checks. Actual manager/gate publication reaches the
native consumer for healthy directory aliases. Independent ambient/required
metadata, owner/mode/type, disappearance/reappearance, readlink and final-proof
retarget controls pass. The full layout digest and exact manager match remain;
between-preparation ambient changes still belong to 005a–007.

Tested source SHA-256 is `c4df120b8e61802a7e0fac85fc628112ff47a460c826dd66a183dc461a4d0c50`
for `tools/kiosk_confinement.py`; the final fixture SHA-256 is
`c87027808b237eeeda4b83d46be8c63772710c3c8a0ea8fdd1f169a537da3f58`.
Native header and policy source match the 002ab identities above. `make build`
passed both formats after the final packaged edit: DEB SHA-256
`483ef5fa54455c6c35199ff9afa229b22b0f512a12edf846dd9aed4213f5c781`;
RPM SHA-256 `c96b869a1c27b6e6d0752b098f10a9d2a54597dd12ef7e7587c1e8bc6fa28e2f`.

Both GPT-6.1 Sol workers finished before acceptance, including independent High
source review. Resource rationale covers private trees, scoped metadata doubles,
bounded waited native children and unchanged cleanup/UI inventories. Runner-owned
cleanup and `tools/cleanup-e2e --host-only` completed; no process, VM, installation
or runtime restoration remains. The pre-existing proof-document edit is preserved.
This host brief declares no Targets and grants no installed or diagnostic-export
acceptance. Only 002a closes; 002b is next, and all other rows retain their scope,
dependencies, order and status.

After queue/pointer/brief close-out, the maintained four-module documentation
consistency selection passed all 313 cases in `20261019T075636Z-75f99911`
(subsequently retired under normal retention during 002).
Changed Markdown links and whitespace checks passed. Expired predecessor report
links above are recorded as historical run identifiers rather than fresh receipts.

### Native binding failure causes — 002b

Host acceptance passed on 2026-10-19 UTC. The native PAM caller now emits bounded
`onpc.pam kiosk native-view` causes for namespace/staging, manifest, metadata,
identity, binding/attachment, read-only and owned-detach refusals. The
[producer schema and sanitized examples](SystemDesign/Logging-and-Feedback.md#kiosk-admission-diagnostics)
give 002 its exact projection input. Invocation-local primary and cleanup causes
remain separate; direct errors use errno 1–4095 and unavailable/comparison errors
use -1. Legacy markers, required refusals, ambient omission/masking, labels,
limits and cleanup authority remain unchanged. Logging failure changes neither
the native result nor its mount/detach sequence.

Original source review found only `execution-boundary outcome=denied stage=bind`
at this boundary; no pre-fix fixture execution is claimed. The final maintained
selection, `tools/run-tests unit` with `tests/unit/test_kiosk_confinement.py`,
`tests/unit/test_kiosk_login.py` and `tests/unit/test_regression_unit.py`,
passed all 1,339 cases in `20261019T080357Z-d7eecb05`
(subsequently retired under normal retention during 002):
1,238 confinement, 74 PAM and 27 partition/resource checks. Its 37 added cases
cover all nine stages and seven reasons, independent inode/mount/namespace
witnesses, errno bounds, silent success, cleanup causes and both complete PAM
caller roles. Private compiler/probe deadlines remain 30/5 seconds. Source SHA-256
for `tools/kiosk_confinement.h` is
`85556d6fa59dab9edf65d647861e97afe4306ae6c1de8a11c1770b5fda87f72f`;
fixture hashes are `72dd22b2b45230951928fc6b8fe095ec62c26e3fb99bb54be6dd466336cb9fcb`
and `7879fb7b06ca7ff49bec35c3d089e68557407279f3f2a81c4137c4882401a744`
for the confinement and PAM modules respectively.

`make build` passed both formats after the final packaged edit: DEB SHA-256
`c6fe4fd9c7f990b1fa8c068309af2c01199d0371023bfcc21118ce195056518f`;
RPM SHA-256 `9608bd1c8914e8fa384f01406e77361d57ce7d0654225c9924d2775d3f8ba593`.
Both workers and the independent High reviewer completed before acceptance.
Resource review retains compatible private fixtures and adds no cleanup/UI
inventory or shared resource. Runner-owned cleanup and
`tools/cleanup-e2e --host-only` finished; no installation, VM, persistent process
or runtime restoration remains. The pre-existing proof-document edit is preserved.
This host brief declares no Targets and grants no installed or archive-projection
credit. Only 002b closes; every other queue row retains its status, order and scope.

After queue/pointer/brief close-out, the maintained four-module documentation
consistency selection passed all 313 cases in `20261019T080606Z-b923ca49`
(subsequently retired under normal retention during 003a).
Changed Markdown links and whitespace checks passed. The native report later
retired under normal retention during 002; its unchanged inputs passed the fresh
cumulative 002 selection below. The documentation result remains historical.
Report retirement preserves the accepted historical result.

### Customer diagnostic projection — 002

Host acceptance passed on 2026-10-19 UTC. Feedback now projects the exact
`onpc.pam kiosk native-view` schema through the existing admission event,
catalogue, storage and archive validators. Native executable, PAM session/service
and record role must agree. Primary denial and independent cleanup failure remain
separate; only closed stages/reasons and errno -1 or 1–4095 enter the report.
The legacy boundary marker remains unchanged. No admission code changed.

The 20-record history now retains the original denial and newest bounded phase
witnesses before distinct causes and repeats, under the unchanged 24-hour,
200-entry, byte and five-second query limits. The permanent 31-record/five-retry
archive regression retains authentication, routing, preparation/native causes and
later armed recovery with distinct source times and realistic manager/gate
provenance. An 89-record archive case retains all 16 phase witnesses, the original
denial and both routing recovery outcomes despite 72 generic denials. Eighteen
both-role native archive combinations cover every stage, independent cleanup and
legacy evidence; 48 rejected-input cases cover provenance, callback/role mismatch,
unknown records/fields and errno limits without exporting private text.
Existing failure/budget/clipping and reboot-history archive controls still pass.
The historical probe and source review established the original gaps; this
session claims no new pre-fix execution.

The historical affected host report `20261019T081141Z-f0874cf2`
(subsequently retired under normal retention during 003a)
passed all 2,117 unit cases and the selected Node command (six assertions).
Exact selection: `tools/run-tests unit` with
`tests/unit/test_kiosk_confinement.py`, `tests/unit/test_kiosk_login.py`,
`tests/unit/test_diagnostics.py`, `tests/unit/test_service_contract.py`,
`tests/unit/test_logs.py`, `tests/unit/test_diagnostic_privacy.py`,
`tests/unit/test_diagnostic_report.py`, `tests/unit/test_diagnostic_export.py`,
`tests/unit/test_regression_unit.py`, then `child-node`
`tests/child/diagnostic_events.test.mjs`. Native compiler/probe deadlines remain
30/5 seconds. Independent High review confirmed 002a/002b's complete required/
ambient and native producer boundaries; their source and fixture hashes match
the accepted identities above. Fresh complete confinement/PAM checks preserve
required refusals, both-role publication, omission/masking and logging-failure
behavior. No producer pass substitutes for the new collector/archive assertions.

Tested SHA-256: collector
`5a9058496cc12be1939895c36489ca413b5ec687ab01be8644955677763a892d`, catalogue
`6c189f93dd206b04107e3b879618d70bd845e667869179374cb49231659ee8e9`, diagnostic
fixtures `4ae139d93fa3e6cac139b0a2df2e26e84aba397ffc244358a4168aa6cc7ddd9e`.
`make build` passed both formats after the final packaged edit: DEB SHA-256
`730c1e671d463459c17cff746ab47e1c708b2eb076bcb62e95b88ea94b16051b`;
RPM SHA-256 `0d605cb1faacdbd8b5237fd622a4cfb538eaa81eb4c10eccabd33ba94256265f`.
The additive catalogue ships with all validators; broker activation is
process restart and frontend readers load on their next launch.

Both workers completed before acceptance. Resource review retains compatible
private journal doubles and `tmp_path` archives with no new cleanup/UI resource.
Runner-owned cleanup and `tools/cleanup-e2e --host-only` finished; no installation,
VM, persistent process or runtime restoration remains. The pre-existing proof
document edit is preserved. This host brief declares no Targets and grants no
installed credit; 003/004/010 retain their installed obligations. Only 002 closes,
and every other queue row keeps its status, order, scope and dependencies.

After queue/pointer/brief close-out, the maintained
[four-module documentation selection](TestAutomation/E2E-Execution-Contracts.md#completion-and-document-cleanup)
passed all 313 cases in `20261019T081327Z-ef31eea8`
(subsequently retired under normal retention during 003a).
The accepted 002 results remain historical. Older
retired receipts above keep their historical run identifiers. Changed-document
links and the final whitespace check passed.

### Ubuntu sibling isolation — 003a

Installed acceptance passed on `onpc-Ubuntu26.04` on 2026-10-19 UTC using
registered enforcement case **290**, `test_kiosk_writable_sibling_isolation`.
The canonical mechanics are in `system_kiosk_confinement.py`; the runner's
`sibling-isolation` phase reuses the existing guarded public station helper.
The public form loaded without a kiosk password and Cancel returned to sign-in.
All 24 observed kiosk processes had empty private views of root-owned 0775/0777
and non-root-owned 0755/0555 inert directories, and no view of the user-owned
0644 file. These independent live-root observations passed initially, after
replacing the exact owned 0777 directory and omitted file, and after restoring
their original inodes/bytes. Both ordinary roles retained contents/access at
each stage. The same manager, mount namespace and generation survived replacement.
The full thread census remained enforcing, a native positive executed, and the
shell negative produced its matching enforcing AppArmor denial. Kernel:
`7.0.0-38-generic`.

The original evidence bundle contained the complete installed result, phase
JUnit, public-entry/exit/fixture cleanup receipt, frozen input manifest and
supporting host reports. Its original SHA-256 was
`ae6e378b33965dbd218a39df280e909928ed2550fac5afffb2f0f4bbf5b534eb`.
Normal retention retired that export during 004a; all constituent receipts remain
in [004a's verified cumulative bundle](#ubuntu-late-refusal-and-recovery--004a).
Original allocation: `onpc-system-s_b4d2cd`; aggregate report:
`20261019T082133Z-f7ba2a4a` (1/1 passed, 4.8 minutes including package-snapshot
refresh). Product, infrastructure, collection and cleanup all passed.
DEB SHA-256:
`031aed4a7d515acca60915a3e67b8165bc38513b8dcadafcccd9bbf9c584f26f`;
package-source digest:
`5135f062b60aff9d002c9a02d0f02feb1a51a281acf99da6fe53cbbaf01a0679`;
fixture digest:
`c12399c7d679ee5f1bbed9de8ee0d51cacbcf88f07dd2e506c465a483ff533cd`;
selected-input digest:
`4a5b25e7052ecade466d1595715181fa6f1ce2ce65592e8c80eaefa2a95cf4b1`.
Current guest mechanics and collected case match the frozen hashes; the public
observer/runner/snapshot/registry host closure also matches its retained receipt.
Later input changes require the normal applicability review before reuse.

The affected confinement, runner and partition selection passed 2,254 checks in
`20261019T082001Z-a16e6ad7`; snapshot/cleanup safety and the final selection
guard passed 313 checks in `20261019T082054Z-dcff4735`. Both reports are included
in the bundle. Existing compatible resource classifications remain appropriate:
host tests use private files and process-local doubles, with closed descriptors,
bounded waited native probes and no new host session, mount, bus or display.
No package source or package-build dependency changed, so no separate `make build` is required.
The maintained artifact preparer built and verified the actual DEB used above.

Fixture restoration/removal, public exit, runner baseline restoration and
standalone `tools/cleanup-e2e --vm onpc-Ubuntu26.04` completed. Its first invocation
was busy while the owned evidence export ran; the serial retry passed after that
export finished. No product assertion failed. No subagent started successfully;
none remains. The pre-existing proof-document edit is preserved. Only 003a
closes; Fedora 003 and Reliability 006a retain their original acceptance scope.

After queue/pointer/brief close-out, the maintained four documentation modules
and unit partition/resource checks passed all 340 cases in
`20261019T082827Z-a4e09239` (subsequently retired under normal retention during 003).
Changed-document links and whitespace passed.
Expired older links above retain their historical run identifiers; no earlier
task is reopened or granted fresh acceptance. The 003a bundle remains retained.

### Fedora sibling isolation and candidate reconciliation — 003

Installed acceptance passed on `onpc-Fedora44` on 2026-10-19 UTC, with a fresh
`onpc-Ubuntu26.04` rerun after the shared native fix. Both used registered case
**290**, `enforcement / test_kiosk_writable_sibling_isolation`, in one maintained
two-target selection. Fedora report `20261019T085656Z-ac264187` took 2.5 minutes;
Ubuntu report `20261019T085656Z-ce7a9f55` took 1.5 minutes. All product,
infrastructure, collection and cleanup outcomes passed on both targets.

The original Fedora attempt `20261019T083355Z-ced15908` reached successful blank
authentication and routing, then refused at native namespace setup with errno 13;
no product assertion ran. Owned maintenance reproduced entry failure. The audit
identified `xdm_t` denied `read` on the namespace's `nsfs_t` file while SELinux
remained enforcing. The three identity-only namespace opens now use `O_PATH`
with `O_CLOEXEC`, retaining descriptor, namespace-change and exact cleanup checks.
No MAC permission changed. The independent native fixture now refuses read opens:
the original code failed 13 of 22 focused controls in `20261019T084557Z-af392122`.
The final confinement/PAM/partition selection passed all 1,355 checks in
`20261019T084637Z-732eb4b9`, including namespace-mismatch and foreign-mount refusals.
GPT-6.1 Sol High independent review found no correctness or security issue and
finished before acceptance. Private fixture ownership/resource classifications
remain unchanged. `make build` passed both formats after the final packaged edit.

On each target, all 24 observed station processes had empty private views of
root-owned 0775/0777 and non-root-owned 0755/0555 directories, with the user-owned
0644 file absent. Both ordinary roles retained exact contents/access initially,
after replacing the recorded 0777 directory and omitted file, and after restoring
their original inodes/bytes. The same manager, namespace and generation survived
replacement. The full thread census stayed confined; the allowed native control
executed and the shell negative had its exact enforcing kernel denial. Public
passwordless entry reached the loaded form and Cancel returned to sign-in.
Fedora kernel: `7.2.11-200.fc44.x86_64`, enforcing SELinux (`permissive=0`);
Ubuntu kernel: `7.0.0-38-generic`, enforcing AppArmor.

Both final receipts bind package-source digest
`f29dbb154edcdb8d1523a49725878e1df956724d03cd41872ca39cfdb58853dd`,
fixture digest `facbd895b378897dba77b7be5832e4db7b2b12595815c4fb78cabf6c7b70996d`
and selected-input digest
`4a5b25e7052ecade466d1595715181fa6f1ce2ce65592e8c80eaefa2a95cf4b1`.
The selected guest and public observer/runner/snapshot/registry closure matches
003a exactly; the native header changed, so its older installed package receipt
was superseded for this candidate by the complete Ubuntu rerun, not reused.
Final installed DEB SHA-256:
`1da3b504aa104b55c845c3ab6b75c3e5687541468ae921f05d12ed3c0feba029`;
RPM SHA-256:
`6751dc9abe401bf82627f2dc208d2766fea89bef781df273aeadc463cc024fb0`.
Native header SHA-256:
`5bd1c93ac8144b7cda9248d84e176845d99c0cfb01016cbb54f8c84cdb5b0cb6`;
host fixture SHA-256:
`ffdc394a5c34ecef12d73d9dbd768f6ccc32db8b02f0f9e6305f8d8e2f6d646e`.

The original verified cumulative bundle, `onpc-evidence-bundle-oyxcp4qk/evidence.zip`,
contained both final results, complete phase JUnit, public entry/exit and fixture
cleanup receipts, frozen input/package manifests, the original Fedora failure,
host negative/final reports and 003a's historical evidence. Bundle SHA-256:
`e2720ed1c6dfc2b73b87b777644f9c4bd8714037309228da1ed64c400d8a7220`.
That export retired under normal retention during 004; all constituent receipts
remain in [004's verified cumulative bundle](#fedora-late-refusal-and-candidate-reconciliation--004).
Final allocations are `onpc-system-oj79lbh3` (Fedora) and
`onpc-system-8knwkc34` (Ubuntu). Fixture removal, diagnostic/preparation session
release, runner baseline restoration and serial
`tools/cleanup-e2e --vm onpc-Ubuntu26.04,onpc-Fedora44` completed. Export cleanup
also completed. The initial busy export and checkout-owner refusals passed on
serial retry after their owners finished. No owned process or VM remains active.
The pre-existing proof-document edit is preserved. Only 003 closes; these matching
receipts are available to Reliability 006a's later scope review without checking
that separate row or granting any other installed obligation acceptance.

After queue/pointer/brief close-out, the maintained four-module documentation
selection passed all 313 cases in `20261019T090218Z-d43a50d8`
(subsequently retired under normal retention during 004a).
Changed-document links and whitespace passed. Both named VMs were independently
observed powered off after cleanup; the cumulative bundle remained verified.

### Ubuntu late refusal and recovery — 004a

Installed acceptance passed on `onpc-Ubuntu26.04` on 2026-10-19 UTC using
registered enforcement case **291**, `test_kiosk_required_ancestor_refusal`,
in the canonical `required-ancestor` phase. The confinement helper records the
required `/usr/lib/systemd` ancestor and executable, then adds only group write
permission (0755 → 0775, owner/group root). The original native PAM session
refused with status 14 at `executable-inventory / untrusted-path`; its executor
returned 125 without running the command. A separate real GDM selection added
new manager preparation/native `prepare` denials, left no station session and
returned to the public account list. No kiosk password was entered or prompt
wording treated as failed authentication.

The exact original inode, owner/group, executable bytes and mode were restored.
Fresh public passwordless entry in the same boot reached the loaded request
form with usable selection/Cancel and its expected limits-disabled explanation.
The complete thread census stayed enforcing under AppArmor, an allowed native
service executed, and the shell negative had its attributed enforcing kernel
denial. Both ordinary roles retained account metadata, executable contents and
execution access; their actual installed PAM authentication and account checks
succeeded before the fault, during refusal and after recovery without changing
their credentials. Public Cancel returned to sign-in. Kernel: `7.0.0-38-generic`.

The first installed attempt, `20261019T091150Z-2639ae1e`, preserved the correct
native/GDM refusal and restoration but stopped in the new public fallback reader.
Owned live diagnosis identified GDM's transient two-label station state before
its account list returned. The shared reader now waits within its original
deadline; absent or duplicate station identity never authorizes input, wrong
account/ambiguous fields still refuse, and persistent ambiguity times out.
The fixed diagnostic run observed the account list on all three reads. A new
fixed maintenance entry reuses the same one-shot selection and shared recovery
storage; its initially missing dispatcher registration was repaired through
the authorized setup route. One new host fixture needed an explicit two-second
budget for three simulated reads; product deadlines and assertions were unchanged.

The final combined report `20261019T092504Z-504622aa` passed all **3,384** affected
host checks and the complete **1/1** Ubuntu installed history (1.9 minutes VM,
2.7 minutes combined). The complete native/PAM selection retains existing
required-source/protocol/mount/read-only/detach refusal controls; the audit found
no distinct uncovered binding branch requiring another installed fault here.
The prior input-directory retirement stopped `20261019T092326Z-031ee095` before
VM work; maintained artifact preparation rebuilt verified inputs automatically.
All final product, infrastructure, collection and cleanup outcomes passed.

The [verified cumulative bundle](../output/test-runs/host/exports/onpc-evidence-bundle-obgg9ean/evidence.zip)
retains the original failure, final result/JUnit/public refusal/recovery and
cleanup receipts, exact frozen input/package manifests, complete host report,
diagnostic samples and predecessor installed receipts. Bundle SHA-256:
`24529f4d2267b8c42de9cb03358e9b5fa86d97f813d9d6753e4529c4cc3b7f87`.
Final allocation: `onpc-system-kqo_t8br`. Installed DEB SHA-256:
`1bcd2efeffec52fd1bac27e14db23991737a74780baeb74665f7d3e1391c4080`;
package-source digest:
`f29dbb154edcdb8d1523a49725878e1df956724d03cd41872ca39cfdb58853dd`;
fixture digest:
`facbd895b378897dba77b7be5832e4db7b2b12595815c4fb78cabf6c7b70996d`;
selected-input digest:
`63cede933c96bf4ddbb424cfaa810a390ed21d8243883412abacdeaa78d8d3d8`.
The changed guest helpers and public observer/runner/snapshot/registry hashes
match the frozen manifest; the receipt confirms the complete host closure stayed
unchanged. Product inputs match 003's source digest; no packaged source or build
dependency changed, so no separate `make build` is required. The maintained
preparer built and verified the actual DEB used here. No predecessor receipt is
reused as this task's acceptance.

Parallelism review retains the existing compatible classifications: private
pytest files, closed descriptors, process-local UI/VM doubles and bounded waited
native children, with no new host display/bus/session owner. Diagnostic and
attempt allocations use shared retention. Exact fault restoration, normal public
exit, inactive-manager verification, maintenance release, runner baseline
restoration and `tools/cleanup-e2e --vm onpc-Ubuntu26.04` completed. The VM was
independently observed powered off and export cleanup completed. No subagent
started successfully; none remains. The pre-existing proof-document edit is
preserved. Setup regenerated its exact executable inventory alongside the
dispatcher refresh. Only 004a closes; these receipts are available to 004 and
Reliability 006b for exact-scope review without closing either consumer.

After queue/pointer/brief close-out, the maintained four documentation modules
passed all 313 cases in `20261019T093023Z-8f0880c7`
(subsequently retired under normal retention during 004).
Changed-document links and whitespace passed. Historical export/report references
retired during this task retain their original identities above; the complete
installed receipts remain in the verified cumulative bundle.

### Fedora late refusal and candidate reconciliation — 004

Installed acceptance passed on `onpc-Fedora44` on 2026-10-19 UTC using
canonical enforcement case **291**, `test_kiosk_required_ancestor_refusal`,
phase `required-ancestor`. The same final selection freshly passed on
`onpc-Ubuntu26.04`. Fedora report `20261019T094152Z-8236f31a` took 3.5 minutes
including input preparation; Ubuntu report `20261019T094152Z-dee12fa6` took
3.1 minutes. Product, infrastructure, collection and cleanup passed on both.

Each uninterrupted history recorded the required `/usr/lib/systemd` ancestor
and executable identity, added only group write permission (0755 → 0775,
owner/group root), then independently required the original native refusal:
PAM status 14, executor status 125 and `executable-inventory / untrusted-path`.
A separate actual GDM selection produced new preparation/native denials,
left no station session and returned to the account list. Fedora retained both
manager and gate preparation causes. No kiosk password was entered, and prompt
wording was not classified as authentication failure.

Exact inode, owner/group, executable bytes and mode restoration preceded fresh
passwordless entry in the same boot. The loaded confined form had usable child
selection and Cancel with the expected limits-disabled explanation. Full thread
census, allowed native execution and the attributed enforcing shell denial passed.
Fedora used kernel `7.2.11-200.fc44.x86_64`, enforcing SELinux (`permissive=0`);
Ubuntu used `7.0.0-38-generic`, enforcing AppArmor. Both ordinary roles retained
metadata, contents and execution access; real installed PAM authentication/account
checks succeeded before the fault, during refusal and after restoration. Public
Cancel returned to sign-in.

The first Fedora attempt, `20261019T093422Z-61651a06`, stopped at the engineering
probe's original-cause capture, before product assertions. Exact restoration and
runner cleanup passed. Live maintenance diagnosis found that the vendor PAM
caller could not write the harness's `user_tmp_t` capture files. A controlled
inherited-pipe experiment independently recovered the 146-byte original refusal
under enforcing SELinux, with PAM 14/executor 125 and exact restoration. The
shared probe now carries bounded diagnostics through a separate inherited
nonblocking pipe, retaining result/stdout separation, deadlines, descriptor cleanup
and every refusal assertion. No product permission changed. The complete affected
confinement/PAM/partition selection passed **1,362/1,362** checks in
`20261019T094054Z-7949f1d1`, including both vendor callers, error paths, pipe
saturation and descriptor cleanup. Existing required-source/protocol/mount/
read-only/detach controls remain; review found no distinct uncovered binding stage
requiring a second installed fault. This installed history proves preparation
refusal, not an injected bind-stage failure.

The initial read-only review matched all 54 guest/host source paths against
004a's receipt. The diagnostic repair then changed one guest input, so both final
target histories above supersede that older receipt for this candidate. Final
selected-input digest:
`fbc2e8175880c850a0f36ac8b55e61fdfc5f7685762205735bec7d2326e103c5`;
all 54 distinct current source paths match, with no mismatch, and both receipts
confirm the host closure stayed unchanged. Package-source digest remains
`f29dbb154edcdb8d1523a49725878e1df956724d03cd41872ca39cfdb58853dd`;
fixture digest remains
`facbd895b378897dba77b7be5832e4db7b2b12595815c4fb78cabf6c7b70996d`.
Installed RPM SHA-256:
`6751dc9abe401bf82627f2dc208d2766fea89bef781df273aeadc463cc024fb0`;
DEB SHA-256:
`1bcd2efeffec52fd1bac27e14db23991737a74780baeb74665f7d3e1391c4080`.
Only test helpers, their regression and documentation changed; no packaged source
or build dependency changed, so no separate `make build` is required.

The [verified cumulative bundle](../output/test-runs/host/exports/onpc-evidence-bundle-a161sv3w/evidence.zip)
retains both final results, complete phase JUnit, public refusal/recovery and
cleanup receipts, frozen input/package manifests, the original failure/error log,
affected host report and predecessor receipts. Bundle SHA-256:
`51268136679d7bdcc3653e0fdca307b2f7e7f1364a15232477363d34479f8575`.
Final allocations: `onpc-system-yg6gu6qf` (Fedora) and
`onpc-system-dks99oc9` (Ubuntu). The diagnostic helper SHA-256 is
`2db892875ff62f3a050cd8c8309e23fd7773a7acf131673e9d6045d4db0eece0`;
regression SHA-256 is
`ced4ff31579ea58f98b8e36c064c8719f3cc0a14263f9e8ea08d76417e2439e6`.

The scoped reviewer/worker finished before acceptance and cleanup. Resource review
retains private files/mocks and fixture-owned descriptor capture; there is no new
host display, bus, session or process owner. Diagnostic mutation restoration,
maintenance release, public exit, fixture cleanup, runner baseline restoration,
serial `tools/cleanup-e2e --vm onpc-Ubuntu26.04,onpc-Fedora44` and export cleanup
completed. Both VMs were independently observed powered off. The pre-existing
proof-document edit is preserved. Only 004 closes; matching receipts are available
to Reliability 006b without completing that row.

After queue/pointer/brief close-out, the maintained four documentation modules
passed all 313 cases in
[20261019T094725Z-f86c5193](../output/test-runs/host/reports/20261019T094725Z-f86c5193/report.md).
Changed-document links and whitespace passed. Retired historical export/report
links retain their original identities and point to the cumulative retained proof.

### Material identity and immutable-pin design — 005a

Review acceptance passed on 2026-10-19 UTC. The enduring
[material/pin design](SystemDesign/Kiosk-Confinement.md#planned-retained-material-and-immutable-pins)
and [activation/recovery boundary](SystemDesign/Lifecycle.md#retained-material-activation-and-recovery)
define required material `M`, original realization `V` and derived invocation
receipt `I`. The finite transition table preserves required-input refusal and
same-byte reinstall while ambient add/remove/mode/owner/kind changes select no
new host source. The finite runtime additions follow actual fixed launch/import,
extension-local schema and generated unit/data consumers; broad distribution
runtime trees retain their documented shallow compatibility limits.

Retained source storage is the verified manager's actual `/usr` mount tree,
held by a native-owned recursive detached clone descriptor after staging detach.
Fresh invocation parents avoid mutating shared dentries. Source allowlists,
inode/material provenance, renewed complete helper assertions, atomic publication,
ready-state interruption, foreign/replaced state, bounds and identity-owned
recovery are explicit. Independent positive/negative witness families allocate
primitives to 006a and selection to 006b; 005 still owns manager/concurrency/native
composition, and 006/007 retain integration and real installed acceptance.

The coordinator reviewed complete preparation, generation verification/publication,
native binding/staging cleanup and canonical `verify_updates()` /
`system_native_update.stale_admission()` histories. The historical ambient-addition
failure in `20261019T061016Z-d39f14ad` remains a required permanent before/after
control at 006b and installed 007, not a current pin-design pass. Its retired
export and earlier attestation-stage denials supply no new acceptance.

Independent GPT-6.1 Sol High review accepted the final design after separating
source versus invocation receipts and clarifying fresh eight-field assertions
for an unlinked retained vendor inode. The reviewer completed before acceptance
and owned no resources. No product source, installation, VM, fixture or persistent
process changed; no runtime restoration remains. The pre-existing proof-document
edit is preserved. Only documentation outside package/build inputs changed, so
no build is required. This review brief declares no Targets and supplies no host
or installed acceptance for the planned mechanism. Only 005a closes.

After queue/pointer/brief close-out, the maintained four-module documentation
consistency selection passed all **313/313** cases in
[20261019T095550Z-158c6599](../output/test-runs/host/reports/20261019T095550Z-158c6599/report.md).
Runner-owned cleanup finished. Changed-document links and whitespace passed;
all other queue rows retain their original status, order, Scope and Requires.

### Retained-view admission proof review — 005

Review acceptance passed on 2026-10-19 UTC. The enduring
[admission proof](SystemDesign/Kiosk-Confinement.md#planned-retained-view-admission-proof)
and [lifecycle composition](SystemDesign/Lifecycle.md#retained-material-activation-and-recovery)
bind the system-manager unit invocation, leader pidfd, complete task/credential/
label/namespace proof, recursive source clone and native receipts through final
validation. Compatible reexec preserves that proof; observed exit or replacement
refuses. Pin lifetime does not promise manager liveness after the admission
decision. Original source `V` and derived gate `I` keep separate ownership,
coverage, publication and cleanup. The finite ambient/required table remains;
006a/006b/006 retain independent primitive, selection and composition witnesses,
and 007a/007 retain actual installed acceptance on their declared targets.

The coordinator reviewed complete `prepare()`, `manager_generation()`, generation
verification/publication, native protocol/proof/binding/staging cleanup and final
MAC callers, plus canonical `manager_boundary()` / `verify_updates()` and
`system_native_update.stale_admission()` with its update/reboot callers. Product
source identities remain `c4df120b8e61802a7e0fac85fc628112ff47a460c826dd66a183dc461a4d0c50`
(preparation) and `5bd1c93ac8144b7cda9248d84e176845d99c0cfb01016cbb54f8c84cdb5b0cb6`
(native header). No existing installed receipt is claimed as proof of the new
mechanism. The earlier attestation refusal remains distinct from an actual
material mismatch; historical ambient-addition failure still needs its permanent
006b before/after control and real 007a/007 history.

Independent GPT-6.1 Sol High review found and then accepted correction of one
lookup-root gap: an original `/` descriptor still crosses a later `/usr`
overmount. The proof now pins original `/usr` separately, explicitly dispatches
aliases and requires an independent post-attachment host-drift refusal while
private bytes stay unchanged. No source-store redesign or prerequisite is needed.
Native proc/clone/bus access, mounted-source completeness, task churn and
publication interruption remain explicit implementation/qualification risks.
Unfinished consumer briefs link to the enduring proof without scope changes.

The first reviewer could not start; the subsequent reviewer completed and owned
no runtime resources. No product source, installation, VM, fixture or persistent
process changed. The pre-existing proof-document edit is preserved; no runtime
restoration remains. Only documentation outside package/build inputs changed,
so no build is required. This review brief declares no Targets and grants no
host or installed pass for the planned mechanism. Only 005 closes.

After queue/pointer/brief close-out, the maintained four-module documentation
consistency selection passed **313/313** cases in
[20261019T100407Z-50c667fb](../output/test-runs/host/reports/20261019T100407Z-50c667fb/report.md).
Runner-owned cleanup finished. Links for all nine changed Markdown documents
and whitespace checks passed; every other queue row retains its original
status, order, Scope and Requires.

### Remaining execution and acceptance

The three discovery reviews now map authentication/account admission,
preparation/native confinement and session/readiness/feedback coverage. Their
cumulative map retains the finite missing regression controls for implementation
and the exact limits of unaffected existing coverage. Existing
unaffected coverage need not be requalified. The independent review confirmed
the incident's blank authentication followed by preparation refusal; it did not qualify a new native
candidate. The selected existing host checks passed 1,223 cases on 2026-10-19 UTC.
The deliberate alias-ancestor and non-UTF-8 publication failures are historical
engineering evidence; their permanent regressions and repairs passed at 002a
above. Temporary review probes were removed.

A further independent review reproduced five host failures in
`20261019T061016Z-d39f14ad` (its export subsequently retired under normal retention):
non-root lexical directory/link ancestry and an intermediate target link were
masked/omitted instead of refused; a non-UTF-8 sibling failed actual binding
publication; and an unrelated masked-directory addition changed the digest and
rejected an otherwise unchanged retained-manager model. The temporary probes
were removed and their containing file restored exactly. These are bounded
engineering reproductions, not maintained regression coverage or installed proof.
The first review report rotated during subsequent checks. The same five failures
were reproduced in run `20261019T061016Z-d39f14ad` and exported before close-out;
the original export included their probe source and failures.
002a owns the first four failures; 005a/005 and 006a/006b/006 own retained-view
repair, with installed acceptance at 003/004/007. Required-path completeness and
metadata-race controls remain mandatory within those owners.

A follow-up review recorded five additional host probe failures
in run `20261019T061847Z-d1c50a84` (its export retired under normal retention
during 003a): non-UTF-8 publication failed for both roles,
ambient addition still changed the retained-manager digest, an absent required
native destination escaped the preserved-only layout completeness check, and
20 repeated denial records displaced all authentication/routing/recovery context
from a 31-record diagnostic input. The last two are newly demonstrated gaps;
002a and 002 respectively own their permanent regressions and correction.
002a's source-reviewed post-layout ambient disappearance/trust-drift boundary
was resolved by the 002aa/002ab prerequisites and revalidated in 002a's affected
selection, preserving strict required-input controls. These are engineering observations,
not installed acceptance. Temporary probes were removed and both containing
test files restored to their exact pre-probe hashes.

The same review found stale proof allocation: the current account-classification
selector is system case 5, and the config-mutation check in
`verify_execution_boundary()` reaches payload attestation before generation
comparison. The enduring references are corrected; 001b/001 and 011a/011 still
must allocate actual generation-stage, final-candidate receipts, using
`system_native_update.stale_admission()` only where its inputs and evidence match.
011a also owns the finite documentation repair for eight unavailable local
recording links in `Kiosk-Confinement-Proof.md` (lines 33, 39 and 40 at review).
Classify them against the existing accepted retention-loss record; this is no
new removal/lifecycle acceptance gate and does not reopen accepted history alone.

Task sizing separates classification, native diagnostics, report projection,
retained-view primitives, admission integration and final evidence allocation.
Installed rows are split by target; each target retains its whole failure,
restoration, recovery and cleanup history. Original numeric IDs identify the
remaining composition, whose delivered scope includes its extracted prerequisites.
Both targets and all in-scope entry/safety assertions remain required. Later
fixes require review of affected earlier receipts and reruns where their relevant
installed inputs changed, under the owning evidence contract. Record the final
package identity and exact input comparison supporting reuse; a different package
hash alone does not mandate unrelated acceptance histories.
Installed fault/recovery histories have explicit session exceptions;
their estimates are not timers. Independent newly discovered work whose upper
estimate exceeds 30 minutes requires a bounded prerequisite before execution,
not silent expansion of the current row. No task may absorb a release-wide
validation campaign. Existing retained launcher runs, if any, still require the
shared explicit reconciliation route; editing this plan does not alter them.

Run `tools/kiosk-prompt --check` to validate this plan without execution.
`tools/kiosk-prompt --tasks 1` executes the next task; `--tasks 0` executes the
remaining queue. Repeating the command reconnects; `--stop` stops between agent
sessions. The wrapper uses GPT-6.1 Sol High and the existing driver, ownership,
task budgets, Git close-out and VM selection. It adds no separate runner or
approval mechanism. New executable command grants use the existing setup-owned
tool discovery; do not broaden rules to start it.

All rows start unfinished. Current source changes and host passes are candidate
work, not installed acceptance or completed queue tasks. At execution, preserve
pre-existing edits and reconcile their ownership through the shared launcher;
do not overwrite a protected dirty baseline or claim it as a task commit.
The development host's installed product and live sessions are not execution
targets for this plan. Each installed brief declares its target; the queue
covers both registered platforms under the [VM mandate](Mandates/VM-Mandate.MD).
Public observations follow the
[UI mandate](Mandates/UI-Automation-Mandate.MD); fault injection remains engineering
coverage. Store results and perform identity-owned restoration through existing
helpers under the [storage mandate](Mandates/Test-Storage-Mandate.md).

For every installed task, retain the original failure and expected/actual result,
exact candidate/package and fixture identities, enforcing security mode, positive
ordinary-account controls, restoration and owned cleanup. Do not enter a password
into an unexpected kiosk-account prompt. Run only affected existing histories;
host passes, manifest inspection, preparation and a successful retry cannot
replace native isolation or public recovery proof. Build after the final
packaged edit. The final row reconciles evidence against the actual final inputs.

## Coordination with existing plans

This queue owns the new kiosk-prompt work. Reuse canonical confinement,
admission, PAM, account and native-update implementations, rather than create
parallel test mechanics. [Reliability 006a](Reliability-Tasks/006a-sibling-masking.md),
[006b](Reliability-Tasks/006b-required-path-refusal.md) and
[010](Reliability-Tasks/010-diagnostic-recovery.md) retain their independent scope
and unfinished status. Their executors must first inspect this queue's matching
receipts and implement only a remaining gap. Each launcher closes only its own
reviewed row; shared evidence must match its full scope, targets, candidate and
cleanup. Do not run overlapping implementations concurrently or edit another
workflow's retained checkpoint.
