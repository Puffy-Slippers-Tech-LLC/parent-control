## v1.2
### Bug Fixes
- Software Updater: Fixed the description to match app name
- Harden execution probes with isolated D-Bus clients, retained late replies, recoverable cleanup, and stricter execution identity checks.
- Packaging: Removed some non-product files (internal tools, docs) from package.
- Screen-time changes failed when fapolicyd 1.3.6 couldn’t represent certain filenames; the fix skips unnecessary exceptions for already-blocked files and validates rules before changing  settings, with clearer errors for unsupported cases.
- Broker: Lunar client still auto launches and can launch in-memory AppImage of Minecraft even when it's soft blocked
- Child App: Added "oh-no-parent-control-child" command as an alias for "oh-no-parent-control --child-overlay"


### New Features
- Logging: Added bunch of logging to help troubleshoot - no PII logged, as promised
- Logging: Changed time from local to UTC
- Feedback dialog: Log collection is now asynchronous, Send feedback button is disabled until logs are collected. Added system-info to logs. No PII logged, as promised
- Parent App: Made "How it's calculated" clearer to understand

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
