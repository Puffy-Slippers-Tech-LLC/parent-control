### Task 01 — Establish specification IDs and executable traceability

- Complexity: medium-high. The mechanics are simple, but preserving the exact
  meaning and acceptance scope of every normative statement needs care.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: make completeness measurable before adding new test layers.
- Work:
  1. Add a stable, unique ID to every normative bullet in `Specification.md`,
     including nested app-policy states and all component requirements. Preserve
     the normative wording.
  2. Create `tests/requirements.json` using a documented schema with requirement
     ID, specification section, responsible component, required test layer,
     executable test references, evidence type, and current coverage state.
  3. Populate all requirement records. Existing tests may be referenced only
     when they execute the stated behavior; source-text assertions may be listed
     as supporting contracts but never as acceptance evidence.
  4. Add `tools/verify_test_traceability.py` using the Python standard library.
     It must reject duplicate IDs, missing specification IDs, unknown test
     references, invalid layer names, and malformed records.
  5. Add focused unit tests for the validator and wire its stage-appropriate mode
     into `make check`. The stage-appropriate mode validates structure and known
     references while allowing explicitly recorded `planned` coverage until
     Task 28.
  6. Document the requirement-ID and mapping maintenance rules in this file and
     the integration test README.
- Verification:
  - Run the traceability validator directly.
  - Run its focused unit tests.
  - Run `make check`.
  - Run `git diff --check`.
- Completion criteria: every normative specification statement has exactly one
  stable ID, every ID has a valid manifest record, and no unsubstantiated
  acceptance claim is present.

