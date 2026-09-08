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
- Model rationale: retain Sol for the first complete graphical package journey;
  the guarded worker and install assertions are already implemented, while
  startup failure diagnosis still spans several services.
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

**Ready and next in checklist order.** [Task 19B is accepted](Evidence/19B-Acceptance-20260908.md)
after three consecutive reviewed public qualifications. No earlier entry is
bypassed; preserve [Task 15A's later saved work](Task-15.md#task-15a-continuation--2026-09-08).
No Task 20 implementation or acceptance is claimed by this scheduling handoff.

**Next bounded result:** audit E2E-002 and assigned E2E-028 declarations against
the startup lifecycle contract and existing worker/asset/observation capabilities.
Resolve E2E-002's requirement gap and implement the smallest missing capability
needed for real terminal installation and actual reboot. Keep unrelated fixture
setup in supported provisioning helpers and startup faults separately declared.
Use focused host checks before the first ready guarded journey; pending
declarations must retain their public refusal until implemented.

The operator's [all-task VM clearance](Implementation-Workflow.md#vm-availability-for-all-tasks)
remains effective. No renewed coordination confirmation is due. The previous
session's commands exited, terminal cleanup passed, the VM was freshly confirmed
off and all three screenshot exports were removed; no operation needs recovery.
Build fresh package-bearing inputs after handoff edits for the next live attempt.

**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep,
pinned by the slice launcher. **Reason:** the qualified harness now supports the
first product installation/reboot/readiness boundary and its separate fault cases.
**Remaining Task 20:** sessions **Unknown**, minutes **Unknown**; its capability
and variant audit has not yet established implementation scope or live timing.
