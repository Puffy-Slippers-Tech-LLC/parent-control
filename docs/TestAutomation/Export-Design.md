# Test evidence and export design

Use this design only for an explicitly requested evidence export or archival
inspection. Routine test runs, task completion, preparation and repair keep
their ordinary results and diagnostics without automatic proof publication.
Completed tasks stay complete when reports rotate; follow the shared
[completion policy](../Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery).

For the requested export, preserve exact selected evidence. Finalize a finite set
of records, copy it through the existing verified bundle writer, record the
receipt with its owner, then allow the original to retire. Runtime contracts in
the [test guide](../../tests/README.md#aggregate-output-retention) and
[storage mandate](../Mandates/Test-Storage-Mandate.md) remain authoritative.

## Stable and specific references

Evidence identifies the exact check, attempt, target, inputs, source bytes,
result and required files. Retries and changed inputs have distinct identities;
identical bytes from different checks do not establish the same claim.

Generate links to exact records and members. A present path, latest-run link or
generic accepted locator alone is insufficient proof. Preserve original
provenance when storage moves, and verify the requested context before returning
archived evidence. Paths and document links grant no access or deletion authority.

## Capture and publication

Only the authenticated live owner may select closed files. Bind the selection to
its checkout, run, attempt, target, original identities and digests. A sealed
subset is independently finished; its parent may still be active. General
readers continue to refuse mutable active allocations.

Keep capture intent and receipts in the existing owner journal:

| State | Required behavior |
| --- | --- |
| Pending | Keep the required original while sealing or copying is incomplete. Recover the same recorded stage. |
| Published | Verify the committed destination, complete payload, receipt and locator. Keep the original until its owner acknowledges that exact copy. |
| Acknowledged | The source owner verifies the matching attempt, member closure and destination. Existing cleanup may release only the recorded source identities. |

Reuse existing publication and recovery transactions. Lost replies retry the
same operation. Failed copies, stale acknowledgements, changed files and capacity
refusals preserve the original and prior proof. Before deletion, hold the owning
locks and revalidate the replacement; an old receipt alone cannot authorize it.

Capture the authoritative terminal result after required collector and outer
cleanup, including late failure, command and recording records. Partial
diagnostics may retain failed or pending cleanup, but cannot satisfy a passing
check. Later recovery is a separate linked record; preserve the original failure.
Exclude credentials and disposable scratch.

Keep the existing activity, owner, lease and writer lock order. Seal under the
source owner, publish under the destination owner, then acknowledge under the
source owner. Do not acquire a destination owner while holding a source writer.
Audit the full deletion set before removing anything and retain exact remaining
identities after partial failure. Unknown, foreign or replaced resources refuse.

## Lifetime, capacity and reuse

Disposable reports and exports keep normal rotation. Required working and
accepted proof lives in its owner's bounded cumulative publication, independently
of unrelated runs. Keep required source bytes until verified copying and
acknowledgement; keep required destination bytes until explicit release or
verified replacement. Completing work does not release proof still in use.

Reuse the existing limits: three retained generations and 4 GiB allocated blocks
per journal; 60,000 files/logical members, a 64-MiB manifest, depth 32 and 256
explicit selections per publication operation. The selection limit is not a
lifetime record quota. Charge seals to their parent and account for simultaneous
source, seal, staging, committed, control and recovery copies. Bundles have no
separate byte ceiling; journal limits still apply.

Publish one complete cumulative replacement per generation. Carry required
members and omit only explicitly released, unreferenced material. Preserve each
logical origin when bytes deduplicate. Never mutate archives in place or share
writable hardlinks. If old plus new cannot fit, preserve current proof and report
usage, limits and a supported release or recovery action.

For identical exports, verify the authenticated selection, provenance and saved
bytes under the publication lock, then reuse the existing receipt without
allocating another session. Concurrent requests serialize this decision. Publish
related files atomically. Verify an archive once per pinned read scope and
invalidate that trust on mutation or scope exit.

Use existing journals, storage and bundle publication. No global consumer
database, reference-count graph, segmented writer or persistent verification
cache is needed. Recording, screenshot and scratch lifetimes retain their own
contracts. Local storage and Git links do not provide an external backup.

## Canonical identities and wire records

Use the existing versioned bundle format and strict readers. Canonical metadata
uses `evidence_bundle.encoded` JSON and lowercase SHA-256 digests; file digests
cover exact bytes. Reject unknown schemas or fields, duplicate identities,
conflicting closures, unsafe paths and invalid numeric types.

A logical record binds repository, workflow, owner, run, check, attempt, target,
input and source identities. Its closure binds status, completeness, members,
dependencies and cleanup. Members preserve original paths, allocation identities,
roles, lengths and digests. Verify the finite dependency closure before accepting
a result. A partial or diagnostic record never becomes a pass through archival.

Schema-2 manifests retain logical records and exact member-to-payload mappings
alongside existing file provenance. Every logical member needs one mapping;
orphan mappings and payloads refuse. Shared bytes retain all logical origins and
count toward existing metadata limits. Receipts bind the complete manifest.
Versioned locators select exact archived records; a locator cannot override their
contents or supply a missing member.

The optional `directories` manifest field proves complete directory selections.
It is a nonempty list of at most 60,000 unique objects, sorted by `path`, each
with exactly `path` and `sha256`. Each path selects a complete nonempty tree
within one original allocation. Its digest covers all descendant file entries in
original-path order: canonical JSON excluding the physical `member` field,
followed by one newline per entry. Capture computes it from the live walk;
verification recomputes it from the complete archive inventory. Cumulative
publication retains that closure unchanged.

Removed members, cross-allocation ancestors, empty inventories, type conflicts
and conflicting selections refuse. Older files-only manifests remain readable,
but matching descendants cannot prove a complete original directory. Strict
reader compatibility must be established before publishing extended metadata.

## Selective authenticated archived reads

Authenticate the caller and declared targets, then inspect explicitly selected
finished bundles before looking for live originals. An absent original with an
exact archived match does not require inspecting unrelated active journals.
When an original exists, retain its normal identity and ownership checks; an
archive cannot hide a changed or active source.

Revalidate absence and pinned archive identities before returning. Keep missing,
denied, corrupt, wrong-context and active-owner outcomes distinct. Discovery is
read-only and performs no rotation or writes to workflow state.

## Proportional validation

| Condition | Behavior |
| --- | --- |
| Wrong identity, corrupt bytes, unsafe ownership, untrusted publication or conflicting records | Block the affected operation and preserve evidence. |
| Missing member selected by the explicit archive operation | Resolve the exact member or fail that archive operation; completed task status is unchanged. |
| Newly authored evidence or required instruction reference is broken or ambiguous | Block its publication with document, line and identity details. |
| Equivalent spelling or harmless formatting with an unchanged claim and verified identity | Normalize or warn. |
| Unchanged unavailable history with no active dependency | Record nonpassing unavailability once and give an advisory. |
| Broken optional presentation link | Give a scoped advisory. |
| Access denied, corruption or active/foreign ownership | Preserve the distinct refusal; do not relabel it as expiry or retry denied authentication. |

Required and optional roles come from the owning contract and structured
declaration. Bind advisories to the exact claim and role revision; changed claims
or roles invalidate them. Integrity, authority and required-evidence failures
take precedence over presentation advisories.

Separate offline syntax checks from evidence materialization. Validate only the
selected operation's required closure and revalidate at the mutation boundary.
Avoid repeated archive scans when inputs have not changed. Diagnostics identify
the affected consumer, expected and actual identity, and a supported recovery
route without exposing secrets.

## Compatibility and migration

Retain supported readers and helper interfaces. Inventory a finite set of tracked
references and registered catalogues with the shared Markdown parser. Classify
exact live or archived proof, ambiguous context, unavailable history, refusals,
examples and operational paths separately. A plausible filename or nearby prose
cannot supply missing context.

Preview destination-only repairs against exact document bytes and proof digests.
Revalidate before each atomic document write. After interruption, verified applied
destinations are no-ops, unchanged pending destinations can resume, and conflicts
remain pending. Preserve claims and completion state; changes to protected claims
require their owner's existing authorization and recovery route.

Missing historical proof, unknown context and access refusals remain nonpassing
until their prerequisites are resolved. Migration creates no new test verdict or
product acceptance.

<a id="required-regression-histories"></a>

## Verification boundaries

Shared infrastructure coverage must establish exact archived resolution after
more than three rotations, preservation on failed capture/stale acknowledgement,
and normal rotation of disposable output. Resolve multiple archived reports
without touching an unrelated active producer. Keep missing, denied, corrupt
and wrong-context outcomes distinct.

When a retained-decision dependency changes, stop at the supported boundary and
resume with fresh code while preserving inputs, responses, counters, ownership
and accepted results. Interruption, capacity refusal, concurrent reuse and
partial deletion must preserve provenance, bounded storage and foreign resources.
Use real shared code with private stores and simulated authentication under the
[test scope mandate](../Mandates/Test-Scope-Mandate.md); product installation,
VM operation and historical acceptance reruns are unnecessary.
