### Task 02 — Adopt pytest without rewriting the existing unit suite

- Complexity: low-medium. Pytest directly collects the existing unittest suite.
- Recommended Codex model: `gpt-5.6-luna`
- Recommended reasoning effort: `medium`
- Objective: create one scalable Python runner while retaining all current test
  coverage and host safety.
- Work:
  1. Add a repository pytest configuration with strict marker and warning
     handling, deterministic test paths, and xUnit2 JUnit output support.
  2. Define and document reproducible test-tool dependencies for Ubuntu 26.04.
     Prefer Ubuntu packages for PyGObject-integrated tools and pin non-Ubuntu
     Python wheels with hashes in an isolated test environment.
  3. Make pytest collect all existing `tests/unit` unittest cases without a bulk
     syntax conversion.
  4. Preserve the existing syntax, XML, policy, and private-API source checks.
  5. Add a host-safe `make check-unit` target and make `make check` invoke it.
  6. Produce a JUnit report under an ignored artifacts directory only when the
     caller requests report output.
- Verification:
  - Prove that pytest collects at least the same 288 existing tests.
  - Run `make check-unit` and `make check`.
  - Run `git diff --check`.
- Completion criteria: the original suite passes under pytest, `make check`
  remains non-privileged and host-safe, and no existing test was silently lost.

The repository configuration is in `pyproject.toml`. Ubuntu 26.04 test-tool
dependencies are recorded in `tests/test-tools-ubuntu-26.04.txt`; use the
Ubuntu archive package rather than unpinned system-wide wheels. `make
check-unit` is the host-safe pytest entry point and writes no report unless a
caller explicitly adds pytest's report options.

