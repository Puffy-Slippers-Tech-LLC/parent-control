# F12 — Decouple Fedora snapshots from fixture payloads

Acceptance: installed
Targets: onpc-Fedora44
Requires: F48

## Purpose and scope

Complete the [snapshot/dependency split](../Fixture-Design.md#runner-and-snapshot-migration)
on Fedora using the same schemas and shared capture/provisioning implementation.
Ordinary new-schema dispatch stays disabled until F41–F47 and F49 pass.

## Read and implement

Read F11's complete digest/capture/legacy recovery changes, F01's remaining
Fedora consumer inventory, native dependency/trust/label ownership and relevant
baseline/app-snapshot safety tests. New Fedora snapshots retain unavoidable
environment dependencies, not movable native runtime payloads, launcher/data
collections or fixture build tools. Preserve native trust ownership recovery
when an old snapshot contains a prior prepared fixture record.

## Finite validation and cleanup

Run affected isolated capture/recovery/native safety tests before protected work.
Record any separately invoked authorized schema-establishing baseline/app refresh.
With registered/listed engineering bindings prove clean captures, standalone app
preparation without fixtures, restore then minimum dynamic provisioning under
enforcing SELinux, original-schema stop/restoration after source/dependency changes
under F24/F30's legacy matrix, and fixture-only A→B update in fresh
attempts with unchanged baseline/app snapshot identities. F08 separately owns
same-boot maintenance refresh. Real dependency/product changes
must still invalidate. Check no mapped consumer resolves a legacy payload fallback
and no leaked staging/old trust admission, archived input tree, E2E asset payload
or launch barrier enters capture. Include F33's full legacy inventory and retained
preparation checkout; no movable source copy may remain. Register the fixed
clean-schema engineering route, retain ordinary admission refusal and hand the
seven distinct clean Fedora envelope checks to F41–F47. F49 enables ordinary
dispatch only after those rows pass against these snapshots; legacy integration
proof cannot substitute. Finish owned restoration,
cache pins and transaction cleanup. Renew any Ubuntu proof invalidated by shared
edits, update all remaining current mandate/environment/support references and
close through the [master](../Fixture-Execution-Plan.md).
