# E05a — Read retained proof during unrelated active runs

Acceptance: host
Requires: E05

## Purpose and delivery

Deliver selective archived-proof resolution from
[lifetime and reuse](../Export-Design.md#lifetime-capacity-and-reuse), following
the [master](../Export-Execution-Plan.md). Read complete
`evidence_bundle.Selection.catalogue`, `load`, `record`, `reference_present`,
archive verification, helper authentication and retention inspection locking.

Inspect only the authenticated journals/dependencies actually required by an
explicit finished archive/reference request. Permit old retained proof reads
while an unrelated producer on the same target owns its current execution
journal. Preserve provenance/catalogue completeness for the selected sources,
live-path conflict checks, deterministic lock order and writer exclusion. Never
skip an authority or integrity failure that the selected request depends on,
read/adopt live mutable active payloads, stop the producer or bypass owner guards.
Keep exact missing, denied, corrupt, busy and foreign-active outcomes distinct.

## Validation and close-out

Reproduce the developer's report in private host fixtures: two vanished earlier
report paths, two exact retained members and an unrelated active synthetic
producer for the same target. Resolve both members during that producer's life;
assert unchanged live journals/payloads and no source rotation/checkpoint writes.
Use the design's [authenticated selection history](../Export-Design.md#required-regression-histories):
the public helper's `bundle-plan` dispatch with a synthetic validated plan,
target, retained bundle and two repeated `--reference` inputs must exercise real
`Selection.catalogue()`/`load()` and inspection locking. Record the pre-fix
eager-catalogue refusal in private fixtures, or verify an earlier delivered fix
and its exact regression without reintroducing the defect. Do not mock selection
or locking or accept only successful `inspect()`/`bundle-read` calls; those already
avoid unrelated target journals. Assert the unrelated journal is not inspected,
not merely that its payload bytes remain unchanged. E07 owns ordinary-plan caller
integration and E14 the composed sequence.
Cover a missing member, wrong target/attempt, corrupt archive, denied reader,
actual active-source request and concurrent reader/writer boundaries. Extend
bundle/artifact/retention safety tests, run scoped host validation and update the
artifact-access owner. No VM or product acceptance; use the master's close-out.
