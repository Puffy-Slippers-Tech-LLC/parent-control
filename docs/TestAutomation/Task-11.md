### Task 11 — Build deterministic native and Flatpak test applications

- Complexity: medium-high. Fixtures must represent real execution identities
  without becoming product dependencies.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: provide stable targets for catalog, enforcement, and termination
  tests.
- Work:
  1. Add a tiny source-built native GUI or long-running process fixture that
     reports readiness and exits cleanly. Build it only in the test environment.
  2. Produce exact-path, path-with-spaces, and versioned AppImage-style copies,
     plus a nonmatching executable in the same directory.
  3. Add child-only and system `.desktop` fixture entries with deterministic IDs,
     names, icons, and executable targets.
  4. Add a minimal Flatpak fixture, local repository, and bundle built without a
     network dependency during test execution.
  5. Add helpers that launch the fixtures as a specified UID and report process
     identity without logging usernames or command-line secrets.
  6. Verify fixture digests and keep all fixture installation scoped to disposable
     test images.
- Verification:
  - Build fixtures from a clean checkout.
  - Launch and terminate each fixture in an unprivileged temporary environment.
  - Run `make check`, relevant component tests, and `git diff --check`.
- Completion criteria: all supported native, pattern, and Flatpak enforcement
  cases have reproducible self-contained targets.

