# 004e — Qualify the Fedora native update history

Acceptance: installed
Targets: onpc-Fedora44

Requires: 004c, 004d.

## Scope and prerequisites

Run one complete Fedora history against all
[004 requirements](004-native-dependency-update.md), with the finite RPM inputs
from [004b](004b-native-transaction-inputs.md) and final registration/invocation
from [004c](004c-native-update-history.md). Planned
`test_native_dependency_update_retained_session` is unimplemented until 004c.
Verify accepted baseline, dependency closure and exact staged inputs first.
Follow the [VM mandate](../../Mandates/VM-Mandate.MD) and maintained runner;
preparation owns reusable dependencies, while only the declared native
transaction is a scenario mutation.

## Acceptance and close-out

Keep old-input admission, retained-session native transaction, old-generation
enforcement, unsafe admission/publication refusal, reexec/retirement and fresh
recovery in one owned history. Require native RPM script/trigger evidence and
both generations' measured digests/process identities, positive and denial
controls, ordinary-user/vendor preservation, public broker operation and
unchanged child policy, with 004a's exact expected outcomes. Preserve enforcing
SELinux and all teardown restrictions. No phase splicing, intermediate restore,
foreign-process signalling or synthetic replacement credit.

Retain matching package/source/input/helper/baseline bindings, phase JUnits and
independent product/infrastructure/collection/cleanup results. Complete recording,
baseline restoration and off verification. Keep evidence through 004 under the
[retention contract](../../../tests/README.md#aggregate-output-retention).
If a Fedora fix changes shared helpers/inputs/assertions, rerun any invalidated
Ubuntu history completely before final 004 close-out. Record receipts in the
existing master/queue, mark only 004e complete and advance to 004; no customer
E2E completion. The 30–45 minute estimate covers one indivisible live history
and cleanup, not additional implementation.
