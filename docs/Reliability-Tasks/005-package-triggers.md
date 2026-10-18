# 005 — Package triggers with exhausted retained users

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and route

Required tasks: 004.
Read the [master](../Reliability-Plan.md),
[administrative bridge contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
[package lifecycle](../SystemDesign/Lifecycle.md), `tools/session_limit_check.py`,
its host tests and the installed session/first-configuration owners.
Core-installation task 001 already qualified failed kiosk-manager reset and
trigger enumeration; do not recreate it as a new standalone deliverable.

Planned selector (unimplemented):
`test_exhausted_user_package_trigger_transport`, extending the canonical package
or session owner according to the runner's phase/fixture contract. Register and
list its actual area before execution.

## Finite history and expected results

Keep one real child's user manager and locked desktop alive at zero usable
time; preserve a second ordinary user's work. Run one same-version native
package transaction that actually invokes the distro's user-unit trigger, using
the maintained installation entry. Checkout installation uses `make install`.
Capture native package/trigger outcomes and the matching administrative bridge;
a successful configuration script alone cannot establish the trigger result.

The root system manager's verified transient `systemd-stdio-bridge --user --quiet`
may reach that user's bus. Ordinary terminal/SSH/GDM time restrictions and kiosk
admission remain enforced; names, environment or forged arguments grant no
exemption. Required negative identity/command controls belong in existing host
tests; native evidence must bind the positive bridge to its real unit/process.
No manager restart, cleared usage or grant may conceal the zero-time boundary.
After one real approval, normal child entry and unchanged policy must work.

## Validation and close-out

Run affected bridge/PAM/package host regressions and, only if their inputs
changed, existing first-configuration recovery selections. Execute the complete
new history on both native package formats and preserve actual user-trigger
receipts, retained identities, other-user controls and owned cleanup. Fix root
causes without broad PAM exceptions. Build as required and record exact coverage.
Earlier-package upgrades and live dependency updates stay in the core queue.
