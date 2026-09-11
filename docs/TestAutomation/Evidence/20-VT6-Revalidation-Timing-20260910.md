# Task 20 — baseline revalidation outlasts the login window

## Result and retained evidence

Authentication attempt 3 again refused `vt6-password-ready` before password
authorization. This run supplies the missing timing discriminator: the selected
unit was running `login` before revalidation and `agetty` afterward. Guest
util-linux is 2.41.3; `/etc/login.defs` configures `LOGIN_TIMEOUT` to 60 seconds.
The intervening baseline recheck took **69.027 seconds**, with source capture
taking **0.091 seconds** and no staged assets. The preceding getty-stage
baseline checks took 69.862 and 69.169 seconds.

The observed wait exceeds the configured login lifetime. Upstream
[login initialization](https://raw.githubusercontent.com/util-linux/util-linux/v2.41/login-utils/login.c)
starts an alarm using this setting, documented in the
[login manual](https://raw.githubusercontent.com/util-linux/util-linux/v2.41/login-utils/login.1.adoc).
Prompt expiry during baseline verification is therefore the supported
explanation; the actual signal/exit was not traced. The early `login` observation
rules out an exclusively wrong initial executable transition. It does not prove
authenticated session continuity or command readiness.

- Route: `tools/run-tests integration check_graphical_vt6_authentication`, exit 1.
- Result: `/tmp/onpc-graphical-smoke-up77al3p/result.json`; receipts: `steps.json`
  in that directory. Only GDM and `vt6-login-ready` completed.
- Durable evidence: `/tmp/onpc-e2e-evidence-z7pwgq80/event-000018.json` (early
  recipient, 611.904 seconds), `event-000019.json` (component times, 681.023),
  `event-000020.json` (late recipient, 681.549), and `event-000023.json`
  (after-cleanup preservation). These are qualification-relative times.
- Worker: `/tmp/onpc-e2e-evidence-y3oiiadh/worker-result.json`.
- Source: `596d97e20d0add3347f1747243100049f870bd77274494ea82cf7d9055d8936e`.
  Baseline: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
  Worker distribution: `89ec8a538814c67e0245def05f5f3feeaf79264350a2ad92d15a4f30e142fb11`.
  The result retains the complete runtime input map.

**Advisory Boolean invalidation:** both retained `matches_pinned_recipient`
values are invalid. Review caught comparison of a digest string with the
observer's `(boot, recipient)` tuple. The original diagnostic double used a
string and missed this interface defect. After cleanup, the parser was corrected
to compare with the pinned recipient digest. New true/false regressions acquire
the pin through real ordered observer reads. This correction is locally tested;
no live continuity match is claimed. The executable/version/timeout/timing
observations are independent of that comparison and remain usable. Raw evidence
was preserved unchanged; no raw authentication capture or account data was read.

## Reused implementation and checks

`VerifiedInputs.recheck` now retains fixed source/assets/baseline durations,
including a failed component. It still performs every full check and latches
refusals. `VT6_LOGIN_DIAGNOSTIC` and the existing read-only transport report only
bounded configuration, executable categories and an advisory identity comparison.
`Authentication` brackets the expensive check with those reads and the existing
`Qualification.progress` persists them as diagnostic events, never proof steps.
No timeout, credential, capture, ownership or provenance guard was relaxed.
The [owning contracts](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) carry reuse
and qualification limits.

- Initial focused run: 243 passed, one failed because the new checkpoint event
  name contained a digit, which the existing recorder forbids. Correcting the
  name to `terminal-diagnostic` yielded **244 passed**.
- Before the VM run: `make check` passed 7,198 unit/contracts and 58 private-D-Bus
  cases plus common checks. Isolated cleanup prerequisites and the dispatcher's
  mandatory repeat each passed **599 tests and 3 subtests**.
- After the advisory comparison correction: **135 focused tests passed**;
  final `make check` passed **7,200 unit/contracts and 58 private-D-Bus cases**
  plus common checks. Canonical cases are in `test_e2e_vt6_diagnostic.py`,
  `test_e2e_vt6_controller.py`, `test_e2e_provenance.py`, and
  `test_graphical_smoke_cleanup_safety.py` under `tests/unit/`.

The live outcome remains infrastructure failure `e2e:worker-execution-failed`;
product and collection remain `not-run`. Worker stopped, callback closed,
baseline restoration passed, lease phase is `complete`, and final source/host
preservation passed. Normal scenario shutdown was not reached. All commands
exited and results were collected; no exports or owned recovery obligations
remain. There was no approval/Polkit denial. Changes after the run are the
advisory comparison/regression correction and documentation; they do not acquire
live qualification from the earlier input identity.

Documentation checks passed 261 local links and scoped `git diff --check`;
untracked-file checks reported no whitespace findings. Two documentation patch
attempts refused duplicate-path operations and an empty hunk before mutation;
corrected native updates applied. Focused reads corrected a guessed module path
and an empty range. These did not change the test outcomes or retained evidence.

## Milestone review and next action

The 15–30 minute slice review led to completing the already-started guarded
attempt, restoration and final correction checks before handoff; no second VM
experiment was started. Authentication history is now three failures: source
drift first, then two password-readiness failures. Prompt history remains one
failure/one pass; installation history remains three historical passes/eighteen
failures. Task 20 and both E2E-028 startup faults remain unaccepted.

The existing authentication chain is implemented. Its missing live proof now
has an evidenced scheduling prerequisite: full baseline checks exceed the stock
login timeout. Next implement a fixed, finite fixture login window through the
supported `LOGIN_TIMEOUT` setting during existing off-VM `mounted_guest`
preparation, with corresponding bounded VT6 worker budget. A 600-second fixture
window and the existing supported 960-second worker limit cover the measured
chain; verify that choice with the integrated attempt. Preserve the accepted
baseline and host configuration through outer restoration, all full rechecks,
one-use recipient/capture proofs and no-retry input. Cover unsafe/partial
provisioning refusal and cleanup locally, then run the guarded authentication
route. Do not repeat an unchanged diagnostic attempt or introduce a digest cache.

All-task VM clearance persists. Task 20 remains earliest ready, no bypass;
15A's later work is preserved. Actual settings: `gpt-6-astra` / `high`, Standard.
Next: `gpt-6-astra` / `high`; model keep, effort keep. The latency is now isolated,
but fitting supported fixture/worker timeouts around the authenticated input and
offline ownership contracts still requires a safety-sensitive correction and
live qualification.
