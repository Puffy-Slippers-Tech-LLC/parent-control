# ONPC Watch

Open run status and live UI/VM viewers in a VS Code editor tab.

Run `./setup.sh --watch` as your desktop user to install or update this extension.
Reload VS Code after updating it. Open a trusted ONPC checkout and click the
full-color product logo at the right end of the editor tab headers. Its tooltip
is **ONPC: Watch**. The button appears
automatically for ONPC clones and Git worktrees, regardless of branch, and hides
when no ONPC checkout is open. Adding or removing workspace folders updates it.
The bundled icon is a copy of `data/app_logo_titlebar.png`.
You can also press **Ctrl+Shift+P** and select **ONPC: Watch** (`onpc.watch`).
Repeating the command reveals the existing tab. Multiple workspace roots offer
a checkout picker.

The tab starts with a 30:70 left/right split. Drag the divider to resize it;
the tab remembers its ratio. Focus the divider and use the arrow keys to resize
with the keyboard, or double-click it to restore 30:70.

The left panel shows **Run Status** across related Git worktrees, using shared
runner discovery and the pipeline dashboard. Active worktrees
share the panel in equal sections initially. The horizontal dividers can be
dragged to resize adjacent sections, or focused
and adjusted with Up/Down. The icon immediately before each copy button toggles
**Collapse** / **Expand**. Collapsing leaves only that launcher's title bar, tabs
and buttons; expanded sections fill the remaining height. Expanding restores the
selected tab. Inactive launchers (finished, failed or stopped) collapse by default,
including when a running launcher exits. A new active run expands by default.
Manual expansion, collapse and resizing survive live refreshes until the next
run or activity transition. Sizes last while Watch is open.
Dividers remain active beside collapsed sections; resizing expands them and
restores their selected tabs.
When a launcher exits for any reason, its
section and all four tabs retain their contents, including while other worktrees
remain active. Reconnecting restores the latest retained run in each idle
worktree from its existing run files. Session input is disabled once its owner
exits. Retention uses existing run files and reader memory; it adds no disk persistence.
Each title, e.g. `[main] fix-tests`, keeps **Status**, **Launcher**, **Error** and **Session**
links at its right end. When narrowed, the title truncates down to five characters
plus an ellipsis, e.g. `[work...`. Further narrowing moves the title and action
buttons onto the first row and all tabs onto the second row. As that row narrows,
the tabs wrap onto additional rows until they stack vertically. Wrapped tabs have
equal widths and centered text. The left panel's minimum width fits both the
shortened title with its action buttons and the widest tab below it. Hover over a
truncated title to see its full text. The name comes from the launcher's `current.json`
publication, including custom plan launcher names. Older runs without a published
name show `launcher` until their next start, attachment or reload request.
**Status** shows the current run status, **Launcher** shows
the launcher terminal output, **Error** shows the shared launcher's **Last Error**
and **Status** fields with the same colors and elapsed ages, and **Session** opens
the session transcript and chat.
For `fix-tests`, the link shows **Session 1**, **Session 2**, and so on for
successive agent sessions repairing the same case. The number remains visible
between sessions and during verification. Once the repair is accepted and closed,
the link returns to struck-through **Session**; the next case starts at **Session 1**.
While an agent repairs an integration check, its **Status** row ends with
` | Session x: <duration>`, using that session's elapsed time and the shared
`01:25` / `3h 45m` duration format. The suffix disappears when the session finishes.
The preceding check duration includes the whole case, including repair sessions
and retries; the session duration measures only the current agent session.
For `fix-tests`, Last Error includes the failing check, the runner's error text
(or a readable summary of a structured failure, falling back to a bounded text
output tail), and its output-log path. Full JSON results remain in that log. Reload launcher
changes with `tools/fix-tests --reload`; `./setup.sh --watch` updates the extension.
The links remain available in every view, including while idle. The copy icon
before **Status** copies the current tab's body as plain text to the clipboard;
in **Session**, it copies the displayed transcript.
For every execution-plan launcher, including `write-e2e`, **Status**
starts with **Total Tasks: completed/unfinished/total**
and **Total Duration**, using the shared launcher counters and colors. A divider
spans the panel above the completed task recaps and current task/session rows.
The **Total Tasks:** and **Total Duration:** labels are bold. When the whole plan
finishes, the summary adds **Ended:** with the local completion time (`HH:MM`),
and the launcher title, including `(finished)`, turns green.
For every execution-plan launcher, completed and current task headings end with
` | <duration>` from the retained task clock across sessions. The session summary
ends with ` | <duration>` from its owner session clock.
The **Session** link shows **Session N** for the current task, including between
sessions and while awaiting an answer; it resets when that task completes.
Every execution-plan launcher inherits the shared pending-input controls,
including after restarting into an unanswered question.
While waiting for input, the Status body shows
`Paused - waiting for your answer (mm:ss +10m)` for timed questions.
The waiting text flashes in the same red as stopped/blocked statuses; the deadline
counts down every second from the current prompt's deadline. Answering removes
that timer; a new prompt starts a fresh countdown. Questions without a deadline
show `Paused - waiting for your answer (no timeout)` in the Status body.
Each click on **+10m** in
the Status body adds ten minutes to the current question's deadline, including
the launcher's actual wait. Questions without a deadline have no extension link.
**Session** is a blue, underlined link with a hand cursor. It replaces that
worktree's status with the shared launcher session transcript, chatbox and
model/effort footer, including the Simplified toggle. The transcript includes
sent prompts and agent messages. Agent prose streams while it is being written;
the completed message replaces its provisional text, including any corrections.
Only completed messages enter the saved transcript. Launcher status metadata and
structured workflow results wait for completion before being interpreted.
Command and tool result bodies are hidden in
both modes; activity names remain visible and saved transcripts retain results.
Simplified mode collapses command activity to one clipped line; turn it off to
see each activity with its original line breaks. Successful Read/Search exploration shows
the activity only; file contents and search matches stay out of both views.
The toggle also works on the retained transcript after the launcher finishes.
Click **Status** to return to run status and its waiting countdown.
The space before each link is outside its underline.
Waiting for input flashes unless reduced motion is
enabled. Enter sends chat directly; there is no Send button. Shift+Enter or
Alt+Enter inserts a new line. Input is
routed only to the displayed, still-current launcher session.
Recording links in **Session**, **Status** and **Error** open through GIO using
the desktop's default video application for local sources. SSH sources transfer
the selected recording on demand and play it in a VS Code video tab. Inline
remote videos are limited to 64 MiB; larger recordings remain available on the
source host. Remote error logs open as text in the editor (up to 2 MiB).
Artifact transfer does not create local test-output copies.
Repair case totals show green completed, red failed and total counts. The failed
count is underlined; click it to open the cumulative `errors.md` in the editor.

The right panel contains the shared All grid across checkouts, UI worker and VM tabs,
VM progress, filtered command output and host resource usage. Screens are view
only. Tiles and viewer tabs group by worktree in the left panel's current order,
following changes on each refresh. Worktrees without a displayed run follow those
shown on the left. Start tests through the usual launchers. Select an idle VM tab to wait for
its next run. The Reconnect button restarts this tab's source connections.

The fixed **Run Time** tab follows **All**. It loads logged VM case durations only
while selected, refreshes the data once per minute, and unloads its body when
another tab is selected. Selecting it again loads fresh data immediately. The selectable,
full-width table keeps one latest duration and recording per case/VM pair, folded
into one row per case. **Case ID / Title** shows a **+** when multiple VMs exist.
Click it to expand a tree of `VM name | Run Time | ▶` children; **-** collapses it.
Children sort by their raw duration, longest first, before display rounding.
The folded recording button and the row's **VM name** and **Run Time** columns
use the slowest child. Cases also sort by that child's raw duration, longest first.
Durations use seconds below one minute (`20s`) and rounded whole minutes otherwise
(`12m`). Run time includes VM preparation
before the first selected case starts, matching the recording's preparation
boundary. Older timings use the linked recording's saved duration as a lower
bound when preparation was omitted. Repair sessions and earlier retries
are excluded; system lifecycle phases in one execution attempt are added together.
New lifecycle recordings join those phases into one video instead of retaining
only the final phase. Existing short recordings require a new execution to replace them.
Rows update only after all selected phases of a case finish. Unfinished attempts
publish no partial row; an earlier completed duration remains until replaced.
Case links open the existing case file in a new editor tab. The recording icon
uses the existing default desktop viewer route (or the SSH video tab). The
**Description** column shows a one-line scenario summary with an expand/collapse
chevron at its end. Expanding shows **Steps:** and **Expected:** labels, each
followed by an indented bullet list. Descriptions come
from checked-in scenario metadata, including for previously logged timings;
updating descriptions requires no test rerun.
Only executed, logged cases appear; this is not a test inventory. Small latest-only
records live in the shared `state` directory under gitignored `output/test-runs/`.

Each VM footer has an **SSH** toggle at the right, off by default. Turn it on
to show the filtered command output above the footer. The choice is retained
when switching viewer tabs until Watch is reopened. Long blue operation messages
truncate before the toggle, whose space stays reserved.

Immediately before **SSH**, **Memory: x.x GB** shows the VM process's resident
host RAM (RSS), including QEMU overhead, in decimal gigabytes. Its mini graph
reuses the footer chart renderer and shows the last minute, sampled once per
second through the existing watch feed without guest commands. The vertical
scale covers configured guest RAM and any higher observed RSS. Missing or stale
readings show **—**; gaps remain disconnected. History stays in memory and resets
when the VM instance changes or Watch reconnects. Existing VM collectors need
their next normal restart to publish this additional reading.

The camera icon at the right end of each tile's title bar saves that tile's UI frame
at its original resolution to the XDG Pictures directory's Screenshots folder,
without a Save dialog. Names follow `Screenshot From 2026-10-30 10-04-15.png`
in local time; repeated captures in one second add a numeric suffix.
A desktop notification appears for five seconds (subject to desktop settings).
Click it to open the default file manager with the screenshot selected, using
the standard desktop notification and FileManager1 APIs. This requires the
system Python's PyGObject/Gio bindings. With Remote SSH, saving and notifications
occur on the extension host's desktop.
It excludes the viewer's headings, command text and footers. Long titles truncate before
the camera, keeping it visible. The camera is disabled without a frame.

Three icon buttons at the right end of the viewer tab row select the tile layout:
**Auto** (the default grid), **Vertical** (one column), or **Horizontal** (one row).
The tab remembers the selection. Overflowing tiles scroll in the chosen direction;
overflowing tab headers scroll independently while the layout buttons stay pinned.

The footer shows CPU, Memory and Disk percentages beside small filled history
graphs. They reuse the once-per-second samples, show the last minute on a fixed
0–100% scale, and retain history only in memory. Closing and reopening Watch or
reconnecting its reader starts fresh; pauses leave gaps rather than joined curves.

**Disk** reports the busiest physical disk's elapsed I/O busy time, matching
`iostat %util`. It avoids adding overlapping request durations. This measures
activity rather than maximum throughput; 100% busy does not necessarily mean an
NVMe drive is saturated.

Every source uses the same [versioned bridge protocol](BRIDGE.md), including the
default local controller. The UI receives display snapshots and opaque IDs; it
does not read controller files, VM sockets or session mailboxes. The local adapter
is `tools/watch_webview.py`; it owns checkout discovery, authenticated local feeds,
run/session state and artifact validation.

Frames travel over private stdio, directly or over SSH, with one request in flight
per source and no listener port. The bridge forwards existing PNGs without
re-encoding, requests snapshots at the existing 200 ms interval, and renders
responses on arrival. Unchanged images are omitted. A slow source cannot block
another source. Hidden tabs stop requesting snapshots; closing Watch stops only
its readers/connections. Nothing is installed in the product or in a guest VM.
No npm packages or compilation step are needed.

## Local and SSH sources

With no configuration, Watch uses this checkout's local adapter as before. Set
`onpc.watch.sources` in VS Code user or workspace settings to replace that default
or combine sources. Source IDs must be unique and stable; labels identify hosts
in run sections, viewer tabs and resource readings. Click Reconnect after editing.

```json
"onpc.watch.sources": [
  { "id": "local", "label": "This computer", "transport": "local" },
  {
    "id": "garage",
    "label": "Garage",
    "transport": "ssh",
    "host": "garage",
    "root": "/srv/onpc/parent-control"
  }
]
```

Use an existing SSH config alias with key/agent access and an already verified
host key. Watch uses noninteractive SSH without a PTY; it never installs remote
software, changes host keys or starts test execution. The remote checkout must
contain a compatible adapter and its prerequisites. Authentication/host-key
refusals require fixing access and clicking Reconnect; transient disconnections
retry automatically with a 1–15 second backoff.

Each source can optionally specify a `command` argv array instead of the default
Python reader. A future Kubernetes adapter can run on the SSH host and implement
the same protocol, without changes to the bridge or UI. That backend is outside
this implementation. Configured commands execute as the extension/SSH user in a
trusted workspace; store connection credentials in SSH configuration, not settings.

Remote controllers own execution and durable run state independently of Watch.
Closing Watch, losing Wi-Fi or rebooting this computer does not cancel remote
work. Reopening Watch reads saved source settings, reconnects and reloads retained
remote run status, logs, transcripts and recordings. Normal source retention
still applies. Chart history, undelivered text and other presentation-only state
are not durable execution data. An interrupted input acknowledgement is reported
as unknown delivery and is never automatically replayed; review the transcript
before sending again.

This is a Linux workspace extension. With Remote SSH, install it and open the
checkout on the extension host; SSH source connections originate there. A source
configured as local always means that extension host. VS Code Workspace Trust is
required. Activate extension changes with `./setup.sh --watch` and reload VS Code;
no product installation or restart is involved.
