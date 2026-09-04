# Task 18 — Package activation and saved-data migration

Execute 18A and 18B separately; each package fixture is built reproducibly and
installed only into its own disposable testbed.

## Task 18A

- Title: Test all package activation classes.
- Depends on: Task 17B.
- Complexity: high. The reviewed classification map and artifact builder make
  this a bounded package-lifecycle matrix.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Work:
  1. Build versioned fixtures differing in exactly one reviewed activation class:
     `none`, `process-restart`, `session-renewal`, and `reboot`. Use generated
     manifests and real maintainer scripts; never hand-edit the manifest.
  2. Install and upgrade fixtures, testing changed, added, and removed relevant
     files. Verify broker PID behavior, next-session payload behavior, reboot
     markers, and activation after reboot according to `Package-Update.md`.
  3. Verify configuration retry does not invent a reboot requirement or clear
     markers owned by other packages.
  4. Restart the package/broker with every enabled child and verify current
     extension publication and saved-policy enforcement.
  5. Record old/new package digests, boot IDs, broker PIDs, session IDs, and
     markers; update activation, startup, and restart mappings.
- Verification:
  - Run every activation fixture from a fresh testbed.
  - Run `make check-system VM_IMAGE=<verified-baseline>`, `make check`, and
    `git diff --check`.
- Completion criteria: all four activation classes follow the real package
  lifecycle with observable process, session, and boot results.

## Task 18B

- Title: Test migration interruption, retry, and invalid data.
- Depends on: Task 18A.
- Complexity: high. Atomic saved-data upgrades and service exclusion require
  careful failure orchestration across package scripts and records.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Inventory the actual saved-data versions and registered migration steps in
     `Data-Migration.md` and code. Build realistic fixtures for every supported
     version, including single-step and direct multi-version upgrades where
     those steps exist. Do not invent historical releases or schema changes.
  2. Exercise package-driven migration and interrupt between records using
     supported guest process controls. Prove the marker excludes the broker,
     configuration retry completes, and migrated records remain correct.
  3. Verify invalid data, duplicate keys, unsafe modes, future versions, missing
     migration steps, and unsupported rollback fail closed without defaults
     replacing user choices.
  4. Record migration and package evidence with no private record contents in
     exported logs; update migration and persistence mappings.
- Verification:
  - Run controller cleanup-safety regressions in isolation before interruption.
  - Run each upgrade/failure fixture from its own fresh testbed and compare
    before/after state through privileged guest assertions.
  - Run `make check-system VM_IMAGE=<verified-baseline>`, `make check`, and
    `git diff --check`.
- Completion criteria: every supported saved-data path and retry/failure
  boundary is verified through real package maintainer scripts.
