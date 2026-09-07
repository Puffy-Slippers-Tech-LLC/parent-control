# Task 19A asset observation — 2026-09-07

This session fixed a booted-tree validation gap and added executed-probe host
coverage. Live transfer acceptance did not advance: concurrent checkout edits
invalidated the sole VM attempt before upload. No customer variant was executed.

## Retained attempt

| Operation | Result and evidence | Time |
| --- | --- | --- |
| Artifact build; handle 57059, exit 0 | `/tmp/onpc-test-artifacts-7a_9mvvo`; revision `9e36732b0c93e94f7b9406b2753a5fe8d536a489`; build/verification passed | A few seconds; exact total not retained |
| Transfer attempt 4 overall; handle 34617, exit 1 | `/tmp/onpc-graphical-smoke-_t5hw6cg/result.json`; checkpoints `/tmp/onpc-e2e-evidence-xgna8eq3`; `provenance:source-changed` before upload/worker | 298.235 s total; preparation 232.031411 s, cleanup 66.155450 s, test 0 |
| Focused host check; handle 22065, exit 0 | 28 transfer tests, including 12 new cases executing the guest probe | 1.52 s |
| Final `make check`; handle 66809, exit 0 | 2,150 unit/contracts; 17 private-D-Bus components; syntax/traceability | 40.18 s unit/contracts; 0.33 s components |

Build source SHA-256:
`21f728c48ef15b02b33242560162b3a5133c7082b744224495c62ac9df333658`.
Package SHA-256:
`dd069522d13b3fdd9ecee498dea95a69b7b6892154f977c2accc3eabbb4f6a84`.
Staged asset SHA-256:
`16e33e35c4f08e48fd77bea07afe033962e4838abc611f991d59d2671cd37d4a`.
Baseline SHA-256:
`cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
The artifact is historical and must not be reused for a new attempt.

The working tree was clean twice, including immediately after building, but
other work then changed `debian/postinst`, `docs/Package-Update.md`,
`tests/unit/test_installer.py`, and `tests/unit/test_package_configuration.py`.
Those edits were preserved. A clean status check does not establish that another
editing session has ended. The request to pause other edits received no answer
before handoff; no second VM attempt was launched.

The installed dispatcher passed 295 isolated safety tests and three subtests
before entering the lease. Source preflight passed; a held-lease recheck then
refused. Finalization retained that original failure, restored the baseline,
completed the lease, and reported host preservation true/source preservation
false. `tools/test-vm status` confirmed off (`state=5`, `id=-1`) at 23:07 UTC.
All command handles exited, with no outstanding worker or maintenance operation.

## Verified implementation progress

The booted probe checked file digests but silently ignored extra empty
directories. It now requires every directory to be an ancestor of an inventoried
file, consistent with offline provisioning. Count/digest receipts and private
evidence formats are unchanged. This is test-tool activation `none`, effective
on next invocation; no product installation or data migration changes.

New tests execute the exact `OBSERVE` program against real filesystem fixtures.
They map only the fixed guest root and root ownership into an unprivileged
fixture. Actual traversal, bytes, permissions, link counts and file kinds are
used. Cases cover receipt agreement, extra empty directories, ownership and
permissions, file/directory symlinks, hardlinks, FIFOs, and changed/missing/extra
files. Initial fixture path adaptation failed under Python 3.14 and was fixed;
the final 28-case result passed. This is host coverage, not live guest proof.

Final commands:

```sh
tools/run-unit-tests tests/unit/test_e2e_asset_transfer_cleanup_safety.py -q --tb=short
make check
git diff --check
```

Only documentation changed after the final runtime checks. The README also
corrects its stale statement about intentional tracked-file deletions. No
screenshots were produced; original logs and evidence were preserved.

## Avoid repeating the blocked loop

Do not start another package-bearing VM attempt based only on clean Git status.
Obtain a confirmed pause/end of the other editing work, finish local edits,
build fresh artifacts, and run one corrected qualification. The inventory-prefix
fix and the stricter booted probe still need live qualification. Historical
attempts remain failed and must not be counted as passes.

If other edits must continue, advance the independent host-side secret/capture
and harmless-console implementation instead; retain its live acceptance gate.
Reuse `e2e_worker.run_distribution`, `PrivateCollector`, the guarded transport,
and the established backend contract. Do not repeat backend/baseline discovery.
Remaining 19A estimate stays **2–3 sessions / 1.5–2.5 active hours**, plus any
source-stability wait. The new probe coverage closes a real gap, but the live
blocker prevents claiming a shorter completion forecast. This slice took about
12 minutes, including the five-minute failed attempt. Usage telemetry unavailable.
