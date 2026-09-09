# Task 20: post-login recipient topology

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
Existing staged/unrelated edits were preserved. This slice changed only
`installation_observations.SUDO_PASSWORD`, its behavioral tests and handoffs.

## Correction and scope

The old proof incorrectly required the getty/login leader to retain the serial
terminal after login. Upstream [util-linux login's fork_session](https://github.com/util-linux/util-linux/blob/master/login-utils/login.c)
detaches the parent terminal and creates a new session for its shell child.
The probe now requires the detached root-owned login process, follows its
single direct child via the process-specific children file, and verifies that
child's parent, session, process group, fixture credentials, Bash executable and
serial terminal. Its foreground process must be the direct sudo child with the
exact fixed install argv, trusted executable and expected credentials.

The proof rechecks login identity, child membership and process continuity;
both shell and sudo stdin must be the serial character device. The existing
terminal-device/no-echo proof, exact prompt gate, capture sealing, failure latch,
durable refusal and prohibition on retry remain. No host-wide process search,
terminal input/read, permission change or secret-bearing diagnostic was added.
This is development-only observation code, activated on next invocation (`none`),
with no product state or data migration.

## Verification

- `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_installation_boundary.py tests/unit/test_e2e_install_helper.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py -q`:
  **290 passed, 1.10s**, handle **69962**, exit 0. Includes realistic detached
  login topology, missing/ambiguous/replaced children, changed ancestry/start
  times/executables, wrong credentials/device types, read failures and echo.
- `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
  **526 passed, 3 subtests, 5.16s**, handle **42602**, exit 0.
- `tools/run-tests artifacts build`: handle **76944**, exit 0;
  `/tmp/onpc-test-artifacts-pywhdjon`. Build and manifest verification passed.
- Scoped whitespace and handoff links passed. No full task-acceptance suite
  was claimed. Exploratory searches included absent guessed filenames; relevant
  existing modules were then read directly. No policy or Polkit denial occurred.

## Fifth guarded attempt

The locally verified topology correction justified this attempt; it was not an
unchanged retry. `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-pywhdjon`:
handle **9353**, **exit 1**, **1038.338s**. Dispatcher prerequisites passed
526 tests and 3 subtests in 5.10s. No checkout edits occurred between build and
terminal collection/cleanup. Prior four prompt failures remain failed.

| Evidence | Location |
| --- | --- |
| Terminal result, preservation and lease state | `/tmp/onpc-graphical-smoke-duixpb6f/result.json` |
| Durable refusal before worker failure | `/tmp/onpc-e2e-evidence-agv7vjom/event-000023.json` |
| Worker termination/callback closure | `/tmp/onpc-e2e-evidence-ri8btwyi/worker-result.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-duixpb6f/testresults/smoke-15.txt` |

Source SHA256: `fa8a5d0ab717cfd3e1457927b0ed0fdc4de36f3a6105e4ed1ab6a3707bbb95c5`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Worker: `worker-51e0400ae52b4b85ae84ccb1eee5b361`.

Serial login and clean-install preconditions passed. The prompt timed out;
fixed command prefix/tail/Enter and paste-mode-off flags were present, while
prompt/error/shell/completion flags remained false. The new first refusal was
**`terminal-echo`**, replacing `getty-terminal`. Thus detached login, its direct
fixture shell, foreground sudo, exact argv, executable/credentials, both serial
stdin devices, first continuity snapshot and opened terminal-device checks all
passed at observation time. The final snapshot after the echo check was not
reached. This does **not** prove disabled echo: the current condition combines
`tcgetattr` failure with enabled ECHO/ECHONL. No sudo password was sent.

Checkpoint 23 and the terminal result retain that refusal. Infrastructure is
`e2e:worker-execution-failed`; product and aggregate collection are `not-run`.
Finalization also logged `unexpected-failure-or-interruption` without replacing
the original terminal category.

## Cleanup and next boundary

Worker stopped, callback closed, display closed; normal journey shutdown was
not reached. Outer cleanup restored and verified the retained baseline. Terminal
cleanup passed, lease phase is complete, host/source preservation passed and
the command exited/released the lease. Backend status is null because the
controller stopped the worker. All commands exited and results were collected;
no exports, owned operations or recovery remain. Preparation/test/cleanup took
501.418/318.125/86.615s; final collection completed before handoff edits.

Next: distinguish terminal-attribute read failure from enabled echo using fixed
allowlisted observations, then diagnose why the proven sudo recipient has not
reached the expected prompt/no-echo boundary. Keep raw authentication terminal
data private and preserve all guards. Read the probe, `onpc_install.pm`,
`ReadOnlyObservations.read`, and their focused tests. Qualify any new observation
locally before another guarded run with fresh source-bound artifacts and
isolated safety prerequisites. **Five expensive attempts on the authentication
blocker; no unchanged sixth.**

Next settings: **`gpt-6-astra` / `high`**, model keep, effort keep. Recipient
topology is now demonstrated, but live sudo/PAM/terminal diagnosis remains
unresolved. Task 20 estimates remain **Unknown sessions / Unknown minutes**:
17.3-minute diagnostic attempts do not predict authentication success, final red
notice, customer reboot, layout/readiness or the two startup faults. Handoff
edits invalidate artifact reuse. Task 20 remains earliest ready; no bypass.
