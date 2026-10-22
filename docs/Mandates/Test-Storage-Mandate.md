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

Human-readable VM watch recordings use the shared library's owner-private
`output/test-runs/recordings/` directory and identity-owned publication through
`tools/recording_storage.py`, under the
[latest-only recording contract](../../tests/README.md#vm-watch-recordings).
They retain one playable file per category/numeric case ID across VM combinations,
without age or size rotation. This explicit recording policy is an exception to
ordinary bounded run retention and host/privileged directory split; it does not
change any other artifact's lifetime. Only the unprivileged recorder creates
this directory; privileged controllers use authenticated read-only discovery.
Session media and encoder scratch still use the ordinary shared scratch route.

| Need | Required route |
| --- | --- |
| Disposable pytest files | `tmp_path` or `tmp_path_factory` through the maintained test launchers, which configure disk scratch. |
| Disposable standalone scratch | `tools.test_storage.scratch_directory()` as the parent of `TemporaryDirectory`, temporary files or subprocess scratch. |
| Host fixture production | `tools.fixture_producer.Store().producer(...)` reserves one durable slot in `tools.test_storage.fixture_directory()`. Register each scratch/staging child with `Producer.allocate()` before payload writes; use `Producer.environment()` for compiler scratch. |
| Retained reports, artifacts or failure evidence | `tools.test_retention.allocate(tempfile.mkdtemp, prefix='onpc-...')` inside the owning retention session. Register the empty allocation before writing payloads. |
| Finalized producer subset during active execution | `tools.evidence_capture` under the live producer session; use its registered, independently finished sealed subowner and `tools.capture_publication` for verified cumulative publication. Slots and recovery state are charged to the parent. Required originals retire only with source-owner acknowledgement and pinned replacement verification. See [sealed handoffs](../../tests/README.md#sealed-producer-handoffs). |
| Atomic qualification evidence export | `tools.test_retention.Store.publication()` and its single `allocate` method, with complete verification before commit/recovery retirement; use the maintained [bundle route](../../tests/README.md#complete-qualification-evidence-bundles). |
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

After retained evidence establishes an interrupted artifact build, recover its
unpublished named input with `tools/cleanup-e2e --vm NAME --discard-unpublished-input CHECK`.
This explicit action derives the input from that qualification's current literal
declaration. It requires one VM, checkout ownership and a finished, unmarked host
journal; it audits the latest recorded allocation identity and refuses any existing
completion manifest, unknown/replaced root, link or mount. It removes only that
unpublished allocation, preserving reports and journal records for retry. It opens
no retention session and changes no VM state. Never use it merely because a
nonempty bundle fails verification; establish the interrupted build first.

Qualification inputs are VM-bound. A batch controller must leave their
preparation and registration to each VM worker's retention session. If retained
evidence establishes that an older batch controller registered a replacement
over a VM journal's stale claim, use
`tools/cleanup-e2e --vm NAME --transfer-batch-input CHECK`. This nondeleting
recovery derives both journals and the input, holds checkout/host activity and
both completed owners, verifies the published bundle and audits unrelated
allocations and projected budgets. It preserves original records and reports,
appends the live identity to the VM owner and retires the batch's cleanup claim.
Durable intents block ordinary retention mutations until both commits complete;
an interrupted transfer must resume with the same VM and selector. It refuses
changed owners, roots or competing intents. It opens no session, rotates no
evidence and supplies no acceptance. Do not use a transfer to adopt an
unregistered or invalid input or to bypass a refusal.

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
This forwarding includes the fixture producer lease in fresh interpreters.
The producer context closes its own lease without unlocking descendants. A live
descendant or interrupted deletion leaves the same reservation occupied;
`Store.recover(transaction_id)` retries only that recorded cleanup after the
last lease closes. New production refuses until cleanup settles. Cleanup audits
every registered allocation's allocator-relative identity, owner, mode and mount
before deleting any tree, preserving unknown and replaced paths. The lifetime
record, `producer.json`, is outside those trees and carries the frozen unfinished
slot fields with checkout, process and lease identities. It neither replaces an active execution's
retention token nor uses evidence rotation for fixture versions.

This lifetime API owns unfinished production only. Immutable host construction
uses the [frozen bundle contract](../../tests/support/README.md#frozen-native-fixture-bundles);
execution-owned input reuse/publication remains the separate
[fixture-plan](../TestAutomation/Fixture-Execution-Plan.md) task F03.
The current proposal reuses ordinary input retention; it adds no shared version
catalogue, cross-journal pins or six-slot policy. There is no byte quota, quota
setup or product installation in producer recovery.

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
[`tools/backupvm`](../../tools/backupvm) and
[`tools/restorevm`](../../tools/restorevm). This operator-owned durable storage
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

Accepted ordinary-plan proof uses the shared bundle writer and verified
publication in its plan namespace, with the same bounded limits. Its stable
locator and historical-disclosure transaction follow the
[execution-plan evidence owner](../Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery).
They do not pin disposable allocations or authorize checkpoint edits by agents.

Changes to allocation or cleanup must cover the affected lifetime, interruption,
identity/refusal and retention boundaries through the maintained test launchers.
Run applicable cleanup-safety regressions as explicit validation before exercising
changed protected operations. Cleanup itself runs no regression tests; it only
recovers recorded owned resources under the [cleanup contract](../../tests/README.md#cleanup-safety-prerequisites).
This mandate changes test tooling only; it grants no product installation,
unrelated deletion or VM-operation authority.
