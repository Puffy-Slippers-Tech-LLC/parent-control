# Replace the extension's access to Main.timeLimitsManager

Status: row 4 exploration; no replacement source or installed acceptance is
delivered. This document owns the timing-input investigation, not an accounting
replacement or expiry implementation. The [broker queue](../Broker-Expiry-Task-Queue.md)
schedules the bounded exploration and contract review.

## Problem and boundaries

An unrelated extension can crash GNOME Shell, after which GNOME may disable
extensions globally. Our extension then loses its timing bridge even when the
native desktop has recovered. Essential timing must eventually stop depending
on our extension being enabled. Surviving extension disablement is distinct from
providing secure locking while Shell itself is crashed or hung.

The current extension reads `Main.timeLimitsManager.dailyLimitTime` inside the
Shell process. Its product `NativeTime1.GetDeadline` endpoint exposes that value
to broker consumers. A standalone GJS/session service cannot access the running
Shell's objects merely by importing similar code. The reviewed ScreenTime D-Bus
interface exposes break-reminder state, not this parental deadline.

Hard constraints:

- No upstream changes, downstream native patches, new native exports or package
  replacement requirements. Use existing public interfaces on both targets.
- Retain GNOME's recording path and Malcontent's measured-usage store; no second
  durable ledger, replacement accountant, usage writer or synthetic checkpoints.
- AccountsService retains live limits/grants. Existing daily activity semantics,
  elapsed-time grants, approval arithmetic and unavailable-read behavior remain.
- No private Shell access, JavaScript evaluation, memory/file scraping of Shell
  internals, GUI scraping or extension endpoint disguised as a new service.
- No scheduler, lock-owner handover, PAM/admission rewrite, new daemon or removal
  of compatibility hooks in this exploration.

Rows 1/2 are complete in the
[current countdown design](Screen-Time.md#countdown-and-expiry-enforcement),
which retains the extension-backed timing source. Moving deadline arithmetic
did not resolve this investigation's source dependency. The
[expiry exploration](Broker-Expiry-Locking.md) separately owns row 3. It can
explore broker effects with extension-backed timing; extension-independent
broker expiry eventually needs both row 3 and row 4 delivery.

## Candidate using existing interfaces

Investigate a read-only live observer in the existing broker:

1. Read recorded usage through Malcontent's public API under the existing
   credential boundaries.
2. Observe the same public logind user activity/idle and sleep inputs used by
   native GNOME. Track the currently observed unfinished activity in memory.
3. Combine recorded and observed intervals as a union, clipped to the local day,
   rather than adding overlapping durations. Reconcile when native GNOME saves
   an interval. Native recording continues unchanged; the broker writes no usage.
4. Derive current daily remaining time and combine it with the live grant through
   broker-owned arithmetic. Publish a deadline with a clock reference for active
   use, and distinguish a paused balance from exhaustion or unavailable input.

This is a candidate composition of supported interfaces, not an existing live
balance API or a proven algorithm. Its transient tracking is additional product
logic even though it does not replace Malcontent's durable accounting. Do not
describe source review as a working extension-independent reader.

| Public source | Established input | Limitation to resolve |
| --- | --- | --- |
| logind user/session D-Bus | User state, idle hints, membership and sleep/lifecycle notifications | Current state and notifications are not replayable history; identity and missed transitions need explicit handling. |
| Malcontent `QueryUsage` | Recorded account usage intervals | The unfinished active interval is absent. Fresh history alone is not live usage. |
| Malcontent `GetEstimatedTimes` | Policy-based effective estimates and change notification | A fresh timestamp does not establish current-use completeness; repeated estimates can move expiry forward. |
| Mutter IdleMonitor D-Bus | Idle time and idle/active watches | Optional only if logind is insufficient; raw input-idle semantics must not silently replace native account activity semantics. |

Native GNOME uses user `State == active`, a false `IdleHint`, and not preparing
for sleep for its activity predicate. logind is a systemd API used by GNOME,
not a new GNOME timing endpoint. Start with those same inputs instead of inventing
an idle threshold or polling mouse/keyboard activity. Hints are useful native
accounting inputs; they are not proof that a screen lock protects input, and
moving their consumer into root does not strengthen their provenance.

Official source references: GNOME's manager in
[50.1](https://github.com/GNOME/gnome-shell/blob/50.1/js/misc/timeLimitsManager.js)
and [50.6](https://github.com/GNOME/gnome-shell/blob/50.6/js/misc/timeLimitsManager.js),
[logind](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html),
[Malcontent timer contract](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml),
and [Mutter IdleMonitor](https://github.com/GNOME/mutter/blob/50.1/data/dbus-interfaces/org.gnome.Mutter.IdleMonitor.xml).
The [recorded source review](../Broker-Expiry-Tasks/001b-live-time-reader.md#source-review-and-return-condition)
retains the rejected direct-reader findings and published package versions.
These references establish interfaces/source behavior, not installed results.

## Questions that decide feasibility

Answer these with one bounded recommendation; do not grow a general accounting
framework or promise perfect crash recovery:

- **Initial synchronization:** how are observation subscription, current state
  and recorded-history reads ordered? A broker starting halfway through active
  use must not assume that usage began at broker startup. Identify whether
  public timestamps/history establish the missing beginning.
- **Reconciliation:** how do newly recorded or overlapping native intervals
  replace the observed contribution without omission or double counting? Account
  for Malcontent's inclusive-second convention and finite precision.
- **Pauses and identity:** preserve native idle/lock/switch/sleep semantics and
  union concurrent sessions once per account. Scope observations to the actual
  account/session and invalidate on replacement; a shared user bus is not a
  unique graphical-session identity.
- **Loss and restart:** what can be reconstructed after broker, timer, logind or
  Shell owner loss? Current hints cannot recover every missed transition. If an
  interval is unknowable, state the exact unavailable condition and recovery
  policy still needed; never invent zero use, charge unknown downtime, reset
  allowance or add persistence as an implicit fix.
- **Time and policy:** preserve local-midnight clipping and daily versus grant
  operands. Revalidate on policy, clock/day and activity changes. Repeated reads
  and transport delays consume one original deadline. A grant-masked effective
  endpoint cannot be inverted into an exact daily balance.
- **Consumer fit:** identify the minimal adapter change for current native-time
  consumers and their failure paths. Do not silently migrate Parent/kiosk/PAM
  or claim that a timing observer fixes Shell resume/unlock compatibility bugs.

## Decision and delivery gate

Read [Screen time](Screen-Time.md#grant-arithmetic-and-usage-identities),
[State](State.md#persistent-and-derived-state) and
[Broker](Broker.md#runtime-hierarchy-and-trust-boundaries). Follow the existing
native reader call chain through core, adapter, helper and extension export;
the task briefs own exact reading routes. Use public research and only necessary
bounded read-only inspection. Read the VM mandate before guest work; this
document neither selects/prepares a VM nor authorizes installation or a prototype.

The result must say feasible, feasible only within an explicitly stated scope,
or blocked, with the exact unresolved boundary. A negative finding is useful;
it is not installed timing acceptance or permission to fall back to upstream
changes, native replacement or a second ledger.

Only a concrete source/observation contract with resolved arithmetic, identity,
startup and recovery decisions can support a bounded implementation proposal.
If the observer cannot fit the old helper-only reader brief, keep delivery
deferred and replace that brief with explicit finite scope before activation.
Do not let a design review automatically authorize a complete accounting engine.
Reconcile all affected timing consumers before claiming endpoint independence.

Future validation reuses existing core/adapter and installed session owners for
uninterrupted progress, overlap reconciliation, inactive return and bounded
unavailability on Ubuntu 26.04 and Fedora 44. Grant-only and shorter-grant controls
must distinguish elapsed grants from daily use. Existing lifecycle/customer
owners retain their scenarios. No new suite, duplicated failure matrix or tests
of this document are needed. The [test documentation map](../TestAutomation/README.md)
owns allocation and the [test scope mandate](../Mandates/Test-Scope-Mandate.md)
limits expansion. This exploration closes no reader, timing or enforcement task.
