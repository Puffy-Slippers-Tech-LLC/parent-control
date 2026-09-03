### Task 12 — Add safe immutable VM baselines and disposable overlay clones

- Complexity: very high. This controls destructive boundaries, libvirt storage,
  identity, credentials, and reliable cleanup.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: make every guest mutation disposable while preserving the protected
  Ubuntu baseline and the development host.
- Work:
  1. Extend the guarded integration controller with explicit commands to build a
     powered-off Ubuntu 26.04 Desktop baseline and to create a unique QCOW2
     overlay clone from an explicitly supplied baseline path.
  2. Keep the current official-image digest verification, deterministic account
     provisioning, exact package matrix, random per-run credentials, marker,
     token-bound domain description, SSH host-key isolation, redaction, and exact
     storage deletion checks.
  3. Create two clean baseline products: Ubuntu Desktop before product install
     and product-installed/rebooted baseline generated from a named Debian
     artifact. Record provenance and digests for both.
  4. Never mutate or revert the `ubuntu26.04` golden domain. Never attach its
     active writable layer to a test domain.
  5. Define generated test domains without filesystem passthrough, shared host
     directories, USB redirection, or access to `/Data`. Transfer artifacts over
     the guarded SSH channel or a read-only generated disk.
  6. Make teardown recoverable and exact: stop and undefine only the token-matched
     disposable domain, then remove only its validated overlay, seed, credentials,
     and state directory.
  7. Add signal handling and a stale-run audit command. Never perform wildcard
     cleanup.
  8. Add unit tests for every refusal and target-validation path and update the
     integration README.
- Verification:
  - Run host-safe harness unit tests.
  - Create, boot, shut down, and destroy one non-product disposable clone.
  - Prove the baseline digest did not change and no filesystem share exists in
    generated domain XML.
  - Run `make check` and `git diff --check`.
- Completion criteria: all later VM tests consume isolated overlays and cannot
  write the protected VM or the host `/Data` tree.

