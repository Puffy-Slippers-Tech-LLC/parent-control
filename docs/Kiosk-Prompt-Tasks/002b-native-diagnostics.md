# 002b — Add native binding failure causes

Acceptance: host

Read the [master](../Kiosk-Prompt.md), audited native failure branches, complete
binding/PAM callers and existing native mount fixture. Reuse those mechanics;
002a's classification and required-input behavior remain authoritative.

Add bounded closed reason/errno markers for native binding refusals that
currently expose only stage=bind: manifest/metadata/identity, namespace/mount,
read-only attachment and owned staging detach. Use closed stage/cause categories
and bounded numbers, without names, paths, identities or arbitrary error text.
Diagnostic failure must preserve the exact native refusal/success result.

Exercise each distinct cause with private native fixtures and independent mount/
identity witnesses. Preserve required ownership, labels, limits and cleanup.
Do not add a general fault-injection or privileged command interface. Give 002
the exact producer schema and sample sanitized records for collector projection.

Run affected native/PAM host selectors and resource reviews, then make build
after final packaged edits. Retain original expected/actual evidence and finish
owned cleanup. Close only cause production; 002 owns archive composition.
