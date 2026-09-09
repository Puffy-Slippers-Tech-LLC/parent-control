# Task 20 command delivery and recipient-proof diagnosis

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.

## Bounded change and verification

`onpc_install.pm` adds fixed command-tail, command-Enter and Readline
paste-mode-off flags to its existing private-buffer diagnostics. After a prompt
timeout it requests the existing exact read-only `install-password` proof for
diagnosis. Prompt failure remains terminal even if that proof succeeds: no
password, completion request, retry or capture is permitted. Exceptions remain
private. The normal successful-prompt path and exact recipient proof are
unchanged. No product, setup, permission or saved-data change; activation is
the next test invocation.

The installed public `testapi::type_string` and
`consoles::serial_screen::type_string` implementations send serial bytes
directly and check their write length. VNC typing-speed options do not pace
this transport. The local full-command test uses real private pipes and fake
libvirt, checking exact bytes including the final newline under alternating
backpressure and 1/16/64/4096-byte sends. This qualifies the adapter, not guest
UART or shell behavior.

- `tools/run-unit-tests tests/unit/test_e2e_install_helper.py tests/unit/test_e2e_serial_helper.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_serial_cleanup_safety.py tests/unit/test_e2e_installation_boundary.py -q`:
  **125 passed, 1.24s**, handle **28115**, exit 0. Cases include
  `test_full_install_command_survives_partial_sends_and_backpressure` and
  `test_prompt_diagnostics_report_only_fixed_flags_and_never_authorize_input`.
  Diagnostic proof success, wrong process, echo enabled, exceptions and private
  canaries are covered; all prompt failures refuse password input.
- Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
  **525 passed, 3 subtests, 5.18s**, handle **75379**, exit 0.
- `tools/run-tests artifacts build`: handle **90532**, exit 0,
  `/tmp/onpc-test-artifacts-nv72hp5q`. Scoped whitespace checks passed; handoff
  links were checked after the documentation update. No task acceptance or
  full-suite pass is claimed.

## Third guarded attempt

New locally verified observability justified one additional attempt after the
two prior prompt failures. No unchanged retry was made.

`tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-nv72hp5q`:
handle **51198**, **exit 1**, **1042.275s**. Dispatcher safety prerequisites also
passed **525 tests and 3 subtests, 5.17s**. No checkout edits occurred from build
through terminal collection and cleanup.

| Evidence | Location |
| --- | --- |
| Terminal result, provenance and split outcomes | `/tmp/onpc-graphical-smoke-05tmbdm5/result.json` |
| Ordered safe qualification checkpoints | `/tmp/onpc-e2e-evidence-gqbzpazl` |
| Worker failure and cleanup | `/tmp/onpc-e2e-evidence-62fucxbs/worker-result.json` |
| Fixed command/prompt flags | `/tmp/onpc-graphical-smoke-05tmbdm5/testresults/smoke-15.txt` |

Source SHA256: `9f6de18b04a7e6c89bcbaa5a76585b7e3e94ea95ceaf876c0b11dfde0505df57`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Worker identity: `worker-3c37725c588d48acb07028016e74ec9b`.
Documentation edits after this run require fresh artifacts for another attempt.

Real serial login and installation preconditions passed. On prompt timeout,
the buffer showed command prefix, exact command tail, tail followed by Enter,
and Readline's paste-mode-off sequence. All recognized prompt/error/shell-return
and completion flags were false. This rejects the simple missing-tail/Enter
hypothesis. It does not prove every middle byte arrived, sudo executed, or the
identity/echo state of its password recipient.

The new diagnostic `install-password` request reached the controller. Its first
boot observation passed, then the exact recipient observation was rejected.
The controller stopped the worker before a reply or final module result could
be written. Therefore `result-smoke.json` is absent (the bounded read returned
FileNotFoundError); listing the directory located the already persisted fixed
flags. Neither `install-recipient-diagnostic` nor `install-failed-stage` was
finalized in this controller-stop path. No sudo password was sent. No raw
authentication terminal data was read or exported. The rejection does not
identify which predicate in `SUDO_PASSWORD` failed.

Infrastructure remains `e2e:worker-execution-failed`; product and aggregate
collection are `not-run`. The runner additionally logged the generic
`unexpected-failure-or-interruption` infrastructure outcome during finalization;
its terminal category preserves the worker failure. Backend exit status is
null because the controller stopped it, not a successful backend completion.
The [first](20-Install-Worker-20260908.md) and
[second](20-Install-Prompt-Diagnostics-20260908.md) attempts remain failed.
**Three expensive attempts on this blocker; one in this slice.**

## Cleanup and next action

Current worker evidence confirms `worker_stopped=true`, `callback_closed=true`.
Normal journey shutdown was not reached (`shutdown_verified=false`). The outer
guard powered off, restored and verified the retained baseline; terminal lease
phase is `complete`, cleanup passed, and host/source preservation are true.
The command exited and released its lease. All started commands exited and
their results were collected; no screenshot export or recovery remains. No
execution-policy or Polkit denial occurred. Early guessed source filenames
were absent; scoped searches located the actual transport modules without
broad repository reads.

Next: locally qualify fixed, read-only per-condition diagnostics for the
existing getty/foreground-process/terminal proof, then use the smallest guarded
attempt with fresh artifacts and isolated safety prerequisites. Distinguish
shell/foreground state, exact sudo argv/executable/ancestry and disabled echo
without publishing identifiers, argv, terminal bytes or exceptions. Follow only
the existing guest getty/foreground identities; do not scan host processes or
weaken the proof. Capture safe refusal evidence before the controller stops
the worker. No unchanged fourth attempt; new discriminating evidence or locally
validated observability is required.

Next settings remain `gpt-6-astra` / `high`: input-tail delivery is now observed,
but recipient identity and terminal-state diagnosis remain unresolved. Once
real authentication success/refusal is proven, reassess to Sol high. Successful
installation, deliberate live refusal, final red notice, customer reboot,
layout/readiness and both startup faults remain unqualified. Task estimates:
**Unknown sessions / Unknown minutes**; measured attempts were 16.7, 16.4 and
17.4 minutes, insufficient to forecast the unresolved boundaries.
