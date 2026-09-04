### Task 12B — Add host-only pre-install baseline capture

- Depends on: Task 12A.
- Complexity: very high. This controls a real libvirt domain, a QCOW2 backing
  chain, shutdown, interrupted image conversion, and immutable output paths.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Execution location: implementation and host-safe tests happen in the
  development checkout. A later operator step runs `make prep-host` manually on
  the development/libvirt host, after `make prep-vm` succeeds in the guest.
- Objective: capture the prepared, product-free `ubuntu26.04` VM as a separate,
  powered-off QCOW2 baseline from which later test guests can be planned,
  without installing the app or changing the source VM's disk chain.
- Fixed host resources:
  - Libvirt connection: `qemu:///system`.
  - Source domain: `ubuntu26.04`.
  - Required backing-chain anchor:
    `/Data/virt-manager/ubuntu26.04.qcow2`.
  - Default baseline directory:
    `/Data/virt-manager/oh-no-parent-control-baselines/`.
  These defaults make plain `make prep-host` the documented command. Any
  supported override must still be explicit, canonical, validated, and covered
  by the same refusal tests.
- Work:
  1. Add only the development-host packages needed by baseline preparation to
     `setup.sh`, using maintained public tools such as libvirt clients,
     `qemu-img`, and a read-only offline guest-inspection tool. `setup.sh` may
     install development/virtualization tooling, but it must never install the
     Oh No! Parent Control package, configure its services, create its users, or
     alter a VM.
  2. Add a `make prep-host` entry point backed by a host controller. It must
     report missing tooling and direct the operator to `./setup.sh`; it must not
     install packages itself.
  3. Before shutdown or file creation, validate the exact libvirt connection,
     domain name and UUID, one writable file-backed system disk, complete QCOW2
     backing chain, and the required canonical anchor path. Resolve the current
     top disk from libvirt rather than assuming it is the anchor file. Reject
     symlinks, unexpected devices, malformed XML, missing chain members, a
     running block job, or any ambiguous storage layout.
  4. Ask libvirt to shut down `ubuntu26.04` cleanly and wait with a bounded,
     event-driven deadline. Never use `destroy`, reset, snapshot-revert, process
     matching, or a host-wide cleanup. On timeout, leave the domain and all
     files intact and report the exact recovery state.
  5. With the domain confirmed shut off, inspect it read-only and require the
     exact root-owned preparation record produced by Task 12A. Verify its schema,
     Ubuntu release, script digest, four account identities and roles, and the
     absence of the installed Debian package and product payload.
  6. Capture the current top disk and its backing data into a new, independent
     QCOW2 image under the baseline directory. Use a unique validated temporary
     file, `qemu-img` conversion while the source domain is off, integrity
     checking, and atomic finalization. Do not alter the source domain XML or
     disk chain, and never overwrite an existing baseline, provenance record, or
     digest file.
  7. Record a versioned provenance document beside the baseline containing the
     source domain UUID, source chain identities and pre-capture digests,
     preparation-record digest, Ubuntu release, fixed account names and roles,
     resolved UIDs, capture timestamp, output format and virtual size, and final
     SHA-256. Record no passwords, password hashes, SSH material, tokens, or raw
     account records. Make the finalized baseline non-writable and verify its
     ownership and mode.
  8. Make capture pausable and resumable through an atomic, root-controlled phase
     record. At minimum distinguish validation, shutdown requested, source off,
     conversion in progress, image verified, and finalized. Signal handling must
     stop at a safe boundary and preserve exact state for a later
     `make prep-host` invocation. Resume only after revalidating every recorded
     path, inode, domain identity, disk chain, and completed artifact; never use
     wildcard cleanup.
  9. Add unit tests for every refusal and resume path, including the source VM
     being absent, the anchor typo `/Data/virt-managewr/`, an unexpected active
     disk or backing chain, symlinks, pre-existing outputs, product presence,
     marker mismatch, shutdown timeout, interrupted conversion, digest mismatch,
     and a changed domain or file between phases.
  10. Update the integration README with the exact operator sequence, output
      locations, interruption recovery, and the invariant that the development
      host and source VM remain product-free. This task only captures the
      pre-install baseline; disposable clone creation and product tests are
      planned by later tasks.
- Verification:
  - Run the focused host-controller safety and resume unit tests with all libvirt
    and image operations mocked.
  - Run `make check`, `git diff --check`, and any new host-safe command-help or
    dry-validation checks.
  - Do not run `make prep-vm`, shut down the VM, or run `make prep-host` in this
    subtask.
- Completion criteria: the manual `make prep-host` workflow is implemented and
  host-tested; it can capture only the explicitly validated, prepared source VM
  into a separate product-free baseline; it is resumable after interruption;
  and no code path installs the product on the host or source VM. Do not perform
  the real capture or mark Task 12C complete in this session.

