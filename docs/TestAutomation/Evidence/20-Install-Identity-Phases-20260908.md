# Task 20: login identity phases and seventh attempt

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
Existing staged/unrelated work was preserved. This slice changed only the
installation password probe, its behavioral tests and task evidence/handoffs.

## Change and local verification

The login probe now distinguishes file stat/read failure, nonregular type,
owner/group, write permissions, process-executable resolution, executable
mismatch and credentials. Each condition identifies its initial, recipient or
continuity snapshot. All identity checks remain mandatory; only refusal detail
changed. Existing generic refusal tokens remain accepted for retained evidence.
Only fixed tokens leave the guest; paths, identities, exceptions, wait symbols
and authentication terminal bytes are never emitted.

The behavioral fixture injects eight faults at each of three snapshots, including
private exception canaries. Transport tests automatically cover all 21 new
allowlisted refusals and failure latching. Development-only activation is `none`
on next invocation; no product migration or setup change.

- `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_installation_boundary.py tests/unit/test_e2e_install_helper.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py -q`:
  **357 passed, 1.18s**, handle **60062**, exit 0.
- `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
  **526 passed, 3 subtests, 5.16s**, handle **79772**, exit 0.
- `tools/run-tests artifacts build`: handle **30439**, exit 0;
  `/tmp/onpc-test-artifacts-s2uscas7`, build and manifest verification passed.
- `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-s2uscas7`:
  handle **36838**, exit **1**, **1050.613s**. Dispatcher safety prerequisites
  passed 526 tests and 3 subtests in 5.13s. New locally tested observations
  justified this attempt; the six earlier attempts remain failed.

No checkout edits occurred from build through terminal collection and cleanup.
Source SHA256: `11f043e7aaabd8a641f35a3a114d26ba16456c648b9b09a0cb936c075db544bb`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Worker: `worker-b9d232b4c30245e797977f824678b065`.

| Evidence | Location |
| --- | --- |
| Final refusal, provenance, preservation and lease | `/tmp/onpc-graphical-smoke-5cjnj_fh/result.json` |
| Rejected installation stage | `/tmp/onpc-e2e-evidence-eqcp7f23/event-000023.json` |
| Worker stop and callback closure | `/tmp/onpc-e2e-evidence-4jwhxmdg/worker-result.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-5cjnj_fh/testresults/smoke-15.txt` |

## Finding and limits

Real serial login and installation preconditions passed. The prompt timed out;
command prefix/tail/Enter and paste-mode-off flags were present, while all prompt,
error, shell and completion flags were false. Recipient proof returned
**`terminal-echo-enabled-other`**. Therefore this observation passed all three
login identity snapshots, exact sudo command/executable and fixture ancestry,
terminal identity and final process continuity, but found ECHO or ECHONL enabled.
The process state was neither stopped/traced nor running at its sampled instant;
the wait value did not match the current fixed mapping. `other` does not
distinguish a zero/unavailable kernel symbol from an unmapped wait symbol.
No sudo password was sent. This does not resolve the sixth attempt's intermittent
`getty-executable` refusal or prove a terminal-drain cause.

Infrastructure failed with `e2e:worker-execution-failed`; product and aggregate
collection remained `not-run`. Finalization additionally logged
`unexpected-failure-or-interruption` without replacing the original category.
The truncated terminal summary was supplemented with bounded retained-artifact
reads for the actual outcome and cleanup fields; raw capture was not inspected.

## Cleanup and next action

Worker stopped, callback/display closed, baseline restored and verified, lease
completed/released, and host/source preservation passed. Normal journey shutdown
was not reached; outer cleanup passed. Preparation/test/cleanup timings were
514.519/328.765/73.228s; the overall duration also includes finalization overhead.
All commands exited and results were collected; no exports or recovery remain.
No approval-review or Polkit denial occurred. Scoped whitespace and links pass;
no task acceptance suite is claimed. Handoff edits require fresh artifacts.

Next, localize the pre-prompt sudo wait using fixed read-only observations of
the already-proved recipient. First distinguish zero wait data from unmapped
symbols and assess supported syscall/serial-output-queue classifications to
test the terminal-drain hypothesis. Qualify privacy, unknown/read-error and
continuity failure paths locally before another live attempt. Do not merely
add guessed wait symbols or repeat unchanged instrumentation. Keep exact prompt,
no-echo, identity, capture and terminal retry guards. **Seven expensive
authentication attempts; no unchanged eighth.** Install success/refusal, final
red notice, customer reboot, layout/readiness and both startup faults remain.

Next settings: **`gpt-6-astra` / `high`**, model keep, effort keep: the live
recipient identity passed, but pre-prompt waiting and intermittent identity
failure remain unresolved across OS/transport boundaries. Task 20 estimates:
**Unknown sessions / Unknown minutes**; the 17.5-minute failure adds no reliable
completion bound for the unqualified authentication and later journey steps.
