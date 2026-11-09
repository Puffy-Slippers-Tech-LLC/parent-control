# Failed usage saves: open issue and investigation

Can normal concurrent usage reads prevent GNOME from saving a child's recent
activity, and how can the supported usage owner retain and retry that activity
without granting extra time or losing older intervals?

By developer decision on 2026-11-09, the delayed-approval family E2E-048
(cases **223, 224, 225, 227, 228 and 230**) and unfinished tasks **269/270**
are removed from execution scheduling and regression selection in Plans A, B
and C. This is an open issue, not an execution plan or launcher handoff.
It creates no prerequisite for remaining E2E work. Do not automatically resume
the former diagnostics or reconstruct these tasks. Reopening requires an
explicit request for this separate investigation.

Historical passes remain historical. The unresolved regression is not fixed,
and removal supplies no new pass or completed-task credit. Stable case IDs
remain reserved in the inventory as pending, with no executable bindings.
Shared countdown, profile, approval, gameplay and ordinary expiry coverage
remain under their existing owners.

## Customer impact and expected behavior

The child uses the desktop while a parent views time status or approves more
time. Those normal actions read usage; GNOME independently saves active usage.
If the read keeps the store busy at the save boundary, Malcontent can reject
the save with `Child.Error.Busy`. Recent activity may then be absent from the
saved record and the countdown may show more time than it should.

The normal read/save overlap is a plausible real-user trigger, not a measured
production frequency. The controlled reproductions deliberately increased or
held contention; they establish a mechanism without proving that it caused the
original uninstrumented failure.

A thirty-second approval should add thirty seconds to the larger current
daily/grant balance, accounting for elapsed active or away time. A failed save
must not silently erase real activity, restart the allowance or lose an older
pending interval. Legitimate allowance increases and inactive gaps must remain
correct. The [specification](Specification.md) still owns expected behavior.

## What is established

- Case 227 passed on Ubuntu 26.04 in `20261109T145508Z-77802a45`.
  The affected case 223 then failed in `20261109T150844Z-997327ad` at
  `E2E-048/daily-only-child-overlay:first-countdown`. Its earlier countdown
  was 592 seconds, then 593 about 110 seconds later after a thirty-second
  request. The broker calculated a 519-second grant; native and timer operands
  later reported 600. Its exact cause remains unproven without matching timer
  traffic. Do not recreate expired historical evidence.
- Stress experiments using genuine QueryUsage requests produced matched
  native RecordUsage/Busy replies and missing saved activity. A reader's Busy
  error alone does not demonstrate a failed write.
- The narrower genuine thirty-second approval experiment allowed the native
  estimate to succeed, then deliberately held a real QueryUsage transaction
  while the original native save was dispatched once. No fake usage interval,
  save response, caller or authorization was substituted.
- In that experiment, saved usage initially ended at 1794248824. Native
  write **284/reply 61** failed Busy for the interval ending 1794248961,
  leaving 137 seconds unsaved. Successful estimates **281/reply 53** and
  **282/reply 54** preceded it. The public countdown went from 417 to 465
  over about 57.53 seconds; after adding thirty seconds it should have been
  about 389.5. The excess was about 75.5 seconds.
- A diagnostic change/restoration of an unused schedule triggered genuine
  successful saves **297/reply 47** and **312/reply 79**. Saved usage became
  complete and the deadline corrected by about 76 seconds. The original
  daily allowance, schedule and grant were verified preserved/restored.
  This establishes recovery in that history, not a supported production fix.
- Natural later closing saves recovered some earlier failed active
  checkpoints. Another controlled history left a **47-second older closing
  interval missing** despite later successful approval and lock saves.
  A later successful save therefore does not guarantee complete recovery.
- Both the native manager and extension share the GNOME Shell process.
  Sender/PID alone cannot distinguish their estimate reads; destination,
  original invocation and matched reply must also be checked.

The latest matched reproduction used
`onpc-daily-delayed-approval-diagnosis-7o37tb_f` and
`onpc-daily-approval-followup-ynmihahf` under the ordinary privileged allocations
root. Existing observations and timer traces follow normal retention; their
continued availability is not an E2E prerequisite. Owned probes were joined,
temporary instrumentation removed, ordinary services restored and the VM
stopped with baseline restoration. No live process or guest is inherited.

## Ownership and limits of proposed fixes

Malcontent owns measured usage; GNOME owns the native activity writer.
The product reads their state and combines it with the approved grant; see
[screen-time ownership](SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities).
Installed-source inspection found that GNOME logs a failed usage save without
immediately retrying it. Completed-interval tracking and current-interval
checkpoints can recover differently; a newer successful checkpoint must not be
assumed to acknowledge every earlier interval.

Malcontent 0.14.0 uses an in-process open-store table to report Busy.
This is not a disk-full finding or evidence that a filesystem lock would
reproduce the same condition. The deliberately held transaction was diagnostic
instrumentation, not ordinary production behavior.

A resilient supported owner could retain exact unsaved intervals until
acknowledged, retry temporary contention asynchronously, and preserve older
pending intervals when new activity arrives. Briefly queuing competing store
operations could avoid Busy failures at the service boundary. These are design
candidates, not implemented or validated solutions. Remaining-time accounting
must include genuinely pending activity without double-counting it after save.

Product-side read serialization cannot serialize GNOME's independent writer.
Omitting a redundant timer read or unchanged AppFilter write may reduce
contention but has not established correctness. Reasserting the identical grant
did not trigger recovery. A schedule pulse triggered saves in some histories,
but could not certify recovery of older missing intervals. Panel clamping,
fabricated usage and private Shell-state changes are not established fixes.

## Questions left open

The investigation has not established the original failure's exact ordering,
the frequency of natural contention, or a maintained public route that reliably
preserves all pending native usage. It remains to determine whether the
supported correction belongs in GNOME, Malcontent, or an available upstream
version, and how it handles shutdown, inactive gaps and multiple missing
intervals.

One unrun diagnostic idea compared dispatching the same genuine pending native
save during a short real transaction versus immediately after it closes.
That could distinguish the store boundary, but would not itself establish a
production serialization mechanism. Former caller-owned /tmp scripts are
unvalidated disposable aids, not maintained prerequisites or instructions to
the next E2E launcher.

No product fix or production recovery protocol was accepted. Reopening this
issue should begin from these findings and current supported sources rather
than repeating the completed contention and schedule-pulse experiments.

## Preserved scenarios outside E2E execution

The former family observed a genuine forty-five-second decision at an
authentication prompt, followed by a thirty-second approval and an immediate
second thirty-second request after cooldown. Both used soft apps excluded.
Daily use continues on the child desktop and pauses while away at the station;
grant time elapses on both surfaces. Each comparison uses current balances,
not the estimate first displayed before the wait.

| Former case / task | Situation and finite preparation | Preserved observation |
| --- | --- | --- |
| 223 / 265 | Daily-only child overlay: ten daily minutes, no grant; Jamie approves. | Active use consumes daily time during the prompt; both additions use current balances. Original regression unresolved. |
| 224 / 266 | Daily-only kiosk: ten daily minutes, no grant; Jamie approves. | Daily time pauses while away; the new grant starts at approval rather than at the old estimate. Historical pass only. |
| 225 / 267 | Grant-only child overlay: zero daily time, genuine twenty-minute grant; Jamie approves. | The original grant continues elapsing through the prompt and both additions. Historical pass only. |
| 227 / 269 | Daily-dominant child overlay: daily zero, approve twenty minutes, then save forty daily minutes while enabled; Sam approves. | Daily exceeds the original grant at the first prompt; the first addition may legitimately make the replacement grant dominant. Historical case pass, unfinished task removed. |
| 228 / 270 | Daily-dominant kiosk with the same twenty/forty-minute preparation; Sam approves. | Daily pauses away while the grant elapses; check both recalculations. Complete journey was never implemented or accepted. |
| 230 / 272 | Grant-dominant kiosk: thirty daily minutes, then twenty additional minutes; Jamie approves. | Grant remains dominant and elapses at the station. Historical pass only. |

The former recipe required at least 300 usable seconds at each prompt, a
first-prompt dominance gap greater than 90 seconds when both operands were
positive, and at least 300 seconds of the smaller balance. Fixtures and
observers preceded the setup grant. Current daily/grant balances after the
first approval also supplied the second request's starting operands.
Comparisons accounted for navigation, authentication, confirmation and display
precision, with no artificial settling wait or grant reset. These finite
histories preserve the question; they schedule no tests. Former removed
combination IDs 226 and 229 remain reserved and must not be reused.
