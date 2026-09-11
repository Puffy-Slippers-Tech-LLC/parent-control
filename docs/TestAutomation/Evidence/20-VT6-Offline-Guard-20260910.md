# Task 20 — offline guard corrected; password capture remains refused

## Verified advancement

`fixture_credentials.provision_vt6_login_window` now uses the established full
lease checks around `system_runner.mounted_guest`, without reentering the disk
inventory while its libguestfs appliance holds the disk. File identity and
metadata are still checked immediately before writing and during readback.
No shared guard, disk-locking option, provenance check or input gate changed.

Attempt 5 narrowed the preparation failure to
`credential:login-window-before-write-failed`. The helper called `Lease.guard`
inside the writable mount; `Capture.inventory` calls locking `qemu-img info`
because the libvirt domain is off. That conflicts with the appliance's disk
writer. This explanation follows the actual call path and
[QEMU's image-locking contract](https://www.qemu.org/docs/master/system/images#disk-image-file-locking);
raw command stderr was not retained, so it is not a recovered error transcript.
The occupied-disk regression reproduces the incompatible call placement.
Attempt 6, with that call removed, completed preparation and readback, then
observed effective `LOGIN_TIMEOUT=600` in the booted guest.

Attempt 6 passed both durable `vt6-login-ready` and `vt6-password-ready`
authorizations. Its early/late diagnostics observed `login`, timeout 600 and
`matches_pinned_recipient=true` on both sides of baseline revalidation
(59.822 seconds; source capture 0.105 seconds). This newly qualifies the matching
advisory branch and login-window preparation. Attempt 3's old advisory values
remain invalid; the replacement/false branch remains locally tested only.
The 960-second worker configuration was used but complete budget adequacy is
unproven because this attempt failed before shell/command completion.

## Retained attempts and failure boundary

Both used `tools/run-tests integration check_graphical_vt6_authentication`,
exited 1 and remain failed. No package-bearing acceptance attempt was run.

| Attempt | Result and checkpoints | Source digest |
| --- | --- | --- |
| 5 | `/tmp/onpc-graphical-smoke-co9_u418/result.json`; `/tmp/onpc-e2e-evidence-caxmsh26` | `e42e5d7eec51140b2b524eea4bdb4cee0dd612597c175782ae3aa1630e177c20` |
| 6 | `/tmp/onpc-graphical-smoke-61hh5yj3/result.json`; `/tmp/onpc-e2e-evidence-ttjpj_gm` | `89b9d8de70d31b3d301b7515cfaa94b0c2ade7046a06bb6ab8ad4953c36c4d8e` |

Baseline digest for both:
`cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
Results retain complete runtime maps. Attempt 5 had no worker or input.
Attempt 6's worker result is
`/tmp/onpc-e2e-evidence-o76f_gpy/worker-result.json`.
Its first failure is `e2e:worker-execution-failed` at `vt6-password-screen`,
after that stage's input recheck and boot read, before a password-screen reply.
The controller's exact subpredicate was lost by the generic worker failure
wrapper. No password-input authorization, credential submission, shell lineage
or command completion is established; worker normal shutdown is false.

The safe request names `testresults/smoke-17.png`. Direct inspection of that
pre-password capture shows the expected empty VT6 password prompt. The worker
log records a positive needle match at similarity 1.00. More decisively, its
approved export has the **same complete PNG SHA-256 as the pinned reference**:
`63f310dff9a066270e8888af30ade4c65fc5e02af2604dc3bba53defff243f47`.
A pixel-content mismatch is therefore excluded for those retained bytes.
There is no `vt6-password-screen.reply.json`; no password-recheck success was
reported. Review `Authentication._pixels` freshness/path/inode/link/timestamp
checks and the real os-autoinst capture creation/deduplication semantics before
another live attempt. Its whole-`stat_result` equality also includes access time;
an access-time change caused by reading is a hypothesis, not a proven cause.
Preserve the exact fixed refusal safely if local reproduction cannot distinguish
the remaining predicates. Do not relax capture, recipient or one-use guards or
rerun this unchanged. Reuse retained captures; no new prompt collection is needed.

## Verification, cleanup and next result

- Focused controller/diagnostic/cleanup selection: **144 passed**.
  `test_login_window_full_guard_runs_outside_appliance_disk_lock` exercises the
  real mounted-guest context with a lock-aware appliance double; existing refusal
  coverage now includes pre-write metadata replacement and post-close guard loss.
- Final `make check`: **7,235 unit/contracts and 58 private-D-Bus tests passed**,
  plus common checks. No local test failure occurred in this slice.
- Isolated safety and dispatch repeat before attempt 5: each **632 tests and
  3 subtests passed**; before attempt 6: each **634 tests and 3 subtests passed**.
- Both runs passed restored-baseline verification, lease completion and final
  source/host preservation. Attempt 6 additionally confirms worker stopped,
  callback closed and display closed. Product/collection remain `not-run`.
  All commands exited. The one temporary PNG export was removed with the
  screenshot cleanup helper; retained private originals remain untouched.
  No approval/Polkit denial or owned recovery obligation remains.

The two planned expensive attempts are complete; the slice exceeded its review
budget to finish the second attempt's full checks, restoration and collection.
The live command-ready shell milestone remains unfinished. Next locally resolve
the capture refusal using the retained byte-identical PNG and real capture API,
then qualify the correction through the same guarded authentication route after
isolated safety. Sudo/notice pixels, complete install/reboot/startup and both
E2E-028 faults remain unaccepted. Authentication history: six failed attempts;
prompt and installation histories are unchanged.

Task 20 is still earliest ready, no bypass; 15A's later work stays preserved.
All-task VM clearance persists. No outside intervention is identified.
Actual settings: `gpt-6-astra` / `high`, Standard. Next settings:
`gpt-6-astra` / `high`; keep model and effort because capture provenance and the
exact refused predicate remain unresolved despite matching content.
