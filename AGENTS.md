# Repository agent instructions

## Environment and communication

- This computer is the development host. Do not install the product here unless
  the task explicitly requires an installed-system workflow. Development previews
  and maintained test viewers are allowed.
- Use `make install` as the sole entry point for any product installation,
  reinstallation or upgrade from this checkout, including tests and agent work.
  The `installdeb` and `installrpm` modules are internal implementation details;
  do not expose or invoke them as separate Make targets.
- For "handoff time", stop at the earliest clean boundary without interrupting
  important work. Return a concise continuation prompt with remaining work and a
  recommended model/effort; do not save it in the repository.
- Keep updates concise: meaningful results, blockers, behavior mismatches,
  validation limits and the next goal. Do not narrate polling or routine test
  phases. Let running commands and owned cleanup finish before reporting their
  result; retain actionable failure details.

## Localization
- When editing user-visible product strings, update all supported languages,
  except What's New release notes, whose synchronization requires the explicit
  request below.
- Never automatically run `tools/sync-whatsnew` when `docs/VersionHistory.md`
  changes. Synchronization requires an explicit user request under the
  [localization mandate](docs/SystemDesign/Localization.md#whats-new-translation-workflow);
  read-only completeness checks remain allowed.
- For recurring What's New translation, use `tools/sync-whatsnew` and the
  [established workflow](docs/SystemDesign/Localization.md#whats-new-translation-workflow).
  Translate only the latest numeric VersionHistory release and matching child
  TOML entry, when present; change translation assets only,
  never infrastructure, English source or older translations in a sync run.

## Authority and reading routes

- Start product work at [System design](docs/System-Design.md): use its module map
  to read the affected component, trust, state and lifecycle boundaries. The
  specification owns expected customer behavior. Follow related modules when a
  change crosses their boundary; a link does not require reading a whole document.
- Apply [Approval tools](docs/Approval-Tools.md) to reads, edits, builds, tests,
  diagnostics, setup and publishing. Reuse existing session/category authorization
  and validated direct launchers. Missing grants are blockers; do not broaden
  rules, retry authentication after denial or bypass ownership checks.
- Preserve all pre-existing work. Do not reset, discard, unstage or overwrite
  unrelated changes.
- Use the [test documentation map](docs/TestAutomation/README.md) to locate each
  rule's owner, including for documentation-only work. Read the applicable
  contract before work; keep enduring rules in that owner and link to them from
  task briefs instead of copying them. For reconciliation, use its
  [working route](docs/TestAutomation/README.md#working-route);
  updating a plan does not execute or close its tasks.
- Reuse unchanged instructions/source in context, including injected AGENTS.md.
  After a new session or compaction, retrieve missing applicable requirements.
  Read complete relevant functions and necessary callers, callees and shared
  state. Expand for ambiguity, stale references, shared changes or failures;
  truncated output and remembered summaries cannot replace a contract.

## Product boundaries

- Fix root causes reproducibly on clean supported computers using maintained
  public APIs. Preserve the shared child-form/kiosk contract and useful diagnostics
  without PII; role labels such as `[Child user]` are acceptable.
- For distro/DE-specific work, determine whether the cause is generic. Fix generic
  causes in shared code; isolate platform-specific behavior and check affected
  supported platforms.
- Read [Do Not Touch Portal](docs/Mandates/Do-Not-Touch-Portal-Mandate.md) when
  touching feedback API-related application code.
- Choose GPT-6.1 Sol Medium for settled implementation and GPT-6.1 Sol High for
  unresolved security, concurrency, ownership, difficult diagnosis or broad
  correctness review. Prefer Sol High over Astra Low; use bounded Astra High
  advice when an applicable workflow requires it. The
  [launcher policies](tests/README.md#scripted-repair-loop) specialize these defaults
  for test repair and E2E implementation. Prefer quality, then allowance.

## Tests and acceptance

- Select the lowest effective validation scope using
  [test maintenance](tests/README.md#all-established-regressions),
  `tools/run-tests --help` and `tools/run-tests --list`. Use the maintained launcher
  and its parallel scheduling within that scope; do not expand unit/UI work to
  `host` or `all` merely for parallelism. Preserve selectors and explicit timeouts.
- Follow [failure handling](tests/README.md#handling-test-failures). Preserve and
  report expected versus actual behavior. That owner distinguishes authorized
  mechanical repairs from behavior decisions; do not redefine expectations to pass.
- For customer acceptance, use the installed product's public actions/results.
  Keep internal probes and fault injection in engineering tests. The
  [shared task contract](docs/TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
  routes implementation, UI/E2E allocation, bounded supporting work and composition
  preflight. Cases own finite data/order/assertions; shared libraries own reusable mechanics.
- For "Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md",
  follow the [plan](docs/TestAutomation/E2E-Execution-Plan.md) and its first
  unchecked active queue row through acceptance and close-out. Documentation
  reconciliation does not execute or close a queue task.
- Review new host modules and resource-affecting test changes under the
  [parallelism contract](tests/README.md#host-test-parallelism-review), including
  every applicable inventory; runtime fallback is not completed review.
- Run `make build` for changes that can affect building/packaging, after the final
  such edit. Use `PACKAGE_SOURCE_FILES` and build-tool dependencies in `Makefile`
  to assess scope. Tests do not replace this check. Documentation/test-only work
  that cannot affect the build needs no build; report missing prerequisites or a
  failed build as unresolved validation.

## Conditional mandates

Read only the mandates triggered by the work:

| Work | Owner |
| --- | --- |
| UI automation, including previews and test adapters | [UI automation mandate](docs/Mandates/UI-Automation-Mandate.MD): route selection, public IDs, provider exception, input/result guards |
| VM operations, preparation or live tests | [VM mandate](docs/Mandates/VM-Mandate.MD): registered targets, unattended authorization, watch, leases and baseline lifetime |
| Test/fixture/tool storage or cleanup changes | [Test storage mandate](docs/Mandates/Test-Storage-Mandate.md): shared allocation, retention, identity and screenshot exceptions |

Read the VM mandate before VM work; it owns selector-specific authorization and
preparation lifetime, which a task's example command cannot establish.

## Reads, edits and evidence

- Quote every path, pattern and URL. Inspect operands and run direct reads from
  the intended working directory. Use `rg -n` with literal paths and quoted
  `--glob` filters; use `tools/read-only files|search --path-glob ...` for filename
  expansion and the validated reader for untrusted arguments.
- Public read-only research and log inspection are authorized. Use maintained
  [diagnostics](docs/Approval-Tools.md#system-reads) and
  [artifact readers](tests/README.md#prompt-free-test-artifact-access) for
  privileged data; never modify logs.
- Edit text with native `apply_patch`. Check changed Markdown with
  `tools/read-only links`; use `tools/read-only words` when counts matter.
- Keep routine failure/fix/verification details in conversation or existing
  runner artifacts. Update current contracts and active handoffs. Create a new
  evidence document only when requested or an active acceptance/recovery need
  has no existing artifact.
- Signal only explicitly spawned, identity-recorded processes. Follow the
  [cleanup contract](tests/README.md#cleanup-safety-prerequisites); cleanup is
  serial ownership/recovery, never a regression-test prerequisite run.
- Use documented artifact readers/exporters. Graphical-smoke PNG exports use
  the [screenshot export and cleanup contract](docs/Mandates/Test-Storage-Mandate.md#screenshot-export-and-cleanup),
  including its narrow caller-owned `/tmp` exception.

## Setup

`./setup.sh` is the sole public development setup entry point.
[One-time setup](docs/Approval-Tools.md#one-time-setup) owns modes, prerequisites,
helper/rule refresh and activation. Do not refresh rules to repair bad quoting.
Tests/builds report missing prerequisites rather than installing them.
