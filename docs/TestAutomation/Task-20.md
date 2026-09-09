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
     record output, and verify the product-created reboot marker. The last
     printed output must be the red kiosk reboot notice below. A hidden
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

### Terminal reboot-notice cases

These are customer-visible package-output assertions, not extra scenario
families. Capable terminals show the notice in red; redirected or `TERM=dumb`
output stays plain text.

- **Install (this task / E2E-002):** after a successful documented package
  installation, the last printed output is
  `*** REBOOT REQUIRED: reboot before using the kiosk session. ***` and is
  red.
- **Uninstall ([Task 18C](Task-18.md#task-18c) / E2E-027):** after a successful
  documented package removal, the last printed output is
  `*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***`
  and is red. This task does not run the removal journey.

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

**Current result:** [explicit-newline installation qualification passed](Evidence/20-Install-Explicit-Newline-20260908.md).
The supported custom prompt now supplies its own newline; exact argv proof
requires it. The guest recognized the complete marker/PAM suffix, independent
recipient/continuity/character-echo proof passed, and one password submission
completed authenticated installation. Independent package identity/digest and
reboot-marker checks, serial logout and GDM return passed. **One successful
attempt this slice, eleven overall; ten historical failures remain failed.**
The [intermittent executable refusal](Evidence/20-Install-Echo-Diagnostics-20260908.md)
did not recur and remains open. This is helper qualification, not E2E-002 acceptance.

**Next bounded result:** qualify one fixed deliberate installation refusal
through the existing guarded worker. Prove no password retry, no installed
package, sealed capture and cleanup. Run focused local failure checks, fresh
artifacts and isolated cleanup prerequisites before the guarded selection.
Do not rerun the successful path merely to resume a session. Red final notice,
customer reboot, installed layout/readiness and both startup faults remain;
the [startup audit](Evidence/20-Startup-Audit-20260908.md) preserves that scope.

**Read list:** [fixed helper](../../tests/integration/graphical_smoke/lib/onpc_install.pm),
[ordered boundary](../../tests/e2e/installation_boundary.py),
[worker integration](Evidence/20-Install-Worker-20260908.md), and the latest
evidence's exact test selectors/provenance. Timeout diagnostics never authorize
input. The installed serial parser now has real pipe/fragment qualification.

**Verification/cleanup:** 1597 focused tests; final helper refinement 115 passed;
526 isolated cleanup tests plus 3 subtests; fresh build passed. The initial
51 parser-fixture failures were corrected from fractional to whole-second
timeouts. Handle **2052** exited **0**, **1165.609s**. Infrastructure, collection
and cleanup passed; product `not-run`. Normal shutdown, worker/callback/display
closure, baseline restoration/verification and lease release all passed;
host/source preserved. All commands exited/results collected. GDM-return image
inspected and temporary export removed; no recovery remains. No policy/Polkit
denial. Existing edits preserved; handoff edits invalidate artifact reuse.
Actual settings: `gpt-6-astra` / `high`, Standard.

The [all-task VM clearance](Implementation-Workflow.md#vm-availability-for-all-tasks)
persists. Selection rechecked: Task 20 remains earliest ready; no bypass.
The authorized single attempt is finished; no second run was started.
**Next-session settings:** `gpt-5.6-sol` / `high`; model: lower; effort: keep.
**Reason:** prompt, exact argv/recipient and the successful worker path are
proven; the bounded refusal case builds on established contracts and local
denial tests. Standard processing; reassess Astra for a new ownership or
authentication ambiguity.
**Remaining Task 20:** sessions **Unknown**, minutes **Unknown**. The successful
helper attempt took 19.4 minutes; the remaining refusal, full reboot/readiness
and startup-fault work lacks a measured batch for a reliable completion range.

### Operator follow-up after Session 34

Completed by the [explicit-newline slice](Evidence/20-Install-Explicit-Newline-20260908.md):
one guarded attempt passed and cleanup finished. The active continuation above
owns subsequent work/settings; the instructions below retain this slice's scope.

The user reviewed Session 34 and authorized one further focused slice. Its
guest implementation audit and corrected recipient/echo proof are real progress;
prompt recognition and authenticated installation remain unqualified. Keep
`gpt-6-astra` / `high`, Standard processing, for the remaining authentication
and transport work. Launch with `--max-slices 1` and perform **at most one new
guarded VM attempt**. Finish owned collection and cleanup before stopping for
result review, including after failure; the existing VM authorization persists.

Implement the explicit newline in the supported custom prompt and update the
independent exact argv check. Preserve the qualified recipient/continuity and
character-echo proof, strict prompt recognition, private capture and refusal
gates. A diagnostic marker match must never authorize password input.

Before fresh artifacts and the sole VM attempt:

1. Exercise fragmented input through the maintained serial buffer/parser path
   locally, including command echo, delimiter and suffix split across reads,
   complete valid prompts, and incomplete or private/unknown suffix refusals.
   Tests of complete preselected strings alone do not establish serial delivery
   behavior. Reuse the existing test routes and keep this qualification focused.
2. Prepare consolidated fixed diagnostics that distinguish a marker absent from
   the observed buffer, partial marker/suffix delivery, and a complete marker
   with unsupported framing or suffix. Distinguish command echo from prompt
   output. Keep unavailable or incomplete observations explicit; absence in an
   observed buffer does not establish that sudo never emitted the prompt.
   Export only fixed categories or flags, never raw authentication bytes,
   arbitrary PAM text or secrets. Collect enough evidence during this attempt
   to identify the remaining interface gap if the new prompt still fails.
3. Validate these observations and input refusal behavior locally, build fresh
   source-bound inputs, and run the isolated cleanup-safety prerequisites.

Report the actual boundary reached: recognized prompt, password submission,
authentication outcome and any subsequent installation result separately. If
input still refuses, identify the supported cause or precise remaining evidence
gap and a different next approach. More passing tests or another undifferentiated
prompt timeout alone do not establish a breakthrough. Do not start a second VM
attempt within the slice, and do not expand a generic diagnostic framework.

### Operator diagnostic intervention — 2026-09-08

Completed in Session 34. The [operator follow-up](#operator-follow-up-after-session-34)
governs the next slice; the instructions below retain the completed intervention.

The operator authorized this intervention after reviewing slow Task 20 progress.
The preceding slice stopped normally after its ninth attempt, with collection,
baseline restoration, lease release and worker/callback closure confirmed.
The next launcher invocation is limited to **one slice** with `--max-slices 1`;
within that slice, run **at most one new guarded VM authentication attempt**.
Finish its collection and cleanup even if it exceeds the usual review time.
The ordinary backlog and VM authorization persist; the limit provides a result
review boundary before another run, not a new permission requirement.

Before another expensive attempt, reconcile these assumptions together:

1. Establish the guest's selected sudo executable and package/version using
   supported read-only evidence, then audit the corresponding implementation and
   distribution changes. Host identity and an unrelated upstream implementation
   are insufficient. Keep unknown identity explicit.
2. Explain how the configured custom prompt reaches the serial reader and its
   matcher, including supported wrappers, terminal controls and command echo.
   Prove that recognition rejects command echoes, unrelated/private PAM text and
   malformed or incomplete prompts; avoid a permissive substring fallback.
3. Review password-character protection separately from newline echo. The ninth
   attempt proved ECHO off and ECHONL on; polling does not establish a pre-prompt
   wait. Any corrected terminal predicate needs an explicit safety rationale and
   behavioral success/refusal tests. Preserve exact recipient identity, process
   continuity, authorized prompt, private capture and terminal refusal/retry
   invariants; do not merely remove a failing check to obtain a pass.

Use the smallest supported correction or a consolidated set of fixed, privacy-safe
observations that distinguishes the remaining explanations in the same boot.
If polling remains causally relevant, distinguish terminal input from a service
dependency rather than adding guessed wait symbols. Validate collectors and
parsers locally, including unknown/read-error and identity-loss cases, before
building fresh artifacts and running the isolated cleanup prerequisites.
Do not expand a generic diagnostic framework or repeat full VM preparation for
each additional diagnostic token.

End with a demonstrated cause and qualified correction, including the real
boundary reached, or a precise unresolved evidence/interface gap and a concrete
different next approach. Record rejected explanations, remaining hypotheses,
attempt identity, observed outcomes and cleanup. A larger unit-test count or one
more refusal label alone does not satisfy this intervention's result criterion.
If the live attempt still fails, finish and hand off for review before any further
VM run. Report actual status honestly under the existing schema; the one-slice
limit stops the launcher without inventing an outside-input blocker.
