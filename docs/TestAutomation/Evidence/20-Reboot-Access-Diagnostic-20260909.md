# Task 20 reboot access diagnostic

Task 20 remains the earliest ready unchecked entry; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
This slice reused the [customer reboot boundary](../../../tests/e2e/README.md#customer-reboot-observation-boundary)
and the existing private serial-result tail. It added no transport, guest policy,
setup change or process-cleanup mechanism. Test-tool activation is `none`.

## Discriminating result and limits

Attempt nineteen overall passed provenance, all 92 asset entries, GDM, serial
authentication, exact sudo recipient/echo proof, installation, package digest,
reboot marker and unchanged boot/session checks. The exact final bold-red notice
also passed. The customer reboot command returned nonzero; the new fixed flags
observed `access-denied=1`. The other six flags were zero. The helper stopped
without retry, another password or boot observation.

This establishes an `Access denied` token in the matched command-result tail.
It does **not** establish the exact denied D-Bus method, Polkit action, policy
rule or service availability. The diagnostic does not distinguish a wall-message
warning from the reboot method's error. Known inhibitor/session and shell-error
messages were not observed; their absence is not a complete exclusion of those
causes. No raw authentication/terminal text was read or exported.

Post-run source review found a diagnostic coverage gap:
[systemd's authentication challenge](https://github.com/systemd/systemd/blob/v259/src/shared/bus-polkit.c)
can start with `Access denied` and use lowercase `requires interactive
authentication`. The live classifier recognized only the shorter capitalized
form. Its zero authentication flag therefore cannot exclude an authentication
challenge. The final helper recognizes both forms; the added long-form regression
passes locally. That extension was made **after** the live attempt and has no
live qualification. Do not reinterpret the retained flags as if it ran there.

[Systemd's local inhibitor/session precheck](https://github.com/systemd/systemd/blob/v259/src/systemctl/systemctl-logind.c)
can also precede authorization. These upstream sources guide the diagnostic;
they do not identify the guest's exact error or prove an authenticated reboot.
The next path should use explicit supported guest administrator authentication,
with the existing sudo recipient/echo proof adapted to a fixed reboot command.
No sudo-cache assumption, force/ignore-inhibitor option, permission change,
host lifecycle substitution or retry after a failed boundary is authorized.

Three historical qualifications remain passed; sixteen attempts remain failed.
One new live attempt was made. The earlier 330-second timeout remains unexplained,
and the intermittent install recipient defect did not recur but remains open.
Successful reboot, missing-marker prompt retention, serial/display continuity,
readiness/layout, graphical notice rendering and assigned E2E-028 faults remain
unaccepted. E2E-002 stays pending.

## Verification and retained evidence

| Selection | Result |
| --- | --- |
| Serial/install/smoke regressions before live attempt | 308 passed, 22.14s; handle 84411, exit 0 |
| Isolated cleanup safety and graphical lease | 546 passed, 3 subtests, 4.71s; handle 64065, exit 0 |
| Pre-attempt `make check` | 5274 unit/contracts and 17 private-D-Bus components passed; traceability/syntax passed; handle 18131, exit 0 |
| Fresh artifact build | Passed; handle 5368, exit 0 |
| Dispatcher safety closure | 546 passed, 3 subtests, 5.10s |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-7ljqstd2` | Failed after reboot returned nonzero; 1279.145s; handle 48288, exit 1 |
| Final classifier long-form regression selection | 36 passed, 0.65s; exit 0 |
| Final `make check` after the wording extension | 5275 unit/contracts, 107.29s, and 17 private-D-Bus components passed; traceability/syntax passed; handle 19312, exit 0 |
| Changed-document links and scoped whitespace | 133 links across five documents passed; scoped `git diff --check` passed |

Manifest: `/tmp/onpc-test-artifacts-7ljqstd2/artifact-manifest.json`.
Revision: `944da18980cab1181c287ba9d59e88276cbea654`.
Source SHA256: `da7c07253664b9fac107e0df41aade2bdf59e9815d6e6610a469c025aadab969`.
Package SHA256: `cd509bfbdfdab8801c33712b14157a09ba66b984f55eb4b07a9fe3d0623a01c9`.
No checkout edits occurred during build, execution, collection or cleanup.
The final classifier extension and documentation require fresh artifacts next time.

| Evidence | Location |
| --- | --- |
| Terminal result, input identities, preservation and lease completion | `/tmp/onpc-graphical-smoke-a38l49aq/result.json` |
| Fixed diagnostic references | Same run, `testresults/result-smoke.json` |
| Notice flags / command result / rejection flags | Same run, `testresults/smoke-17.txt`, `smoke-20.txt`, `smoke-21.txt` |
| Durable checkpoints | `/tmp/onpc-e2e-evidence-pmqnyv89` |
| Worker result and cleanup | `/tmp/onpc-e2e-evidence-g13sbh87/worker-result.json` |

Infrastructure failed (`worker-execution-failed`); product/collection aggregates
are `not-run`. The backend's zero exit plus failure artifact correctly failed
the run, and `shutdown_verified=false` remains explicit. Worker
`worker-7df0bd35f3db49198a6d10de501f5a24` stopped; callback and display closed.
Outer baseline restoration/verification, lease completion, cleanup and host/source
preservation passed. Fresh guarded VM status is `state=5`, `id=-1`.
No screenshot exports, live resources or recovery remain. Preparation/test/cleanup
were 509.520/559.288/72.873 seconds. The review window was exceeded to finish
the single owned attempt and its preservation checks, then correct the discovered
diagnostic wording gap. No execution-policy, auto-review or host Polkit denial
occurred. Public documentation fetches had unavailable-page responses; upstream
versioned source supplied the relevant diagnostic contracts. All session commands
have exited and results are collected; cleanup is complete.

## Next bounded result

Implement the supported, explicitly authenticated customer reboot path. Reuse
`onpc_install.pm`'s fresh sudo challenge and `installation_observations.py`'s
getty-derived recipient/terminal proof, factoring only the fixed command-specific
part. Never accept arbitrary worker-selected argv or reuse the apt proof for a
different recipient. Prove refusal/no retry and secret sealing locally, then
fresh artifacts, isolated safety and one guarded attempt for changed boot and
serial/GDM return. Keep current denial evidence failed and policy unchanged.
No further unchanged noninteractive reboot attempt is useful.

Next settings: `gpt-6-astra` / `high`, Standard; keep model and effort because
the new password-recipient capability and first cross-boot continuity proof
still require authorization/ownership review. Task 15A's later work is preserved.
