# Task 19P — Screen and input compatibility

Task 19P is accepted: three consecutive complete corrected-input smokes passed
with all intended captures privately reviewed. The supported
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
| 13 | Complete corrected-input smoke passed; private review confirmed all three states. | 113.623 / 36.558 / 71.833 / 222.031 | `/tmp/onpc-graphical-smoke-l_0524mo` |
| 14 | Complete corrected-input smoke passed; private review confirmed all three states. | 109.041 / 37.121 / 72.128 / 218.304 | `/tmp/onpc-graphical-smoke-wb7zkkro` |

Smoke 9 recorded 1024×768 stage digests: GDM
`f890e6aac9a2f62d05b225e97ee59e38d1cd448e3caf19d44111d4c43b359c8b`,
selected credential screen
`3e412773995763791de05c6bfcf239a88ffb9a901329d9593720f9431f2a90e2`,
and dismissed greeter
`b17ef4025f696ab86432ef08658c722417482716cc73a6d2f039251611b09dae`.
Private review of smoke 8 established the intended selected and dismissed
semantics. Its temporary owner-readable copies were removed through
`tools/cleanup-screenshots`; raw captures remain root-private.

The pre-settling passing run used `os-autoinst=5.1768577300.b85e4864-1`, test API 48,
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

Smoke 13 also completed normally with `lease_phase=complete` and passed
infrastructure, collection and cleanup outcomes. The earlier handoff incorrectly
called this run interrupted: the agent discarded the command session metadata,
then interpreted intermediate observations as a stale controller. The duplicate
invocation at `/tmp/onpc-graphical-smoke-020hix7s/result.json` correctly failed
with `state:busy-controller` before acquiring the lease. It did not boot or
mutate the VM and is retained as a separate failed invocation, not a smoke
qualification. No controller recovery, lock removal or process signal was
needed. The original run's final result disproves the claimed controller defect.
The workflow now explicitly requires retaining and polling command handles.

Smoke 13's privately reviewed GDM, selected and dismissed capture digests are
`a79679d38a2254934e3167f0c5aaaf40ba696619ccd5910c9dc221f443563e89`,
`3819063de49c170b342d2540e86618da6e94b30b6d1bb1e2d98161b3ec38e0b7`, and
`d97ac7ba9989685c4b0deae49627ab2abb7d2652b9c8b60ac930c9ddc81815a0`.
The three exports were removed with `tools/cleanup-screenshots` after review.

Smoke 14's GDM, selected and dismissed capture digests are
`6ea81650f72e14adfa1c480978cc161d4ae58685529f48178d883b3e850c97b4`,
`ce077e0f492256c42860bc283a0d7484e39ca475db5c5f0f50ca4d50ab2e43d1`, and
`b55e7a7aa19a7d93ad3a2f035dc94ed9fb84bd7f56648da168d1fcd1f392a9c2`.
The export hashes matched the result's stage hashes; private review confirmed
the account list, empty password prompt and returned account list. All three
temporary exports were removed through `tools/cleanup-screenshots`.

A structured comparison of the three complete `result.json` files (12–14)
confirmed identical full `inputs_sha256` maps, baseline identities and backend
package versions. Each recorded `outcome=passed`, `lease_phase=complete`, and
passed infrastructure, collection and cleanup outcomes. Corrected `smoke.pm`
SHA-256 is `6b92862e73fb69e2849a121439c224bfc23d9fd33531c859469a15eaee20459a`.
The current-input guard also checked the source map at the end of each smoke.

## Acceptance verification

- Focused smoke/worker unit selection: 45 passed.
- Each live attempt's isolated dispatcher prerequisites passed; the stable run
  used the current expanded set of 175 tests and three subtests.
- Final `make check`: 1,190 unit/contracts (13.61 s) and 17 components (0.30 s)
  passed, along with syntax and stage traceability. This includes all 28 focused
  smoke tests and the worker/lease/cleanup regressions.
- `git diff --check` passed after the completion documentation changes.
- All three stable runs completed with `lease_phase=complete`, all infrastructure,
  collection and cleanup outcomes passed, and the VM restored and shut off.

The required three consecutive full corrected-input smoke successes are accepted.
The separate busy-controller refusal did not start a smoke and is not counted
toward qualification. Smoke 8 remains a failed integrity attempt and smoke 11
remains semantically rejected. These are feasibility results; `product=not-run`
is intentional and no customer E2E or release pass is claimed.

This session completed the two outstanding capture reviews and final live
attempt. Smokes 13–14 used 222.664 s preparation, 73.679 s test and 143.960 s
cleanup (440.335 s total). Agent waiting/diagnosis and host authentication add
unmeasured overhead; context/usage telemetry was unavailable. No product or
test implementation change was needed. The workflow correction prevents losing
command handles from turning normal asynchronous progress into another false
recovery investigation. Task 14 is next; 19A/19B retain full runner, secret-safe
capture, scenario inventory and needle-based matching work.
