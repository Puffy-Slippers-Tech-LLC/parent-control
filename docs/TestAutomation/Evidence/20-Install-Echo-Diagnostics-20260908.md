# Task 20: terminal diagnostics and sixth attempt

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
Existing staged/unrelated work was preserved. This slice changed only
`installation_observations.SUDO_PASSWORD`, its behavioral tests and handoffs.

## Implementation and verification

The probe separates `terminal-attributes` read failure from enabled ECHO/ECHONL.
On enabled echo it follows only the already-proved sudo recipient and returns
an allowlisted state/wait classification, never raw symbols, identities,
exceptions or terminal bytes. Unknown symbols map to `other`; diagnostic read
errors map to `unavailable`. A further identity/command/ancestry snapshot must
pass before returning the classification; its failures retain their own stage.
Exact prompt, ownership, serial device, no-echo, capture and retry guards remain.
The old `terminal-echo` token remains accepted for evidence compatibility.
Development-only activation is `none` on next invocation; no product migration.

- `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_installation_boundary.py tests/unit/test_e2e_install_helper.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py -q`:
  **312 passed, 1.13s**, handle **43222**, exit 0. Covers attribute/echo failures,
  state/wait classifications, private canaries, read errors, continuity changes
  and every transport refusal with failure latching.
- `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
  **526 passed, 3 subtests, 5.08s**, handle **44261**, exit 0.
- `tools/run-tests artifacts build`: handle **42962**, exit 0;
  `/tmp/onpc-test-artifacts-e12myp8g`, build/manifest verification passed.
- `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-e12myp8g`:
  handle **8917**, exit **1**, **1222.911s**. Dispatcher prerequisites passed
  526 tests and 3 subtests in 5.14s. New locally tested diagnostics justified
  this attempt; all five earlier failures remain failed.

No checkout edits occurred from build through terminal collection/cleanup.
Source SHA256: `d4ccd08f3303d1a91ccdeb98557cc474a152d06d2f7e3fcf5a20e1d6f9aa0444`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Worker: `worker-f88c7c132df644319ac86fe632634063`.

| Evidence | Location |
| --- | --- |
| Terminal result, preservation and lease | `/tmp/onpc-graphical-smoke-4mhiaxh6/result.json` |
| Durable refusal | `/tmp/onpc-e2e-evidence-uchdu_uv/event-000023.json` |
| Worker stop and callback closure | `/tmp/onpc-e2e-evidence-470h3cp8/worker-result.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-4mhiaxh6/testresults/smoke-15.txt` |

## Finding and limits

Real serial login and install preconditions passed. The prompt timed out;
command prefix/tail/Enter and paste-mode-off flags were present, while prompt,
error, shell and completion flags remained false. Proof returned
**`getty-executable`**, not a terminal classification. This combines login-file
trust checks and process-executable resolution and is reused in initial and
continuity snapshots. Evidence does **not** identify which check/snapshot failed,
whether the terminal branch was reached, or whether echo was enabled. The
[fifth attempt's ambiguity](20-Install-Login-Topology-20260908.md) is unresolved.
No sudo password was sent. Infrastructure remained `e2e:worker-execution-failed`;
product and aggregate collection are `not-run`. Finalization additionally logged
`unexpected-failure-or-interruption` without replacing the original category.

Source inspection found a possible terminal-drain hypothesis, not a proven VM
cause: upstream sudo changes terminal mode before printing the prompt and uses
a draining/flushing attribute update; Linux terminal draining may wait for
pending output. References: [sudo prompt](https://github.com/sudo-project/sudo/blob/main/src/tgetpass.c),
[sudo terminal helper](https://github.com/sudo-project/sudo/blob/main/lib/util/term.c),
[Linux terminal drain](https://github.com/torvalds/linux/blob/master/drivers/tty/tty_ioctl.c).

## Cleanup and continuation

Worker stopped, callback/display closed, baseline restored and verified, lease
complete/released, host/source preservation passed. Normal journey shutdown
was not reached; outer cleanup passed. All commands exited/results collected;
no exports or recovery remain. Preparation/test/cleanup took
532.519/306.986/249.909s. The 20.4-minute attempt and final collection were allowed
to finish; no operation was stopped for the slice estimate.

An ordinary private-artifact read received filesystem permission denied; the
approved artifact helper succeeded. No approval-review/Polkit denial or permission
change occurred. A handoff patch failed context validation without applying;
corrected context was then used. Scoped whitespace and links pass; no full task
acceptance suite is claimed. Handoff edits invalidate artifact reuse.

Next: split login-file trust/read/resolve/replacement conditions and initial
versus continuity snapshot using fixed, locally tested observations. Retain
terminal diagnostics and identity guards; do not infer a topology regression.
Read `login_identity`, `snapshot`, their behavioral tests and the durable refusal
consumer. **Six expensive authentication attempts; no unchanged seventh.**
Require locally validated correction or discriminating observability before
fresh artifacts and another guarded attempt. Install success/refusal, final red
notice, customer reboot, layout/readiness and both startup faults remain.

Next settings: **`gpt-6-astra` / `high`**, model keep, effort keep: varying live
refusals and repeated identity snapshots require difficult ownership and
authentication diagnosis. Task 20 estimates remain **Unknown sessions / Unknown
minutes**; measured failures of 16.4–20.4 minutes cannot predict completion of
the unqualified boundaries. Selection rechecked: Task 20, no bypass.
