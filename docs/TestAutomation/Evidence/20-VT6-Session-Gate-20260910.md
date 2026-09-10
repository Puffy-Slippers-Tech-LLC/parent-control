# Task 20 — VT6 authenticated-session observation

## Result and scope

Implemented the missing fixed `vt6-session` read-only observation. It requires
the canonical parent fixture's sole active local `login` session on `tty6` and
checks the kernel active VT before each logind command and before success.
Wrong users, terminals, services, remote sessions, duplicate/other user sessions,
foreground loss and unavailable observations refuse. Only the existing root SSH
observer exception is retained; root local or graphical sessions cannot use it.
The transport accepts only `vt6-session-ready` with its terminating newline,
exports fixed role/boolean fields and latches all failures without retry.

Reused the existing graphical/serial session predicate through explicit fixed
adapters in `guest_observations.py`, replacing serial's source-text substitution.
`PARENT_SESSION` and `SERIAL_SESSION` keep their surface requirements and output
tokens. `ReadOnlyObservations.read` owns the guarded transport and safe grammar.
See the [owning VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](../Reuse-Map.md#installation-helper-and-open-limits).

This is local session-observer verification only. It does not prove an
interactive shell is ready, bind a session to a previously observed login
process, authorize a password or establish atomic observation-to-input
continuity. The authenticated worker/controller route and reviewed-pixel needle
are still unimplemented. The initial broader login/input slice was narrowed to
this missing prerequisite; no live attempt was ready. The all-task VM clearance
remains in effect, and no old coordination hold was applied.

## Verification

- `tools/run-unit-tests tests/unit/test_e2e_observation_transport.py
  tests/unit/test_e2e_serial_observation.py tests/unit/test_e2e_vt6_prompt.py
  -q --tb=short`: **1,470 passed**.
- `make check`: **exit 0**, **6,631 unit/contract tests and 58 private-D-Bus
  component tests passed**, with stage traceability and common source checks.
  Checkout inputs remained unchanged during this command.
- Expanded `test_actual_guest_authentication_probe_rejects_wrong_sessions`
  executes all three real guest programs against controlled sessions, including
  missing fields, deadline/cardinality limits, transport failure and active-VT
  loss before, during and after logind reads.
- `test_fixed_probe_checks_ownership_before_and_after_output` and
  `test_vt6_proofs_refuse_other_surfaces_private_output_and_latch` cover the new
  probe's exact transport, foreign tokens, private suffixes, ownership failure
  and refusal latch. Existing login/getty/capture regressions also passed.

No test failed; no VM, build or acceptance attempt was made. Historical prompt
and installation attempt counts/results are unchanged. The retained
[prompt qualification](20-VT6-Prompt-Qualification-20260910.md) still establishes
the original collection only; this session does not extend its live scope.

## Cleanup and next action

All started commands exited and results were collected. No VM lease, worker,
callback, screenshot export or recovery obligation was created. No approval or
Polkit denial occurred. Existing frontend and prior task edits were preserved.
Task 20 remains earliest ready, with no bypass; its acceptance and both startup
fault cases remain unfinished.

Next: implement the reviewed native-resolution prompt needle and one-shot VNC
password route, using the existing capture/credential helpers and this session
observer. Bind worker/controller stages to unchanged boot and recipient/input
provenance; verify stale/wrong-account/missing-prompt and retry refusals before
the smallest guarded authenticated success/failure qualification. Do not repeat
credential-free collection. Sudo/notice and full installation remain later work.

Actual settings: `gpt-6-astra` / `high`, Standard. Next settings:
`gpt-6-astra` / `high`, Standard: the session predicate is verified locally, but
screen-based secret authorization and continuity across the new input route
remain unresolved security/correctness boundaries.
