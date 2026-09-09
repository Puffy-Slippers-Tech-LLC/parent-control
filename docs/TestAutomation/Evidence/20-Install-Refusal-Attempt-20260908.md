# Task 20 deliberate installation refusal — first live attempt

Scope: fixed helper qualification, not E2E-002 acceptance. Task 20 remains the
earliest ready unchecked task and the all-task guarded VM clearance persists.
Actual settings: `gpt-5.6-sol` / `high`, Standard processing.

## Implemented boundary

The mutually exclusive `--qualify-install-refusal` route reuses the qualified
asset, fixture-credential, serial-login, prompt and recipient contracts. After
the exact prompt and independent sudo/terminal proof, the helper submits one
fixed non-secret, non-hex password that cannot equal the random lowercase-hex
fixture password. It requires the first re-prompt and refuses a second password.
Capture stays sealed. A final read-only probe follows only the systemd-owned
getty/login lineage and requires the exact fixture shell to have no child
installer; package database, payload and reboot-marker absence are also required.

The first implementation used graphical `send_key('ctrl-c')` after the refusal.
The selected console is the maintained pipe-backed serial transport. The live
sequence below localized cancellation to that call, so the helper now sends the
fixed interrupt byte through `type_string`, the same qualified serial input API
used for its command and Enter. The next live attempt must qualify this correction.

Local verification:

- The complete focused selection passed **1,474 tests** after correction of one
  new boundary-test expectation and five fake-path fixture failures in the new
  executable post-refusal probe matrix.
- After the live transport correction, the directly affected install/serial
  helper selection passed **134 tests** in 18.95 seconds.
- Isolated cleanup prerequisites passed **526 tests plus 3 subtests** in 5.25
  seconds; the guarded dispatcher repeated the same closure in 4.95 seconds.
- Documentation links and `git diff --check` passed. The installed dispatcher
  refresh and fresh artifact build passed.

## Live result and evidence

Fresh build directory: `/tmp/onpc-test-artifacts-9m25qdvl`. Source SHA256:
`2e7a82891abd5903bd0ca2225014828b6d184af8524519b100daa9d11de899e1`.
Package SHA256:
`9950bc96b9a7f609700121a97a676813a5789ae64d75a8e20161aa42d94626f1`.
Handoff and correction edits make these inputs stale for another attempt.

Guarded handle **14132** exited **1** after **980.910 seconds**. This was the
twelfth installation-authentication attempt overall: one successful qualification
and eleven failures, including the ten historical failures. No second attempt
was started in this slice.

| Evidence | Location |
| --- | --- |
| Terminal result, provenance, stages and cleanup | `/tmp/onpc-graphical-smoke-tucwtrnl/result.json` |
| Ordered controller checkpoints | `/tmp/onpc-e2e-evidence-vdhla1e4` |
| Worker failure and resource closure | `/tmp/onpc-e2e-evidence-6pn_3bqr/worker-result.json` |
| Private module result and fixed refusal checkpoint | `/tmp/onpc-graphical-smoke-tucwtrnl/testresults/result-smoke.json`, `smoke-16.txt` |

The run verified fresh provenance, fixture credentials, all 92 transferred
entries, GDM interaction, real serial login, product absence, audited sudo-rs
0.2.13-0ubuntu1, unchanged boot identity, exact prompt, recipient/process
continuity and password-character echo disabled. It then submitted the fixed
invalid value once, observed its rejection and recorded that no retry password
was submitted. The public module became `canceled` immediately afterward,
before `install-refused`; it did not reach the package/process postcondition,
serial logout or GDM return. Product remained `not-run`. The backend failure
artifact and `e2e:worker-execution-failed` correctly kept the attempt failed.

The fixed checkpoint plus the ordered source makes the graphical-key API at a
pipe-backed serial console the supported cause hypothesis, not a prompt,
recipient or authentication-rejection ambiguity. The corrected interrupt-byte
path is locally qualified. The next attempt must observe the shell prompt,
`install-refused`, serial logout and GDM return; a different failure there needs
fresh diagnosis rather than another unchanged retry.

## Cleanup and next action

Worker `worker-c2ec4cabc867434dbb4e09699f0a923a` stopped and callback/display
closed. Normal journey shutdown was not reached, so `shutdown_verified` is
false; the outer guard powered off, restored and verified the retained baseline.
Lease phase is `complete`; cleanup passed, host/source preservation passed, and
all commands exited with results collected. No exported screenshot or recovery
remains. No approval, execution-policy or Polkit denial occurred.

Next: build fresh source-bound artifacts, rerun isolated cleanup prerequisites,
and make one guarded `--qualify-install-refusal` attempt with the serial-byte
correction. Do not repeat the successful install path. The red final notice,
customer reboot, installed layout/readiness and both startup faults remain after
this helper qualification.

Next settings: `gpt-5.6-sol` / `high`, keep both, Standard. Prompt, recipient,
first rejection and no-retry behavior are proven; the next bounded attempt tests
one locally corrected serial transport call with established guards. Reassess
Astra only if the corrected attempt exposes a new ownership/authentication
ambiguity. Remaining refusal qualification: **1 session / 15–25 minutes** based
on this 16.4-minute run and a fresh build/safety closure. Remaining full Task 20:
**Unknown sessions / Unknown minutes** because reboot/readiness and both startup
fault batches remain unmeasured.
