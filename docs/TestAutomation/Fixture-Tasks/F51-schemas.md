# F51 — Freeze fixture schemas and transition contracts

Acceptance: review
Requires: F01

## Scope and deliverables

Read F01's complete placement/consumer inventory and the
[target design](../Fixture-Design.md). Freeze canonical manifest, content/source/
toolchain/ABI keys, catalogue/build-slot states, durable pin and authenticated
host/root request fields, guest receipt generations, original-schema recovery
sidecar and target qualification-receipt fields. Bind the actual checkout/caller,
host run, nonce, pin, bundle, subset and privileged attempt; never trust supplied
UIDs or cache roots. Keep normal retention and fixture-cache ownership separate.

Specify catalogue/producer/version/VM lock order and pre-build oldest eligible
retirement, including an unfinished slot at the six-build default. No byte quota
or quota-specific setup prerequisite is required. Specify supported native rule
grammar/order and the chosen finite per-operation acknowledgement protocol,
including unique private probe executables, log/daemon bindings, safe observer
retirement and refusing an unsupported backend. F31/F32/F50 implement these
separate mechanics. F33 imports the entire original movable inventory; F11/F12
exclude retained source copies from capture. Seven clean-schema checks plus a
target admission receipt precede each ordinary cutover.

## Validation and close-out

Walk successful, failed, interrupted and lost-reply transitions against complete
shared source. Ensure each schema field has an authority and recovery owner;
each externally visible name remains planned until registered. Resolve ambiguity
without changing safety requirements or product assertions. Run links and plan
structure checks. No VM, fixture build or implementation is part of this task.
F52 independently reviews the frozen result; close through the
[master](../Fixture-Execution-Plan.md).
