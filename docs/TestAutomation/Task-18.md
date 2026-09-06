# Task 18 — Package activation and saved-data migration

Execute 18A, 18B, and 18C separately; each package fixture is built reproducibly
and installed only into the guarded existing test VM. Reset the retained
product-free baseline only outside complete scenario attempts. Never create
an installed snapshot or restore between install, upgrade, retry, reboot,
remove, or reinstall steps. Real maintainer scripts and OS services execute
every package transition; host mocks are supporting tests only.

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
  - Run `make check-system ARTIFACT_DIR=<verified-directory>`, `make check`, and
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
  - Run `make check-system ARTIFACT_DIR=<verified-directory>`, `make check`, and
    `git diff --check`.
- Completion criteria: every supported saved-data path and retry/failure
  boundary is verified through real package maintainer scripts.

## Task 18C

- Title: Test real package removal, reinstall, and purge.
- Depends on: Task 18B.
- Complexity: high. Removal crosses real PAM, login-manager, identity, and
  policy ownership boundaries; mocked maintainer-script tests are insufficient.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Use the exact release artifact and the ownership/retention expectations in
     [the package removal lifecycle](../System-Design.md#package-removal-lifecycle).
     Execute one continuous real
     install → reboot → configure/use → remove → reboot → reinstall → purge
     sequence on the guarded VM. No VM checkpoint creates an intermediate state.
  2. Verify real PAM, GDM, AccountsService, kiosk identity, services, fapolicyd,
     generated integrations, and reboot markers across the sequence. Preserve
     unrelated users, administrator-owned integrations, and other packages'
     state. Read-only evidence corroborates actual package operations.
  3. Prove ordinary removal retains saved choices and reinstall uses them;
     prove explicit package purge performs only its documented product-owned
     cleanup. Do not manually delete or edit logs to manufacture evidence.
  4. Exercise documented refusal/retry cases against real guest state, including
     an active kiosk session and changed ownership/integration files. Keep
     adversarial fixtures separately identified and retain failure evidence.
  5. Publish installed assertions for Task 26C's graphical lifecycle journey,
     register these required system cases under the package area, and retain
     package/boot/process/ownership evidence with no PII export.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated controls.
  - Run the complete lifecycle and separate refusal/retry cases with the
    existing guarded system runner and a digest-identified artifact.
  - Verify host/baseline preservation and the documented final VM state.
  - Run `make check`, `git diff --check`, and the focused installed selectors
    introduced here; record them for the later `test-system AREA=package` alias.
- Completion criteria: real installed lifecycle and retry evidence complements
  existing mocked regressions; Task 26C still owns the continuous graphical
  customer lifecycle, including actual post-removal login.

### Supporting validation and acceptance boundary

The existing maintainer-script tests execute shell scripts against temporary
filesystems and fake account/service commands. Regressions cover removal and
purge, retry, aborted removal and first unpack, saved-data retention, symlinks,
mounts, changed identities and hooks, original PAM selections, local PAM edits,
reboot notifier absence/failure/deferral, preservation of other reboot requests,
and reinstall. The staging build checks the real payload and activation
manifest without installing it on the development workstation.

These checks do not establish that the full Ubuntu VM lifecycle has passed.
Task 18C requires the continuous install → reboot → configure/use → remove →
reboot → reinstall → purge sequence above with real GDM, PAM, AccountsService,
and fapolicyd, plus evidence for the refusal and retry cases.
