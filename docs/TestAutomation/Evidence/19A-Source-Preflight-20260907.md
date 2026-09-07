# Task 19A source preflight — 2026-09-07

This continuation made a verified guard improvement; full transfer qualification
remains unaccepted. It did not change the inventory-prefix correction or execute
customer coverage. All 156 variants remain pending.

## Attempts and evidence

| Operation | Evidence and result | Measured time |
| --- | --- | --- |
| Fresh artifact build; handle 80543, exit 0 | `/tmp/onpc-test-artifacts-cfadp_24`; build and verification passed before concurrent edits | Short build; exact duration not retained |
| Third transfer attempt overall; handle 73916, exit 1 | `/tmp/onpc-graphical-smoke-sdy1kurm/result.json`; checkpoints `/tmp/onpc-e2e-evidence-032y93kj`; `provenance:recheck-failed` before transfer or worker startup | 252.326 s total; preparation 180.542462 s, cleanup 71.735513 s, test 0 |
| Deliberate early refusal with the same now-stale artifacts; handle 91370, expected exit 1 | `/tmp/onpc-graphical-smoke-sazn6j6r/result.json`; `provenance:source-preflight-failed`, `lease_phase=null`, no guest operation or checkpoint collection | 1.211 s total; preparation 1.211325 s, cleanup 0.000001 s, test 0 |

The build recorded source
`d7fdfb6df93b9b4cfb2d6a20f3b3cd003b5da744d066dbe10287f31c634f0c5b`
at revision `88970876138fda675b5b20397445dc47a048f4f6` and package digest
`572343f17e653d3dd2a1d446b9776069c2996757a3d05d2c1a7d9bebece1da5e`.
These artifacts are stale and are not nominated for another live attempt.

The live attempt passed 294 isolated safety tests plus three subtests. It
completed baseline restoration, released its lease and preserved the host.
Concurrent package-removal work deleted the tracked reboot-notice executable
between source capture and recheck. Subsequent full checks reproduced the
missing path as `tools/oh-no-parent-control-reboot-notice`. The file was not
restored or staged by this session. Other edits later included `debian/postinst`
and its tests. A request to pause concurrent edits received no answer during
this slice; a new VM attempt was therefore not started.

## Concrete improvement and attribution

This session added `provenance.preflight_source`, wired it into qualification
before libvirt connection/lease construction, preserved explicit evidence-error
categories in the terminal report, and added five regression cases. Host tests
exercise current inputs, stale/deleted inputs, mutation during verification,
redacted diagnostics and refusal before VM APIs. The actual installed-launcher
denial passed 295 isolated safety tests plus three subtests and demonstrated
that invalid starting inputs need no guest preparation or restoration.

The concurrent session independently added handling of intentional uncommitted
deletions to both `tools/build_test_artifacts.py` and `provenance.source_paths`,
plus deletion/rename regressions. Our attempted overlapping patch did not apply;
that implementation was preserved and then verified together with our changes.
The early check does not prevent later edits: held-lease source checks remain
mandatory and unchanged.

Initial focused testing exposed lost early-failure categories; reporting was
corrected. The first `make check` passed 2,130 tests and failed only the deleted
tracked-file check. After the concurrent correction, the complete focused
selection passed 82 tests with no deselections:

```sh
tools/run-unit-tests tests/unit/test_e2e_provenance.py tests/unit/test_graphical_smoke_cleanup_safety.py tests/unit/test_build_test_artifacts.py -q
```

Final full-check results are recorded in the active Task 19A handoff. Docs added
after verification invalidate artifact reuse, not the recorded runtime evidence.
At 22:54 UTC the guarded VM reported `state=5`, `id=-1`; no VM attempt remained.
No logs or evidence were modified/deleted, and no screenshots were created.

## Next action and forecast

Do not repeat a full VM attempt while the shared source is changing. Once the
other editing work has ended, build fresh artifacts and run one corrected
transfer qualification. Inspect offline and booted receipts and finalization.
The historical two transfer failures remain in the
[previous evidence](19A-Asset-Transfer-20260907.md); the third failed before that
boundary. No backend, baseline or setup rediscovery is needed.

Remaining 19A is still **2–3 sessions / 1.5–2.5 hours of active work**: live
transfer success, secret/capture and harmless console transport, then acceptance.
Waiting for source stability is additional and cannot be forecast. The concrete
progress here is the proven early refusal and verification of deletion support;
it is not a transfer pass. No usage/token telemetry was exposed.
