# 08 — Run the complete host UI selection

**Recommended model: GPT-5.6 Sol. Effort: high.** The work is a fixed verification
selection; escalate reasoning/model only if a new difficult diagnosis appears.

**Prerequisite:** [07](07-focused-unit-verification.md) passed on the current
implementation, and [shared preflight](README.md).
**Status:** Not started. **Next:** [09](09-child-static-runtime.md).

## Run

Keep implementation frozen. Run all twelve files, without `-x` or narrowed
selectors, and collect the final status. The marker explicitly retains only the
synthetic spectator case; its two live variants require an independently active
E2E attempt and stay outside this host-only run:

```sh
tools/run-ui-tests --timeout 1200s -q -m 'not live_e2e' \
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
