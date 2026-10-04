# VM mandate

This mandate owns VM target selection, observation, leases and preparation
lifetime. [Approval tools](../Approval-Tools.md) owns command grants;
[test maintenance](../../tests/README.md#all-established-regressions) owns runner
scheduling and [E2E execution](../TestAutomation/E2E-Execution-Contracts.md#live-verification-contract)
owns task acceptance. A documentation-only reconciliation performs no VM work
and supplies no live qualification.

## Authority and operation

- Apply the repository-wide [approval contract](../Approval-Tools.md) to all VM
  work. Run authorized work unattended through its existing grants and validated
  tools. Reuse session and category-wide authorization; do not broaden libvirt
  grants or bypass a missing prerequisite or grant.
- Test launchers `tools/run-tests` and `tools/fix-tests`, and
  preparation tools `tools/prepare-baseline` and `tools/prepare-appsnapshot`, read
  `config/test-vm.json`. Without `--vm`, they select entries whose `enabled` is
  the string `"true"`. `--vm` accepts one exact name or ID, a comma-separated
  list of names/IDs, `all-enabled` (the default selection), or `all` (every
  registered VM, including disabled entries). Explicit names/IDs also include
  disabled entries. Duplicate aliases execute once, in first-selected order;
  invalid selectors fail before any work starts.
  The positive integer `concurrency` caps simultaneous operations with or without
  `--vm`. Each free slot immediately takes the next VM, without waiting for the
  other workers. The finite queue drains even after an individual VM fails.
  Tests within each VM remain ordered. Preparation uses isolated workers;
  baseline helper refresh runs once after workers finish. Cancellation stops
  queued work and waits for active cleanup; an active baseline replacement
  finishes before returning cancellation because it has no cooperative stop protocol.
  VM maintenance still requires one explicit `--vm NAME` whose exact,
  case-sensitive name or ID appears in the registry.
  Automation and agent sessions use `--y` for authorized preparation; manual
  work omits it to retain confirmation. Multiple selections are confirmed
  together before workers start. An omitted selector prepares all enabled VMs.
  `tools/write-e2e` also defaults to the enabled queue with the same concurrency
  cap; its explicit selector remains one registered name or ID.
  All `--vm` and Make
  `VM=` selectors resolve names and IDs from the current JSON on invocation.
  IDs are unique positive decimal strings or integers; renumbering them requires
  no tools refresh or baseline replacement. Controllers retain canonical names
  for leases, UUID pins and active-run ownership, never a saved ID mapping.
  `tools/cleanup-e2e` may
  reconcile all enabled VMs serially when the selector is omitted.
  Operate the selected, individually pinned VM only through `tools/test-vm`.
  Do not bypass ownership or create snapshots, overlays or clones outside the
  maintained preparation/execution routes. Stop maintenance
  before system/E2E tests; reset is not a customer journey step.
  Root OS investigation uses `tools/test-vm --vm NAME exec -- COMMAND [ARG ...]`
  in an owned running online app-snapshot maintenance instance. Arbitrary command
  arguments and root privileges apply only in the guest. The route must reuse
  the existing private SSH identity, guarded transport, exclusive lease and
  observation; it must never restore the guest to inspect it or adopt another
  controller's running instance.
  Probing every registered VM has standing authorization, including entries
  disabled for test scheduling. Direct `tools/test-vm` guest commands, including
  guest shells and interpreters, require no additional command approval or
  developer confirmation. The installed helper's Polkit grant is automatic for
  the active local administrator; unavailable authorization fails without an
  authentication dialog. Reuse that grant and retain all identity, ownership,
  lease and observation checks.
  Each VM has an exclusive preparation/execution lease and separate evidence
  journals. New controllers also hold a shared legacy root lease,
  excluding older controllers that still require it exclusively. Existing
  unfinished legacy journals refuse new execution until recovered; evidence
  is never discarded to enable parallelism.
- **Controller contention:** Checkout activity locks do not reserve the VM
  across every category transition or exclude work from another checkout.
  For `state:busy-controller` or a launcher ownership refusal, inspect the
  retained failure location and current runner/owner through authorized
  read-only diagnostics. A refusal before acquisition is infrastructure
  contention, not a product assertion. Attach only to a matching run in the
  current checkout; otherwise let the foreign owner finish its normal cleanup.
  Do not stop its VM/processes, clear locks/journals, or refresh the baseline
  to make room. Recheck readiness through the maintained route after release,
  then retry only the affected selection. If the owner cannot finish without
  external action, report that concrete blocker and preserve completed results.

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

- All reusable, one-time guest prerequisites belong to `tools/prepare-baseline`:
  dependencies, fixed fixture applications and launchers, and persistent harness
  settings. Runners, cases and app-snapshot preparation only verify them. Missing
  or stale prerequisites fail with baseline-refresh guidance; no on-the-fly
  installation, repair or alternate preparation route is permitted in tests.
  Attempt-specific SSH identities, evidence/transport state, product packages
  under test and deliberate scenario mutations remain attempt-owned. Do not
  preseed product policy, grants, usage or a scenario's expected result.
  This includes reusable native, Snap, Flatpak and offline-game fixtures once
  implemented. Their pending capability tasks must add preparation and read-only
  verification to the shared routes before consumers can use them. A package
  change explicitly exercised by a catalogue/update/removal case remains a
  scenario mutation; it is not an on-the-fly prerequisite repair.
- Preparation is an idempotent reconciliation of a finite declared inventory.
  Reuse matching state without rewriting it, update only proven owned inputs,
  preserve unrelated files/accounts/settings, and safely resume partial work.
  Refuse links, foreign ownership, ambiguous state and unexpected collisions.
  Verify bytes, modes, owners, launchers and configuration before capture; bind
  fixture sources to the baseline identity so stale baselines and derived app
  snapshots cannot pass. Cover first run, repeat, update and interrupted retry.
  Auto mode still applies available system updates and replaces snapshots as
  documented; idempotence never weakens the lease, provenance or product-free gate.
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
  authorized launcher/session work uses `--mode manual --y`. Interactive invocation omits
  `--y` to retain confirmation. Both modes still show the warning, require the
  VM off and retain all tool safety checks; see
  [VM prerequisites](../../tests/integration/Environment.md).
  Ordinary setup and E2E runners never prepare or replace it implicitly; invoke
  the preapproved auto-mode preparation separately when needed.
  Baseline preparation and E2E require the literal `TEST_ACCOUNT_PASSWORD` in the
  host's private `.envrc`; E2E never changes passwords.
