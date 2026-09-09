# Task 20: explicit-newline prompt qualification

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
One guarded attempt passed: the eleventh authentication attempt overall.
The ten earlier failed attempts remain failed. Existing staged/unrelated work
was preserved; no checkout edits occurred from build through final collection.

## Changed boundary and local verification

`onpc_install.pm` supplies a leading newline through sudo's supported `-p`
argument, encoded as a literal Bash escape during typing. The independent
`SUDO_PASSWORD` argv check requires the actual newline, rejecting the old prompt
and a literal unexpanded escape. The matcher requires the newline, complete
fixed marker and complete English PAM suffix at the buffer end. It cannot
accept the bare marker before a fragmented unknown/private suffix arrives.
The sudo wrapper's earlier terminal framing no longer supplies the delimiter.

The [upstream v0.2.13 conversation source](https://raw.githubusercontent.com/trifectatechfoundation/sudo-rs/v0.2.13/src/pam/converse.rs)
confirms how the custom prompt and PAM suffix are composed. The distribution
fetch returned `Invalid OpenID transaction`; this upstream cross-check does not
replace the [retained guest/distribution audit](20-Install-Sudo-Contract-20260908.md).

Fixed failure categories distinguish unavailable/empty buffers, absent output
markers after excluding the literal echoed prompt argument, partial markers,
partial suffixes, unsupported framing/suffixes and supported prompts. Diagnostic
proof never authorizes input. Absence describes only the observed ring buffer.
Post-input diagnostics distinguish fixed denial/apt-output/re-prompt flags;
successful prompt recognition and single password submission have separate
fixed checkpoints. No raw authentication output or arbitrary PAM text is exported.

Tests exercise the installed os-autoinst `serial_screen::read_until` and its
real pipe reader with scheduled fragments. Every split in the valid prompt,
one-byte command echoes, delimiter/unknown-suffix fragments, retained failure
buffers, independent recipient refusal, private capture and retry refusal are
covered. No writer process is spawned. A stream cannot predict bytes delivered
after an already complete valid prompt; trailing private bytes are separately
tested in the same read, with recipient/continuity proof still mandatory.

| Verification | Result |
| --- | --- |
| Initial helper/password tests, handle 34779 | 290 passed, 51 failed: test fixture used a fractional timeout that the installed Perl parser treated as zero. Corrected to a supported whole-second timeout. |
| Corrected helper tests, handle 15796 | 115 passed, 18.60s, exit 0 |
| `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_install_helper.py tests/unit/test_e2e_installation_observations.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_installation_boundary.py tests/unit/test_graphical_smoke.py -q --tb=short` | 1597 passed, 20.72s; handle 27571, exit 0 |
| Final helper tests after strengthening fragment-consumption/private-suffix assertions | 115 passed, 18.70s; handle 69676, exit 0 |
| Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q --tb=short` | 526 passed, 3 subtests, 4.84s; handle 80926, exit 0 |
| Dispatcher safety closure | 526 passed, 3 subtests, 5.21s |
| `tools/run-tests artifacts build` | Passed; handle 38249, exit 0; `/tmp/onpc-test-artifacts-444tw0j2` |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-444tw0j2` | Passed; handle 2052, exit 0; 1165.609s |
| Scoped whitespace and local Markdown links | Passed |

## Live evidence and limits

| Evidence | Location |
| --- | --- |
| Terminal result, provenance, split outcomes and lease completion | `/tmp/onpc-graphical-smoke-7a9fw3je/result.json` |
| Explicit newline/fixed suffix recognized | Same run, `testresults/smoke-15.txt` |
| Single password and Enter submitted after independent proof | Same run, `testresults/smoke-16.txt` |
| Fixed authenticated package command and independent result passed | Same run, `testresults/smoke-17.txt` |
| Module result and GDM-return image | Same run, `testresults/result-smoke.json`, `testresults/smoke-19.png` |
| Worker/callback closure | `/tmp/onpc-e2e-evidence-sjj2q6jn/worker-result.json` |
| Controller qualification evidence | `/tmp/onpc-e2e-evidence-d42zxii9` |

Source SHA256: `c3dfa729ffa8411e4709f985db1aec1a96092f6f2bfc33c4488d0e5fb64b41a9`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.

The guest again established sudo-rs 0.2.13-0ubuntu1. Prompt recognition passed,
exact recipient/argv/continuity and character-echo proof passed, the password
was submitted once, and the authenticated apt command succeeded. Independent
package identity/digest and reboot-marker checks passed without changing boot
identity. Serial logout and GDM return passed; the return screenshot was directly
inspected and showed the account chooser. Infrastructure, collection and cleanup
passed. Product outcome remains `not-run`: this is helper qualification.

The historical intermittent executable refusal did not recur and remains open.
No deliberate live installation denial was run. The red final notice, customer
reboot, full installed layout/readiness and both startup faults remain outside
this qualification. Task 20 and E2E-002 are not accepted.

## Cleanup and next slice

Worker `worker-aeb8de441cdd4bfbaf2c52261ebd4fb0` stopped; callback/display closed;
normal shutdown verified. Outer baseline restoration/verification passed, lease
completed/released, host/source preserved. All commands exited and results were
collected. The scoped GDM screenshot export was inspected then removed with
`tools/cleanup-screenshots`; private originals remain. No recovery or live owned
operation remains. No approval-review or Polkit denial occurred.

Preparation/test/cleanup: 459.809/523.425/62.434 seconds; total includes final
validation. The slice exceeded its 25–30-minute planning range to finish the
single owned attempt and evidence/cleanup; no second attempt was started.

Next: qualify one fixed deliberate installation refusal through the existing
guarded worker, proving no password retry, no installed package, sealed capture
and cleanup. Do not replay the accepted happy path merely for a fresh session.
Then continue the preserved E2E-002 reboot/readiness and startup-fault scope.
Handoff edits require fresh artifacts for the next VM attempt.

Next settings: `gpt-5.6-sol` / `high`, lower model, keep effort, Standard.
The exact prompt/argv/recipient and successful worker path are now proven;
the next bounded refusal case builds on those contracts and local denial tests.
Reassess Astra if a new ownership or authentication ambiguity appears.
Remaining Task 20 estimates: **Unknown sessions / Unknown minutes**. The first
successful helper attempt took 19.4 minutes, but no measured batch establishes
the remaining refusal, complete reboot/readiness and startup-fault effort.
