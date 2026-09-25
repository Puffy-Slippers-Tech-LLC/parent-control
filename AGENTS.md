# Repository agent instructions

## Environment and communication

- Treat this computer as the development host. The product is not installed and
  must not be installed unless the task explicitly requires an installed-system
  workflow. Development previews and the maintained test viewers are allowed.
- When asked for "handoff time" or a similar phrase, stop at the earliest clean boundary without interrupting important ongoing work and return
  a concise continuation prompt. Include only the remaining work and recommend a
  model and effort; do not save the prompt in the repository.
- Do not send progress messages while a command is running. Report it after it
  completes or fails.
- Keep progress updates and final responses concise and focused on meaningful
  results and the next intended action. Omit routine prerequisites, procedural
  narration and test counts unless they affect a decision or explain a problem.
  Perform required checks without narrating each step. Preserve important
  updates: blockers, unexpected findings, behavior mismatches, material risks,
  validation limits and decisions requiring user input. Describe the next goal
  accurately without implying that its prerequisites are already complete.
  Example: "All scoped tests now pass. Next I'll run the live qualification."

## Authority and unattended work

- Start product work at [System design](docs/System-Design.md). It owns component,
  trust, state and lifecycle boundaries. The specification owns expected customer
  behavior. Use the design's overview/module map to locate the affected boundary;
  read the applicable sections, following related modules when that boundary is
  crossed. A link to a contract does not require loading its entire document.
- Apply the repository-wide [approval contract](docs/Approval-Tools.md) to all
  reads, edits, builds, tests, diagnostics, setup and publishing. Run
  authorized work unattended through its existing grants and validated tools.
- Reuse session and category-wide authorization. Do not request Codex or Polkit
  prompts, add duplicate rules, broaden shell/interpreter/Git/Make grants,
  or use authentication fallbacks after denial. A missing prerequisite or grant
  is a blocker to report, not a control to bypass.
- Executable project `tools/` launchers are preapproved only within the requested
  task. Invoke them directly. Use their scoped out-of-sandbox routes when sockets,
  Polkit or real ownership metadata require them.
- Preserve all pre-existing work. Do not reset, discard, unstage or overwrite
  unrelated changes.

## Product boundaries

- Fix root causes reproducibly on clean computers with supported, maintained
  public APIs. Preserve the shared child-form/kiosk contract and log useful
  diagnostics without PII; role labels such as `[Child user]` are acceptable.
- Read [Do-Not-Touch-Portal-Mandate](docs/Mandates/Do-Not-Touch-Portal-Mandate.md) only when touching
  feedback API-related application code.
- Choose the implementation model by the current slice: Sol for settled work;
  Astra for unresolved security, concurrency, ownership, difficult diagnosis or
  broad correctness review. Prefer quality, then weekly allowance.

## Test and customer acceptance

- Follow the [test-automation documentation map](docs/TestAutomation/README.md)
  and the [executable inventory](tests/e2e/scenarios.json). Customer acceptance
  operates the installed product through public interfaces and observes customer
  results; backend probes and internal fault injection remain engineering tests.
- Use the documentation map's ownership and status terms when reconciling E2E
  records: the plan selects the next task from its canonical queue, briefs define
  unfinished task scope, and inventory `coverage_id` values select runnable cases.
  Task IDs and scenario IDs are separate namespaces. Inventory `ready` means
  registered for execution; task completion requires its acceptance and close-out.
  Reconciliation alone supplies no live acceptance or task-completion credit.
- For “Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md”,
  implement exactly its first unchecked active queue row. Table order is final;
  task IDs are labels, and prerequisites name earlier tasks' delivered scopes.
  Finish that row's acceptance and close-out before advancing the sole pointer.
  Do not select alternative work, complete a later scenario inside a capability
  task, or skip a blocker. Keep each complete E2E case in its own task. Maintain
  the queue consistency checks when splitting or repairing the plan.
- Tests must catch regressions. On a behavior mismatch, preserve the evidence and
  report expected versus actual behavior. Obtain developer confirmation before
  accepting the change or altering expectations unless that exact behavior change
  is already authorized. Never weaken, skip or delete a check to match the app.
  Proven mechanical defects in tests, fixtures or harnesses may be fixed while
  preserving the intended assertion. See [failure handling](tests/README.md#handling-test-failures).

## UI automation mandate

Read the [UI automation mandate](docs/Mandates/UI-Automation-Mandate.MD) only when doing UI automation work.

## VM mandate

Read the [VM mandate](docs/Mandates/VM-Mandate.MD) only when doing VM operations or tests.

## Reads, edits and evidence

- Reuse unchanged instructions and source already available in the current
  context, including injected AGENTS.md. In a fresh session or after compaction,
  retrieve missing applicable requirements; do not treat a remembered summary as
  their replacement. Read linked documents by task-relevant heading/row and code
  by complete relevant function plus necessary callers, callees and shared state.
  Expand for ambiguity, stale references, shared changes or failures. Token
  savings never justify missing a contract, weakening checks or guessing at
  truncated output. For repeated E2E work, use the execution plan's
  [reading routes](docs/TestAutomation/E2E-Execution-Plan.md#load-only-the-selected-context).
- Quote every path, pattern and URL. Inspect operands before execution. Run
  direct reads in the intended working directory; do not wrap them in shells,
  substitutions, assignments or redirections.
- Use `rg -n` only with literal paths and quoted ripgrep `--glob` filters. Use
  `tools/read-only files|search --path-glob ...` when filename expansion is
  required. Use `tools/read-only` for untrusted arguments and the other bounded
  read/filter/fetch operations documented by the approval contract.
- Public read-only research and log inspection are authorized. Use the maintained
  diagnostics and artifact readers for privileged data; never modify logs.
- Edit text with native `apply_patch`. Validate changed Markdown with
  `tools/read-only links` and use `tools/read-only words` when counts matter.
- Keep routine failure/fix/verification details in the conversation or existing
  runner artifacts. Update current contracts and active handoffs, not historical
  incident narratives. Create a new evidence document only when explicitly asked
  or when an active acceptance/recovery need has no existing artifact.

## Tests and artifacts

- Review every added host test module, and resource-affecting changes to existing
  tests, for parallel execution before marking the work complete. Check mutable
  paths, caches, processes, sockets/buses/displays, fixtures and resource demand.
  Classify qualified work in the applicable unit, cleanup and UI schedulers;
  cleanup modules need both unit and cleanup review. Use build resource admission
  for heavy fixture construction. Record a concrete shared-resource reason for
  any necessary exclusive classification. The unreviewed fallback is a runtime
  safeguard, not an acceptable final classification. Maintain the host inventory
  review regression and validate the affected scheduling scope; see the
  [parallelism review contract](tests/README.md#host-test-parallelism-review).
- Read the [test storage mandate](docs/Mandates/Test-Storage-Mandate.md) when
  creating or changing test storage. Use its shared allocation helpers; tests
  must not choose `/tmp` or hardcode their own temporary storage root.
- Discover suites and their exact routes with `tools/run-tests --list` and
  `tools/run-tests --help`. Choose coverage from the change and its regression
  risk first, then use `tools/run-tests` for the selected scope: `ui` for UI-only
  validation, `unit` for unit-only validation, or the required categories and
  quoted file/case selectors. Prefer the launcher's existing parallel scheduling
  wherever supported within that scope. Never expand UI-only or unit-only
  validation to `host` or `all` merely to obtain parallelism; test-file count
  alone does not justify unrelated checks or package builds. Direct
  `tools/run-unit-tests` and `tools/run-ui-tests` remain appropriate for narrow
  iteration or diagnosis. Preserve
  selectors and explicit UI timeouts; avoid `-x` or positive `--maxfail` for broad
  unit/UI passes because those diagnostic options retain serial execution. See the
  [scheduling contract](tests/README.md#all-established-regressions).
- Run `make build` when a change that could affect building or packaging the app
  is ready for validation, and again after further build-affecting edits. This
  includes product source and assets, package metadata, build/install recipes,
  and tools or generated inputs used by those recipes. Use `Makefile`'s
  `PACKAGE_SOURCE_FILES` and build rules to assess the scope, including build-tool
  dependencies that are not shipped. Run the relevant tests separately; a passing
  unit or UI suite does not establish that the package builds. Report a failed
  build or missing build prerequisite as unresolved validation. Changes confined
  to documentation or tests that cannot affect the build do not need this check.
- Use `tools/run-tests host` only when all host coverage is justified, and
  `tools/run-tests all` only when the entire established regression set is
  justified. Combine complete categories when each is required, sharing their
  report and package inputs. Use plain approved Make targets only as documented in
  the [approval contract](docs/Approval-Tools.md). Do not replace the launcher
  routes with generic pytest, interpreter or Make invocations, and do not start
  competing launchers against the aggregate's checkout lock.
- Quote test patterns and parametrized IDs. New privileged integration checks are
  argument-free `tests/integration/check_[a-z][a-z0-9_]*.py` files with applicable
  cleanup-safety coverage.
- Signal only explicitly spawned, identity-recorded processes. Before a
  host-integrated test terminates processes, pass its cleanup-safety regressions
  in isolation.
- Use only the documented artifact readers/exporters. Export graphical PNGs with
  `onpc-export-screenshot` and clean only explicit caller-owned `/tmp/onpc-*.png`
  files through `tools/cleanup-screenshots`.

## Setup

- `./setup.sh` is the sole public development setup entry point. Modes
  must be retryable, preserve unrelated configuration and fail on missing
  prerequisites. Tests and builds report missing prerequisites; they do not
  install them.
- Refresh helpers with `./setup.sh --test-tools-only` and rules alone with
  `./setup.sh --codex-rules-only`; restart Codex after rule changes. First install
  uses `./setup.sh --bootstrap-tools`. Do not refresh rules to fix bad quoting.
- Routine privileged setup uses the installed, pinned, default-deny `onpc-setup`
  helper. Do not use direct sudo, generic privileged interpreters, installer
  shortcuts or weakened ownership/policy checks.
