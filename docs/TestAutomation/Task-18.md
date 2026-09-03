### Task 18 — Test package activation and saved-data migration end to end

- Complexity: very high. Multiple real package versions and activation boundaries
  must be produced and verified.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove the package lifecycle described in `Package-Update.md` and
  `Data-Migration.md` on installed machines.
- Work:
  1. Build versioned package fixtures that differ in exactly one reviewed
     activation class: `none`, `process-restart`, `session-renewal`, and `reboot`.
  2. Install and upgrade them in order, proving broker PID behavior, session
     payload behavior, reboot-required markers, and next-boot activation.
  3. Create realistic records for every released saved-data version and perform
     single-step and multi-version upgrades with the package scripts.
  4. Interrupt migration between records, verify the marker keeps the broker
     unavailable, retry package configuration, and prove already migrated records
     remain correct.
  5. Verify invalid, duplicate-key, unsafe-mode, future-version, and rollback-
     unsupported data fail closed without replacement by defaults.
  6. Test a package or broker restart with every enabled child and prove current
     extension payload publication and saved-policy enforcement.
  7. Update package, migration, persistence, and startup requirement mappings.
- Verification:
  - Run every upgrade fixture from its own fresh overlay.
  - Record old/new package digests, boot IDs, broker PIDs, session IDs, migration
    records, and reboot markers.
  - Run `make check-system`, `make check`, and `git diff --check`.
- Completion criteria: all activation classes and released migration paths are
  verified through real package maintainer scripts.

