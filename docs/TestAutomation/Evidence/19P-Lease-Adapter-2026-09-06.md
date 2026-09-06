# Task 19P lease adapter — 2026-09-06

This slice implements and verifies the controller side of the graphical
adapter. **No live graphical attempt ran; 19P remains incomplete.** The backend
tool installation/preflight from the [previous slice](19P-Backend-Preflight-2026-09-06.md)
was reused. No host dependency or product configuration changed.

## Implemented boundary

`system_runner.Lease(..., graphics_type='vnc')` creates a VNC display with
`listen type='none'` while retaining existing disk, baseline, exclusive lease,
and host-sharing checks. Its default installed-system configuration remains
SPICE. Every VNC lease guard rejects display replacement, additional displays,
TCP/Unix listeners, automatic ports, and unexpected graphics attributes.
Libvirt documents [non-listening graphics](https://libvirt.org/formatdomain.html#graphical-framebuffers)
and the public [openGraphicsFD API](https://libvirt.org/html/libvirt-libvirt-domain.html#virDomainOpenGraphicsFD).
The adapter uses index zero, flags zero, and checks ownership before and after
acquiring the descriptor. This public API path is source-backed; its execution
against the real VM is still unproven.

`graphical_lease.Adapter` maps the public generalhw initial off/on/final off
sequence to the existing lease. Initial off validates an already-off guest;
later off invokes the extracted `Lease.stop()` with recorded-instance checks
and the existing bounded shutdown behavior. It never restores a baseline
between callbacks, and rejects a second start in the same smoke attempt.
Outer `Lease.finish()` still restores and verifies the baseline and original
configuration. Tests cover changed domain IDs, run markers, listeners, and
missing source disks before controls, plus replacement during FD acquisition.

`CallbackServer` services bounded root-only Unix `SOCK_SEQPACKET` requests from
the lease owner's thread. It checks the private directory identity, kernel peer
UID, run token, packet length, and allowed verb. Graphics replies transfer one
descriptor with `SCM_RIGHTS`; the controller retains a socket whose shutdown
revokes the transferred connection. Ownership loss, failed replies, stop, and
server close revoke the display. No process discovery or process signalling
was added. Call `serve_once()` repeatedly and `close()` in the outer controller's
finally block; closing the server does not replace lease cleanup.

`lifecycle_variables(socket_path, run)` emits the documented
[generalhw command variables](https://github.com/os-autoinst/os-autoinst/blob/b85e4864/doc/backend_vars.asciidoc)
for `/usr/bin/python3 -B .../graphical_lease.py --socket ... --run ... on|off|status`.
Status returns 0 for off and 1 for on; protocol failures return 2. These scripts
have no libvirt connection. Paths that the backend's space-splitting argument
parser cannot represent are refused. Raw request data, paths, XML, and exception
text are excluded from the adapter's diagnostic events.

## Verification and inputs

| Check | Result |
| --- | --- |
| Existing six isolated cleanup-safety modules listed in `tests/README.md` | 49 passed, 3 subtests passed; 0.74 s |
| `/usr/bin/python3 -B -m pytest tests/unit/test_graphical_lease.py -q` in isolation | 54 passed; 0.33 s |
| Focused adapter plus existing system-runner tests before the last five test additions | 130 passed; 0.46 s |
| `make check` on final code/test inputs | 989 unit/contract tests and 17 private-D-Bus component tests passed; syntax and stage traceability passed |
| `git diff --check` | Passed |
| Read-only final `virsh --connect qemu:///system domstate ubuntu26.04` | `shut off` |

The first focused invocation was denied by the sandbox while wrapping socket
descriptors. The authorized outside-sandbox rerun proved descriptor operations
work. Two missing-disk tests initially expected only the runner exception;
the existing canonical-path check instead raises `FileNotFoundError` before
any control. Their expectations were corrected. No production bypass or host
configuration change was needed. Real socket tests use `SCM_RIGHTS` transfer,
data exchange, and revocation; VM calls and privileged RPC peers are mocked.
The root-only server has not been exercised by a live worker.

Base revision: `f9bae49189f99eec3a3dcdad1935bb85b8f93a64`. Final code identities:

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_runner.py` | `1261f7a966ce81f9e3b0e5ce7885265f4ad7b949f2065363ea071eee6104fa98` |
| `tests/integration/graphical_lease.py` | `c05a43fb1709b5c863ed3cc52354c142c8aa5e50dc25c37f86ae99425711fc0b` |
| `tests/unit/test_graphical_lease.py` | `41c750191040cb737adb3e8a06c1f9003dab80158a4606327da4a36df7001246` |

Approximately 25 minutes for design, implementation, and focused verification;
the aggregate unit/component phases took 13.10 s / 0.39 s. VM preparation,
live test, and VM cleanup time: zero. Exact context/usage telemetry unavailable.
All commands finished; no controller, worker, or owned VM operation is pending.
Concurrent publishing/compliance edits were preserved.

## Remaining boundary

generalhw still needs TCP VNC. The proposed bridge must place that TCP listener
and worker in a private network namespace, connect only to the lease-issued FD,
and keep the host without an exposed guest display endpoint. Worker subprocess
lifetime and interruption cleanup must be qualified without inferred process
ownership. Neither the bridge nor worker supervisor/launch command exists yet.

Next: implement and qualify that worker/bridge boundary with a non-VM success
and forced-interruption test, then wire the adapter into a guarded attempt.
Only after those checks pass run the smallest GDM/menu keyboard/mouse/screenshot
and read-only observation smoke. Guest observation transport, safe screen
collection, actual backend compatibility, and clean live cleanup remain
unproven. Expensive VM attempts spent on 19P: **0**. Do not repeat the solved
tooling investigation or mark 19P complete on these local results.
