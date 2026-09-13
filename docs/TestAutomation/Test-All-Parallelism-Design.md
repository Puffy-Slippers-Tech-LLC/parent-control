# Proposed scheduling for `make test-all`

Status: implementation present, 2026-09-12. The design below records the reviewed
target; the following scope describes the code now present. Generated aggregate
reports own per-run qualification and timing evidence; this document does not
claim a standing release pass.

## UI bucket extension

The host queue now partitions the discovered UI inventory into six groups:
request behavior, layout/overflow, feedback, preview/About, screen fidelity and
nested Shell. Entire modules run sequentially inside a private pytest process;
the two existing workers can each admit a UI bucket using the unchanged full UI
reservation. No additional worker or inner pytest parallelism is introduced.
New modules are discovered automatically and default to exclusive execution
until reviewed. Every bucket must recollect exactly its assigned IDs; missing,
duplicate or changed IDs cannot yield a pass. Fixture setup/teardown failures
stop further scheduling and drain owned companions through cooperative cleanup.

The isolation audit covers private Mutter, D-Bus, AT-SPI and XDG state,
per-test temporary evidence, and owned preview process handles. Nested Shell
remains one job because it publishes stable latest artifacts. Its
outer display comes from an explicitly requested private compositor fixture,
including when the nested-Shell module runs on its own. Dogtail's default
shared truncating debug file is disabled through its supported checkout config;
pytest console and per-test diagnostic evidence remain captured. Existing
deadlines, assertions and each launcher's safety prerequisite process remain.
Nested-Shell interaction sets and observes the public `OverviewActive` property
on its owned bus instead of relying on timed Super/Escape toggles. It retains
keyboard-opening coverage, while repeated pointer activations target the real
indicator's observed AT-SPI allocation inside overview so focus transfer to the
new app cannot activate Cancel. St.Button does not expose AT-SPI Action.
No automatic retries are added. Initial duration estimates include a startup
allowance and case counts; per-phase pytest durations are retained for calibration.

`tools/run-tests host` qualifies this same host plan through the join boundary
without VM inventory/authorization, publishing or artifact construction. Its
report labels the limited scope. Generated reports own actual qualification
and timings; the presence of this implementation is not itself a stability claim.
Use unchanged-input runs to assess interference and variance, preserve every
failure, and fix its cause before accepting overlap. All full-run build/VM
ordering remains as documented below.

The coordinator displays a persistent red interruption warning during owned
shutdown at every stage. Signal handlers only latch cancellation; repeated
interrupts cannot bypass cleanup. Final output distinguishes shutdown completion
from the cleanup outcome recorded in the report.

## Original implementation scope

The existing aggregate now schedules at most two host categories through
`regression_schedule.py`, with one coordinator for category state, tagged output,
private raw streams and progress. UI starts first; sequential companions include
units, private-bus components, fixtures and small checks. Publishing, both
reproducibility builds and VM execution stay serial. The installed-system
selection continues to share one installation across all functional phases;
regressions protect that behavior. There are no compatible ready E2E customer
journeys to group yet, and their independent-attempt evidence contract remains
unchanged.

`regression_resources.py` samples CPU utilization, unified cgroup ancestor
limits, memory availability, swap activity and pressure. It uses the proposed
pressure thresholds and 20-second admission window. Any swap write or at least
1 MiB/s of swap reads closes admission. Smaller reads of previously evicted
pages do not alone imply current reclaim; memory and PSI gates still apply.
Both swap rates are recorded for calibration. Initial fixed reservations
are intentionally conservative: UI 4 CPUs/4 GiB, units 2 CPUs/2 GiB, other host
categories 1–2 CPUs/1 GiB. These are engineering budgets, not measured subtree
peaks. They are added to observed usage rather than attempting unsafe process
attribution. CPU headroom gates overlap; memory gates even single known host
jobs. High host pressure or over 75% observed CPU use defers even serial work.
Publishing reserves 6 GiB, artifact construction 4 GiB. Before a VM attempt,
the maintained pinned `tools/test-vm xml` reader supplies configured RAM and
vCPU counts; admission adds QEMU/controller overhead without changing the VM.
A single CPU-heavy job remains eligible on smaller otherwise healthy hosts.
Missing metrics disable overlap. Unknown categories stay exclusive. Internal Node and package
build concurrency is bounded at two; no CPU/I/O priority or cgroup mutation was
introduced. Peak-based profiles and stronger process resource controls remain
outside this first scope.

`test_activity.py` coordinates maintained checkout launchers using an inherited
locked descriptor, not an environment-only bypass. Ordinary pytest caches are
disabled. Source content/mode checks at boundaries reject detected input changes;
they do not provide immutable source execution. New regression modules cover
scheduling, resource admission, input identity and activity ownership, with
real two-worker cancellation in `test_regression_cleanup_safety.py`.
The report records measured host wall time, summed category execution and maximum
active workers; private `resources.jsonl` records sampled headroom and pressure.

These changes are development/test tooling; package update activation is none.
They do not alter installed product state or require new privileged operations.

## Objectives and review decision

Priorities, in order: preserve reliable results and resource ownership; reduce
complete-run wall time; preserve responsiveness for ordinary desktop work.
Parallel execution is an optimization that can be disabled without changing
collection, assertions, prerequisites, required evidence, or acceptance.

Replace the earlier three-lane proposal with **at most two active categories**.
Start a long eligible host suite and fill the other slot with sequential,
compatible work. One category can contain many child processes: the limit is
additional to CPU, memory, and I/O admission rules, not a resource guarantee.
Keep all VM attempts exclusive of other test execution in the first release.

The previous [aggregate](../../tools/regression.py) called categories serially.
`make -j` could not parallelize that Python loop. The existing
[runner contracts](../../tests/README.md#all-established-regressions) and
[Task 28A](Task-28.md#task-28a) remain authoritative; planned input capture and
artifact caching are not assumed to exist.

## Resource and isolation contract

Use a small, fixed category table in the existing aggregate. Each category
declares prerequisites, exclusive resources, qualified companion categories,
and a conservative resource estimate. Unknown categories default to exclusive
execution; newly discovered cases remain included in their owning suite.
Changes to fixtures, launchers, or external dependencies require reassessing
the affected overlap qualification.

| Work | Initial concurrency policy |
| --- | --- |
| Discovery and initial cleanup-safety gate | Serial, before protected work. |
| UI/nested-Shell buckets | One serial UI process per admitted bucket; at most two host jobs, private graphical sessions, unchanged full UI reservations. New modules stay exclusive pending isolation review. |
| Unit/contracts, private-D-Bus components, fixture runtime | Eligible companions after isolation audit and qualification; execute in separate processes. |
| Source/traceability, static, child Node/GJS, backend readiness | Eligible companions; their short durations do not justify additional slots. |
| Publishing, artifact build A, artifact build B, comparison | One build operation at a time, in private directories. UI overlap requires separate qualification and resource admission. |
| Installed-system and each ready E2E variant | Exclusive of other test categories, from controller launch through collection, restoration, and exit. |

Retain the existing nonblocking [VM lease](../../tests/integration/system_runner.py)
across all invocations. It rejects conflicts; it does not queue controllers.
Never launch a controller speculatively and use lease refusal as scheduling.
No simultaneous guest pytest, guest areas, or E2E variants; no extra VM,
snapshot, or overlay. Preserve the installed-system-before-E2E order and refusal
of subsequent VM attempts after failure or unproven cleanup.

One aggregate owns scheduling for the checkout. A competing aggregate must
refuse clearly before tests start. Supported focused launchers must coordinate
with this ownership or refuse while an aggregate owns execution; otherwise a
second terminal could bypass both the concurrency cap and evidence isolation.
Use validated ownership through the maintained launchers, not a caller-supplied
environment flag. Host activity outside the project is handled by load sensing.

Before qualifying a companion, audit writable files, caches, ports, buses,
settings, fixture identities, subprocess cleanup, and library session state.
Private D-Bus and compositor fixtures are promising isolation, not proof of
conflict freedom. Disable or privatize ordinary pytest caches. Preserve private
temporary directories and run-specific evidence. Nested-Shell shared `latest`
outputs must not be written by concurrent invocations. Keep tests serial inside
their current session-scoped UI and D-Bus fixtures.

## Schedule and selection

```text
Discovery + isolated safety prerequisites
                    |
         +----------+--------------------------------------+
         |                                                 |
  Long host category                          Sequential companion queue
  (currently UI)                              unit / components / fixtures /
                                              small checks
         |                                                 |
         +--------------------- join ----------------------+
                                |
           publishing -> build A -> build B -> comparison
                                |
           installed-system -> cleanup -> E2E -> cleanup -> ...
```

This is a capacity diagram, not a requirement to keep both slots occupied.
Each companion starts only after its own prerequisites pass and the current
load admits it. Launcher cleanup checks remain separate prerequisite processes
before their protected child; none are removed or replaced by cached results.
The initial cleanup-safety gate completes before any parallel branch starts.

Schedule ready work by estimated remaining critical-path duration, with fixed
category order as a deterministic tie-breaker. A prerequisite inherits the
importance of work it unlocks. Estimates include launcher prerequisite and
cleanup time. Long work starts early; do not deliberately delay it to match
the end of another suite. When UI finishes, remaining compatible host work
can use both slots, but the one-build rule still applies. If a candidate does
not fit, try another compatible ready category rather than blocking the queue
behind it. With one slot available, execute the same complete scope serially.

No publishing/artifact job is assumed to be short. Initially use conservative
estimates; record their actual times before optimizing ordering. Build A and B
remain independent fresh builds, sequentially scheduled, and comparison depends
on both. Package-bearing tests require successful builds and comparison.
Preserve current independent product-failure reporting; a failed host test does
not become a pass or automatically erase other required results. Infrastructure,
source-integrity, prerequisite, cancellation, and cleanup failures block work
according to their dependencies, with uncertain ownership stopping new work.

## Load-aware admission and desktop headroom

Sample read-only CPU utilization, effective CPU capacity, `MemAvailable`,
swap-in/out activity, and CPU/memory/I/O pressure every two seconds. Use sustained
windows rather than a single `loadavg` reading. Linux
[pressure stall information](https://docs.kernel.org/accounting/psi.html)
measures time lost waiting for resources and provides recent averages. Use
CPU `some`, memory `some`/`full`, and I/O `some`/`full`; system CPU `full` is not
a useful signal. Missing or stale measurements disable overlap, with a visible
reason. A known inability to fit even one job requires waiting or an explicit
resource refusal, not forced execution.

Proposed starting policy, to calibrate during qualification:

| Control | Initial design value |
| --- | --- |
| Active categories | Maximum two; serial fallback. |
| CPU headroom | Predict total host demand, including unrelated work, at no more than 75% of effective CPU capacity. Account for subprocesses and internal build/Node parallelism. |
| Memory headroom | Keep at least the larger of 2 GiB or 20% of usable RAM available after admitting the candidate and reserving remaining growth of active jobs. Do not count swap as headroom. |
| Estimate margin | Use a conservative observed peak plus at least 25% for the full job subtree, not just the launcher. Unknown or materially stale estimates require serial measurement. |
| Permit overlap | All resource budgets fit and, for 20 seconds, CPU `some avg10` < 5%, memory `some avg10` < 0.5%, I/O `full avg10` < 1%, with no sustained swap-in/out. |
| Defer new launches | A headroom budget fails, or CPU `some avg10` >= 10%, memory `some avg10` >= 1%, or I/O `full avg10` >= 2%. Reopen only after the full low-pressure window. |
| Marginal readings | Between admission and deferral thresholds, preserve the current gate state; never override the headroom budgets. |

These are proposed thresholds, not measured guarantees or kernel recommendations.
Use available memory plus expected *incremental* growth; do not subtract the
same resident memory twice. Account for external CPU demand separately from
active tests' reserved demand. Peak measurements must cover owned descendants;
never infer ownership through process-name matching or host-wide process scans.
Cold build caches and representative external load belong in qualification.

The review snapshot exposed 20 logical CPUs, about 30.5 GiB RAM, and 19.4 GiB
available. The proposed memory reserve would be about 6.1 GiB. These values are
illustrative; admission uses runtime measurements and effective limits.

Cap internal build parallelism explicitly; preserve the publishing builder's
current two-job setting. Qualify reduced CPU/I/O priority for background build
work through supported process-group/resource controls. Any cgroup accounting
or priority setup must use supported delegated interfaces through the maintained
setup/launcher boundary, and verify coverage of actual children. Libvirt's QEMU
process is not assumed to inherit the caller's limits. CPU/I/O weights provide
relative preference, not guaranteed reservations; tight memory limits can cause
reclaim stalls or OOM failures. See the kernel's
[cgroup controls](https://docs.kernel.org/admin-guide/cgroup-v2.html).
Do not use dynamic throttling of UI/VM execution as the normal load response.

On rising load, stop admitting work and let active jobs finish and clean up.
Do not SIGSTOP tests, freeze the VM, change clocks/timeouts, or automatically
retry a failure. Already-running jobs cannot instantly shed their resource
usage; conservative reservations and bounded internal parallelism are necessary.
Arbitrary new external load cannot be guaranteed harmless. If resources become
critically unsafe, use owned cooperative cancellation, retain an incomplete
result, and await cleanup. Resource waiting is visible, cancellable, and counted
separately from test execution; prolonged deferral never relaxes the thresholds.

## Coordinator, evidence, and source consistency

One coordinator owns admission, category state, timers, dashboard, and atomic
progress writes. Workers use the existing validated category commands and owned
cancellation protocol. They send tagged output/events to the coordinator;
workers never concurrently mutate report objects. Preserve per-category raw
output and stream tagged blocks into the main report, including partial lines
and immediate failure details. A slow or failed evidence writer must cause
backpressure or controlled cancellation, not lost evidence or a false pass.

Register every owned child before cancellation can act on it. Cancellation
latches once, stops all new launches, notifies all active owned children, and
waits for every cleanup. Protect launch-versus-cancel and completion-versus-
resource-release races. Reserve resources before spawning and release them only
after child exit and cleanup, including failure paths. Resource accounting is
not permission to signal unrecorded descendants or QEMU directly.

All workers must refer to the same run input identity. Extend the existing
source validation without pretending the planned immutable checkout support is
available: record inputs before dispatch, validate at stage boundaries and final
acceptance, and invalidate the run on detected changes. Keep generated files
outside source inputs. If complete input consistency cannot be established,
refuse a green aggregate; do not silently combine results from changed sources.
Checks at boundaries alone do not prove immunity to edit-and-revert races;
stronger input capture, if required, belongs to the existing Task 28A contract.

Record execution time separately from resource/dependency wait time, prerequisite
and cleanup time, resource estimates/peaks, admitted overlaps, and deferral
reasons. Current category elapsed timers are useful but insufficient for this
distinction. Compare complete-run wall time; summed worker time and test counts
do not establish savings. Historical timings only guide scheduling, never reuse
passing tests or replace required cleanup checks.

## Verification required before enabling overlap

1. Deterministic scheduler tests with fake time/resource samples: dependency and
   exclusivity enforcement, maximum concurrency, long-job selection, sequential
   companions, hysteresis, unknown/stale metrics, memory growth, and starvation.
2. Cross-invocation refusal and existing VM lease tests; no unsafe queued launch
   after lease, source, safety, infrastructure, or cleanup failure.
3. Interleaved-output, report-write failure, duplicate/missing event, exit-code,
   and cancellation-at-every-lifecycle-boundary tests with explicitly owned
   harmless processes. Prove all children are reaped and evidence survives.
4. Audit each enabled pairing and obtain current serial timing/resource evidence
   through supported launchers. Qualify pairings individually under idle and
   representative busy-host conditions. Start with UI plus unit/short host work;
   admit UI plus publishing/build only after its separate qualification.
5. Verify no changes to host desktop/settings/accounts, fixture ownership,
   source files, artifact integrity, or shared evidence. Prove parallel and serial
   plans execute the same discovered case IDs and prerequisite closure.
6. Run required cleanup regressions before protected operations. Complete the
   serial VM sequence after parallel host work, including a cancellation case
   proving restoration finishes before the next attempt is possible.
7. Retain a current-input complete aggregate result with every required suite
   and ready variant. Accept the optimization only with lower wall time, no
   unexplained failures or new timing instability, and preserved desktop
   headroom. A passing retry never overwrites a failed attempt.

The UI bucket extension above addresses the remaining host critical path.
Simultaneous reproducibility builds, a third slot, and host/VM overlap remain
outside scope and require separate qualification.
