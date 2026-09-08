# Unattended implementation sessions

The repository launcher runs one fresh `codex exec` per coherent implementation
slice, then starts the next session after a verified handoff and cleanup. It
continues until the [master checklist](Test-Automation.md#unfinished-tasks) is
complete, a blocker needs outside input, or you request a stop.

Start from this checkout in a terminal:

```sh
tools/codex_slices.py start
```

This returns your shell prompt and starts a detached local process. Live Codex
messages, commands, command results, changes and tool updates continue to appear
in that terminal as the CLI emits them. The launcher renders a text stream,
not the interactive Codex screen. Session output is not written to a log.
The process can keep running after you close the terminal; output after closure
is discarded. Starting without a terminal also discards live output. Use `run`
in a dedicated terminal for uninterrupted viewing and another terminal for
`status` or `stop`.

The default has no slice-count or overall time limit. The computer
must remain powered on and awake, Codex authentication and usage capacity must
remain available, and the host's existing test authorization must remain valid.
In particular, the project's Polkit grants require an active local administrator
session; detaching the launcher does not provide authorization after logout.
This launcher does not install a boot service or restart itself after a reboot.

For an initial one-slice run, use `start --max-slices 1`. To watch the launcher
in the foreground, use `run` instead of `start`.

```sh
tools/codex_slices.py status
tools/codex_slices.py stop
```

Help (`tools/codex_slices.py --help` or `-h`) and `status` have maintained
inspection-only Codex rules. Use the executable directly, without a `python3`
prefix; setup renders relative and checkout-absolute forms. Starting or
controlling the loop still needs authorization for that work. Use the native
`apply_patch` tool for workspace handoff edits. See the
[inspection and editing contract](Approval-Tools.md#launcher-inspection-and-workspace-edits).

`stop` requests a stop at the next safe slice boundary. It does not terminate
Codex or a running test. In foreground mode Ctrl+C has the same behavior. Start
again with the original command to continue from the saved documents.

## Cumulative session summaries

After each session exits, the launcher appends one report to
[Test-Automation-Slice-Summary.md](../Test-Automation-Slice-Summary.md). This is
the durable history to read after leaving the launcher unattended. Each report
contains its session number, completion timestamp in UTC to the minute, elapsed
duration rounded up to whole minutes, outcome, settings, completed work,
verification and cleanup, next action, and estimated sessions/minutes remaining
for the named current task. Estimates include their basis and uncertainty;
unsupported estimates are explicitly unknown. They are not execution deadlines.

The launcher opens the document **write-only, in append mode**. It never reads,
summarizes, rotates, truncates or rewrites earlier entries. Session numbering is
kept in control state, without scanning the log. Workers are instructed to
exclude this file from reads, searches and diffs; only the compact task handoff
is carried forward. The final response contains the new summary, and the
supervisor adds measured timing and appends it before launching another session.

Blocked and failed sessions get an end entry too; missing/invalid reports are
marked unconfirmed with unknown estimates. A transient retry gets its own entry.
If writing a summary fails, the loop stops for review. Power loss or forcibly
killing the supervisor can prevent its final append; the recorded active state
requires reconciliation. No in-session chatter is appended to this document.

## What carries between sessions

The [unattended prompt](Unattended-Prompt.md) authorizes the documented successive
slices and their model/effort settings when you launch the run. It overrides the
interactive “Go ahead” pause for that run. Ordinary interactive sessions keep
their existing confirmation procedure. Execution policies and actual denials
continue to apply.

The [implementation workflow](Implementation-Workflow.md) still owns selection,
scope, verification, acceptance and the compact handoff. Each worker reads
Continuation.md, the relevant active task and current files. The supervisor
never resumes or forks the previous conversation and never sends its transcript
to the next session. Standard project instructions and user configuration still
load normally. Every worker uses `--ephemeral`, so Codex does not persist its
session rollout to disk. Recovery relies on the task handoff, operation evidence
and control metadata, rather than a saved conversation.

The supervisor pins every slice to `gpt-6-astra` with `high` reasoning effort
in the launcher code. Continuation.md records these settings for the handoff:

```text
- Settings: **`gpt-6-astra` / `high`**, pinned by the slice launcher.
```

Workers maintain that line and the task handoff; edits to the line cannot change
the launch settings. There is no model substitution. The pinned model must be available to
the signed-in account. Slice budgets remain review points, so an active VM
attempt can exceed 30 minutes while it finishes collection and cleanup.

## Completion and interruption

Each worker returns structured status, progress, cleanup and summary fields. The
supervisor requires a successful completed CLI turn and validates the result.
It checks the authoritative checklist before accepting completion. Empty,
malformed or deleted task entries cannot make a running backlog complete.
The model must still perform the task's acceptance checks: checkbox validation
alone cannot establish test correctness.

Only one supervisor/worker pair can hold this checkout's loop lock. The loop
does not lock out independently opened editors or interactive Codex sessions;
let it own implementation of this backlog while it runs. Existing guarded test
launchers continue to serialize VM access. Source changes are kept in the same
checkout, including uncommitted changes; starting a session does not reset Git.

An explicit transient API failure before any tool use is retried with increasing
delay, capped at one hour. The default permits 12 consecutive retries; change
this with `--max-api-retries N` (0 disables retries). A tool-using interrupted
turn, missing handoff, uncertain cleanup, authentication failure or no progress
stops for review. The launcher does not retry an uncertain VM operation.

For a normal `blocked` result, resolve the concrete issue in the active task
handoff and start again. For `launching`/`running` state without a live loop, or
`needs-review`, first reconcile the recorded attempt, current task handoff and
any owned operation using the workflow and guarded diagnostic tools. Finish/reconcile its
collection and cleanup, update the handoff, and then use:

```sh
tools/codex_slices.py start --reconciled
```

This is an operator acknowledgement, not a cleanup command. It still refuses
an occupied lock and never kills a process or overrides VM ownership. Do not
delete locks, state, or logs to bypass a refusal.

## Prerequisites and progress records

Use an already installed, signed-in Codex CLI with `exec --approve-for-me`,
`--ephemeral`, `--json`, `--output-schema` and `--output-last-message` support. The launcher
checks these flags before running. It uses automatic approval review with the
workspace sandbox and retains existing user/project rules. Account and managed
policy must permit that mode; denied actions remain blocked. Existing machine
preparation remains through [setup.sh](../../setup.sh), as described in the
[approval guide](Approval-Tools.md). The launcher installs no dependencies or
permission rules.

Control metadata is private to the invoking user under the Git-ignored directory
`output/codex-slices/`: `state.json`, append-only `launcher.log`, and a unique
directory per attempt with the final structured response. Lifecycle events
include timestamps, CLI thread IDs, exit status and token counts. `status` also
shows the session count and latest completion time, duration and outcome. Raw
CLI stderr, command output and in-session assistant prose go only to the live
terminal, including for detached `start`; they never go to `launcher.log`.
The cumulative summary document is ordinary repository documentation, so final
reports must contain no PII or secrets. Existing task evidence and application
logs follow their own retention rules. Shell redirection or terminal recording
can still capture what you choose to display.

The host-safe supervisor regressions use a fake local Codex executable:

```sh
tools/run-unit-tests tests/unit/test_codex_slices.py -q
```

No live model, installed-system test or VM is used by these regressions. This
is development orchestration; package activation is `none` and no application
data migration applies.

Official interfaces: [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
documents scripted runs and structured output;
[automatic review](https://learn.chatgpt.com/docs/sandboxing/auto-review) describes
approval handling and denials.
