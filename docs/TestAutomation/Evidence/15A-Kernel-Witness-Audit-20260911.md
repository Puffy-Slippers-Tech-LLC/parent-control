# 15A kernel-witness audit — 2026-09-11

Development host; actual settings `gpt-6-astra/high`, Standard. This is source
and protocol analysis, not a runtime qualification. Task 20's retained
source-change deferral has no new writer-completion/window evidence; no
unchanged stability experiment ran. All-task guarded VM clearance persists.

## New discriminating evidence

The audited upstream tag remains **v1.4.5**, not an assertion about the guest's
installed dependency. Direct public source reads established:

- [`policy.c`](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/src/library/policy.c):
  `_load_rules` stops at a rejected line, but `do_reload_rules` ignores that
  result and returns success after destroying the old rules. A marker before
  the product rules could survive a later parse failure. `process_event`
  allows when no rule has an opinion. Thus neither command success nor a
  lone positive marker establishes the complete candidate.
- [`notify.c`](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/src/daemon/notify.c):
  `handle_events` denies queue-overflow events without evaluating a rule;
  permissive mode changes that response to allow. A nonce-path denial, even
  with an adjacent successful control, could therefore occur under stale
  policy. This rules out making denial the generation-bearing observation.
- The [public rule format](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/doc/fapolicyd.rules.5)
  provides first-match exact paths, UID-scoped execute decisions and decision
  logging. These support a candidate challenge, but do not themselves supply
  an atomic ruleset receipt.

These are additional counterexamples to the prior
[interface audit](15A-Activation-Interface-Audit-20260911.md), not a repeat of its
rejected pre-parse digest proposal. No source from another checkout was read.

## Candidate protocol and its acceptance gate

The [application contract](../../SystemDesign/Applications.md#generation-witness-design-gate)
owns this proposed protocol. It is **not implemented or proven sufficient**.

Use a fresh root-only probe path per transaction, with a corresponding exact
allow rule and a separate deny control in an owned probe namespace. Place the
witness after all generated product rules, before the permissive fallback.
Keep executable content, DAC/mount conditions and UID fixed across controls;
ordinary execution must return the packaged probe's expected status. A stale
generation must not supply that generation's positive receipt. Correlate a
public rule-decision record for the unique probe with its actual kernel
execution outcome and the captured compiled input. A ruleset digest event alone
is still insufficient. Decision logging is a new candidate, not acceptance of
the earlier journal proposal.

Before connecting this to successful broker writes, locally and then in the
guest distinguish these cases:

| Condition | Required result |
| --- | --- |
| Correct candidate, expected positive decision and execution, deny control | Candidate may be acknowledged only after identity/input checks |
| Previous generation or foreign earlier allowance | No matching candidate rule receipt; reject |
| Queue-overflow/DAC/noexec denial | No matching deny-rule receipt; reject |
| Stopped, permissive, or unmonitored backend | Deny control executes; reject |
| Parse error before/after marker, missing or rate-limited records | No complete acceptance evidence; reject |
| Daemon restart, changed compiled input, or foreign writer during observation | Invalidate transaction; never reuse the observation |
| Timeout, unexpected exit, or uncertain cleanup | Fail without acknowledging activation |

Full compiled-input binding, marker placement in the presence of administrator
rules, public decision-field availability, and restart bracketing still need
executable refusal tests. Do not infer an arbitrary administrator ruleset's
complete successful parsing from a product marker. The next guest attempt must
use `system_enforcement.record_execution_backend` and audit its actual version.

## Bounded execution: concrete missing capability

The existing `tools/execution_policy_ready.py` directly runs a fixed boot
canary without a deadline. `tests/support/terminal.py::capture` owns its child
after `Popen` returns. Neither provides the missing bound on a kernel-stalled
exec during process creation. Python's [documented timeout behavior](https://docs.python.org/3/library/subprocess.html#timeout-behavior)
explicitly excludes initial process creation on some platform APIs. Adding
`timeout=` or a polling thread cannot establish cleanup of that missing handle.
This is a limit of reuse for this new boundary, not evidence that the accepted
terminal tests failed.

Prefer a small adapter over systemd's public
[`StartTransientUnit`](https://github.com/systemd/systemd/blob/v259/man/org.freedesktop.systemd1.xml)
and [service deadlines](https://github.com/systemd/systemd/blob/v259/man/systemd.service.xml),
using the broker's existing Gio system-bus connection and finite D-Bus calls.
A unique service with `Type=exec`, explicit startup/runtime/stop limits and no
restart lets the service manager own execution before exec completes. These
upstream interfaces are audited candidates; installed compatibility is pending.

**Next bounded implementation gate:** locally exercise successful execution,
exec failure, start timeout, lost reply, unit-name collision, identity replacement
and collection/cleanup failure. Record the returned job and unit invocation;
retain terminal evidence before unit collection. An ambiguous create reply must
not authorize stopping a unit merely because its name matches. Cleanup can act
only on the proven owned invocation. No unit was created here. Do not introduce
general job orchestration, broad process discovery, native fork machinery or a
new privilege grant to solve this one probe operation. Unit status such as
`203/EXEC` is an execution failure, not proof that fapolicyd denied it.

## Rollback and removal constraints

Every forward **and rollback** activation needs a fresh witness; restoring old
bytes or observing an old token must not establish a new acknowledgement. Keep
the cache unknown until the corresponding receipt is complete. A failed forward
operation still fails after successful rollback; uncertain rollback remains a
separate failure with retry state retained.

Deleting the sole witness with `89-oh-no-parent-control.rules` cannot prove that
its absence became active. A separate product-owned witness file could attest
the compiled input without the account-policy file during reversible `prerm`.
That introduces an explicit removal dependency: `postrm` must remove the witness
before deciding whether administrator rules remain, and preserve the existing
baseline/empty-directory handling. Its final reload/restoration needs separate
acceptance. No generated witness file, on-disk format or package behavior was
changed in this slice. Ship those ownership/cleanup changes together with any
witness integration; do not silently retain a new file or relabel current
notification-only cleanup as acknowledged removal.

## Verification and cleanup

- Read the existing notification recovery regressions and owning adapter,
  readiness, terminal-capture and uninstall implementations. No product tests
  were run for this documentation-only audit; retained runtime results keep
  their original scope. The activation attempt count remains two.
- Public browser reads had cache misses/403 responses; direct literal-URL
  upstream source reads succeeded. One POSIX reference was unavailable and is
  not relied upon. Three guessed local source operands were absent; file
  discovery/the support map resolved the maintained paths. No execution-policy,
  approval or Polkit denial occurred.
- Local link verification passed: **7 documents, 241 links, none missing**;
  scoped whitespace checks passed. All commands exited. No VM, worker, transient unit, lease,
  probe process, screenshot or background operation was started; no recovery
  obligation or temporary artifact remains. Other work was preserved.

Acknowledgement implementation, installed compatibility, all required controls,
native route/update coverage, Snap/Flatpak and full Task 15A acceptance remain
unfinished. Do not spend another full native run merely testing these known
counterexamples before local implementation/refusal coverage exists.
