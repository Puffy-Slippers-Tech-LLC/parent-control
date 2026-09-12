# 15A bounded probe transport — 2026-09-11

Development host; actual settings `gpt-6-astra/high`, Standard. Task 20's
source-change deferral was rechecked without another unchanged experiment;
no writer-completion/window evidence was supplied. All-task VM clearance persists.

## Implemented and locally verified

The [owning contract](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits)
defines `broker/oh_no_parent_control/execution_probe.py::ExecutionProbe` and its
limits. This small adapter reuses the broker's finite Gio call transport and
the packaged canary. It creates a fresh named transient service, pins terminal
evidence, binds observations to a unique manager and observed invocation, then
releases its own client reference and observes collection. It never signals a
process or stops/resets a unit by name. No policy transaction is wired to it.

The existing boot canary is deliberately the only executable accepted. Fresh
root-owned generation paths and the decision/compiled-input receipt remain
separate unfinished work; this result cannot acknowledge any policy generation.

## Supported interface audit

The upstream **v259** audit is not a claim about the guest's installed version:

- [Manager implementation](https://github.com/systemd/systemd/blob/v259/src/core/dbus-manager.c):
  transient creation refuses a non-pristine unit before setting properties;
  `AddRef` tracks the sending client after property setup and before job queueing.
- [Unit implementation](https://github.com/systemd/systemd/blob/v259/src/core/dbus-unit.c):
  `UnrefUnit` delegates to sender-reference removal, not a process stop. The
  [systemd-run client](https://github.com/systemd/systemd/blob/v259/src/run/run.c)
  uses `AddRef` for bus-client lifetime pinning.
- [Unit lifetime documentation](https://github.com/systemd/systemd/blob/v259/man/systemd.unit.xml)
  and [GC implementation](https://github.com/systemd/systemd/blob/v259/src/core/unit.c):
  client references retain status, collection discards it, and active jobs or
  remaining processes prevent collection. Job timeout alone does not stop a
  service, hence the separate start/runtime/stop limits.
- The [public D-Bus interface](https://github.com/systemd/systemd/blob/v259/man/org.freedesktop.systemd1.xml)
  supplies creation, property reads and reference release; no private native
  interface, process discovery or new privilege grant was introduced.

The freedesktop rendered manual returned HTTP 403; direct tagged upstream
source reads succeeded. One source-symbol search had no match; the owning
unit/manager implementations supplied the relevant definitions. No approval
or Polkit denial occurred.

## Verification

Exact final focused selection:

```sh
tools/run-unit-tests tests/unit/test_execution_probe_cleanup_safety.py tests/unit/test_execution_policy.py tests/unit/test_adapters.py -q
```

**52 tests and 24 subtests passed**, including 25 new probe cases. An initial
21-case probe run also passed before adding stable-transition, command-binding
and between-poll replacement checks. No test failure occurred.

The probe cases cover fast exit with retained status, execution failure/signal/
startup timeout results, lost create reply before/after creation, collision,
identity and manager changes, missing evidence, changed command, pending job,
stalled startup/runtime/stop, failed reference release/collection, ordinary
state transitions and redacted diagnostics. Doubles model client pinning and
GC; they create no processes or systemd units and do not establish kernel or
installed-systemd behavior. The existing adapter and notification/rollback
regressions remain green. Full `make check`, installed runs and task acceptance
were not attempted for this unfinished local boundary.

Changed-document links passed: six documents, 236 targets, none missing.
Scoped tracked/new-file whitespace checks reported no defects. The new-file
`git diff --no-index --check` calls returned 1 for file differences, with no
whitespace diagnostics. Handoff patch context mismatches were corrected before
verification; no code/test failure or denied action resulted.

## Remaining gate and cleanup

A timed-out create can still be dispatched later. Absence at observation time
cannot prove that no unit/reference will appear on the broker's long-lived bus
connection. Such a result stays failed with cleanup uncertain; it is never
silently retried or converted into success by name lookup. Resolve safe
settlement/lifetime ownership before live qualification. Also bind the original
job to its invocation before receipt integration; pre-observation privileged
replacement is outside this local proof. Then qualify the real transport's
success, denial/failure and cleanup through a guarded installed selection.

All commands this session started exited and their results were collected.
No host/guest transient unit, VM, lease, worker, probe process, screenshot or
background operation was started; no operational cleanup/recovery remains.
The simulated uncertain-cleanup cases above are test results, not live leftovers.
Unrelated documentation changes appeared between entry and final status in
`docs/SystemDesign/Frontends.md`, `docs/Artwork/Request-Scenery.md` and
`docs/Portal-updates.md`; they were preserved without reading or diffing them.
No fresh source-stability claim or VM attempt was made.
Activation attempt count stays two. Native routes/update, Snap/Flatpak,
generation receipts, rollback/removal and full Task 15A acceptance remain open.
