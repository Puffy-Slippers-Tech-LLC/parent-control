# E05 — Reuse exports and verified reads

Acceptance: host
Requires: E04

## Purpose and delivery

Deliver idempotent exports and bounded efficient inspection from
[lifetime and reuse](../Export-Design.md#lifetime-capacity-and-reuse), following
the [master](../Export-Execution-Plan.md). Read the complete `onpc-test-artifacts`
export/source validation, shared bundle writer/reader, retention inspection locks
and existing verified-read/repeated-export regressions.

Return an existing private export/receipt when exact source selection, content,
provenance and authority still match, without starting a new retention session.
Handle concurrent identical requests without duplicate committed exports. Replaced,
missing or changed copies require safe recapture or a specific refusal; never
return a remembered path as success. Group related files atomically through the
existing bundle writer. Preserve filename compatibility where promised, caller/
root ownership and source immutability; no unsafe shared writable hardlinks.
Keep concurrent readers compatible and reuse verification only within the same
pinned verified scope. Revalidate after mutation or scope release.

## Validation and close-out

Test repeated identical export without slot growth or eviction of another report,
changed source, same basenames, stale reuse records, concurrent requests/readers,
writer exclusion, interrupted grouped export and archive mutation. Assert private
modes, correct owner and original source bytes. Extend artifact/bundle/retention
regressions with meaningful allocation and verification-count bounds. Run the
lowest effective host selections and applicable cleanup-safety tests, update
artifact access documentation and follow the master's cleanup and close-out.
