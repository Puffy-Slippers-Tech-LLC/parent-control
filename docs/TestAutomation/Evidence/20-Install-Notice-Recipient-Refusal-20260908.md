# Task 20 final notice assertion and recurring recipient refusal

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
The slice isolated the missing final terminal-notice assertion before extending
the journey across reboot. No checkout edits occurred during build/live execution.

## Implemented boundary

`onpc_install.pm` checks the private serial tail through the split APT success
marker. It requires the exact bold-red ANSI notice immediately before the marker;
altered/plain/non-red text, intervening output and control-modified lines refuse.
One normalized CRLF layer is allowed. The 4 KiB ring retains the tail without
recording authentication output. Only fixed text/color/final-position flags enter
public evidence. Package result acknowledgement follows this assertion.

Tests cover these refusals, sealed capture/no retry, every notice/marker split
through the installed serial parser, ring overflow and carried shell-prompt bytes.
This asserts emitted output, not graphical rendering or reboot. Development
activation is `none` on invocation; no setup/product/migration change.

## Verification and inputs

| Selection | Result |
| --- | --- |
| Initial helper/package-transaction tests | 232 passed, 23.66s |
| `tools/run-unit-tests tests/unit/test_e2e_install_helper.py tests/unit/test_package_transaction_notice.py tests/unit/test_e2e_serial_helper.py tests/unit/test_graphical_smoke.py -q --tb=short` | 293 passed, 24.45s; handle 56802, exit 0 |
| Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q --tb=short` | 546 passed, 3 subtests, 6.10s; handle 46099, exit 0 |
| Dispatcher safety closure | 546 passed, 3 subtests, 6.02s |
| `tools/run-tests artifacts build` | Verified; handle 18203, exit 0 |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-m9ih6c6p` | Failed, 1210.207s; handle 73490, exit 1 |
| Changed-file whitespace and local Markdown links | Passed |

Manifest: `/tmp/onpc-test-artifacts-m9ih6c6p/artifact-manifest.json`.
Revision: `48a6bcf01dbc9e4ef392e15f71d9a2bb3c50be6b`.
Source SHA256: `8b3b90547f0819536cef31d140a61f0fef9f613595b240a240f92b344c60cadf`.
Package SHA256: `d339d1839a3fabcee53d0ca099a745ceace52c580906f69e494a261fd33eec4f`.

## Live finding and limits

Attempt fourteen overall: twelve failures remain failed, with two earlier
qualifications passed. All 92 assets matched; GDM interaction, real serial login,
product absence and audited sudo-rs 0.2.13-0ubuntu1 passed. The exact newline/PAM
prompt was recognized, then recipient proof refused at
**`getty-initial-exe-resolve`**, before password submission. The notice assertion,
authenticated package result, logout and GDM return were not reached.

The historical executable refusal recurred with narrower evidence: leader
selection, process stat and installed login file checks passed, then strict
resolution of that process's executable failed. The category cannot distinguish
a vanished/replaced process, permission error, missing target or another
resolution failure. No errno or continuity-at-failure evidence was captured.
Do not infer a prompt/ECHONL regression, relax identity checks or retry passwords.

| Evidence | Location |
| --- | --- |
| Final refusal, provenance, preservation and outer cleanup | `/tmp/onpc-graphical-smoke-p_pn690u/result.json` |
| Recognized fixed install prompt | Same run, `testresults/smoke-15.txt` |
| Ordered controller evidence | `/tmp/onpc-e2e-evidence-wnew223q` |
| Worker/callback closure | `/tmp/onpc-e2e-evidence-_nv62cu2/worker-result.json` |

Infrastructure failed with `e2e:worker-execution-failed`; finalization additionally
logged `unexpected-failure-or-interruption` without replacing the first category.
Product and aggregate collection are `not-run`. Early termination left no
`testresults/result-smoke.json`; fixed checkpoints and the worker result were
collected separately. An ordinary artifact read was permission denied; the
approved privileged reader succeeded. No approval-review, execution-policy or
Polkit denial occurred. Raw capture was not inspected.

## Cleanup and next action

Worker `worker-bad0358b661c47019abc27e42a149e15` stopped; callback/display closed.
Normal journey shutdown was not reached (`shutdown_verified=false`). Outer
cleanup restored/verified the baseline, completed/released the lease and preserved
host/source inputs. Fresh guarded status reported the pinned VM off (`state=5`,
`id=-1`). All commands exited; no exports, owned operations or recovery remain.
Preparation/test/cleanup: 536.025/294.508/250.224s; total includes final validation.
No second attempt ran. The planning range was exceeded to collect the failed
result and finish guarded cleanup.

Next audit `login_identity` and its read-only execution context. Add fixed
resolution-error categories and same-leader/start-time continuity at failure,
following only the selected identity. Validate missing/replaced identity,
permission/unknown errors and private-canary redaction. Diagnostic recovery must
never authorize password input. This is the second observed intermittent
executable refusal (the sixth attempt had a broad category); new locally
validated observability or a demonstrated correction is required before another
attempt. Then build fresh inputs and run one guarded qualification, retaining
the notice assertion. Return to reboot/readiness afterward; keep both startup
faults separate. Handoff edits invalidate artifact reuse.

Next settings: `gpt-6-astra` / `high`, model keep, effort keep, Standard: the read
is localized but its cause and ownership continuity remain unresolved.
Task 20 estimates: **Unknown sessions / Unknown minutes**. Live attempts cost
about 20 minutes, but the intermittent prerequisite and cross-boot/fault
interfaces have no measured completion bound.
