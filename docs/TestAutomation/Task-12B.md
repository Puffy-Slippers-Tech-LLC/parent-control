### Task 12B — Add host-only pre-install baseline snapshot

- Depends on: Task 12A.
- Complexity: very high. The workflow controls the existing domain, validates
  its backing chain, shuts it down, and recovers interrupted snapshot creation.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Execution location: implement and test in the development checkout. The
  operator runs `make prep-host` on the development/libvirt host after
  `make prep-vm` succeeds inside the existing guest.
- Objective: save a product-free baseline as the internal libvirt snapshot
  `oh-no-parent-control-baseline` of `ubuntu26.04`. Later tests use the same
  VM and repeatedly revert this snapshot. Never copy the VM, convert its disk,
  create an overlay, or define a replacement domain.
- Fixed resources:
  - Connection: `qemu:///system`.
  - Domain: `ubuntu26.04`.
  - Backing-chain anchor: `/Data/virt-manager/ubuntu26.04.qcow2`.
  - Snapshot: `oh-no-parent-control-baseline`.
  - Controller state: `/Data/virt-manager/oh-no-parent-control-baseline-state/`.
  - Host and guest checkout: `/Data/Code/PST/parent-control`.
  No operator resource overrides are supported.
- Work:
  1. Pin maintained public libvirt, QEMU, and libguestfs development tools in
     `setup.sh` and `tests/test-tools-ubuntu-26.04.txt`. Never install the
     product through this workflow. An existing host installation is ignored.
  2. Keep `make prep-host` and read-only dependency diagnostics. Report missing
     tooling with instructions to run `./setup.sh`; do not install it.
  3. Before shutdown, validate connection, domain name/UUID, active/persistent
     storage, one writable QCOW2 disk, canonical chain paths, and the anchor.
     Reject missing files, symlinks, block jobs, ambiguous storage, or external
     firmware/TPM state not covered by an offline internal disk snapshot.
     Preserve existing external backing chains and unrelated snapshots.
  4. Request clean ACPI shutdown through libvirt and use a bounded event-driven
     wait. Never force-stop the VM or perform host-wide process cleanup.
  5. Inspect the stopped guest with explicit read-only QCOW2 libguestfs access.
     Verify the Task 12A marker, script digest, release, identities, roles, and
     absence of guest product residue. Repository/build files are permitted.
  6. Use the public libvirt snapshot API with internal disk storage, no memory
     image, and atomic creation. Preserve libvirt metadata so standard
     snapshot-revert can restore the baseline repeatedly.
  7. Persist a private atomic journal binding the operation to domain/disk
     identities, preparation evidence, backing digests, and snapshot identity.
     Record no passwords, hashes of passwords, raw account tables, or tokens
     from the guest. Do not create a baseline image or image sidecars.
  8. Recover interruptions by reconciling the journal with libvirt and the
     internal disk snapshot. Never overwrite/redefine/delete a same-name
     snapshot. Repeated completed runs preserve the original snapshot even
     after testing changes the current guest or installs the product.
     A repeat must not shut down, re-inspect, recapture, or revert a test guest.
  9. Test storage/identity refusals, public API flags/XML, clean shutdown,
     interrupted creation before/after libvirt success, incomplete metadata,
     replaced snapshots, and repeated runs after guest writes. Mock all real
     VM operations; prove there is no disk conversion or VM creation.
  10. Document creation, recovery, and repeated manual reset of the existing VM.
      Shared host files are outside the snapshot. Automated test runners must
      detach the writable preparation share before each test boot, including
      after snapshot reversion restores the saved domain definition.
- Verification:
  - Run cleanup-safety regressions in isolation.
  - Run focused mocked host-controller tests, `make check`, command-help
    diagnostics, and `git diff --check`.
  - Do not run preparation, shut down the real VM, create a real snapshot, or
    revert it during implementation. Task 12C owns manual acceptance.
- Completion criteria: `make prep-host` creates and preserves the named
  internal snapshot on the existing VM, with no VM copy and no installation.
  Task 12C remains a separate manual acceptance task.
