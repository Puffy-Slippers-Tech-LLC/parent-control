# System support for live time

**Superseded proposal; do not execute.** The developer now forbids upstream/native
package changes and replacement of Malcontent accounting. The recommendation
below is retained as previous design work, not an active prerequisite, permission
or delivery instruction. [Replace Main.timeLimitsManager](SystemDesign/Replace-Main.timeLimitsManager.md)
owns the current row 4 exploration using existing public inputs. The
[broker queue](Broker-Expiry-Task-Queue.md) owns its revised tasks. No task is
completed by superseding this proposal; its original source gaps remain findings.

Everything below describes the superseded proposal, including its former
prerequisite and authorization language.

Status: design recommendation; no system support, accounting change or reader
delivered. Native delivery remains a prerequisite to task 001a.

The developer authorized a separate plan to define needed system changes before
implementation. The [expiry master](Broker-Expiry-Plan.md) and its
[ordered queue](Broker-Expiry-Task-Queue.md) retain execution ownership.
[001a0 — Design system support for live time](Broker-Expiry-Tasks/001a0-live-time-support.md)
owns the design decision below. This document introduces no launcher or second
queue. Task 001a remains unfinished until an actual supported source exists.

## Problem and smallest useful change

The [source review](Broker-Expiry-Tasks/001b-live-time-reader.md#source-review-and-return-condition)
found that saved Malcontent records omit the current active interval. Shell
holds the live deadline, and the product currently exposes it through the child
extension. Repeated reads of saved records cannot replace that deadline.
The review records published package versions, not fresh installed inspection.

Recommend extending the native Malcontent accountant to include unfinished
activity and expose one account-scoped live snapshot. GNOME Shell remains the
activity observer; Malcontent combines completed and open intervals. The broker
only reads the result. This needs coordinated upstream Shell/Malcontent changes
and supported packages; it is **a proposed system change, not an existing API**.

| Candidate | Decision |
| --- | --- |
| Existing timer query or command | Rejected by the recorded review: unfinished activity is absent. Do not repeat that fallback. |
| Public export of Shell's current endpoint alone | Smaller surface, but insufficient: it is an effective, session-owner cache, can be zero while inactive, and does not supply account-wide completeness or crash recovery. A new bus wrapper cannot repair those properties. |
| Native live snapshot with native open-interval support | Selected: keeps one accountant and lets native admission, Shell and product readers share its result. Adds the missing input/recovery contract at its owner. |
| Broker accountant | Not selected: needs the same missing observation/recovery guarantees, plus a new durable ledger, native writer shutdown, history transfer and replacement/delegation of PAM and Shell calculations. It is a larger ownership change, not a reader implementation. |

The selection minimizes changed authorities, not a promised patch size. If
upstream support cannot be obtained, retain the working extension path and the
001a blocker. Do not implement a private equivalent under 001b.

## 1. Choose one accounting authority

The current [state ownership](SystemDesign/State.md#persistent-and-derived-state),
[time arithmetic](SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities)
and [expiry invariants](SystemDesign/Broker-Expiry-Locking.md#scope-and-invariants)
remain authoritative until separately scoped delivery passes.

| Responsibility | Current boundary | Selected proposed boundary |
| --- | --- | --- |
| Observe activity | GNOME Shell | Retain native observation and its current activity meaning; add ordered, session-bound delivery of real transitions and continuity information. No broker polling tracker. |
| Save/combine usage | Malcontent | Retain its store and overlap merging; extend it to hold open intervals and observation completeness atomically with completed records. No second ledger. |
| Hold unfinished use | Shell time-limit manager | Move authoritative open-interval aggregation into Malcontent; Shell retains only observer state and a revision-bound native estimate. |
| Limits and grants | AccountsService | Retain live authority, broker authorization and existing grant writes. A snapshot references the exact policy/grant values it evaluated; it is not another grant store. |
| Status/approvals | Broker and fixed helper | Retain roles, exact-child reads, approver-scoped history queries and transaction ordering. Consume validated native daily/effective operands. |
| Admission/native expiry | PAM, Malcontent library and Shell | Retain these owners; update their native calculation inputs to the same live union. No independent PAM total or broker-only correction. |
| Protect input | GNOME secure lock and current product coordination | Unchanged. Accounting delivery neither implements a scheduler nor retires any extension lock/compatibility behavior. |

Affected consumers, all requiring explicit delivery scope before edits:

- Native Shell recording, estimate refresh and expiry evaluation; native timer
  queries/command and library/PAM calculation paths. Old `RecordUsage` callers
  must remain compatible without counting an open interval twice.
- [Broker status and approvals](../broker/oh_no_parent_control/core.py):
  `GetTimeStatus` currently caps only self-status with `_native_deadline`;
  fixed child approvals use that cap, while Parent/kiosk status and kiosk
  approvals use recorded history. The proposed source can serve all identities;
  this design does not silently broaden 001b's acceptance to a consumer migration.
- [Adapter](../broker/oh_no_parent_control/adapters.py) and
  [fixed helper](../broker/oh-no-parent-control-query-usage): replace the
  extension-backed read only after 001a pins the real supported contract.
- Extension countdown, `CalculateOwnRemainingTime` inputs and
  [retained/fresh admission](SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
  including the product session-limit helper's broker status read. Parent and
  both request forms retain their existing public behavior and unavailable-state
  presentation. Cached panel values never become authority.

Native packages must agree on one live-accounting protocol before activation.
Broker startup can discover capability but cannot create it or repair native
history. Keep existing extension startup, resume and authenticated-unlock
workarounds until their separate replacement checks pass. Update the owning
State, Screen-Time, Broker and Lifecycle descriptions only with actual delivery.

## 2. Verify supported observations on both systems

The 2026-11-01 public-source review confirms these published versions; neither
VM was started. These facts do not attest installed versions, downstream patch
contents or a passing live observation on either target.

| Target | Published versions and native source baseline |
| --- | --- |
| Ubuntu 26.04 | [Malcontent 0.14.0-0ubuntu1.2](https://packages.ubuntu.com/resolute-updates/malcontent), [Shell 50.1-0ubuntu1.4](https://packages.ubuntu.com/resolute-updates/gnome-shell); [upstream 50.1](https://github.com/GNOME/gnome-shell/blob/50.1/js/misc/timeLimitsManager.js) |
| Fedora 44 | [Malcontent 0.14.0-1.fc44](https://packages.fedoraproject.org/pkgs/malcontent/malcontent/fedora-44.html), [Shell 50.6-1.fc44](https://packages.fedoraproject.org/pkgs/gnome-shell/gnome-shell/); [upstream 50.6](https://github.com/GNOME/gnome-shell/blob/50.6/js/misc/timeLimitsManager.js) |

Existing contracts and their limits:

- The official [Child timer interface](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml)
  selects the caller's account, records inclusive Unix-second intervals and
  merges overlap. Its query returns an effective estimate, not a grant-free
  daily operand or a live completeness witness. Reuse the
  [recorded credential/failure review](Broker-Expiry-Tasks/001b-live-time-reader.md#source-review-and-return-condition).
- In the reviewed Shell tags, native observation uses aggregate logind user
  activity/idle and sleep state; completed transitions feed Malcontent.
  This is not a raw keyboard/mouse activity contract. The wellbeing 03:00 day
  boundary is not the product's local-midnight daily rule. Neither a wellbeing
  total nor Shell's cached parental endpoint is a replacement daily operand.
- [logind](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html)
  supplies session/user identity, seat activity, lifecycle notifications and
  sleep coordination. Desktop clients report idle/locked hints; these are not
  authenticated evidence of protected input, nor a replayable usage history.
  Its current-state timestamps cannot reconstruct every missed transition.
- The published [Shell 50.1 ScreenTime interface](https://github.com/GNOME/gnome-shell/blob/50.1/data/dbus-interfaces/org.gnome.Shell.ScreenTime.xml)
  and [50.6 interface](https://github.com/GNOME/gnome-shell/blob/50.6/data/dbus-interfaces/org.gnome.Shell.ScreenTime.xml)
  provide break state, not a live parental balance. The internal GObject getter
  is not an extension-independent public bus contract.

The following are **requirements for upstream delivery**, not verified current
facilities. Keep native activity semantics; do not promise stronger tamper
resistance merely by moving calculations. The existing trusted-session recording
model permits same-account clients to submit usage; Unix credentials establish
account identity, not that a process is an honest compositor. Upstream must
document its observer trust/registration boundary and reject competing observer
epochs. A user-owned bus name alone is insufficient provenance.

| Observation | Proposed native requirement and present gap |
| --- | --- |
| Active use; idle entry/exit | Shell sends real native state transitions with sequence, observer epoch and account/session binding. Malcontent checks continuity; no reconstruction from periodically sampled hints. There is no supported live-edge protocol today. |
| Lock/unlock; user switch | Preserve the native inactivity predicate and qualify its transition timing against usable/locked desktops. Logind seat/session state supports identity, not proof of input protection. No additional broker interpretation of hints. |
| Suspend/resume | Native observer commits the last transition before releasing the logind delay inhibitor, then resynchronizes before publishing a valid post-wake snapshot. An expired inhibitor or missing transition means incomplete observation. |
| Concurrent sessions | Track contributing session/observer instances, union qualifying intervals once per account, and enumerate membership with change generations. A shared user bus is not a unique graphical session. Missing or unsupported contributing sessions make the account snapshot unavailable. |
| Session end and owner loss | A normal end closes the interval; an unclean end invalidates continuity unless native durable records establish the actual boundary. Neither connection loss nor a new Shell process proves when usage stopped. |

For each row, GNOME/Malcontent maintainers own the native contract and code;
Ubuntu/Fedora maintainers own supported builds. This session cannot attest their
acceptance or supply those packages. A broker accountant would still need all
these observations and could not acquire them by moving the same hints into root.

## 3. Define recovery and arithmetic before implementation

Proposed read: one bounded, read-only system-bus snapshot from Malcontent under
the exact child's fresh bus credentials, including when no child desktop is
running. No root impersonation, selected administrator or session-bus endpoint
is needed for this self-read. Existing authenticated-approver `QueryUsage`
permissions remain separate. Retain the helper's five-second call limit and
25-second shared retry budget within its 30-second process bound; authorization,
malformed data and completeness failures are terminal for that attempt.

The upstream contract must define a versioned typed reply with:

- Target UID plus native account incarnation, boot ID, service-owner epoch,
  observation generation and contributing session/observer epochs.
- Native local-day start/end, timezone/clock generation, evaluation realtime
  and monotonic microseconds, and exact live limit/grant values or a revision
  binding those values. AccountsService remains authoritative.
- Separate daily remaining seconds **excluding grants**, grant expiry in Unix
  seconds and effective remaining/endpoint; finite, nonnegative, range-checked
  numbers with declared whole-second accounting precision. Microsecond transport
  timestamps do not imply microsecond usage accuracy.
- Distinct disabled, active, inactive, exhausted and unavailable states.
  Inactive positive daily time is a paused daily balance, not a zero deadline;
  no sessions is valid only when native enumeration and usage continuity are
  complete. Unavailable carries a bounded category, never fabricated zero use.

Reads must not write checkpoints, activate an observer or award time. Signals
invalidate cached state and trigger a fresh read; they confer no entitlement.
Address replies to the observed native unique owner and reject replacement,
session/account change, expired freshness or changed policy. Validate membership
and policy generations around acquisition; reread on change within the original
budget. A daemon evaluation timestamp alone proves neither input completeness
nor current policy. The API needs an explicit maximum observation age and gap
indicator; 001a must pin their delivered values, not guess them from latency.

Arithmetic remains `D = max(0, daily_limit - union_use_today)`,
`G = max(0, issued + duration - realtime_now)`, `T = max(D, G)`.
Fixed approval stores `max(D, G) + additional` at the existing issuance time;
rest-of-day replaces the grant with the next local-midnight endpoint. An
effective endpoint alone cannot reveal D when a longer grant masks it. Until
native daily support is delivered, the existing recorded-use cap remains only
its documented cap, not proof of an exact daily balance.

For continuous activity, carry the native absolute monotonic daily endpoint;
subtract transport/retry time, never add the returned duration to receipt time.
For an inactive daily balance, any activity-generation change invalidates it
before use. A future scheduler must subscribe and revalidate; a paused balance
cannot arm an old active deadline. Grant arithmetic always reevaluates the
AccountsService epoch endpoint, including sleep/offline time. Bracket realtime
conversion with monotonic samples and reject a clock step or unprovable mapping;
monotonic timestamps expire across boot and must be resampled after resume.
Rounding is applied once to the original endpoint, never once per retry.

| Boundary | Selected recovery requirement |
| --- | --- |
| Continuous use | Native open intervals contribute through evaluation time without committing synthetic completed records. Repeated reads during an unchanged active epoch preserve the same expiry. |
| Idle, lock, switch, suspend | Close/pause daily activity at its real native boundary; grants continue. Refresh native cached admission/expiry state before evaluation on return. Existing resume/unlock workarounds remain until separately qualified. |
| Overlap | Union completed and open intervals at Malcontent, including duplicate deliveries, once per account. Never sum two Shells' independent balances. |
| Midnight/timezone/clock | Clip the union to local midnight/day endpoints, including DST; refresh at the day boundary even during uninterrupted use. Split intervals using recorded clock/day generations. If a timezone or clock change cannot be mapped from retained native records, report incomplete instead of shifting old use speculatively. Grant epoch semantics remain unchanged. |
| Approval/revoke/policy | Snapshot references exact live values; broker revalidates target, preferences and live grant around reads and before effects under its existing transaction lock. Native policy changes invalidate estimates. A shorter/cleared grant cannot erase positive D. |
| Broker restart | Requery native authority; no broker usage state or cached entitlement to restore. |
| Timer/bus restart | Restore committed native open/closed state, obtain current observer continuity and publish a new owner epoch before valid reads. Lost bus signals require snapshot resynchronization. |
| Shell crash/replacement | Reconcile the original observer's durable transitions with native membership. Do not continue its open interval through unknown downtime or reinterpret the replacement as a fresh allowance. |
| Upgrade/account replacement | Native identity generation isolates reused UIDs, sessions and old callbacks. Adopt existing completed history once; reject history that cannot be bound to the current account. No product preference ledger or implicit transfer by numeric UID alone. |

Native durability is necessary, not supplied by an export: persist a real
transition and its sequence before acknowledging it; atomically close an open
interval and merge its completed span in the **existing native store**. Replay
of the same observer/sequence is idempotent; conflicting replay refuses. Shell
must retain unacknowledged real transitions durably, with bounded storage and
explicit overflow/gap reporting. Reconnect replays those transitions before a
complete snapshot is published. Native startup must reconcile legacy writers
and open intervals without duplicate usage; old clients' overlapping records
remain merged under the documented inclusive-second convention. Native/product
interval conversion must explicitly handle that convention and qualify the
existing whole-second rounding difference, not change broker arithmetic here.

This ordering recovers acknowledged events and durable, unacknowledged events;
it cannot recover activity never observed or persisted before a crash. Such a
gap stays unavailable, not zero/exhausted or an interval charged until restart.
Current status/approval failures already refuse unavailable usage without
account writes; they cannot repair the gap. A recoverable native journal may
restore continuity. Otherwise an unresolved **delivery gate** remains: upstream
must provide trustworthy reconstruction, or the developer must explicitly
authorize the customer recovery policy for unknowable usage and its admission
consequences. This plan chooses no time award, invented charge, reset or logout
fallback. An API which merely hides the gap cannot pass 001a's reliability
requirement. The recommendation is concrete; lossless arbitrary-crash recovery
is not claimed or assumed to be solved by a journal.

## 4. Review, then scope delivery

The recommendation preserves the [customer time/approval rules](Specification.md#screen-time-setup-and-enforcement)
and [approval calculation](Specification.md#requesting-and-approving-access),
exact-child isolation and unavailable-read handling. It neither claims secure
locking from hints nor resolves native retained-unlock defects. Required
delivery gates, in order; these are proposals, not newly scheduled tasks:

1. **Native contract and authority.** The developer must separately authorize
   bounded upstream/package work and name a delivery maintainer. That maintainer
   obtains GNOME/Malcontent agreement on the snapshot, live observations,
   credential/trust boundary, account incarnation, policy coherence and crash-gap
   contract above. No upstream acceptance, public submission or system patch is
   authorized by this task. Unrecoverable-gap behavior needs the explicit product
   decision described above unless upstream supplies sufficient reconstruction.
2. **Native implementation and packages.** GNOME/Malcontent maintainers deliver
   coordinated observer/store/read/native-consumer changes; Ubuntu and Fedora
   maintainers deliver supported packages/backports with documented minimum
   versions and upgrade compatibility. A private Shell export or locally patched
   binary is not this prerequisite. No availability date or version is promised.
3. **Native lifecycle qualification.** The delivery maintainer must demonstrate
   native readers/PAM/Shell agree, bounded gaps remain unavailable, and upgrades
   preserve history. Negotiate feature/version compatibility before starting the
   new protocol; never run two authorities. If native storage changes, its native
   migration owner preserves old history and refuses unsupported downgrade.
   Rollback is permitted only with proven native compatibility; otherwise retain
   diagnostics and refuse the unsupported combination. Do not copy usage into
   the product's [preference migrations](SystemDesign/Data-Migration.md).
4. **Existing source and reader gates.** Only actual supported delivery lets
   unchanged 001a evaluate both targets. Then 001b pins that contract, implements
   its bounded reader and owns backend review, build and installed integration.
   A richer reply may need additional adapter representation; if it cannot fit
   001b's current boundary, return for explicit scope/acceptance authorization.
   Broader Parent/kiosk/native admission migrations require their own authorized
   scope; this design grants no acceptance for them. Task 002 retains all its
   original timing/identity assertions and both-target acceptance.

Product package changes later need dependency/capability gates for the delivered
native versions on both formats. Under [Lifecycle](SystemDesign/Lifecycle.md#package-activation-and-session-renewal)
and [activation](Publishing.md#package-update-activation), fixed helper code loads
next invocation, broker changes require restart, and changed Shell consumers
require an owned session renewal; external native packages must declare their
own activation needs. Do not restart unrelated desktops during configuration.
On [removal](SystemDesign/Package-Removal.md#payload-and-reversible-enforcement-cleanup),
retain current grant/limit cleanup and rollback order; native usage/history
remains native-owned and is not erased by product purge. Removing the product
must not uninstall shared native support or leave a product observer as a required
usage writer. Interrupted native delivery cannot be repaired by reinstalling the
product or silently falling back to completed-only reads.

A broker replacement remains outside this proposal. Reconsidering it would
require explicit changes to State's Malcontent ownership, Screen-Time's daily
calculation, Broker trust/transactions, Lifecycle/removal and expiry invariants;
replace/delegate every native reader/writer at one transfer point, preserve
history, and authorize new admission/recovery/consumer acceptance on both
systems. It could not pass 001a, 001b or 002 unchanged. No such boundary or
acceptance revision is requested or scheduled here.

Apply the [test scope mandate](Mandates/Test-Scope-Mandate.md): plan product
arithmetic, identity and recovery checks at existing owners and affected installed
checks on both targets. Reuse expiry, idle, suspend and admission owners; do not
create a second campaign or tests of these documents.
Future validation must include continuous-use deadline stability through latency,
separate D/G arithmetic (including grant-only and shorter-grant controls), native
inclusive-second conversion, inactivity and account-wide overlap, local midnight,
clock discontinuity, owner/account replacement, ordered replay and an actual
unrecoverable-gap refusal. Validate native PAM/Shell agreement and lifecycle on
both supported targets with the extension endpoint unavailable; installed input,
work retention and locking remain their current owners. Do not invent executable
selectors. Implementation retains core-backend review, queued package build and
installed acceptance. Planning, introspection and design review earn none of it.

Task 001a resumes with its original acceptance and session counts; it passes
only after a usable supported native source exists on both systems. No product
source, test, installation, native package or enforcement change is part of this
design task. Independent design review and document checks are recorded in the
queue result after completion; no inspection resources are required.
