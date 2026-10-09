## v1.4 -
### New Features
- **Language Dialog**: You can search for a language by its English name as well as its localized name
- **Remaing Time Reminders**: Added default critical reminders in child session. Reminders can show in full-screen apps and can be customized in child preferences.
- **Parent App**: Revoke dialog shows list of running soft blocked apps that will be terminated.
- **What's New**: Added metadata-driven What's new infra

### Bug Fixes
- **Broker**: Fixed startup failures caused by temporary trust-database lock contention and preserved bounded dependency diagnostics after service recovery without collecting personal data.
- **Broker**: Added automatic recovery when the fapolicyd service exits with an error.
- **Parent App**: Parent app app grid column headers on some RTL languages overlap
- **Parent App**: Fixed the disabled Revoke button at zero remaining time when soft-blocked apps are still running, allowing parents to close those apps after the child’s session locks.

### Fedora Workstation 44 Readiness
- **Test Automation:** One big step closer - all automated tests are passing on Fedora


## v1.3 - 2026-10-03
### New Features
- Localization: Supports 62 languages, including RTL (you voted, we listened! Don't get spoiled though :) Do me a favor, spread the word out, help more families!)

### Bug Fixes
- Parent and kiosk: Added a reboot-required modal with a red Reboot now button for pending product updates; unrelated system reboot requests do not trigger it.

### Fedora Workstation 44 Readiness
- Across the board: Fixed a few blocking issues across fdpolicy import, SELinux, Broker. Basic testing proves the product is working end to end (yeah!). Next step: more manual testing and crazy automation coverage. Don't get excited too early. 10% effort on product, 90% on testing, matches my 30yr experience.

### Non Product Changes
- Increased e2e coverage to 33

## v1.2 - 2026-09-29
### Bug Fixes
- Software Updater: Fixed the description to match app name
- Packaging: Removed some non-product files (internal tools, docs) from package.
- Screen time bug: Screen-time changes failed when fapolicyd 1.3.6 couldn’t represent certain filenames; the fix skips unnecessary exceptions for already-blocked files and validates rules before changing  settings, with clearer errors for unsupported cases.
- Broker: Lunar client still auto launches and can launch in-memory AppImage of Minecraft even when it's soft blocked
- Broker: Harden execution probes with isolated D-Bus clients, retained late replies, recoverable cleanup, and stricter execution identity checks.
- Child App: Fixed Child App timer recovery after waking from suspend and added privacy-safe diagnostics for countdown refresh failures (thanks for the crash report on 9/27/2026, dear user!)


### New Features
- Logging: Added bunch of logging to help troubleshoot - no PII logged, as promised
- Logging: Changed time from local to UTC
- Feedback dialog: Log collection is now asynchronous, Send feedback button is disabled until logs are collected. Added system-info to logs. No PII logged, as promised
- Parent App: Made "How it's calculated" clearer to understand
- Child App: Added "oh-no-parent-control-child" command as an alias for "oh-no-parent-control --child-overlay". Easier for future expansion to other distros and desktop environments

### Non Product Changes
- Automated 24 E2E cases (serious efforts on serious high quality testing, as advertised)

## v1.1 — 2026-09-11
### Bug Fixes
- **Parent App:** Fixed an issue where Daily Allowance would not expand on small screens.
- **Broker**: Fixed execution policies failing to reload when unchanged rule files masked stale active rules.

## v1.0 — 2026-09-10
### New Features
- Initial release.

- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
- Initial release.
