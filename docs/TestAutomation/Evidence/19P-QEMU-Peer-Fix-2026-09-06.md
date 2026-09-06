# Task 19P — QEMU graphics descriptor fix

The graphics attachment blocker is fixed in the development-host policy and
reproduced by `setup.sh`. The unchanged public `openGraphicsFD(0, 0)` adapter
opened the display and the os-autoinst VNC client connected in the real guarded
VM. The corrected observation then passed and the first 1024×768 guest greeter
screen was captured, with automatic cleanup complete. These are solved transport
and observation boundaries; do not repeat their investigation. The complete
smoke still fails at the subsequent mouse-change assertion, so 19P is incomplete.

## Cause and implementation

The attachment-only diagnostic compares both public libvirt graphics APIs in
one exclusively leased boot. It retains a root-private, receive-only strace and
checks for the VNC protocol greeting. Its child has a deadline; the identity-owned
tracer uses `--kill-on-exit`. The parent retains the existing VM lease and alone
owns lifecycle operations. No new VM, snapshot, overlay or public listener is
created. `strace=6.19+ds-0ubuntu5` is recorded in setup and the tool inventory.

The first trace showed `recvmsg = 1`, `msg_controllen=0` and `MSG_CTRUNC`.
Libvirt synthesizes `EACCES` for missing ancillary data; this was not a syscall
returning that errno. The caller-supplied API reached QEMU, whose `getfd` reported
no `SCM_RIGHTS`. Startup profile loads exhausted the kernel's audit burst. A
second diagnostic's fixed six-second quiet window before each API retained the
exact denials: `file_receive`, the fixed guest's `libvirt-<UUID>` profile,
anonymous Unix stream, denied `send receive`, peer `snap.code.code`. Both APIs
hit that same missing QEMU permission. These diagnostic waits are not daily
test readiness or product-duration waits.

AppArmor rechecks both peers when a socket descriptor changes hands and merges
the receiving label into the socket context. The earlier libvirtd-only fixture
therefore did not prove the later QEMU/client transfer. The new versioned
`config/apparmor/onpc-graphical-qemu-tests` permits only anonymous stream
send/receive with the exact classic Code snap peer. It adds no named socket,
listener, file, execution or ptrace permission.

The installer uses the maintained `abstractions/libvirt-qemu.d` include,
compiles the proposed abstraction before writing, preserves site rules and
refuses unsafe files/directories. It does not reload existing guest profiles;
libvirt applies the drop-in at the next guest start. This is development-only
integration, product activation `none`, with no product data migration.
For future installations/refreshes use `./setup.sh` as required by `AGENTS.md`.
The earlier installation completed despite its interrupted tool reply; the
installed root-owned drop-in was read back and matched the prepared rule. A
subsequent redundant setup invocation was stopped at its first sudo prompt.

## Attempts and retained evidence

Earlier four failed full smokes remain in the preceding evidence records.
Original failures below remain failed even after the fix.

| Attempt | Result | Preparation / test / cleanup / total seconds | Root-private directory |
| --- | --- | --- | --- |
| Attachment diagnostic 1 | Both APIs failed; truncated descriptor trace retained; cleanup complete. | 73.562 / 0.156 / 254.395 / 328.132 | `/tmp/onpc-graphical-attachment-31r5kogw` |
| Attachment diagnostic 2 | Both APIs failed; exact QEMU peer denials retained in the kernel journal; cleanup complete. | 63.811 / 12.191 / 64.705 / 140.722 | `/tmp/onpc-graphical-attachment-u4i2d_nn` |
| Full smoke 5, after policy fix | Display opened, VNC connected and SSH ready; greeter observation rejected; cleanup complete. | 98.361 / 101.855 / 74.224 / 274.394 | `/tmp/onpc-graphical-smoke-j7hd4bqs` |
| Full smoke 6, after observer fix | `ready` and `gdm` passed; first screen captured; `smoke:mouse-no-change` failed; cleanup complete. | 107.110 / 38.701 / 71.966 / 217.790 | `/tmp/onpc-graphical-smoke-8t1e05la` |

The fifth smoke exposed an observation bug: its root SSH connection creates a
logind user session, which the original assertion rejected. The corrected
assertion excludes only root, remote, `sshd`, non-graphical observation sessions.
Other users, local sessions, and inactive/remote graphical user sessions remain
rejected. Timeout output now contains only three diagnostic booleans. Seven
executable observation regressions cover the exclusion and denials without
exporting session IDs or names.

The sixth smoke live-verified that correction. Its `steps.json` retains the
passed `ready` and `gdm` steps and screen SHA-256
`90aa716b82096046467811a2e5d0ba7b709d7344b300e0fa4d63dd8b09162adb`.
The overall failed `result.json` has an empty top-level `steps` array because
`run_backend` raised; use the separately retained stage evidence, not that array,
when diagnosing the completed fragment. `testresults/smoke-7.txt` identifies
`smoke:mouse-no-change` at distribution line 39. The installed public API accepts
the positional `mouse_set` call and documents the boolean return of
`wait_screen_change`; neither is an API-signature bug. Next review the retained
before/after PNGs and backend timing privately to distinguish a missed menu click
from a screen-comparison issue before changing coordinates or thresholds. One
attempt has reached this new boundary. Do not rerun FD diagnostics or change
confinement to investigate it.

All four completed live operations consumed 961.038 seconds. Authentication and
interruption waits extended the session beyond its initial estimate; it finished
the corrected bounded operation and cleanup. Context/usage telemetry was not
available. A final read-only query confirmed the fixed VM shut off. No command,
authentication request or VM operation remains pending. Task 19's active handoff
records the next slice and reassessed settings.
Raw captures and command output remain root-private and are not approved for
public export. Full per-attempt source maps and baseline identities are in each
`result.json`.

## Verification

The focused policy/attachment/lease/smoke selection passed 102 tests before the
observation change. Its seven new observation cases also passed. Final
`make check` passed 1,137 unit/contracts and 17 private-bus components, plus
syntax and stage traceability (14.26 and 0.45 seconds for pytest). The dispatcher
ran 162 cleanup/lease prerequisites and three subtests in isolation before each
live operation. `bash -n setup.sh` and `git diff --check` passed.

| Changed input | SHA-256 |
| --- | --- |
| `config/apparmor/onpc-graphical-qemu-tests` | `e36737d5a7ad7b1f1c33a2ed65bae49932aca887d0f956eb948a5b138686bb0b` |
| `tools/install_graphical_test_policy.py` | `5569d059cab43170fc0a424e13c3656aa0dbfc06344ed87b30b6e83b5e7af7e9` |
| `tests/integration/check_graphical_smoke.py` | `76779e06e304a28937b9eb013e766a13869e446a1e86bc7750c1ff7a63664285` |
| `tests/integration/check_graphical_attachment.py` | `b3041cc6113424213883cf45bf76ea7359cd9246b57cdb44305a670fa5a19725` |
| `tests/integration/graphical_attachment_probe.py` | `30344e96178e4f28f4d6e69f75e5df707a4fed1221edfbcc90aba9c85dfc3c9b` |

Primary implementation references:
[libvirt public graphics APIs](https://libvirt.org/html/libvirt-libvirt-domain.html#virDomainOpenGraphics),
[libvirt 12 receive handling](https://github.com/libvirt/libvirt/blob/v12.0.0/src/util/virsocket.c),
[libvirt QEMU graphics handling](https://github.com/libvirt/libvirt/blob/v12.0.0/src/qemu/qemu_driver.c),
[Linux AppArmor socket revalidation](https://github.com/torvalds/linux/blob/v6.19/security/apparmor/af_unix.c).
The installed Ubuntu abstraction explicitly provides `abstractions/libvirt-qemu.d`
and marks the older `local/abstractions/libvirt-qemu` include deprecated; the fix
uses the supported directory.
