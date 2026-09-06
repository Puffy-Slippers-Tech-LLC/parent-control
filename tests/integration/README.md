# Installed-system runner

Use the [daily guide](../../docs/Test-Automation.md) for command scope and the
[test contributor guide](../README.md) for local layers and safety prerequisites.
This document retains the implemented runner and artifact contracts. Initial
setup tasks, historical test counts, and dated acceptance directories are not
instructions for a new run.

## Environment and ownership

Installed-system tests use the real package and operating-system services on
the existing guarded `ubuntu26.04` VM. They do not install the product or change
accounts, PAM, Polkit, services or policy on the development host. An existing
host product installation is preserved. Detailed identity, baseline and
recovery requirements are in [Environment.md](Environment.md).

The runner exclusively leases the VM, validates the finalized baseline and
recorded disk/domain identities, restores only outside a complete attempt,
detaches writable host shares/transfer channels before boot, and leaves the VM
off with its prior persistent domain configuration restored after cleanup.
It creates no new VM, snapshot, disk copy or overlay. A real reboot within an
attempt preserves guest state and must produce a new boot identity.

The host and guest tooling sources are `setup.sh`,
[../test-tools-ubuntu-26.04.txt](../test-tools-ubuntu-26.04.txt),
and the runner's pinned guest bootstrap configuration. Record actual runtime
versions in each result; do not use a dated development-workstation package
table as evidence of the installed guest's environment.

## Package and fixture inputs

`tools/build_test_artifacts.py` builds without installing the product on the
host. Use a new empty output directory under `/tmp`, outside the checkout:

```sh
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-test-artifacts/run-input
```

Choose a different empty directory for another build. Output contains
`artifact-manifest.json`, the named Debian package in `package/`, and
deterministic native/Flatpak fixture assets in `fixtures/`. The manifest records
source revision/content digest, source date epoch, architecture, build inputs,
tool versions, and package/stable-fixture digests.

`tests/fixtures/build_test_applications.py` supplies real long-running native
executables, path/space/version-pattern variants, desktop entries and a minimal
Flatpak runtime/application bundle. `make check-test-fixtures` tests the builder
and identity-recorded processes with private temporary Flatpak state, never the
developer's actual installation. `make build-test-fixtures OUTPUT_DIR=...`
retains a payload for focused fixture work. These are enforcement targets, not
proof of real-game behavior. Later Snap and game assets must use the same
verified input discipline.

`make verify-test-artifacts FIRST_OUTPUT=... SECOND_OUTPUT=...` performs two
isolated builds and compares package bytes, contents/metadata, recorded inputs
and the stable fixture payload. Both outputs must be new. Flatpak delivery
containers can carry host-clock metadata; their stable payload digest is
distinct from the exact-byte hashes verified during transfer. Do not claim
byte-identical delivery containers when only their payloads were compared.

The builder records `DEB_BUILD_OPTIONS=nocheck`: current controller tests require
the fixed development checkout and run through host checks separately. A
successful build alone therefore does not establish passing tests. Test the
current source/package inputs; previous acceptance artifacts are not defaults.
Future `test-system`/`test-e2e` prepare inputs automatically, and `test-all`
coordinates host results and VM artifacts for the same source content.

## Running the current installed suite

First run the applicable
[isolated cleanup-safety regressions](../README.md#cleanup-safety-prerequisites),
including persistent-caller cleanup if that helper is used. After building and
verifying the input, invoke the host controller from a root shell:

```sh
make check-system ARTIFACT_DIR=/tmp/onpc-test-artifacts/run-input
```

From an administrator's graphical session the equivalent is
`pkexec make -C /Data/Code/PST/parent-control check-system ARTIFACT_DIR=<verified-directory>`.
The command resets guest disk changes since the retained baseline. Never run
it on an unleased VM containing work that must be kept. `VM_IMAGE` is refused.

Both Makefile and direct controller paths suppress Python bytecode writes.
Default host pytest collection excludes `tests/system/`; guest pytest uses
its own configuration and disables plugin autoload. Do not invoke guest tests
as host pytest or bypass the controller merely to select a test.

After guarded offline bootstrap, the guest verifies its root-private run marker,
machine identity distinct from the host, DMI domain UUID, supported Ubuntu
release, absence of host shares, and package/transfer digests. Only then does
APT install the exact package. The runner waits for systemd boot completion
before service assertions; SSH alone is insufficient. A degraded boot does not
skip the service assertions. Readiness waits never retry installation or a
failed test assertion.

The installed suite covers real package content/ownership, service and D-Bus
readiness, PAM/Polkit/session integration, execution policy and actual reboot.
Installed authorization coverage is being extended; the
[Task 14 handoff](../../docs/TestAutomation/Task-14.md#continuation-handoff--2026-09-05-incomplete)
owns its current status. These tests are not complete graphical E2E acceptance.
The future E2E runner must obey the
[real customer-operations contract](../../docs/TestAutomation/E2E-Coverage.md).

## Reusable implementation contracts

- `system_runner.Lease`: the existing controller lock spans validation, outer
  reset, bootstrap, the whole attempt and cleanup. Cleanup is bound to the
  recorded UUID, live domain identity, run marker, disk identities and snapshot
  metadata. It must not affect a replacement or unrelated VM.
- `stage_assets`: freezes the package/fixture manifest and test inputs, verifies
  canonical fixture digests, and hashes exact transferred bytes, including
  variable Flatpak containers and executable test code.
- `vm_transport.Transport`: pinned-key SSH, safely quoted argument transport,
  constrained archive extraction, bounded readiness and real reboot. Every
  readiness probe revalidates identity; a guest guard failure is not retried as
  a transient SSH error. The first phase's evidence is retrieved before reboot.
- `owned_commands.Commands`: pins directly spawned host/guest processes and
  bounds interruption cleanup. No guessed process discovery or ownership.
- `system_guest`: validates the guest/attempt boundary and drives real APT and
  installed pytest phases. Package assertions account for actual packaged
  permissions, including the restricted Parent launcher and fapolicyd's
  tmpfiles-managed configuration ownership.
- `system_caller.py`: drops real/effective/saved credentials, opens a fresh
  system-bus connection and verifies the bus-reported UID. Structured replies
  and private-state assertions stay in private diagnostics, without exposing
  account contents in public assertion errors.
- `system_caller.PersistentCaller(uid)`: context-managed real caller connection
  with `name`, `call(method, signature, args)`, and separate `send(operation)` /
  `receive(timeout)` operations. EOF closes it; bounded context cleanup signals
  only its directly spawned pidfd. It is not an authentication agent and does
  not by itself prove password handling or approval.
- `tests/system/test_authorization.py`: reusable `batch`, `call`,
  `account_property` and `account_state` assertions. Account state compares
  private preferences and public limit/grant/filter state without printing
  private values. Keep phase expectations aligned with actual collection;
  fixed historical pass counts are not coverage definitions.

Current bootstrap operates only in the reset guest. Its offline repository
normalization preserves signing, suites/components and unrelated repositories;
it does not disable APT authentication. Libguestfs handles close before another
guest tool opens the image. The pinned SSH key comes from read-only inspection.
Keep changing implementation details and exact package pins in the controller,
not duplicated as dated facts in this guide.

## Evidence and failure recovery

Every attempt retains a unique `/tmp/onpc-system-*/` directory. Public
`evidence/` contains aggregate `result.json`, xUnit `results.xml`, TAP
`results.tap`, redacted guest logs, and the applicable guest phase XML
(`installed.xml`, `rebooted.xml`, `authorization.xml`). Raw diagnostics and
temporary SSH credentials remain root-private. Use only validated redacted
exports; read source logs and journals without modifying them.

Results record package SHA-256, stable fixture digest and
`baseline_provenance_sha256`. The last hashes finalized provenance, not the
writable active QCOW2. Cleanup independently checks immutable backing hashes,
snapshot metadata, product-free offline inspection and host product/PAM
fingerprints, including after failure.

An incomplete `system-run.json` prevents a new attempt. Preserve it and its
evidence for [identity-verified recovery](Environment.md#interrupted-or-invalid-state).
Never delete controller state or rebuild the baseline to conceal an error.
Normal cleanup retains a failed outcome. Missing/skipped/failed phases cannot
be called a complete pass; a later diagnostic success does not erase an earlier
failure. The pending shared evidence/aggregate work adds executable
scenario/variant/step reconciliation; current file-level requirement validation
alone cannot establish that stronger claim.

Existing tests for controller guards, transport and guest assertions remain
ordinary regressions, even though the original runner implementation task is
complete. Repeated live smoke qualification belongs to harness changes or
diagnosis, not every daily run. No documentation cleanup authorizes deletion
of historical evidence or logs.
