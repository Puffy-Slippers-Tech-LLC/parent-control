# Task 20 — cross-observation VT6 recipient gate

## Result and scope

The former fixed-token probes discarded process identity after each observation.
Added `VT6_GETTY_IDENTITY` and `VT6_PASSWORD_IDENTITY`, reusing their existing
guest predicates, plus the ordered single-use `ReadOnlyObservations` sequence
`vt6-getty-identity` → `vt6-password-identity` → `vt6-password-recheck`.
Boot/unit/PID/start-time digests bind all three reads to the same recipient.
The reader returns fixed booleans and the boot digest; recipient digests and raw
process data do not reach scenario evidence. Replaced identities, changed boot,
reordered/repeated reads, ownership/transport failures and invalid output latch
refusal. The old serial and credential-free prompt APIs retain their behavior.

The [owning VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
records the durable semantics, upstream references, canonical regressions and
limits; the [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) links it.
This is one completed prerequisite of controller authorization, not live input
qualification. `Smoke` does not call the sequence and `smoke.pm` still cannot
select authenticated VT6. The initial shell-proof scope was bounded here:
logind session activity does not establish shell command-input readiness, and
login detaches its terminal before forking a new session for its shell.
The [util-linux login implementation](https://raw.githubusercontent.com/util-linux/util-linux/master/login-utils/login.c)
supports that distinction; an unchanged login session-ID assertion on the child
would be incorrect. No placeholder shell or input-authorization proof was added.

## Verification

- `tools/run-unit-tests tests/unit/test_e2e_serial_observation.py
  tests/unit/test_e2e_vt6_recipient.py
  tests/unit/test_e2e_observation_transport.py -q`: **1,561 passed**, exit 0.
- `test_guest_password_probe_refuses_wrong_process_or_echo` executes the actual
  guest programs with process/terminal fixtures. New identity variants cover
  late unit/start-time/executable replacement, boot changes/malformed identity,
  root credentials and compatibility with the independent boot digest. Existing
  wrong-recipient, terminal, echo and active-VT cases also apply. Opened terminal
  descriptors close on success and refusal.
- `test_vt6_recipient_uses_fresh_fixed_probes_and_only_returns_proofs` checks the
  exact fixed programs, timeout, ownership bracketing and absence of input/shell
  authorization. The sequence has no copy/reboot capability.
- `test_vt6_recipient_refuses_skips_replays_and_repinning`,
  `test_vt6_recipient_requires_independent_boot_observation`,
  `test_vt6_recipient_refusal_is_private_and_permanent` and
  `test_vt6_recipient_new_boot_read_cannot_repin_original_identity` cover ordering,
  replaced identities, strict serialization, private output, guard failures,
  interruption, and permanent refusal of every subsequent observation.
- `make check`: **6,973 unit/contract and 58 private-D-Bus component tests passed**,
  exit 0, plus source and stage traceability checks. No checkout edits occurred
  during the command; documentation updates followed its exit.
- Documentation validation: **218 local links across five documents, none
  missing**; scoped `git diff --check` passed. Continuation selects the earliest
  ready task and contains exactly one supported settings line with a fresh reason.
- No test failed. No VM, package build or acceptance attempt was started.
  Historical prompt, matcher, installation and reboot failures remain retained
  through the [active handoff](../Task-20.md#task-20-continuation--2026-09-08).
  Prompt history remains two attempts (one failure, one corrected pass);
  installation history remains 21 (three historical passes, eighteen failures).

## Cleanup and next action

All started commands exited and results were collected. No VM lease, worker,
callback, screenshot export or recovery obligation was created. No approval or
Polkit denial occurred. Prior edits were preserved. **All-task VM clearance
persists**; missing executable controller proofs limit live readiness.

Task 20 remains earliest ready, with no bypass; Task 15A's later work stays
preserved. Next prove shell readiness/lineage using the pinned recipient, then
finish worker/capture provenance and durable exact-pixel authorization before
dispatch and the smallest guarded authenticated success/refusal. Do not repeat
prompt-only collection. Task 20 acceptance, sudo/notice pixels, full
installation/reboot/startup and both E2E-028 faults remain unfinished.

Actual settings: `gpt-6-astra` / `high`, Standard. Next settings:
`gpt-6-astra` / `high`, Standard. Recipient pinning is now locally verified;
shell readiness/lineage and capture authorization remain unresolved security
and correctness boundaries.
