### Task 20 — Automate clean installation, reboot, and startup readiness

Follow [E2E-Coverage.md](E2E-Coverage.md). Audit the existing E2E-002 and assigned
E2E-028 variants before implementing gaps; real customer steps
and declared OS fault controls must have distinct categories and evidence.

## Implementation slices

Use the [implementation workflow](Implementation-Workflow.md). These are small
work boundaries within the existing task, not extra acceptance checklists.
Verification below is task acceptance; edits use the smallest affected selection.

| Task | First proof, then expansion |
| --- | --- |
| 20 | One real clean install/reboot/readiness journey; then separately declared startup failures. |

- Depends on: Task 19B.
- Complexity: high. This is the first complete release-path graphical job.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Model rationale: use Sol for implementation over qualified installation and
  reboot contracts. Use Astra high while missing authentication, private capture
  or boot-continuity boundaries require design or first live qualification;
  the active handoff selects the next slice under the shared model policy.
- Objective: prove a clean supported Ubuntu machine reaches a safe login screen
  after installing the exact release artifact.
- Work:
  1. Start from the before-product baseline and upload the exact `.deb`, fixture
     bundle, and their digests through the controlled asset channel. Provision
     accounts and unrelated fixture apps through supported helpers. Installation
     and reboot are asserted product lifecycle transitions in this task and
     remain real customer operations; other tasks may use verified package
     installation as prerequisite setup without replaying this acceptance case.
  2. Verify the product is absent, install the package through its real package
     path from the guest terminal with real administrator authentication,
     record output, and verify the product-created reboot marker. A hidden
     preinstalled image or helper installation is not this journey's evidence.
  3. Request an actual reboot through the customer-visible guest interface.
     Verify the boot identity changes and that GDM returns; do not reload VM
     state. Forced-power recovery belongs to a separately declared fault case.
  4. Assert visually that GDM becomes usable only after fapolicyd readiness.
     Independently prove the broker publishes its D-Bus object only after its
     startup reconciliation completes, as specified in the
     [startup design](../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle).
  5. Assert through serial that installed files, ownership, services, D-Bus,
     Polkit, PAM, session descriptors, configuration, extension payload, logs,
     and execution policy match the package.
  6. Prove a broker startup reconciliation failure prevents broker readiness and
     a fapolicyd readiness failure prevents managed graphical login startup.
  7. Collect all startup evidence and update installation/startup requirement
     mappings. Resolve E2E-002's existing `requirement_gap` against the normative
     lifecycle contract before readiness; keep broker and fapolicyd startup
     failures independently asserted even where they share scenario helpers.
- Verification:
  - Run runner cleanup-safety regressions in isolation before live scenarios.
  - Run every clean-install/startup-failure variant once as a complete attempt.
    Repetition follows the workflow's stability rule. Restore the retained
    baseline only outside attempts, never across a journey's reboot.
  - Run `make check-e2e ARTIFACT_DIR=<verified-directory> SCENARIO=E2E-002`,
    package-focused system tests, `make check`, and `git diff --check`.
- Completion criteria: a digest-identified release package passes a real clean
  installation and reboot with visible and backend readiness evidence. Register
  and run the separate E2E-028 startup-failure variants as well.

### Task 20 continuation — 2026-09-08

**Earliest ready task; not accepted.** [Task 19B remains accepted](Evidence/19B-Acceptance-20260908.md).
No earlier entry is bypassed; preserve [15A's later work](Task-15.md#task-15a-continuation--2026-09-08).

**Locally verified boundary:** [onpc_install.pm](../../tests/integration/graphical_smoke/lib/onpc_install.pm)
types only the fixed authenticated package command through the existing serial
console. It forces fresh sudo authentication, requires a distinct no-echo proof,
rejects command echo as completion, seals capture, suppresses private errors and
refuses retries. `onpc_serial::run_install` reaches it only after real fixture
login and shell readiness; the accepted smoke retains its original `run` path.

[InstallationBoundary.observe](../../tests/e2e/installation_boundary.py) orders
`install-ready`, `install-password`, `install-complete`; verifies transferred
assets and absence before input, binds the result to `VerifiedInputs`, and
rejects boot changes before/during each observation. Any refusal is terminal.
The separate `install-password` probe in
[installation_observations.py](../../tests/e2e/installation_observations.py)
follows the stock getty's foreground group, checking exact sudo argv, trusted
executable, fixture-owned Bash parent, process/session identities and disabled
echo. Existing absence/installed probes remain intact. Only safe fields leave
the guarded observation transport.

**Scope limit:** no live authentication/install is proven. The worker request
protocol does not yet dispatch this boundary; no pending product selection was
opened. The [startup audit](Evidence/20-Startup-Audit-20260908.md) still owns the
three pending cases. Next live observation must establish that the qualified
Ubuntu sudo implementation exposes the expected foreground/UID/parent shape;
do not weaken the proof if it refuses. Capture only safe discriminating fields.

**Verification:** the six-file focused selection covering install helper,
controller phases, sudo probe, package probes, transport and serial helper
passed **199 tests in 0.88s**, before the final serial-entry regression and
formatting refinements. Final `make check` passed **3,176 unit tests (81.17s)**,
**17 private-D-Bus tests (0.49s)**, stage traceability and common checks. No test
failure or retry occurred. New executable regressions are
`test_e2e_install_helper.py`, `test_e2e_install_password_observation.py` and
`test_e2e_installation_boundary.py` under `tests/unit`; the serial and observation
transport suites cover shared consumers. Scoped staged/unstaged whitespace and
handoff link checks pass. Existing unrelated edits are preserved. Later
handoff-only edits require fresh package artifacts, not repeated host tests.
These local checks do not qualify the live helper.

**Next bounded result:** connect the installation stages to
`check_graphical_smoke.Smoke`, `graphical_smoke/tests/smoke.pm` and the guarded
worker, preserving serial draining before observations and evidence persistence
before replies. Use the maintained qualification dispatcher for the smallest
real success and deliberate failure; add a bounded route there if required,
never mark a partial E2E-002 ready. Run cleanup-safety prerequisites in isolation,
then build fresh source-bound package inputs after final edits. Remaining Task
20 acceptance also needs private installation output/visible notice, customer
reboot/reconnect, full layout and readiness ordering, and both startup faults.

The [all-task VM clearance](Implementation-Workflow.md#vm-availability-for-all-tasks)
persists; no renewed coordination is due. No expensive VM attempt or approval
denial this slice; implementation readiness is the live-run prerequisite.
All session commands exited and results were collected. No VM lease, guest
process or screenshot export was created; no cleanup/recovery remains. No VM
power-state claim is made.

**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** local checks establish the installation protocol, but live sudo
identity, private capture and reboot continuity remain unqualified. Retain
Astra for this boundary's integration and first live proof, then reassess to
Sol high for implementation and variants over the proven path. This is a
slice-specific choice under the [model policy](Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff),
not a launcher pin.
**Remaining Task 20:** sessions **Unknown**, minutes **Unknown**. The audit bounds
three cases and proves the local installation boundary, but worker integration,
reboot/reconnect and fault controls still lack measured live timing.
