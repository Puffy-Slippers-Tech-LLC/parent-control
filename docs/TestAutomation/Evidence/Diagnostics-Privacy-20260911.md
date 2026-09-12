# Automatic diagnostics privacy

The client now produces schema-validated technical reports while preserving
customer-written feedback, optional reply email, and selected attachments.
The governing contract is [Logging, diagnostics, and feedback](../../SystemDesign/Logging-and-Feedback.md).

## Implemented boundary

- The shared catalogue approves each event, component, field, numeric bound,
  enum and fixed description before a LogRecord is created. Python and child
  JavaScript producers use the same catalogue. Logging prefixes are `onpc.*`.
- Storage and export accept structured events only. Existing text logs,
  journals, exception messages, user identities, paths and arbitrary files
  never enter the automatic report. ZIP metadata is discarded by rebuilding
  again before HTTP attachment. Customer-selected files retain their contents.
- Bounded history, repeat suppression, collection counters and pinned error or
  anomaly context preserve useful evidence without collecting an activity
  history linked to an account. Grant observations record arithmetic and
  attribution limits; unrelated operations cannot be tied to a particular child.
- Background grant reads hold no approval lock. A transaction revision and
  observation guard reject stale reads. Diagnostic faults cannot change grant
  calculations, authorization, write verification or rollback behavior.
- Startup test ownership evidence comes from `GetStartupTimings` on the pinned
  live owner, with existing process/invocation/boot continuity checks. Those
  identities are excluded from diagnostic logs and feedback.

The call-site audit covered broker authorization, account adapters, policy,
grants, persistence, lifecycle and removal; parent discovery and management;
child countdown/session/request behavior; kiosk and shared UI resources; and
feedback/editor/transport failures. Pure formatting and customer-input helpers
keep failure reporting at their owning operation rather than logging inputs.
The [privacy tests](../../../tests/unit/test_diagnostic_privacy.py) enforce the
catalogue at application logging sites and reject arbitrary field text.

## Verification

| Check | Result |
| --- | --- |
| `make check` | 7,910 unit tests and 134 private-D-Bus component tests passed. |
| Final privacy, grant, broker property/state-machine, storage, export and transport regressions | 490 tests and 18 subtests passed after the final observer/conversion safeguards. |
| Final service/startup private-D-Bus checks | 25 passed; 806 isolated cleanup prerequisites passed. |
| Child Node and GJS adapters | 14 Node tests passed; GJS adapters passed. |
| Parent, child and kiosk feedback UI | All 14 cases passed; two stale exception-text expectations were corrected and rerun. Real delivery was mocked. |
| Static/source checks | Shell, GJS, syntax and staged traceability passed. |
| Package | The validated artifact builder produced and verified a Debian package from an isolated source copy. |

The direct `make build` route encountered a pre-existing root-owned Python
cache in the working checkout. The artifact builder includes current tracked
and untracked source while excluding generated caches; it requires no ownership
change or product installation. Final artifact directories include a source
digest and verified package/fixture manifest.

This is local verification, without a customer installation, live feedback
email, portal edit, or installed end-to-end qualification. Ship broker and
frontends together: broker changes require process restart, desktop apps load
new code in new processes, and the child extension/shared session payload uses
session renewal. Mixed old raw-log/new-schema processes fail closed for
diagnostics; sending customer feedback without diagnostics remains available.
