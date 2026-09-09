# Task 20 safe prompt diagnostics and second live attempt

Task 20 remains earliest ready and **not accepted**; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.

## Change and local verification

`onpc_install.pm` now reports fixed failure stages and, only after the unchanged
sudo-prompt match fails, fixed diagnostic flags. It uses the installed public
`testapi::wait_serial` negative-match mode with an impossible regex, a one-second
timeout, a 4096-byte ring buffer, `quiet=1` and `record_output=0`. The installed
API documentation and `consoles::serial_screen::read_until` confirm that failed
matches retain the ring buffer. No terminal bytes, identifiers, buffer lengths
or raw exceptions are published. The observation never authorizes password
input; prompt, exact process/no-echo proof, capture sealing and retry refusal
remain unchanged. Fixed stage recording also survives a diagnostic API error.

- `tools/run-unit-tests tests/unit/test_e2e_install_helper.py tests/unit/test_e2e_serial_helper.py tests/unit/test_graphical_smoke.py -q`:
  **82 passed, 0.93s**, handle **91903**, exit 0. The new
  `test_prompt_diagnostics_report_only_fixed_flags_and_never_authorize_input`
  covers eight cases: absent/unavailable data, command echo, sudo errors,
  CRLF/control/end prompt forms and diagnostic exceptions. Private canaries
  remain absent from stdout/stderr and no failure case sends a password.
- Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
  **521 passed, 3 subtests, 5.08s**, handle **34308**, exit 0.
- Scoped whitespace and handoff link checks passed. No product code, installed
  helper, setup policy or saved-data change; activation is next test invocation.
  Existing staged and unrelated working changes remain preserved.

## Live attempt and findings

`tools/run-tests artifacts build`, handle **94154**, exit 0, produced
`/tmp/onpc-test-artifacts-ya5brp0l`. Then
`tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-ya5brp0l`,
handle **10413**, **exit 1**, **981.015s**. The dispatcher repeated isolated
safety prerequisites: **521 passed, 3 subtests, 5.12s**. No checkout edits occurred
between build and terminal finalization/cleanup.

| Evidence | Location |
| --- | --- |
| Terminal result, source/package identities, stages and split outcomes | `/tmp/onpc-graphical-smoke-l9163274/result.json` |
| Ordered safe qualification checkpoints | `/tmp/onpc-e2e-evidence-deyoojv7` |
| Worker result and cleanup | `/tmp/onpc-e2e-evidence-in89dx8b/worker-result.json` |
| Module result linking fixed diagnostic records | `/tmp/onpc-graphical-smoke-l9163274/testresults/result-smoke.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-l9163274/testresults/smoke-15.txt` |
| Fixed failed stage (`password-prompt`) | `/tmp/onpc-graphical-smoke-l9163274/testresults/smoke-16.txt` |

Source SHA256: `5caaa23419efd2ce9555dd6f442a61e8c9afc5bedfc11904a046b851f95e8890`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Handoff edits require fresh artifacts for another VM attempt.

Real serial login and installation preconditions passed. The prompt match again
failed before the `install-password` request: no sudo password was sent and the
sudo process probe never ran. The diagnostic buffer was **present** and contained
**command echo**. All other flags were false: standalone custom prompt, exact
prompt end, CRLF/control suffix, line-start sudo error, unsupported-option text,
shell return and completion token. This proves some command input/output reached
the console and excludes an empty-buffer explanation. It does **not** prove
complete command delivery, sudo execution, absence of a differently formatted
prompt or the root cause. Do not relax authentication matching from these flags.

Backend exit 0 accompanied a failed module; the controller correctly retained
`e2e:worker-execution-failed` and recorded `e2e:backend-failure-artifact` during
finalization. Product and aggregate collection outcomes are `not-run`; safe
checkpoints, module diagnostics and terminal reports are nevertheless retained.
No product installation/reboot/startup coverage or deliberate live refusal is
accepted. The [first failed attempt](20-Install-Worker-20260908.md) remains failed.
**Two expensive attempts on this prompt blocker; one in this slice.**

## Cleanup and next boundary

Current worker result confirms `worker_stopped=true`, `callback_closed=true`.
`shutdown_verified=false` means normal journey shutdown was not reached. The
outer guard powered off and restored/verified the retained baseline; terminal
lease phase is `complete`, cleanup passed, host/source preservation are true,
and the command exited and released the lease. All session commands exited and
results were collected. No screenshots were exported and no recovery remains.
No execution-policy or Polkit denial occurred. Terminal stdout was truncated in
the tool response; relevant diagnostics and worker cleanup were subsequently
read from their complete bounded artifacts. A guessed console-module filename
was absent; a scoped source search resolved the actual public console wiring.

Next: locally qualify full-length command delivery and safe foreground/terminal
state observations before a third VM attempt. Distinguish partial command or
line-editing/transport state from a real sudo process with a differently
formatted prompt. Existing `SerialConsole.step`, public serial-screen input and
the `install-password` process proof are the relevant boundaries. The public
serial `type_string` implementation writes the supplied bytes directly; do not
assume VNC typing-speed options pace this console. Publish only fixed role/state
flags, never raw authentication terminal data. Require new discriminating
evidence or locally validated observability before the third attempt, as the
workflow requires. Do not perform an unchanged retry or broaden product cases.

Next settings: `gpt-6-astra` / `high`; unresolved transport/prompt diagnosis and
password-recipient privacy still require Astra. Task 20 estimates remain
**Unknown sessions / Unknown minutes**: the two attempts measured 16.7 and 16.4
minutes, but the first successful install, deliberate refusal, reboot/readiness
and startup faults remain unqualified. The bounded diagnostic result is complete;
the live failure is preserved for the next slice.
