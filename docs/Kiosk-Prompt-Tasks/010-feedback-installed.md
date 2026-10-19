# 010 — Qualify Fedora feedback-only diagnosis

Acceptance: installed
Targets: onpc-Fedora44

Session boundary: qualify 010a's canonical report history on Fedora and
reconcile both candidate receipts. Session exception: original failure, later
success, reboot, actual public archive and cleanup remain in one history. 010a
retains Ubuntu acceptance; rerun it after invalidating implementation changes.

Read the [master](../Kiosk-Prompt.md),
[diagnostic contracts](../SystemDesign/Logging-and-Feedback.md), existing Parent
feedback/export mechanics and [Reliability 010](../Reliability-Tasks/010-diagnostic-recovery.md).
No report upload or portal change is required or authorized by this task.

On Fedora, induce one owned pre-form entry failure from this incident class.
Recover and demonstrate later usable kiosk entry; also retain a bounded reboot
before collecting the report to test the audited cross-boot history requirement.
Use Parent's actual public diagnostic download and inspect that archive alone.
It must distinguish successful passwordless authentication from routing,
preparation/binding failure and identify the closed ownership/type/access/scope
cause. Later success must not erase the original denial. Collection limitations
must be explicit, not interpreted as absence of a failure.

Assert source UTC ordering, clipping/failure categories and exclusion of raw
journals, arbitrary paths, account/process/host identities and exception text.
Use host tests for redundant hostile-record and collection-failure permutations.
Retain only existing runner evidence and clean up owned mutations/exports through
maintained routes. Share matching receipts with Reliability 010 without closing it.
