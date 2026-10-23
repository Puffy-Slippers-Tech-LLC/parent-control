# Remaining kiosk confinement improvements queue

The [master](Kiosk-Session-Confinement-New-Plan.md) owns usability, reasonable-child
threat scope, finite improvements and final acceptance. The
[baseline queue](Kiosk-Prompt-Queue.md) ends at C05f and is independent of these
improvements. C06a first requires completed desktop D04 and baseline C05u/f;
an unfinished prerequisite keeps it unchecked. Desktop-only rows move to the
[desktop queue](Kiosk-Desktop-Queue.md). Remaining IDs and assertions are retained.

Apply the master's [confinement priority](Kiosk-Session-Confinement-New-Plan.md#confinement-priority):
finish `tools/kiosk-desktop` before this plan. This queue owns everything else:
standalone terminal/TTY and SSH access, other actions/inputs and confinement
compatibility/recovery/lifecycle work. Neither launcher closes the other's tasks.

Targeted new confinement tests and normal-use controls belong here. New general
feature automation stays in the [E2E queue](TestAutomation/E2E-Task-Queue.md).
Reuse shared implementations and qualification under the
[cross-plan map](TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse);
no duplicate feature campaign or silent cross-queue completion.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | C06a | [Review remaining login routes](Kiosk-Prompt-Tasks/C06a-login-review.md) | Baseline | Verify accepted desktop/baseline gates and map standalone terminal/TTY and SSH defenses with permitted controls | 20–30 min |
| [ ] | C06x | [Map exposed launch actions](Kiosk-Prompt-Tasks/C06x-action-review.md) | C06a | Map actual reachable links, choosers, handlers and automatic launches with justified negatives and permitted controls | 20–30 min |
| [ ] | C06i | [Map child-controlled consumed inputs](Kiosk-Prompt-Tasks/C06i-input-review.md) | C06x | Map actual child-writable startup, settings, environment and search inputs at their real consumers | 20–30 min |
| [ ] | C06 | [Review the minimal remaining protection design](Kiosk-Prompt-Tasks/C06-protection-review.md) | C06i | Independently review the completed login/action/input maps and allocate finite protection and test boundaries | 20–30 min |
| [ ] | C07t | [Protect standalone terminal and TTY access](Kiosk-Prompt-Tasks/C07t-terminal-routes.md) | C06 | Implement only justified terminal/TTY and non-desktop shortcut barriers with normal-use controls | 20–30 min |
| [ ] | C07tu | [Verify normal kiosk use after C07t on Ubuntu](Kiosk-Prompt-Tasks/C07t-usability-ubuntu.md) | C07t | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07tf | [Verify normal kiosk use after C07t on Fedora](Kiosk-Prompt-Tasks/C07t-usability-fedora.md) | C07tu | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07b | [Protect kiosk SSH access](Kiosk-Prompt-Tasks/C07b-ssh.md) | C07tf | Implement the justified SSH account-route barrier with ordinary-account positive coverage | 20–30 min |
| [ ] | C07bu | [Verify normal kiosk use after C07b on Ubuntu](Kiosk-Prompt-Tasks/C07b-usability-ubuntu.md) | C07b | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C07bf | [Verify normal kiosk use after C07b on Fedora](Kiosk-Prompt-Tasks/C07b-usability-fedora.md) | C07bu | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C08a | [Protect exposed launch actions](Kiosk-Prompt-Tasks/C08a-actions.md) | C07bf | Close justified link/chooser/handler and automatic-launch escape routes outside full desktop prevention | 20–30 min |
| [ ] | C08au | [Verify normal kiosk use after C08a on Ubuntu](Kiosk-Prompt-Tasks/C08a-usability-ubuntu.md) | C08a | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C08af | [Verify normal kiosk use after C08a on Fedora](Kiosk-Prompt-Tasks/C08a-usability-fedora.md) | C08au | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C08 | [Protect child-controlled consumed inputs](Kiosk-Prompt-Tasks/C08-exposed-routes.md) | C08af | Exclude justified child-controlled startup/settings inputs without private loading infrastructure | 20–30 min |
| [ ] | C08u | [Verify normal kiosk use after C08 on Ubuntu](Kiosk-Prompt-Tasks/C08-usability-ubuntu.md) | C08 | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C08f | [Verify normal kiosk use after C08 on Fedora](Kiosk-Prompt-Tasks/C08-usability-fedora.md) | C08u | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09a | [Preserve optional presentation fallbacks](Kiosk-Prompt-Tasks/C09a-optional.md) | C08f | Remove demonstrated artwork, style, catalogue and notification coupling while retaining core requests | 20–30 min |
| [ ] | C09au | [Verify normal kiosk use after C09a on Ubuntu](Kiosk-Prompt-Tasks/C09a-usability-ubuntu.md) | C09a | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09af | [Verify normal kiosk use after C09a on Fedora](Kiosk-Prompt-Tasks/C09a-usability-fedora.md) | C09au | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09a1 | [Preserve native authentication language fallback](Kiosk-Prompt-Tasks/C09a1-auth-language.md) | C09af | Preserve genuine selected-parent authentication when optional native translations or locales are unavailable | 20–30 min |
| [ ] | C09a1u | [Verify normal kiosk use after C09a1 on Ubuntu](Kiosk-Prompt-Tasks/C09a1-usability-ubuntu.md) | C09a1 | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09a1f | [Verify normal kiosk use after C09a1 on Fedora](Kiosk-Prompt-Tasks/C09a1-usability-fedora.md) | C09a1u | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09b | [Bound required-service recovery](Kiosk-Prompt-Tasks/C09b-service-recovery.md) | C09a1f | Recover a transient shared-service fault and preserve its original sanitized diagnostic cause | 20–30 min |
| [ ] | C09bu | [Verify normal kiosk use after C09b on Ubuntu](Kiosk-Prompt-Tasks/C09b-usability-ubuntu.md) | C09b | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09bf | [Verify normal kiosk use after C09b on Fedora](Kiosk-Prompt-Tasks/C09b-usability-fedora.md) | C09bu | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09b1 | [Isolate an unavailable child's integration](Kiosk-Prompt-Tasks/C09b1-child-isolation.md) | C09bf | Keep healthy-child requests usable without weakening an unavailable child's required enforcement | 20–30 min |
| [ ] | C09b1u | [Verify normal kiosk use after C09b1 on Ubuntu](Kiosk-Prompt-Tasks/C09b1-usability-ubuntu.md) | C09b1 | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09b1f | [Verify normal kiosk use after C09b1 on Fedora](Kiosk-Prompt-Tasks/C09b1-usability-fedora.md) | C09b1u | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09c | [Recover owned interrupted or stale state](Kiosk-Prompt-Tasks/C09c-owned-recovery.md) | C09b1f | Recover proven owned stale state while preserving foreign and live sessions | 20–30 min |
| [ ] | C09cu | [Verify normal kiosk use after C09c on Ubuntu](Kiosk-Prompt-Tasks/C09c-usability-ubuntu.md) | C09c | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09cf | [Verify normal kiosk use after C09c on Fedora](Kiosk-Prompt-Tasks/C09c-usability-fedora.md) | C09cu | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09c1 | [Preserve usable entry through relevant updates](Kiosk-Prompt-Tasks/C09c1-update-activation.md) | C09cf | Fix demonstrated product/dependency activation gaps and bind one complete update/reentry history | 20–30 min |
| [ ] | C09c1u | [Verify normal kiosk use after C09c1 on Ubuntu](Kiosk-Prompt-Tasks/C09c1-usability-ubuntu.md) | C09c1 | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09c1f | [Verify normal kiosk use after C09c1 on Fedora](Kiosk-Prompt-Tasks/C09c1-usability-fedora.md) | C09c1u | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09 | [Audit valid host variation and remaining usability coupling](Kiosk-Prompt-Tasks/C09-compatibility.md) | C09c1f | Verify valid host/PAM variation and close the bounded compatibility disposition map | 20–30 min |
| [ ] | C09u | [Verify normal kiosk use after C09 on Ubuntu](Kiosk-Prompt-Tasks/C09-usability-ubuntu.md) | C09 | Ubuntu: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C09f | [Verify normal kiosk use after C09 on Fedora](Kiosk-Prompt-Tasks/C09-usability-fedora.md) | C09u | Fedora: Require candidate-matching passwordless entry and complete core use before the next product slice | 30–60 min; session exception: complete core customer history and restoration |
| [ ] | C10 | [Freeze the finite final acceptance map](Kiosk-Prompt-Tasks/C10-acceptance-map.md) | C09f | Verify exact registered histories, candidate applicability and both-platform acceptance ownership | 20–30 min |
| [ ] | C11 | [Qualify the final core journey on Ubuntu](Kiosk-Prompt-Tasks/C11-acceptance-ubuntu.md) | C10 | Ubuntu: Complete final passwordless, approval/time/app and retained-feature public journey | 30–60 min; session exception: complete final customer journey |
| [ ] | C11a | [Qualify valid host variation on Ubuntu](Kiosk-Prompt-Tasks/C11a-variation-ubuntu.md) | C11 | Ubuntu: Verify finite host/PAM variations preserve usable requests | 20–30 min |
| [ ] | C11a1 | [Qualify optional fallbacks on Ubuntu](Kiosk-Prompt-Tasks/C11a1-optional-ubuntu.md) | C11a | Ubuntu: Verify finite presentation and native-language fallbacks preserve genuine approval | 20–30 min |
| [ ] | C11b | [Qualify service recovery and diagnostics on Ubuntu](Kiosk-Prompt-Tasks/C11b-service-recovery-ubuntu.md) | C11a1 | Ubuntu: Complete required-service recovery and real Parent diagnostic download | 30–45 min; session exception: complete service recovery and diagnostic history |
| [ ] | C11b1 | [Qualify healthy-child isolation on Ubuntu](Kiosk-Prompt-Tasks/C11b1-child-isolation-ubuntu.md) | C11b | Ubuntu: Complete unavailable-child, healthy-child request and restored-child history | 20–30 min |
| [ ] | C11c | [Qualify owned-state recovery on Ubuntu](Kiosk-Prompt-Tasks/C11c-lifecycle-ubuntu.md) | C11b1 | Ubuntu: Complete owned interrupted-state recovery and fresh entry | 30–45 min; session exception: complete owned-state recovery history |
| [ ] | C11c1 | [Qualify update and reentry on Ubuntu](Kiosk-Prompt-Tasks/C11c1-updates-ubuntu.md) | C11c | Ubuntu: Complete relevant product/dependency update and fresh-entry history | 30–60 min; session exception: complete package/dependency update history |
| [ ] | C11t | [Qualify terminal and TTY barriers on Ubuntu](Kiosk-Prompt-Tasks/C11t-terminal-routes-ubuntu.md) | C11c1 | Ubuntu: Pair standalone terminal/TTY and non-desktop shortcut attempts with permitted entry controls | 20–30 min |
| [ ] | C11e | [Qualify the SSH account boundary on Ubuntu](Kiosk-Prompt-Tasks/C11e-ssh-ubuntu.md) | C11t | Ubuntu: Verify kiosk SSH denial with an enabled service and ordinary-account positive | 20–30 min |
| [ ] | C11g | [Qualify exposed actions on Ubuntu](Kiosk-Prompt-Tasks/C11g-exposed-inputs-ubuntu.md) | C11e | Ubuntu: Verify finite exposed-launch negatives and permitted public-action controls | 20–30 min |
| [ ] | C11g1 | [Qualify consumed inputs on Ubuntu](Kiosk-Prompt-Tasks/C11g1-consumed-inputs-ubuntu.md) | C11g | Ubuntu: Verify actual child-controlled consumed inputs and trusted-loading positives | 20–30 min |
| [ ] | C12 | [Qualify the final core journey on Fedora](Kiosk-Prompt-Tasks/C12-acceptance-fedora.md) | C11g1 | Fedora: Complete final passwordless, approval/time/app and retained-feature public journey | 30–60 min; session exception: complete final customer journey |
| [ ] | C12a | [Qualify valid host variation on Fedora](Kiosk-Prompt-Tasks/C12a-variation-fedora.md) | C12 | Fedora: Verify finite host/PAM variations preserve usable requests | 20–30 min |
| [ ] | C12a1 | [Qualify optional fallbacks on Fedora](Kiosk-Prompt-Tasks/C12a1-optional-fedora.md) | C12a | Fedora: Verify finite presentation and native-language fallbacks preserve genuine approval | 20–30 min |
| [ ] | C12b | [Qualify service recovery and diagnostics on Fedora](Kiosk-Prompt-Tasks/C12b-service-recovery-fedora.md) | C12a1 | Fedora: Complete required-service recovery and real Parent diagnostic download | 30–45 min; session exception: complete service recovery and diagnostic history |
| [ ] | C12b1 | [Qualify healthy-child isolation on Fedora](Kiosk-Prompt-Tasks/C12b1-child-isolation-fedora.md) | C12b | Fedora: Complete unavailable-child, healthy-child request and restored-child history | 20–30 min |
| [ ] | C12c | [Qualify owned-state recovery on Fedora](Kiosk-Prompt-Tasks/C12c-lifecycle-fedora.md) | C12b1 | Fedora: Complete owned interrupted-state recovery and fresh entry | 30–45 min; session exception: complete owned-state recovery history |
| [ ] | C12c1 | [Qualify update and reentry on Fedora](Kiosk-Prompt-Tasks/C12c1-updates-fedora.md) | C12c | Fedora: Complete relevant product/dependency update and fresh-entry history | 30–60 min; session exception: complete package/dependency update history |
| [ ] | C12t | [Qualify terminal and TTY barriers on Fedora](Kiosk-Prompt-Tasks/C12t-terminal-routes-fedora.md) | C12c1 | Fedora: Pair standalone terminal/TTY and non-desktop shortcut attempts with permitted entry controls | 20–30 min |
| [ ] | C12e | [Qualify the SSH account boundary on Fedora](Kiosk-Prompt-Tasks/C12e-ssh-fedora.md) | C12t | Fedora: Verify kiosk SSH denial with an enabled service and ordinary-account positive | 20–30 min |
| [ ] | C12g | [Qualify exposed actions on Fedora](Kiosk-Prompt-Tasks/C12g-exposed-inputs-fedora.md) | C12e | Fedora: Verify finite exposed-launch negatives and permitted public-action controls | 20–30 min |
| [ ] | C12g1 | [Qualify consumed inputs on Fedora](Kiosk-Prompt-Tasks/C12g1-consumed-inputs-fedora.md) | C12g | Fedora: Verify actual child-controlled consumed inputs and trusted-loading positives | 20–30 min |
| [ ] | C13a | [Audit final source and automation dispositions](Kiosk-Prompt-Tasks/C13a-source-audit.md) | C12g1 | Verify final release lineage, retained features and closure of conflicting source/test consumers against D00's map | 20–30 min |
| [ ] | C13 | [Close matching product, automation and documentation](Kiosk-Prompt-Tasks/C13-closeout.md) | C13a | Audit justified refusals, retained both-platform evidence and matching final documentation | 20–30 min |

Order is authoritative; IDs are stable labels. C06a's external gate is desktop
D04, which follows accepted baseline C05u/f. Desktop rows C07a/C07s/C07 and
C11d/f–C12d/f belong only to their desktop queue. C07t/C11t/C12t retain the
standalone terminal/TTY assertions split from those rows. No checkbox closes
through planning. Remaining protection/recovery tasks own affected finite bindings; C10 verifies their
qualification and candidate applicability. C11/C12 each retain full per-platform
histories and restoration, including named longer session exceptions.
Unexpected independent work uses the selected-consumer prerequisite contract.

Selectors are planned until implemented, registered and qualified. Host checks
and `--check` establish no installed pass. C13 audits matching product/TA/docs
and retained evidence after both-target final acceptance.
Use the shared launcher's current-definition and completion policies; ordinary
execution needs no plan-specific migration or historical-report preflight.
