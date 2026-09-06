# Task 19P descriptor transport and cleanup — 2026-09-06

**19P remains incomplete: no screen, input or SSH-observation stage completed.**
This slice proved automatic cleanup after graphics RPC disconnection, fixed a
specific outgoing AppArmor denial, and established cheap directional probes.
It did not resolve the live `openGraphicsFD` receive failure.

## Changes and proven boundaries

`graphical_lease.Adapter.open_display()` now opens a separate disposable libvirt
connection for graphics. It checks the fixed URI, UUID, domain ID and exact XML
against the guarded lease, then rechecks ownership after acquiring the FD.
Failures close/revoke owned sockets without closing the lifecycle connection.
Replacement and disconnect regressions use mocked domains and real sockets.
The live failures below both completed ordinary baseline cleanup; no separate
recovery command was needed.

The alternative public `openGraphics` API was evaluated with a caller-created
socket pair. A non-booting probe sends the impossible graphics index
`0xffffffff` while the fixed domain is off, so it cannot attach a display even
if an external actor starts the domain concurrently. Before the host policy
fix, its RPC disconnected (libvirt error 38). At 18:45:46 UTC the kernel logged
`apparmor="DENIED" operation="file_receive" class="net" profile="libvirtd"`,
requested/denied `send receive`, anonymous Unix stream, peer `snap.code.code`.
This directly proves the outgoing denial, unlike the earlier ptrace lead.

With user-approved installation, the versioned
`config/apparmor/onpc-graphical-tests` rule adds only anonymous Unix stream
send/receive with the exact `snap.code.code` peer to libvirtd's local policy.
The installer preserves site rules, compiles the whole proposed profile before
writing, and reloads only that profile. `setup.sh` installs AppArmor and invokes
this installer on clean development hosts. No ptrace grant, QEMU policy, daemon
restart, product package or application data change was made. Activation is
immediate policy reload; product activation classification is `none`.

Afterward the same outgoing probe returned the ordinary domain-off refusal
(error 55) and left the connection alive. The final non-VM probe also launched
one owned `aa-exec --profile=libvirtd` fixture, verified its enforced label, and
received one usable socket with the expected bytes and no truncated ancillary
data. The fixture changes neither the daemon nor its policy and uses existing
pidfd-owned command cleanup. Both directions passed:
`/tmp/onpc-graphics-transport-y6k4uz6a/result.json`. The final edit only adds
classified failure-summary retention; that failure branch was not exercised live.

These probes prove basic transfer, not the live graphics RPC. The final adapter
retains `openGraphicsFD(0, 0)` so libvirt creates the pair for QEMU, with normal
authentication flags. No speculative third full smoke was launched this slice.

## Live attempts and costs

Both used `pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_smoke`.
Earlier attempts 1–2 remain in [the original record](19P-Live-Smoke-2026-09-06.md).

| Attempt | Result | Preparation / backend / cleanup / total seconds | Root-private evidence |
| --- | --- | --- | --- |
| 3 | Caller-owned `openGraphics` failed receiving the FD in libvirtd, before the policy fix. Independent lifecycle connection completed cleanup. | 98.532 / 4.630 / 245.443 / 348.588 | `/tmp/onpc-graphical-smoke-czrlld79/result.json` |
| 4 | Original `openGraphicsFD` on the separate connection still failed receiving the FD in the client, after the policy fix. Cleanup passed. | 116.009 / 4.721 / 252.506 / 373.217 | `/tmp/onpc-graphical-smoke-yf1fj9sj/result.json` |

Both results preserve infrastructure failure, `collection: not-run`, empty
steps, `cleanup: passed` and lease phase `complete`. Cleanup includes the
bounded ACPI shutdown/fallback and restored-baseline verification. No product
was installed on the host or guest. No new VM, snapshot or overlay was created.
Around 40 minutes including approval waits, both cleanup operations and the
final cheap discriminating probe; context/usage telemetry was unavailable.

## Remaining question and next experiment

Why does the real graphics RPC lose/refuse its returned FD when both basic
directional probes pass? The 18:52:06–10 UTC kernel journal contains profile
load/status and VM-network events, **no new AppArmor denial**. The daemon reports
EOF when the client disconnects. Do not claim this proves a different LSM or
weakens the existing policy boundary. Libvirt's `virSocketRecvFD` also generates
`EACCES` when expected ancillary data is absent/malformed; the message alone
does not distinguish a syscall denial from missing `SCM_RIGHTS`.

Next build one small lease-owned graphics attachment diagnostic, with raw
syscall evidence confined to its private directory, to record `recvmsg` return,
control flags and descriptor presence. Compare the daemon-created and public
caller-supplied socket APIs under the same guarded attempt if needed. Verify
collection and failure cleanup locally before booting. This avoids repeating
distribution/worker qualification or the full graphical smoke just to diagnose
attachment. No further AppArmor permission expansion is justified by current
evidence. First actual screen/input/observation, safe evidence review and stable
qualification remain required before 19P acceptance.

## Verification and identities

Final `make check`: **1,114 unit/contract tests**, **17 components**, syntax and
stage traceability passed (14.33 s and 0.39 s for pytest stages). Latest dispatcher
safety selection: **148 passed, 3 subtests passed**. Installer tests cover site
rule preservation, idempotence, malformed blocks and compile-before-write failure.
Full proposed AppArmor profile compilation and kernel reload passed. `bash -n
setup.sh` and `git diff --check` passed. Final fresh read-only query confirmed
`ubuntu26.04` shut off; all owned commands finished. Concurrent product/UI edits
and Task 14's failures were preserved.

Host: `apparmor=5.0.2-0ubuntu1~26.04.1`,
`libvirt-daemon-system=12.0.0-1ubuntu5.3`; backend remains
`os-autoinst=5.1768577300.b85e4864-1`, test API 48. Both live results retain their
complete integration-source digest maps and baseline identity.

| Final file | SHA-256 |
| --- | --- |
| `tests/integration/graphical_lease.py` | `414f604c6afdd17140a39ee049d7cba0dc80d5d2b0ea51445ba04852e1c7db75` |
| `tests/integration/check_graphical_transport.py` | `a29bb02aea7ac0fc7f556351e23c6eb38de2d8a426dd79e10d6a4655ec749171` |
| `tests/integration/graphical_transport_fixture.py` | `2f3a37194914edd26d9374ada1bc735f9d0067e72b1870bdff8b2f2620ced7d9` |
| `tools/install_graphical_test_policy.py` | `76aa426d06d9c492ee04b03e9d7d4727cbf7eafbfd4376947cc5b160e0046f48` |
| `config/apparmor/onpc-graphical-tests` | `91d64e928fa579d669da91f168c44e1849ff0f09f98d3da9a551d761f04523dd` |
| `/etc/apparmor.d/usr.sbin.libvirtd` | `ddf1cf88e69644ad651a52ad743017307f624fc63d43926c8c94f3a79c78d3df` |
| `/etc/apparmor.d/local/usr.sbin.libvirtd` | `85708d3fb5a717e68556d0c09770d30a3d50c5e2359c02ec6dbf2c4dbd043c7c` |

Sources: [public graphics APIs](https://www.libvirt.org/html/libvirt-libvirt-domain.html#virDomainOpenGraphics),
[libvirt receive implementation](https://github.com/libvirt/libvirt/blob/v12.0.0/src/util/virsocket.c),
[libvirt AppArmor local include](https://gitlab.com/libvirt/libvirt/-/blob/master/src/security/apparmor/usr.sbin.libvirtd.in),
[AppArmor Unix policy grammar](https://www.apparmor.net/man/4.0/apparmor.d/).
