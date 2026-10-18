# 004d — Qualify the Ubuntu native update history

Acceptance: installed
Targets: onpc-Ubuntu26.04

Requires: 004c.

## Scope and prerequisites

Run one complete Ubuntu history implementing every
[004 assertion](004-native-dependency-update.md), using the finite DEB inputs
from [004b](004b-native-transaction-inputs.md) and the registered history from
[004c](004c-native-update-history.md). The selector
`test_native_dependency_update_retained_session` is planned/unimplemented until
004c records its actual registration/invocation. Verify both prerequisites and
accepted baseline provenance before execution. Follow the
[VM mandate](../../Mandates/VM-Mandate.MD) and maintained installed runner;
auto preparation owns missing reusable prerequisites. No ad hoc package fetch,
baseline repair or unbounded update inside the history.

## Acceptance and close-out

Keep the complete old-generation admission → retained-session native transaction
→ enforcing old mappings/refused unsafe publication → normal retirement and
fresh-session recovery in one owned attempt, with no intermediate restore.
Require real native script/trigger evidence, changed measured bytes, exact live
identity/generation, independent denial and positive controls, loader/reexec
results, unchanged policy, ordinary-user/vendor preservation and public broker
recovery under 004a's resolved expectations. Fresh installation after a prior
dependency update and service readiness alone supply no acceptance.

Retain both-generation native versions/digests, exact package/input/helper/
baseline bindings, phase JUnits and separate product/infrastructure/collection/
cleanup results. Let recording, baseline restoration and off verification finish.
Keep reports through 004 close-out using
[retention/export](../../../tests/README.md#aggregate-output-retention).
Record receipts in the existing master/queue; mark only 004d complete and advance.
Leave 004 unchecked. The 30–45 minute session exception covers one indivisible
native transaction/recovery history and cleanup. Additional independent missing
work requires a prerequisite, not reduced assertions.
