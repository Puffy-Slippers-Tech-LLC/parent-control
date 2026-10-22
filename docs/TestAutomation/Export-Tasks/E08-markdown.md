# E08 — Unify local Markdown reference checks

Acceptance: host
Requires: E02, E08p-capacity

## Purpose and delivery

Deliver the shared bounded reference parser required by
[specific references](../Export-Design.md#stable-and-specific-references) and
[proportional validation](../Export-Design.md#proportional-validation), following
the [master](../Export-Execution-Plan.md). Read `document_checks.py`, `read-only`,
`execution_plan.evidence_references`, `plan_evidence._references` and rewrite
consumers plus their parsing and protected-structure tests.

Parse local inline/image and reference-style destinations, document-relative
paths and supported fragments through one shared representation with source
offsets. Define heading/explicit-anchor compatibility against repository usage,
including duplicate headings, escaping, Unicode, encoded spaces and parentheses.
Mask code/examples without losing line offsets. Do not fetch URLs or interpret
source text as commands. Distinguish literal terminal filename punctuation from
sentence punctuation. Keep protected queue comparison narrower than general
parsing: unsupported syntax must not normalize arbitrary claim changes.
Expose structure separately from evidence identity/availability validation.

## Validation and close-out

Follow the master's [mandate boundaries](../Export-Execution-Plan.md#delivery).
Test parsing once at the shared owner, with representative consumer integration
for a distinct command-safety or protected-claim boundary. Reuse existing cases;
do not duplicate the syntax matrix in document, reader and plan tests.
Cover inline/reference/image syntax, fragments,
same-document anchors, malformed links, duplicate headings, code fences/spans,
spaces, angle destinations and literal punctuation. Check stable diagnostics and
finite input bounds; optional versus required severity is assigned by E10, not
guessed by this parser. Run scoped host tests and changed Markdown checks, update
the documented reader contract and follow the master's cleanup and close-out.

## Retained implementation and remaining acceptance

The shared parser, fragment checker, evidence collection, protected comparisons
and rewrite/recovery consumers are implemented. Reader documentation, resource
review and generated coverage are updated. Independent Sol High review approved
after heading projection, explicit-anchor attributes, raw label bounds,
conservative legacy masking and literal code-path spelling were corrected.
Both helpers finished; no agent or test process remains running.

The fresh 600s host selection passed all 623 cases, including the shared syntax
owner, command safety, evidence/recovery consumers, protected queue claims,
actual-byte restart guards and all four consistency modules
([report](../../../output/test-runs/host/reports/20261022T230339Z-448ceedb/report.md)).
Its final evidence publication failed with `capture publication: invalid request
closure`; this is not accepted E08 proof. The shared regression publication
retains 253 requests, and this seven-record run exceeds the hardcoded 256-request
history check in `tools/capture_publication.py`. The prerequisite owns repair
and exact retained-capture recovery; preserve all sealed originals and prior
publications. Do not reset journals or replace the original verdict/attempt.

The earlier seven-module run passed 1130 cases and failed two
([report](../../../output/test-runs/host/reports/20261022T225110Z-799ff2d1/report.md)):
the new rewrite fixture exposed Markdown examples being mistaken for code paths,
and a real restart guard observed source edits during execution. The reader was
corrected; both points passed in the unchanged-source 623-case renewal above.
After the prerequisite passes, finish E08's applicable acceptance, owned cleanup
and normal close-out. E08 remains unchecked and receives no acceptance credit
from these retained execution results. No product/package inputs changed.

The required post-insertion consistency attempt did not execute its cases:
host recovery hit the same publication limit
([retained output](../../../output/test-runs/host/sessions-host/b7b27070e9164ab197983d356e9f8664/output)).
The runner ended; no test or helper process remains active. Complete that
consistency selection after the prerequisite repair.
