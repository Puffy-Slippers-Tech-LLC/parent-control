# F23 — Integrate Fedora transfer qualification

Acceptance: installed
Targets: onpc-Fedora44
Requires: F22

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate standalone `runner --qualify-transfer` through
`Qualification.execute`, `check_graphical_smoke` and `AssetTransfer.provision`.
Read the complete bootstrap/asset chain. Keep preboot work limited to transport
prerequisites; reusable payload moves through shared SSH only after readiness.
An installed app snapshot cannot substitute for this product-free envelope.
Keep serial aliases gated until their own tasks.

Reuse the execution-owned immutable input and single SSH provisioner on clean
captures. Bind readiness to the actual restored/rebound boot and attempt.
Enable only this qualified target/branch; other unmigrated branches must refuse.
Preserve enforcing SELinux, exact native admissions and labels. Renew affected
Ubuntu checks after shared corrections.

## Acceptance and cleanup

Run exact affected host composition/provenance/ownership safety selections.
Register/list the planned `check_fixture_transfer` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_transfer
```

Exercise the real standalone transfer preparation and independent harmless
native use. Prove product absence, no reusable preboot upload and fail-closed
uncertain transfer recovery without replay. Stop before graphical input.
Prove selected manifest bytes independently, positive runtime use, fresh readiness,
missing/incompatible refusal before input and no version switch under host edits.
No complete fixture collection is copied into results; preserve scenario mutations.
Finish watched owned restoration and credential/staging/input/transport cleanup.
Update delivered runner/support owners and close through the
[master](../Fixture-Execution-Plan.md). This supplies no customer/E2E acceptance.
