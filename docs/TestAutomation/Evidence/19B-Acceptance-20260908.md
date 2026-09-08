# Task 19B — third qualification and acceptance

**19B accepted.** Three consecutive public E2E-001/gdm-observation
qualifications passed with direct visual review and terminal cleanup. This is
`runner-smoke` qualification, not customer or release acceptance. The earlier
unreviewed runtime pass is excluded. No implementation or permission changed
in this slice; existing work was preserved.

## Third qualification

Build: `tools/run-tests artifacts build`, handle **91346**, exit 0, output
`/tmp/onpc-test-artifacts-nn_evrwf`.
Run: `tools/run-tests e2e --artifacts /tmp/onpc-test-artifacts-nn_evrwf --scenario E2E-001`,
handle **56706**, exit 0. The dispatcher first passed **521 isolated safety
tests and three subtests in 5.00 s**. No test failed or action was denied.
Inputs remained unchanged through terminal collection and cleanup.

- Invocation: `/tmp/onpc-e2e-evidence-cpqtxuwi`; post-close output passed the
  complete expected selection with no first failure.
- Case: `/tmp/onpc-e2e-evidence-p10iva3a`, run
  `scenario-ea8bdab4d37b491fa2cff0f0c9e28cef`.
- Terminal: `invocation-000003.json`; final scenario: `event-000029.json`.
- Raw worker: `/tmp/onpc-graphical-smoke-djjx7pzl`.
- Worker result: `/tmp/onpc-e2e-evidence-v84v8c86/worker-result.json`.

| Input | SHA-256 |
| --- | --- |
| Source | `5178cce037109eea0b4487ede1046b66fa268be373c27b7541a1d7e5b8b1677b` |
| Inventory | `15fd719181f41bfb6d12ac5f30f9a02fbd652626037856e02827f8361170fe39` |
| Package | `0b1328cd53aecf4c24f7e0aa2ce6129467105cb7196c0032b995d9bc3592e7ac` |
| Assets | `766737294c9c5c17eb63393521bfcc948891608314086c8637d7b19953e32586` |
| Baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Worker distribution | `970ba820f1a4e85ba8ea810d0e06ce11a88bcd306fe4424e15971330f06151b4` |

Comparison with [qualification 2](19B-Qualification-2-20260908.md) confirms
identical package, fixture digest, build configuration and tool identities.
Inventory, baseline and worker distribution also match. Source file count rose
from 502 to 503 with handoff documentation; staged assets include that changed
manifest. These changes do not invalidate qualifications 1 or 2.

## Review and cleanup

All nine observations share one actual boot identity. All seven recorded steps
and the visible, backend and other-user assertions passed. Structured
`serial-command.evidence` confirms an active local serial session, the actual
command marker and no unexpected user session. Six positive screen matches
scored 100%; the deliberate account-list match against the empty password
prompt scored zero. The final GDM match follows the serial-logout detail.

Direct review of `smoke-1.png`, `smoke-6.png` and `smoke-16.png` confirmed
initial GDM, the selected `[Parent user]` empty focused password prompt and
returned GDM, all 1024×768. Initial and returned captures are identical within
this attempt; exact digests remain in `matched-screens.evidence`. Captures
contain account labels and remain private. All 18 structured artifacts carry
`reviewed-secret-checked-v1`; collection passed registered-secret exclusion.
Raw authentication output was not exported. Video is disabled under the
established `NOVIDEO=1` secret-safe contract; no video review is claimed.

The guarded exporter created `/tmp/onpc-19b-q3-gdm.png`,
`/tmp/onpc-19b-q3-prompt.png` and `/tmp/onpc-19b-q3-return.png` with caller
ownership and mode 0600. After inspection, `tools/cleanup-screenshots`
confirmed all three removals. Private evidence remains retained.

Worker exit 0, callback closure, owned-process shutdown, baseline restoration,
host/source preservation and collection passed. Final scenario cleanup fields
are all true with lease phase `complete`. Fresh `tools/test-vm status` confirmed
off (`state=5`, `id=-1`). Every command exited; no recovery or owned operation
remains. A default-length diagnostic read truncated the final JSON; a bounded
65,536-byte read recovered the complete record without changing evidence.

Measured stages: preparation **367.055 s**, test **574.781 s**, cleanup
**68.392 s**; worker **37.401 s**. Stage totals exclude some finalization time.

## Acceptance audit

| Required boundary | Accepted evidence |
| --- | --- |
| Reusable GDM/login, console and screen helpers; stable regions, explicit clicks, bounded matches | `tests/integration/graphical_smoke/lib/onpc_gdm.pm`, `onpc_serial.pm`, reviewed needles and [helper qualification](19B-GDM-Matching-20260908.md). Initial deadline 90 seconds, subsequent matches 30 seconds; clock/animation regions excluded. |
| Fresh product-free boot, graphical recognition, harmless real serial command, graphical return and shutdown | Nine ordered observations and six reconciled matches in all three public runs; [recorder implementation](19B-Ordered-Recorder-20260908.md). |
| Helper usage, deadlines, failure artifacts and exact public invocation | [Public contract](../../../tests/e2e/README.md#maintain-declarations) and [GDM helper contract](../../../tests/e2e/README.md#gdm-readiness-and-graphical-return). |
| Three consecutive complete, reviewed qualifications | [Qualification 1](19B-Storage-Qualification-20260908.md), [qualification 2](19B-Qualification-2-20260908.md), and qualification 3 above. Each has isolated safety prerequisites and terminal cleanup. |
| Screens, serial, secret exclusion and cleanup | Direct private review and structured evidence above and in both earlier records. Video remains deliberately disabled, not omitted evidence claimed as reviewed. |
| Focused regressions and common checks | Qualification 1 retains 90 focused passes and final-code `make check`: 3,060 unit/contracts, 17 components, syntax and stage traceability. No subsequent code/tool change invalidates it. Staged/unstaged whitespace and acceptance-document link checks passed this slice. |

Historical failures and their fixes remain in the linked evidence; none is
reclassified as passing. The prior unreviewed runtime run remains outside the
three-qualification count. No product requirement is newly marked covered.

## Next selection

Task 20 is now the earliest ready unchecked entry because its 19B dependency
is accepted. Begin with E2E-002's clean-install/reboot/readiness contract and
assigned E2E-028 variant audit; keep their customer operations and declared
faults separate. Preserve Task 15A's later saved work. No earlier entry is
bypassed. The [all-task VM clearance](../Implementation-Workflow.md#vm-availability-for-all-tasks)
remains effective; no new coordination confirmation is due.

Settings: **`gpt-6-astra` / `high`**, pinned by the slice launcher. Keep both for
the first product installation journey and its real reboot/readiness boundary.
Remaining Task 19B: **0 sessions / 0 minutes**. Fresh artifacts are required
after documentation edits for the next package-bearing attempt; do not rerun
accepted qualifications solely because of this handoff.
