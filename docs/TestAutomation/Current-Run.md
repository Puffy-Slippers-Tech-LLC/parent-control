# Current daily test run — completed follow-up

Checkpoint: 2026-09-05 America/Los_Angeles (2026-09-06 UTC). The user confirmed
this is the development and VM host.
This handoff covers the interrupted daily-run follow-up, not implementation
Task 14. No implementation backlog item was advanced or completed.

Recommended model: **`gpt-5.6-luna`**, reasoning effort **`low`**. The remaining
work is a small dependency/setup correction and a focused static check. This
task-specific recommendation uses the available model catalog and
[official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna);
it does not inherit the security implementation task's Astra/high setting.

## Follow-up outcome

The prerequisite manifest's `shellcheck=0.11.0-2` entry is now included in
`setup.sh`. `bash -n setup.sh`, `make check-shell`, and `git diff --check` pass.
Previously recorded suite evidence remains valid for its recorded inputs; no
completed suites were rerun.

<!-- Original remaining-work record retained below for historical evidence.
1. Recheck ShellCheck availability and the current checkout changes. The first
   `make check-static` failed because `shellcheck` was missing. The prerequisite
   manifest `tests/test-tools-ubuntu-26.04.txt` declares `shellcheck=0.11.0-2`,
   but `setup.sh` does not install it. Add the declared dependency to setup so
   a clean development machine can run the documented checks. Preserve all
   concurrent edits. No host package installation was performed by this run;
   follow the environment guide's explicit host-preparation boundary and obtain
   any required authorization before installing the dependency on this host.
2. Once the prerequisite is available, run `make check-shell` and
   `git diff --check`. GJS static checks already passed separately. Preserve
   the original blocked static attempt and label the new result as a follow-up.
   Address actual findings if any; increase model/effort only if their complexity
   warrants it. Do not rerun completed host/UI/VM suites merely to resume.
3. Record the focused outcome and close this daily-run handoff. Remove its
   active pointer from the daily guide once resolved. Comprehensive graphical
   E2E and `test-all` are unimplemented and cannot be reported as passing. -->

## Evidence needed to avoid duplicate work

Tested revision: `093d218b4c927908a86b5121ab55138435437716`.
Package-input source digest:
`9a5cc1bf97ef6a0b434a173395e7aa06a7f271a6f6456a4d4d3a30d0f30d9eb5`.

- Isolated cleanup prerequisites: 39 passed, 3 subtests passed.
- `make check`: 816 unit/contract and 17 private-D-Bus tests passed; syntax,
  source guards and stage traceability passed.
- Child Node/GJS runtime and GJS static/module checks passed.
- Nested-Shell: 3 passed. Remaining GTK/UI: 64 passed, including both shared
  form modes. XML: `/tmp/onpc-daily-20260906T030051/ui.xml`.
- Two fresh builds and reproducibility comparison passed. Inputs:
  `/tmp/onpc-daily-20260906T030051/first` and sibling `second`.
  Package SHA-256:
  `2e17b7abfb42d8ec3a23f0a0a89ca43ba4c7b0a8853448d83e406bec96895153`.
- Guarded installed suite: 2 installed, 2 rebooted and 213 authorization tests
  passed, zero failures/errors/skips. Evidence:
  `/tmp/onpc-system-7utjj2ct/evidence/`; `result.json` reports
  `outcome=passed`, `category=all-checks-passed`, `cleanup_phase=complete`.
  Guest XML files independently confirmed those counts. Exported broker and
  service logs contained no matches for `Traceback`, `CRITICAL` or `ERROR`.

Host test counts above are recorded from command output; do not imply a shared
aggregate evidence manifest exists. Preserve temporary evidence and verify paths
before using them. These results belong to the recorded inputs, not arbitrary
future revisions. Source/test changes require appropriate fresh validation.

## Clean checkpoint and ownership

All launched commands exited. No process or VM attempt needs resumption or
recovery. The runner restored the retained baseline and prior domain
configuration, verified host product/PAM preservation, and completed cleanup.
An independent `virsh --connect qemu:///system domstate ubuntu26.04` returned
`shut off`. Do not prepare another baseline or restart the VM for the static
follow-up.

No product/test code was changed during the run. Concurrent edits adding model
confirmation instructions to `docs/Test-Automation.md` and
`docs/TestAutomation/Test-Automation.md` were present at completion and must be
preserved. This checkpoint adds only this handoff and its daily-guide link.
