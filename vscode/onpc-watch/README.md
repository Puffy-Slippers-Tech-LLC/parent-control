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
share the panel in equal sections; when idle, it retains the last displayed run.
Each title, e.g. `[main] fix-tests`, keeps **Status**, **Launcher**, **Error** and **Session**
links at its right end. The name comes from the launcher's `current.json`
publication, including custom plan launcher names. Older runs without a published
name show `launcher` until their next start, attachment or reload request.
**Status** shows the current run status, **Launcher** shows
the launcher terminal output, **Error** shows the shared launcher's **Last Error**
and **Status** fields with the same colors and elapsed ages, and **Session** opens
the session transcript and chat.
For `fix-tests`, Last Error includes the failing check, the runner's error text
(or a bounded command-output tail), and its output-log path. Reload launcher
changes with `tools/fix-tests --reload`; `./setup.sh --watch` updates the extension.
The links remain available in every view, including while idle.
For `write-e2e`, **Status** starts with **Total Tasks: completed/unfinished/total**
and **Total Duration**, using the shared launcher counters and colors. A divider
spans the panel above the completed task recaps and current task/session rows.
For every execution-plan launcher, completed and current task headings end with
` | <duration>` from the retained task clock across sessions. The session summary
ends with ` | <duration>` from its owner session clock.
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
sent prompts and agent messages. Command and tool result bodies are hidden in
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
Repair case totals show green completed, red failed and total counts. The failed
count is underlined; click it to open the cumulative `errors.md` in the editor.

The right panel contains the shared All grid across checkouts, UI worker and VM tabs,
VM progress, filtered command output and host resource usage. Screens are view
only. Tiles and viewer tabs group by worktree in the left panel's current order,
following changes on each refresh. Worktrees without a displayed run follow those
shown on the left. Start tests through the usual launchers. Select an idle VM tab to wait for
its next run. The Reconnect button restarts only this tab's reader.

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

The extension runs the selected trusted checkout's `tools/watch_webview.py` with
system Python. That adapter uses shared checkout discovery,
authenticated feeds and scope selection. Frames travel over private stdio,
with one snapshot in flight and no listener port. Hidden tabs stop requesting
snapshots; closing a tab stops its reader. Nothing is installed in the product
or in a guest VM. No npm packages or compilation step are needed.

This is a Linux workspace extension. With Remote SSH, install it and open the
checkout on the development host where the watch publications live. VS Code
Workspace Trust is required.
