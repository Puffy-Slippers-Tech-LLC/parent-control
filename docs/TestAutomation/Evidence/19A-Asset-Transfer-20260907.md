# Task 19A asset transfer — 2026-09-07

This session implemented the asset boundary and exercised actual guest uploads.
It did **not** achieve a complete passing transfer qualification or accept 19A.
All 156 customer variants remain pending. The final inventory-prefix fix is
host-tested only; another live run needs stable shared checkout inputs.

## Implemented boundary

`AssetTransfer` uses the existing lease and offline `mounted_guest` to upload
controller-verified package/fixture files through public libguestfs APIs. It
opens pinned host file descriptors, checks every copied digest, and refuses
stale inputs, inconsistent manifests/package aliases, existing destinations,
incorrect trees, and repeat provisioning. A fixed read-only SSH probe checks
the booted files before the graphical ready acknowledgement. Neither copying
nor observation installs the product or sets product state. The outer runner
retains checkpoint history and owns all restoration and release operations.

The existing category now accepts:

```sh
tools/run-tests artifacts build
tools/run-tests e2e --qualify-transfer --artifacts /tmp/onpc-<new-build>
```

The qualification flag rejects scenario/list selectors and leaves pending
dispatch closed. `./setup.sh --test-tools-only` refreshed the installed
dispatcher successfully. Its existing category-wide approval already covers
the option. No additional approval prefix is needed. Test-tool activation is
`none` (next invocation), with no product data or schema change.

## Experiments and retained failures

| Attempt | Inputs and evidence | Result / measured seconds |
| --- | --- | --- |
| 1; command 79955, exit 1 | Artifacts `/tmp/onpc-test-artifacts-6e9v_n9d`; report `/tmp/onpc-graphical-smoke-kxrjoe8o/result.json`; checkpoints `/tmp/onpc-e2e-evidence-71835pny` | Refused `provenance:package-source-mismatch` before upload/worker. Preparation 187.193; test 0; cleanup 69.148; total 256.391. |
| 2; command 6291, exit 1 | Artifacts `/tmp/onpc-test-artifacts-1v9nv__0`; report `/tmp/onpc-graphical-smoke-hai7u4ru/result.json`; six checkpoints `/tmp/onpc-e2e-evidence-bxxn7sh2` | Source capture and every uploaded file digest passed, then `transfer:copied-tree-mismatch`; no worker boot. Preparation 313.102; test 0; cleanup 73.685; total 458.991, including about 72.2 seconds of unbucketed finalization. |

Both attempts ran 293 isolated cleanup-safety tests and three subtests before
VM access. Both restored the baseline, completed the lease, released ownership,
and passed host preservation. The second finalization also rejected source
preservation: another session changed `Makefile`, package-removal code, related
docs/tests and added an APT removal-notice fixture/test during the attempt.
An outside-sandbox `git status` reconciled those edits; they were preserved.
This late failure did not replace the original transfer failure.

The first build recorded source
`e5dcecb1e0502cf34d88814309bb086e68d53c18e1b3686c1b131f19f5196c24`;
the second recorded
`8d2b1ddf7ed3af319a54a28756c7c544f9858fc6a548b46c6577331bd4c94da7`.
Both had package SHA-256
`f878a99b82a3678819d2f551bfdb95c3b3039d8406c540d2d03ab54aaae20e13`
and stable fixture payload SHA-256
`af14791d22b53c87d6b503bbb361107d3be545db18e775b2f3fecebcbf743a1d`.
Attempt 2 recorded staged assets
`286231a06fdd9036fbb45734125eb863a63a8c0cf2d61df4047fa8611e039c9f`.
The retained baseline identity remains
`cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
These are historical inputs, not nominated artifacts for the next attempt.

## Demonstrated causes and corrections

1. The builder sorts `Path` components; provenance previously sorted whole
   strings. Hidden `.codex/rules/...` and `.codex-staged-...` paths expose the
   different order. A new actual-checkout regression failed at exactly that
   comparison. Provenance now uses the builder's ordering, and the synthetic
   source fixture includes the collision. Attempt 2 proved this fix live.
2. The [public upload API](https://libguestfs.org/guestfs.3.html#guestfs_upload)
   successfully copied all files. The tree check used `find` without a trailing
   separator. The upstream [daemon implementation](https://github.com/libguestfs/libguestfs/blob/master/daemon/find.c)
   strips the supplied prefix verbatim, while the [library implementation](https://github.com/libguestfs/libguestfs/blob/master/lib/file.c)
   preserves those returned strings. Passing a trailing slash produces relative
   names for comparison. The test double now reproduces both forms, and a
   regression covers the explicit prefix and redacted count/digest diagnostics.
   Extra/missing entries still refuse. This final correction is local only.

No third attempt ran. A third now has a specific correction and locally tested
observability; it must also have stable source inputs. Do not repeat either
failed input set or reinterpret the failed attempts as passes.

## Final local verification and continuation

```sh
tools/run-unit-tests tests/unit/test_e2e_asset_transfer_cleanup_safety.py tests/unit/test_e2e_provenance.py tests/unit/test_e2e_runner.py tests/unit/test_graphical_smoke_cleanup_safety.py tests/unit/test_system_runner_cleanup_safety.py -q
make check
git diff --check
```

The focused command passed 151 tests (handle 90451). Final `make check` handle
52103 exited 0: 2,123 unit/contracts in 32.92 seconds and 17 components in
0.35 seconds, plus syntax/traceability. This includes 30 tests added by the
concurrent package-removal work; this session added 20 regression cases.
Earlier full checks also passed; the final one followed the inventory fix.
Initial local import and source-ordering test failures were corrected.

Only handoff/guide documentation changed after these checks. Those edits,
the final inventory fix and concurrent work invalidate both historical build
directories for another package-bearing attempt. Build current inputs after
coordinating a stable checkout; run the qualification once and inspect its
transfer receipt, ready-stage observation, terminal result and held-lease
finalization. Reuse lifecycle/worker/backend qualification; do not rediscover it.

At 22:36 UTC, `tools/test-vm status` reported shutoff (`state=5`, `id=-1`).
All owned command handles exited; no VM worker, maintenance operation or lease
remains. Logs and private evidence were not modified or deleted.

Two live attempts consumed about 11.9 minutes total; diagnosis, implementation,
builds, local verification and the separate approval-command investigation
extended the planned slice. No token/usage telemetry was exposed. Remaining
19A estimate: **2–3 sessions / 1.5–2.5 hours**, assuming stable source inputs:
finish live transfer qualification, implement secret/capture and harmless
console transport, then complete affected acceptance. The transfer implementation
and demonstrated provenance fix are solid progress; full acceptance is pending.
