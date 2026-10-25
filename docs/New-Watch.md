# Watch in a VS Code editor tab

## Objective

Implement the entire Watch application as a VS Code editor tab, like Markdown
Preview. The tab must contain the terminal panels, host UI previews, VM viewers,
checkout navigation and resource statistics. Opening a terminal tab that merely
launches the existing GTK window does not meet this requirement.

This is an implementation brief for a future session. Start that session with:

> Implement docs/New-Watch.md.

Follow [repository instructions](../AGENTS.md). This file records the requested
outcome; existing contracts linked below own their detailed rules. No Watch
implementation is part of writing this brief.

## User experience

- Provide a Command Palette command named **Parent Control: Open Watch**.
  It starts or connects the necessary observation backend and opens Watch in
  an editor tab without requiring an earlier `make watch` invocation.
- Repeated invocation reveals the existing Watch tab for that VS Code window
  rather than creating duplicate viewers or backend processes.
- Support ordinary editor placement, including splits and moving between editor
  groups. The user can drag Watch outside the main VS Code window or use
  **Move into New Window** to place it beside the editor or on another monitor.
  This floating window remains part of the VS Code session; independent execution
  after exiting VS Code is not required.
- Preserve the displayed session, selected tabs, draft input and scroll position
  when moving the tab or switching away and back. Observation reconnects cleanly
  when necessary without restarting tests or losing the current draft.
- Opening, closing or moving Watch does not start, stop or otherwise take
  ownership of tests or VMs. Explicit existing stop and session-input actions
  retain their current meaning and guards.

## Feature scope

Preserve the behavior described by
[Watching host UI tests](../tests/README.md#watching-host-ui-tests), including
the current terminal-tab additions:

| Area | Required behavior |
| --- | --- |
| Terminal | **Run Status** and **Session** tabs; live pipeline/test output; independent transcript, draft and scrolling; copying and existing stop controls |
| Session | Active launcher transcript; model/effort and lifecycle information; interactive messages, interruption and continuation; pending developer decisions for batch sessions; clear idle state |
| Checkouts | **All** and individual branch scopes; related worktree discovery; correct checkout identity even when branch names match; combined terminal sections and retained finished output |
| UI and VM viewers | Shared flat tab row and combined grid; individual views; current activity/progress; dynamic registration, idle/offline states and reconnects |
| Layout | Resizable terminal/viewer split, existing ordering and selection behavior, responsive previews and resource statistics |

Use that owning contract for the detailed ordering, frame-rate bounds,
observation lifecycle and cancellation behavior rather than copying it into a
second specification. Implement functional parity; identical GTK styling is not
required. Preserve the existing `make watch` workflow during migration and
document how it relates to the completed VS Code entry point. Maintaining two
independent versions of the watch logic is not a goal.

## Repository ownership and setup

- Keep extension source, web UI, dependencies, build configuration and usage
  documentation in this repository, maintained with the Watch backend.
- Use `./setup.sh` as the public development setup route to build and locally
  install/update the extension. Integrate with its existing modes rather than
  introducing a separate setup procedure. Ordinary Watch launch must not install
  dependencies.
- No separate extension repository or Marketplace publication is required.
- Keep checkout selection explicit and correct across worktrees. The extension
  must connect to compatible code from the intended checkout rather than silently
  using a stale backend from another location. Report actionable setup or
  compatibility errors.
- This is development tooling. It does not require installing the Parent Control
  product on the development host or changing product packaging/runtime behavior.

## Implementation direction and reuse

Use a web frontend in a thin VS Code webview extension. Rebuild the GTK
presentation for the web while reusing existing observation, discovery, output
and session machinery. A browser terminal component may preserve the existing
terminal renderer and input behavior; choose the simplest maintained integration.
Do not build another test runner or VM controller.

At the time of this brief, the working tree contains ongoing terminal/session
changes. Inspect their current state before implementation, preserve that work,
and integrate its final interfaces rather than overwriting it or assuming it is
already committed and accepted.

| Existing code | Intended reuse |
| --- | --- |
| [watch_output.py](../tools/watch_output.py) | Output following and the new `SessionOutput` discovery, transcript following and guarded input routing |
| [launcher_session.py](../tools/launcher_session.py) | Extracted `SessionPanel` transcript/composer rendering, editor and caret behavior where a web terminal can reuse it |
| [launcher_render.py](../tools/launcher_render.py), [detached_launcher.py](../tools/detached_launcher.py) | Session transcript publication and session identity/lifecycle metadata |
| [launcher_chat.py](../tools/launcher_chat.py) | Existing conversation controls and expected-session checks |
| [watch_checkouts.py](../tools/watch_checkouts.py) | Checkout/worktree discovery and identity |
| [ui_watch_transport.py](../tools/ui_watch_transport.py), [e2e_watch_viewer.py](../tools/e2e_watch_viewer.py) | Existing UI/VM feed acquisition and transport boundaries; separate any reusable feed logic from GTK presentation as needed |
| [watch_viewer.py](../tools/watch_viewer.py), [ui_watch_viewer.py](../tools/ui_watch_viewer.py) | Current interface behavior to port; replace GTK widgets, VTE integration and GTK event wiring |

The conversation's rough estimate of 70–80% reuse applied only to the active
terminal/session additions, assuming a web terminal. It is not an estimate for
the entire Watch application or a constraint on the final implementation.

Keep private feeds and existing owner/session validation behind a narrow bridge.
The webview must not gain arbitrary shell, file, VM or process-control access.
Keep frame transport bounded, avoid hidden-view rendering work and preserve
useful diagnostics. Closing the viewer releases only its owned observation
resources, allowing it to reopen against a still-running workflow.

## Reading and validation

Begin with the Watch contract above and the listed source entry points. Follow
[Approval tools](Approval-Tools.md) for setup and command routes and
[Execution plans](Execution-Plans.md) if implementation needs a large execution
plan. Read the applicable
[UI automation mandate](Mandates/UI-Automation-Mandate.MD),
[VM mandate](Mandates/VM-Mandate.MD) and
[test storage mandate](Mandates/Test-Storage-Mandate.md) before work that triggers
them. Do not change the separate product E2E queue merely to implement this tool.

Completion requires a working repo-managed extension and a bounded development
smoke run demonstrating:

1. Setup installs/updates the local extension, and the command opens the complete
   Watch interface without a prior `make watch`.
2. Run Status and Session display a real existing workflow; input and stop actions
   reach only the displayed owner/session through existing guarded routes.
3. Checkout scopes and available host UI/VM feeds behave as specified, including
   idle/disconnected transitions and reconnection.
4. Watch can move into a floating window and back, retain its state while hidden
   or moved, and close/reopen without interrupting the observed workflow.
5. Viewer-owned resources settle on close, and usage/setup documentation reflects
   the delivered behavior.

Follow the [test scope mandate](Mandates/Test-Scope-Mandate.md): validate this
development tool through existing consumers and bounded smoke use, maintain
affected existing coverage, and do not add tool UI tests.
Select the lowest effective existing checks through
maintained launchers. Follow repository build requirements if edits affect
building or packaging. Report unavailable prerequisites and unverified behavior
as unresolved; source review alone does not demonstrate the working integration.
