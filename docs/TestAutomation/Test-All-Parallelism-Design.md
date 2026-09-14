# Scheduling for `make test-all`

This document owns the current scheduling policy and isolation rationale.
The [runner guide](../../tests/README.md#all-established-regressions) owns commands,
operator output and retention; [Task 28A](Task-28.md#task-28a) owns unfinished
input-capture and caching work. Update contracts in place. Generated aggregate
reports own per-run qualification and timing evidence.

Priorities are reliable results and resource ownership, complete-run wall time,
then desktop responsiveness. Disabling overlap must preserve discovery,
assertions, prerequisites and evidence. Implementation presence does not
establish a release pass. Package update activation is **none**: these are
development/test tools, and a running coordinator retains its loaded policy.

## Schedule and selection

Scheduler workers, admission, branch assignment and the dashboard share a
four-worker cap. Every candidate must be compatible with every active job and
fit the combined budgets. Discovery precedes cleanup; every cleanup worker must
pass and exit before downstream execution. Host jobs, publishing and artifact
operations then share the four branches. Installed-system and each ready E2E
variant run exclusively after the host/build join, with cleanup between attempts.

Validate dependencies and job identities before launch. Order ready jobs by
estimated downstream duration, preserving declaration order for ties. A
prerequisite inherits the importance of work it unlocks. Estimates include
startup and cleanup and affect ordering only. Request behavior precedes units
and components. Try another compatible ready job when a candidate cannot fit;
with one slot available, execute the same complete scope serially.

Refill a free branch within five seconds, or at most ten seconds through an
ordinary transient delay, when compatible, dependency-ready work fits the
budgets. These targets never override resource shortages or failed prerequisites.

## Cleanup buckets and required join

After discovery, the same four host branches execute the cleanup prerequisites
in four balanced buckets. `regression_cleanup.py` keeps reviewed modules eligible
to overlap only with other cleanup buckets; newly discovered safety modules stay
included but exclusive until their isolation is reviewed. All cases in
`test_*cleanup_safety.py` and `test_graphical_lease.py` remain required. Workers
run serial pytest sessions with private temporary trees, disabled caches and no
inherited aggregate retention registration. External commands and VM services in
these modules are doubles; real child-process, socket and kernel-lease checks
operate on explicitly owned resources. Keep every module and its fixtures
together, including retention's three 100-run stress variants.

Only those retention repetition tests use private `/tmp` trees, with per-iteration
bounds of fewer than 64 entries and 256 KiB of file contents per case. They keep
all 100 iterations and real filesystem operations. Memory-backed `/tmp` avoids
repeating disk flush latency; hosts with disk-backed `/tmp` may be slower.
Disk-backed tests separately verify journal flush/replace/directory-sync order,
I/O failure propagation and preservation of existing evidence. The ordinary
pytest temporary root, runner journals and evidence remain disk-backed; no
production sync or cleanup protection is bypassed.

The existing scheduler applies the same resource budgets and cancellation
protocol. Pack the longest estimated pieces first into the least-loaded bucket,
using deterministic tie-breaks. Grouping avoids an interpreter start and repeated
admission for every small module. Estimates affect packing and ordering only;
actual wall time and host contention determine savings. Exact collection and completion IDs must match
each bucket's discovered inventory. The coordinator joins every worker, requires
every bucket to pass, validates source inputs and persists results before
publishing the shared cleanup gate. No downstream host, build or VM execution
starts before this join. Discovery and collection still precede the gate.

Before the first cleanup launch, allow the existing overlap monitor up to one
recovery window plus one sample (six seconds) to warm up. Otherwise one early
disk-heavy bucket can prevent its companions from being admitted. This wait is
cancellable and counted in cleanup wall time. Missing metrics or persistent
pressure retain normal serial fallback; no admission threshold is relaxed.

The dashboard and schedule distinguish cleanup from subsequent host execution;
both phases reuse branches 1–4 and have independent frozen timers and joins.
Waiting rows append case totals and omit routine capacity/dependency reasons;
resource and other actionable reasons remain visible and the schedule retains
all reasons. A vertical spacer continues the tree before each join.

Cooperative interruption drains every owned worker. Abrupt termination during
parallel cleanup refuses automatic recovery because partial bucket results do
not prove all children exited. Preserve the existing recovery journal rather
than broadening the old serial-initial-check exception.

## Builds and compatible companions

Publishing, two fresh artifact builds and comparison participate in the
four-worker host schedule. Publishing, build A and build B are independent;
only comparison depends on both builders. No comparison starts before both
builders exit and the coordinator validates their results. Both artifact paths
must be present, distinct and supplied by successful builders. Outputs are keyed
by build identity so either builder can finish first. Build failure blocks
comparison; publishing failure leaves independent builds eligible. Any package
qualification failure blocks VM execution without erasing independent host
assertions. Fixture setup/cleanup or pytest infrastructure failure stops further
scheduling and drains owned companions. Setup/teardown events latch cancellation
as soon as their failure record is durable, without waiting for category exit.
Checkpoint cadence and durability limits belong to the
[runner guide](../../tests/README.md#all-established-regressions).
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
unit, component, request behavior and screen fidelity, based on its private compositor, D-Bus, PipeWire, XDG
state, owned process cleanup and per-test evidence against publishing's private
snapshot and sbuild source/config/output directories. Publishing supplies no
host bind mounts, display/bus environment or external build hooks. Other UI/publishing
pairings and unreviewed candidates remain disabled. Artifact operations can overlap
all known parallel host categories, publishing and each other. Each builder reads
selected checkout inputs into its own temporary source copy, stages the Debian
package under that copy, and builds fixtures into a distinct output with a private
Flatpak repository and HOME/XDG roots. It does not install or run the product.
Comparison reads only the two completed artifact directories. The inherited
activity lock and retention writer lock coordinate ownership and allocations;
owned command cancellation and aggregate cleanup prerequisites remain unchanged.
Unknown/exclusive UI categories and all VM work remain incompatible with artifacts.
A second publishing operation remains incompatible with publishing.
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

## UI isolation

The host queue partitions the discovered UI inventory into six groups:
request behavior, layout/overflow, feedback, preview/About, screen fidelity and
nested Shell. Entire modules run sequentially inside a private pytest process;
each of the four host workers can admit a UI bucket using the full UI
reservation. There is no inner pytest parallelism.
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

## Shared ownership and isolation

Use a small, fixed category table in the existing aggregate. Each category
declares prerequisites, exclusive resources, qualified companion categories,
and a conservative resource estimate. Unknown categories default to exclusive
execution; newly discovered cases remain included in their owning suite.
Changes to fixtures, launchers, or external dependencies require reassessing
the affected overlap qualification.

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

## Load-aware admission and desktop headroom

`regression_resources.py` samples CPU utilization, unified cgroup ancestor
limits, memory availability, swap activity and pressure every two seconds.
Admission uses CPU `some`, memory `some` and I/O `full` percentages from interval
changes in PSI total counters; kernel `avg10` values remain diagnostic evidence.
Cached readings cannot advance recovery. Missing, stale, malformed or decreasing
counters disable overlap until valid samples and the recovery window return.

| Control | Policy |
| --- | --- |
| CPU | Overlap must fit 75% of effective capacity, including measured usage, full candidate demand and active allowances. Observed usage above 75% also defers serial work; a single CPU-heavy job can run on a smaller otherwise healthy host. |
| Host memory | 2 GiB desktop reserve plus full candidate budget, startup reservations and pooled established growth. Shortage defers even one known host job. |
| VM memory | 2 GiB desktop reserve plus configured guest RAM and QEMU/controller overhead, using the pinned `tools/test-vm xml` reader. Swap is not headroom. |
| Open overlap gate | Four seconds of fresh samples with CPU pressure < 5%, memory pressure < 0.5%, I/O pressure < 5% and no disqualifying swap activity. Normally three samples. |
| Close overlap gate | CPU pressure >= 10%, memory pressure >= 1%, host I/O pressure >= 10%, or disqualifying swap activity. |
| Artifact and VM I/O | Artifact, installed-system and E2E launches additionally refuse at I/O pressure >= 2%, even when the host overlap gate is open. |
| Swap | Any swap write or reads >= 1 MiB/s defer admission. Smaller reads alone do not imply current reclaim. |
| Marginal pressure | Preserve gate state between low/high thresholds; budgets still apply. |
| Inner concurrency | Node file and package build concurrency are capped at two. |

Reserve full active CPU and memory budgets until a fresh sample at least
20 seconds after launch. This prevents launches spending the same unsampled
headroom. After startup, measured usage already includes resident work:
add one CPU core of growth per established job, capped at its estimate;
add up to 1 GiB per job, capped at its memory estimate, to a growth pool
capped at 2 GiB. Startup reservations are separate and never capped by that pool.

Budgets include nested processes: UI 4 CPUs/4 GiB; units and cleanup 2 CPUs/2 GiB;
other host categories 1–2 CPUs/1 GiB; publishing 2 CPUs/6 GiB; artifacts
2 CPUs/4 GiB. Adding units beside established UI needs 5 GiB available; a second
UI bucket needs 7 GiB; a fourth beside three established UI jobs needs 8 GiB.
These are engineering allowances, not hard limits or measured subtree peaks.
Later growth and unrelated applications can exceed them. Regression coverage
includes mixed startup/established workers, one-byte memory boundaries,
stale samples, new pressure bursts and invalid counters.

Wait reasons distinguish pressure recovery, CPU, memory, I/O and swap; memory
and CPU budget messages show required headroom. Missing metrics permit only
normal serial fallback, never override a known shortage. Waiting is visible,
cancellable and timed; prolonged waits never relax thresholds.

On rising load, stop admitting work and let active jobs finish and clean up.
Do not freeze tests/VMs, change clocks or deadlines, or automatically retry.
Critical resource conditions require owned cooperative cancellation and an
incomplete result. No CPU/I/O priority or cgroup mutation is implemented.
Stronger controls require supported delegated interfaces and qualification
covering actual owned children; QEMU does not necessarily inherit caller limits.
Never infer ownership or attribute peaks through host-wide process scans.

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

## Progress event framing

`regression_events.emit` writes the leading delimiter, JSON and trailing
delimiter in one stream write, then flushes to prevent diagnostics from splitting
the event framing. The prepare-host dispatch test also joins its
owned thread before returning, so its deliberate failure diagnostic cannot
escape into the next test. The decoder still rejects malformed records.
`test_regression.py` deterministically interleaves diagnostics between stream
writes for collection, completion and failure events, including fragmented
delivery and multiline details. Generated host aggregate reports own live
qualification; a single stream write does not establish arbitrary multi-process
atomicity for records larger than a pipe's atomic-write limit.

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
   representative busy-host conditions. New pairings require separate
   qualification before admission.
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

Simultaneous reproducibility builds require distinct validated outputs and
successful comparison. Host/VM overlap remains outside scope.
