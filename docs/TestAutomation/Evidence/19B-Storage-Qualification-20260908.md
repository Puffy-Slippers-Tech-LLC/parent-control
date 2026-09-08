# Task 19B — guarded storage repair and qualification 1

**The public screenshot/storage boundary is repaired and E2E-001/gdm-observation
has one complete, visually reviewed qualification of the required three.**
This is `runner-smoke`, not customer coverage or Task 19B acceptance.

## Change and focused verification

`tests/e2e/execution.py:attempt` now allocates private raw attempts directly in
`/tmp/onpc-graphical-smoke-<run>`, independent of `TMPDIR`. The existing installed
PNG export helper accepted the new captures without a helper, policy or permission
change. Activation is next invocation (`none`); no product migration is involved.
The public controller contract is documented in `tests/e2e/README.md`.

`test_retained_attempt_screens_support_guarded_export` executes the controller
with real temporary allocation and the maintained export implementation, both
after success and a preparation failure. It verifies private mode/ownership,
unchanged source bytes, export compatibility under another temp default, closed
collectors and the applicable owned cleanup. Existing export regressions now
explicitly refuse the old attempt prefix as well.

Focused selection: `tools/run-unit-tests tests/unit/test_e2e_execution_cleanup_safety.py tests/unit/test_screenshot_export_safety.py tests/unit/test_screenshot_cleanup_safety.py -q`.
The first run had **2 failed, 88 passed** because the new synthetic PNG inherited
group-writable permissions. The exporter correctly refused it. Setting the
fixture to mode 0600 fixed the test; the real worker already uses umask 0077.
The corrected run passed **90 tests**. No exporter guard was weakened.

`make check`, handle **81137**, exit 0: **3,060 unit/contracts in 70.02 s**,
**17 components in 0.32 s**, syntax and stage traceability passed. Scoped
whitespace and local-link checks passed after the final documentation edits.

## Public qualification and reusable evidence

Build: `tools/run-tests artifacts build`, handle **69792**, exit 0,
output `/tmp/onpc-test-artifacts-kmoljoy8`.
Run: `tools/run-tests e2e --artifacts /tmp/onpc-test-artifacts-kmoljoy8 --scenario E2E-001`,
handle **16984**, exit 0. Its dispatcher passed **521 isolated safety tests and
three subtests in 5.02 s** before acquiring the VM. Checkout inputs remained
unchanged through terminal collection and cleanup.

- Invocation: `/tmp/onpc-e2e-evidence-shzmj2ea`; its post-close terminal output
  reported `passed`, all expected cases executed and no first failure.
- Case: `/tmp/onpc-e2e-evidence-emag1huy`, run
  `scenario-52e07ff55edc4327ab9601986687166e`.
- Case terminal: `invocation-000003.json`; final scenario: `event-000029.json`.
- Raw worker evidence: `/tmp/onpc-graphical-smoke-8_bgk6m8`.
- Worker result: `/tmp/onpc-e2e-evidence-zgcuroga/worker-result.json`.

| Input | SHA-256 |
| --- | --- |
| Source | `09034f01bee9c75aaed948a00a7c7b0b9e3b6f3eac4b150690451c3cd5952af2` |
| Inventory | `15fd719181f41bfb6d12ac5f30f9a02fbd652626037856e02827f8361170fe39` |
| Package | `0b1328cd53aecf4c24f7e0aa2ce6129467105cb7196c0032b995d9bc3592e7ac` |
| Assets | `c5ee34c58afdc2ff41a7231d61c144cd43d5233aec00debd4e6ad58e75d631a4` |
| Baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Worker distribution | `970ba820f1a4e85ba8ea810d0e06ce11a88bcd306fe4424e15971330f06151b4` |

All nine ordered observations passed with one boot identity. Structured
`serial-command.evidence` confirms an active local serial session, actual command
marker and no unexpected user session. `matched-screens.evidence` reconciles
six positive 100% matches. Raw `testresults/result-smoke.json` records the
deliberate account-list mismatch on the empty password prompt at zero similarity;
the final GDM match follows the serial-logout detail.

Direct visual inspection of `smoke-1.png`, `smoke-6.png` and `smoke-16.png`
confirmed the initial GDM list, the selected `[Parent user]`'s empty focused
password prompt and the returned list. All are 1024×768. Initial, select-ready,
click, dismissed and returned screens share digest
`8d60f3c7dfafa5cd4f99c2a25344c1dc483891d6fda3d5ceb2210845cbff04bc`;
prompt digest is `d30ba993e2f3f4968fd38fac4f6977f6236d5ea94d4f1bf1d51529b408609428`.
Equal list images are expected because the serial journey leaves GDM unchanged.
Raw captures contain account labels and remain private, not published redacted
artifacts. Reviewed structured artifacts passed registered-secret exclusion.
`NOVIDEO=1` remains the established secret-safe contract; there is no video to
review (the retained `video_time.vtt` is timing metadata). Raw authentication
logs were not exported as reviewed evidence.

Each PNG was exported through `pkexec /usr/local/libexec/onpc-export-screenshot`
to `/tmp/onpc-19b-q1-gdm.png`, `/tmp/onpc-19b-q1-prompt.png` and
`/tmp/onpc-19b-q1-return.png`. All three exports succeeded with private mode and
caller ownership, were inspected, then removed by `tools/cleanup-screenshots`
(confirmed three removals). No denial, alternative copy route or helper refresh
occurred.

## Cleanup, qualification count and next action

Worker exit 0, callback closure, owned-process shutdown, baseline restoration,
source/host preservation and collection all passed; lease phase `complete`.
Fresh `tools/test-vm status` confirmed off (`state=5`, `id=-1`). All command
handles exited, all review exports were removed, and no owned operation or
recovery is pending. Private raw evidence is retained intentionally.

Measured stage totals: preparation **370.615 s**, test **581.506 s**, cleanup
**66.228 s**; worker **37.524 s**. The invocation took approximately **23 minutes**
including finalization; stage totals omit some held-lease validation time.
This slice performed one expensive VM attempt. The preceding
[runtime pass](19B-Public-Runtime-20260908.md) remains valid runtime evidence but
cannot count as a fully reviewed qualification because its captures remain
outside the approved export scope. Historical failed attempts remain failed.

Next, build fresh artifacts after handoff edits and complete qualifications 2
and 3 through the same public selection, with direct review and terminal cleanup
for each. Preserve this first qualification unless a relevant implementation,
needle, scenario, tool or baseline change invalidates it; document input
differences. Documentation-only handoffs require new provenance but do not
invalidate the already reviewed behavior. Then finish the 19B acceptance audit.
Do not rerun accepted helper qualifications or use the old capture path.

19B remains the earliest ready unchecked task; no earlier task was bypassed.
Task 20 follows its acceptance, then 15A's saved work. The operator's
[all-task VM clearance](../Implementation-Workflow.md#vm-availability-for-all-tasks)
remains effective; no renewed coordination confirmation is due.
Settings: **`gpt-6-astra` / `high`**, pinned by the slice launcher.
Remaining 19B estimate: **2–3 sessions / 50–90 minutes**, assuming two further
approximately 23-minute invocations, build/review/cleanup and an acceptance
audit, with no new failure or relevant code change.
