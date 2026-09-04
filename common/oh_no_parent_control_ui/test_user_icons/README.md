# Shared test account portraits

These four PNGs were cropped from the user-provided four-person image on
2026-09-04. Each contains only its portrait, with a transparent circular edge,
resized to 128×128 for AccountsService.

`test_identities.py` is the single mapping used by parent, kiosk, and child
overlay previews and by `tests/integration/prepare_vm.py`. Do not copy these
assets into individual apps. VM preparation passes the same source files to
AccountsService's `SetIconFile` and verifies the returned icon contents;
AccountsService manages any system-owned copy itself.

These are test fixtures, not production account defaults. Packaged shared
assets have update activation `none`: newly opened previews read them.
Re-run VM preparation to apply changed portraits to the fixed VM accounts.
