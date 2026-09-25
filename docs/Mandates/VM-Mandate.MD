# VM mandate

## Authority and operation

- Apply the repository-wide [approval contract](../Approval-Tools.md) to all VM
  work. Run authorized work unattended through its existing grants and validated
  tools. Reuse session and category-wide authorization; do not broaden libvirt
  grants or bypass a missing prerequisite or grant.
- Operate the pinned VM only through `tools/test-vm`. Do not bypass ownership,
  select another guest, or create snapshots, overlays or clones. Stop maintenance
  before system/E2E tests; reset is not a customer journey step.

## VM observation mandate

- Every VM operation, experiment, qualification, setup, maintenance and test must
  use the shared `watchvm` infrastructure, regardless of its caller or whether it
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
- `tools/watchvm` must remain read-only, live and interruption-free. Users can
  connect, disconnect and reconnect at any time, including between maintenance
  commands, without affecting VM operations. Viewer lifetime must never control
  the VM, its input, command execution or collector lifetime. Qualify new routes
  for intent-before-action, live screen/SSH visibility and independent viewing.

## VM-host setup and baseline

- `./setup.sh` is the sole public VM-host setup entry point. Modes must be
  retryable, preserve unrelated configuration and fail on missing prerequisites.
  Tests and builds report missing prerequisites; they do not install them.
- Baseline preparation is an explicit destructive operation through
  `tools/prepare-baseline --mode auto` (restore and update) or
  `tools/prepare-baseline --mode manual` (prepare the current state). Both require
  the VM off and confirmation before deleting all versioned app snapshots and
  creating or replacing `onpc_baseline`; see
  [VM prerequisites](../../tests/integration/Environment.md).
  Ordinary setup and E2E never prepare or replace it.
  Baseline preparation and E2E require the literal `TEST_ACCOUNT_PASSWORD` in the
  host's private `.envrc`; E2E never changes passwords.
