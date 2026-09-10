# Task 20 — VT6 prompt collection qualification

## Result and scope

The corrected credential-free `check_graphical_vt6_prompt` route passed its
first corrected guarded attempt. Both genuine VNC terminal images were directly
reviewed after finalization. The selected agetty gate, login password recipient,
disabled echo, active VT6 and unchanged boot checks passed at their collection
checkpoints. No password was provisioned, read or submitted. This qualifies
prompt collection on the retained baseline, not authenticated input, installation
or E2E-002. Task 20 and its two E2E-028 startup faults remain unaccepted.

Reuse `onpc_vt6::inspect_prompt`, `Smoke.VT6_PROMPT_STAGES`, `VT6_GETTY` and
`VT6_PASSWORD` through the
[owning VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal).
No new implementation or runtime inputs were needed in this slice. The
[original failure and correction](20-VT6-Prompt-Readiness-20260909.md) remain
retained: the old canonical/echo predicate refused; the supported-mode correction
now passes live. Individual terminal flag values were not exported, so this
does not identify which allowed getty mode the guest used. The independent
password probe did establish canonical input with echo disabled.

## Verification and retained evidence

- Isolated prerequisites: `tools/run-unit-tests
  'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py
  -q --tb=short`: **585 passed, 3 subtests**. The dispatcher's mandatory repeat
  passed the same selection before VM mutation.
- Sole VM command: `tools/run-tests integration check_graphical_vt6_prompt`:
  **exit 0**. Infrastructure, collection and cleanup passed; product `not-run`.
- Result: `/tmp/onpc-graphical-smoke-40maopls/result.json`.
  Source digest: `7ed147617249070018395bbf88ca5af8280aa7ce7c9accc563c35e773a04b068`.
  Baseline digest: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
  Exact selected inputs remain in that run's `input/selected-inputs.json`.
- Controller evidence: `/tmp/onpc-e2e-evidence-3g4c8tc1`.
  Worker result: `/tmp/onpc-e2e-evidence-1uhqp_ww/worker-result.json`;
  backend exit 0, no failures, normal shutdown verified, worker stopped and
  callback closed.
- `vt6-login-screen.request.json` identifies `testresults/smoke-15.png`:
  SHA-256 `2aacbd8e89bb205ce63a7ab7f43d305b5f43e37576a7bb1b70120b4e4811c3bc`.
  `vt6-prompt-screen.request.json` identifies `testresults/smoke-17.png`:
  SHA-256 `63f310dff9a066270e8888af30ade4c65fc5e02af2604dc3bba53defff243f47`.
  Both are native **1024×768**, unlike the earlier 1280×800 maintenance image.
  Both checkpoints passed their recipient and unchanged-boot checks.
- Runtime inputs were unchanged from the preceding focused correction result
  (**1,415 passed**); those checks were reused, not rerun. This slice adds live
  qualification and documentation only. No full common/package acceptance run.
- Documentation validation: 191 local links across the five updated documents,
  none missing; scoped `git diff --check` passed. Continuation contains exactly
  one supported settings line and still selects the earliest unchecked task.

Prompt-route history: **2 attempts, 1 original failure and 1 corrected pass**.
Installation history remains **21 attempts, 3 historical passes and 18 failures**.
This result does not resolve the separate intermittent recipient or historical
source-provenance failures; no diagnostic refusal was triggered here.

## Direct image review and needle contract

The reviewed login image shows the kernel terminal banner identifying tty6,
an empty `login:` prompt and cursor, with otherwise black screen. The challenge
image retains that banner and echoes only the selected parent fixture on the
login line, followed immediately by `Password:` on the next line. No failure,
shell prompt, submitted password or additional output is visible. Raw account
and host labels remain in private evidence; this report uses role labels.

The next maintained needle must use these genuine native-resolution pixels:

1. Match the complete selected fixture echo and the adjacent `Password:` line
   together. A generic password label or banner alone cannot select an account.
2. Preserve the blank challenge area and exclude only the blinking cursor from
   matching. Do not resize/replay the screen or use the maintenance screenshot.
   Exact match rectangles and wrong-account/stale-screen/missing-prompt cases
   still need executable matcher validation before this needle authorizes input.
3. Bind the match to `sut`, active VT6, unchanged boot, selected login recipient
   and canonical/no-echo proof. A blank no-echo field does not reveal whether
   invisible characters have already been typed: an empty challenge additionally
   requires the one-shot input state and no preceding password submission.
4. Seal explicit captures before secret access/input, retain private automatic
   captures and `NOVIDEO=1`, and latch any failure without retry. A screenshot
   alone is never permission to type a password.

No needle asset or password-enabled route was added in this slice. Sudo prompts
and final red-notice pixels remain uncollected. The owning contract carries
these qualification limits for downstream reuse.

## Cleanup and next action

The original command exited and all results were collected before documentation
edits. The outer owner restored and verified the baseline, reached lease phase
`complete`, and passed source/host preservation. VM off; worker stopped; callback
closed; no lease or recovery remains. The two caller-owned review exports,
`/tmp/onpc-vt6-login-20260910.png` and `/tmp/onpc-vt6-prompt-20260910.png`, were
removed through `tools/cleanup-screenshots`; private source images are retained.
No approval or Polkit denial occurred. No permissions or setup changed.
**All-task VM clearance persists.** Existing unrelated edits are preserved.

Next: implement the bounded authenticated VT6 login/session and controller input
gates using this reviewed image contract and the existing credential/private
capture helpers. Validate exact image matching and executable refusal/no-retry
behavior locally, then qualify the smallest guarded authenticated flow with
isolated safety prerequisites. Do not repeat prompt-only collection or maintenance
without new invalidating evidence. Sudo/notice and full install/reboot/startup
remain subsequent Task 20 work. Task 20 is still earliest ready; no bypass.

Actual settings: `gpt-6-astra` / `high`, Standard. Next settings:
`gpt-6-astra` / `high`, Standard: prompt/recipient collection is now live-qualified,
but secret-input authorization, session continuity and capture sealing across
the new VNC path remain unresolved correctness boundaries.
