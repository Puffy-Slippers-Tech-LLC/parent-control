# Task 19A — private secret staging and password/capture boundary

This session made solid host implementation progress: a frozen fixture-secret
registry, descriptor-pinned private variable staging, and a maintained Perl
password/capture helper now exist. The credential-free worker uses the staging
route; its smoke uses the guarded explicit capture route. There are **51 new
regressions** (49 secret/storage/Perl behavior cases and two worker staging
failure/interruption cases). This is not live authentication/serial acceptance.

The [contract](../../../tests/e2e/README.md#credential-staging-and-password-capture-boundary)
documents variable names, supported fixture characters, capture exclusions,
fixed masked-prompt tags, failure latching and remaining integration. Public
`get_required_var`, `assert_screen` and `type_password` are the only password
API operations. The installed pinned `testapi.pm` documents and implements
secret input; `bmwqemu.pm` filters the secret variable names on filtered saves.
Sources: [testapi](https://github.com/os-autoinst/os-autoinst/blob/b85e4864/testapi.pm)
and [variable saving](https://github.com/os-autoinst/os-autoinst/blob/b85e4864/bmwqemu.pm).
Local installed source was inspected; web retrieval did not supply new evidence.
Automatic screenshots remain possible and private, even with `NOVIDEO=1`.

## Verification and inputs

| Experiment | Result and measured test time | Preparation / VM / cleanup |
| --- | --- | --- |
| `tools/run-unit-tests tests/unit/test_e2e_secret_variables.py tests/unit/test_e2e_worker_cleanup_safety.py -q` | 86 passed, 0.71 s; command session 85225 exited 0 | No setup or VM operation; ordinary temporary unit fixtures only |
| `make check` outside sandbox for private D-Bus sockets | 2,270 unit/contracts passed in 36.83 s; 17 components in 0.32 s; syntax and stage traceability passed; command session 34024 exited 0 | No VM operation or host teardown |
| `git diff --check` | Passed after final documentation edits | No runtime work |

Inputs atop `5fe25e3`, including these uncommitted implementation bytes:

| File | SHA-256 |
| --- | --- |
| `tests/e2e/secret_variables.py` | `47a6beadee4ffa5fe377725e0116528c498ced0fc89cbc792ddf90a5a90ee2cd` |
| `tests/e2e/e2e_worker.py` | `57769f8a39c2bc6eb4e74502a8a3987a2e73cf84eb818de9c3713523afd5382e` |
| `tests/integration/graphical_smoke/lib/onpc_password.pm` | `409fa538ed36805aa343610f02d403f0c205cf7bda9eeb72095b70cd1789b1f5` |
| `tests/integration/graphical_smoke/tests/smoke.pm` | `b4da46db25ddb6a7ba1ec46c949b0cf0e155c32be0f7ea343bf4516547a0c6a1` |
| `tests/unit/test_e2e_secret_variables.py` | `c4be53a88239696e1128d791d7088a97c643d89c22b4522ee1369439e0b513e3` |
| `tests/unit/test_e2e_worker_cleanup_safety.py` | `b059c7a004f8678da8707060e25fec6540e29159ba848b9e1511bcecfb8ce47c` |

Concurrent edits to AGENTS.md, approval/read-only tooling documentation and tests
were preserved. The broader pass includes those checkout inputs; no package or
current-source VM artifact is nominated. Only this slice's documentation changed
after its implementation checks. Reuse these host results only for matching
inputs; changed capture/distribution behavior still requires live qualification.

## Remaining work and no-loop boundary

Do not recreate this registry or re-investigate the password API next session.
Wire trusted fixture credential acquisition to the frozen registry and collector,
add verified masked-prompt assets (distribution staging currently accepts only
Perl), and integrate a public console transport for the harmless serial smoke.
No masked-prompt needles or live password calls were added here. The helper
refuses unmatched prompts and unmasked terminal surfaces; do not weaken this
contract to obtain a login. Preserve real authentication and lease ownership.

Then obtain a stable source window, build fresh artifacts and exercise the
smallest guarded live authentication/serial smoke with required safety checks.
Asset-transfer qualification remains unaccepted at **four** historical attempts;
there was no fifth attempt and no new source-blocked VM loop. Use the already
implemented transfer selector once stable, preserving the earlier failures.
All 156 E2E variants remain pending. Estimated remaining Task 19A work: **about
three sessions / 2–3 active hours**, plus any source-stability wait. The remaining
cost is live integration/qualification, not these completed host helpers.

All owned test commands exited. No VM, lease, worker backend, screenshot export
or live credential operation was started; no such operation needs recovery.
