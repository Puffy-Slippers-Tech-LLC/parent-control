# 011 — Bounded repeated histories under guest load

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and route

Required tasks: 003, 004, 005, 008, 010.
Read the [master](../Reliability-Plan.md), relevant canonical session/accounting,
retained-work and kiosk helpers delivered above, and the
[shared support contract](../../tests/support/README.md).
Keep this engineering stress composition separate from the existing customer
long-routine and suspend/wake cases. It cannot close their rows.

Planned qualification (unimplemented): `check_e2e_repeated_reliability_history`.
Cases supply finite data/order/assertions; extend shared mechanics rather than
copying input, credential or cleanup code into this case.

## Three-cycle history and expected results

Keep two children, independent saved policy and recognizable retained work in
one attempt. Use the existing Riley/Jordan fixture identities: Riley is the
exercised child and Jordan the retained isolation control. Publicly prepare a
two-minute daily-only profile for Riley and four minutes for Jordan, with
observed zero initial grants and adequate starting balances. Run exactly three
Riley cycles: usable work → 20-second locked inactivity → normal return →
natural exhaustion → real kiosk approval of an additional 300 seconds → one
authorized retained return. Observe zero-time denial before each approval.

In cycle two only, after normal return and while the desktop is usable, obtain
one additional 60 seconds through the child overlay before proceeding to
natural exhaustion. This is the overlay binding; an exhausted locked desktop
cannot open that form. Preserve the resulting original grant deadline and
wait for its actual exhaustion before the kiosk approval. Every submission is
single-use with its own freshly verified recipient and independent result.
Compare both children's time, policy and original work before continuing;
Jordan's grant/daily arithmetic follows its own real activity. Never restore a
snapshot, clear usage or reset policy between cycles. No open-ended soak or
random retry.

Cycle two adds a guest-owned workload overlapping active countdown for at most
45 seconds: one CPU worker capped at 25% of one virtual CPU and one writer
creating a single file of at most 64 MiB in attempt-owned scratch. The owned
guest scope has a 128 MiB memory limit and at most four tasks. Admit it through
the maintained process/scope interface, collect its precise identity and
independently verify its resource limits. No host stress, global disk fill or
unbounded child allocation. Stop/reap only that owned workload.

Require deadline progress without extra time, usable authorized return, enforced
zero-time denial, unaffected other-child work and bounded resource lifetime.
Compare owned timers/signals, app/report children, namespace staging mounts and
unit state at equivalent quiescent checkpoints after every cycle. Retain the
first failed intermediate assertion; final recovery cannot turn an incomplete
history into a pass. Bound the whole history to 20 minutes without extending
any existing operation deadline.

## Validation and close-out

Run host composition, cancellation, resource admission and cleanup guards before
the complete three-cycle attempt on both targets. Missing reusable workload
prerequisites use baseline preparation; insert a bounded prerequisite if the
maintained resource interface is absent. Fix demonstrated leaks, races or
state/accounting defects and rerun the complete affected history after final
edits. Retain each intermediate result and complete cleanup, build as required
and register this qualification exactly once.
