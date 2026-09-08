# Task 15A desktop Path and system fallback fixtures

Date: 2026-09-08. Settings: `gpt-6-astra` / `high`, pinned by the slice launcher.
Development-host implementation only; existing guarded test-VM scope persists.

The registered `test_native_catalog_is_selected_child_scoped` now checks three
more targets on each child/other-child/child-again selection. `DesktopPath` uses
an absolute desktop `Path` containing a space and must beat child and fixed
system copies of the same command. `SystemPreferred` selects `/usr/local/bin`
over `/usr/bin`. `SystemFallback` selects a separate command from `/usr/bin`
with its `/usr/local/bin` candidate absent. Administrator copies remain present.
The existing relative-command case also gains a lower-priority system decoy.

Provisioning refuses system-command collisions, unsafe directory ancestors and
a preexisting higher-priority fallback candidate before any writes. New files
remain exclusively created; existing account and system directories retain
their modes/ownership. Files live only in the guarded guest in real execution;
outer baseline cleanup owns their removal. No writes through the guest's
potential `/bin` alias are needed. This does not qualify an independent `/bin`
runtime fallback; that policy retains its existing host catalog unit coverage.

Host checks use real filesystem discovery with D-Bus, identities, ownership
changes and fixed system directories substituted into temporary fixtures.
Seven fault cases remove/change desktop `Path`, remove its target, remove or
disable the preferred system target, remove fallback, or substitute the
administrator search path. Every fault rejects the catalog before a passed
stage is recorded. Five new safety variants preserve existing files and refuse
before mutation; the existing-directory test now also covers a system directory.
No product code, setup integration, migration or requirement mapping changed.

| Experiment | Result and measured test time | Cleanup |
| --- | --- | --- |
| Initial isolated safety check | 14 passed, 0.08 s | Exited 0 |
| `tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q` | 19 passed, 0.10 s | Exited 0; temporary filesystem fixtures only |
| `tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q` | 163 passed, 0.85 s; after adding system-directory preservation, 164 passed, 0.80 s; final handle 43726 | Both exited 0; results collected |
| `make check` | 2,854 unit/contracts passed, 63.37 s; 17 private-D-Bus components passed, 0.36 s; syntax/stage traceability passed; handle 65182 | Exited 0; private-bus fixtures completed |
| Scoped `git diff --check` and `tools/read-only links` | Passed for changed source, handoff and evidence documents | Exited 0; read-only |

Preparation and cleanup were included in test invocations; separate timing was
not exposed. No build or VM attempt was started; no expensive 15A attempt was
spent. No failed test or approval/Polkit denial occurred.
All commands exited and results were collected. No owned process, VM lease,
screenshot export or recovery remains; no current VM state is inferred.

## Verified source identities

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `daf27456548fbfc51a2d67bd95471db4a8c772f91f73ad67fcc27ad55553569d` |
| `tests/unit/test_system_enforcement.py` | `8bcf121ff471dc2bf2cf7c1c3d052550bb9a9c7801fd45eed0d8b5ea8b8009ed` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `356cec20b40766ab94aec666aa27eea8437bb4e7b46319245be667fa31978a03` |
| `tests/unit/test_catalog_scope.py` | `95522b70f5e0c744626bae23fc8c0e7c6602c355029e85ebdd505dba1fbb3436` |
| `broker/oh_no_parent_control/catalog.py` | `bb2610094be4e0e5cdbf6739fea3e5fd0f8314f498dd3cccfa50ad4ccd00f35f` |

Earlier [relative-command evidence](15A-Catalog-Relative-Fixtures-20260908.md)
and [registration evidence](15A-Installed-Catalog-Registration-20260908.md)
retain their original input identities. Current local success is not installed
broker or kernel acceptance. [Task 15A](../Task-15.md#task-15a-continuation--2026-09-08)
remains unchecked. Live qualification still requires explicit writer coordination
through collection. Documentation changes invalidate package provenance under
the current whole-checkout input contract; no stale artifact is approved for reuse.
