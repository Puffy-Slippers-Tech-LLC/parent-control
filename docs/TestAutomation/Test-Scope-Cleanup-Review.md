# Test scope cleanup review

Date: 2026-10-22. Independent reviewer: `review_test_reduction` subagent.
Scope: the test reduction following the [test scope mandate](../Mandates/Test-Scope-Mandate.md).

## Independent source review

The reviewer reported no findings. Removed suites target watcher and fixture
widgets, the preview screen picker, recursive test-file architecture checks,
trivial helper behavior and an observation-only recording benchmark.

The review confirmed that:

- Product assertions and installed customer journeys remain intact.
- Screen-value validation remains in `tests/unit/test_preview_screen.py`.
- Direct capture/reconnect, input isolation, credential masking, recording
  integrity, evidence publication and owned cleanup coverage remain.
- The recording integration checks retain their compositor and encoder without
  exercising viewer UI controls.
- Scheduler groups and resource classifications remain aligned, and active
  sources/documents have no stale references to the removed tests or probes.

## Validation and limits

No tests were added for this cleanup. Document links and diff whitespace checks
passed, and the generated inventory was refreshed.

The reviewer ran existing focused checks in an isolated disk-backed checkout.
The first run recorded 354 passes before safe shutdown, with two reported
failures/errors: a stale scheduler branch expectation after removal of the
screen bucket, and an evidence-capture fixture rejecting a producer journal
outside shared checkout storage. The scheduler expectation was corrected to
require the ready component job to fill the newly free branch promptly.
The evidence-capture fixture issue is outside this test reduction; its guard
and assertions were preserved.

Initial report:
`/Data/Code/PST/parent-control-test-scope-validation-20261022/output/test-runs/host/reports/20261022T205539Z-b373705b/report.md`.
After correcting the scheduler expectation, only that existing check was rerun:
both parameter variants passed, with exit 0 and completed owned cleanup.
Focused report:
`/Data/Code/PST/parent-control-test-scope-validation-20261022/output/test-runs/host/reports/20261022T205907Z-5f2bc193/report.md`.
This review does not claim a complete-suite pass or new installed acceptance.
