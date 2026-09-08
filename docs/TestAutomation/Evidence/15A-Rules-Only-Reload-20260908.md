# 15A rules-only reload qualification — 2026-09-08

Development-host build/unit scope and the existing guarded VM were authorized.
Settings: `gpt-6-astra` / `high`, pinned by the slice launcher. The all-task VM
clearance remains valid. This is partial native qualification, not 15A acceptance.

## Cause, correction, and limits

The [first failed runtime](15A-Native-Runtime-20260908.md) retained a trust-database
refresh immediately after the first policy change; later source/compiled rules
changed without corresponding live ruleset identities. Released upstream
[`fagenrules`](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/init/fagenrules)
confirms that `--load` sends SIGHUP. The public
[`fapolicyd-cli` interface](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/doc/fapolicyd-cli.8)
separates trust updates from rules-only notification. Current upstream retains
these interfaces; no development-only API was adopted.

`broker/oh_no_parent_control/execution_policy.py` now compiles with
`/usr/sbin/fagenrules` and then requests `/usr/sbin/fapolicyd-cli --reload-rules`.
Both forward activation and rollback use this sequence. Compiler failure prevents
candidate notification. Notification failure restores and recompiles the previous
rules before notifying again. Each subprocess retains its 15-second timeout.
Logs record stage, exception type or status, never subprocess output or rule data.
This broker change activates through the existing `process-restart` classification;
there are no new integration files or saved-data changes.

**Limit:** the public reload command is a notification, not an acknowledgement.
This correction removes the observed unnecessary trust refresh. The successful
runtime below does not establish that every broker reply waits for daemon
activation. A bounded active-policy acknowledgement remains necessary before
claiming synchronous policy transactions, including rollback. The boot canary in
`tools/execution_policy_ready.py` witnesses only initial enforcement, not a new
policy generation. Do not introduce launch retries, arbitrary sleeps, daemon
restarts, private FIFO writes or unsupported status fields to conceal the gap.

## Verification

- An initial focused selection named a nonexistent extra test file; the validated
  launcher refused before running tests. Corrected discovery selected maintained files.
- `tools/run-unit-tests tests/unit/test_execution_policy.py -q`: 11 passed and
  four subtests passed. Covers compilation, notification, rollback, timeout and
  safe error logging.
- `tools/run-unit-tests tests/unit/test_execution_policy.py
  tests/unit/test_execution_policy_ready.py tests/unit/test_system_enforcement.py
  tests/unit/test_uninstall.py -q`: 185 passed and four subtests passed, 0.45 seconds.
- Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py'
  tests/unit/test_graphical_lease.py -q`: 519 passed and three subtests passed,
  4.58 seconds. The privileged dispatcher's clean environment independently
  passed the same scope in 5.91 seconds.
- Fresh `tools/run-tests artifacts build` succeeded at
  `/tmp/onpc-test-artifacts-gyyw4imz`; no product installed on the host.
- `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-gyyw4imz
  --area enforcement --test test_native_command_policy_is_uid_scoped` exited 0
  (handle 31652). No checkout edits occurred from build through terminal cleanup.

Retained evidence: `/tmp/onpc-system-f3jqhqra/evidence`, available through the
documented `onpc-test-artifacts` reader. `result.json` reports five expected and
five executed cases: four installed/reboot prerequisites and the selected
command case. Product, infrastructure, collection and cleanup all passed;
`cleanup_phase=complete`. `guest/enforcement.xml` has one passed test, no skips,
errors or failures; its properties retain all ten stages and twenty launches.

| Screen-time control | Selected-child results | Other-child results |
| --- | --- | --- |
| Disabled | Initial allow, hard deny, restored allow, soft deny, restored allow | Allowed at all five stages |
| Enabled | Initial allow, hard deny, restored allow, soft deny, restored allow | Allowed at all five stages |

Preference restoration passed. `guest/service-journal.txt` shows the eight
successive deny/allow ruleset changes after startup and the four expected
denials. There is no trust-database refresh during those policy saves. This
discriminates the corrected rules-only path from the failed SIGHUP path.
The first failed attempt remains failed; other native cases were not rerun here.
No requirement mapping or checklist entry was promoted. The earlier broad-check
kiosk failure remains in the linked historical chain; `make check` was not rerun.

## Provenance and cost

| Identity | SHA-256 / revision |
| --- | --- |
| Source revision | `dde97bf2ee5db883bf417bd5399694e1d6a70568` |
| Source content | `5e318943771935d0a3c87efa30794b7a5ae7b02695075be0d46304d587645ded` |
| Package | `0b1328cd53aecf4c24f7e0aa2ce6129467105cb7196c0032b995d9bc3592e7ac` |
| Fixture | `1b2aee47186c5057c581a6777c64f1ed7b40e960f47cc4e676e5628753074365` |
| Selected inputs | `ef0568282a3571d142d261777cc176a3787a5fcb8da9585a3feeb964de164ce2` |
| Baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |

Controller times (seconds): preparation 72.574, bootstrap 45.799, installation
50.519, reboot 12.696, tests 44.562, collection 1.698, cleanup 95.521;
approximately 5.4 minutes total. The selected enforcement pytest took 11.222
seconds. Two live activation-boundary attempts total: original failure and this
corrected-code pass; one earlier safety refusal never entered the VM. No unchanged
retry occurred. A further attempt needs changed inputs or a distinct observation.

All commands exited and results were collected. Fresh `tools/test-vm status`
reported state 5, ID -1. The runner verified baseline and host restoration; no
owned process, lease, screenshot or recovery remains. No approval or Polkit
denial occurred. Logs and prior artifacts were preserved.

Next: establish a supported bounded active-policy acknowledgement with local
failure/rollback checks, then rebuild and run the registered native area in the
guarded VM. Preserve the operator clearance and guards. Full 15A estimates are
**Unknown** sessions and **Unknown** minutes: one successful command case does
not size the acknowledgement, missing routes/update cases or Snap/Flatpak work.
