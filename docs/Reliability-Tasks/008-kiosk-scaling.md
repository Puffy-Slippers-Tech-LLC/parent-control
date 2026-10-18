# 008 — Kiosk reliability with enlarged inventory

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 008a, 008b.
Estimate: 30–60 minutes.
Session exception: ordinary entry, supported profile activation and two retained
enlarged-inventory cycles compare one candidate in a finite history per target.

## Purpose and route

Target inventory-dependent preparation and warm-up/logout lifetime from
`6987d0ce`, `925438ba` and `75f608f6`. The result is a usable station within
existing deadlines, a correctly bound immediate request and clean exit/reentry.
This task does not inherit the commits' performance-improvement objective.

Read the [master](../Reliability-Plan.md),
[frontend lifecycle](../SystemDesign/Frontends.md),
[directory-generation lifecycle](../SystemDesign/Kiosk-Confinement.md#native-execution-and-executable-identity),
[timing observation contract](../../tests/e2e/README.md#kiosk-transition-timing)
and complete shared `vm_probe.py`, locale/logout and namespace cleanup call
chains. 008a/008c supply deterministic pending-warm-up ordering and failure/retry;
008b supplies fallback lifetime. Use the existing native startup fixture and
record its actual renderer path; neither 006a's writable-directory mutation nor
007b's GPU mapping proof is a prerequisite for this inventory-growth condition.
Crash/export and unrelated customer scenarios are not prerequisites.

Planned qualification (unimplemented): `check_e2e_kiosk_inventory_scaling`,
extending the existing transition qualification/transport owner.

## Finite history and expected results

Use one verified candidate. Run one ordinary-inventory entry/Request/Cancel
cycle, then add 256 inert root-owned sibling entries through the shared owned
fixture. Activate that changed inventory through the existing supported guest
reboot/session preparation route before its first kiosk entry: confinement pins
the manager's directory generation, so reusing the ordinary profile's live
manager would test stale-generation refusal instead of inventory growth.
Run two enlarged-profile entry/Request/Cancel cycles without resetting between
them. Record both inventory manifests and an owned idle resource baseline per
profile. The activation reboot is not a cold/warm benchmark matrix.

In each cycle, submit Request once at the first independently established form
readiness. Observe the correctly bound native approval prompt, cancel without
a password and confirm unchanged grant/policy and request choices. Then use
station Cancel and independently observe usable GDM within existing deadlines.
This complete transition is the minimum result for the warm-up/logout lesson;
no approval, exhaustion or broader form-feature journey is required here.

Capture raw transition times and the failed stage if a deadline is missed,
using existing observer/clock uncertainty definitions. Latency is diagnostic;
there is no new percentile, speedup or relative-performance gate. Do not wait
deliberately for speculative preparation; a fast VM completion does not prove
the pending-warm-up race, which 008a/008c cover deterministically.

At equivalent quiescent checkpoints after every cycle, compare owned timers,
app/report children, namespace staging mounts and units against that profile's
recorded baseline. A previous kiosk must not leave duplicate clients or staging
behind.
Global process counts are not an ownership oracle. Preserve each intermediate
failure before another transition can hide it.

## Work sequence

1. Verify candidate, ordinary manifest and baseline; complete the ordinary cycle.
2. Apply the exact owned enlarged-inventory fixture, perform supported activation
   and record its idle baseline. Complete its first cycle with independent
   readiness, prompt, unchanged-state, exit and resource checks.
3. Reenter without another reboot/reset and complete the second enlarged cycle
   with the same checks. Retain each result and raw timing, not an average hiding
   a failure.
4. Restore only the owned inventory mutation and finish cleanup.

## Validation and close-out

Run affected host locale/logout, namespace/input/timing and cleanup guards.
Execute all three cycles on both targets. Fix demonstrated redundant work or
lifecycle defects without weakening policy, durability, recipient checks or
deadlines. Rerun the complete affected history after changed inputs. Build after
product edits; retain actual selector, functional/resource results and cleanup
in existing owners. Close only 008.
