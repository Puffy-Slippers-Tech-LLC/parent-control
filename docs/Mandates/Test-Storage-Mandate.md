# Test storage mandate

Apply this mandate when creating or changing storage in tests, fixtures, test
support, launchers, diagnostics or test artifact builders.

All bulk test storage must use the shared
[test storage library](../../tools/test_storage.py). It owns the disk-backed,
gitignored `output/test-runs/` root, the host/privileged ownership split and
filesystem validation. The shared
[retention library](../../tools/test_retention.py) owns allocation identities,
journals, rotation and safe deletion. The operational contract is
[aggregate output retention](../../tests/README.md#aggregate-output-retention).

## Required shared allocation routes

| Need | Required route |
| --- | --- |
| Disposable pytest files | `tmp_path` or `tmp_path_factory` through the maintained test launchers, which configure disk scratch. |
| Disposable standalone scratch | `tools.test_storage.scratch_directory()` as the parent of `TemporaryDirectory`, temporary files or subprocess scratch. |
| Retained reports, artifacts or failure evidence | `tools.test_retention.allocate(tempfile.mkdtemp, prefix='onpc-...')` inside the owning retention session. Register the empty allocation before writing payloads. |
| Qualification evidence | `tests.integration.qualification_storage.session()` and its `allocate` helper; reuse an existing qualification session. |
| Recovery diagnostics | `tests.integration.qualification_storage.recovery_session()` and its `allocate` helper, preserving the separate unfinished VM journal. |
| Launcher category roots, frozen inputs or privileged journals | `tools.test_storage.directory(kind)`, `named_input()` or `privileged_state(uid)`; let the shared library choose and validate the root. |
| Small AF_UNIX socket fixtures | The `short_runtime` pytest fixture or `tools.test_storage.runtime_directory()`. A lifecycle owner that cannot use a context manager may use `runtime_allocation` and must remove its recorded identity on close and failure. |

Use the repository's established import spelling for the calling entry point;
do not copy these implementations into a test or local helper. Ordinary
`TemporaryDirectory` is also appropriate within launcher-configured disk
scratch. Retained diagnostics must not depend on that scratch's lifetime.
Keep the recorded allocation root private and stable through cleanup; use child
directories for fixtures that intentionally change permissions or replace paths.

## Prohibited storage choices

- Test producers must not choose `/tmp`, `/var/tmp`, a caller-supplied `TMPDIR`
  or another system temporary directory as their storage root.
- Do not hardcode or reconstruct `output/test-runs/`, its ownership branches,
  or a replacement root in a test, fixture or producer. Request the appropriate
  shared helper and create only task-local children beneath its returned path.
- Do not use plain `mkdtemp` for retained evidence, bypass registration, or fall
  back to memory-backed storage when disk validation fails.
- Do not reclaim directories by name, prefix, age or a filesystem sweep. Use
  the recorded identities, owner locks and cleanup operations of the shared
  libraries; preserve unknown or replaced entries.

Build and launcher subprocess layers must forward
`tools.test_storage.scratch_descriptors()` through `pass_fds` when descendants
use scratch, including through intermediate fixture builders. A coordinator's
exit must not make a still-running descendant's scratch eligible for deletion.

The only short-path exceptions are centrally owned socket runtime allocation
and the existing explicit screenshot-export contract. Socket runtime holds
only sockets and their small supporting configuration/witness files, is cleaned
on close, and must not hold builds, bundles, logs or retained evidence. Tests
must call the shared runtime helpers rather than spell `/tmp` themselves.
Screenshot exports use `onpc-export-screenshot`; cleanup uses
`tools/cleanup-screenshots` for explicit caller-owned `/tmp/onpc-*.png` files.

Legacy migration readers and validator tests may contain literal paths as
inputs. Storage-library tests may inject isolated roots beneath pytest fixtures
to verify ownership, mount, identity and refusal behavior. Neither exception
authorizes ordinary producers to allocate under an independent root.

## Evidence and verification

Retained evidence belongs to a bounded journal. Preserve oversized current-run
evidence and refuse replacement until explicit cleanup; do not silently rotate
it away to start new work. Failed or interrupted recovery must keep diagnostic
evidence without clearing or rotating the unfinished VM journal.

Changes to allocation or cleanup must cover the affected lifetime, interruption,
identity/refusal and retention boundaries through the maintained test launchers.
Pass applicable cleanup-safety regressions before protected host operations.
This mandate changes test tooling only; it grants no product installation,
unrelated deletion or VM-operation authority.
