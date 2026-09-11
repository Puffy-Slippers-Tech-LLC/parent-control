# Task 20 — joined authentication review and attempt 8

## Result and qualification limit

The joined review found and locally corrected two additional defects downstream
of the already corrected screenshot comparison. Guarded authentication attempt
8 then refused source drift during credential preparation, before worker startup
or any VT6 input. No authenticated shell, command completion or full Task 20
acceptance is claimed. The one-slice Astra/xhigh intervention was used for this
review and attempt; it does not pin later settings.

## Reproduced defects and maintained corrections

- `vt6_command.READ_MARKER` used whole-stat equality, repeating the screenshot
  reader's access-time defect. A fresh `/tmp` marker read after a 1.05-second
  delay reproduced the false refusal. Its guest-local `marker_identity` now
  uses the stable fields of `provenance.identity` plus UID/GID. Both descriptor
  and path must retain identity, mode, links, size, ownership and nanosecond
  mtime/ctime; only read-driven atime is excluded. Tests retain real Bash marker
  generation, collisions/consumed/partial input, exact nonce/PID and late lineage
  refusal. Eighteen new descriptor/path field mutations include one-nanosecond
  changes that the old tuple comparison could miss.
- `VT6_SHELL_LINEAGE` called `tcgetpgrp` on VT6 from its SSH observer. The
  [Linux API](https://man7.org/linux/man-pages/man3/tcgetpgrp.3.html) requires the
  caller's controlling terminal. A real noncontrolling PTY reproduced `ENOTTY`
  through the original probe; the old doubles had incorrectly supplied a
  successful process group. The correction uses the existing repeated pinned
  shell's [kernel process fields](https://www.kernel.org/doc/html/latest/filesystems/proc.html),
  including terminal, session, pgrp and tpgid. Those checks bracket the terminal
  open and retain late foreground replacement refusal. Device validation,
  descriptor closure, boot/start-time/credentials and direct-child checks remain;
  no observer terminal ownership or session is changed.

The review also checked worker receipt consumers, capture sealing, current-worker
and source checks, recipient/shell continuity, fixed command grammar and cumulative
timeouts. The existing 600-second fixture login window, 420-second per-exchange
wait and 960-second worker limit are unchanged. Their complete live adequacy is
still unproved. No new gate, retry, capture route or permission was introduced.
The [owning contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) carry reuse.

## Verification

- `test_marker_first_read_after_provenance_delay_preserves_identity` failed
  against the original marker comparison, then passed after correction.
- The original shell probe failed the realistic noncontrolling-terminal case
  with errno 25. Final regressions are
  `test_linux_foreground_ioctl_requires_the_observers_controlling_terminal` and
  `test_vt6_shell_follows_only_pinned_login_child`, whose ioctl double now refuses
  and whose matrix includes late shell foreground replacement.
- First focused worker/controller/command/shell/recipient selection: **361 passed**.
  Final affected selection adds observation transport and serial observation:
  **1,861 passed**, using `tools/run-unit-tests` with the seven corresponding
  `tests/unit/test_e2e_*.py` files and `-q --tb=short`.
- Common checks were run after the marker correction and again after the final
  shell correction. Both exited **2**, with **7,326** and **7,325** unit/contracts
  passing respectively and one existing failure:
  `test_helpers_do_not_import_collected_case_modules[tests/ui/test_control_overflow.py]`.
  That UI module imports `request_display_scale` from the collected
  `tests.ui.test_request_layout` module. The shared fixture belongs in support
  or the UI conftest. Separate UI work was preserved. The common run stops at
  this failure; later component/common stages did not execute and no complete
  `make check` pass is claimed. Stage traceability passed.
- Isolated cleanup safety and the integration dispatcher's repeat each passed
  **685 tests and 3 subtests** before attempt 8.

## Retained attempt and cleanup

- Route: `tools/run-tests integration check_graphical_vt6_authentication`.
  Handle **15518**, exit **1**, duration **312.369 seconds**.
- Result: `/tmp/onpc-graphical-smoke-npa4zgk8/result.json`.
- Qualification: `/tmp/onpc-e2e-evidence-g7pb22df/event-000006.json` retains
  `finalization-rejected`; no authentication step completed.
- Source SHA-256: `4df2a91ef45a88143fd1c800475780777a32d2a5e6afe7de2acc39c884c299b6`.
- Baseline SHA-256: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
- Infrastructure category `credential:provisioning-failed`; final refusal
  `provenance:source-changed`. Product/collection stayed `not-run`.
- Baseline restoration and host preservation passed, lease phase `complete`.
  Source preservation failed. No worker, callback, display or screenshot export
  was started by this attempt. Local PTYs and temporary marker/capture directories
  closed through their test cleanup. All listed commands exited; no owned
  recovery obligation or approval/Polkit denial remains.

No checkout edit was made by this session from live launch through cleanup.
Compared with the pre-attempt state, new changes appeared in
`docs/SystemDesign/Frontends.md`, `parent/oh_no_parent_control_parent/main.py`,
`tests/ui/parent_component_preview.py`, `tests/ui/test_control_overflow.py`, and
the new `tests/ui/parent_allowance_probe.py`. Their observed modification times
span **05:34:34–05:38:51 UTC on 2026-09-11**, overlapping this attempt. This is
current evidence of another writer, not reinstatement of the historical VM hold.
The full differing snapshot was not retained, so the exact first offending path
or metadata field is not asserted. The maintained provenance guard correctly
keeps the attempt failed; do not exclude paths or weaken it to retry.

Authentication history is now **eight failed attempts**. Attempts 6/7 retain
the furthest live proof: finite login preparation, password readiness, and exact
prompt pixels before the old post-read capture refusal. The two corrections
above and the stable screenshot comparison still require fresh live qualification
with unchanged checkout inputs. All-task VM authorization remains valid.

Final documentation checks passed: **307 local links across six documents**,
no missing targets, and scoped `git diff --check HEAD`. Continuation has exactly
one supported settings line. The current-writer question remained unanswered
at handoff; independent Task 15A acknowledgement work is next, with a mandatory
recheck of Task 20's return condition. Next settings: `gpt-6-astra` / `high`,
Standard, for unresolved active-policy acknowledgement and rollback semantics.
