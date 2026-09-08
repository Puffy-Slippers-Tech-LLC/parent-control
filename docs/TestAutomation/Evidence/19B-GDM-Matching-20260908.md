# Task 19B — stable GDM and serial-return helper

**Solid progress:** the shared worker now recognizes GDM without the fixed
ten-second render delay, matches the intended empty password prompt after a
needle-relative click, rejects the list needle on that prompt, recognizes Escape
return, and matches GDM again after real serial logout. The corrected guarded
attempt passed through final exit 0. Task 19B and E2E-001 remain unfinished;
this is one helper qualification, not the three-run public scenario acceptance.

## Implemented and reviewed boundary

`tests/integration/graphical_smoke/lib/onpc_gdm.pm` uses the maintained public
`assert_screen`, `assert_and_click`, `current_console` and `select_console`
APIs. Initial recognition has a 90-second ceiling; subsequent matches have a
30-second ceiling. Small existing reviewed regions and 100% thresholds are
unchanged. Account needles now explicitly specify their interior relative
click points; staging rejects malformed, out-of-region and password-prompt
click points. The parser freezes these bytes with the worker distribution.

The initial worker explicitly selects `sut`. generalhw opening the VNC display
does not itself populate testapi's current-console identity. This distinction
is documented by the installed pinned API and covered by a regression starting
with an unset console. The [upstream public API](https://github.com/os-autoinst/os-autoinst/blob/master/testapi.pm)
defines console selection, bounded screen matching and needle click points.
No backend, lifecycle owner, host setup, needle pixels, product data or baseline
was changed. These test-helper edits activate on the next invocation (`none`).

Post-password explicit capture stays permanently sealed. Graphical-return
matching uses the public match's automatic private screenshot, not a reopened
capture route. `NOVIDEO=1` was confirmed; no video was generated or claimed
reviewed. Structured command observations verify real serial authentication,
the split-marker command output, logout, and absence of an unexpected user
session. Worker collection remains under the existing secret registry.

## Attempts and retained evidence

Both commands were `tools/run-tests integration check_graphical_serial` on the
existing development host and pinned VM. Each dispatcher first passed 445
isolated cleanup-safety cases and three subtests. No package build was needed.

| Attempt / handle | Result | Preparation / test / cleanup / total seconds |
| --- | --- | --- |
| 1 / 85525 | Failed at `gdm:console`, before the first screenshot: implicit backend display activation had not selected a public console. Source/host preservation and restoration passed. | 393.565 / 89.954 / 71.955 / 696.324 |
| 2 / 45005 | Passed after explicit `select_console('sut')`; all eight controller stages, positive/negative screen matches, serial command, truthful shutdown, collection and final preservation passed. | 383.597 / 107.249 / 70.230 / 700.307 |

Stage sums exclude finalization/provenance work. Corrected worker time was
36.694 seconds; preparation and preservation dominate the 11.67-minute
invocation. The two live attempts consumed 23.28 minutes. This slice exceeded
its initial 30-minute estimate to finish the demonstrated correction and safe
finalization. No token-usage telemetry was exposed. There was no unchanged
retry, third experiment, recovery, baseline recreation or ownership bypass.

Original failure:

- `/tmp/onpc-graphical-smoke-7nu82mbh/result.json`
- `/tmp/onpc-graphical-smoke-7nu82mbh/testresults/smoke-3.txt`
- `/tmp/onpc-e2e-evidence-0a49oecr/worker-result.json`
- Checkpoints: `/tmp/onpc-e2e-evidence-yayk8sg4`
- Source: `3f376073315284b17e0949b9da4c3b160a8becaef539cab77dbab78fb5896128`

Corrected pass:

- `/tmp/onpc-graphical-smoke-lmyu1g2o/result.json`
- `/tmp/onpc-graphical-smoke-lmyu1g2o/testresults/result-smoke.json`
- `/tmp/onpc-e2e-evidence-gs6n4o5v/worker-result.json`
- Checkpoints: `/tmp/onpc-e2e-evidence-f1k6ly7a`
- Source: `ea0b5c8c435c6c7b90bb1092d5caa20b0bd335d9c389069b32f33a436e64a26d`
- Distribution: `ad03a42c8adce99ab44d3465792ef75939a37135f5fe468c5bea7e63f5120e12`
- Baseline: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`
- Inventory: `dc5ccd5e954dc2f8b0ce188b1d89cde15865e4113cbab1244e220dc74f1456d4`

The corrected module's positive areas all have similarity 100. Its deliberate
list-on-prompt check has similarity 0 and does not authorize another input.
Private visual review of `smoke-1.png`, `smoke-6.png`, and `smoke-15.png`
confirmed initial GDM, the intended empty/focused/masked prompt, and GDM after
serial logout. Initial/return PNG SHA-256 is
`7fb03833a3c63c59cf6c6616599c6a692b2f53282439f0e77b928457db50a85e`;
prompt PNG SHA-256 is
`b0e945f602ac32dce467e5118f7d9f61f1faac21b5fa47306188c9ffaa50811e`.
The serial console does not change the graphical greeter, so an identical
return image is expected. Match evidence records the later console selection.
All three temporary exports were removed with `tools/cleanup-screenshots`;
raw images/logs remain private and have not been published as redacted evidence.

## Host verification and remaining work

The final focused selection passed 93 cases, including missing-screen refusal,
unsafe points, wrong consoles, real Perl flow, sealed capture and shutdown.
Final `make check` (27529) passed 2,521 unit/contracts in 36.75 seconds,
17 components in 0.37 seconds, syntax and stage traceability. This adds 19 cases.
The earlier broad check exposed missing APIs in the shutdown test double;
those were corrected before the successful run. Final `git diff --check` passed.

Both live handles and all host-check handles exited. Final `tools/test-vm status`
reported `state=5, id=-1`. No operation, review export or recovery is pending.
Only documentation changes follow these runtime inputs; fresh artifacts are
still required for a package-bearing public attempt.

Next implement E2E-001's ordered callback and screen-match evidence, retaining
the accepted serial/controller guarantees and avoiding duplicate ordinary
E2E-001/E2E-034 qualification. In particular, current `SERIAL_STAGES` stops at
`serial-logout`; graphical return is proven by the private worker module but
is not yet an independently acknowledged recorder stage. Integrate that exact
boundary without reopening generic post-authentication capture. Then run three
complete public qualifications and the task's final acceptance checks. Do not
rerun standalone helper qualification merely to start another session.
