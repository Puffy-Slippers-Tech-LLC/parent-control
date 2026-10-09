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
Verify that the owning retention session is active before allocating retained
evidence. `allocate()` without a session can return disposable scratch; calling
it alone does not establish retention. Qualification helpers reuse an active
session rather than open a second run.
Keep the recorded allocation root private and stable through cleanup; use child
directories for fixtures that intentionally change permissions or replace paths.

An empty named input is a reservation, not a verified bundle or permission to
adopt its directory. `named_input()` preserves empty slots and selects a bounded
fresh generation; the launcher registers that new allocation before building.
Nonempty inputs retain normal manifest/tree verification and refusal, even when
incomplete. Do not reclaim an empty slot without its recorded identity.

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

The only short-path exceptions for new producers are centrally owned socket
runtime allocation and [explicit screenshot exports](#screenshot-export-and-cleanup).
Socket runtime holds
only sockets and their small supporting configuration/witness files, is cleaned
on close, and must not hold builds, bundles, logs or retained evidence. Tests
must call the shared runtime helpers rather than spell `/tmp` themselves.

Legacy migration readers and validator tests may contain literal paths as
inputs. Storage-library tests may inject isolated roots beneath pytest fixtures
to verify ownership, mount, identity and refusal behavior. Neither exception
authorizes ordinary producers to allocate under an independent root.

## Disaster recovery archives

Explicit VM disaster archives use `backup_root` in
[`config/test-vm.json`](../../config/test-vm.json) through
[`tools/backupvms`](../../tools/backupvms) and
[`tools/restorevms`](../../tools/restorevms). This operator-owned durable storage
is an exception to disposable test-output allocation, not a new test scratch
route. The archive root, VM directories and generations are root-private;
publication is atomic and checksummed. Each VM has one folder named exactly
after the VM. A verified temporary replacement overwrites the previous copy;
recorded temporary and superseded files are removed after publication. Failed
copying cleans its recorded scratch; interrupted publication/deletion resumes
from private journals. Unknown or replaced entries are preserved and refused.
These archives are never swept or rotated by test retention. File copies preserve
sparse holes and use independent bytes rather than reflinks.

Restore staging files and displaced originals stay beside their exact registered
destinations, under the VM lease and identity-bound `restore-vms.json` journal.
They are transaction/recovery payloads, not disposable scratch. Preserve them
on success and interruption; this workflow grants no automatic deletion.
Saved-memory credentials continue to use the shared state allocation route;
host-safe regressions use pytest-private fixtures. See
[VM disaster recovery](../../tests/integration/Environment.md#vm-disaster-recovery).

## Screenshot export and cleanup

For an explicit graphical-smoke PNG export, run the installed
[`onpc-export-screenshot`](../../tools/onpc-export-screenshot) helper from the
intended checkout root with `--keep-cwd` before its path:

```sh
pkexec --keep-cwd /usr/local/libexec/onpc-export-screenshot 'SOURCE' '/tmp/onpc-new.png'
```

Replace `SOURCE` with an exact returned PNG path directly inside
`output/test-runs/{host,privileged}/allocations/onpc-graphical-smoke-*/testresults/`.
Legacy `/tmp/onpc-graphical-smoke-*/testresults/` sources remain readable; this
compatibility route does not authorize new producers there. Other artifact
types and locations use the [artifact reader/exporter](../../tests/README.md#prompt-free-test-artifact-access).
Exports preserve the source. The helper pins descriptors, refuses symlink
traversal and unsafe ownership/permissions, requires a regular singly linked
PNG of at most 32 MiB, and creates a new caller-owned file at mode 0600 without
overwriting an existing destination.

Remove only explicitly selected caller-owned `/tmp/onpc-*.png` files with
[`tools/cleanup-screenshots`](../../tools/cleanup-screenshots):

```sh
tools/cleanup-screenshots '/tmp/onpc-new.png'
```

Quote exact names; directories and wildcards are refused. Cleanup validates
the whole selection before deletion, refuses nonregular or foreign-owned files,
and rechecks each recorded device/inode identity before unlinking it. Missing
files are harmless. This narrow caller-owned exception grants no deletion of
source evidence, VM capture directories or unrelated temporary files.

## Evidence and verification

Retained evidence belongs to a bounded journal. Follow
[aggregate output retention](../../tests/README.md#aggregate-output-retention)
for budgets, automatic retirement of completed execution evidence and explicit
discard authorization. Preserve current-run evidence at a budget failure;
failed or interrupted recovery retains diagnostics without clearing or rotating
the unfinished VM journal.

Changes to allocation or cleanup must cover the affected lifetime, interruption,
identity/refusal and retention boundaries through the maintained test launchers.
Run applicable cleanup-safety regressions as explicit validation before exercising
changed protected operations. Cleanup itself runs no regression tests; it only
recovers recorded owned resources under the [cleanup contract](../../tests/README.md#cleanup-safety-prerequisites).
This mandate changes test tooling only; it grants no product installation,
unrelated deletion or VM-operation authority.
