# Task 20 — finite login window; preparation refusal

## Result and evidence

Authentication attempt 4 failed during offline login-window preparation, before
worker startup, VM test boot or authentication input. Fresh fixture credentials
were verified. The new helper returned `credential:login-window-failed` after
1.934 seconds; its initial generic exception wrapper discarded the precise
predicate/API failure. The cause and whether a partial write occurred are
unknown. This attempt does not qualify the 600-second setting, the 960-second
worker budget, advisory recipient comparison or authenticated shell.

- Route: `tools/run-tests integration check_graphical_vt6_authentication`, exit 1.
- Result: `/tmp/onpc-graphical-smoke-ysi4jxc4/result.json`.
- Checkpoints: `/tmp/onpc-e2e-evidence-vwlzdajw/event-000005.json` starts login
  preparation at 377.579 seconds; `event-000006.json` records the refusal at
  379.513; `event-000007.json` records final preservation after cleanup.
- Source: `cf4dcb39d8450a4ca75b490156071b2a4945a87293b243ddd69573b5633b0158`.
  Baseline: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
  The result retains the full runtime input map; no package or worker was used.
- Infrastructure failed with the retained preparation category. Product and
  collection are `not-run`; steps are empty. Baseline restoration, lease phase
  `complete`, final source/host preservation and cleanup passed. The outer log's
  generic caught-failure message did not replace the specific result category.

All commands exited and the terminal result was collected. No worker/callback
was started, no screenshot was exported, no owned recovery obligation remains,
and no approval or Polkit denial occurred. Original failed artifacts remain
unchanged. Post-run edits add bounded diagnostics and tests; they have local
verification only.

## Reused implementation and correction

`fixture_credentials.provision_vt6_login_window` reuses the held-lease/offline
`system_runner.mounted_guest` path. It changes only the attempt disk's existing
`/etc/login.defs` setting from 60 to 600, permits an already prepared 600 value,
preserves unrelated bytes and file identity/ownership/mode, and verifies readback.
Missing, duplicate, malformed or unexpected settings and unsafe metadata refuse.
The outer lease restores the active disk even after partial preparation; the
accepted baseline and host configuration are never write targets.

This is a supported finite fixture configuration: the
[util-linux login manual](https://raw.githubusercontent.com/util-linux/util-linux/v2.41/login-utils/login.1.adoc)
defines `LOGIN_TIMEOUT` in `/etc/login.defs`, with a 60-second default.
The preceding [timing evidence](20-VT6-Revalidation-Timing-20260910.md) establishes
that full baseline revalidation exceeds that default. `run_backend` now selects
the existing 960-second worker limit for VT6 auth; other modes retain their
budgets. Full provenance, input, capture, identity and cleanup guards remain.
No product installation, system activation or saved-data contract changes.

The failed attempt exposed inadequate error retention in the new helper.
After cleanup, it was corrected to retain a finite allowlist of fixed predicate
codes, and fixed operation boundaries for other exceptions: lease, mount,
metadata, read, configuration, before-write, write, readback, close and
after-close. Raw exception text and guest configuration never enter reports.
This makes the next attempt discriminating; it does not explain the old failure.
The [owning VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) carry these
qualification limits and regression links.

## Verification and milestone review

- `tests/unit/test_graphical_smoke_cleanup_safety.py`: real `mounted_guest`
  control flow with a guestfs double verifies metadata/content preservation,
  idempotence, unsafe/partial preparation refusal, sync/close/interruption,
  worker gating, outer restoration/release and unchanged other-mode budgets.
  Post-run cases additionally verify exact refusal categories and private API
  error redaction.
- Initial focused run: 135 passed, four budget-test failures from a
  nonserializable `Smoke.steps` double. Correcting the double yielded 139 passes.
  Final focused selection, including `test_e2e_vt6_controller.py` and
  `test_e2e_vt6_diagnostic.py`: **142 passed**.
- Pre-run `make check`: **7,230 unit/contracts and 58 private-D-Bus cases**.
  Isolated safety and the dispatch repeat each passed **629 tests and 3 subtests**.
  Final `make check` after diagnostic correction: **7,233 unit/contracts and
  58 private-D-Bus cases**, plus common checks. These local passes do not qualify
  the failed live boundary.
- Documentation: local links and scoped whitespace checks passed; prior staged
  work was preserved. No authoritative checklist entry was completed.

One live attempt was made. The slice review ended the experiment after its
guarded cleanup and diagnostic correction; no unchanged rerun or second VM
attempt was started. The milestone is still one authenticated command-ready
shell. Its new first failing boundary is fixture preparation, whose exact cause
was lost by the initial wrapper. The existing controller cannot supply that
missing predicate, but the corrected helper now preserves it. Next run the
guarded integrated route after isolated safety prerequisites, diagnose/correct
any precise preparation refusal, and qualify the login/command chain with
unchanged inputs through cleanup. Do not change guards or guess a configuration
relaxation. Sudo/notice pixels, complete install/reboot/startup and both E2E-028
faults remain after authentication. Authentication history is four failures;
prompt and installation histories are unchanged. Task 20 remains unaccepted.

Task 20 is still earliest ready; no bypass. All-task VM clearance persists and
15A's later work stays preserved. No outside intervention is identified.
Actual settings: `gpt-6-astra` / `high`, Standard. Next: `gpt-6-astra` / `high`;
model keep, effort keep. The new offline preparation refusal has an unknown
cause, and corrected diagnostics still need live qualification before the
authentication ownership chain can be accepted.
