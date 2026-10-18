# 006 — Confinement with heterogeneous filesystem inputs

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and route

Required tasks: 005.
Read the [master](../Reliability-Plan.md),
[directory-view contract](../SystemDesign/Kiosk-Confinement.md#native-execution-and-executable-identity),
`tools/kiosk_confinement.py`, native binding/preparation callers and the complete
relevant `system_kiosk_confinement.py` functions. Extend those canonical
environment variants and existing host directory/trust/alias tests.

Planned selector (unimplemented): `test_kiosk_directory_environment_variants`,
area `enforcement`. Reuse exact existing assertions rather than duplicate the
full confinement matrix. Attempt-owned path mutations must have recorded
identities; reusable fixtures belong in baseline preparation.

## Finite variants and expected results

1. Two unrelated root-owned sibling data directories, one mode 0775 and one
   mode 0777, each containing one distinct inert canary:
   kiosk entry works; its private view is empty and receives no host mutation.
   Ordinary users retain the original contents and access.
2. A group-writable required executable ancestor, and a required input whose
   alias/target chain no longer matches its pinned identity: preparation refuses
   before publishing untrusted execution. A legitimate trusted package change
   is not automatically an unsafe alias.
   Restore only the exact owned mutation and require normal native recovery.
3. Host mutation/replacement of an unrelated masked entry after preparation:
   the retained kiosk cannot acquire mutable content through a host alias.

Use inert canaries, never an unbounded scan or arbitrary third-party installer.
Preserve required native binds and strict group/world-write rules, including
root-group inputs. Verify admission, enforcing execution and isolation rather
than accepting a generated manifest or policy string as native proof.

## Validation and close-out

Run affected host trust/layout/refusal and fixture-cleanup checks, then all
finite installed variants and restored-input recovery on both targets. Record
the actual variant, kernel/security mode, private-view witness, positive
ordinary-user control and cleanup. Repair generic root causes in shared code;
isolate only demonstrated distro differences. Build after product edits and
update the existing confinement/environment coverage owners.
