# Linux Mint support investigation

Research date: 2026-09-07. Target: the forthcoming Ubuntu 26.04 LTS-based Linux Mint release, with Cinnamon and LightDM. Status: investigation and recommendation; support has not been implemented or qualified on a Mint image.

## Short Summary

Supporting this Mint release looks feasible. The main work is making screen-time tracking, the child interface, login/unlock restrictions, and the request kiosk work correctly with Cinnamon and LightDM.

- **Keep Malcontent.** Ubuntu 26.04 provides the interfaces the application uses.
- **No compatibility reason to downgrade or replace it has been demonstrated.** Either choice would still leave the Cinnamon and LightDM integration work.
- **Fix the known Malcontent security issue before release.** Local users can cause its timer data to fill disk space; Ubuntu currently lists it as unresolved.
- **Budget roughly 4–8 person-weeks for one Cinnamon session configuration, or 6–10 for both X11 and Wayland.** Shared security fixes and unfinished Ubuntu baseline qualification are additional work. A custom timer could add several weeks to months.

## Scope and evidence

The investigation evaluates technical feasibility, enforcement risk, backend choices, and incremental engineering cost. Simple distribution-name checks and version allowlists are excluded from the estimate. The primary desktop under consideration is Cinnamon with LightDM; additional desktop editions would need their own assessment and qualification.

Repository findings are based on the [system design](System-Design.md), [screen-time design](SystemDesign/Screen-Time.md), [front-end design](SystemDesign/Frontends.md), and their implementation files. External findings come from official Mint announcements, Ubuntu package and security information, and upstream source and interface documentation.

Mint has announced Ubuntu 26.04 LTS as the package base. Its published plan targets Christmas 2026 and includes fully supported X11 and Wayland sessions, an integrated Cinnamon lock screen, and systemd graphical-session support. These establish a plausible target architecture, not proof of application compatibility. Final Mint package versions, defaults, and authentication paths remain subject to verification. [Mint package-base announcement](https://blog.linuxmint.com/?p=5019), [Mint session and release plans](https://blog.linuxmint.com/?p=5046).

## Dependency compatibility

Ubuntu 26.04 currently provides the following relevant packages:

| Component | Package version observed | Implication |
| --- | --- | --- |
| Malcontent | `0.14.0-0ubuntu1` | Supplies the public timer API generation used by the application's usage queries and screen-time model. |
| GNOME Kiosk | `50.0-1` | Provides a candidate compositor/session stack for retaining the dedicated request kiosk. |

Sources: [Ubuntu Malcontent package](https://packages.ubuntu.com/resolute/malcontent), [Ubuntu GNOME Kiosk package](https://packages.ubuntu.com/resolute/gnome-kiosk).

Assuming Mint inherits these interfaces, dependency compatibility is promising. Repository availability does not establish installation by default, working Cinnamon integration, or successful kiosk startup under LightDM.

The Python broker, AccountsService integration, GTK4/libadwaita request form, Polkit authorization, and fapolicyd enforcement are candidates for substantial reuse. Their behavior still needs validation on the selected Mint packages. The GNOME Shell child component and GDM-specific integration require more direct adaptation.

## Technical work and risks

### Cinnamon usage reporting and child interface

The current [child indicator](../child/remainingTimeIndicator.js) imports GNOME Shell UI modules and uses `Main.timeLimitsManager`. The [extension manager](../broker/oh_no_parent_control/extension_manager.py) also depends on GNOME extension activation and verification. These are real desktop dependencies that configuration changes cannot resolve.

Malcontent's documented architecture receives usage records from the child's desktop session and stores them in a system service. It exposes public `RecordUsage`, `GetEstimatedTimes`, and `EstimatedTimesChanged` interfaces. A Cinnamon component could report usage and query deadlines through those interfaces while retaining Malcontent's storage and access controls. This is an integration proposal, not a verified implementation. [Malcontent screen-time design](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/docs/screen-time.md), [public child timer interface](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml).

The Cinnamon work would include countdown display, request-form launch, per-child activation, expiry locking, and session-entry reconciliation through the broker. Usage accounting must handle locking, suspend/resume, user switching, concurrent sessions, and component restarts without granting unaccounted time or counting the same interval twice. The shared GTK form also needs focus, fullscreen, and multiple-monitor checks under Cinnamon.

Risk is **medium for UI integration and high for accounting/enforcement correctness**. A countdown that appears to work is insufficient evidence of enforced time limits.

### Login and unlock enforcement

Cinnamon's development lock-screen implementation exposes `org.cinnamon.ScreenSaver`, including lock requests and state notifications. That provides a supported interface to investigate for expiry handling. [Cinnamon screen-saver interface](https://github.com/linuxmint/cinnamon/blob/master/js/misc/screenSaver.js).

A concrete gap exists in the authentication path. The inspected Cinnamon implementation uses the `cinnamon` PAM service. Its authentication helper calls PAM account management but ignores that operation's failure result. The Debian PAM profile includes `common-auth`. Consequently, installing an account-phase restriction alone does not establish exhausted-time unlock denial. [PAM service name](https://github.com/linuxmint/cinnamon/blob/master/src/screensaver/cs-auth.h), [authentication helper](https://github.com/linuxmint/cinnamon/blob/master/src/screensaver/cs-auth-pam.c#L522), [Debian PAM profile](https://github.com/linuxmint/cinnamon/blob/master/data/pam/cinnamon.pam.debian).

The application's [additional PAM authentication check](../tools/session_limit_check.py) currently applies only to `gdm-password`. Mint support would need to apply the remaining-time decision through the supported Cinnamon authentication path and verify the actual LightDM login paths. This must preserve valid grants, deny exhausted accounts, and handle backend errors correctly. Password, fingerprint, autologin, and user-switching paths must be assessed where enabled in the supported configuration.

The product's required behavior remains locking the retained child session at expiry while preventing usable access without time. Applications must survive screen-time expiry; repeated relocking after a successful unauthorized unlock is not sufficient. See the [screen-time enforcement contract](SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement).

This is a **high-risk integration area**. The Cinnamon sources cited here are development sources and must be checked against the release package.

### LightDM and the request kiosk

The existing kiosk uses a GNOME session declared with `Kiosk=true`, GNOME user service targets, a GDM pre-session hook, and a kiosk account login check that recognizes GDM-specific authentication. Relevant implementation: [session definition](../data/gnome-session/sessions/oh-no-parent-control.session), [kiosk application service](../data/systemd/user/oh-no-parent-control-app.service), [GDM hook](../data/gdm3/PreSession/Default), and [login check](../tools/oh-no-parent-control-login-check).

Keeping GNOME Kiosk as a dedicated request session under LightDM is a plausible option. LightDM supports Wayland session discovery and privileged session setup and cleanup hooks. Those capabilities justify a feasibility test; they do not prove this application's GNOME session starts and shuts down correctly there. [LightDM configuration interfaces](https://github.com/canonical/lightdm/blob/main/data/lightdm.conf).

Qualification must prove that the kiosk account can enter only its intended session, cannot obtain a normal desktop or unrelated login path, and returns safely to the greeter. It must also cover Polkit agent availability, cancelled requests, startup failures, and session cleanup. The child overlay and kiosk share a form, so both entry paths need validation.

Risk is **high for confinement and session lifecycle**, with no demonstrated need to replace the kiosk compositor itself.

### Application enforcement, packaging, and lifecycle

The broker's application enforcement should be reusable in large part, but Cinnamon's process identities and application launch behavior need examination. The [application-scope matcher](../broker/oh_no_parent_control/app_termination.py) recognizes specific paths under `app.slice` and application unit names. Cinnamon's new graphical-session target does not itself prove those conventions match. [Cinnamon session target](https://github.com/linuxmint/cinnamon-session/blob/master/data/systemd/user/cinnamon-session.target).

Installed tests must verify native and Flatpak launch routes, the broker's selection of running applications, enforcement after updates, and isolation from other users. Any advertised Snap behavior also needs qualification where Snap is installed. Launcher visibility is not proof of execution denial. See the [application policy design](SystemDesign/Applications.md).

The current [package dependencies](../debian/control) assume GNOME Shell and GDM. Mint packaging would need to express the appropriate desktop integration and retain LightDM as intended. Installation, activation, upgrades, and removal must preserve unrelated desktop configuration. Future implementation would follow the existing [setup entry point](../setup.sh), [package activation contract](Publishing.md#package-update-activation), and [data migration contract](SystemDesign/Data-Migration.md) where applicable.

Risk is **medium**, with most effort expected in integration and installed verification rather than replacing the broker or GTK application.

## Malcontent security and stability

Compatibility and release readiness are separate questions. Ubuntu currently marks Malcontent on Ubuntu 26.04 as vulnerable to **CVE-2026-44931**, with the fix deferred. Its advisory was last updated on August 17, 2026 and states that no upstream fix was available then. The issue permits local users to cause unbounded timer storage growth. SUSE's investigation also reports limited upstream development resources, which is relevant to maintenance planning. [Ubuntu advisory](https://ubuntu.com/security/CVE-2026-44931), [SUSE security investigation](https://security.opensuse.org/2026/05/11/malcontent-disk-space-dos.html).

This is a shared Ubuntu 26.04 dependency concern. The [project threat model](Threat-Model.md#supported-claims-limitations-and-release-blockers) already requires that the selected supported package no longer expose this vulnerability. The preferred resolution is a maintained upstream or distribution fix, followed by bounded-storage and normal-usage regression verification. The recommendation to retain Malcontent does not establish the currently observed package as release-ready.

Malcontent's design also relies on session-supplied usage and does not claim a hard security boundary. The project must demonstrate its stronger advertised guarantees against its own threat model, including attempts to interrupt reporting or obtain usable access after expiry. A custom root timer would still need trustworthy session, lock, and activity inputs; moving storage or arithmetic into the broker alone would not establish those guarantees. [Malcontent design and access model](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/docs/screen-time.md).

There is no target-image evidence here establishing that Malcontent is unstable specifically on Mint. The unresolved vulnerability and enforcement validation are concrete concerns; general Mint runtime stability remains unmeasured.

## Backend options

| Option | Assessment | Engineering consequence |
| --- | --- | --- |
| Keep modern Malcontent | Preferred, conditional on security fixes and supported-interface qualification. | Preserve the existing account policy, usage, grant, and Flatpak integration; add Cinnamon and LightDM support. |
| Downgrade Malcontent | No demonstrated Mint compatibility benefit. Consider a version change only for a reproduced regression with a maintained, compatible alternative. | Does not supply missing desktop or authentication integration; losing required APIs would create additional work. |
| Use Timekpr-nExT | No established advantage for this application's enforcement contract. | Requires policy and grant integration, failure/rollback analysis, and the same desktop and kiosk work. |
| Build a custom timer service | Reserve for a requirement that cannot be met using supported Malcontent interfaces and maintained fixes. | Own accounting, bounded storage, authorization, recovery, calendar/time behavior, testing, and long-term maintenance. |

Timekpr-nExT documents Cinnamon among its previously tested desktops, but its maintainer reports limited proactive testing against new desktop and dependency releases. Its default expiry action terminates sessions. Its lock mode permits unlocking followed by relocking and is described as appropriate for self-control. Neither provides a demonstrated match for this application's retained-session, exhausted-time denial requirement. [Timekpr-nExT documentation](https://mjasnik.gitlab.io/timekpr-next/).

If a timer replacement becomes necessary, evaluate it separately from Malcontent's application-filter integration. Replacing time accounting does not automatically justify replacing the AccountsService/Flatpak policy path. The application also reads usage in both the parent and broker helper flows, so a timer change would affect more than a single broker adapter. See [usage identities and grant arithmetic](SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities).

## Cost and ongoing support

These are preliminary person-week estimates for an engineer familiar with this repository. They describe incremental Mint work, not elapsed calendar promises or measured implementation results.

| Scope | Estimated effort |
| --- | --- |
| Retain Malcontent; qualify one Cinnamon session configuration with LightDM and the kiosk | 4–8 person-weeks |
| Retain Malcontent; qualify both Cinnamon X11 and Wayland | 6–10 person-weeks total |
| Replace the timer with a custom service | Several additional weeks to months, plus continuing maintenance |

The retained-backend estimate covers Cinnamon UI and usage reporting, PAM and LightDM integration, packaging and lifecycle adaptation, and installed-system qualification. It excludes shared Ubuntu security fixes, unfinished baseline qualification, additional desktop editions, and waiting for upstream fixes or target release availability. Supporting both display protocols enlarges the lock, suspend, focus, monitor, and failure-recovery test matrix.

Ongoing support requires a dedicated Mint regression environment and testing when Cinnamon, LightDM, authentication components, or enforcement dependencies change. Reusing the backend limits duplicated policy logic, but the desktop integration remains an additional maintained component. Installation footprint and runtime overhead have not been measured; the final package dependency set and reporter behavior should be measured during qualification.

## Proposed feasibility milestone and acceptance evidence

If implementation is commissioned, budget the first 3–5 engineering days within the estimates above to establish the following on a representative target image:

1. Confirm package versions and public interfaces; record the selected Cinnamon session type, locker, LightDM configuration, and authentication methods.
2. Demonstrate usage reporting and deadline queries across lock/unlock, suspend/resume, and component restart, with correct grant behavior.
3. Demonstrate that an exhausted child cannot obtain a usable session through the supported login and unlock paths, while a valid grant restores access.
4. Demonstrate the dedicated kiosk under LightDM, including account confinement, parent authentication, failed startup, cancellation, and return to greeter.

These results would narrow the integration estimate. Full acceptance would add midnight/time-change cases, concurrent sessions, reporting interruption, backend failure, application enforcement, other-user isolation, package lifecycle tests, and verification of the Malcontent security fix. The existing [threat model](Threat-Model.md) and [test automation](Test-Automation.md) define the required level of evidence.

The recommended implementation direction is to retain a maintained Malcontent backend, add supported Cinnamon and LightDM integration, and qualify an explicit Mint configuration before declaring support.
