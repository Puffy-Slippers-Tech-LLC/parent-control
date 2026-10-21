# F04 — Retain six fixture builds and clean oldest eligible inputs

Acceptance: host
Requires: F14

## Purpose and scope

Deliver the [cache retention policy](../Fixture-Design.md#bounded-cache-and-retention):
six occupied build slots globally, including staging/recovery, and at most three
completed versions per declared profile/target key. Enable public cache use only
after count, automatic retirement and ownership gates pass.

## Read and implement

Read the producer/publication/pin authority and shared storage/retention owners.
Implement pre-build slot admission, automatic oldest eligible retirement and
identity-bound interrupted deletion recovery. Oldest means durable publication
sequence, then bundle ID; hits do not reorder it. Inspect/prune uses the same
authority and never a filesystem sweep. Preserve protected inputs and refuse
admission when pins or unresolved identities prevent the necessary retirement.

Follow the [working-set contract](../Fixture-Design.md#initial-working-set-and-producer-reservation).
Six slots hold three versions for each target while idle. A full-cache miss
retires an eligible version before reserving the producer, leaving five
completed builds plus one producer; never allocate a seventh. Integrate F29's
descendant lifetime, including failed/staging scratch until exact cleanup.
Validate a configurable global integer from 1 through 9 and a positive per-key
limit no greater than it. Lower limits automatically retire oldest eligible
builds or refuse when protected inputs prevent compliance. Report occupied slots,
completed counts, allocated bytes, pins and pending/retirement reasons. Bytes
are diagnostic; there is no byte quota or quota-specific setup prerequisite.
Attempt inputs reference pins/manifests rather than full bundle copies; register
necessary subset-transfer scratch and remove it with its consumer.

## Finite validation and cleanup

Use tiny count limits and private allocations for fourth-per-key/seventh-global
requests, automatic oldest selection, old ABI keys, hits without growth, failed
and staging slot accounting, all-pinned refusal, invalid/tighter limits and
disk-full failure preserving committed inputs. Cover consumer/retirement races,
owner crash, interrupted deletion and unknown replacement preservation. Verify
evicted identities never resolve to different bytes and repeated failures cannot
accumulate extra build generations.

Exercise all six current-target versions at idle, retirement before a replacement
producer starts and both pinned target readers during production. Reuse F14's
active-session and authenticated-caller checks. Confirm subset selection creates
no additional cache key/version or full result-tree fixture copy. Run isolated
safety regressions before protected pruning. Review resource inventories, finish
only recorded private cleanup, update delivered storage/retention/help owners
and close through the [master](../Fixture-Execution-Plan.md).
