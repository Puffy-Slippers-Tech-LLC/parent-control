# Agent adapter proposal

Status: proposed design; adapter implementation is not part of this change.

The repository should select its coding agent solely from the checked-in
top-level `agent` field in [config/environment.json](../config/environment.json).
The allowed values are `codex` and `claude`. Changing that field should switch
all repository-owned coding-agent sessions through a shared adapter boundary,
while retaining the existing workflows, public launcher commands, acceptance
checks, task budgets and resource ownership.

The compatibility fix in [vm_config.py](../tests/integration/vm_config.py)
accepts the additional field as unused metadata. It does not validate agent
capabilities, select Claude, or change the existing Codex commands. Until the
proposal is implemented, both field values leave execution on the existing
Codex path. The remainder of this document describes future changes.

## Configuration and scope

The existing configuration contains:

```json
{
  "agent": "codex"
}
```

This is an excerpt, not a replacement for the host, branch, launcher and VM
configuration. To select Claude after implementation, change that one value to
`claude`. Do not add a provider argument to public or private launcher command
lines, an environment-variable override, a second selection file, or an
interactive agent picker. No executable path or arbitrary import comes from
this field: a fixed mapping selects one of two maintained adapter classes.

The selection covers `fix-tests`, `write-e2e`, `execute-plan`,
`sync-whatsnew`, their delegated workers/monitors/advisers/reviewers, supervised
commit sessions, and automatic merge/stash-restoration conflict resolution.
Future repository-owned agent callers must use the same boundary.
Agent-free tests, builds, diagnostics, deterministic Git operations and VM
helpers continue to work without either coding CLI installed or authenticated.
Editing this field cannot change the coding application already running the
developer's current interactive conversation.

The installed parent-control product has no coding-agent dependency. Keep the
adapter and its configuration in development infrastructure, outside the runtime
dependency and package payload maps.

## Current integration map

| Area | Existing coupling | Proposed change |
| --- | --- | --- |
| Configuration | [vm_config.py](../tests/integration/vm_config.py) owns the shared document reader; [vm_selection.py](../tools/vm_selection.py) exposes it to launchers | Keep one document parser; add strict live agent selection at the adapter entry point |
| Shared execution | [detached_launcher.py](../tools/detached_launcher.py) builds Codex commands, injects instructions, supervises processes and retries capacity failures | Retain ownership/supervision; delegate native commands, session protocol and model configuration |
| Conversation | [launcher_chat.py](../tools/launcher_chat.py) combines shared mailbox/status behavior with Codex app-server messages | Keep mailbox, status validation and input/result serialization shared; move Codex RPC into its adapter |
| Presentation | [launcher_render.py](../tools/launcher_render.py) consumes Codex-shaped events | Render a small common event format produced by either adapter |
| Repair | [fix_tests.py](../tools/fix_tests.py) pins Sol, validates the Codex model catalogue and supplies repair tiers | Request workflow roles and capability tiers from the selected adapter |
| E2E | [write_e2e.py](../tools/write_e2e.py) pins coordinator tiers, adviser roles and native configuration | Preserve its acceptance/escalation engine; resolve models and roles through the adapter |
| Ordinary plans | [plan_launcher.py](../tools/plan_launcher.py) embeds model defaults, delegation and capacity fallback | Keep plan selection and completion guards; pass structured session requirements |
| Translation | [sync_whatsnew.py](../tools/sync_whatsnew.py) builds read-only Codex sessions and translator agents | Preserve launcher-owned catalogue writes and read-only translation sessions |
| Git recovery | [launcher_git.py](../tools/launcher_git.py) and [launcher_worktrees.py](../tools/launcher_worktrees.py) launch pinned Sol sessions | Use the parent's selected adapter for dependent agent sessions; keep deterministic Git transactions shared |
| Policies and roles | [AGENTS.md](../AGENTS.md), [Execution-Plans.md](Execution-Plans.md), [tests/README.md](../tests/README.md), and agent-role TOMLs name Codex APIs/models | Revise the owning policies and render native role definitions from shared role requirements |
| Setup | [setup.sh](../setup.sh), [install_codex_rules.py](../tools/install_codex_rules.py), [setup_checkout.sh](../tools/setup_checkout.sh), and `config/codex-*` manage Codex rules/readiness | Add the selected agent's setup/readiness path without changing the public setup entry point |
| Remote and Watch | [launcher_controller.py](../tools/launcher_controller.py) and [extension.js](../vscode/onpc-watch/extension.js) check specifically for Codex on SSH startup | Resolve on the executing checkout, prepare its CLI environment and display the recorded agent |
| Supporting assets | Existing test doubles, skills, ignore rules, source archives and launcher reload inventories contain Codex assumptions | Adapt affected consumers without introducing a second workflow or unrelated test matrix |

## Adapter boundary

Use composition beneath the existing launcher engines, following the
[extension boundary](Execution-Plans.md#extension-boundary). Start with three
small modules: proposed `tools/agent_adapter.py`, `tools/agent_codex.py`, and
`tools/agent_claude.py`. These names describe new implementation files; they do
not exist as part of this proposal. Do not build a plugin framework or a generic
multi-provider orchestration service.

`agent_adapter.py` owns the common session request, fixed adapter selection,
workflow/role vocabulary, and normalized events/results/errors. Each concrete
adapter owns native CLI/SDK details and its supported model profiles. Shared
launcher code must not index into native argument lists or insert Codex `-c`
values. For example, translation requests a read-only session directly instead
of replacing the argument following `--sandbox`.

The proposed interface has three responsibilities:

| Operation | Input and output |
| --- | --- |
| Resolve | Read the executing checkout's configuration and return the fixed adapter for its validated `agent` value |
| Preflight | Check the executable, authentication/readiness and capabilities required by the workflow/role; return actionable errors without starting task work |
| Prepare session | Accept a typed session request and return native argv, environment, working directory and a per-session protocol handler for shared supervision |

The request carries the workflow, role, logical tier, permissions, prompt,
result schema, owned run directory, allowed extra directories, delegation
limits and any existing explicit model/effort setting. It also carries the
controller's immutable selection snapshot. The snapshot is internal state,
not a new command-line override. Pass it through existing controller/session
state rather than rereading unrelated checkouts inside every helper.

The protocol handler supplies initial input, decodes native output, accepts
follow-up messages, requests turn interruption, and finalizes a candidate
result. The existing supervisor continues to own subprocess creation, pipes,
recorded process identity, cancellation, bounded shutdown and reaping. An SDK
bridge, if needed, must remain an owned child and must not create an independent
daemon or untracked background sessions.

The adapter never decides that a task passed, operates a VM, advances a queue,
stages a file or commits changes. Existing workflow validators retain those
decisions under the [execution and test contracts](TestAutomation/README.md).

## Reading and changing the selection

Extend the shared configuration reader's allowlist for `agent`; retain its
duplicate-key and other structural checks. Legacy documents used for archived
state or agent-free fixtures may omit the field. When present, the eventual
reader validates that it is exactly one of the two lowercase strings. A live
agent session additionally requires the field: a missing, invalid or unreadable
selection fails before spawning an agent. Do not infer Codex from an old
checkpoint, the CLI on PATH, a model name, or a personal configuration file.

Resolve branch/host dispatch first. The checkout that actually executes the
workflow reads its own checked-in `config/environment.json`; a client or
another worktree cannot override it through forwarded launcher arguments.
Normal Git synchronization distributes the setting. If checkouts temporarily
disagree, report the executing checkout and its selected agent rather than
silently applying the client's value.

Read the selection before each new logical agent session and pin it through
that session's turns, delegated helpers and bounded capacity retries. Dependent
Git close-out/resolution sessions inherit the originating selection until their
owned operation reaches a clean boundary. A config edit during work does not
kill the current agent or reinterpret its results. The next independent agent
session reads the new value after prior children and owned cleanup finish.

On restart, reconcile any interrupted operation through existing ownership and
recovery routes before starting another agent. With no live agent left, resolve
the current configuration for the new recovery/continuation session, preserving
the transaction journal and unfinished task. No old provider must remain
installed solely because a checkpoint records it. Reattachment to a live run
observes its pinned session and does not change its selection.

Record the actual agent, native model, native effort and logical tier in existing
session metadata and usage records. Retained selection is provenance, not an
alternative configuration source. Legacy records remain readable with unknown
agent provenance; never relabel old sessions as Claude. Switching preserves
accepted tasks, remaining work, session counts, model-promotion history, checks,
owned edits and pending close-out. It does not resume the other agent's private
conversation or reset any allowance.

Stop, cleanup and observation must remain available even when the new selection
is invalid or its CLI is missing. Those operations use retained owner identities
and must not depend on a fresh agent preflight. Likewise, help, listing and
agent-free checks must not require agent login or a model request.

## Native transports and common results

The Codex adapter initially extracts the existing behavior: batch `codex exec`,
interactive `app-server`, schema output, policy overrides and role configuration.
Preserve its current permissions and fresh-context behavior while moving the
code. Codex's documented batch interface supplies JSON events and
schema-constrained output. See [OpenAI non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

The Claude adapter uses `claude -p` for batch sessions, with structured JSON
output and the supplied JSON Schema. Extract the `structured_output` payload
from the native result envelope; a missing payload or unsuccessful native result
is not a valid workflow response. For interactive sessions, use the supported
Claude Agent SDK streaming-input interface behind the owned transport bridge.
It supports follow-up input and interruption; do not emulate Codex RPC names
or treat restarting a one-shot CLI as equivalent to steering an active turn.
See [Claude programmatic execution](https://code.claude.com/docs/en/headless)
and [streaming input](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode).

Both adapters emit a bounded common vocabulary: session/turn lifecycle,
assistant text, tool/command start and completion, command-output deltas, file
changes, delegated-agent activity, usage, candidate result, and classified
failure. Keep native details inside the adapter or sanitized diagnostic payloads.
Unknown events may be displayed as inert diagnostics; they cannot control
execution. Suppress private reasoning content in the common presentation path.

Keep the existing workflow result schemas and validators, including
`plan_response.schema.json`, `write_e2e_response.schema.json`,
`fix_tests_response.schema.json`, and `sync_whatsnew_response.schema.json`.
The shared result path remains `agent-result.json`; normalize native output
before handing it to existing response validation. Never accept a successful
process exit, partial stream, tool result, or helper's final message as the
coordinator's completed workflow response.

Preserve the current mailbox gate: drain pending user input before accepting
completion; bind steering/interruption to the current session and turn; finish
interrupted nested-test cleanup before continuing. An interrupt must not become
completion or a fabricated structured response. If Claude's native interruption
or message-queue semantics differ, reconcile them inside its adapter and expose
only the shared behavior after qualification. Do not advertise interactive
support before that behavior works.

Normalize usage without inventing missing counters or billing equivalence.
Keep native model identity and provider-reported scope; do not assume cache,
reasoning or delegated-agent tokens are counted identically by the two CLIs.

## Models, roles and repository policy

Workflows retain the reasons and timing for escalation. The adapters map the
same role/tier request to supported native model/effort pairs in one place per
agent. Required roles include coordinator/implementer, routine worker,
read-only monitor, bounded adviser, independent backend reviewer, translator,
commit helper and conflict resolver. Preserve per-workflow restrictions on
delegation, concurrency, depth, freshness and write ownership.

Preserve Codex's current profiles during extraction. Define and qualify a finite
Claude profile table against the installed CLI and authenticated account;
do not mechanically copy Sol/Astra model names or assume effort labels denote
equivalent capability. Exact Claude profiles and their supported efforts must
be settled before enabling their consuming workflow. Missing capability is a
preflight blocker, never a silent downgrade or a reason to invoke Codex.

Existing public `--model` and `--effort` options, where already present, remain
within the configured agent. They cannot select a different adapter. A model
override incompatible with the selected agent is rejected clearly. A retained
override from an older run is reported and reconciled through the existing
resume policy; it cannot silently force the old agent or be discarded. No new
launcher parameters are needed for adapter selection or model profiles.

Two owning policies require coordinated revisions before Claude execution:

1. [Execution and delegation](Execution-Plans.md#execution-and-delegation)
   requires an actual Codex goal, including for helpers, and rejects replacing
   it with prompt text. Retain the simplicity objective as shared policy and
   retain native goal activation for Codex. Explicitly define the Claude
   alternative in that owner, with its real guarantees. Do not claim that prompt
   injection or a launcher metadata field implements the Codex goal API.
2. [Core backend requirements](../AGENTS.md#product-boundaries) currently pin
   implementation and independent review to OpenAI models. To meet the single
   `agent` selection requirement across the whole repo, revise them to require
   qualified implementation and an independent reviewer within the selected
   agent, with native profiles defined by each adapter. Preserve the review's
   read-only scope, fresh context, pause/join discipline and findings resolution.
   Do not retain a hidden Astra call when `agent` is `claude`, or silently weaken
   the existing mandate before its owner is changed.

These are proposed policy migrations, not exceptions granted by this document.
Update conflicting prompts, role TOMLs and active contract consumers together.
Keep shared instruction text separate from native configuration so equivalent
role restrictions do not drift across implementations. Native agent tools and
lifecycle operations may differ; render the appropriate delegation instructions
rather than requiring Claude to call Codex's `spawn_agent` API.

## Permissions, instructions and setup

Keep the [approval contract](Approval-Tools.md) and validated public helpers as
the authority. Codex rules and Claude permissions have different formats and
execution semantics; do not translate them by textual substitution or enable
permission bypass to make a workflow work.

The Claude policy should allow the required maintained commands and workspace
edits, deny unauthorized operations, and refuse unapproved requests without an
interactive prompt. `dontAsk` denies calls that would otherwise prompt; it is
not filesystem isolation. Configure the appropriate sandbox and tool restrictions
as well. Read-only roles must prevent mutation through shell and external tools,
not merely omit Edit/Write or rely on a read-only prompt. Preserve external
directory limits needed for Git recovery and the separate Polkit boundary.
See [Claude permissions](https://code.claude.com/docs/en/permissions).

Share `AGENTS.md` rather than maintaining a second copy. Configure Claude's
project-instruction loading explicitly; a small tracked `CLAUDE.md` importing
`@AGENTS.md` is a compatibility option. Make the commit and goal skills available
through the selected agent's supported discovery path, with native-tool wording
where needed. Disable unwanted automatic memory/history reuse and inherited
conversation identities while preserving legitimate authentication and managed
policies. See [Claude instruction loading](https://code.claude.com/docs/en/memory).

Keep `./setup.sh` as the sole development setup entry point. Integrate selected
agent policy preparation and readiness reporting there; do not install or
authenticate a coding CLI automatically during tests or launcher preflight.
Preserve existing personal settings, trust choices and inactive-agent policy
files. Keep credentials, user paths, local permission decisions and session
state out of Git. Add narrowly allowlisted shared Claude assets and ignore
private state, following the existing Codex portability boundary.

The privileged setup dispatcher currently exposes a fixed `codex-rules`
operation. Do not silently repurpose its privileged authority for Claude
installation or general file writes. Route new user-owned configuration outside
the privileged dispatcher; any genuinely necessary managed host policy needs
an explicitly scoped installer and the existing setup/approval process.

## Remote execution, Watch and failure handling

Replace Codex-specific SSH PATH checks in both launcher dispatch and Watch
controls. Resolve the executing checkout and its configuration before checking
its selected CLI; prepare native user-local installation paths as needed without
sourcing arbitrary interactive shell startup files. The selected agent's login
must belong to the actual remote execution account. Client authentication and
plugin connections are not transferred to the server.

Watch continues to observe the same bounded transcripts, run identities and
mailboxes. Add the recorded agent to session metadata alongside native model
and effort. Keep start/resume/reload commands unchanged; restarting from Watch
reads the executing checkout's configuration at the same safe boundary as
terminal execution. Observation and stop actions do not require a coding CLI.

Normalize failures into capacity, rate limit, authentication, permission denial,
provider refusal, unsupported capability, malformed result and process/transport
failure. Preserve useful provider reasons without exposing credentials or private
conversation state. Existing response repair applies only to successful turns
with invalid workflow results; it must not reinterpret a provider refusal as
something the next model should work around.

Use bounded retry policy only for qualifying transient failures, accounting for
retries already performed by the native CLI/SDK. Keep capacity retries within
the same logical session and original task allowance. Any model fallback stays
within the configured agent's explicitly supported profile policy. Exhaustion,
missing authentication, refusal or missing capabilities must not trigger a
cross-agent fallback. The selected agent remains the config value.

## Delivery and validation

Implement incrementally without maintaining parallel workflow engines:

1. Keep the compatibility fix independent: accept the extra configuration key
   while leaving it unused. This allows ordinary tools to keep working before
   any adapter is ready.
2. Extract the existing Codex behavior into the common interface and Codex
   adapter. Replace native argument manipulation in every caller; reconcile the
   owning policy documents and native role profiles before activating selection.
3. Implement Claude batch and interactive transport, role configuration,
   permissions and preflight. Wire all agent callers through the shared resolver.
   Do not ship a selection that affects the coordinator but leaves translation,
   backend review or Git recovery silently using another agent.
4. Complete setup, SSH, Watch, skills and documentation integration. Update
   controller reload/dependency inventories, including
   `plan_launcher.RESPONSE_VALIDATOR_SOURCES`, so running controllers load
   changed adapter code at owned reload boundaries.
5. Enable configuration-driven selection only when each affected workflow
   satisfies its preserved contract for both agents. Missing support must be
   reported explicitly rather than substituted with the other agent.

Apply the [test scope mandate](Mandates/Test-Scope-Mandate.md) and
[test maintenance](../tests/README.md#all-established-regressions). Preserve and
adapt existing critical execution/ownership regressions and native process
doubles. Do not add tests for ordinary infrastructure branches, mirrors of the
profile table, or Watch widgets. New non-product tests require the explicit
authorization in [AGENTS.md](../AGENTS.md#tests-and-acceptance).

For implementation acceptance, exercise the actual shared boundary with finite
passing/failing results: selection from the executing checkout, ignored external
overrides, fresh sessions, correct schema/result ownership, pending input at
completion, interruption and cleanup, refusal versus transient retry, and
resume across a configured switch without losing work or resetting budgets.
Reuse existing checks where possible. Perform bounded real-agent smoke checks
for both adapters using a disposable checkout and maintained ownership/storage
routes; CLI help or synthetic events alone do not establish native compatibility.
No VM/product installation is required merely to qualify the agent transport.

Verify that the proposed development assets stay outside
`Makefile.PACKAGE_SOURCE_FILES` and product-only archives; review
[source exclusions](../debian/source/options) if adding `.claude` or
`CLAUDE.md`. Run `tools/build_package.py` after the final implementation edit
that can affect building/packaging, as required by AGENTS.md. Pure proposal edits
need Markdown link checks, not a package build or new tests.

Completion means that editing only `config/environment.json` selects the agent
for every repository-owned agent session, with no new launcher parameters,
hidden provider fallback, acceptance changes, or lost recovery state. This
proposal itself neither activates selection nor changes the current model,
goal, review or approval contracts.
