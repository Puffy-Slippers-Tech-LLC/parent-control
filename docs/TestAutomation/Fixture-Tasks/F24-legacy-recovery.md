# F24 — Preserve original baseline and fixture decoding

Acceptance: host
Requires: F04

## Purpose and scope

Implement the baseline/fixture half of the
[legacy compatibility matrix](../Fixture-Design.md#legacy-recovery-compatibility)
before guest readers or snapshot schemas migrate. F30 separately owns app,
credential and VM-owner formats.

## Read and implement

Read complete preparation-marker/capture validators, fixture/native-trust/backend
codecs and their callers/tests. Dispatch recognized original marker schemas 2/3,
capture schema 2, reusable-fixture v1 and native-trust/backend variants using
accepted root-owned baseline provenance. Preserve original dependency inventories,
accounts, fixture declarations, exact file metadata and native exceptions;
do not compare an old marker with current declarations.

Add the versioned root-owned recovery sidecar specified by the design, bound to
the original capture/baseline and retained with its recovery owner. Preserve raw
accepted records and original assertions before declarations change. Missing
original proof or an unknown shape refuses; no archived code execution or receipt
adoption is allowed. Pending placement stays with its original preparation owner.
New acquisition still requires current ABI/readiness. This task decodes and
preserves proof; F33 owns import and retirement of legacy movable files.

## Finite validation and cleanup

Use original-schema private inputs for unchanged recovery after declaration
changes, known native variants, pending-placement/backend shapes, sidecar lifetime
and exact missing/foreign/replaced/unknown refusal. Assert decoding does not
rewrite saved identities. Preserve currently unsupported phases. Run exact
baseline/fixture/native safety selectors and resource review; clean only private
owned inputs. F11/F12 own live original-schema recovery before clean capture.
Update delivered recovery owners and close through the
[master](../Fixture-Execution-Plan.md).
