# Task 27 — Supporting evidence and wait improvements

**Scope — 2026-09-14:** existing runner contracts, regression tests, secret
protection, provenance, cleanup and artifacts stay intact. Broad new evidence
and orchestration work is deferred outside the active queue. A named customer
journey or mechanical installation case may bring forward only the minimal
adapter required to execute safely and report its actual result.

Follow [E2E-Coverage.md](E2E-Coverage.md). Customer pass/fail uses visible
behavior; mechanical Tasks 18/20 retain their internal evidence. Do not make
customer cases wait for a comprehensive new schema, collector or all-runner
migration.

## Implementation slices

For a concrete consumer, state the blocked action or required artifact, reuse
the existing interface, implement the minimum change and complete that consumer.
Keep its work and progress in the consumer's handoff. General helper passes
are not completed customer scenarios.

## Task 27A

- Status: deferred general evidence expansion; not an automatic launcher task.
- Permitted consumer work: adapt the existing evidence validator so a declared
  customer scenario can use visible assertions without mandatory backend
  product witnesses. Preserve identity, safe artifacts, failure reporting and
  cleanup validation. Mechanical/system tests keep their internal assertions.
- Do not invent backend values, make every evidence field optional, or loosen
  secret/ownership guards. Qualify changed refusal paths with focused existing
  test patterns, then execute the named customer scenario.
- Broader archive/redaction/schema work remains a separate engineering scope;
  existing coverage must not be deleted or weakened.

## Task 27B

- Status: deferred broad runner integration.
- Reuse existing framework outputs and implemented adapters. Add a field mapping
  only if a concrete selected customer/package case cannot report required
  evidence through the current safe interface.
- Do not collect D-Bus/PAM/rule/process/private-state evidence for customer
  assertions. Installation/system collectors retain their legitimate scope.

## Task 27C

- Status: fix only an observed wait failure blocking a named consumer.
- Use existing bounded graphical waits for visible readiness. Preserve timeouts
  and first failures; a retry is a new whole attempt, not a green rewrite.
- Do not standardize every service/SSH/boot/internal wait before implementing
  customer cases. Never add backend probes to replace a visible assertion.
- Existing transport/cleanup safety checks remain required. Repeat qualification
  only for changed behavior or a documented stability question, then return to
  the consumer. A third unfinished prerequisite slice needs the
  [workflow's intervention](Implementation-Workflow.md#handoff-format-and-cost-review).
