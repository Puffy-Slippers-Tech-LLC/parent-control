# New kiosk confinement improvements queue

The [master](Kiosk-Session-Confinement-New-Plan.md) owns usability, reasonable-child
threat scope, finite improvements and final acceptance. The
[baseline queue](Kiosk-Prompt-Queue.md) ends at C05f and is independent of these
improvements. C06a first verifies accepted C05u/f results; missing baseline
evidence keeps it unchecked. Stable C06–C13 IDs and original scopes are retained.

Targeted new confinement tests and normal-use controls belong here. New general
feature automation stays in the [E2E queue](TestAutomation/E2E-Task-Queue.md).
Reuse shared implementations and qualification under the
[cross-plan map](TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse);
no duplicate feature campaign or silent cross-queue completion.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | C06a | [Review ordinary login and remote routes](Kiosk-Prompt-Tasks/C06a-login-review.md) | Baseline | Map justified local/TTY/SSH/remote-desktop defenses and their permitted controls | 20–30 min |
| [ ] | C06 | [Review exposed routes and minimal protection design](Kiosk-Prompt-Tasks/C06-protection-review.md) | C06a | Complete the exposed-action/input map and independently approve the finite protection design | 20–30 min |
| [ ] | C07a | [Protect local desktop and TTY routes](Kiosk-Prompt-Tasks/C07a-local-routes.md) | C06 | Implement only justified graphical-session, shortcut, terminal and TTY barriers | 20–30 min |
| [ ] | C07b | [Protect kiosk SSH access](Kiosk-Prompt-Tasks/C07b-ssh.md) | C07a | Implement the justified SSH account-route barrier with ordinary-account positive coverage | 20–30 min |
| [ ] | C07 | [Protect the supported remote-desktop route](Kiosk-Prompt-Tasks/C07-login-routes.md) | C07b | Implement the named remote-desktop barrier and finish the login-route defense map | 20–30 min |
| [ ] | C08a | [Protect exposed launch actions](Kiosk-Prompt-Tasks/C08a-actions.md) | C07 | Close justified link/chooser/handler and automatic-launch escape routes | 20–30 min |
| [ ] | C08 | [Protect child-controlled consumed inputs](Kiosk-Prompt-Tasks/C08-exposed-routes.md) | C08a | Exclude justified child-controlled startup/settings inputs without private loading infrastructure | 20–30 min |
| [ ] | C09a | [Preserve optional presentation and language fallbacks](Kiosk-Prompt-Tasks/C09a-optional.md) | C08 | Remove demonstrated optional-resource admission coupling while retaining core requests | 20–30 min |
| [ ] | C09b | [Bound required-service recovery](Kiosk-Prompt-Tasks/C09b-service-recovery.md) | C09a | Recover a transient shared-service fault and preserve its original sanitized diagnostic cause | 20–30 min |
| [ ] | C09b1 | [Isolate an unavailable child's integration](Kiosk-Prompt-Tasks/C09b1-child-isolation.md) | C09b | Keep healthy-child requests usable without weakening an unavailable child's required enforcement | 20–30 min |
| [ ] | C09c | [Recover owned interrupted or stale state](Kiosk-Prompt-Tasks/C09c-owned-recovery.md) | C09b1 | Recover proven owned stale state while preserving foreign and live sessions | 20–30 min |
| [ ] | C09c1 | [Preserve usable entry through relevant updates](Kiosk-Prompt-Tasks/C09c1-update-activation.md) | C09c | Fix demonstrated product/dependency activation gaps and bind one complete update/reentry history | 20–30 min |
| [ ] | C09 | [Audit valid host variation and remaining usability coupling](Kiosk-Prompt-Tasks/C09-compatibility.md) | C09c1 | Verify valid host/PAM variation and close the bounded compatibility disposition map | 20–30 min |
| [ ] | C10 | [Freeze the finite final acceptance map](Kiosk-Prompt-Tasks/C10-acceptance-map.md) | C09 | Verify exact registered histories, candidate applicability and both-platform acceptance ownership | 20–30 min |
| [ ] | C11 | [Qualify the final core journey on Ubuntu](Kiosk-Prompt-Tasks/C11-acceptance-ubuntu.md) | C10 | Ubuntu: Complete final passwordless, approval/time/app and retained-feature public journey | 30–60 min; session exception: complete final customer journey |
| [ ] | C11a | [Qualify valid host variation on Ubuntu](Kiosk-Prompt-Tasks/C11a-variation-ubuntu.md) | C11 | Ubuntu: Verify finite host/PAM variations preserve usable requests | 20–30 min |
| [ ] | C11a1 | [Qualify optional fallbacks on Ubuntu](Kiosk-Prompt-Tasks/C11a1-optional-ubuntu.md) | C11a | Ubuntu: Verify finite presentation and native-language fallbacks preserve genuine approval | 20–30 min |
| [ ] | C11b | [Qualify service recovery and diagnostics on Ubuntu](Kiosk-Prompt-Tasks/C11b-service-recovery-ubuntu.md) | C11a1 | Ubuntu: Complete required-service recovery and real Parent diagnostic download | 30–45 min; session exception: complete service recovery and diagnostic history |
| [ ] | C11b1 | [Qualify healthy-child isolation on Ubuntu](Kiosk-Prompt-Tasks/C11b1-child-isolation-ubuntu.md) | C11b | Ubuntu: Complete unavailable-child, healthy-child request and restored-child history | 20–30 min |
| [ ] | C11c | [Qualify owned-state recovery on Ubuntu](Kiosk-Prompt-Tasks/C11c-lifecycle-ubuntu.md) | C11b1 | Ubuntu: Complete owned interrupted-state recovery and fresh entry | 30–45 min; session exception: complete owned-state recovery history |
| [ ] | C11c1 | [Qualify update and reentry on Ubuntu](Kiosk-Prompt-Tasks/C11c1-updates-ubuntu.md) | C11c | Ubuntu: Complete relevant product/dependency update and fresh-entry history | 30–60 min; session exception: complete package/dependency update history |
| [ ] | C11d | [Qualify desktop and TTY barriers on Ubuntu](Kiosk-Prompt-Tasks/C11d-local-routes-ubuntu.md) | C11c1 | Ubuntu: Pair actual local desktop/terminal/TTY attempts with permitted entry controls | 20–30 min |
| [ ] | C11e | [Qualify the SSH account boundary on Ubuntu](Kiosk-Prompt-Tasks/C11e-ssh-ubuntu.md) | C11d | Ubuntu: Verify kiosk SSH denial with an enabled service and ordinary-account positive | 20–30 min |
| [ ] | C11f | [Qualify the remote-desktop boundary on Ubuntu](Kiosk-Prompt-Tasks/C11f-remote-desktop-ubuntu.md) | C11e | Ubuntu: Verify named-provider kiosk denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | C11g | [Qualify exposed actions on Ubuntu](Kiosk-Prompt-Tasks/C11g-exposed-inputs-ubuntu.md) | C11f | Ubuntu: Verify finite exposed-launch negatives and permitted public-action controls | 20–30 min |
| [ ] | C11g1 | [Qualify consumed inputs on Ubuntu](Kiosk-Prompt-Tasks/C11g1-consumed-inputs-ubuntu.md) | C11g | Ubuntu: Verify actual child-controlled consumed inputs and trusted-loading positives | 20–30 min |
| [ ] | C12 | [Qualify the final core journey on Fedora](Kiosk-Prompt-Tasks/C12-acceptance-fedora.md) | C11g1 | Fedora: Complete final passwordless, approval/time/app and retained-feature public journey | 30–60 min; session exception: complete final customer journey |
| [ ] | C12a | [Qualify valid host variation on Fedora](Kiosk-Prompt-Tasks/C12a-variation-fedora.md) | C12 | Fedora: Verify finite host/PAM variations preserve usable requests | 20–30 min |
| [ ] | C12a1 | [Qualify optional fallbacks on Fedora](Kiosk-Prompt-Tasks/C12a1-optional-fedora.md) | C12a | Fedora: Verify finite presentation and native-language fallbacks preserve genuine approval | 20–30 min |
| [ ] | C12b | [Qualify service recovery and diagnostics on Fedora](Kiosk-Prompt-Tasks/C12b-service-recovery-fedora.md) | C12a1 | Fedora: Complete required-service recovery and real Parent diagnostic download | 30–45 min; session exception: complete service recovery and diagnostic history |
| [ ] | C12b1 | [Qualify healthy-child isolation on Fedora](Kiosk-Prompt-Tasks/C12b1-child-isolation-fedora.md) | C12b | Fedora: Complete unavailable-child, healthy-child request and restored-child history | 20–30 min |
| [ ] | C12c | [Qualify owned-state recovery on Fedora](Kiosk-Prompt-Tasks/C12c-lifecycle-fedora.md) | C12b1 | Fedora: Complete owned interrupted-state recovery and fresh entry | 30–45 min; session exception: complete owned-state recovery history |
| [ ] | C12c1 | [Qualify update and reentry on Fedora](Kiosk-Prompt-Tasks/C12c1-updates-fedora.md) | C12c | Fedora: Complete relevant product/dependency update and fresh-entry history | 30–60 min; session exception: complete package/dependency update history |
| [ ] | C12d | [Qualify desktop and TTY barriers on Fedora](Kiosk-Prompt-Tasks/C12d-local-routes-fedora.md) | C12c1 | Fedora: Pair actual local desktop/terminal/TTY attempts with permitted entry controls | 20–30 min |
| [ ] | C12e | [Qualify the SSH account boundary on Fedora](Kiosk-Prompt-Tasks/C12e-ssh-fedora.md) | C12d | Fedora: Verify kiosk SSH denial with an enabled service and ordinary-account positive | 20–30 min |
| [ ] | C12f | [Qualify the remote-desktop boundary on Fedora](Kiosk-Prompt-Tasks/C12f-remote-desktop-fedora.md) | C12e | Fedora: Verify named-provider kiosk denial and permitted ordinary-account remote desktop | 20–30 min |
| [ ] | C12g | [Qualify exposed actions on Fedora](Kiosk-Prompt-Tasks/C12g-exposed-inputs-fedora.md) | C12f | Fedora: Verify finite exposed-launch negatives and permitted public-action controls | 20–30 min |
| [ ] | C12g1 | [Qualify consumed inputs on Fedora](Kiosk-Prompt-Tasks/C12g1-consumed-inputs-fedora.md) | C12g | Fedora: Verify actual child-controlled consumed inputs and trusted-loading positives | 20–30 min |
| [ ] | C13 | [Close matching product, automation and documentation](Kiosk-Prompt-Tasks/C13-closeout.md) | C12g1 | Audit release provenance, retained features, justified refusals and final matching both-platform evidence | 20–30 min |

Order is authoritative; IDs are stable labels. C06a's external baseline gate
replaces its former same-queue C05f dependency. Every other dependency, scope,
installed target and acceptance family remains. No checkbox transfers or closes
through planning. C07–C09 own affected finite bindings; C10 verifies their
qualification and candidate applicability. C11/C12 each retain full per-platform
histories and restoration, including named longer session exceptions.
Unexpected independent work uses the selected-consumer prerequisite contract.

Selectors are planned until implemented, registered and qualified. Host checks
and `--check` establish no installed pass. C13 audits matching product/TA/docs
and retained evidence after both-target final acceptance.
