### Task 12C — Create and verify the prepared VM baseline snapshot

- Depends on: Tasks 12A and 12B.
- Complexity: medium. The operator runs privileged preparation; Codex verifies
  the resulting snapshot using read-only inspection.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Execution locations: the developer runs `make prep-vm` inside
  `ubuntu26.04`, then `make prep-host` on its development/libvirt host.
  Both use `/Data/Code/PST/parent-control` and fixed resource identities.
  Codex performs read-only acceptance after the developer reports completion.
- Objective: create the reusable, product-free internal snapshot
  `oh-no-parent-control-baseline` on the existing `ubuntu26.04` VM.
  There is no copied VM, separate baseline QCOW2, or disposable overlay.
- Operator sequence:
  1. Inside the intended VM, run `make prep-vm` from the fixed checkout and
     enter the shared password at its no-echo prompt. Do not install the product
     before creating the baseline.
  2. On the host, enter a root shell in the checkout and run `make prep-host`.
     Let it shut down the guest cleanly, inspect it, and create the named
     snapshot. Do not start it or edit storage concurrently.
  3. Report completion. If interrupted, preserve all state and rerun
     `make prep-host`; it reconciles the recorded snapshot without replacing it.
- Read-only acceptance:
  1. Verify the private phase record under
     `/Data/virt-manager/oh-no-parent-control-baseline-state/` is finalized.
     Inspect domain XML/state, the named libvirt snapshot XML, and explicit
     QCOW2 information. Confirm the domain UUID and disk paths are unchanged,
     and that the snapshot is internal, named correctly, and taken at shutoff.
  2. Confirm the internal QCOW2 snapshot identity matches the journal, libvirt
     metadata includes the saved domain configuration, and preparation evidence
     describes the expected Ubuntu release/accounts without secrets. Confirm
     no image copy was created. Any offline guest access must be read-only
     with explicit QCOW2 format; at initial acceptance the guest is product-free.
  3. Run focused host-safe preparation tests, `make check`, and
     `git diff --check`. An installed product on the host is allowed and is
     not inspected.
  4. Mark Task 12C complete and append its record only after the real snapshot
     and all acceptance checks pass. Do not restore the snapshot as part of
     read-only acceptance.
- Subsequent testing: boot and test the existing VM, then shut it down cleanly,
  use `virsh --connect qemu:///system snapshot-revert ubuntu26.04 oh-no-parent-control-baseline`,
  and boot it again. Revert discards test disk changes and preserves the named
  baseline for further resets. Shared host files are not restored. Automated
  runners must detach the writable host share before each test boot.
- Completion criteria: the named internal snapshot exists on the existing VM
  with verified preparation and recovery evidence. The source is powered off
  at initial acceptance. No product installation or later system test has been
  performed by this task. Stop before implementing later runner work.
