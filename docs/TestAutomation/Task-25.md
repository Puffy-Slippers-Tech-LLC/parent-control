# Task 25 — Customer application use and user isolation

Follow [E2E-Coverage.md](E2E-Coverage.md). Configure through Parent, launch
through the supported customer route and observe the resulting window, denial
or terminal output. Use normal user switching to observe other users.
Task 15's internal matrix and policy acknowledgement are not dependencies.

## Implementation slices

First complete one native allow/block journey, then extend only for distinct
supported routes and behavior. Reuse prepared real apps and graphical input.
A missing native/Snap/Flatpak asset is a concrete setup need for its consumer,
not a reason to build an execution-witness framework.

Before expanding legacy E2E-019's cross-product, identify each distinct
customer behavior. Retain supported routes, meaningful matching cases and both
screen-time settings where behavior differs; do not multiply unrelated choices.
Record deduplication and scope transfers separately from passing scenarios.

## Task 25A

- Title: Application launch routes and matching.
- Depends on: installed app assets and the selected Parent/login interactions.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-019/020 and canonical launch portions of E2E-006.
- Work:
  1. Set allowed, hard and soft choices in Parent, including control enabled
     and disabled where specified. Use a real request for a soft-app exception.
  2. Launch native applications through app grid/desktop entry, file manager
     and guest terminal where supported. Launch Snap/Flatpak through their
     public user interfaces. Observe usable apps or the documented denial.
     Do not inspect fapolicyd, launch probes, kernel identities or rules.
  3. Exercise exact/version-tolerant matching, spaces, unrelated files and
     documented copied/renamed limitations by ordinary file/app operations.
     Observe the resulting launch behavior. Do not certify future filenames
     by reading generated policy.
  4. Perform a supported app update or removal and revisit Parent/launch.
     Observe displayed selection and retained matching behavior. Unrelated
     package assets may be fixture setup; a tested update uses the real
     customer operation. Mechanical package assertions belong to Task 18.
  5. Switch to another user and launch/use the same app for the assigned
     isolation case.
- Verification/completion: complete the finite assigned customer variants,
  retain visible evidence and existing setup/cleanup safeguards, and run
  affected regressions/common checks at stable task acceptance.
  A generic failed launch without the expected observable behavior is not a pass.

## Task 25B

- Title: App-window effects and other-user continued use.
- Depends on: only the real launch, request and user-switching steps used.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-007/021; reuse one canonical journey per behavior.
- Work:
  1. Log in and open apps as the selected child and another user. Establish
     supported retained sessions through real login/Switch User operations.
  2. Save a restrictive policy, approve each soft-app choice, or revoke through
     real interfaces in separately declared paths. Observe required app windows
     close/remain and subsequent launches permit/deny access.
  3. Switch to the other user's desktop and continue interacting with their app.
     Observe that the selected-child action did not interrupt their use.
  4. For expiry/replacement behavior, reuse Task 22/26's customer sequence:
     natural lock, real replacement approval, normal unlock and observed app
     windows. Do not inspect processes while locked or infer internal ordering.
- Verification/completion: every assigned window/access/isolation result passes
  by customer operation and observation with safe cleanup. No PID, cgroup,
  Snap-label, Flatpak-instance, filter or grant assertion is required.
- Separate work: partial-termination injection, confinement internals and
  rollback proofs remain in [Task 15B](Task-15.md#task-15b); existing regressions
  are unchanged. A visible failure remains a separate product blocker.
