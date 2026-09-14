# Task 18 — Package activation and saved-data migration

**Operator scope — 2026-09-14:** retain the mechanical depth of installation,
upgrade, migration, removal and recovery qualification below. Existing tests
are unchanged. This package work follows the prioritized customer queue and
does not gate unrelated feature scenarios. Internal assertions are labeled
package/system evidence; the customer portions of E2E-026/027 use only actions
and observations available to real users. Those continuous customer package
journeys are owned here, with Task 26C linking their canonical evidence.

Execute 18A, 18B, and 18C separately; each package fixture is built reproducibly
and installed only into the guarded existing test VM. Reset the retained
product-free baseline only outside complete scenario attempts. Never create
an installed snapshot or restore between install, upgrade, retry, reboot,
remove, or reinstall steps. Real maintainer scripts and OS services execute
every package transition; host mocks are supporting tests only.

## Implementation slices

**Scheduling — 2026-09-14:** these installed package tests follow the customer
queue and precede Task 20 under the current master checklist.
Use the existing guarded runner's package/reboot setup. Reuse applicable
[package and terminal helpers](Reuse-Map.md#installation-helper-and-open-limits),
qualifying a missing capability in its first affected consumer and publishing
the result for later tasks. Task 20's complete graphical clean-install
acceptance is not required. Keep 18C's real continuous lifecycle and terminal
notice assertions; setup-only evidence cannot replace those operations.

Use the [implementation workflow](Implementation-Workflow.md). These are small
work boundaries within the existing task, not extra acceptance checklists.
Verification below is task acceptance; edits use the smallest affected selection.

| Task | First proof, then expansion |
| --- | --- |
| 18A | One activation fixture end to end; then parameterize the remaining classes without rebuilding unchanged fixtures per case. |
| 18B | Inventory actual migration versions first; prove one supported path and interruption; then the finite invalid-data matrix. |
| 18C | One continuous removal/reinstall/purge journey; then isolated refusal/retry variants using the same ownership assertions. |

## Task 18A

- Title: Test all package activation classes.
- Depends on: verified installed-package setup and real versioned package
  fixtures. Deferred Task 17B and policy-acknowledgement design are not prerequisites.
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
     markers, and activation after reboot according to `Publishing.md#package-update-activation`.
  3. Verify configuration retry does not invent a reboot requirement or clear
     markers owned by other packages.
  4. Restart the package/broker with every enabled child and verify current
     extension publication and saved-policy enforcement.
  5. Record old/new package digests, boot IDs, broker PIDs, session IDs, and
     markers; update activation, startup, and restart mappings.
  6. Own the continuous customer E2E-026 path: configure through Parent, perform
     a real supported package update, follow the requested restart/logout/reboot
     through customer interfaces, reopen the app and observe retained choices
     and actual child use. Keep the internal assertions above separately labeled;
     a customer pass neither requires nor claims their proof.
- Verification:
  - Run every activation fixture from a fresh testbed.
  - Execute the complete E2E-026 customer update/resumed-use path through its
    guarded graphical selector; label visible and mechanical results separately.
  - Register and run this task's installed area with F1 and its prerequisite
    closure, then `make check` and `git diff --check` once for acceptance.
    Focused iterations select the affected case; no direct host guest-pytest.
- Completion criteria: all four activation classes follow the real package
  lifecycle with observable process, session, and boot results, and the complete
  customer update path has passing visible evidence.

## Task 18B

- Title: Test migration interruption, retry, and invalid data.
- Depends on: Task 18A.
- Complexity: high. Atomic saved-data upgrades and service exclusion require
  careful failure orchestration across package scripts and records.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Inventory the actual saved-data versions and registered migration steps in
     [Data migration](../SystemDesign/Data-Migration.md) and code. Build realistic fixtures for every supported
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
  - Register and run this task's installed area with F1 and its prerequisite
    closure, then `make check` and `git diff --check` once for acceptance.
    Focused iterations select the affected case; no direct host guest-pytest.
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
     generated integrations, and reboot markers across the sequence. After
     successful documented removal, the last printed output must be
     `*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***`
     and must be red on a capable terminal. Preserve unrelated users,
     administrator-owned integrations, and other packages' state. Read-only
     evidence corroborates actual package operations.
  3. Prove ordinary removal retains saved choices and reinstall uses them;
     prove explicit package purge performs only its documented product-owned
     cleanup. Do not manually delete or edit logs to manufacture evidence.
  4. Exercise documented refusal/retry cases against real guest state, including
     an active kiosk session and changed ownership/integration files. Keep
     adversarial fixtures separately identified and retain failure evidence.
  5. Retain installed assertions separately from the customer lifecycle journey,
     register these required system cases under the package area, and retain
     package/boot/process/ownership evidence with no PII export.
  6. Own E2E-027's continuous customer path through real terminal/UI operations:
     install/reboot/configure/use, remove/reboot, ordinary login, reinstall and
     observe retained choices, then purge and observe the documented fresh
     behavior on subsequent use where applicable. No helper or internal-state
     check substitutes for a claimed customer action. Reuse the same attempt
     when it can provide separately labeled mechanical and visible evidence.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated controls.
  - Run the complete lifecycle and separate refusal/retry cases with the
    existing guarded system runner and a digest-identified artifact.
  - Execute the complete E2E-027 customer lifecycle through its guarded
    graphical selector; retain real post-removal login and reopened settings.
  - Verify host/baseline preservation and the documented final VM state.
  - Run `make check`, `git diff --check`, and the focused installed selectors
    provided by F1; record them for the later `test-system AREA=package` alias.
- Completion criteria: real installed lifecycle and retry evidence complements
  existing mocked regressions; the separately labeled continuous customer
  lifecycle includes actual post-removal login and visible saved-choice behavior.

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
