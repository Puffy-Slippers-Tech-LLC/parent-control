Continue kiosk confinement work using GPT-6.1 Sol High.

This is a self-contained continuation prompt for the development machine. It
records the investigation and implementation boundary reached on October 11,
2026, on the incident machine. It is not a claim that confinement is complete.

Repository: `parent-control`.
Implementation commit: `3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc`.
Title: `Harden kiosk PAM session routing and admission diagnostics`.
Parent: `697a4c30`.
At handoff preparation, the implementation commit was local on `main` on the
incident machine and had not been pushed. Transfer that commit to the development
machine if it is not already present. This prompt is a subsequent documentation
addition.

The user requires the following:

- Investigate why the reserved kiosk account entered a normal graphical desktop
  instead of the kiosk application.
- Determine whether this was an original conditional bug or a regression after
  1.0; fix root causes and improve useful diagnostics without PII.
- Meet the stronger acceptance requirement: the account must permit only the
  kiosk application and its necessary services.
- Supply full context for independent review after completion. Independent
  review has not yet been completed.
- Finish remaining work on the development machine. The incident machine has no
  VMs, is not a full development machine, and must be released to its user.

Incident evidence:

- The machine runs Ubuntu 26.04.1, GNOME 50 and GDM 50.1. The installed product
  version was `1.4+local1~ubuntu26.04.1`.
- The reserved account is `oh-no-parent-control`, UID 1002.
- On October 11, an earlier boot started GNOME Kiosk and the product correctly.
  A later boot admitted the same account into Ubuntu GNOME, with
  `gnome-shell --mode=ubuntu` and ordinary desktop applications.
- AccountsService subsequently reported `Session="ubuntu"`, `XSession=""` and
  `SessionType=""`.
- No relevant product, GDM, AccountsService or GNOME package upgrade occurred
  between the successful and failed logins.
- The user does not know whether anyone selected another session using GDM's
  gear menu or whether this was simply the first login after reboot.

Root-cause assessment:

- Provisioning set a preferred session, which is not an enforcement boundary.
- The legacy PreSession hook checked `GDMSESSION`, but GDM 50.1 does not invoke
  that hook.
- The old PAM helper admitted any `gdm-password` login for the kiosk account,
  without checking the selected session.
- These routing mechanisms were materially unchanged since v1.0. Evidence
  therefore supports an original, conditional confinement gap, rather than a
  post-1.0 product regression.
- The exact event that changed or selected Ubuntu is not established. A normally
  correct saved preference explains why the gap could remain unnoticed; that
  does not prove the original trigger.

The implementation commit provides a partial fix:

- Required native PAM checks run in both account and session stages.
- A validated root-owned `/run` lock serializes kiosk account authorization
  through PAM session opening.
- The account stage verifies the dedicated Wayland default, then writes the
  pending AccountsService session marker
  `oh-no-parent-control-verification-pending`.
- GDM must replace that marker with its saved selection before session opening.
  The session stage requires the dedicated selection and actual Wayland
  transport. The marker prevents a failed settings save from leaving a stale
  correct default that could falsely attest a different selection.
- Incorrect or interrupted routing is repaired through public AccountsService
  setters, but the current attempt remains denied. A subsequent attempt may
  retry. Unavailable or unverifiable state fails closed.
- The fixed-purpose Python helper uses isolated interpreter startup (`-I`), a
  clean environment and bounded, noninteractive system-bus calls.
- Native helper execution has a bounded timeout, owned-child reaping and lock
  retention if the PAM worker aborts.
- Provisioning sets and reads back both `Session` and `SessionType`.
- Shared Ubuntu/Fedora PAM integration is updated.
- Local fixed-category admission and recovery diagnostics were added without
  usernames, arbitrary session values, exception text or command stderr. These
  are local journal diagnostics, not an automatic feedback-export extension.
- Principal implementation files are `tools/pam_oh_no_parent_control.c`,
  `tools/oh-no-parent-control-login-check` and `tools/provision.py`.
- Current implementation boundaries and logging details are documented in
  [Lifecycle](SystemDesign/Lifecycle.md) and
  [Logging and feedback](SystemDesign/Logging-and-Feedback.md).

The critical unfinished boundary is final execution. GDM 50.1 saves session
settings before `pam_open_session`, but sends `GDMSESSION` afterward. The
candidate verifies the saved selection at PAM session opening; it does not
attest the final executable. GDM can change its selection after PAM opening and
before launch. Validate that timing explicitly.

This candidate does not implement an account-wide execution sandbox or executable
allowlist. `systemd-user` admission is intentionally exempt from routing checks.
Existing child fapolicyd application policy excludes the kiosk account. Do not
describe this commit as bulletproof confinement.

Validation completed at this boundary:

- Six focused unit modules selected 171 cases: 170 passed initially. The remaining
  new test failed because it attempted to execute the nonexecutable checkout
  source directly. Its fixture was corrected to copy identical bytes with
  executable permissions; the narrow rerun passed. This was not a subsequent
  full 171-case rerun.
- The modules were `tests/unit/test_kiosk_login.py`,
  `tests/unit/test_pam_runtime_cap.py`, `tests/unit/test_provision.py`,
  `tests/unit/test_fedora_pam.py`, `tests/unit/test_rpm_packaging.py` and
  `tests/unit/test_regression_unit.py`.
- Private native PAM tests cover transaction state, contention, unsafe locks,
  worker abort, descriptor handling, timeout and logging privacy.
- Final `make build` passed for both DEB and RPM artifacts.
- Implementation documentation links: 62 checked, zero missing.
  `git diff --check` passed.
- No real GDM acceptance, VM qualification or final-execution timing test was
  completed. Unit tests and package builds do not establish installed acceptance.

Installation status at handoff preparation:

- A `make install` attempt stopped at sudo authentication before package changes.
  The waiting command was cancelled cleanly.
- The incident machine still had its old installed product. The user was given
  the following local installation commands; whether the user subsequently ran
  them is unknown:

  ```bash
  cd '/home/edgar/parent-control'
  make install
  ```

- The built DEB is
  `output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`.
- Installation requests a reboot. No reboot, logout or GDM restart was performed
  during this work. Existing user and kiosk sessions were left untouched.
- The same package version is reused, so the version alone cannot identify
  whether the partial fix is installed.
- All owned build, test and installation commands had finished before handoff.

Controlled engineering reproduction, not yet executed:

On an unpatched supported disposable test system, set the reserved account's
AccountsService `Session` to `ubuntu` (the appropriate GNOME session on Fedora)
and `SessionType` to `wayland` through public setters, then log in graphically.
This seeds the known routing gap; it does not prove the original incident
trigger. Restore `Session=oh-no-parent-control` and `SessionType=wayland`.
The candidate should deny incorrect admission, repair defaults and permit a
later correct retry. Keep this fault injection in engineering tests; use public
customer actions and results for customer acceptance.

Remaining work:

1. Independently review the partial commit and its PAM/GDM assumptions.
2. Design and implement account-wide confinement across GDM launch, user-manager
   services, alternate login paths and executable/interpreter entry points.
   Fix generic causes in shared code and isolate platform-specific policy.
3. Preserve required Polkit authentication, notifications, the shared request
   form, wellbeing and other necessary product services.
4. Test alternate desktops, post-PAM selection timing, concurrent and interrupted
   attempts, unavailable dependencies, clean installation and upgrades.
5. Qualify supported Ubuntu. Fedora Workstation 44 packaging is prepared but is
   not release-qualified. Finish independent review with complete evidence.

Design pitfalls already identified:

- A fapolicyd allowlist alone can fail open when its daemon is absent or stopped.
- Generic Python, shell or GJS permissions can become arbitrary-code routes.
  Review imports, plugins, loaders, environment injection and memfd execution.
- Landlock may require `NoNewPrivileges`, which conflicts with the setuid Polkit
  authentication helper needed by the product.
- Restrictions applied inside systemd's PAM helper do not automatically confine
  the user manager. Privileged systemd command prefixes can bypass expected
  credential/PAM setup.
- A `nologin` shell alone does not constrain GDM's direct desktop execution.
- No final confinement design has been selected. These observations are inputs
  to design and validation, not a completed sandbox implementation.

Primary upstream inspection routes:

- [GDM 50.1 session worker](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-worker.c)
- [GDM 50.1 session settings](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-settings.c)
- [GDM 50.1 session selection and launch](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session.c)
- [GDM 50.1 Wayland session execution](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-wayland-session.c)
- [GNOME Session 50.0 leader](https://github.com/GNOME/gnome-session/blob/50.0/gnome-session/leader-main.c)

Follow the repository's current [agent instructions](../AGENTS.md). Start with
[System design](System-Design.md), then the affected lifecycle and application
policy modules. The [test documentation map](TestAutomation/README.md) routes
test ownership and acceptance requirements; [Approval tools](Approval-Tools.md)
owns command authorization. Use `make install` exclusively for product
installation and `./setup.sh` exclusively for development setup. Read the
[VM mandate](Mandates/VM-Mandate.MD) before VM operations and use maintained test
launchers. Do not return to or modify the released incident machine for the
remaining engineering work.
