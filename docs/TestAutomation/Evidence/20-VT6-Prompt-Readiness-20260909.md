# Task 20 — VT6 prompt readiness refusal and correction

## Result

One guarded credential-free worker attempt reached `vt6-ready` and refused
before the fixture name, password access, or terminal capture acknowledgement.
The retained traceback identifies the getty probe's canonical/echo assertion,
after active-VT, selected agetty identity, device and stdin checks had passed.
The correction passes locally; no second live attempt was run. Task 20 remains
unaccepted, with fixture/challenge pixels and real VT6 authentication pending.

The checkout already contained `onpc_vt6::inspect_prompt`, the `Smoke`
`VT6_PROMPT_STAGES` controller, and the no-argument
`check_graphical_vt6_prompt.py` entry point. The earlier handoff omitted them.
Reuse that credential-free collector, not another maintenance inspection or
new worker. It prohibits credential provisioning and authentication modes,
binds both captures to unchanged boot and independent getty/login observations,
uses private captures, and seals capture on return/failure. Its purpose is to
collect reviewable evidence before any password-enabled route is implemented.

## Cause and correction

`private/command-0338-stderr.txt` in the attempt below identifies generated
probe line 33: the conjunction requiring `ICANON` and `ECHO`. It does not record
individual flag values, so the exact live flag combination remains unknown.
It does establish that this predicate, not the prior active-VT/process/device
checks, caused refusal.

The [upstream util-linux v2.42 agetty implementation](https://github.com/util-linux/util-linux/blob/v2.42/term-utils/agetty.c)
initializes the virtual console with `reset_vc(..., canon=0)`; with
`AGETTY_RELOAD`, that clears local flags. `get_logname` implements character
input and echo itself when kernel echo is off. Builds without this mode retain
canonical input and kernel echo. This is a supported implementation explanation,
not a measured identity/version or flag reading from this guest.

`VT6_GETTY` now accepts those two coherent canonical/echo pairs and refuses
mixed pairs. Only the fixed nonsecret fixture name may follow this gate.
`VT6_PASSWORD`, all sudo password probes, boot/ownership checks, failure latches
and credential/capture policies are unchanged. The new raw agetty fixture in
`test_guest_password_probe_refuses_wrong_process_or_echo` exercises both modes
and the existing identity/device/foreground/read-error refusals. No new setup,
product integration activation or migration is needed.

## Verification and retained evidence

- Before live use: `tools/run-unit-tests tests/unit/test_e2e_vt6_prompt.py
  tests/unit/test_e2e_serial_observation.py
  tests/unit/test_e2e_observation_transport.py -q --tb=short`: **1,398 passed**.
- Isolated safety: `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py'
  tests/unit/test_graphical_lease.py -q --tb=short`: **585 passed, 3 subtests**.
  The installed dispatcher repeated its required safety selection with the
  same result before VM mutation.
- Sole live command: `tools/run-tests integration check_graphical_vt6_prompt`,
  through normal escalation outside the sandbox. **Exit 1**, infrastructure
  category `e2e:worker-execution-failed`, at `vt6-ready`. Product and collection
  outcomes are `not-run`; this is not successful prompt qualification.
- Attempt: `/tmp/onpc-graphical-smoke-b2tb9qum/result.json`; fixed traceback:
  `/tmp/onpc-graphical-smoke-b2tb9qum/private/command-0338-stderr.txt`.
  Controller checkpoints: `/tmp/onpc-e2e-evidence-l_1lon98`.
  Worker result: `/tmp/onpc-e2e-evidence-j6iis_t0/worker-result.json`.
- After correction, the same focused selection: **1,415 passed**. This adds
  the raw-mode getty fixture; it does not qualify live login or prompt pixels.
  Scoped whitespace validation passed; documentation validation checked 183
  local links across the five changed documents with none missing. No common
  or package acceptance run.

No credentials were read, provisioned or submitted. No terminal screenshots
were acknowledged, reviewed, exported or made into needles. The private worker
log confirms `sut`, Ctrl+Alt+F6 and the readiness request; it stops before fixture
typing. Existing private automatic screenshots remain retained, unreviewed.
Installation history remains 21 attempts (3 historical passes, 18 failures);
this separate credential-free VT6 prompt route has one failed attempt.

## Cleanup and next action

All launched commands exited and their results were collected. The worker
reports `worker_stopped=true`, `callback_closed=true`, and
`shutdown_verified=false`: normal graphical shutdown was not reached after
refusal. The outer owner completed baseline restoration and verification,
`lease_phase=complete`, cleanup passed, and both source and host preservation
passed. The VM is off/restored; no lease or recovery obligation remains.
No approval/Polkit denial occurred. A reader's unsupported positional tail
count was corrected to its supported default; no permission was widened.
Source edits began only after finalization. Unrelated frontend edits remain
preserved. **All-task VM clearance persists.**

Next: run the corrected credential-free collector once after isolated safety
checks, review both genuine terminal screenshots, and establish the selected
fixture echo/empty-challenge needle contract. If it refuses, inspect its exact
retained traceback before changing checks. Do not repeat the old predicate or
reinterpret the maintenance image as authentication evidence. Then implement
the missing authenticated local-VT6 session/controller gate and password input
with reviewed pixels. Sudo/notice pixels and full install/reboot/startup and
two independent E2E-028 faults remain later Task 20 acceptance work.

Actual settings: `gpt-6-astra` / `high`, Standard. Next settings:
`gpt-6-astra` / `high`, Standard, because live prompt/recipient qualification
and the private authentication boundary still require correctness review.
