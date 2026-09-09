# Task 20: guest sudo contract and prompt intervention

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `xhigh`, Standard. All-task guarded VM clearance persists.
This operator intervention made exactly one guarded attempt, the tenth failed
authentication attempt overall. Existing staged and unrelated work is preserved.

## Proven contract and correction

The new `sudo-implementation` observation establishes the selected executable,
its installed package owner and numeric Ubuntu version before command input.
The guest actually runs **sudo-rs 0.2.13-0ubuntu1**, selected at
`/usr/lib/cargo/bin/sudo`; the host's later revision was not guest evidence.
Unknown implementations, unreviewed revisions, malformed/private fields,
read failures and noncanonical output refuse before authentication.

The matching Ubuntu source is retained by the distribution at commit
`c6c372786a8abe4971ba0b7bb57242753d8025af`:

- [PAM conversation](https://git.launchpad.net/ubuntu/+source/rust-sudo-rs/plain/src/pam/converse.rs?id=c6c372786a8abe4971ba0b7bb57242753d8025af)
  wraps the supplied custom prompt together with the PAM message.
- [Password reader](https://git.launchpad.net/ubuntu/+source/rust-sudo-rs/plain/src/pam/rpassword.rs?id=c6c372786a8abe4971ba0b7bb57242753d8025af)
  disables ECHO and ICANON, enables ECHONL, writes the prompt, then polls input.
  The [Ubuntu revision changelog](https://changelogs.ubuntu.com/changelogs/pool/main/r/rust-sudo-rs/rust-sudo-rs_0.2.13-0ubuntu1.2/changelog)
  and applied 0.2.13-0ubuntu1.1 source were also reviewed; the later .2 change
  concerns sudoedit. The preflight permits only these three reviewed revisions.
- Ubuntu Bash's [Readline terminal code](https://git.launchpad.net/ubuntu/+source/bash/plain/lib/readline/rltty.c?h=ubuntu/resolute)
  and [control constant](https://git.launchpad.net/ubuntu/+source/bash/plain/lib/readline/rlprivate.h?h=ubuntu/resolute)
  explain the bracketed-paste shutdown sequence ending in carriage return.

`SUDO_PASSWORD` now rejects character echo while allowing ECHONL. The password
is restricted to printable ASCII; Enter is sent separately. Real kernel PTY
tests cover canonical/noncanonical modes and character echo on/off. The full
recipient/read-error/continuity fault matrix also runs with ECHONL enabled.
Exact recipient/argv, process continuity, prompt, sealed capture, ordered
acknowledgements and terminal refusal/retry checks remain mandatory.

`onpc_install.pm` gained a strict raw-byte matcher for the custom prompt or
sudo-rs wrapper with the fixed English PAM suffix, optionally preceded by the
exact Readline shutdown sequence. Unknown controls, command echoes, arbitrary
PAM suffixes and incomplete prompts refuse input. Installed os-autoinst
`serial_screen::read_until` matches its ring buffer before `testapi::wait_serial`
normalizes CRLF; the project serial bridge forwards bytes without rewriting.

## Verification and live result

| Check | Result |
| --- | --- |
| `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_install_helper.py tests/unit/test_e2e_installation_observations.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_installation_boundary.py tests/unit/test_graphical_smoke.py -q` | 1535 passed, 3.45s; handle 44194, exit 0 |
| Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q` | 526 passed plus 3 subtests, 5.51s; handle 75272, exit 0 |
| Dispatcher safety closure | 526 passed plus 3 subtests, 5.46s |
| `tools/run-tests artifacts build` | Passed; handle 62886, exit 0; `/tmp/onpc-test-artifacts-8lagwo7n` |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-8lagwo7n` | Failed; handle 24280, exit 1; 1095.074s |
| Scoped whitespace and local Markdown links | Passed |

No checkout edits occurred from artifact build through terminal result and
cleanup. Source SHA256:
`2848959edbc7e51ffb09c8d4892706aa5581c5820905056b110c52cbd91d44e2`.
Package SHA256:
`ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.

| Evidence | Location |
| --- | --- |
| Terminal result, identity, provenance and lease completion | `/tmp/onpc-graphical-smoke-9796ahf2/result.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-9796ahf2/testresults/smoke-15.txt` |
| Safe recipient proof / failure stage | Same directory, `smoke-16.txt` / `smoke-17.txt` |
| Worker/callback closure | `/tmp/onpc-e2e-evidence-m7newexy/worker-result.json` |
| Controller qualification evidence | `/tmp/onpc-e2e-evidence-dul47_0g` |

GDM, serial login, guest implementation, product absence, assets, boot continuity
and the corrected independent sudo password proof passed. **Prompt recognition
still failed; no sudo password was sent.** The diagnostic proof succeeds only
after prompt timeout and cannot authorize input. Both `prompt-supported` and
`prompt-readline-wrapper` were false; command tail/Enter/paste-off were present.
Thus Readline framing alone did not explain the complete live stream. Exact
prompt presence/composition versus serial delivery remains unobserved by the
current fixed classifiers. Authentication success is not established.
The intermittent login executable refusal was not reproduced and remains open.

Infrastructure retained `e2e:worker-execution-failed`; finalization additionally
reported `e2e:backend-failure-artifact`. Product and aggregate collection were
not run. Install result, final red notice, reboot/readiness and both startup
faults remain unqualified. Historical failures remain failed.

## Cleanup and different next approach

Worker `worker-bdccdf16c0c14a969e65463acd667d26` stopped; callback/display closed;
baseline restored and verified; lease complete and released; host/source
preserved. Normal journey shutdown was not reached; outer cleanup passed.
Preparation/test/cleanup: 510.374/392.060/61.305 seconds; total includes
finalization. The diagnostic review and owned attempt exceeded the planned
25–30-minute slice; no second VM experiment was started. All commands exited
and results are collected. No export, live operation or recovery remains.
An unprivileged artifact read hit filesystem permission denial; the approved
bounded artifact helper escalation succeeded. No approval-review or Polkit
denial occurred. Public source fetches included missing-ref HTTP 404s and an
invalid response; valid distribution refs/commit reads supplied the audit.

Do not rerun this matcher unchanged or add another guessed prefix. The next
bounded approach is a **self-delimiting custom prompt**: use sudo's supported
custom-prompt option with an explicit leading newline, encoded as literal
escapes in the typed Bash command. Require the exact resulting marker and
known PAM suffix at the buffer end, and update the independently checked argv.
This makes the prompt's line boundary part of the fixed protocol instead of
depending on preceding Readline/terminal output. Locally prove command-echo
rejection, partial delivery, unknown/private suffix refusal, capture and
recipient gates before fresh artifacts and another single guarded attempt.
If that still fails, distinguish marker delivery from suffix composition in
the same attempt; do not relax input authorization to a substring match.
No claim is made that this unimplemented approach has solved delivery.

Task 20 stays earliest ready. Next settings: `gpt-6-astra` / `high`, keep model,
lower effort: guest implementation and ECHONL semantics are proven; the narrower
remaining prompt/transport boundary still needs security review. Standard
processing; no renewed VM coordination. Task estimates remain **Unknown sessions
/ Unknown minutes** because authentication and later journey boundaries remain
unqualified. Handoff edits require fresh artifacts for any next live attempt.
