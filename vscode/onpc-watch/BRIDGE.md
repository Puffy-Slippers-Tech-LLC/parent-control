# Watch bridge protocol 1

The boundary is newline-delimited UTF-8 JSON over a reader process's stdin/stdout.
Diagnostics go to stderr. `bridge.js` uses exactly the same protocol for local
processes and processes reached through SSH. The webview receives aggregated
display snapshots, never controller paths as routing identities. Source-qualified
IDs prevent collisions between hosts, including identical checkout and VM names.

An adapter translates its controller's state into this display contract. The
existing local adapter is [`tools/watch_webview.py`](../../tools/watch_webview.py).
A replacement adapter implements the contract below; it does not need that
reader's filesystem layout, Python modules, libvirt or Unix-socket protocol.

## Lifecycle and flow control

- Opening a connection starts an observer only. Closing stdin, SSH loss or reader
  termination releases observer resources and must not cancel or own test work.
- Controllers retain authoritative run/checkpoint/log/session/artifact state.
  A new reader must reconstruct the latest retained run without requiring a
  previous Watch process, local cache or a replay of start commands. Adapters
  must not tie controller lifetime to the SSH connection.
- One request produces one response, in order. There are no unsolicited messages.
  All messages include `"protocol": 1`. There is no listener port or handshake RTT.
  Each message ends with a newline, including the final reply before EOF. Reads
  may split anywhere, including inside UTF-8 characters, or contain several lines.
  EOF inside a message is a failed connection. The bridge drains stdout/stderr
  before classifying process closure. The local reader also accepts legacy
  unversioned snapshot requests; session actions use the schema below.
- Watch requests at 200 ms intervals while visible and ready to render, with at most one request in
  flight per source. Responses render immediately with UI backpressure. Slow
  sources skip requests, rather than accumulating a frame queue or blocking peers.
  Hidden Watch panels stop requesting; an already pending request may finish.
- Requests time out after ten seconds. Broken connections retry independently with
  a 1–15 second backoff; SSH authentication/host-key refusals require manual
  reconnection after repair. Reconnection requests a full frame reset.
- Responses are bounded to 96 MiB per line (excluding newline) and requests to
  512 KiB (including newline). Frame buffers and
  snapshots stay in memory. Only changed frame data crosses the bridge; it is not
  re-encoded or recompressed by the bridge. No additional capture process is used.

## Snapshot request

```json
{"protocol":1,"scope":"all","selected":"all","reset":false,"session_root":""}
```

`scope` is `all` or a checkout ID. `selected` is `all`, `run-time` or a viewer ID. An unknown
selection means no viewer pixels are requested (metadata still returns). An empty
`session_root` requests no transcript body; otherwise it identifies a run section.
`reset` requests full images for the visible selection. IDs are opaque strings;
the adapter may use paths internally, but the renderer must not interpret them.
IDs are nonempty strings of at most 4096 characters, unique within each array.
Checkout IDs cannot be `all`; viewer IDs cannot be `all` or `__hidden__` (the
bridge's no-pixels selection). Run IDs that refer to a checkout use its ID.
Every snapshot includes current metadata for the selected scope, even when
pixels or transcript bodies are omitted. Viewers outside `scope` may be omitted.

The response contains these fields:

| Field | Shape and meaning |
| --- | --- |
| `protocol` | Integer `1`. Incompatible versions fail the source connection. |
| `capabilities` | `{sessions: boolean, artifacts: boolean}`. Unsupported operations must also refuse at the adapter. |
| `checkouts` | Array of `{id, label}`. |
| `runs` | Run sections described below, including retained idle runs. |
| `entries` | Viewer entries described below, including idle configured viewers. |
| `resources` | Readable resource summary for the source host. |
| `resource_sample` | Sample identity, compared only within this source. |
| `resource_charts` | Array of `{label, text, segments}` for CPU, Memory and Disk; empty if unavailable. |
| `session_result` | Optional `{id, ok, error?}` acknowledging the requested action. |
| `run_times` | Optional array, populated only for `selected: "run-time"`: `{id, title, category, vm, seconds, case_file, description, case_link, recording}`. Links are published artifact references; recording may be null. |

A run section has `id`, `label`, `active`, `status`, `run` (run identity or null),
`rows`, `error_rows`, `launcher_output`, `session` (identity or null),
`session_active`, `session_number`, `session_inactive`, `session_waiting`,
`session_deadline` (Unix seconds or null), `session_question`, and `session_view`.
`label`, `status` and `launcher_output` are strings. `active`, `session_active`,
`session_inactive` and `session_waiting` are booleans. `session_number` is a
positive integer or null; `session_question` is a question ID or null.
`session` identifies the exact input recipient, not just its run; it changes when
that recipient changes. Question IDs change on each new prompt, within a session.
Rows are arrays of spans: `{text, bold?, compact?, waiting?, color?, link?}`.
They contain text, never HTML. `text` is a string, optional flags are booleans,
`color` is a CSS color string or null, and `link` is a string reference of at most
8192 characters or null.
Links are adapter-owned artifact references; the renderer interprets no URI paths.
`session_view` is null or `{rows, input_enabled, working, model, simplified}`.
`input_enabled` and `simplified` are booleans; `working` and `model` are strings.
Only the requested run needs a transcript body. An idle run must keep its retained
contents and disable input when its owner exits. Final status updates remain
authoritative after exit; the UI does not freeze the first idle response.

A viewer entry has string fields `id`, `source` (producer identity), `kind` (`vm`
or `ui`), `label`, `heading`, `step`, `status`, `activity`; booleans `active` and
`locked`; optional `memory` (`{text, sample, segments}`); and optional `screen`.
`source` identifies the frame producer generation and changes when its cached
pixels cease to be valid (including producer replacement). Changing `source`
invalidates the previously displayed frame even if `screen` is omitted. `screen` omitted
means unchanged, null means clear, and an object has `{width, height, image}` with
a PNG data URI. Optional `cursor` has `{image, x, y, width, height}` and a PNG data
URI. Reset responses include images or explicit nulls for visible entries.
Image dimensions are positive integers at most 8192 per side; cursor coordinates
are finite numbers. In All view only active entries are visible; a selected entry
is visible even when idle. On becoming visible, an entry receives the bridge's
latest cached frame even if that adapter response omits unchanged pixels.
Charts use arrays of nonempty polyline segments of normalized `[x,y]` pairs;
the source handles sampling/freshness and clock domains before serialization.
Chart `text` is a string; `sample` is a scalar identity or null, changing whenever
the chart changes. Resource and VM memory sample identities are independent.

## Session actions

A snapshot request can include:

```json
"session_action": {
  "id": "client-action-id", "root": "run-section-id", "session": "session-id", "question": "question-id-or-empty",
  "kind": "send", "text": "message or answer"
}
```

Kinds are `send`, `extend` (text is the question ID), and `simplified` (text is
empty). Text is limited to 64 KiB UTF-8; action IDs are unique across webview
lifetimes and limited to 128 characters. `question` is the displayed question ID,
or an empty string for chat without a pending question. For `extend`, text must
also identify that question. The adapter revalidates current owner, session
and question identity at execution time, then returns `session_result` with the
same action ID, boolean `ok`, and a string `error` on refusal. `simplified` changes
only observer presentation, so it may operate on a retained, inactive session.
Every action receives exactly one acknowledgement, including stale-session
refusals; snapshots without an action omit `session_result` or set it to null.
The bridge routes actions only to their displayed source/session.
Disconnected sources disable input while retaining the observed transcript.

Actions are never retried automatically. Losing a response leaves delivery
unknown; inspect the authoritative transcript before submitting again. Exactly
once delivery across a client reboot is not claimed. Snapshot polling and
reconnection must never replay an action, start, stop or restore test execution.

## Artifacts

Artifacts use the same connection and one-request flow control, on demand:

```json
{"protocol":1,"artifact":{"uri":"published-reference","inline":true}}
```

The adapter validates that the reference is still published by this reader and
checks filesystem/ownership permissions itself. It returns
`{"protocol":1,"artifact_result":...}` with one of:

- `{kind: "file", uri: "file:///...", media_type: "video/webm"|"text/markdown"|"text/plain"}`
  for local access when `inline` is false. SSH sources refuse file results as local
  file access. The extension also checks local files before opening them.
- `{kind: "text", text: "..."}` for editor display.
- `{kind: "video", data: "base64 WebM"}` for in-memory video playback.
- `{error: "readable reason"}` for refusal/unavailability.

The local adapter exports published case files under discovered checkouts' `tests/`
directories, repair-owner `errors.md` logs and watch recordings. Merely mentioning an
unrelated `errors.md` path in output does not authorize access. Both forms require
regular, single-link files owned by the observer user, without symlink paths;
inline limits are 2 MiB text and 64 MiB video. No downloads occur during polling.
An artifact transfer temporarily occupies its source connection; other sources
continue updating. Original artifacts remain under their source's retention and
ownership policy. The bridge creates no local artifact cache or saved test data.

See [source configuration](README.md#local-and-ssh-sources) for local/SSH examples
and the `command` override used to introduce another backend adapter.
