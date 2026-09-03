### Task 05 — Add a real private-D-Bus broker component harness

- Complexity: high. It crosses GLib event loops, asynchronous replies, caller
  disconnects, and service dependencies.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: execute the broker's real D-Bus dispatch and public error contract
  without touching the host system bus.
- Work:
  1. Use current `python-dbusmock` support for a private session bus and a private
     bus addressed as the test system bus.
  2. Refactor service construction through ordinary dependency injection so
     tests can supply broker adapters, configuration, clocks, and a temporary
     log writer. Do not add a test-only public API or authorization bypass.
  3. Call every public D-Bus method through a real `Gio.DBusConnection` and
     assert signatures, serialization, error names, public error text, and
     completion on the GLib main loop.
  4. Exercise concurrent request dispatch, caller disappearance, cancellation,
     worker exceptions, malformed JSON, and unknown methods.
  5. Assert that D-Bus logs identify stages and error categories without UIDs,
     usernames, labels, request secrets, or paths supplied by callers.
  6. Update the D-Bus requirement mappings.
- Verification:
  - Run the private-D-Bus suite repeatedly in one process and in fresh processes.
  - Run `make check` and `git diff --check`.
- Completion criteria: the real service dispatch layer is executable on a
  private bus and no test contacts or changes the host system bus.

