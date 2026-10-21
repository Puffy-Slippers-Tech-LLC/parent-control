# F19 — Integrate Fedora installed E2E preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F18

## Scope and implementation

Qualify F18's installed E2E [matrix row](../Fixture-Design.md#runner-acceptance-matrix)
on Fedora. Read the full online restore/credential rebind/setup chain, F01's
Fedora consumer and affected native fixture/label readers. Use the same pinned
preparation and existing UI bindings; preserve native denials and enforcing SELinux.

## Finite acceptance

Run affected isolated safety checks and register/list the planned binding before
`tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_e2e_installed`.
Through the real online installed E2E preparation prove harmless fixture use
over SSH, then stop before E2E input or product actions/assertions. Check trust/
labels, fresh boot/attempt receipt after resume, missing/incompatible refusal
before worker input and no mid-attempt version switch. Confirm aliases use the
same guarded API and no full fixture copy remains in result inputs. Finish
watched restoration/transport/pin cleanup, renew affected Ubuntu proof after
shared fixes and update delivered owners through the [master](../Fixture-Execution-Plan.md).
