# E08 — Unify local Markdown reference checks

Acceptance: host
Requires: E02

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
