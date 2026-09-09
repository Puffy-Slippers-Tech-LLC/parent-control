# Kiosk unavailable after grant expiry during login

The automation VM was released on the main development computer for the
[runtime continuation](Kiosk-Session-Expiry-Runtime-2026-09-09.md). That document
records new artifacts, actual VM attempts and outstanding checks. The original
machine-specific restrictions and `/tmp` paths below describe the earlier session.

## Scope and operator instructions

The user requested review of the kiosk failure diagnosis and a root-cause fix.
This computer is an installed-app test machine with a copied checkout. The
separate automation VM is occupied by other work and **must not be used in this
session**. Perform local tests here. Resume the VM-dependent checks below from
the main development computer when the user says that VM is free. Quality takes
priority over finishing quickly. No VM operation was performed for this fix.

The checkout contains many unrelated staged and unstaged changes. Preserve them.
This document is independent of the ongoing Task 20 handoffs; it does not claim
completion of any of their pending scenarios.

## Reviewed diagnosis

On September 9, local PDT timestamps show:

1. At 13:47:04 the broker approved a 120-second grant.
2. After a reboot, a child session opened at 13:49:03. At 13:49:04 systemd
   reported `Scope reached runtime time limit. Stopping.`
3. At 13:49:05 GNOME Shell failed to register with GDM (`No display available`),
   hit a D-Bus assertion, and aborted with signal 6.
4. At 13:49:06 `org.gnome.Shell-disable-extensions.service` ran. Its installed
   command sets `org.gnome.shell disable-user-extensions` to true.
5. The kiosk triggered broker activation at 13:49:16. Extension activation
   rejected the switch, and broker initialization failed repeatedly through
   13:49:47. Systemd subsequently reported the broker failed.

The first investigation correctly identified the immediate backend outage but
missed the earlier PAM defect. The installed `common-session` placed the
external cap-clearing helper **before** `pam_systemd.so`. No session scope or
`XDG_SESSION_ID` existed yet. The helper silently did nothing, and pam_systemd
then created the finite kill timer from pam_malcontent's PAM data. Clearing a
scope later also races a grant with one second remaining. The timestamps support
expiry during login as the trigger; no claim is made that the product extension
itself caused the GNOME crash.

Source evidence: `/var/log/oh-no-parent-control/broker/2026-09-09.log`, the kiosk
log for that date, and the system journal from 13:47 through 13:50. Raw logs and
account identifiers were not copied into this handoff.

## Implementation

- [Native PAM module](../tools/pam_oh_no_parent_control.c): an account hook
  replaces an existing `systemd.runtime_max_sec` value with `infinity` on the
  same PAM handle, before GDM session creation. Terminal, SSH, and other PAM
  services retain their timers because GNOME screen-lock enforcement is absent.
  It uses the documented
  [pam_systemd data interface](https://github.com/systemd/systemd/blob/main/man/pam_systemd.xml)
  and [pam_set_data ownership contract](https://github.com/linux-pam/linux-pam/blob/master/doc/man/pam_set_data.3.xml).
  It preserves absent data and other resource limits, propagates API failures,
  and logs only fixed stages and numeric status codes.
- [PAM profile](../data/pam-configs/oh-no-parent-control-session-limits): the
  hook follows `pam_malcontent.so` in account management. Skip counts exclude
  both modules for the existing exempt/unrestricted paths. Malcontent's denial
  remains authoritative. The ineffective external session helper and its
  packaging/tests were removed.
- [AccountsService adapter](../broker/oh_no_parent_control/adapters.py): the
  broker's existing-session fallback now also requires a graphical GDM user
  session, preserving timers on terminal, SSH, and unknown session types.
- [Extension manager](../broker/oh_no_parent_control/extension_manager.py):
  startup reassertion for a saved enabled account restores the global extension switch,
  verifies it, and then requires the existing activation verification. Failure
  restores the global switch and the individual extension lists and verifies
  rollback. This can resume other individually enabled GNOME extensions;
  their individual choices are preserved. Ordinary preference transitions keep
  the existing refusal for a disabled global switch; this avoids changing that
  switch inside a larger transaction which could subsequently roll back.
  Disabling control does not turn on the global switch. Startup still fails if enforcement cannot be established;
  the fix does not swallow extension errors to make the broker appear healthy.
- Installation observers now require the account hook after Malcontent, in
  [system checks](../tests/integration/system_guest.py) and the
  [E2E layout observer](../tests/e2e/installation_observations.py).
- [Screen-time design](SystemDesign/Screen-Time.md) documents the final behavior.
  PAM changes require **reboot** activation; broker changes require
  **process-restart**. Existing activation rules cover both. No saved-data
  format changed and no migration is required.

## Local validation and environment

The source checkout is mounted `noexec`. The system initially lacked pytest
and the development helpers. With the user's approval, a local executable copy
was created at `/tmp/onpc-kiosk-local-20260909`; `./setup.sh --bootstrap-tools`
installed helpers and scoped authorization there, and
`./setup.sh --dependencies-only` installed the maintained prerequisites. This
does not prepare a VM baseline. Installed development helpers are pinned to that
temporary checkout on this test machine; the main development computer should
use its own maintained setup and checkout, not these temporary paths.

Final verification ran from the executable source copy at
`/tmp/onpc-kiosk-validation-20260909`. All 26 implementation, test, and design
files involved in this fix were compared with the original checkout and matched.
The removed external helper and its former unit test are absent from both copies.

| Local check | Result |
| --- | --- |
| `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q` before broader execution | 562 passed; 3 subtests passed |
| `tools/run-unit-tests tests/unit/test_pam_runtime_cap.py tests/unit/test_adapters.py tests/unit/test_core.py tests/unit/test_extension_manager.py -q` after the final GDM restriction | 142 passed; 36 subtests passed |
| Final `make check` | 5,779 unit tests and 25 private-D-Bus component tests passed; C/JavaScript syntax, traceability, Python/XML parsing, and forbidden-interface checks passed |
| `tools/run-tests artifacts build` | Debian package and fixtures built; artifact digest verification passed |
| Extracted package inspection | Exports `pam_sm_acct_mgmt`; account profile orders the native hook after Malcontent; obsolete external helper absent; PAM entries classify as `reboot`, changed broker entries as `process-restart` |
| `git diff HEAD --check` and maintained Markdown link checker | Passed |

The native tests compile the product module with warnings as errors and invoke
real libpam with private configuration. They cover the one-second boundary,
multiple GDM services, absent/infinite data, repeated reconciliation, preserved
non-GDM timers and other resource limits, account denial, and every packaged
account-stack bypass. A negative control without the new hook confirms that the
finite timer reaches the session phase. They do not invoke real pam_systemd,
create a login scope, or start a desktop.

Relocation exposed existing assumptions in four fully mocked test modules:
[E2E cleanup](../tests/unit/test_e2e_execution_cleanup_safety.py),
[graphical cleanup](../tests/unit/test_graphical_smoke_cleanup_safety.py),
[host preparation](../tests/unit/test_prepare_host.py), and
[system runner](../tests/unit/test_system_runner.py). Their fixtures now pin the
mock checkout identity to the executing test copy. Real ownership validation and
VM protections are unchanged. Initial failures were resolved before the passing
cleanup and full-suite runs above; no real VM tests were run.

Final artifact directory: `/tmp/onpc-test-artifacts-m_xlgkkp`.
Package: `package/oh-no-parent-control_1.0_amd64.deb`.
Its `artifact-manifest.json` records:

- Package SHA-256: `493f64dfcef2c1cdfe0971a39ff908778fd0dbf7707fc530b204d707e7ed87ab`.
- Source input SHA-256: `87ceba5df3671f6b345cda21c31d0b220a5be93656c008d34a4b4a215fe63229`.
- Base Git revision: `944da18980cab1181c287ba9d59e88276cbea654`; 582 source input files,
  including uncommitted changes. That revision alone does not contain this fix.

The builder uses its documented `nocheck` packaging mode; the separate final
`make check` above supplies test evidence. Final handoff prose was filled in
after the build. Earlier temporary artifacts are superseded by this artifact.
The package remains version 1.0; a same-version APT no-op must not be mistaken
for activation of the new payload during continuation.

The product package has not been installed or activated by this fix. No product
broker restart, account-settings repair, login-manager restart, or reboot was
performed. Installed-session behavior remains pending below. Transfer the actual
working-tree changes, including new test files and deleted helper files, with
this document; preserve the unrelated work already present in the checkout.

## VM-dependent continuation

Do not treat local fake-command tests or private PAM stacks as proof of the
installed GNOME/GDM behavior. When the user releases the automation VM:

1. Read [System design](System-Design.md), [Screen time](SystemDesign/Screen-Time.md),
   [Package update](Package-Update.md), and the current
   [approval/tool contract](TestAutomation/Approval-Tools.md). Bring the actual
   source changes with this document to the development computer; `/tmp`
   artifacts from this machine are not transferable evidence of that checkout.
2. Build and verify new package artifacts from those exact inputs. Use the
   guarded installed-system/E2E routes and their ownership/cleanup prerequisites.
   Do not take over an occupied VM or reset it inside a customer journey.
3. Verify fresh installation and update activation: the installed PAM account
   hook follows Malcontent, the obsolete external session hook is absent, and
   the package requests the required reboot boundary.
4. Exercise child login with roughly one second of grant remaining. Inspect the
   created scope's `RuntimeMaxUSec` through the approved observer and require
   infinity from creation. Verify expiry locks the session without ending it,
   and zero-time fresh login and unlock remain denied.
5. Extend an active session's time and verify the earlier grant deadline never
   terminates the session. Check another user's foreground session is unaffected,
   and terminal/SSH session timers remain enforced.
6. Through guarded fixtures, start with the global extension switch disabled
   for an enabled managed child. Verify broker startup recovers, other extension
   selections remain intact, and both kiosk and child-overlay requests work.
   Test live and offline activation, including the actual GNOME notification
   timing; require configured and active readback rather than just settings.
7. Inject activation/write/readback failures. Require verified rollback and no
   approval without working enforcement; do not count broker registration alone
   as recovery. Check logs for fixed diagnostics without account data.
8. Record package/source identities, assertions, screenshots where relevant,
   cleanup outcomes, and any remaining limits in this document or a linked
   evidence document. Update the diagnosis if real runtime evidence differs.

Next-session settings: `gpt-6-astra` / `high`, Standard processing. Reason:
the remaining work crosses PAM session creation, GNOME recovery, and real
enforcement ordering; reassess once that boundary is verified.

Resume prompt: “Continue the kiosk expiry fix from
docs/Kiosk-Session-Expiry-Fix-Handoff-2026-09-09.md. The automation VM is now
available. Preserve unrelated work and complete the pending runtime checks.”
