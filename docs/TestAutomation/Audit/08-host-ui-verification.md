# 08 — Run the complete host UI selection

**Recommended model: GPT-5.6 Sol. Effort: high.** The work is a fixed verification
selection; escalate reasoning/model only if a new difficult diagnosis appears.

**Prerequisite:** [07](07-focused-unit-verification.md) passed on the current
implementation, and [shared preflight](README.md).
**Status:** Complete; cleanup and the complete 136-case selection passed.
**Next:** [09](09-child-static-runtime.md).

## Run

Keep implementation frozen. Run all twelve files, without `-x` or narrowed
selectors, and collect the final status. The marker explicitly retains only the
synthetic spectator case; its two live variants require an independently active
E2E attempt and stay outside this host-only run:

```sh
tools/run-ui-tests --timeout 5400s -q -m 'not live_e2e' \
  'tests/ui/test_about_release.py' \
  'tests/ui/test_automation_identity.py' \
  'tests/ui/test_control_overflow.py' \
  'tests/ui/test_e2e_accessible_adapter.py' \
  'tests/ui/test_e2e_watch.py' \
  'tests/ui/test_error_feedback.py' \
  'tests/ui/test_parent_feedback.py' \
  'tests/ui/test_preview_smoke.py' \
  'tests/ui/test_request_form_component.py' \
  'tests/ui/test_request_layout.py' \
  'tests/ui/test_screen_preview.py' \
  'tests/ui/test_fixture_gui.py'
```

Allow the launcher to run its mandatory cleanup prerequisite. Keep the session
identifier and normal runner artifact locations until its actual final result
is read. Do not start another suite while it runs, and do not replace lost output
with collection counts. Report a timeout as incomplete, not as a pass. The two
explicitly excluded live spectator cases are expected deselections, not
unexpected skips.

## Acceptance and failure handling

Require a passing cleanup gate and final selected-suite result. Investigate every
failure, unexpected skip or deselection; preserve the complete twelve-file scope.
Specifically retain both Parent overflow scales, independent legend content
visibility, shared child/kiosk behavior, and all four fixture variants with their
independent instances, edit/typing, submit/readback, moves and secondary closure.
Provider refusal checks must be reported as refusal coverage, not live provider
qualification. Cosmetic differences cannot gate acceptance.

If a test exposes changed product behavior, preserve expected/actual evidence
and seek developer direction before accepting it or changing expectations.
Mechanical fixes must preserve behavior checks. Any code/test fix reopens its
owning task, reruns affected units, then requires this full twelve-file command
again on the new frozen code. A narrow successful retry is not final completion.

Complete with exact final counts, command, artifacts and any explicit limits.
No installed App Limits, Snap confinement, desktop-login or customer E2E claim
follows from this host run.

## Progress record

The first complete command, using the original 1,200-second budget, passed its
mandatory cleanup gate with **1,476 tests and 3 subtests in 83.64s**, then
reached six failures before the launcher exited 124 at its 1,200-second timeout
without a final pytest summary. The retained Shell artifact is
`/tmp/onpc-e2e-search-uica_ft_`. A verbose six-node diagnostic rerun reproduced:

- the expected Shell provider refusal followed by an unrelated unavailable
  nested-Shell screenshot method;
- four host-only Parent adapter cases refusing because their synthetic session
  did not qualify its known-absent prompt providers; and
- kiosk-hidden feedback controls retaining public IDs in the accessibility tree.

The mechanical corrections preserve the checks: provider-refusal coverage now
stops its owned Shell without requiring screenshot evidence, the host Parent
adapters declare ID-complete absent prompt-provider contracts, and controls that
the kiosk does not offer publish no kiosk automation IDs. Affected units passed:

```sh
tools/run-unit-tests -q 'tests/unit/test_accessible_e2e_ui.py' 'tests/unit/test_automation_ids.py' 'tests/unit/test_child_preview.py' 'tests/unit/test_feedback_collection.py'
```

Result: **416 passed in 1.87s**.

The first targeted retry selected all six failed nodes. Its cleanup gate passed
**1,476 tests and 3 subtests in 81.10s**. The Shell refusal, both empty-Parent
scales and the full Parent 1.0-scale case passed before the 600-second launcher
timeout; the full Parent 1.25-scale case did not finish and the kiosk case did
not run. The two outstanding nodes were then run together:

```sh
tools/run-ui-tests --timeout 900s -q \
  'tests/ui/test_e2e_accessible_adapter.py::test_parent_functional_adapter_at_display_scales[1.25]' \
  'tests/ui/test_error_feedback.py::test_request_error_review_restrictions_and_submission[kiosk]'
```

Its cleanup gate passed **1,476 tests and 3 subtests in 83.17s**; the selected
result was **2 passed in 487.01s**. Thus every originally exposed failure has a
passing targeted result, but the full twelve-file selection has not passed and
Task 08 remains incomplete. The next session must rerun the complete scope and
retain its actual final status.

The next complete attempt used a 3,600-second budget. Its cleanup gate passed
**1,476 tests and 3 subtests in 84.77s**. Collection separately confirmed
**136 selected and 2 expected `live_e2e` deselections**. Pytest emitted 130 of
the 136 progress markers and five failures before the launcher again exited 124
without a final summary. The exact failure positions in the unchanged
collection order were:

- `test_feedback_submission_outcomes[409]`;
- both `denied` variants of `test_outcomes_are_actionable_and_redacted`; and
- both variants of
  `test_single_flight_ignores_escape_while_authentication_is_active`.

A verbose exact-node diagnostic passed the `409` node unchanged and reproduced
the other four failures. Its cleanup gate passed **1,476 tests and 3 subtests in
82.48s**; selected result: **1 passed, 4 failed in 135.68s**. Failure evidence is
under `/var/tmp/pytest-of-edgar/pytest-1307` and these preview directories:
`/var/tmp/onpc-ui-preview-onq6856p`,
`/var/tmp/onpc-ui-preview-b5m4ia5l`,
`/var/tmp/onpc-ui-preview-wm2ylji7`, and
`/var/tmp/onpc-ui-preview-dtf99o8z`.

The four reproducible failures were mechanical fixture/test drift. Denial is an
inline `kiosk-request-status` message with choices enabled for retry, as required
by ONPC-CORE-REQUEST-013, rather than a result-page title. The synthetic broker
now holds its slow request reply until the real Escape handler records the
in-flight decision, instead of racing semantic reveal/input against a
1.5-second timer. Its correlation cookie is also a schema-valid fixed UUID.
The assertions still require public-ID lookup, the exact denial copy, retry
availability, one request, an unhandled in-flight Escape, a later public result,
and no premature logout or overlay close.

The exact five-node validation command was:

```sh
tools/run-ui-tests --timeout 900s -v --tb=short \
  'tests/ui/test_parent_feedback.py::test_feedback_submission_outcomes[409]' \
  'tests/ui/test_request_form_component.py::test_outcomes_are_actionable_and_redacted[False-denied-Request denied]' \
  'tests/ui/test_request_form_component.py::test_outcomes_are_actionable_and_redacted[True-denied-Request denied]' \
  'tests/ui/test_request_form_component.py::test_single_flight_ignores_escape_while_authentication_is_active[kiosk]' \
  'tests/ui/test_request_form_component.py::test_single_flight_ignores_escape_while_authentication_is_active[child-overlay]'
```

Its cleanup gate passed **1,476 tests and 3 subtests in 80.53s**; the selected
result was **5 passed in 91.43s**. Retained evidence is
`/var/tmp/pytest-of-edgar/pytest-1309` and preview directories
`/var/tmp/onpc-ui-preview-vdqcyszm`,
`/var/tmp/onpc-ui-preview-nfj1zlix`,
`/var/tmp/onpc-ui-preview-adh5bd4o`,
`/var/tmp/onpc-ui-preview-851trw27`, and
`/var/tmp/onpc-ui-preview-fawf18yi`.

The implementation changed after the incomplete full attempt, so Task 08 still
requires the exact complete command above. Its bounded budget is now 5,400
seconds: the 3,600-second attempt reached 130 of 136 markers, and the additional
50 percent covers the remaining cases and host variability without narrowing
scope. Do not infer a pass from either timeout, and do not begin Task 09 until
the complete selection has an actual passing final summary.

The required final attempt ran the exact complete command above on the frozen
implementation. Its mandatory cleanup gate passed **1,476 tests and 3 subtests
in 82.35s**. The selected suite then completed with **136 passed and 2 expected
`live_e2e` deselections in 3,522.70s (58:42)**. There were no failures,
unexpected skips or unexpected deselections. The normal pytest evidence root is
`/var/tmp/pytest-of-edgar/pytest-1311`; the retained passing Shell render
artifact is `/tmp/onpc-e2e-search-_iui6hbp`. This closes Task 08's host-only
scope without qualifying an installed provider or customer E2E journey.
