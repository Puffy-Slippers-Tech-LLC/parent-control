# Task 19P — Screen and input compatibility

The graphical feasibility smoke has its first complete corrected-input pass. The supported
generalhw backend controlled the existing lease-owned VM through the public
libvirt graphics FD, captured the real guest greeter, selected a large user tile
with VNC mouse input, observed the credential screen, dismissed it with Escape,
and returned to the greeter list. No credential was entered and the fixed SSH
observer continued to report an active greeter with no non-observer user session.
Collection, baseline restoration, host-state verification and cleanup passed.

## Root cause and fix

Moving the pointer to the original small status icon caused no semantic change.
A large fixed-baseline tile then produced a changed framebuffer, proving the
mouse event reached GDM, but os-autoinst failed while decoding the update:
`Error in VNC protocol - relogin: not read enough data`. The exception comes from
the pinned client's 16-bit ZRLE path after its initial full frame had succeeded.

The generalhw backend officially exposes `GENERAL_HW_VNC_DEPTH`; its documented
default is 16. The smoke now selects depth 32, using the backend's existing
rgb888 path without changing the public VNC, libvirt or lease interfaces. See
the [upstream generalhw variable contract](https://github.com/os-autoinst/os-autoinst/blob/master/doc/backend_vars.md#generalhw-backend).
The test clicks the first large tile on this fixed product-free baseline; Task
19B owns later needle-based screen matching. This change has activation `none`,
adds no host package or product integration, and changes no saved application
data.

## Attempts and retained evidence

| Smoke | Outcome | Preparation / test / cleanup / total seconds | Root-private directory |
| --- | --- | --- | --- |
| 7 | Large tile click reached a changed frame; 16-bit ZRLE decode failed; cleanup passed. | 97.138 / 27.105 / 66.740 / 190.998 | `/tmp/onpc-graphical-smoke-n4cvanbk` |
| 8 | All input stages passed; source-integrity guard caught a concurrent `prepare_vm.py` edit; cleanup passed. | 124.111 / 29.112 / 67.249 / 220.487 | `/tmp/onpc-graphical-smoke-pes8mg6r` |
| 9 | Complete stable-input smoke passed. | 107.181 / 28.243 / 70.768 / 206.230 | `/tmp/onpc-graphical-smoke-aohv8xui` |
| 10 | Complete pre-settling smoke passed; private review confirmed all three states. | 132.661 / 27.861 / 66.093 / 226.630 | `/tmp/onpc-graphical-smoke-8kjmfjg3` |
| 11 | Executable checks passed, but private review rejected the GDM capture because it still showed the boot splash. | 111.437 / 25.795 / 70.296 / 207.543 | `/tmp/onpc-graphical-smoke-_1vougc_` |
| 12 | Complete corrected-input smoke passed; private review confirmed all three states. | 105.018 / 36.342 / 62.688 / 204.061 | `/tmp/onpc-graphical-smoke-r23h3m2c` |

Smoke 9 recorded 1024×768 stage digests: GDM
`f890e6aac9a2f62d05b225e97ee59e38d1cd448e3caf19d44111d4c43b359c8b`,
selected credential screen
`3e412773995763791de05c6bfcf239a88ffb9a901329d9593720f9431f2a90e2`,
and dismissed greeter
`b17ef4025f696ab86432ef08658c722417482716cc73a6d2f039251611b09dae`.
Private review of smoke 8 established the intended selected and dismissed
semantics. Its temporary owner-readable copies were removed through
`tools/cleanup-screenshots`; raw captures remain root-private.

The passing run used `os-autoinst=5.1768577300.b85e4864-1`, test API 48,
baseline SHA-256
`cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`,
`check_graphical_smoke.py` SHA-256
`925cc1979a3a065e2ee26e1203497d5e0524c3d67b289ed44aa7f5169a788ff5`,
and `smoke.pm` SHA-256
`4513c43a9312219242d2f2180de0f73ef866bd4d8312c994c6bfa934d8813380`.

Smoke 11 demonstrated that the active greeter observation can precede Plymouth's
visible display handoff. The fixed-baseline feasibility module now allows ten
seconds for rendering before its stable-screen capture. Task 19B still owns
needle-based readiness. Smoke 12 recorded GDM, selected and dismissed digests
`1d2ce41a3b91df1ceb5c7b4d474787dd9599e8ee7f5721d3fa749070a5a309bc`,
`1e9160931bc6f27f6bb54846e3b9528199ccf00b72394c383a2d936051fb8e23`, and
`80fa0b288ae359fbd14ba88616ad894e8f802b93c18958116f2db2d0caf3c17c`.
Temporary review exports from attempts 10–12 were removed with the guarded
cleanup helper.

## Verification and remaining qualification

- Focused smoke/worker unit selection: 45 passed.
- Each live attempt's isolated dispatcher prerequisites passed; the stable run
  used the current expanded set of 175 tests and three subtests.
- `make check`: 1,152 unit/contracts and 17 components passed, along with syntax
  and stage traceability.
- The stable run completed with `lease_phase=complete`, all infrastructure,
  collection and cleanup outcomes passed, and the VM restored and shut off.

One of the required three consecutive corrected-input smoke successes is
recorded. The next session must run two more attempts without source changes,
privately review their captures, and then finish 19P acceptance. Smoke 8 remains
a failed integrity attempt and smoke 11 remains semantically rejected.
