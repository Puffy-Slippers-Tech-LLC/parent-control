# Kiosk entry and unexpected password prompt

Task queue: [Ordered task queue](Kiosk-Prompt-Queue.md).
Next task: **001 — [Reconcile the entry failure map](Kiosk-Prompt-Tasks/001-entry-audit.md)**.

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
four-module documentation consistency selection passed 313/313 in
[the retained runner report](../output/test-runs/host/reports/20261019T063757Z-1fe129b7/report.md).
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

**Evidence applicability and remaining proof.** The retained
[five-failure review](../output/test-runs/host/exports/onpc-artifact-export-tmc1qzhs/report.md)
contains `alias-directory`, `alias-link` and `target-link` controls that expected
refusal but did not raise, a publication `UnicodeEncodeError`, and the ambient
generation mismatch. The
[follow-up report](../output/test-runs/host/exports/onpc-artifact-export-3obq7d2l/report.md)
retains missing required destination, manager/gate encoding and ambient digest
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
required four-module documentation consistency selection passed 313/313 in
[the retained runner report](../output/test-runs/host/reports/20261019T064419Z-1aad8930/report.md).

### Remaining execution and acceptance

Discovery is the first three bounded tasks: authentication/account admission,
preparation/native confinement, then session/readiness/feedback coverage
reconciliation. Their union must map the shipped entry failure stages and the
finite missing regression controls before implementation closes. Existing
unaffected coverage need not be requalified. The independent review confirmed
the incident's blank authentication followed by preparation refusal; it did not qualify a new native
candidate. The selected existing host checks passed 1,223 cases on 2026-10-19 UTC.
The deliberate alias-ancestor and non-UTF-8 publication failures remain unresolved
engineering evidence in existing runner reports; temporary review probes were
removed.

A further independent review reproduced five host failures in
[the exported probe report](../output/test-runs/host/exports/onpc-artifact-export-tmc1qzhs/report.md):
non-root lexical directory/link ancestry and an intermediate target link were
masked/omitted instead of refused; a non-UTF-8 sibling failed actual binding
publication; and an unrelated masked-directory addition changed the digest and
rejected an otherwise unchanged retained-manager model. The temporary probes
were removed and their containing file restored exactly. These are bounded
engineering reproductions, not maintained regression coverage or installed proof.
The first review report rotated during subsequent checks. The same five failures
were reproduced in run `20261019T061016Z-d39f14ad` and exported before close-out;
the linked report includes their probe source and failures.
002a owns the first four failures; 005a/005 and 006a/006b/006 own retained-view
repair, with installed acceptance at 003/004/007. Required-path completeness and
metadata-race controls remain mandatory within those owners.

A follow-up review retained
[five additional host probe failures](../output/test-runs/host/exports/onpc-artifact-export-3obq7d2l/report.md)
in run `20261019T061847Z-d1c50a84`: non-UTF-8 publication failed for both roles,
ambient addition still changed the retained-manager digest, an absent required
native destination escaped the preserved-only layout completeness check, and
20 repeated denial records displaced all authentication/routing/recovery context
from a 31-record diagnostic input. The last two are newly demonstrated gaps;
002a and 002 respectively own their permanent regressions and correction.
002a also owns the source-reviewed post-layout ambient disappearance/trust-drift
boundary: native bind checks remain strict, but currently make that unrelated
source an entry prerequisite. Its brief requires a bounded prerequisite if
safe handling needs an independent mechanism. These are engineering observations,
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
