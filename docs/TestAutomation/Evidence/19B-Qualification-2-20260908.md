# Task 19B — public qualification 2

**E2E-001/gdm-observation passed its second consecutive complete, visually
reviewed public qualification.** This is `runner-smoke`; Task 19B remains
unchecked until qualification 3 and the acceptance audit pass. No implementation
or policy changed in this slice. Existing edits were preserved.

## Execution and evidence

Build: `tools/run-tests artifacts build`, handle **86081**, exit 0;
output `/tmp/onpc-test-artifacts-s_uba7s3`.
Run: `tools/run-tests e2e --artifacts /tmp/onpc-test-artifacts-s_uba7s3 --scenario E2E-001`,
handle **79356**, exit 0. The dispatcher first passed **521 isolated cleanup-safety
tests and three subtests in 5.01 s**. No attempt failed or was denied this slice.
Checkout inputs remained unchanged through terminal collection and cleanup.

- Invocation: `/tmp/onpc-e2e-evidence-a9qpzs5s`; post-close output passed the
  complete expected selection with no first failure.
- Case: `/tmp/onpc-e2e-evidence-3e12nq7z`, run
  `scenario-36d47a5fc7cb4228bc691e27af2e0090`.
- Terminal evidence: `invocation-000003.json`; scenario: `event-000029.json`.
- Raw worker evidence: `/tmp/onpc-graphical-smoke-nttp215u`.
- Worker result: `/tmp/onpc-e2e-evidence-1imjt18w/worker-result.json`.

| Input | SHA-256 |
| --- | --- |
| Source | `1842b994c84bafa928e79941becc4af3ae71c5420f20090384aa133ff404a653` |
| Inventory | `15fd719181f41bfb6d12ac5f30f9a02fbd652626037856e02827f8361170fe39` |
| Package | `0b1328cd53aecf4c24f7e0aa2ce6129467105cb7196c0032b995d9bc3592e7ac` |
| Assets | `58af79df7fc847d7d8506c0a0e1b17dcd3a7c96b08e5e594b16b615b02f98906` |
| Baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Worker distribution | `970ba820f1a4e85ba8ea810d0e06ce11a88bcd306fe4424e15971330f06151b4` |

Compared with [qualification 1](19B-Storage-Qualification-20260908.md), package,
fixture digest (`1b2aee47186c5057c581a6777c64f1ed7b40e960f47cc4e676e5628753074365`),
inventory, baseline and worker distribution are unchanged. Both build manifests
have identical tool/build identities; the source digest and file count reflect
the preceding documentation handoff (501 to 502 files). The staged asset identity
includes that changed manifest (`tests/e2e/provenance.py:VerifiedInputs`). These
documentation/provenance changes do not invalidate qualification 1.

## Review and cleanup

All nine ordered observations share one actual boot identity. Structured
`serial-command.evidence` confirms an active local serial session, the actual
command marker and no unexpected user session. Six screen matches passed at
100%; the deliberate account-list match against the empty password prompt
correctly returned zero similarity. Raw `testresults/result-smoke.json` puts
the final GDM match after the serial-logout detail.

Direct review of `smoke-1.png`, `smoke-6.png` and `smoke-16.png` confirmed the
initial GDM list, selected `[Parent user]` empty focused password prompt and
returned GDM list, all 1024×768. Structured match evidence retains exact image
digests. Initial and returned images are identical within this attempt; the
clock differs from qualification 1 outside the stable matched regions.
Captures contain account labels and remain private. Structured artifacts have
`reviewed-secret-checked-v1` redaction; raw authentication output was not exported.
Video remains disabled by the established `NOVIDEO=1` contract; no video review
is claimed, and `video_time.vtt` is timing metadata only.

The unchanged guarded exporter created `/tmp/onpc-19b-q2-gdm.png`,
`/tmp/onpc-19b-q2-prompt.png` and `/tmp/onpc-19b-q2-return.png` with caller
ownership and mode 0600. After inspection, `tools/cleanup-screenshots` confirmed
all three removals. Private raw evidence is intentionally retained.

Worker exit 0, callback closure, owned-process shutdown, baseline restoration,
host/source preservation and collection all passed; terminal lease phase is
`complete`. Fresh `tools/test-vm status` confirmed off (`state=5`, `id=-1`).
All session commands exited; no owned operation or recovery remains.

| Experiment | Preparation | Test | Cleanup | Worker | Result |
| --- | --- | --- | --- | --- | --- |
| Public qualification 2 | 365.053 s | 578.950 s | 67.350 s | 38.595 s | Passed, visually reviewed, terminal cleanup complete |

The complete invocation took roughly 23 minutes; stage totals omit some
finalization. Prior `make check` remains applicable because this slice changed
only evidence/handoffs; its result is retained in qualification 1. Scoped
whitespace and local-link checks passed after these edits.

## Next boundary

Build fresh inputs after this handoff, run qualification 3 through the same
public selection, review its evidence and cleanup, then finish the acceptance
audit. Keep both reviewed qualifications unless relevant behavior/tool/baseline
changes invalidate them. The earlier unreviewed runtime pass still does not count.

19B remains earliest ready; no earlier entry was bypassed. Task 20 follows its
acceptance, with 15A's saved work preserved. The operator's
[all-task VM clearance](../Implementation-Workflow.md#vm-availability-for-all-tasks)
remains effective. Settings: **`gpt-6-astra` / `high`**, pinned by the slice launcher.
Remaining 19B: **1–2 sessions / 30–55 minutes**, assuming one roughly 23-minute
run plus build, visual review and audit, with no new failure or relevant change.
