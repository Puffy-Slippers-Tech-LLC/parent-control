# Host-owned fixture design

Fixtures are immutable host-built inputs. Guests receive only the runtime files
needed by the selected test. Fixture changes have independent identity from
product packages and clean VM snapshots.

The [support guide](../../tests/support/README.md) owns operational interfaces.
The [environment contract](../../tests/integration/Environment.md) and
[installed runner guide](../../tests/integration/README.md) own target availability
and preparation routes. Existing storage, transport, native-policy and VM owners
govern fixture operations.

## Ownership and placement

Sources, compilers, workspaces, expected results and unused collections stay on
the host. Guests receive selected executables, modules, desktop files and data.
Guest owners resolve from accepted roles; host UIDs and credentials never enter
bundles.

[baseline_assets.py](../../tests/fixtures/baseline_assets.py) and
[native_assets.py](../../tests/fixtures/native_assets.py) declare exact membership,
destinations, modes, symbolic owners, absence controls and native-policy actions.

| Family | Placement and boundary |
| --- | --- |
| Native GUI | Selected executables and adjacent modules under `/opt/onpc-test-fixtures/Applications`, with required desktop files. Jordan owns executables (0755) and modules (0644); desktop files (0644) belong to their declared child. Nested-version and legacy-root controls remain distinct. Intentionally untrusted; Fedora uses exact child/content admissions. |
| Mechanical and pattern | Root-owned command, whitespace, wildcard, unrelated-version and retention controls, without unnecessary GUI runtime. |
| Trusted hard/soft and activity | Distinct hard/soft bytes and required activity modules, root-owned. Trust applies to exact declared files. |
| Catalogue and PATH | Complete selected precedence comparisons, including masked entries, user/system ownership and absence of the fallback executable. |
| Environment | Accounts, pictures, passwords/keyrings, language/desktop settings, SSH, dependencies, backend configuration and distro-specific masks remain baseline-owned. |
| Scenario inputs | Packages, attachments, documents, future versions, deliberate file/launcher mutations and policy/grants/usage retain independent provenance. Provisioning never preseeds results. |

One `native-runtime` build per target supplies finite subsets and their declared
unions. Subsets select files from that build; guests receive only the selected
closure.

## Bundle identity and publication

Native runtime, complete artifacts and packages have separate source closures
and provenance. [artifact_inputs.py](../../tools/artifact_inputs.py),
[package_inputs.py](../../tools/package_inputs.py) and
[test_storage.py](../../tools/test_storage.py) own input identity and declaration.
Dispatch declarations match actual consumers, including empty and dormant branches.

Build frozen sources in host-side target environments. Record source, toolchain,
OS, release, architecture and runtime dependencies separately from output digests.
Verify target ABI compatibility and recheck sources before publication to prevent
mixed builds.

A bundle contains a versioned manifest, payload and completion marker. The
manifest binds each member's length, checksum, mode, symbolic owner, finite
destination ID, subset, absence controls and native actions. Paths derive from
maintained declarations. Verification rejects unsupported schemas, malformed or
duplicate fields, unsafe members, links, devices, undeclared bytes and inconsistent
lengths before mutation. Independent verification of the completed tree precedes
atomic publication. The
[bundle contract](../../tests/support/README.md#frozen-native-fixture-bundles)
defines the format.

## Execution lifetime

Select and register immutable inputs before lifecycle lease acquisition or restore,
within the enclosing
[central VM checkout](../Mandates/VM-Mandate.MD#central-vm-checkout).
Source edits cannot change an attempt's selection.

The producer lease owns temporary work. Copy verified output into the execution's
retained allocation before releasing that lease. Retain inputs until descendants
and owned cleanup finish. Each allocation has one deletion owner; independent
executions may retain independent bounded copies under existing
[storage and retention rules](../Mandates/Test-Storage-Mandate.md).

Reuse requires matching verified inputs already owned by the execution journal.
Privileged consumers authenticate the actual caller and open inputs read-only.
Incomplete nonempty inputs refuse rather than being replaced with a current build.

## Provisioning and readiness

The [shared provisioner](../../tests/support/README.md#attempt-owned-fixture-provisioning)
runs under the exclusive VM lease and guarded, watched SSH, after restore and
transport readiness and before fixture launch or scenario input.

Preflight checks the complete closure, accepted accounts, existing destinations
and native metadata. Unknown or modified files, unsafe paths, wrong owners and
incompatible inputs refuse before writes. Private staging belongs to the attempt.
Placement installs only declared bytes, owners and modes, using existing native
trust, admission and label APIs while preserving unrelated and product policy.

Independent readback verifies bytes and metadata. A harmless runtime witness
checks activation as the accepted child. The headless hard witness requires
`ONPC_TEST_APPLICATION_READY` and exit 0. The native witness verifies its executable
and modules, starts it with `--stay-alive`, observes the marker and stops only its
recorded owned process, requiring exit 0. Runtime markers complement manifest
verification.

Readiness binds the manifest, subset, actual VM UUID, boot and attempt. Receipts
from snapshots or other attempts cannot establish readiness. Identical repeats
verify without rewriting matching payloads. Fresh attempts start fixture-free;
subset changes require another clean attempt. Empty closures verify absence and
acquire no native-input dependency.

Transfer, placement, activation or uncertain-reply failures invalidate the attempt.
Scenario input stays blocked, diagnostics remain retained and owned recovery
restores the recorded snapshot. Per-file retries cannot resume uncertain mutation.

## Idle maintenance refresh

Explicit live replacement supports the fixed `trusted-hard` subset through the
[idle maintenance route](../../tests/integration/README.md#idle-fixture-maintenance-refresh).
It requires verified retained input and an idle owned guest, with no fixture
worker, fixture-using graphical session or unowned process. Existing ownership
checks exclude concurrent input and launch; uncertainty refuses.

Refresh keeps the same subset and destinations. Verify closure A against retained
input, preflight B and retain both through cleanup. Invalidate A readiness before
writes; publish B readiness only after placement, native activation and independent
byte/runtime checks. Replace only A's verified files and exact native entries.
Fedora preserves enforcing SELinux and exact labels and admissions.

Success preserves boot, domain and snapshot identities, changes no product service
or policy and records a new diagnostic generation. Earlier results remain bound
to their original inputs. Failure requires owned recovery; same-boot recovery is
not guaranteed. Busy guests and subset changes require fresh preparation.

## Snapshot boundaries

Clean captures retain dependencies and product provenance while excluding movable
fixture payloads, copied sources and exact fixture admissions. Removal targets
only proven owned files and entries; unrelated state, account pictures and
recovery/environment records remain intact. Snapshot contents are immutable.

Recover existing owners before changing record contracts. Old payloads cannot
be silently adopted, and their journals cannot be rewritten to imply new ownership.
Fixture-only changes leave package and clean-snapshot identity independent.

## Runner integration

Runners share one post-SSH readiness step and existing attempt/staging ownership.
Each caller retains its restore, credential, package, upgrade and input guards.
Missing or incompatible inputs refuse before mutation or scenario input.

| Preparation envelope | Fixture boundary |
| --- | --- |
| Product-free system | Selected closure after transport readiness, before installation input; trusted hard by default, command only for Ubuntu removal/recovery and PAM histories. Preserve product absence. |
| Installed system | Trusted hard closure before case input; preserve installed history and restore mode. |
| Installed E2E | Native closure by default; the fixed consumers listed in the [preparation contract](../../tests/integration/README.md#ubuntu-installed-e2e-preparation) select the native/activity/baseline-child union before stage actions, with actual child-catalogue and activity readback under current readiness. Preserve online resume/rebind and explicit offline attachment. |
| Product-free E2E | Native closure after SSH, before customer package input; GDM-only entry uses an empty closure. |
| Standalone transfer | Transport-only preboot preparation, native provisioning after SSH, separate package-only transfer. |
| Standalone serial | Preserve credential/getty preboot lifetime; native provisioning precedes graphical or customer input. |
| Recorded serial | Bind selected input and fresh readiness to recorder provenance before the ready reply; preserve stage ordering and worker shutdown. |

Credential/display-only consumers and language-only profiles have no movable
fixture dependency. Attachments, document changes, new versions and launcher
mutations remain scenario actions. Transfer preserves recipient, replay,
collision and attempt guards; serial installation preserves reboot versus
refused-install logout results.

Each distinct target/preparation path requires selected-byte, metadata and runtime
verification, no-write repeats, fresh attempt/boot binding and owned cleanup before
worker input. Qualification establishes infrastructure readiness; customer results
remain the responsibility of consuming tests. Provisioning, activation, restore
or ownership changes require renewed verification of the affected boundary.
