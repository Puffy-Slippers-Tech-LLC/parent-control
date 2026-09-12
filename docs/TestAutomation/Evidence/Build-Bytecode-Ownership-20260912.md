# Build bytecode ownership regression — 2026-09-12

`make build` failed because the unattended privileged test dispatcher created
`tools/__pycache__/test_launcher.cpython-314.pyc` in a root-owned directory.
The ordinary developer could not unlink that file during Debian package clean.

## Cause and missing coverage

The dispatcher started with `python3 -I`, without `-B`. Its unattended route
called `regression_process.safety_command`, which imported `test_launcher` in
the privileged interpreter. The bytecode environment variable passed to child
processes did not disable writes in this interpreter; isolated Python also
ignores an inherited `PYTHONDONTWRITEBYTECODE` setting.

Existing dispatcher tests loaded code within pytest, inheriting its disabled
bytecode writes. Publishing checks built a snapshot excluding ignored caches.
Neither covered privileged checkout imports followed by cleaning that checkout.

## Test-first evidence

Added `test_unattended_dispatcher_leaves_checkout_build_cleanable` to
[the dispatcher tests](../../../tests/unit/test_privileged_test_runner.py).
It starts a fresh interpreter with the rendered installed helper's shebang,
executes the real unattended selection and checkout import, and stubs process
execution and signal/pipe setup. No root execution or VM operation is required.
It makes any generated cache directory unwritable to model the developer's
permissions, then executes the real `debian/rules clean` with debhelper.

Before changing implementation, both cases (cleanup prerequisites passing and
failing) failed at Debian clean with the reported error:

```text
rm: cannot remove './tools/__pycache__/test_launcher.cpython-314.pyc': Permission denied
2 failed, 19 deselected
```

## Fix and validation

- The dispatcher now starts with `-IB`, disabling its own bytecode writes.
- Tools refresh repairs only a root-owned `tools/__pycache__` directory's
  ownership, using the tools directory's owner/group. Directory descriptors
  and no-follow opens prevent following symlinks. Cache files are preserved
  for ordinary package clean; absent/already non-root-owned caches are no-ops.
- Added repair, unsafe-path refusal, repeat-run, and failed-install/retry tests
  in [the installer tests](../../../tests/unit/test_dev_tool_installation.py).
- The seven selected dispatcher, installer, setup, launcher, and regression
  test modules passed: **195 passed in 8.15 seconds**, including both new build
  regression cases. The complete `test-all` aggregate was not run.
- `./setup.sh --test-tools-only` succeeded and reported repaired cache directory
  ownership. The installed dispatcher was verified to start with `-IB`.
- **`make build` succeeded**, including the previously failing `dh_clean` step.
  The package is `output/oh-no-parent-control_1.1+ppa1~ubuntu26.04.1_amd64.deb`;
  the stale cache directory no longer exists.
- Markdown links and `git diff --check` passed.

The tests are discovered by the existing unit category in `make test-all`.
Activation is the next development-helper invocation after tools refresh;
there is no product service restart or saved-data migration. Setup also refreshed
generated Codex rules from the existing maintained configuration, including its
existing `test-publish` target entry; rule loading follows the usual Codex restart.
