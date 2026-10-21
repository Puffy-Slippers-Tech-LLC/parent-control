# F50 — Compose fixture-native activation acknowledgements

Acceptance: host
Requires: F32

## Scope and implementation

Compose F31's rule/decision API and F32's owned tracees into the
[finite native protocol](../Fixture-Design.md#fixture-only-native-acknowledgement-protocol).
Journal barrier installation, per-UID open/execute proof, exact trust addition/
retirement, payload readback, barrier release and probe/observer retirement.
Bind nonce, phase, input/rule maps, journal cursor and daemon invocation throughout.
Require attributed allow plus actual positive execution/readback and attributed
deny plus actual refusal. Prove retiring trust at original paths before unlink;
retain shared digest admissions needed by surviving identical runtimes.

Observers require the unique private executable as well as PID/UID. Settle all
tracees/descendants and close descriptors before removing that executable;
then retire observer sources. PID reuse cannot activate a stale observer.
Keep all non-fixture rules unchanged. Treat partial parse, unrelated denial,
permissive/stopped/restarted daemon, missing log, changed inputs or external rule
mutation as unavailable readiness. Reconcile lost replies using recorded receipts;
do not repeat uncertain execution or signals. This supplies no acknowledgement
of arbitrary product/admin policy and no product acceptance.

## Finite validation and cleanup

Use independent file/rule/compiled/daemon/process doubles for every before/after
transition, stale generation, partial parsing, queue-overflow denial, permissive
mode, log loss, wrong attribution, daemon restart, observer removal delay/PID reuse
and trust retirement. Failed barrier activation must prevent payload mutation.
Prove unavailable readiness and exact recovery until all witnesses settle.
Run exact safety selectors and resource review; no live native policy or VM.
F05/F06 must establish the complete protocol independently on each target before
dispatch. This task has a 30–60 minute exception for the single recoverable
activation protocol. Update owners and close through the
[master](../Fixture-Execution-Plan.md).
