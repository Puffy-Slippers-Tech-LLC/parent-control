# Task 20 — live command proof and shutdown deadline

## Result and scope

Attempt 10 completed every ordered VT6 authentication stage, including authorized
password submission, the pinned authenticated shell and the fixed nonsecret
command round trip. It then failed with `e2e:deadline` after power-off and before
normal worker shutdown verification. This is new live stage evidence, **not a
passing qualification or Task 20 acceptance**. Attempts 9 and 10 both restored
the baseline and passed source/host preservation and cleanup. All ten historical
authentication attempts remain failed.

Reuse the [VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal),
[worker shutdown contract](../../../tests/e2e/README.md#shared-guarded-worker) and
[reuse map](../Reuse-Map.md#installation-helper-and-open-limits).

## Reproduced cause and correction

Attempt 9 reached authenticated session and shell-identity observations, then
refused `vt6-auth:command-prepare-refused`. The standalone smoke controller loads
its E2E modules under a temporary import path and restores that path afterward.
`ReadOnlyObservations.vt6_command_boundary` imported `vt6_command` only at this
late stage. Pytest's permanent E2E path and already imported module concealed
the missing standalone dependency.

`test_command_boundary_survives_launcher_import_path_restoration` removes that
test-only path/cache advantage and reproduced `ModuleNotFoundError` before any
command transport call. The correction loads `CommandRoundTrip` with the other
observer dependencies at module import. The same test passes afterward; attempt
10 durably records both `vt6-shell` and `vt6-authenticated`. No input, ownership,
capture, marker or provenance guard changed.

The screenshot stable-identity correction now has live stage proof in attempts
9/10. The pinned foreground-shell correction passes live observation in 9 and
the completed shell stage in 10. Attempt 10 also executes the marker reader's
stable metadata comparison and the real keyboard command. These advances do not
erase either failed run or qualify normal worker shutdown.

## Retained attempts

Both used `tools/run-tests integration check_graphical_vt6_authentication`,
with fresh product-free inputs; no package build was required. Baseline SHA-256:
`cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.

| Evidence | Attempt 9 | Attempt 10 |
| --- | --- | --- |
| Command handle / exit | `57610` / 1 | `2665` / 1 |
| Result | `/tmp/onpc-graphical-smoke-skpwzp12/result.json` | `/tmp/onpc-graphical-smoke-gif62zbv/result.json` |
| Qualification checkpoints | `/tmp/onpc-e2e-evidence-s5lrxvtc/` | `/tmp/onpc-e2e-evidence-a4i94z5z/` |
| Worker result | `/tmp/onpc-e2e-evidence-urcvofeu/worker-result.json` | `/tmp/onpc-e2e-evidence-ua59m8jt/worker-result.json` |
| Source SHA-256 | `8582f7f4c0a2416a131bfdce06dd0d3f5cb64a7429d05163577172109fd2d860` | `4d497f7dd26e0bfc2f6ec2870c1d7cd3b916b0476701fd0f8649d3b7facbb6e0` |
| Total seconds | 1510.074 | 2110.510 |
| Preparation / test / measured cleanup seconds | 382.034 / 651.916 / 282.409 | 774.641 / 1132.911 / 69.752 |
| Worker seconds | 579.454 | 1036.426 |
| Last completed VT6 stage | `vt6-password-screen`; session/lineage observations followed | `vt6-authenticated` |

Total durations also include checks outside the named ledger timers. The private
worker reports retain `worker-execution-failed`; attempt 10's terminal
finalization additionally reports the original fixed `e2e:deadline` category.
Its backend exit status is null, lifecycle is `initial-off`, `poweron`, `poweroff`,
and `shutdown_verified` is false. No later `status-off` event was recorded.
This confirms deadline failure, not an authentication refusal. Both outer
results retain product/collection `not-run` and infrastructure `failed`.

Attempt 10's ten mandatory authentication baseline rechecks total **802.363
seconds**; source checks total **1.047 seconds**. Each stage and its input
provenance were durably recorded. The fixed prompt capture digest in both runs
equals the existing reviewed reference:
`63f310dff9a066270e8888af30ade4c65fc5e02af2604dc3bba53defff243f47`.
No raw authentication output or screenshot was exported or newly approved.

## Verification and cleanup

- The shared UI `request_display_scale` fixture was moved unchanged from a
  collected case into `tests/ui/conftest.py`, resolving the existing architecture
  failure while preserving unrelated frontend work. Architecture selection:
  **355 passed**. Guarded UI cases
  `test_request_layout_keeps_text_readable_and_controls_reachable[kiosk-fractional]`
  and `test_parent_expanded_legend_follows_content_height[1.25]`: **2 passed**.
- New import regression first failed as described above. Final affected selection
  (`test_e2e_vt6_command`, `test_e2e_vt6_controller`, `test_e2e_vt6_recipient`,
  `test_e2e_observation_transport`, `test_graphical_smoke`,
  `test_support_architecture`): **1,988 passed**.
- `make check` passed after the UI relocation (**7,326 unit/contracts, 58
  components**) and after the runtime correction (**7,327 unit/contracts, 58
  components**); stage traceability and the remaining common checks passed.
- Isolated safety before each attempt and each dispatcher's prerequisite repeat:
  **685 passed, 3 subtests passed** per run.
- Both leases reached `complete`; source and host preservation are true and
  cleanup passed. Workers stopped, callbacks and display descriptors closed,
  and the accepted baseline was restored. All commands exited. UI fixture
  teardown completed; no owned recovery obligation, temporary screenshot export,
  approval denial or Polkit denial remains. No checkout writes occurred during
  either guarded attempt. Only documentation changes followed final verification.
- Final documentation checks: **336 local links across six documents**, no
  missing targets, clean scoped whitespace checks, and exactly one supported
  settings line in Continuation. The authoritative checklist remains unchanged.

## Next bounded result

Reproduce the worker deadline with a delayed synchronous shutdown callback using
the existing clock/worker doubles, then make its finite budget account for the
required authentication rechecks and normal shutdown/off observation. Reuse
`e2e_worker.run_distribution`, `CallbackServer.serve_once`, `Adapter`,
`Lease.stop`, `test_timeout_refuses_and_cleans_up` and the shutdown regressions.
Inspect the existing worker timeout and callback contract together; no further
generic diagnostic or prompt collector is needed. Preserve full provenance and
ownership validation, bounded operation waits, failure retention and refusal of
unfinished shutdown. Do not simply rerun the unchanged 960-second attempt.
After correction and focused/safety checks, qualify the same guarded route through
normal worker exit and final preservation. Only then advance to sudo/notice
pixels and the complete installation/reboot/startup journey.

The session used `gpt-6-astra` / `xhigh`, Standard, consuming the renewed one-slice
override. The overrun was the two guarded attempts and their full cleanup; the
second corrected the locally reproduced first failure. No third attempt began.
Task 20 remains earliest ready; all-task VM clearance persists. Next settings:
`gpt-6-astra` / `high`, Standard, for the remaining deadline/shutdown ownership
boundary; authenticated command behavior is now evidenced.
