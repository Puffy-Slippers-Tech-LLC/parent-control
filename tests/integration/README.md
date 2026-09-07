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

## Graphical backend prerequisite

Task 19P's candidate backend is the pinned os-autoinst `generalhw` package.
After the isolated `test_system_runner_cleanup_safety.py` prerequisites, run
`/usr/bin/python3 -B tests/integration/graphical_backend.py` for a read-only
package/API/dependency check. It requires neither root nor VM access and reports
tooling readiness only. `setup.sh` includes the Perl dependency missing from
the backend package's dependency declaration. The
[19P completion handoff](../../docs/TestAutomation/Task-19.md#completion-handoff--2026-09-06-19p-accepted)
records the qualified lease adapter and live smoke. Run its credential-free
feasibility check with
`pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_smoke`;
the dispatcher supplies isolated cleanup/lease prerequisites. This establishes
graphical compatibility, while the full E2E runner and customer coverage remain
under development. Preflight alone establishes only tooling readiness.

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

For implementation, use the [bounded diagnostic workflow](../../docs/TestAutomation/Implementation-Workflow.md).
The current controller executes the complete installed/reboot/authorization
scope when unselected. F1 can list the registered `package` and `authorization`
cases and their explicit prerequisite closure without artifacts, root access,
or VM operations:

```sh
make check-system LIST=1 AREA=authorization
make check-system LIST=1 AREA=authorization TEST='test_real_selected_parent_authentication[child1]'
```

The listing uses pytest's public collection-only mode with project and third-party
plugins disabled; it imports the test definitions but never executes guest
fixtures. A non-listing selection forwards only its exact cases plus registered
package/reboot prerequisites through the same guarded VM controller. It labels
the result partial and records expected and observed JUnit case identities;
missing, additional, duplicate, failed, or skipped identities fail the run.
The controller freezes only the test modules and guest helpers required by that
resolved execution closure. `selected-inputs.json` binds their byte digests to
the exact phases/case IDs, and its SHA-256 is carried independently through the
guest marker, guest result, and aggregate result. Arbitrary guest pytest
arguments remain unsupported. F1's selected and unselected runner qualification
is complete; its [acceptance evidence](../../docs/TestAutomation/Evidence/F1-Qualification-2026-09-06.md)
preserves the known Task 14 authentication failures as product/helper failures.

For fixed harness qualification only, add `QUALIFICATION_FAILURE=1` to
`make check-system` with `AREA=authorization` and
`TEST='test_method_role_matrix[ListManagedUsers-parent1]'`. `LIST=1` also accepts
this option. Every other scope is refused before VM mutation. The qualification
plugin is frozen in selected-input provenance and loaded only for the selected
authorization phase. Its [public pytest call wrapper](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html#hook-wrappers-executing-around-other-hooks)
injects `harness:qualification-failure` only after the real assertion succeeds;
existing assertion, setup and skip outcomes remain intact.

Qualification retains a failing exit status and labels the result
`harness-qualification`. The controller attributes the fixed fault to
infrastructure only when all five exact executions are collected, prerequisite
cases pass, and the selected case has only the fixed failure. Missing or unsafe
evidence and cleanup failures remain separate outcomes. Even if the hook fails
to inject its fault, qualification cannot become a passing product result.

One expensive attempt should collect the safe observations needed to distinguish
the current hypothesis on success and failure. Check parser/collector handling
locally first. After two attempts on the same blocker, improve the evidence or
justify a new discriminating experiment before another boot; carry that history
across handoffs. Never leave a VM running or restore an intermediate state to
save conversation context. A completed attempt's failure remains preserved.

First run the applicable
[isolated cleanup-safety regressions](../README.md#cleanup-safety-prerequisites),
including persistent-caller cleanup if that helper is used. After building and
verifying the input, invoke the host controller from a root shell:

```sh
make check-system ARTIFACT_DIR=/tmp/onpc-test-artifacts/run-input
make check-system ARTIFACT_DIR=/tmp/onpc-test-artifacts/run-input \
    AREA=authorization TEST='test_method_role_matrix[ListManagedUsers-child1]'
```

From an administrator's graphical session the equivalent is
`pkexec make -C /Data/Code/PST/parent-control check-system ARTIFACT_DIR=<verified-directory>`.
The command resets guest disk changes since the retained baseline. Never run
it on an unleased VM containing work that must be kept. `VM_IMAGE` is refused.

Preparation checks all directly invoked host tools, including `dpkg-deb` and
`dpkg-query`, and names a missing tool without logging command arguments.
Missing, inaccessible, or otherwise unavailable artifact sources report distinct
`assets:source-*` categories before run storage or VM access. These input errors
do not establish a missing executable; verify the supplied artifact directory
in the same privileged host context as the runner.

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
- `stage_assets`: freezes the package/fixture manifest, verifies canonical
  fixture digests, and hashes exact transferred bytes, including variable
  Flatpak containers. `stage_selected_inputs` separately freezes the resolved
  executable test/helper closure and binds its files to the selected case IDs.
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
- `system_caller.TextAgent(caller)`: guarded real `pkttyagent --process` attached
  to the persistent caller's pinned PID and kernel start time, with registration
  readiness on its inherited notification pipe. Polkit resolves the broker's
  real bus-name challenge to that process. Startup failure reports only a fixed
  category and child exit status; terminal bytes are never exported.
  `prompt(selected_uid, other_uid)` checks the
  selected identity and waits for terminal echo to be disabled;
  `authenticate(password, succeeds=...)` drives the real PAM challenge. Terminal
  contents remain in memory; unexpected acceptance, denial or cancellation
  fails immediately with a fixed category instead of waiting for a timeout.
  Denied challenges also report an allowlisted helper failure stage (PAM or
  authority response, or `unclassified`); arbitrary helper stderr and terminal
  contents are never exported, and the category alone does not prove the cause.
  `FixturePassword` generates distinct temporary
  credentials and sets them through guarded guest stdin without diagnostic
  export. Agent cleanup signals only its directly spawned pidfd; run
  `test_system_agent_cleanup_safety.py` before integrated use. This text-agent
  coverage does not replace graphical authentication journeys.
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
(`installed.xml`, `rebooted.xml`, `authorization.xml`). The authentication journal
collects Polkit service and PAM helper messages through the same redaction pass;
a failed authentication-journal command fails collection explicitly.
Authentication tests also retain `onpc.authentication` JUnit suite properties
using pytest's public xunit2-compatible fixture. Each JSON value names the
registered `case_id`, its one-based `attempt`, `expected` and actual `outcome`,
and an allowlisted `helper_category` (null for accepted/cancelled outcomes).
Recording precedes the outcome assertion, so an unexpected denial retains its
category and remains a test failure. Attempt numbers restart for each case;
credentials, account identities and terminal contents are excluded. JUnit
redaction operates on decoded XML values before serialization, preserving valid
XML even when a traceback contains a password assignment.
Raw diagnostics and
temporary SSH credentials remain root-private. Use only validated redacted
exports; read source logs and journals without modifying them.

Results record package SHA-256, stable fixture digest,
`selected_inputs_sha256`, and `baseline_provenance_sha256`. The selected-input
digest is distinct from package/fixture identity and changes with either the
resolved execution closure or any staged test/helper byte. The baseline digest
hashes finalized provenance, not the writable active QCOW2. Cleanup independently
checks immutable backing hashes, snapshot metadata, product-free offline
inspection and host product/PAM fingerprints, including after failure.

The aggregate result also records monotonic accumulated seconds for preparation,
bootstrap, install, reboot, test, collection, and cleanup. Its `outcomes` object
reports product, infrastructure, collection, and cleanup independently. Each
domain retains its first fixed failure category; later collection or cleanup
failures remain visible without replacing the aggregate run's original category.
An outcome is `not-run` when the attempt ended before that boundary could be
established, rather than being inferred as a pass.

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

## Graphical adapter under development

Task 19P now has controller plumbing in `graphical_lease.py`: public generalhw
lifecycle command variables, a private Unix callback service, and revocable
graphics descriptors from a `Lease(..., graphics_type='vnc')`. `Lease.stop()`
stops the recorded instance without restoring within a backend attempt; the
outer lease still performs baseline cleanup. All callback processing stays in
the controller thread and revalidates lease ownership.

Graphics FD RPCs use a short-lived, separate libvirt connection. Its URI, UUID,
domain instance and exact XML must match the guarded lease before attachment,
and ownership is checked again afterward. A graphics connection failure cannot
close the lifecycle connection needed for normal baseline cleanup.

On a development host launched from the classic VS Code snap, `pkexec` retains
the `snap.code.code` AppArmor label. `setup.sh` installs the versioned
`config/apparmor/onpc-graphical-tests` rule in the managed section of
`/etc/apparmor.d/local/usr.sbin.libvirtd`, preserving other site rules. The
installer compiles the proposed whole profile before writing and reloads only
libvirtd's profile. The rule permits anonymous Unix stream send/receive with
that exact peer label; it grants no named-socket, ptrace or additional QEMU
permission. Libvirt authentication and the exclusive VM lease still apply.
This development-only integration activates immediately on profile reload
(`none` for product packaging); it changes no application data or product package.

The fixed non-booting diagnostic is
`pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_transport`.
It requires the existing domain to be off and sends only an impossible graphics
index. A normal libvirt refusal with the connection still alive proves outgoing
FD RPC transport; a disconnected RPC is a failure. A separate owned fixture
runs under libvirtd's existing AppArmor profile with `aa-exec`, sends one socket
back, and requires usable bytes and no truncated ancillary data. Neither test
starts a guest or attaches a usable display. These probes distinguish basic
directional FD transfer from the live graphics RPC; their pass does not prove
`openGraphicsFD` or graphical compatibility. Raw fixture diagnostics and the
result are retained under root-private `/tmp/onpc-graphics-transport-*`. Use
this cheap probe before another boot when diagnosing descriptor receipt. The
dispatcher runs its safety regressions automatically.

`graphical_worker.Worker(directory, callback_path, run, command)` now launches
trusted backend commands inside private network/PID/mount namespaces. The
bridge listens on `127.0.0.1:5900` only there, acquiring the lease-issued display
FD lazily when the backend connects. Supply `GENERAL_HW_VNC_IP=127.0.0.1` and
`GENERAL_HW_VNC_PORT=5900` in the backend variables alongside
`graphical_lease.lifecycle_variables()`. The worker does not create those vars
or a distribution; its command is an internal controller API, not a privileged
arbitrary-command CLI.

Service callbacks from the lease owner's thread through `worker.run(server,
timeout=...)`, or `worker.poll()` plus `server.serve_once()`. Close the worker
in `finally` before closing the callback server and finishing the lease. Its
pidfd/start gate, controller EOF, and `unshare --kill-child=KILL` bound backend
descendant lifetime without process discovery. Kernel namespace cleanup also
covers orphaned backend children. This contains trusted tooling; it is not a
security sandbox for hostile root code. Working files and raw backend output
remain root-private and are not safe evidence exports.

The fixed non-VM qualification is
`pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_worker`.
The dispatcher runs the isolated cleanup prerequisites first. See the
[worker evidence](../../docs/TestAutomation/Evidence/19P-Worker-Bridge-2026-09-06.md)
for its success/failure scope.

The fixed live feasibility invocation is now
`pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_smoke`.
It accepts no arguments and uses the same isolated safety prerequisites and
exclusive baseline lease. Before acquiring the lease it uses the documented
`_EXIT_AFTER_SCHEDULE=1` mode to load the distribution without starting a backend.
The pinned CLI overrides its early exit status with 1; the preflight requires
both exact schedule/completion diagnostics, and rejects an ordinary compile
failure. The actual graphical run uses `--exit-status-from-test-results` and
also requires an `ok` module result with no failed/soft-failed details.
`graphical_smoke/main.pm` loads one credential-free
generalhw test: await guarded greeter observation, capture GDM, select the first
large user tile, and dismiss the resulting credential prompt with Escape,
requiring both screen changes. It explicitly selects the backend's documented
32-bit VNC depth. The default 16-bit path can decode QEMU's initial full frame
but the pinned client's ZRLE decoder rejects a subsequent changed rectangle.
The large fixed-baseline tile proves input transport without depending on small,
theme-sensitive status icons; Task 19B owns needle-based interaction helpers. The
controller independently checks the active greeter and absence of logged-in
user sessions through fixed read-only SSH observations at each stage. Bootstrap
uses the existing offline SSH provisioning with `observation_only=True`; no
product package or guest pytest is installed by this smoke.

Raw screenshots, backend logs, command diagnostics, SSH keys and working vars
stay in its root-private `/tmp/onpc-graphical-smoke-*` directory. Only fixed
stage labels, dimensions, digests and classified outcomes appear in the summary.
Retaining private images does not approve them for export or prove their
semantic content; reviewed/redacted screen evidence remains an acceptance
obligation. No credentials are entered, serial capture is disabled, and no
customer E2E claim is made. The task's active handoff owns live qualification
status. These are development-only test changes, activated on next invocation
(`none`); no host tools, product services or saved-data schema change.
