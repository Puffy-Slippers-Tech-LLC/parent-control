# Test evidence and export infrastructure queue

The [master](Export-Execution-Plan.md) owns the sole next-task pointer. Remaining
rows bind the [proposed design](Export-Design.md). Host acceptance
means infrastructure checks only, including synthetic privileged/target metadata.
No product acceptance or live VM work belongs to this queue.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | E01 | [Audit history, producers and retirement paths](Export-Design.md#e01-source-and-history-audit) | Baseline | Verify historical fixes and map finite producer, consumer, retirement and controller-dependency inventories to delivery and regressions | Reviewed 2026-10-21: all 15 histories; producer/consumer, retirement and controller maps with reuse anchors and P01–P12 planned histories. Source cross-check findings resolved; 321 metadata/adapter checks passed ([report](../../output/test-runs/host/plans/643d1e71b404620c98e268576999c6fd3cf8a728c1c844f648f480b1ff2dfb3c/accepted-evidence.json)); links and plan check passed. Helpers finished; no temporary resources remain. |
| [ ] | E01a | [Design identity, capture and lifetime protocols](Export-Tasks/E01a-protocols.md) | E01 | Propose concrete versioned schemas, exact helper/reference interfaces, authenticated handoff, lock/budget/recovery and compatibility protocols | 45–60 min |
| [ ] | E01b | [Independently review and freeze delivery](Export-Tasks/E01b-freeze.md) | E01a | Freeze historical failure inventory, all producer/consumer dispositions, interfaces, schemas and independent design review | 45–60 min |
| [ ] | E02 | [Resolve stable evidence identities](Export-Tasks/E02-identities.md) | E01b | Exact task/check/attempt/target/input/member identities and verified references independent of physical report paths | 45–60 min |
| [ ] | E03 | [Capture evidence before rotation](Export-Tasks/E03-capture.md) | E02 | Bounded owner-authorized capture of finalized records during active executions with durable interruption recovery | 60–90 min provisional |
| [ ] | E04 | [Preserve referenced proof within budgets](Export-Tasks/E04-lifetime.md) | E03 | Separate working and accepted lifetimes, preflight capacity, safe publication/compaction and reference-aware retirement | 60–90 min provisional |
| [ ] | E05 | [Reuse exports and verified reads](Export-Tasks/E05-reuse.md) | E04 | Idempotent private exports, grouped publication, concurrent readers and verification reuse without stale trust | 30–60 min |
| [ ] | E05a | [Read retained proof during unrelated active runs](Export-Tasks/E05a-active-readers.md) | E05 | Selective authenticated journal inspection and exact archived-member recovery without adopting active mutable sources | 30–45 min |
| [ ] | E06 | [Capture runner results at terminal boundaries](Export-Tasks/E06-runners.md) | E05a | Aggregate/category/worker report capture before rotation, preserving exact inventories and failed attempts | 30–60 min |
| [ ] | E06a | [Capture qualification and E2E collector records](Export-Tasks/E06a-qualifications.md) | E06 | Standalone qualification, recovery-diagnostic and E2E collector handoffs use shared finalized-record capture with exact target/cleanup provenance | 45–60 min |
| [ ] | E07 | [Integrate ordinary-plan evidence consumers](Export-Tasks/E07-launchers.md) | E06a | Ordinary plans share structured capture/references through continuation, suspension, protected recovery and Git retry | 60–90 min provisional |
| [ ] | E07a | [Integrate repair and E2E launcher consumers](Export-Tasks/E07a-specialized.md) | E07 | Specialized repair/E2E consumers retain exact evidence through retries and continuation without changing acceptance policy | 45–60 min |
| [ ] | E08 | [Unify local Markdown reference checks](Export-Tasks/E08-markdown.md) | E02 | Shared bounded parsing, relative paths, reference-style links and fragment validation with code/example exclusions | 30–60 min |
| [ ] | E09 | [Generate and validate specific evidence links](Export-Tasks/E09-validation.md) | E07a, E08 | Reference creation and semantic checks across declared document consumers, including wrong-but-existing destinations | 45–60 min |
| [ ] | E10 | [Apply proportional checks at lifecycle boundaries](Export-Tasks/E10-gates.md) | E09 | Early scoped preflight and publication gates, strict quality failures, advisory trivialities and finite actionable diagnostics | 30–45 min |
| [ ] | E11 | [Inventory legacy references and recoverability](Export-Tasks/E11-inventory.md) | E10 | Deterministic read-only catalogue of tracked legacy references, exact retained matches, unavailable proof and protected consumers | 20–30 min |
| [ ] | E12 | [Migrate verified legacy destinations](Export-Tasks/E12-migration.md) | E11 | Guarded finite reference migration preserving claims, exact original proof, active checkpoints and unrelated work | 30–60 min |
| [ ] | E13 | [Make historical loss explicit and nonrecurring](Export-Tasks/E13-history.md) | E12 | Structured historical availability and repair guidance without invented proof, new passes or repeated unrelated acceptance | 30–45 min |
| [ ] | E14 | [Qualify the composed infrastructure](Export-Tasks/E14-composition.md) | E13 | Private end-to-end failure matrix, compatibility and resource review and all-consumer disposition using earlier safety coverage | 60–90 min provisional |
| [ ] | E14a | [Independently review final delivery](Export-Tasks/E14a-review.md) | E14 | Independent final source/evidence review against frozen history, interfaces, producer/consumer coverage and safety regressions | 45–60 min |

Estimates include reading, delivery, applicable regressions and cleanup; they do
not shorten safety acceptance or change session allowances. E01b must review all
ranges, including its own review and E14/E14a, and resolve every provisional
allocation (E03, E04, E07 and E14) before runtime work. The wider ranges cover
indivisible recovery histories; E01b must freeze concrete prerequisite allocations
for independent work under its protected-insertion contract. Split independently
deliverable mechanisms and producer/launcher families before their consumer under the
[shared prerequisite route](../Execution-Plans.md#execution-and-delegation);
do not weaken acceptance or shift product work into this queue.
