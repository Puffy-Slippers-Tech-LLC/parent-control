# 004d — Qualify the Ubuntu and Fedora native update histories

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Requires: 004c, 004c1.

The [004c1 host prerequisite](../Core-Installation-Coverage-Handoff.md#task-004c1-fedora-native-triggers)
reconciled the actual Fedora external trigger inventory. Its host checks and
read-only probes supply no installed acceptance.
The [master recovery record](../Core-Installation-Coverage-Handoff.md#task-004d-qualification-suspension)
retains failed attempts, exact bindings, the host-checked Ubuntu readiness repair
and completed cleanup. Neither failed history supplies acceptance; restart both
complete histories after the prerequisite with final applicable inputs/helpers.

## Scope and prerequisites

Run one complete history per target implementing every
[004 assertion](004-native-dependency-update.md), using the finite DEB/RPM inputs
from [004b](004b-native-transaction-inputs.md) and the registered history from
[004c](../Core-Installation-Coverage-Handoff.md#task-004c-retained-session-history).
System case **289**, `test_native_dependency_update_retained_session`, has two
ordered phases, `native-update` and `native-update-rebooted`, in one baseline
attempt. Follow the [installed runner invocation](../../../tests/integration/README.md#retained-session-native-dependency-update):

```sh
tools/run-tests system --vm 'onpc-Ubuntu26.04,onpc-Fedora44' --id 289 --native-inputs
```

Each target worker prepares current product inputs and its own verified native
pair; Ubuntu receives DEB/bubblewrap and Fedora receives RPM/xdg-dbus-proxy.
Do not reuse a sibling's input path. The old native transaction precedes product
installation, initial configuration and reboot; the first phase retains the
public station across the new native transaction. Normal public exit, preserved
pre-reboot evidence and a second real reboot precede fresh admission in the
second phase. A failed or interrupted history restarts in full.
Verify both prerequisites and
accepted baseline provenance, dependency closure and exact staged inputs for
each target before execution. Follow the
[VM mandate](../../Mandates/VM-Mandate.MD) and maintained installed runner;
auto preparation owns missing reusable prerequisites. No ad hoc package fetch,
baseline repair or unbounded update inside the history.

Schedule Ubuntu and Fedora in parallel through maintained runner routes within
the registry concurrency cap, with separate leases, target-specific inputs and
evidence. Neither target depends on the other's pass. Keep each VM's phases
ordered. Split out a target-specific prerequisite only for an evidenced issue
unique to that VM; keep shared implementation and fixes in common tasks.

Original scopes retained by consolidation:

- Complete retained-session native package transaction and recovery on Ubuntu, with owned cleanup
- Complete retained-session native package transaction and recovery on Fedora, with owned cleanup

## Acceptance and close-out

Keep the complete old-generation admission → retained-session native transaction
→ enforcing old mappings/refused unsafe publication → normal retirement and
fresh-session recovery in one owned attempt, with no intermediate restore.
Require real native script/trigger evidence, changed measured bytes, exact live
identity/generation, independent denial and positive controls, loader/reexec
results, unchanged policy, ordinary-user/vendor preservation and public broker
recovery under 004a's resolved expectations. Fresh installation after a prior
dependency update and service readiness alone supply no acceptance.
Require native DEB/RPM script/trigger evidence for the corresponding target.
Preserve enforcing SELinux on Fedora and all teardown restrictions on both VMs;
no foreign-process signalling or synthetic replacement credit.

For each target, retain both-generation native versions/digests, exact
package/source/input/helper/baseline bindings, phase JUnits and separate product/infrastructure/collection/
cleanup results. Let recording, baseline restoration and off verification finish.
Keep reports through 004 close-out using
[retention/export](../../../tests/README.md#aggregate-output-retention).
Record both receipts in the existing master/queue; mark only 004d complete after
both targets pass and advance to 004. Keep a valid complete result when its
sibling fails; rerun every failed or invalidated complete target history, including
a previously passing sibling affected by shared helper/input/assertion changes.
Leave 004 unchecked and customer E2E untouched. The 30–45 minute session exception
covers parallel indivisible native transaction/recovery histories and cleanup;
a lower concurrency cap can increase wall time. Additional independent missing
work requires a prerequisite, not reduced assertions.
