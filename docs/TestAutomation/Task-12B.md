### Task 12B — Add host-only pre-install baseline capture

- Depends on: Task 12A.
- Complexity: very high. This controls a real libvirt domain, a QCOW2 backing
  chain, shutdown, interrupted image conversion, and immutable output paths.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Model rationale: the source-disk guards, durable phase state, and interruption
  recovery form one safety boundary. Keep their implementation and refusal tests
  together; splitting the small setup/README work would add a handoff without
  removing meaningful complexity.
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
  - Host and source-guest checkout:
    `/Data/Code/PST/parent-control`.
  These fixed values make plain `make prep-host` the documented command. No VM,
  UUID, anchor, checkout, image, or baseline-directory parameter is required or
  supported. Test seams may inject values only in host-safe unit tests and must
  not become operator-facing overrides. The existing source image is a
  prerequisite; this workflow must not download a cloud image or create a new
  source VM or source image.
- Work:
  1. Add only the development-host packages needed by baseline preparation to
     `setup.sh`, using maintained public tools such as libvirt clients,
     `qemu-img`, and a read-only offline guest-inspection tool. `setup.sh` may
     install development/virtualization tooling, but it must never install the
     Oh No! Parent Control package, configure its services, create its users, or
     alter a VM. Pin the Ubuntu 26.04 package versions consistently with the
     existing development dependencies and update
     `tests/test-tools-ubuntu-26.04.txt` with the exact tools and versions.
  2. Add a `make prep-host` entry point backed by a host controller. It must
     report missing tooling and direct the operator to `./setup.sh`; it must not
     install packages itself.
  3. Before shutdown or file creation, validate the exact libvirt connection,
     domain name and UUID, one writable file-backed system disk, complete QCOW2
     backing chain, and the required canonical anchor path. Resolve the current
     top disk from libvirt rather than assuming it is the anchor file. Reject
     symlinks, unexpected devices, malformed XML, missing chain members, a
     running block job, or any ambiguous storage layout. The source VM's
     preparation-only `/Data` virtiofs share is expected and is not a system
     disk or part of the QCOW2 baseline; record it as source-domain context and
     never propagate it to a disposable test guest.
  4. Ask libvirt to shut down `ubuntu26.04` cleanly and wait with a bounded,
     event-driven deadline. Never use `destroy`, reset, snapshot-revert, process
     matching, or a host-wide cleanup. On timeout, leave the domain and all
     files intact and report the exact recovery state.
  5. With the domain confirmed shut off, inspect it read-only and require the
     exact root-owned preparation record produced by Task 12A. Verify its schema,
     Ubuntu release, script digest, four account identities and roles, and the
     absence of the installed Debian package and every product-residue category
     defined by Task 12A. Repository source and build artifacts do not count as
     an installation. Invoke libguestfs inspection with explicit read-only mode
     (`--ro` or the corresponding `readonly=true` API) and an explicit QCOW2
     format; never rely on a tool's default access mode or format probing.
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
  8. Make the controller workflow interruptible and restartable through an
     atomic, root-controlled phase record. At minimum distinguish validation,
     shutdown requested, source off, conversion in progress, image verified,
     and finalized. `qemu-img convert` itself is never resumed. After an
     interrupted conversion, revalidate every recorded path, inode, domain
     identity, and disk-chain member; reject any mismatch; remove only the exact
     recorded incomplete temporary image; and start a complete conversion into
     a newly created unique temporary file. Never reuse, trust, or finalize a
     partial conversion, and never use wildcard cleanup. Signal handling may
     signal only the conversion process directly spawned and identity-recorded
     by the controller, then must preserve the exact phase for the next plain
     `make prep-host` invocation. A completed verified artifact may be reused
     only after its recorded identity and digest are revalidated.
  9. Add unit tests for every refusal, recovery, and restart path, including the source VM
     being absent, the anchor typo `/Data/virt-managewr/`, an unexpected active
     disk or backing chain, symlinks, pre-existing outputs, product presence,
     marker mismatch, shutdown timeout, interrupted conversion, digest mismatch,
     and a changed domain or file between phases. Prove that an interrupted
     conversion is restarted in a new temporary file and that its partial image
     can never be finalized.
  10. Update the integration README with the exact operator sequence, output
      locations, interruption recovery, and the invariant that the development
      host and source VM remain product-free. This task only captures the
      pre-install baseline; disposable clone creation and product tests are
      planned by later tasks. Replace the existing cloud-image and brand-new-VM
      setup path as the supported prerequisite: the already-present
      `/Data/virt-manager/ubuntu26.04.qcow2` source and `ubuntu26.04` domain are
      the only Task 12 source. Preserve reusable guard and redacted-artifact
      safety behavior from the existing harness where later tasks consume it,
      but do not retain a second supported baseline path.
- Verification:
  - Run controller cleanup-safety regressions in isolation before any
    host-integrated test that terminates a spawned process.
  - Run the focused host-controller safety, recovery, and restart unit tests with
    all libvirt and image operations mocked.
  - Run `make check`, `git diff --check`, and any new host-safe command-help or
    dry-validation checks.
  - Do not run `make prep-vm`, shut down the VM, or run `make prep-host` in this
    subtask.
- Completion criteria: the manual `make prep-host` workflow is implemented and
  host-tested; it can capture only the explicitly validated, prepared source VM
  into a separate product-free baseline; it safely restarts rather than resumes
  an interrupted conversion; and no code path installs the product on the host
  or source VM. Do not perform the real capture or mark Task 12C complete in this
  session.
