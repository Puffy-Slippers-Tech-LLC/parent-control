# Kiosk expiry: automation VM runtime continuation

Continuation of the [original fix handoff](Kiosk-Session-Expiry-Fix-Handoff-2026-09-09.md)
on the main development computer. The user released the automation VM for these
checks. The installed-app machine described in that handoff is a different
computer. No product package was installed on the development host, and unrelated
staged and unstaged work was preserved.

## Inputs and scope

New artifacts were built here, rather than reusing the other computer's `/tmp`
paths. Both `/tmp/onpc-test-artifacts-y3grarvy` and
`/tmp/onpc-test-artifacts-d8ramxb3` contain the same package bytes:

- Package SHA-256: `12ad6400a7d120281f0473bc4334c067c0244856ce34917bc71bd055e72ed8ff`.
- Latest artifact source digest: `337d1fe1dad0f92315da84f164cf1322574266c3e5e83ca6c8ce1d03d09e7cc8`.
- Base revision: `944da18980cab1181c287ba9d59e88276cbea654`; uncommitted source is included.
- Finalized VM baseline provenance: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.

The controller separately freezes and hashes each attempt's exact selected guest
tests/helpers. Test-tooling changes after package build therefore have their own
`selected_inputs_sha256`; they do not silently change the installed package.
The package remains version 1.0. Each attempt starts from the product-free baseline.

## Attempts

### Fresh installation and reboot observation

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-y3grarvy --area package`.
Evidence: `/tmp/onpc-system-4zo4j97d/evidence`.
Selected input digest: `a83d7e2b1d456469e08c3ff46f054a93d0044ede8c65732c5d43630f174dfab6`.

Fresh installation, installed file checks, PAM account ordering, broker activation
and first-install reboot notification passed. The old transport then failed with
`transport:reboot-not-observed`: the reboot closed its original SSH connection,
but another connection briefly read the old boot before sshd stopped. The next
collection connection was reset. The failed run is retained; cleanup passed and
restored the baseline, original domain configuration and powered-off state.

[Transport.reboot](../tests/integration/vm_transport.py) now reuses the existing
bounded boot-change observer. It waits through a valid old boot and SSH transport
resets, while refusing malformed output, guest guard failures, lost ownership,
command failure and deadline exhaustion. Focused regressions include the observed
old-boot/connection-reset/new-boot sequence.

### Installed PAM scopes and offline recovery

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-d8ramxb3 --area enforcement --test test_kiosk_expiry_installed_runtime`.
Evidence: `/tmp/onpc-system-5t4wbmqf/evidence`.
Selected input digest: `1010bd5f30c75b24b60b7311d5f2e2ed49a6551f53a3ebdd090f5bfb4ab81c3f`.

All four package/install/reboot checks passed; actual changed-boot observation
took 14.034 seconds. The focused check established:

| Observation | Result |
| --- | --- |
| Offline broker startup with global extensions disabled | Broker activated, switch restored, individual enabled/disabled selections preserved |
| Installed `gdm-password` PAM account phase | Accepted with 0.779 seconds remaining |
| Its real pam_systemd scope | `RuntimeMaxUSec=infinity`; still active past the original deadline |
| Installed `gdm-autologin` PAM account phase | Accepted with 0.800 seconds remaining |
| Its real pam_systemd scope | `RuntimeMaxUSec=infinity`; still active past the original deadline |
| Installed `login` PAM scope | Finite `RuntimeMaxUSec=3s` |

These PAM probes run outside the SSH scope in a test-started transient service.
They explicitly use an unspecified session type, excluding the broker's
graphical-only fallback. They invoke the installed stack and real pam_systemd,
but do not themselves start a GDM desktop.

The attempt failed at the `login` termination witness. The probe moved out of
its launcher service into the login scope; the launcher reported successful
deactivation when that scope ended. Its exit status is not the scope's timer
result. The fixture now requires the actual created scope's journal event,
`Scope reached runtime time limit. Stopping.` SSH remained untested in this
failed attempt. Collection and cleanup both passed. The failed result is not
relabelled as a passing run.

## Graphical check under qualification

The new registered `session` area uses the same controller, accepted baseline,
exclusive lease, immutable selected inputs, installed prerequisites and cleanup.
It repeats the installed PAM/offline checks, prepares a one-shot fixture, and
performs another real reboot. A guest-only `pam_exec` account hook seeds one
second of grant immediately before the unchanged stock account checks. It does
not override their status or create a synthetic desktop. The broker is started
before that hook returns, and its invocation identity must remain unchanged
through the initial scope observation, excluding a later startup cap repair.

The observer requires a real local graphical `gdm-autologin` user session,
the native module's before-session journal witness, an infinite scope, a live
configured/active extension, and the same retained session locked after expiry.
It then disables the global switch, waits for actual deactivation, and tests
broker recovery against live GNOME state and preserved settings lists.

This fixture uses [GNOME's documented automatic login configuration](https://help.gnome.org/system-admin-guide/login-automatic.html)
through AccountsService. It is an installed runtime diagnostic, not a password
entry or full customer-journey assertion. Runtime acceptance and the remaining
handoff cases are still in progress; this document must not be read as completion.
