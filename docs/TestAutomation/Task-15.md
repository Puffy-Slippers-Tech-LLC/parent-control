### Task 15 — Test installed catalog, fapolicyd, and process termination

- Complexity: very high. The test must prove kernel execution behavior and UID-
  confined termination, not merely generated rule text.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: execute application-policy enforcement through all supported paths.
- Work:
  1. Install the Task 11 fixtures for each relevant user and verify the catalog
     sees system and child-only launchers for the selected child, not the
     administrator's substitutions.
  2. Apply allowed, hard, and soft policies while screen-time control is enabled
     and disabled.
  3. Execute native targets from a launcher, file-manager activation, and command;
     execute the Flatpak fixture by its full identity.
  4. Test exact paths, spaces, matching future versioned filenames, unrelated
     same-directory files, target refresh after update, and preservation after a
     launcher disappears.
  5. Run the same executable as the selected child and unrelated users and prove
     UID-scoped enforcement.
  6. Start blocked fixtures in every live session for one child, trigger approval
     and revocation termination paths, and prove pidfd/Flatpak confinement and
     unrelated-process survival.
  7. Force fapolicyd reload failure in the disposable guest and prove transactional
     policy restoration and clear PII-safe logs.
  8. Update application-policy requirement mappings.
- Verification:
  - Run the full enforcement matrix from a fresh installed overlay.
  - Capture source and compiled fapolicyd rules and process evidence.
  - Run `make check-system`, `make check`, and `git diff --check`.
- Completion criteria: supported application routes are tested against real
  fapolicyd and Flatpak behavior with positive, negative, and isolation evidence.

