# 15A notification recovery — 2026-09-11

One manual-intervention slice, actual settings `gpt-6-astra/high`, Standard.
Development-host scope; all-task guarded VM clearance persists. The
[Task 20 intervention](../Task-20.md#manual-source-stability-intervention--2026-09-11)
selected local 15A work because no completion/pause evidence established that
the release-tool writer had stopped. No VM attempt was used to test stability.

## Reproduced failure and correction

After candidate notification fails, restoring the prior file and then failing
its notification leaves disk and daemon potentially different. Previously,
`reconcile` accepted a later request matching the restored file without any
reload. A new adapter similarly treated an existing file as sufficient.

`FapolicydPolicy` now records only the bytes whose compile and notification
completed in this instance. Reconciliation/removal invalidate that record before
mutation; successful rollback restores it, failed rollback leaves it unknown.
An identical request retries when unknown; repeated failure still raises.
The existing lock, atomic replacement, bounded public commands and error
propagation remain. Added rollback logs contain no rule contents or raw errors.

The [owning contract](../../SystemDesign/Applications.md#notification-recovery-and-acknowledgement-limit)
and [reuse map](../Reuse-Map.md#existing-interfaces-to-find-once) publish the
implementation, downstream consumers and limits. This is command-notification
recovery, not active-policy acknowledgement. No new OS integration or saved-data
format; activation remains `process-restart`.

## Verification and cleanup

- Before correction, `tools/run-unit-tests tests/unit/test_execution_policy.py -q`
  exited 1: two failed operation subtests in
  `test_identical_rules_after_failed_rollback_retry_daemon_notification` and
  `test_new_adapter_reloads_existing_identical_rules` failed; 12 tests and four
  subtests passed. The stateful double independently models source, compiled and
  daemon rules, including a failed command whose notification was consumed.
- After the final code/test edits,
  `tools/run-unit-tests tests/unit/test_execution_policy.py tests/unit/test_execution_policy_ready.py tests/unit/test_system_enforcement.py tests/unit/test_uninstall.py tests/unit/test_adapters.py -q`
  exited 0: **201 passed, 24 subtests passed**, 0.52 seconds. Includes eventual
  recovery, repeated refusal, new-adapter retry, successful-rollback reuse,
  compilation/notification failure, timeouts, safe logging and affected callers.
- Focused diff review, changed Markdown links and scoped `git diff --check`
  complete this local slice. No full `make check`, package build or installed
  acceptance is claimed. Existing Task 15A native results retain their original
  input identities; the new adapter needs live qualification with fresh inputs.
- An initial architecture search used a nonexistent guessed module name; the
  design index resolved it to `SystemDesign/Applications.md`. A web-tool fetch
  of the CLI manual failed; its direct public read succeeded. Neither was an
  approval denial or test failure.
- All commands exited. Temporary test directories were context-managed and
  removed. No VM, worker, lease, screenshot or long-lived process was started;
  no current VM-state claim is inferred from historical runs. No approval or
  Polkit denial; other workspace edits and logs were preserved.

Next: establish a supported, generation-specific bounded active-policy witness
with failure/rollback semantics. Audit the actual installed-version public
interface before implementation; neither `--list`, command exit status nor the
boot-only canary is that witness. Once inputs are stable, fresh guarded native
qualification remains required. Task 20 resumes first when its documented
source-stability return condition is established. No checklist entry completed.
