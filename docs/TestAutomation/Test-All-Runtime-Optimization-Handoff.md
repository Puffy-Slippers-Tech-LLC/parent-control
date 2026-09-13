# Handoff: reduce `make test-all` VM verification overhead

Status: the earlier read-lease implementation and qualification are complete.
The new [guest-preparation change](#guest-preparation-implementation) is awaiting
live qualification on a newly prepared baseline. The earlier final `make test-all`
passed all 15 categories in 36.3 minutes. This is approximately 35% below the
historical 55.5-minute run; the half-time target was not reached. The original
request and acceptance scope follow the current results below. This handoff does
not replace another session's roadmap continuation.

The user subsequently authorized two aggregate modes: `make test-all` skips
backing-byte scans for development; `make test-all-verify` retains the fully
verified behavior measured below. Both keep ownership, read leases, snapshot and
guest checks, restoration, and cleanup. Reports record the policy; fast results
are not retrospectively upgraded by a later audit. See [the current command
contract](../../tests/README.md#all-established-regressions).

## Implementation results

The new attempt-local Linux read-lease proof preserves every validation gate,
with full hashes at acquisition, the first existing check after startup and
after restoration. Healthy
proofs end before VM disk transitions; no cached digest crosses those transitions.
It does not change the
accepted baseline, source/asset verification, VM topology, resource admission or
scheduler concurrency. Unsupported environments retain full reads. See the
[owning contract](../../tests/e2e/README.md#backing-file-verification-within-an-attempt)
and [kernel/refusal regressions](../../tests/unit/test_backing_verification_cleanup_safety.py).
Release also now preserves an active controller's command-lock reference when
a concurrent lease sharing its adapter is refused.

The instrumented unoptimized E2E invocation passed all four outcome domains and
completed lease cleanup. Its private invocation reports are in
`/tmp/onpc-e2e-evidence-q_aut51t`, its attempt reports in
`/tmp/onpc-e2e-evidence-j82sgixk`, and raw worker artifacts in
`/tmp/onpc-graphical-smoke-pdomrb1f`. Artifacts were freshly built and verified at
`/tmp/onpc-test-artifacts-ohpis2qj`; source SHA-256 was
`482204f1e0d5751f2a4fa8e28c8d4bf27368da722246cbf0eee921ed5b8447ec`.

| Instrumented baseline | Measured value |
| --- | ---: |
| Complete controller invocation, report timestamps | 1456.501 s |
| Preparation | 386.250 s |
| Test stage, including nested checks | 663.816 s |
| Cleanup | 69.421 s |
| Finalization, outside the test timer | 336.996 s |
| Backing verification | 19 calls; 1276.584 s |
| Backing bytes read | 780,044,271,616 bytes |

The controller invocation excludes the launcher's separately reported 9.57-second
safety prerequisite run. One backing file is 41,054,961,664 bytes; the top image
is writable and is excluded from these byte totals. All 19 calls used full reads,
including five finalization calls after restoration. No cache flush was performed,
and other host applications remained running; this is not a controlled cold-cache
benchmark. No other project suite or VM attempt ran concurrently.

Focused checks passed: 163 cleanup/kernel/maintenance tests and 724 existing
baseline, provenance, recording, graphical and VT6 tests. The new kernel tests
use synchronous nonblocking conflicts and actual file leases, with no sleeps,
background writers or dependence on signal delivery. They exercise same-size
mutations/restored bytes, writable mappings, partial acquisition, replacement,
links, state/snapshot changes, stale proofs, lost ownership and cleanup errors.
The final callback/cleanup/provenance selection passed 631 tests. The live
optimized results and completed aggregate comparison follow.

The ready E2E passed all four outcome domains with completed lease cleanup.
Fresh verified artifacts are at `/tmp/onpc-test-artifacts-rus096zz`; source
SHA-256 is `32076a135fb681918d8c413b75da91b8d72bc4aa33d0e4567383e85086b70ee3`.
Private invocation reports are at `/tmp/onpc-e2e-evidence-7046w63f`, attempt
reports at `/tmp/onpc-e2e-evidence-_s355whd`, and raw worker artifacts at
`/tmp/onpc-graphical-smoke-w2hdsfwt`.

| Comparable ready E2E | Unoptimized | Optimized |
| --- | ---: | ---: |
| Controller invocation, report timestamps | 1456.501 s | 227.170 s |
| Preparation | 386.250 s | 106.745 s |
| Test stage, including nested checks | 663.816 s | 48.827 s |
| Cleanup | 69.421 s | 70.482 s |
| Finalization | 336.996 s | 1.093 s |
| Backing verification calls | 19 | 19 |
| Backing verification time | 1276.584 s | 136.216 s |
| Backing bytes read | 780,044,271,616 | 82,109,923,328 |

Controller wall time fell 84.4%; backing bytes fell 89.5%. Both timings exclude
the separately reported launcher prerequisites (9.57 s before, 9.92 s after).
All gates remain: 17 checks reused valid proofs and two read every backing byte.
No cache flush or controlled cold-cache comparison was performed; individual
full audits still took approximately 67–69 seconds. The later host sample had
20.3 GB available memory, 5.9 GB swap in use and load averages 1.78/2.31/2.25;
ordinary desktop applications remained running. No other project suite or VM
attempt ran concurrently.

Live `check_graphical_vt6_authentication` also passed at the same source identity,
in 484.530 seconds, with completed cleanup and source/host preservation. Its
result is `/tmp/onpc-graphical-smoke-v1gfw0y2/result.json`; qualification evidence
is `/tmp/onpc-e2e-evidence-fz7hd26r`. It retained 19 backing checks, reading
123,164,884,992 bytes in 206.014 seconds: acquisition, the first active-VM gate,
and restoration each required a full audit. The subsequent recipient and
password authorization checks reused the valid proof. This is authenticated
VT6 shell qualification only; it does not promote pending E2E scenarios to
ordinary acceptance. Existing shutdown deadlines were unchanged.

The first optimized live attempt correctly failed acceptance with
`guard:backing-lease-broken`, despite passing all graphical journey observations.
Normal QEMU startup can request a transient writable backing handle, invalidating
an attempt-long read lease. The failed invocation is preserved at
`/tmp/onpc-e2e-evidence-8a1ppto9`, attempt
`/tmp/onpc-e2e-evidence-ikwqqnle`, raw worker
`/tmp/onpc-graphical-smoke-wrot6_pa`; its failure must never be overwritten by a
later pass. The implementation now retires healthy proofs before startup/shutdown
and requires a new full audit afterward. Focused transition/recovery checks pass
316 tests. The maintained recovery route now permits auditing an exactly restored
powered-off guest without issuing any VM mutations; all other identities and the
original failed outcome remain protected.

That guarded recovery passed in 69.439 seconds, including a fresh
41,054,961,664-byte audit. Its runner result is at
`/tmp/onpc-graphical-recovery-yjhocg33/result.json`; the journal is complete and
the pinned guest is off. Common checks then passed 8,164 unit tests, 852 isolated
safety prerequisites (including the final two cleanup/ownership regressions),
three subtests and 134 private-D-Bus component tests. The final aggregate below
includes the complete unit suite with those last two regressions included.

A second attempt preserved backing integrity and completed restoration, but an
added full hash inside the power callback delayed serial attachment by 69 seconds
and missed the login prompt. Invocation `/tmp/onpc-e2e-evidence-qou9773j`, attempt
`/tmp/onpc-e2e-evidence-tqz0pjeu` and raw worker
`/tmp/onpc-graphical-smoke-unod3yh9` retain that failed result. Startup now acquires
an **unverified** new lease without hashing in the callback. Its first existing
validation gate must perform the full read; no prior digest crosses startup.
This preserves the established serial attachment and authorization ordering.

Ownership is checked before normal preparation, restoration and journal writes;
lost-lock regressions verify that refusal precedes any of those mutations.

## Final aggregate qualification

The [final aggregate report](Evidence/test-all-runs/20260913T033140Z-763bfa9c/report.md)
and [category results](Evidence/test-all-runs/20260913T033140Z-763bfa9c/progress.json)
record exit status 0, all 15 categories passed and 9,546/9,546 counted executions
or checks. These include 852 isolated cleanup-safety prerequisites, 8,166 unit
tests, 134 private-D-Bus component tests, 142 UI tests, all 240 installed-system
executions and `E2E-001/gdm-observation`. Both VM attempts passed product,
infrastructure, collection and cleanup outcomes. Final VM status was off
(`state=5`, `id=-1`), and both attempt reports record completed lease cleanup.
All commands ran unattended through the approved launchers.

| Aggregate work | Historical run | Final run |
| --- | ---: | ---: |
| Complete wall time, reported to 0.1 minute | 55.5 min | 36.3 min |
| Host branches, wall time | 806.339 s | 782.674 s |
| Host categories, summed execution | 982.357 s | 959.999 s |
| Publishing | 344.711 s | 331.028 s |
| Two artifact builds and comparison | 12.416 s | 12.561 s |
| Installed-system category | 720.898 s | 767.695 s |
| Ready E2E category | 1375.885 s | 255.939 s |

The overall reduction is approximately 19.2 minutes (34.6%); the result remains
8.6 minutes above half the historical wall time. Installed-system time increased
in this run, while the E2E category fell by 81.4%. The aggregate category timers
include launcher overhead; they are not the standalone controller timings above.
There were no concurrency or resource-budget changes to pursue the remaining
target. Host branches still admitted at most two categories, and all VM work
remained serial.

The final run spent 8.098 seconds in serial-category resource admission: 2.045
seconds for artifacts, 6.046 seconds for E2E and negligible time for publishing
and installed-system admission. Host queue delays are already included in the
782.674-second branch wall time and must not be summed as additional wall time.
At launch the host had approximately 23.2 GB available RAM; the final E2E
admission sample recorded 21.65 GB. No caches were flushed, and unrelated host
applications remained running. Full backing audits took approximately 73–75
seconds, compared with 67–69 seconds during standalone qualification. These
are observed runs under ordinary host load, not a controlled cold-cache benchmark.

Fresh artifacts were built at `/tmp/onpc-test-artifacts-wvkhhx26` and
`/tmp/onpc-test-artifacts-_zs3p9yl`, verified and compared before VM execution.
The aggregate input SHA-256 is
`28b72152160cccd556ee7283bdfd030154a43fd970bc603235c952dd1c2661f6`;
the package and VM provenance source SHA-256 is
`781e8c024122572a10597b87cd317001bfd6a30f3512fa4dd4c310fdbde079e4`.
These identify the stable inputs used throughout this run. Only these completion
notes were updated afterward; the qualified runtime code is unchanged.

Installed-system evidence is at `/tmp/onpc-system-cnixte01/evidence/result.json`.
Its two mandatory full audits read 82,109,923,328 bytes in 147.037 seconds.
E2E invocation evidence is at `/tmp/onpc-e2e-evidence-924gxiot`, attempt evidence
at `/tmp/onpc-e2e-evidence-qx1d7ppg`, and raw worker evidence at
`/tmp/onpc-graphical-smoke-ar7lye6_`. It retained all 19 verification gates:
two full audits and 17 valid proof reuses, 82,109,923,328 bytes read, 150.978
verification seconds and zero verification failures. Its measured preparation
was 114.947 seconds, test stage 51.269 seconds, cleanup 76.909 seconds and
finalization 1.032 seconds. No pending scenario was promoted.

The [earlier aggregate attempt](Evidence/test-all-runs/20260913T024933Z-4137da6e/report.md)
is preserved as incomplete. It passed 13 categories, then waited below the
unchanged 20.39 GB VM admission threshold. On resumption its process was no
longer present and it had no final result. Because the maintained runner has no
checkpoint-resume option, the final qualification above reran the entire
aggregate; earlier category results were not combined into that pass.

## Guest preparation implementation

`make prepare-vm` and the retained `make prep-vm` alias delegate to
`setup.sh --prepare-vm`, inside the product-free guest. Preparation installs
the single pinned inventory in `tests/integration/guest_test_dependencies.py`,
including OpenSSH/pytest and OpenLDAP/SSSD tools. Repeats verify configured
versions without APT transactions. Archive normalization also moves here.
LDAP/SSSD remain unconfigured and disabled for automatic startup; unrelated
directory configuration is refused. The test later uses public
`dpkg-reconfigure` and LDAP/NSS interfaces to create fresh remote identities.
Per-attempt credentials and actual product installation remain runtime work.

Shared bootstrap now uses two sequential libguestfs appliances instead of three,
eliminating its package-install/`virt-customize` invocation. It writes the
attempt's public key with OpenSSH's documented `authorized_keys` interface,
preserves existing keys, rejects unsafe paths, then syncs/closes and independently
reopens read-only to verify key/marker bytes, ownership/modes and the server key.
All backing audits, snapshot guards, reboots and acceptance checks remain.
This removes repeated work; elapsed savings have not yet been measured.

The [owning contract](../../tests/integration/Environment.md) documents schema 2
and its exact dependency inventory. Offline inspection verifies actual package
status, not only the marker. Earlier account-only snapshots are intentionally
incompatible. Lease acquisition rejects a changed preparation digest before
backing audits, journal writes or VM mutations. Existing `--prepare-host`
preserves the accepted snapshot; no
controller state, snapshot, VM or host service was changed in this implementation.
A new prepared baseline requires deliberate maintenance/acceptance, not removal
of the old journal or bypass of its guards. Do not run guest preparation on this
development host. No owned VM attempt or background command remains afterward.

Focused verification covers first/repeat preparation, failed prerequisites,
configuration preservation, malformed/missing packages, old markers, bootstrap
readback failures, unsafe key paths, selected-input provenance, remote fixture
composition, both Make aliases and E2E cleanup composition. Before live
acceptance, qualify guest preparation/repeat, real SSH and LDAP, complete
installed-system selection and ready E2E on the new baseline; retain first
failures and compare stage timings. Historical results below qualify only their
recorded inputs. The next work is baseline activation and live qualification;
keep Astra for the unresolved ownership/activation boundary.

The final focused selection passed 537 tests. Isolated cleanup/ownership
prerequisites passed 853 tests and three subtests, including the new stale
preparation refusal. Final `make check` passed 8,193 unit tests, its isolated
853 safety tests/three subtests and 134 private-D-Bus component tests, plus
source/traceability checks. Document links and `git diff --check` passed.
No live VM qualification or new end-to-end timing is claimed.

## Follow-up investigation: manual VM operations versus runner time

Read-only review of the final aggregate above, its category streams and retained
guest JUnit confirms that the remaining long category times are not long reboot
sleeps. No new VM attempt or runtime change was made for this investigation.
The inspected pinned domain uses KVM, host-passthrough CPU, six vCPUs and virtio
disk/network devices; `isolated_xml` retains those settings.

| Installed-system work in the final run | Seconds |
| --- | ---: |
| Initial backing audit | 74.018 |
| Remaining preparation | 2.375 |
| Offline bootstrap, startup, readiness and input transfer | 66.119 |
| Product package installation | 50.603 |
| Installation reboot to guarded SSH readiness | 13.508 |
| Second reboot for the GDM expiry fixture | 38.024 |
| Tests and graphical fixture preparation | 398.079 |
| Collection | 4.164 |
| Cleanup, including the 73.020-second final backing audit | 107.664 |

These stage values exclude some launcher/controller overhead; the category's
complete duration remains 767.695 seconds. Installation plus its first reboot
took 64.111 seconds. The next installed-package assertion took 31.951 seconds,
including any remaining systemd startup wait and package/service checks; do not
attribute that whole assertion to boot without finer measurements.

`Transport._probe_ready` and DHCP discovery use 500 ms libvirt timer events;
shutdown observes lifecycle events. Their 180/300/330-second limits are failure
ceilings, not mandatory delays. `system_guest.wait_for_boot` waits for systemd
startup completion and then checks product dependencies. Shorter ceilings do not
speed successful readiness. The second reboot establishes the real GDM/PAM
expiry scenario and cannot be removed while claiming the same coverage.

Guest JUnit identifies substantive work inside the test total: remote-account
qualification took 46.279 seconds, four native enforcement cases 11.790–16.068 seconds
each, installed expiry 24.162 seconds, and graphical expiry 64.756 seconds.
The requester-disconnect/recovery case took 18.217 seconds and deliberately lets
the real request interval elapse. Do not replace real time or skip assertions to
make these cases faster. The 240 installed executions already share one attempt;
the separate ready E2E requires a product-free starting state.

The remaining opportunities, in order of implementation risk:

1. **Prepare stable test dependencies once.** `system_runner.bootstrap` installs
   pinned OpenSSH/pytest on each restored guest; remote-account provisioning
   installs its LDAP/SSSD packages during the test. A deliberately revised
   product-free baseline could contain these test tools or verified package
   payloads. Preserve per-attempt credentials, run markers, fixture setup, exact
   version checks and the real product install/reboot. Put preparation behind
   `setup.sh`, with explicit baseline acceptance and offline/network-failure
   coverage. Installing LDAP/SSSD earlier can affect NSS and services, so package
   availability alone is not equivalent fixture state. The measured bootstrap
   and remote-case totals include other work and are upper bounds, not promised
   savings. Do not recapture the current accepted baseline during an ordinary run.
2. **Consolidate compatible offline operations.** Bootstrap opens a libguestfs
   appliance to edit configuration, invokes `virt-customize`, then opens another
   appliance to read the host key. Upstream recommends
   [minimizing appliance launches](https://libguestfs.org/guestfs-performance.1.html#REDUCING-THE-NUMBER-OF-TIMES-THE-APPLIANCE-IS-LAUNCHED);
   [virt-customize](https://libguestfs.org/virt-customize.1.html) supports ordered
   customization commands. Measure these substeps before changing them, retain
   independent post-write validation, and close every disk handle before boot
   or restoration. Savings belong to the existing bootstrap budget, not an
   additional budget to add to item 1.
3. **Treat further backing-audit reduction as a separate design.** Four full
   41,054,961,664-byte reads across the two categories cost approximately 298
   seconds. Linux
   [fs-verity](https://cdn.kernel.org/doc/html/latest/filesystems/fsverity.html)
   provides immutable files, constant-time digest retrieval and verified reads.
   It is a supported research candidate, not a qualified replacement: its
   digest differs from ordinary SHA-256, unread corruption is detected on later
   access rather than by an eager whole-file audit, and QEMU startup's transient
   writable backing opens need compatibility verification. Preserve full audits
   unless an accepted replacement proves the required integrity and recovery
   guarantees. Never apply it to the writable top image.

Even eliminating all four full-audit durations would save only about five of
the current 17.1 VM-category minutes, or 14% of the 36.3-minute aggregate.
Another tenfold reduction of those categories is not supported by these
measurements. The historical order-scale repeated-read bottleneck was already
addressed by the implementation above. Resource admission is separate: the
earlier incomplete run waited for memory headroom, while the final run spent
only 8.098 seconds waiting for serial-category admission. Preserve its resource
reserve rather than labeling queued time as slow guest boot.

## Objective and constraints

Aim toward approximately half the observed 55.5-minute aggregate runtime, with
reliable results and absence of conflicts taking priority over speed. There is
one shared test VM. Preserve desktop breathing room and existing CPU, RAM, swap
and I/O admission gates. Half-time is a target, not a demonstrated feasible result.

Scope: this client checkout and its maintained test tooling. Use only approved
launchers and the pinned VM controller. Preserve other sessions' uncommitted
changes, logs, generated evidence and accepted baseline. No portal changes,
extra guests, new snapshots/overlays/clones, or concurrent VM attempts. New setup
requirements belong behind `setup.sh`; test commands must not install them.

The ownership boundary and acceptance checks are now implemented and qualified.
For follow-up work, reassess model and effort using the
[implementation workflow](Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff):
Sol/high for settled implementation, Astra for newly unresolved ownership or
concurrency questions. Do not spawn agents by default.

## Original evidence and implementation

The [completed aggregate report](Evidence/test-all-runs/20260912T234802Z-d0cea2e3/report.md)
and adjacent [category timings](Evidence/test-all-runs/20260912T234802Z-d0cea2e3/progress.json)
record all 15 categories passing, including 240 installed-system executions and
the sole ready E2E variant, `E2E-001/gdm-observation`.

| Work | Observed duration |
| --- | ---: |
| Host branches, wall time | 806.339 s |
| Host categories, summed execution | 982.357 s |
| Publishing | 344.711 s |
| Two artifact builds and comparison | 12.416 s |
| Installed-system | 720.898 s |
| Ready E2E | 1375.885 s |

The 176.018-second difference is measured host overlap, not a controlled serial
versus parallel benchmark. VM categories alone total approximately 35 minutes;
merely widening host overlap cannot reach a 28-minute total with these durations.
Account separately for resource waits, collection and controller work.

The [first implementation](Test-All-Parallelism-Design.md#implemented-first-scope)
limits host work to two categories: UI plus sequential smaller suites. Publishing,
artifact builds and all VM attempts remain serial. Installed-system functional
phases already share one installation. The ready E2E case needs a product-free
guest; it cannot inherit the installed-system guest state. Pending journeys are
not available work to combine.

Later dashboard changes add actual branch assignments, simultaneous refreshes,
queue reasons and a saved branch summary. They passed 8 cleanup-safety tests plus
146 focused dashboard/scheduler/launcher tests. The full aggregate predates those
display edits. This is a dirty working tree, not a pinned commit; fresh artifacts
must match the final current inputs. No owned command is still running from this
session. The old run completed cleanup; inspect current VM ownership before use,
since another session may have acquired it.

## Original bottleneck and investigation scope

Read [system architecture](../System-Design.md), then these owning modules:

- [provenance.py](../../tests/e2e/provenance.py): `VerifiedInputs.__init__`,
  `recheck`, `contract`, `recheck_contract`, `validate`, and `baseline_inputs`.
  Rechecks already measure source/assets/baseline separately.
- [prepare_host.py](../../tests/integration/prepare_host.py):
  `Capture.verify_snapshot`, `revalidate`, `disk_snapshot`, and `digest`.
  Verification rehashes **every backing-chain file after the writable top image**
  (`chain[1:]`). It checks the top image's retained internal snapshot metadata;
  normal active-image writes are expected. Do not treat the whole chain as immutable.
- [system_runner.py](../../tests/integration/system_runner.py): `Lease` acquisition,
  restoration, finalization and recovery. It also verifies the snapshot.
- [execution.py](../../tests/e2e/execution.py),
  [leased_recording.py](../../tests/e2e/leased_recording.py), and
  [recording.py](../../tests/e2e/recording.py): nested preparation, startup and
  acceptance calls. `ScenarioRecorder.validate` invokes full validation twice,
  bracketing the saved acceptance report. These calls protect different boundaries.
- [Controller-owned provenance contract](../../tests/e2e/README.md#controller-owned-provenance):
  earlier VT6 qualification measured 69.027 seconds in baseline verification
  versus 0.091 seconds in source capture. That is historical diagnostic evidence,
  not per-call profiling of the newer aggregate. Full checks remain required
  until an equivalent replacement is verified.

Working hypothesis: repeated backing-file reads dominate the E2E runtime.
The aggregate preparation includes a 65.951-second baseline check, but current
evidence does not assign every second of the 1375.885-second category to hashing.
Measure the current call count, nesting, bytes read and wall time before claiming
recoverable minutes. Include finalization outside the scenario's test timer.

## Implementation and acceptance

1. Add bounded timing/count evidence around the existing verification path.
   Reuse private runner artifacts and fixed event fields; export no accounts,
   credentials, private paths or raw exception text. Establish a comparable
   current-input E2E baseline without launching another aggregate unnecessarily.
2. Establish which files and metadata can change, by whom, and when. Investigate
   a supported way to enforce backing-file immutability or safely consolidate
   redundant reads within a proven validation boundary. A lease, root ownership,
   pinned descriptor, unchanged size/mtime, or cached successful digest alone
   does not prove unchanged bytes. The attempt-local kernel proof in the current
   implementation results now owns the replacement decision.
3. Implement the smallest proven optimization. Preserve snapshot/durable-state
   reconciliation, source/asset checks, startup authorization, evidence checks
   around acceptance writes, restoration verification and failure latching.
   Do not replace full byte verification with metadata-only caching or simply
   delete repeated calls. Unsupported environments must retain full verification
   or refuse safely. Do not weaken a gate to meet a timing target.
4. Cover backing-byte mutation (including same-size writes), replacement,
   symlinks/hardlinks, chain and snapshot changes, stale/cross-attempt proof reuse,
   lost/replaced leases, failure followed by restored bytes, interruption and
   cleanup errors. Retain the first failure and owned-only process cleanup.
   Exercise existing consumers, including VT6 authorization, without silently
   promoting pending scenarios to ordinary acceptance.
5. Run focused regressions, then the ready E2E with freshly built, verified
   artifacts through `tools/run-tests e2e`. Reconcile its four outcome domains
   and completed lease cleanup. Finish with `make test-all` after inputs are
   stable. Compare complete wall time, verification calls/bytes, preparation,
   functional work, finalization, cleanup and resource waits under comparable
   load; report cache conditions and any remaining shortfall honestly.

First cleanup-safety command, before affected host-integrated execution:

```sh
tools/run-unit-tests 'tests/unit/test_prepare_host_cleanup_safety.py' 'tests/unit/test_system_runner_cleanup_safety.py' 'tests/unit/test_e2e_execution_cleanup_safety.py' 'tests/unit/test_e2e_leased_recording_cleanup_safety.py' -q
```

Then select affected provenance, baseline, recording and graphical regressions
with the same validated launcher. Follow the
[qualification policy](Implementation-Workflow.md#verify-at-the-right-scope);
changes to graphical/cleanup transport
require their specific live qualification. Update the owning provenance contract
and [reuse map](Reuse-Map.md) only for behavior actually implemented and proven.
Keep further findings in this handoff and generated reports rather than creating
one-off investigation documents. UI/build overlap is a secondary, separately
qualified opportunity if measurements still justify it after this bottleneck.
