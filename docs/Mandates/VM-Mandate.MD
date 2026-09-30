# VM mandate

## Authority and operation

- Apply the repository-wide [approval contract](../Approval-Tools.md) to all VM
  work. Run authorized work unattended through its existing grants and validated
  tools. Reuse session and category-wide authorization; do not broaden libvirt
  grants or bypass a missing prerequisite or grant.
- Test launchers `tools/run-tests`, `tools/fix-tests` and `tools/write-e2e` read
  `config/test-vm.json`: only entries whose `enabled` is the string `"true"`
  participate, and its positive integer `concurrency` caps simultaneous guests.
  They drain that finite queue, including after an individual VM fails. Tests
  within each VM remain ordered. `--vm NAME` narrows tests to one enabled entry.
  VM maintenance and preparation still require an explicit `--vm NAME` whose
  exact, case-sensitive name appears in the registry. `tools/cleanup-e2e` may
  reconcile all enabled VMs serially when the selector is omitted.
  Operate the selected, individually pinned VM only through `tools/test-vm`.
  Do not bypass ownership or create snapshots, overlays or clones. Stop maintenance
  before system/E2E tests; reset is not a customer journey step.
  Each VM has an exclusive preparation/execution lease and separate evidence
  journals. New controllers also hold a shared legacy root lease,
  excluding older controllers that still require it exclusively. Existing
  unfinished legacy journals refuse new execution until recovered; evidence
  is never discarded to enable parallelism.

## VM observation mandate

- Every VM operation, experiment, qualification, setup, maintenance and test must
  use the shared `watch` infrastructure, regardless of its caller or whether it
  is E2E. Start display observation through the shared VM lease; route host/SSH
  commands through the guarded command transport and publish a nonsecret intention
  through `watch_activity.operation` (or its `observed` decorator) before performing
  work. Keep that intention in the viewer footer throughout the operation,
  including waits and cleanup; nested operations restore the enclosing intention
  when finished.
- Reuse the existing display collector, authenticated command transcript and
  progress interfaces. Do not add per-workflow viewers, SSH tails, capture loops
  or alternate intention channels. A missing integration must be fixed in this
  shared infrastructure before adding its consumer. Preserve private-input
  filtering and the existing VM ownership/identity checks.
- `tools/watch` observes all registered VMs without a VM parameter.
  Its VM panels must remain read-only, live and interruption-free.
  The left runner terminal may request its displayed command's cooperative
  cancellation, including the owned cleanup of a VM test; it never sends direct
  input to the VM. Users can
  connect, disconnect and reconnect at any time, including between maintenance
  commands, without affecting VM operations. Viewer lifetime must never control
  the VM, its input, command execution or collector lifetime. Qualify new routes
  for intent-before-action, live screen/SSH visibility and independent viewing.

## VM-host setup and baseline

- `./setup.sh` is the sole public VM-host setup entry point. Modes must be
  retryable, preserve unrelated configuration and fail on missing prerequisites.
  Tests and builds report missing prerequisites; they do not install them.
- Baseline preparation is an explicit destructive operation through
  `tools/prepare-baseline --vm NAME --mode auto` (restore and update) or
  `tools/prepare-baseline --vm NAME --mode manual` (prepare the current state). Auto-mode
  refresh is preapproved when needed for authorized development or testing,
  including deletion of all versioned app snapshots and replacement of
  `onpc_baseline`. Do not ask the developer for confirmation; launcher/session
  work uses `tools/prepare-baseline --vm NAME --mode auto --y` to suppress the
  y/n prompt. Manual mode still requires explicit developer authorization;
  authorized launcher/session work uses `--mode manual --y`. Manual work omits
  `--y` to retain confirmation. Both modes still show the warning, require the
  VM off and retain all tool safety checks; see
  [VM prerequisites](../../tests/integration/Environment.md).
  Ordinary setup and E2E runners never prepare or replace it implicitly; invoke
  the preapproved auto-mode preparation separately when needed.
  Baseline preparation and E2E require the literal `TEST_ACCOUNT_PASSWORD` in the
  host's private `.envrc`; E2E never changes passwords.
