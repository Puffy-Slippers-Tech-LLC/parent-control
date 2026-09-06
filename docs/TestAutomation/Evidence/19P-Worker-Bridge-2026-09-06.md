# Task 19P worker and bridge — 2026-09-06

This slice qualifies private namespace containment and a byte bridge with
non-VM fixtures. **No os-autoinst graphical attempt or VM boot ran. Task 19P
remains incomplete.** Reuse the earlier [controller adapter](19P-Lease-Adapter-2026-09-06.md)
and [tool preflight](19P-Backend-Preflight-2026-09-06.md).

## Implemented boundary

`graphical_worker.py` starts a trusted backend command using public util-linux
`unshare --mount --net --pid --fork --kill-child=KILL --mount-proc --propagation
private`. The controller pins its directly spawned supervisor with a pidfd
before releasing a socket start gate. Namespace init verifies changed network,
PID and mount identities and its private `/proc` before enabling loopback and
creating the TCP listener. It creates no host TCP listener. Only the control
socket descriptor crosses the initial spawn; the backend inherits neither
that descriptor nor the VM lease lock. The environment excludes the host
desktop/session variables.

The documented [unshare lifetime options](https://man7.org/linux/man-pages/man1/unshare.1.html)
and [PID namespace init behavior](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html)
provide the cleanup boundary. Controller EOF normally exits namespace init;
a bounded fallback signals only the recorded supervisor pidfd. On supervisor
death, `--kill-child=KILL` ends init, and the kernel removes its namespace
members. Cleanup never discovers or signals host processes by names, a process
scan, or inferred ancestry. A failed cleanup wait retains the pinned identity
for owned recovery. This is containment for trusted root test tooling, not a
hostile-code sandbox.

The bridge binds `127.0.0.1:5900` in that private network namespace. On a
connection, it requests exactly one connected stream FD from the root-only
lease callback service, rejecting failed/truncated/extra-FD replies and closing
received descriptors on failure. It relays bytes with bounded 256 KiB buffers
per direction and no content capture. All VM calls remain in the controller's
callback loop. Raw backend output stays in a root-private working directory.
Actual VNC semantics and libvirt endpoint normalization still need the VM smoke.

The [integration guide](../../../tests/integration/README.md#graphical-adapter-under-development)
documents the worker/controller interface and close order. `setup.sh` and the
test-tool inventory now explicitly pin the already-installed
`util-linux=2.41.3-3ubuntu2.2` and `iproute2=6.19.0-1ubuntu1.1`. No tool installation
was needed. These development-only tools activate on their next invocation
(`none`); no product service, saved data, or package integration changed.

## Experiments and verification

The first attempted privileged invocation used a relative script path; pkexec
changed its directory to `/root`, so no test started. The subsequent absolute
invocation was interrupted at approval, with no fixture evidence directory
created. Work resumed through the newly supplied approved project dispatcher:

```sh
pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_worker
```

The check accepts no CLI arguments. Its namespace-only subprocess fixture is
in `graphical_worker_fixture.py`. It sends 1 MiB through the bridge and echo FD,
then transfers pidfds for itself and its explicitly spawned child to prove
both identities alive before the requested completion/interruption and exited
after cleanup. It uses no libvirt imports or VM controls.

| Attempt | Result and retained evidence |
| --- | --- |
| Initial fixture | Normal exit passed, 0.553 s. Forced interruption failed the collector's immediate two-pidfd readiness assertion. `/tmp/onpc-graphical-worker-vq3uqbar/result.json` preserves the failure. |
| Corrected fixture | Normal exit passed, 0.530 s; controller disconnect passed, 0.443 s; forced supervisor SIGKILL passed, 0.428 s. Every case transferred 1,048,576 bytes and confirmed both recorded processes exited. `/tmp/onpc-graphical-worker-ics8m0p6/result.json`. |

The first assertion mistook `select()` returning for *one* exited process for
the completion deadline. The fix waits until every recorded pidfd is ready
or the deadline expires; a regression supplies separate readiness events to
verify this. The corrected result establishes cleanup for the tested cases;
it does not rewrite the original failed attempt. This was two cheap non-VM
fixture invocations, not repeated VM smoke qualification.

Focused worker tests: **29 passed** (12 isolated cleanup and 17 transport/result
tests). The final dispatcher invocation automatically ran **118 cleanup/adapter
tests and 3 subtests**, all passed, before its privileged operation. The earlier
adapter-only sandbox run hit socket descriptor restrictions; its authorized
outside-sandbox rerun passed all 54 tests. Final `make check` passed: **1,032
unit/contract tests** in 15.06 s, **17 components** in 0.45 s, syntax and stage
traceability. `bash -n setup.sh` and `git diff --check` passed.

Base revision: `f9bae49189f99eec3a3dcdad1935bb85b8f93a64`. Tested uncommitted
input identities:

| File | SHA-256 |
| --- | --- |
| `tests/integration/graphical_worker.py` | `c6772ffc2935b400f790d04029d67e78be1c55716f946a03e593c200d7e1034d` |
| `tests/integration/graphical_worker_fixture.py` | `ad3ad054fbf5d640890a30a2f2f03d61295fdd8a2f290d3b3c152eb9d7fa3a7c` |
| `tests/integration/check_graphical_worker.py` | `44de1600808c8209ff9a54b6b861a36de44ddc92ef6e55f6835ab3be93b7e1ab` |
| `tests/unit/test_graphical_worker.py` | `7ab38c5a511c8403e254ee6c86d0f5ae801bef780f0070757ab6d0143c358d40` |
| `tests/unit/test_graphical_worker_cleanup_safety.py` | `da0f964a2e94054bfcce094cdc841c91dbda115fda2faceb0c3094a2a875683e` |
| `setup.sh` | `107ef3c7986b4b760f6d0d1b17ad5c27665debb2f43828e3917a3e6d9b73e1a0` |
| `tests/test-tools-ubuntu-26.04.txt` | `7f042998e8d4c6abad3db6e8309cdc17b41b86a2d817298ccee6443d928eb2db` |

Approximately 30 minutes including a roughly ten-minute approval/interruption
gap; about 20 minutes active implementation, verification and handoff work.
Final fixture bodies totaled 1.401 s, and their safety prerequisites took
1.63 s. No VM preparation/test/cleanup time. Exact context/usage telemetry is
unavailable. All owned fixture commands finished. A fresh read-only domain
query confirmed `ubuntu26.04` shut off. Concurrent publishing and test-dispatcher
changes were preserved.

## Next boundary

Wire the worker, lifecycle variables and callback service into one guarded,
credential-free generalhw distribution and fixed `check_*.py` smoke. Establish
real libvirt graphics-FD compatibility, guest keyboard/mouse and screenshot
evidence, and a supported fixed read-only observation. The guest remains owned
by the existing exclusive lease throughout. Do not repeat tooling/namespace
qualification unless its inputs change. Live expensive attempts spent: **0**.
