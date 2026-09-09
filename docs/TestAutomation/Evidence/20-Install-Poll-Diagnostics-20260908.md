# Task 20: pre-prompt syscall and output-queue diagnostics

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
Existing staged/unrelated edits were preserved. This slice changed only
`installation_observations.py`, its behavioral tests and task evidence/handoffs.

## Change and qualification

The no-echo refusal now independently classifies zero/unmapped/unavailable wait
data, the proved sudo process's current syscall, and the serial output queue.
Syscall decoding requires a native x86-64 ELF header and matching kernel
architecture; other ABIs remain unsupported. Terminal-drain classification
requires a supported drain-setting ioctl whose descriptor is the proved serial
device. Queue observation uses read-only `TIOCOUTQ` on the already-validated fd.
Only fixed tokens leave the guest: no addresses, register values, descriptor
numbers, wait symbols, exception messages, terminal bytes or queue counts.
Identity and continuity checks remain mandatory after diagnostic read errors.
No-echo success avoids these advisory reads entirely. Prompt timeout and every
refusal remain terminal; no new observation authorizes password input.

Supported interfaces were checked against the primary
[proc syscall documentation](https://man7.org/linux/man-pages/man5/proc_pid_syscall.5.html),
[output queue documentation](https://man7.org/linux/man-pages/man2/TIOCOUTQ.2const.html),
[terminal setting documentation](https://man7.org/linux/man-pages/man2/TCSETS.2const.html)
and [Linux x86-64 syscall table](https://github.com/torvalds/linux/blob/master/arch/x86/entry/syscalls/syscall_64.tbl).
Development-only activation is `none`, on next invocation; no setup or migration.

- Final focused selection: **709 passed, 1.59s**, handle **27638**, exit 0.
  Modules: `test_e2e_install_password_observation`, `test_e2e_observation_transport`,
  `test_e2e_installation_boundary`, `test_e2e_install_helper`,
  `test_graphical_smoke`, `test_graphical_smoke_cleanup_safety`.
  Behavioral cases cover syscall classes, queue states, wrong descriptor,
  unsupported ABI, private/malformed reads and continuity loss after read failure.
  Transport coverage verifies all fixed refusals, durable failure and retry latching.
  An earlier intermediate selection passed 702 tests; no local test failed.
- Isolated cleanup selection: **526 passed, 3 subtests, 5.14s**, handle **84263**,
  exit 0. Dispatcher reran its required closure: 526 plus 3, 5.11s.
- Fresh artifact build/verification: handle **33522**, exit 0;
  `/tmp/onpc-test-artifacts-fpimoptg`.
- Guarded `--qualify-install`: handle **55855**, exit **1**, **1050.214s**.
  This was the **eighth** expensive authentication attempt, one in this slice,
  justified by the locally qualified discriminating observations. All eight failed.

No checkout edits occurred between artifact build and terminal result/cleanup.
Source SHA256: `df2dee677f9e93a01fa243ed86cd121da10d5fe47ece50cdf3e44fc833223a9e`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Worker: `worker-89690cc434d443cb8b384894fc25e00a`.

| Evidence | Location |
| --- | --- |
| Terminal result, provenance, preservation and lease | `/tmp/onpc-graphical-smoke-to0saf8b/result.json` |
| Installation-stage refusal | `/tmp/onpc-e2e-evidence-0u3p69zh/event-000023.json` |
| Worker stop and callback closure | `/tmp/onpc-e2e-evidence-f_2ulmuq/worker-result.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-to0saf8b/testresults/smoke-15.txt` |

## Discriminating result and limits

The exact recipient passed initial, recipient and continuity identities but
returned **`terminal-echo-enabled-other-syscall-poll-queue-empty`**. The sampled
syscall is poll or ppoll, and the serial output buffer is empty. The wait symbol
is unmapped, **not zero**. The terminal still has ECHO or ECHONL enabled.
This does not support an output-backlog/drain explanation at that sampled instant;
it does not establish which descriptor or service sudo is polling, or exclude
an earlier/different wait. Observations are sequential, not an atomic snapshot.

Command prefix/tail/Enter and paste-mode-off flags passed; every prompt, error,
shell-return and completion flag was false. No sudo password was sent.
The earlier intermittent login executable refusal remains unresolved, though
all identity phases passed in this attempt. Real installation and later product
assertions did not run. Infrastructure failed with `e2e:worker-execution-failed`;
aggregate collection and product outcomes are `not-run`. Finalization also
logged `unexpected-failure-or-interruption` without replacing the original failure.

## Cleanup and continuation

Worker stopped, callback/display closed, baseline restored and verified, lease
completed/released, and host/source preservation passed. Normal journey shutdown
was not reached; outer cleanup passed. Preparation/test/cleanup timings were
510.107/325.986/72.609 seconds; overall duration includes finalization overhead.
All commands exited and results were collected. Bounded approved artifact reads
confirmed worker closure and prompt flags; the stage-event read was truncated
after its relevant stage field, with complete outcome/provenance already present
in the terminal result. Raw capture was not inspected. No exports, recovery,
approval-review denial or Polkit denial remain. Scoped whitespace and links pass.

Next, audit the installed sudo implementation's pre-prompt poll paths and the
serial transport interaction. Design the smallest fixed, read-only observation
that distinguishes terminal polling from service/policy waiting on the proved
recipient; locally qualify privacy, unknown/read-error and continuity paths
before any ninth attempt. Do not merely add guessed wait symbols or repeat the
same instrumentation. Keep all prompt, echo, identity, capture and retry guards.
Real success/deliberate refusal, final red notice, customer reboot, layout/readiness
and both startup faults remain unqualified. Handoff edits require fresh artifacts.

Next settings: **`gpt-6-astra` / `high`**, keep model and effort: the poll/empty-queue
finding narrows the cause but leaves difficult sudo/OS/transport diagnosis.
Task 20 estimates: **Unknown sessions / Unknown minutes**. Eight authentication
attempts took 16.4–20.4 minutes each; unresolved authentication and later journey
boundaries prevent a defensible completion range.
