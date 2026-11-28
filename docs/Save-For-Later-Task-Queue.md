# Save approved time for later task queue

The [master plan](Save-For-Later.md) owns the next-task pointer. Each row owns
one deliverable and its scoped acceptance. Estimates are per task and include
its checks, excluding queue waits. Baseline means the settled design and its
recorded native qualification.

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | Define how requests and results travel between the app and broker | Baseline | Additive method signatures, status, errors, and client compatibility | Done: [wire contract](Save-For-Later-Design.md#wire-contract) reviewed |
| [x] | 002 | Store saved time securely for each child | 001 | Private versioned records, account binding, revisions, and JSON migration | Done: `grant_store.py` and grant migration pass; independent review on Opus 5.5 xhigh (developer-authorized) resolved |
| [x] | 003 | Track what can be paused without changing immediate approvals | 002 | Balance arithmetic, grant classification, and immediate approval recording | Done. Focused host checks, queued package builds, and independent backend review passed. |
| [x] | 004 | Keep saved time through upgrades and clear it on removal | 002 | DEB/RPM package hooks, state retention and cleanup, and activation | Done. Host checks, queued package builds, and independent backend review passed. |
| [x] | 005 | Verify who can control the timer and capture time at lock | 001 | Caller/session binding and bounded lock-and-usage capture | Done. Host checks, queued package builds, and independent backend review passed. |
| [x] | 006 | Pause the timer and preserve the remaining approved time | 003, 005 | Shared pause transaction, fault recovery, and expiry policy on session entry | Done. 388 host checks, queued package builds, and independent backend review passed. |
| [x] | 007 | Start saved time once with the approved app access | 003, 005 | Shared redemption transaction and roll-forward recovery | Done. 447 focused host checks, queued package builds, and independent backend review passed. |
| [x] | 008 | Let a parent approve time for later | 006 | Mode-bound authentication, durable approval, and optional pause | Done. 766 focused host checks, queued package builds, and independent backend review passed. |
| [x] | 009 | Recover interrupted transfers and clear withdrawn time | 006, 007, 008 | Recovery triggers and serialization, revoke, and control-toggle invalidation | Done. 727 scoped host checks, queued package builds, and independent backend review passed. |
| [x] | 010 | Make saved time and timer actions available to the apps | 004, 009 | Broker dispatch, consistent status, and frontend client transport | Done. Host checks, queued DEB and RPM builds, and independent backend review passed. |
| [x] | 025 | Refresh the child countdown while the overlay stays open | 001 | Overlay-to-panel refresh request bound to the started overlay process | Done. Focused countdown and nested Shell checks, queued DEB and RPM builds, and fixture cleanup passed. |
| [x] | 011 | Build the request and approved-time tabs | 001 | Shared layout, menu, Approved time states, and lock dialog | Done. Focused host checks and queued DEB/RPM builds passed. |
| [x] | 012 | Connect both request screens to the timer actions | 010, 011, 025 | Request form state and actions, success routes, and the countdown refresh call | Done. Request UI and client checks, queued DEB/RPM builds, and fixture cleanup passed. |
| [x] | 013 | Show saved time in Parent and let parents revoke it | 010 | Parent balance display, availability, and saved-only revoke | Done. Parent UI and client checks, queued DEB and RPM builds, and fixture cleanup passed. |
| [x] | 014 | Report saved-time operations without personal information | 010 | Structured event catalogue, operation outcomes, and field validation | Done. Host diagnostics and D-Bus checks, queued package builds, and independent review passed. |
| [x] | 015 | Check that removal preserves saved time only if it is aborted | 010 | Installed removal, rollback, retry, reinstall, and purge engineering histories | Done. Installed checks passed on all three targets, including both Fedora rollback histories. Host fixture checks passed. |
| [x] | 016 | Check that an upgrade preserves saved time | 010 | Installed broker restart and package update with saved time and recovery state | Done. Both installed upgrade histories passed on all three targets. |
| [x] | 026 | Let children sign in remotely when they have time | 010 | Installed Fedora child SSH admission with time available under SELinux | Done. Both Fedora targets admitted SSH with time and refused at zero under enforcing SELinux. |
| [x] | 023 | Check that pausing captures all usage on every target | 010, 026 | Installed kiosk-rule lock before capture after a raw VT switch, per target | Done. Installed checks passed on all three targets, and cleanup finished. Focused host checks passed. |
| [x] | 017 | Qualify the shared test actions for saved time | 012, 013, 014 | Reusable public UI actions and observations on both surfaces | Done. Both installed slices passed on all three targets, and cleanup finished. |
| [x] | 018 | Save a running grant at the kiosk and unlock the retained desktop | 017, 023 | Scenario 1 retained desktop variant | Done. Case 267 passed on all three targets before the kiosk form changes. A later form check reported one failure. Cleanup finished, and the developer waived further reruns. |
| [x] | 019 | Keep a kiosk approval through reboot and use it at a fresh login | 018 | Scenario 1 reboot and fresh login variant | Done. Case 268 passed on all three targets, and cleanup finished. |
| [x] | 027 | Let long test runs finish without being cut off | Baseline | Claude session command time limit for waiting test runs | Done. New Claude sessions allow one command up to four hours. Source and launcher unit checks passed. |
| [ ] | 020 | [Pause and reuse approved time at the kiosk without losing seconds](Save-For-Later-Tasks/020.md) | 017, 023, 027 | Scenario 2 repeated transfers and saved-only revocation | 1–2 h |
| [ ] | 021 | [Pause from the child overlay and use the time from the kiosk](Save-For-Later-Tasks/021.md) | 017 | Scenario 3 pause variant: lock confirmation, shield, and kiosk return | 1–2 h |
| [ ] | 024 | [Save and use approved time alongside daily time from the child overlay](Save-For-Later-Tasks/024.md) | 021 | Scenario 3 daily-time variant: save, use, app policy, and deferral | 2–3 h |
| [ ] | 022 | [Bring the specification and test records up to date](Save-For-Later-Tasks/022.md) | 015, 016, 019, 020, 024 | Reconcile shipped behavior, ownership, security, and coverage documentation | 45–90 min |
