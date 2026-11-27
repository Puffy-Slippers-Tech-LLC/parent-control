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
| [ ] | 008 | [Let a parent approve time for later](Save-For-Later-Tasks/008.md) | 006 | Mode-bound authentication, durable approval, and optional pause | 1–2 h |
| [ ] | 009 | [Recover interrupted transfers and clear withdrawn time](Save-For-Later-Tasks/009.md) | 006, 007, 008 | Recovery triggers and serialization, revoke, and control-toggle invalidation | 1–2 h |
| [ ] | 010 | [Make saved time and timer actions available to the apps](Save-For-Later-Tasks/010.md) | 004, 009 | Broker dispatch, consistent status, and frontend client transport | 1–2 h |
| [ ] | 025 | [Refresh the child countdown while the overlay stays open](Save-For-Later-Tasks/025.md) | 001 | Overlay-to-panel refresh request bound to the started overlay process | 45–90 min |
| [ ] | 011 | [Build the request and approved-time tabs](Save-For-Later-Tasks/011.md) | 001 | Shared layout, menu, Approved time states, and lock dialog | 1–2 h |
| [ ] | 012 | [Connect both request screens to the timer actions](Save-For-Later-Tasks/012.md) | 010, 011, 025 | Request form state and actions, success routes, and the countdown refresh call | 2–3 h |
| [ ] | 013 | [Show saved time in Parent and let parents revoke it](Save-For-Later-Tasks/013.md) | 010 | Parent balance display, availability, and saved-only revoke | 1–2 h |
| [ ] | 014 | [Report saved-time operations without personal information](Save-For-Later-Tasks/014.md) | 010 | Structured event catalogue, operation outcomes, and field validation | 45–90 min |
| [ ] | 015 | [Check that removal preserves saved time only if it is aborted](Save-For-Later-Tasks/015.md) | 010 | Installed removal, rollback, retry, reinstall, and purge engineering histories | 2–3 h |
| [ ] | 016 | [Check that an upgrade preserves saved time](Save-For-Later-Tasks/016.md) | 010 | Installed broker restart and package update with saved time and recovery state | 2–3 h |
| [ ] | 023 | [Check that pausing captures all usage on every target](Save-For-Later-Tasks/023.md) | 010 | Installed kiosk-rule lock before capture after a raw VT switch, per target | 2–3 h |
| [ ] | 017 | [Qualify the shared test actions for saved time](Save-For-Later-Tasks/017.md) | 012, 013, 014 | Reusable public UI actions and observations on both surfaces | 2–3 h |
| [ ] | 018 | [Save a running grant at the kiosk and unlock the retained desktop](Save-For-Later-Tasks/018.md) | 017, 023 | Scenario 1 retained desktop variant | 1–2 h |
| [ ] | 019 | [Keep a kiosk approval through reboot and use it at a fresh login](Save-For-Later-Tasks/019.md) | 018 | Scenario 1 reboot and fresh login variant | 1–2 h |
| [ ] | 020 | [Pause and reuse approved time at the kiosk without losing seconds](Save-For-Later-Tasks/020.md) | 017, 023 | Scenario 2 repeated transfers and saved-only revocation | 1–2 h |
| [ ] | 021 | [Pause from the child overlay and use the time from the kiosk](Save-For-Later-Tasks/021.md) | 017 | Scenario 3 pause variant: lock confirmation, shield, and kiosk return | 1–2 h |
| [ ] | 024 | [Save and use approved time alongside daily time from the child overlay](Save-For-Later-Tasks/024.md) | 021 | Scenario 3 daily-time variant: save, use, app policy, and deferral | 2–3 h |
| [ ] | 022 | [Bring the specification and test records up to date](Save-For-Later-Tasks/022.md) | 015, 016, 019, 020, 024 | Reconcile shipped behavior, ownership, security, and coverage documentation | 45–90 min |
