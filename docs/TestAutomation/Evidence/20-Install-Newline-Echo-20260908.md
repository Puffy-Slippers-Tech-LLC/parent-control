# Task 20: separate character echo from newline echo

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
Existing staged and unrelated changes were preserved. This slice changed the
installation observation, fixed prompt diagnostics, their two behavioral test
modules, and task evidence/handoffs. Test-tool activation is `none`, on next
invocation; no setup or product migration is involved.

## Audit and implementation

The earlier combined ECHO/ECHONL refusal does **not** establish character echo
or a pre-prompt wait. Upstream sudo-rs 0.2.13's
[password reader](https://github.com/trifectatechfoundation/sudo-rs/blob/v0.2.13/src/pam/rpassword.rs)
disables ECHO, enables ECHONL, disables canonical mode, writes the prompt, then
polls for password input. Its
[PAM conversation](https://github.com/trifectatechfoundation/sudo-rs/blob/v0.2.13/src/pam/converse.rs)
wraps the supplied custom prompt together with the PAM message. These are
concrete alternatives to the earlier service/policy-wait interpretation.
Read-only host inspection found sudo-rs `0.2.13-0ubuntu1.2` selected via
`/usr/lib/cargo/bin/sudo`, alongside sudo `1.9.17p2-1ubuntu3`; this does not prove
the guest's exact package version or distribution patches.

`SUDO_PASSWORD` now appends one fixed echo class: characters, newline, or both.
The underlying refusal, exact identities, continuity, capture and retry guards
are unchanged. `onpc_install::_prompt_diagnostic` adds a fixed boolean for the
line-anchored sudo/sudo-rs custom-prompt wrapper, without exporting PAM text or
terminal contents. Neither diagnostic authorizes input. Tests exercise all three
echo combinations, both wrapper names, private suffixes, command-like text that
must not match, existing read failures and continuity refusal. Successful
no-echo observations still avoid advisory reads entirely.

## Verification and attempt

| Check | Result / identity |
| --- | --- |
| `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_install_helper.py tests/unit/test_e2e_observation_transport.py -q` | 1286 passed, 2.00s; handle 63334, exit 0 |
| `tools/run-unit-tests tests/unit/test_e2e_installation_boundary.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py -q` | 87 passed, 0.25s; exit 0 |
| Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q` | 526 passed plus 3 subtests, 4.93s; handle 50942, exit 0 |
| Dispatcher safety closure | 526 passed plus 3 subtests, 4.99s |
| `tools/run-tests artifacts build` | Build/verify passed; handle 61203, exit 0; `/tmp/onpc-test-artifacts-2u0a0an7` |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-2u0a0an7` | Ninth expensive authentication attempt, one this slice; handle 71745, exit 1, 1055.743s |

All nine authentication attempts remain failed. New locally qualified diagnostics
justified this attempt; no unchanged rerun occurred. No checkout edits occurred
between artifact build and terminal result/cleanup. Source SHA256:
`8221843ab89ea6d7dd469073495ff61d96b17146c3787dc44a3ef50f32649fd7`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Worker: `worker-ddbf2f1ac1a9420c96be86f23c47978a`.

| Evidence | Location |
| --- | --- |
| Terminal result, provenance, restoration and lease | `/tmp/onpc-graphical-smoke-0k6g18lj/result.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-0k6g18lj/testresults/smoke-15.txt` |
| Worker/callback closure | `/tmp/onpc-e2e-evidence-v0dbslye/worker-result.json` |
| Controller qualification evidence | `/tmp/onpc-e2e-evidence-xbxecbjl` |

## Discriminating result and limits

Live recipient and continuity identities passed. The refusal was
`terminal-echo-enabled-other-syscall-poll-queue-empty-echo-newline`:
**ECHO was disabled and ECHONL enabled** at the sampled instant. This invalidates
the earlier inference that the poll necessarily precedes password input or that
password characters would echo. It is consistent with the audited password-read
path; it does not identify the polled descriptor or prove guest implementation.
Wait state remained unmapped and serial output queue empty.

The new line-anchored `prompt-sudo-rs` flag was **false**, as were all existing
prompt/error/shell-return/completion flags. Command prefix, tail, Enter and
paste-mode-off flags passed. Thus the exact wrapper/line-boundary hypothesis was
not established. Remaining possibilities include terminal controls at the line
boundary or a different packaged prompt composition; these require fixed safe
observations or source confirmation, not raw capture export or guessed matching.
The intermittent login executable refusal was not reproduced and remains open.

No sudo password was sent. Infrastructure failed with
`e2e:worker-execution-failed`; product and aggregate collection were not run.
Finalization additionally logged `unexpected-failure-or-interruption` while
retaining the original failure category. Installation, notice, reboot and startup
assertions did not execute.

## Cleanup and next action

Worker stopped, callback/display closed, baseline restored/verified, lease
completed/released, host/source preserved. Normal journey shutdown was not
reached; outer cleanup passed. Preparation/test/cleanup took
503.393/346.590/73.531 seconds; total includes finalization. The planned review
point was reached while finishing the owned operation; no second experiment
was started. All commands exited and results were collected. Unprivileged
artifact reads hit filesystem permission errors; the approved bounded
`onpc-test-artifacts read` escalation succeeded for both files. No approval-review
or Polkit denial, export, live owned operation, or recovery remains. Raw capture
was not inspected. Scoped whitespace and local links pass.

Next: qualify supported sudo prompt recognition and the password-character echo
contract using this new evidence. Audit distribution prompt composition and
serial control normalization; if necessary add fixed marker/control observations
that distinguish a wrapper following terminal controls from absence, without
accepting command echo or arbitrary PAM output as authentication proof. Review
newline-only handling explicitly before changing the input gate; retain exact
recipient/continuity, prompt, capture and retry requirements. Do not repeat the
ninth instrumentation unchanged. Then use fresh artifacts and isolated safety
checks for the smallest guarded success/refusal qualification. Real installation
success, final red notice, reboot/layout/readiness and both startup faults remain.

Next settings: `gpt-6-astra` / `high`, keep model and effort: the new echo evidence
corrects the diagnosis, but supported prompt recognition and any change to the
password-input safety contract still need security and transport review.
Task 20 estimates: **Unknown sessions / Unknown minutes**. Attempts have taken
16.4–20.4 minutes each; no successful authentication or later journey qualification
yet supports a reliable completion range. Handoff edits require fresh artifacts.
