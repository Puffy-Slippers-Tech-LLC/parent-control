# Unattended execution

- Apply the repository-wide [approval contract](docs/Approval-Tools.md) to all
  work, including research, edits, builds, diagnostics, setup and publishing.
  Reuse session authorization; routine implementation decisions need no renewed
  approval. Human authorization is reserved for the contract's rare exceptions.
- Run authorized work fully unattended through existing agent rules, approved
  command prefixes and validated harnesses. Do not prompt for Codex or Polkit
  approvals. Correct quoting/command-shape problems; if required grants or
  prerequisites are missing, report the blocker without bypassing controls.
- Reuse category-wide grants; never add duplicate/per-directory rules, broader
  shell/interpreter/Git/Make/libvirt grants or prompts overriding global allows.
  Prefixes do not validate trailing arguments or environments. Honor denials and
  restrictive project/organization policy over older broad grants.
- Direct execution of executable project `tools/` commands is preapproved within
  authorized task scope.
  Invoke launchers directly; this grants no generic wrappers or additional scope.
- Use approved helpers outside the sandbox when sockets, Polkit or real ownership
  metadata require it. Check execution context before reinstalling tools; never
  disable ownership validation or use authentication fallbacks after denial.

# Project boundaries

- Start at [System-Design.md](docs/System-Design.md). Fix root causes reproducibly
  on clean computers; assume a new app unless specified otherwise. Use supported,
  maintained public code/APIs, not legacy, private or hacky substitutes.
  Preserve shared child-form/kiosk compatibility; add useful logging without PII
  (redacted labels such as `[Child user]` are allowed).
- Never edit or deploy the portal checkout from a client session, regardless of
  prior work/approvals. Request API changes through a client `docs/` handoff:
  reason, current/requested contracts, request/response examples, compatibility,
  release dependencies and acceptance checks. Report formatting, component names,
  metadata and attachments belong in the client; portal delivery stays generic.
- Classify new integrations under [package update activation](docs/Publishing.md#package-update-activation).
  Ship required [migrations](docs/SystemDesign/Data-Migration.md) before
  incompatible saved-data readers/writers.
- Choose implementation models by scope:
  quality first, weekly allowance second. Reassess each slice: Sol high/Standard
  for settled implementation; Astra for unresolved security, concurrency,
  ownership, difficult diagnosis or broad correctness review. No blanket
  Astra/high/max default or further settings approval; historical pins are records.

# Customer acceptance

- Tests must catch regressions. When a test detects changed app behavior or a
  mismatch with expected behavior, preserve the failure evidence, report a
  potential regression with expected and actual results, and ask the developer
  whether the change is intended before accepting it or changing expectations.
  Reuse explicit behavior-change authorization already given in the session.
  Never change, weaken, skip or delete checks merely to match current app behavior.
  Fix mechanical test issues automatically (such as broken test code, fixtures
  or harness crashes) when evidence shows the intended behavior check is
  preserved; a mismatch alone is not evidence that the test is wrong. See
  [failure handling](tests/README.md#handling-test-failures).
- Follow [E2E building blocks](docs/TestAutomation/E2E-Building-Blocks.md) and
  [E2E scenarios](tests/e2e/scenarios.json): operate and observe
  the installed app as a customer across all surfaces, without backend product
  probes or internal fault injection. Preserve completed unit/component/system
  tests, including mechanical install/upgrade/migration/removal checks.
- Prioritize the customer queue; deferred policy-acknowledgement design is no
  dependency. Add infrastructure only for a named blocked consumer. Measure
  completed scenarios and shrinking frozen remaining scope.
- [Functional GUI acceptance](docs/TestAutomation/E2E-Building-Blocks.md#functional-validation)
  uses public accessibility names/roles/states and real UI actions to verify
  customer results. Cosmetic defects, resolution/scale, screenshot similarity
  and fixed geometry cannot gate acceptance. Fail when required behavior or
  results are incorrect, interaction is blocked, or required information is
  inaccessible.

# Reads and edits

- Inspect search operands; quote all paths, regexes, patterns and URLs. Run reads
  directly with the tool's working directory and full filenames on one command
  line; no shell wrappers, substitutions, environment assignments or redirections.
- `rg -n 'regex' 'literal/path'` accepts quoted `--glob` filters anchored to the
  literal root. For any filename expansion use
  `tools/read-only search --path-glob 'path/prefix*' 'regex' 'literal/path'`
  or `tools/read-only files --path-glob 'path/prefix*'`; repeat the option for
  multiple patterns. Never pass wildcard paths directly to `rg`.
- Logs/journals and public read-only internet research are authorized, without
  writes. Fetch with `curl -fsSL 'https://example.com/path'`; no uploads, custom
  requests or output files. Correct command shape before escalating a read.
- For untrusted arguments or repeated escalated reads beyond ordinary
  `rg -n`/`sed -n`/`curl -fsSL`, use
  `tools/read-only <search|files|slice|sort|unique|gzip|fetch>` instead of broad
  saved utility grants. See [Approval-Tools.md](docs/Approval-Tools.md).
- Troubleshoot `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.events` with
  ordinary readers or `tools/diagnose`; never modify/delete logs or use raw
  privileged systemctl/journalctl. Use minimum necessary read-only escalation
  under existing grants. Recurring privileged diagnostics require reviewed,
  reusable, argument-validated entry points, not inline Python or broad grants.
- Edit text with native `apply_patch`. Validate Markdown with
  `tools/read-only links '<file.md>'`; count with `tools/read-only words '<file.md>'`.
  No inline Python, heredocs or unrestricted shells as substitutes.
- Retain useful evidence without one-off reports:
  report routine failures/fixes/verification in conversation or PR; keep run
  history in runner artifacts. Preserve useful reports/logs/artifacts. Revise
  current contracts and needed active handoffs, not incident histories in design
  docs. New evidence documents require an explicit request or ongoing acceptance/
  recovery need unmet by existing artifacts; a failure or fix alone is insufficient.

# Tests, artifacts and VM ownership

- Plain `make build`, `make check` and targets in `config/codex-tests.rules` are
  authorized. Use validated launchers for options; privileged Make and direct
  system-test/setup targets remain restricted.
- Discover categories with `tools/run-tests --list`. Use `tools/run-unit-tests`
  for unit/property/contracts, `tools/run-tests component` for private D-Bus,
  and fixed categories for other suites. Privileged integration/system/E2E uses
  `tools/run-tests <category>` or installed `onpc-test-runner`; unimplemented
  routes refuse. No generic pytest markers, Make arguments or Python substitutes.
- Quote test patterns/parametrized IDs. Non-VM UI tests use
  `tools/run-ui-tests --timeout <duration> [validated selections/options...]`.
  New integration checks are argument-free
  `tests/integration/check_[a-z][a-z0-9_]*.py` files with applicable cleanup tests.
- Signal only explicitly spawned, identity-recorded processes; never infer
  ownership from names, environments, runtime directories or host `/proc` scans.
  Before host-integrated tests terminate processes, pass their cleanup-safety
  regressions in isolation.
- Prefer unprivileged artifact reads. Otherwise use
  `pkexec /usr/local/libexec/onpc-test-artifacts <read|tail|list|stat|export> <absolute-path>`
  within [documented storage/log roots](tests/README.md); store new privileged
  artifacts there. Never substitute privileged readers/copy tools/interpreters.
- Export graphical PNGs only through
  `pkexec /usr/local/libexec/onpc-export-screenshot /tmp/onpc-graphical-smoke-<run>/testresults/<image>.png /tmp/onpc-<name>.png`.
  Resolve validation failures. Clean authorized temporary screenshots with
  `tools/cleanup-screenshots '/tmp/onpc-<name>.png' ...`: explicit caller-owned
  regular PNGs directly in `/tmp`, never logs.
- VM maintenance uses only
  `tools/test-vm <status|xml|start|stop|reboot|reset|screenshot|send-key>` with its
  pinned UUID/shared lease. No ownership bypass, other guests, snapshots, overlays
  or clones. Stop maintenance before system/E2E tests; reset is never a customer
  journey step.

# Setup and rules

- `./setup.sh` is the sole public development/VM-host setup entry point. Keep
  changes in appropriate modes and specialist modules scoped; Make aliases only
  delegate. Builds/tests report missing prerequisites instead of installing them.
- Modes must be retryable, preserve unrelated configuration and stop on failed
  prerequisites. Ordinary setup preserves accepted baselines. Cover orchestration
  repeat/failure behavior and update master help/docs. Explicit `--prepare-baseline`
  requires an off VM, deletes the existing baseline without restoring it and
  captures the current guest. Neither it nor guest-only `--prepare-vm` runs during
  ordinary host setup.
- Refresh helpers and Polkit/Codex rules with `./setup.sh --test-tools-only`;
  rules alone with `./setup.sh --codex-rules-only`. Global read rules live in
  `config/codex-read-only.rules`. Codex needs a restart with this checkout trusted;
  Polkit watches its rules directory. Do not refresh rules to fix command quoting.
- First installation uses `./setup.sh --bootstrap-tools`; administrator setup is
  a prerequisite to unattended work if no grant exists. Full setup bootstraps
  missing helpers before dependencies; repeats reuse the grant. Denied-installation
  repair requires that mode in an administrator-authorized root session.
- Routine modes use installed `onpc-setup`: fixed operations, pinned trusted
  checkout, default-deny Polkit action and noninteractive privilege checks.
  Invoking-user Git/venv setup stays unprivileged. No direct sudo, generic
  `pkexec python3`, privileged installer shortcuts or weakened policy. Grants
  trust maintained checkout tests/imports, not filename patterns alone.
