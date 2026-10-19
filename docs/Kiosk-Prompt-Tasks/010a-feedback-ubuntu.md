# 010a — Qualify Ubuntu feedback-only diagnosis

Acceptance: installed
Targets: onpc-Ubuntu26.04

## First action when selected

Apply the developer-requested [staged split](../Kiosk-Prompt.md#smaller-execution-slices).
Insert this unchecked prerequisite immediately before the active consumer:

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 010a1 | [Implement canonical diagnostic history](010a1-feedback-history-host.md) | 004, 007, 009 | Register and host-validate the finite failed-entry/recovery/reboot/public-download archive history | 20–30 min |

Use the queue-relative `Kiosk-Prompt-Tasks/...` link. Add 010a1 to this consumer's
Requires, preserving 004, 007, 009, its Scope and the complete history below.
Move Next task to 010a1, finish owned cleanup and return `prerequisite_required`.
Then run this original consumer's whole installed Ubuntu acceptance. Independent
missing adapters need finite prerequisites rather than expansion of this history;
host implementation never supplies installed acceptance.

Read the [master](../Kiosk-Prompt.md), admission diagnostic owner, actual Parent
diagnostic-download mechanics and Reliability 010. Extend/register the finite
canonical history; no report upload or portal change is authorized.

Induce one owned pre-form incident-class failure, restore it and demonstrate later
usable entry, then reboot within the retained-history bounds. Collect through
Parent's actual public download. The archive alone must distinguish successful
passwordless authentication, routing and preparation/binding failure and retain
the closed ownership/type/access/scope cause after recovery. Collection limits
must remain explicit.

Assert UTC source ordering and privacy: no raw journals, arbitrary paths,
account/process/host identities or exception text. Redundant hostile-record/
collection-failure branches remain host tests. Session exception: the complete
failure/recovery/reboot/archive/cleanup history and initial implementation may
take 30–60 minutes; extract independent adapter work first.

Run affected host/build checks and retain exact candidate/fixture/archive/cleanup
receipts in existing storage. Give reusable mechanics and Ubuntu receipts to 010
and matching Reliability 010 evidence without closing those consumers.
