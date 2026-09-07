# E2E inventory and runner contract

`scenarios.json` is the versioned starting inventory for
[E2E coverage](../../docs/TestAutomation/E2E-Coverage.md). All 156 variants are
currently **pending**. Inventory validation is host unit coverage; it does not
establish graphical behavior or complete Task 19A. The guarded E2E launcher,
runtime evidence collector and `make check-e2e` remain unfinished.

## Inspect scope on the host

From the checkout, these commands only read declarations and print JSON. They
need no root, package artifacts, installed product, graphical tools or VM:

```sh
python3 -B tests/e2e/inventory.py
python3 -B tests/e2e/inventory.py --scenario E2E-023
python3 -B tests/e2e/inventory.py --scenario E2E-023/fullscreen
```

An omitted selector lists every category, family and variant, including pending
work. An exact family selects all its variants. An exact `E2E-NNN/variant`
selects one case and is partial, even if the family currently has one variant.
Any explicit selection is partial relative to the full inventory. Empty,
unknown, wildcard, prefix and comma-separated selectors fail with exit 2.
`--require-runnable` also refuses any selection containing a pending variant;
it still only lists and never executes anything. Pending cases are never
silently filtered to obtain a successful selection.

The JSON includes canonical case IDs, owner, status/reason, parameters,
environment, prerequisites, duration bound, ordered phases, assertions,
expected evidence and the SHA-256 of the exact inventory bytes read. This digest
identifies the declaration only. The future runner must separately freeze and
identify current source, requirement mappings, packages, assets and environment.

## Maintain declarations

Schema version 1 has common family declarations inherited by each explicit
variant. Every variant has a stable ID and one canonical owner from the
family's related tasks. There is no runtime Cartesian expansion or duplicate
execution for related owners. Dimensions enumerate required values;
`full_combinations` names interacting groups whose entire product must appear
in explicit variants. Validation rejects missing values, missing combinations
and duplicate combinations. Independent sequential boundary checks belong in
the ordered steps and the matrix rationale. Owning tasks must audit and expand
this starting matrix before acceptance; declared matrix closure is not proof
that every product requirement or transition has been enumerated.

The first 29 families come from the required coverage table. E2E-030 adds
installed About/license access; E2E-031 covers feedback drafts, validation and
attachment/diagnostic review; E2E-032 covers authorized real delivery; E2E-033
covers retry after a declared real transport fault. Delivery prerequisites are
explicit authorization, a dedicated test recipient and the actual supported
service profile. Inventory registration grants no delivery permission.
Installation, About and feedback requirement-mapping gaps are explicit pending
work with owners and authoritative contract references. They must be mapped
before those cases become ready. No existing requirement is marked covered.

`pending` requires a reason and a null executable. `ready` requires no pending
reason or requirement gap and an existing `tests/e2e/*.py` or `*.pm` reference
(including subdirectories) plus its unique executable test ID. Validation never
imports or runs those files. Ready means registered for execution, **not passed**;
the future collector must reconcile actual scheduling and completed results
with the selected identities. References cannot traverse outside `tests/e2e`,
including through a symlink.

Each attempt has distinct setup, start, ordered steps, end and cleanup phases.
Provisioning belongs only in setup and the outer reset only in cleanup.
Customer steps are UI actions, read-only observations or real waits. Fault and
controlled-environment operations require the matching category and a declared
intervention with actor, step and expected evidence. Every family declares
visible, backend and other-user assertions tied to actual journey steps. The
runner smoke instead checks host/source preservation without claiming a
customer isolation test. These typed declarations are not a sandbox for test
code: the launcher must enforce lifecycle, secret and observation boundaries.

## Minimum evidence declaration, version 1

The inventory pins required run and step field names so the next collector
can implement a shared format. This slice validates the **declaration**, not
runtime result payloads, artifact safety, or completeness of a passing attempt.

| Fields | Required meaning for the collector |
| --- | --- |
| `run_id`, `scenario_id`, `variant_id` | One independent attempt and its exact selected identity; reruns have new attempt IDs. |
| `source_sha256`, `inventory_sha256`, `package_sha256`, `assets_sha256`, `environment_id`, `baseline_sha256` | Current input provenance. A product-free smoke records an explicit null package identity, never an invented package digest. |
| `started_at`, `ended_at`, `steps` | Actual attempt boundaries and ordered step records, including failure/interruption. |
| `artifacts` | Collected, validated private artifact references with content digests and redaction status; never credentials or arbitrary raw worker output. |
| `outcomes`, `first_failure`, `cleanup` | Separate product, infrastructure, collection and cleanup outcomes; preserve the first failure and record lease/host/baseline restoration. A passing diagnostic retry cannot replace it. |
| Step `step_id`, `phase`, `operation`, `outcome`, `monotonic_seconds` | Actual execution order, declared operation and bounded measured timing. |
| Step `boot_id`, `session_ids`, `assertion_ids`, `artifact_ids` | Real continuity, using safe identity aliases in exported evidence, and links to executed assertions and collected evidence. |

Expected evidence always includes action trace, screen, backend, other-user,
continuity, input provenance, split outcomes and cleanup. Declared faults also
require intervention evidence, and external-delivery scenarios require delivery
evidence. Missing, extra, duplicate, skipped, failed or stale required results,
unsafe artifacts and failed cleanup must prevent a runtime pass. Task 19A's
collector/launcher slice implements those checks; Task 27 extends the contract.

## Verify edits

```sh
/usr/bin/python3 -B -m pytest tests/unit/test_e2e_inventory.py -q
```

These tests run automatically in `make check` via ordinary unit discovery.
They cover selection refusal, pending/ready separation, matrix closure,
three-sided evidence declarations, malformed input, executable containment,
phase/intervention categories and host-only CLI behavior.
