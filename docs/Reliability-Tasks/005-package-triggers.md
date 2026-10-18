# 005 — Package triggers with exhausted retained users

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 45–75 minutes.

## Session boundary

Deliver the native package/user-trigger history while the exhausted user's
manager and desktop remain alive. 005a supplies deterministic bridge identity
controls. Session exception: package trigger, zero-time admission and approved
recovery must be observed within each target's same retained-user history.

## Purpose and route

Required tasks: 004, 005a.
Read the [master](../Reliability-Plan.md),
[administrative bridge contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
[package lifecycle](../SystemDesign/Lifecycle.md), `tools/session_limit_check.py`,
its host tests and the installed session/first-configuration owners.
This is the native retained-user/package-trigger gap from `f0e4dc77`, with the
denied-kiosk precursor fixed in `0690f1de`. Core-installation task 001 already
qualified failed kiosk-manager reset and trigger enumeration; do not recreate
it as a new standalone deliverable.

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
exemption. Reuse 005a's negative identity/command controls; native evidence must
bind the positive bridge to its real unit/process.
No manager restart, cleared usage or grant may conceal the zero-time boundary.
After one real approval, normal child entry and unchanged policy must work.

## Work sequence

1. Establish zero usable time with the child's manager and locked desktop still
   alive. Record those identities and the second user's retained work.
2. Perform the one maintained same-version package transaction. Bind its actual
   user-unit trigger and positive administrative bridge to native unit/process
   evidence before changing the child's time state.
3. Observe the ordinary zero-time restrictions and kiosk admission boundary;
   no restart, usage clearing or grant may repair this intermediate result.
4. Obtain the real approval, verify normal child entry and unchanged policy,
   recheck the other user's work and complete owned cleanup.

## Validation and close-out

Run affected bridge/PAM/package host regressions and, only if their inputs
changed, existing first-configuration recovery selections. Execute the complete
new history on both native package formats and preserve actual user-trigger
receipts, retained identities, other-user controls and owned cleanup. Fix root
causes without broad PAM exceptions. Build as required and record exact coverage.
Earlier-package upgrades and live dependency updates stay in the core queue.
