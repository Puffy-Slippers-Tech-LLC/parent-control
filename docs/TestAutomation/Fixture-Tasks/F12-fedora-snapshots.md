# F12 — Decouple Fedora snapshots from fixture payloads

Acceptance: installed
Targets: onpc-Fedora44
Requires: F05

## Scope and implementation

Deliver Fedora's [clean snapshot boundary](../Fixture-Design.md#runner-and-snapshot-migration)
using F11's shared implementation. Read its complete digest/capture/recovery
changes and remaining Fedora baseline/native/label/credential owners.
Retire only the complete proven owned legacy movable set, preserve environment
and legacy recovery, and refuse ambiguous identity. Preserve enforcing SELinux,
exact native ownership and genuine dependency/product invalidation.
Keep unmigrated Fedora consumers unavailable on clean captures.

## Acceptance and cleanup

Run affected capture/recovery/native safety tests first. Register/list
`check_fixture_snapshots` on this target and record any separately authorized
auto-mode refresh. Prove clean baseline/app captures, standalone app preparation
without runtime fixtures, legacy stop/restoration, fixture-only source independence
and no archived source/payload/admission leaks. No fallback to embedded fixtures.
Finish watched owned restoration. Renew affected Ubuntu checks after shared
changes and update the remaining VM/approval/environment owners for this boundary.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
