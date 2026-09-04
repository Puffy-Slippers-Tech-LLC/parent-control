### Task 12C — Capture and verify the prepared VM baseline

- Depends on: Tasks 12A and 12B.
- Complexity: medium. The operator runs the already-tested privileged commands;
  Codex verifies their outputs through a fixed read-only acceptance checklist.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Model rationale: acceptance checks use the implemented controller's provenance
  contract. New capture/recovery implementation is not part of this task.
- Execution locations: `make prep-vm` is run manually by the developer inside
  the existing `ubuntu26.04` guest from the shared
  `/Data/Code/PST/parent-control` checkout. `make prep-host` is then run manually
  by the developer from that same path on the development host. Both commands
  use fixed validated defaults and take no VM, image, UUID, checkout, or output
  path parameters. Codex performs only read-only inspection and host-safe
  verification after the developer says both commands completed.
- Objective: produce and verify the one-time, product-free Ubuntu 26.04 baseline
  that later system-test planning can consume.
- Operator sequence:
  1. Confirm that the terminal is inside the intended `ubuntu26.04` VM, enter a
     root shell, change to `/Data/Code/PST/parent-control`, run `make prep-vm`,
     and enter the shared password once at its no-echo prompt. Preparation sets
     the guest hostname to `ubuntu26.04` automatically. Do not install
     the product.
  2. Return to the development/libvirt host, change to its repository checkout,
     and run `make prep-host`. Let it shut down the source VM cleanly and finish
     the baseline capture, restarting a prior interrupted conversion when the
     controller's validated phase record requires it. Do not run
     `make installdeb` on the host.
  3. Report completion and the baseline/provenance paths to Codex. If either
     command fails or is interrupted, keep all state and report its exact output;
     do not delete partial files or alter libvirt manually. Re-run plain
     `make prep-host` after an interrupted conversion so the controller can
     validate its phase record, discard only its recorded partial image, and
     restart the conversion safely.
- Codex verification after operator completion:
  1. Read the preparation record, capture phase record, provenance document,
     libvirt domain XML/state, QCOW2 information, permissions, and digest using
     read-only commands. Any libguestfs access must explicitly select read-only
     mode and QCOW2 format. Confirm the source domain is shut off and its disk
     chain was not changed by capture.
  2. Confirm the baseline is an independent, non-writable QCOW2 image, passes
     integrity checking, matches its recorded SHA-256, describes Ubuntu 26.04,
     contains the four fixed test identities and no recorded secret, and has no
     installed Oh No! Parent Control package, payload, configuration, saved
     state, integration, logs, or product-created account. Repository source and
     build artifacts do not count as an installation.
  3. Confirm read-only that the development host has no installed product
     package, product service, product PAM/Polkit integration, or product-created
     accounts. Repository source and build artifacts do not count as an install.
  4. Run the focused host-safe preparation tests, `make check`, and
     `git diff --check`.
  5. Mark Task 12C complete and append its completion record only after the real
     baseline and every verification above pass. Tasks 12A and 12B must already
     have their own completion records from their implementation sessions.
- Completion criteria: the prepared, product-free baseline exists with verified
  provenance and digest; the source VM is safely powered off with its original
  disk chain intact; the development host remains product-free; and no product
  installation or later system test has been run. Stop so the remaining VM test
  workflow can be planned in the next task.
