# Proposed scheduling for `make test-all`

## Four host branches

The host concurrency cap is now four, reduced from six. Scheduler workers,
resource admission, branch assignment and the dashboard share one limit.
Every candidate must still be compatible with every active job and fit the
combined CPU and memory budgets. Pressure hysteresis, startup reservations,
exclusive artifact/VM work and inner build/Node concurrency remain unchanged.
The change applies to newly started runs; an existing process retains its
loaded limit. Idle branch headings are gray and running branch headings are bold.
Earlier worker-limit decisions and qualification records below
describe the preceding implementation.

Status: implementation present, 2026-09-12. The design below records the reviewed
target; the following scope describes the code now present. Generated aggregate
reports own per-run qualification and timing evidence; this document does not
claim a standing release pass.

## Host CPU admission

Run `20260914T002856Z-9c33d3d8` left branches 4 and 5 idle with compatible work
queued and the pressure gate open. Admission added every active job's full CPU
estimate to measured host usage, which already included those jobs. With two
UI buckets and units active, adding components reserved another 12 cores above
observed usage, exceeding the 15-core limit on the 20-core host even at 25% load.

Admission now adds the candidate's full estimate and one core of growth per
established job (capped at its estimate) to measured host usage. Full active
reservations apply until a fresh sample at least 20 seconds after launch, using
the same startup window as memory. Four UI buckets can therefore be admitted
in stages at 30% measured CPU usage when memory and pressure also permit.
The 75% CPU admission ceiling, pressure hysteresis, memory allowances and
compatibility rules still apply. Growth is an engineering allowance, not a hard
CPU limit; later bursts can exceed it and defer further launches. Wait reasons
separate pressure recovery from CPU budget and report the required spare cores.
This supersedes full active-CPU re-reservation in the earlier design below.
An already running coordinator retains its loaded policy.

## Prompt admission after pressure recovery

Run `20260914T004136Z-36bf75e1` started branches 2–4 about 50 seconds after
branch 1 and branches 5–6 about 72 seconds after it. The first delay came from
I/O `full avg10` retaining earlier stalls and a further 20-second low-pressure
window. The later launches also waited for active memory startup reservations.

Admission now computes CPU `some`, memory `some` and I/O `full` stall percentages
from changes in the kernel's PSI `total` counters over each sampling interval,
alongside CPU utilization and swap rates. These counters are the supported
[custom-window PSI interface](https://docs.kernel.org/accounting/psi.html#pressure-interface).
The kernel's `avg10` values remain in `resources.jsonl` as separate diagnostic
fields. A new pressure burst closes overlap immediately on observation; reopening
requires four seconds of consecutive low-pressure observations, normally three
samples at the two-second cadence. Cached readings cannot advance recovery.
Missing, malformed or decreasing counters disable overlap until valid samples
and the recovery window return.

CPU, memory, I/O and swap thresholds, the four-worker cap, category compatibility,
CPU/memory budgets and 20-second startup reservations remain in force. The
shorter recovery window replaces the original double smoothing; it is an
engineering policy, not a guarantee against later load spikes. It allows more
responsive admission after transient I/O and also detects new stalls before
they dominate `avg10`. Reports retain the pressure basis, recovery duration and
observed healthy time. Deterministic tests cover cold scheduler startup, active
reservations, stale averages, new stalls and invalid counters. Generated host
runs own live qualification. Package update activation is none; a running
coordinator retains the policy it loaded.

## Host memory admission

Host tests keep a fixed 2 GiB desktop reserve plus the candidate's full memory
budget. Established categories contribute up to 1 GiB each (capped at their full
budgets) to a shared growth allowance capped at 2 GiB across the active jobs.
Each launch is recorded by the coordinator; an active category keeps its full
reservation until a resource sample taken at least 20 seconds after launch.
These startup reservations are added separately and never capped by the pool.
This prevents immediate launches from spending the same unsampled headroom.
After startup, available memory already reflects resident running work; charging
its full budget again stranded a worker during publishing with roughly 8 GiB
available and no pressure. Adding components alongside established publishing
now requires 4 GiB available, adding units alongside publishing or UI requires
5 GiB, and adding another UI bucket requires 7 GiB. Publishing as the new
candidate still needs its full 6 GiB plus desktop and active growth allowances.

Run `20260914T010021Z-8419fee6` exposed excessive growth reservation with six
branches: branch 4 was idle while pending feedback and nested-Shell UI jobs
required 11 GiB (2 GiB desktop, 4 GiB candidate and 5 GiB established growth).
One recorded sample had 9.57 GiB available, 5.77 busy cores out of 20, an open
pressure gate and no swapping. The 2 GiB shared growth cap lowers that admission
requirement to 8 GiB. Regression tests retain the recorded sample to verify the
reduced worker cap and exercise four simultaneous UI workers at the 8 GiB
boundary before any worker finishes.
Mixed startup/established workers, one-byte memory boundaries, stale samples,
new launches and the other admission gates remain covered.

These remain engineering allowances, not measured subtree peaks or hard limits.
Startup duration does not prove peak allocation is complete: the policy accepts
later combined growth exceeding the 2 GiB pool, and unexpected external allocations
can still cause pressure. CPU, swap, pressure hysteresis, pairing restrictions and the four-worker
cap remain unchanged. VM launches keep the larger of 2 GiB or 20% of usable RAM
in addition to configured guest RAM and overhead. Memory deferrals display the
required available RAM alongside the existing sampled resource evidence.

This policy supersedes the original percentage-based host reserve and full
active-memory re-reservation below, and uncapped per-category growth allowances.
Package update activation is none; an already running coordinator does not
reload the policy.

## Build queue extension

The publishing companion list now also includes screen fidelity (`ui-screen`).
The run `20260913T235318Z-f66c0c90` left branch 2 idle for 127 seconds after units
and components finished: every remaining ready job was pairing-blocked, while
memory recovered above 7 GiB and the pressure gate stayed open. Lower memory
reservations alone cannot fix that exclusion. Screen fidelity can now fill the
free slot on the next scheduler pass with sufficient headroom. The scheduler
regression exercises this exhaustion of units/components with real admission
and asserts refill within one coordinator tick; it does not establish live
graphical/build qualification. That overlap remains to be validated in a fresh
unchanged-input host/build run.

Publishing, two fresh artifact builds and comparison now participate in the
two-worker host schedule. Four separate progress rows form the dependency chain
`publish -> build-a -> build-b -> compare`. No successor starts before its
predecessor exits and the coordinator validates its result. Both artifact paths
must be present, distinct and supplied by successful builders. Publishing/build
failure blocks dependent jobs and VM execution without erasing independent host
assertions. Fixture setup/cleanup or pytest infrastructure failure stops further
scheduling and drains owned companions. Setup/teardown events latch cancellation
as soon as their failure record is durable, without waiting for category exit.
Routine output remains flushed to live readers, with progress snapshots coalesced
to one per second and disk synchronization batched every five seconds by the
coordinator. Failure records, category closure and final closure force a checkpoint.
This prevents per-event report barriers from generating I/O pressure that starves
queued branches. Abrupt machine failure may lose the latest routine interval;
failure checkpoints retain the immediate durability boundary. Wait messages name
I/O, CPU, memory or swap pressure separately so spare RAM is not mistaken for a
guarantee that every admission gate is open.
Host pytest capture/fixtures and retained UI images use disk-backed `/var/tmp`
storage; see the [quota failure and storage contract](../../tests/README.md#local-component-work).
The isolated aggregate cleanup gate is shared with its UI, component and
fixture-runtime workers through the inherited checkout activity lock. A worker
checks the current source digest against the passing gate before reuse. A fresh
activity clears the coordination record, so it cannot cache success across runs;
missing records run prerequisites and invalid/changed records refuse execution.
The record is coordination among trusted host launchers, not privileged
authorization. Publishing, artifacts and installed/VM paths retain their own
safety gates. This removes repeated disk-backed cleanup fixtures from host
startup while preserving the complete prerequisite coverage before host work.
Dependency cycles and missing/duplicate
job identities are refused before any launch.

Publishing companionship is an explicit symmetric list in `regression_resources.py`:
unit and component, both exercised by the live host/build qualification, plus
screen fidelity after reviewing its private compositor, D-Bus, PipeWire, XDG
state, owned process cleanup and per-test evidence against publishing's private
snapshot and sbuild source/config/output directories. Publishing supplies no
host bind mounts, display/bus environment or external build hooks. The earlier
wider candidate run could not admit UI/build overlap with its required memory
headroom; it provides no live evidence for screen fidelity. Other UI buckets and
unreviewed candidates remain disabled. Artifact
operations remain exclusive. UI buckets retain distinct scheduling identities
for future qualification; reviewing one never authorizes the others. A second
publishing/build operation and all VM work remain incompatible with publishing.
Publishing reserves the existing
2 CPUs/6 GiB and artifact operations 2 CPUs/4 GiB, including nested processes.
These are conservative engineering reservations, not measured subtree peaks.
Full budgets apply to new launches and startup; established active work uses
the growth allowance described above.

The isolation review relies on private publishing source/build/output directories,
the sbuild unshare environment with fixed hooks and no host bind mounts, private
test buses and fixture directories, and screen fidelity's private compositor,
XDG state and per-test evidence. Publishing retains the package's declared
`make check`; host results never substitute for testing the packaged source in
its clean build environment. Source identities, test inventories, caller/fixture
behavior and every VM boundary remain unchanged. Installed authorization,
enforcement and expiry share accounts and global services and stay serial inside
one installation. This extension does not implement caller caching, guest test
sharding, new VMs or different backing verification.

The scheduler validates dependencies before launch and orders ready jobs by their
estimated downstream duration, preserving declaration order for ties. Build
estimates are based on retained runs (publishing about six minutes, each artifact
build about seven seconds); existing UI estimates remain ordering hints.
Unknown/changed jobs require isolation review, regardless of estimated duration.
One coordinator records `schedule.jsonl` start/finish/dependency/wait events,
including admitted companions, beside the existing resource samples and raw
pytest duration streams. Resource observations cover host load, including build
descendants and unrelated applications; they are not attributed process peaks.
Serial command ticks continue sampling throughout publishing and VM execution,
and each observation names the currently running categories. Comparisons therefore
include actual execution load rather than only admission samples.

`tools/run-tests host-builds` runs the complete host/build scope without inspecting
or authorizing the VM. Its sole optional `--serial-builds` flag retains publishing
and artifact operations after the host join for comparison. The existing `host`
route continues to omit publishing/builds. All use the maintained activity lock,
cleanup prerequisites and cooperative cancellation. Generated qualification
reports, not this implementation description, establish observed overlap,
outcomes and timings. Compare repeated unchanged-input serial/overlap runs and
both complete verification modes; preserve each first failure. No retries,
weaker assertions, longer deadlines or relaxed capacity gates establish success.
If a pairing shows unexplained interference, remove it from the list until its
cause is fixed and qualified. Measure total wall time as well as post-join time;
moving work across the join alone is not a speed improvement.

The following original scope is historical where it describes serial publishing.
VM exclusivity, ownership, resource reserves and qualification requirements
continue to apply. Package update activation remains **none**.

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
deadlines and assertions remain. Standalone launchers run their safety
prerequisites; aggregate workers validate the shared passing gate described above.
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

The live terminal dashboard fits both terminal width and height, reserving a
row for its trailing newline so refreshes cannot leave duplicate branch frames
in scrollback. When space is limited, prioritize overall/interruption status,
running or failed categories, and branch headings; indicate how many rows are
hidden. Resize invalidates the previous cursor offset and clears the visible
frame. Reports and redirected output retain the complete category inventory.

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
