"""Run postinst with fake commands and all system paths in a temporary tree.

No host service, account, process, or policy is changed.
"""

import subprocess

import pytest


from tests.support.paths import ROOT
BROKER = "oh-no-parent-control-broker.service"
REBOOT_NOTICE = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"


from tests.support.package_scripts import package_machine


@pytest.mark.parametrize("reboot", [False, True])
def test_configuration_output_ends_with_success_then_reboot_notice(package_machine, reboot):
    _, _, run = package_machine
    result = run(combine_output=True, IMPACTS="reboot" if reboot else "")
    assert result.returncode == 0, result.stdout
    success = (
        "\033[1;32mPASS: Oh No! Parent Control package configuration "
        "completed successfully.\033[0m"
    )
    expected = [success, REBOOT_NOTICE] if reboot else [success]
    assert result.stdout.splitlines()[-len(expected):] == expected
    assert result.stdout.count(success) == 1
    assert result.stdout.count(REBOOT_NOTICE) == int(reboot)


def test_apt_configuration_queues_notice_until_dpkg_finishes(package_machine):
    root, _, run = package_machine
    result = run(DPKG_FRONTEND_LOCKED="true", IMPACTS="reboot")
    assert result.returncode == 0, result.stderr
    assert "PASS:" not in result.stdout
    assert REBOOT_NOTICE not in result.stderr
    pending = root / "run/oh-no-parent-control-package-configuration-complete"
    assert pending.is_file()
    assert pending.stat().st_mode & 0o777 == 0o600
    result = run(DPKG_FRONTEND_LOCKED="true", BROKER_STATUS="1")
    assert result.returncode != 0
    assert not pending.exists(), "failed retries must discard earlier completion"


@pytest.mark.parametrize("impacts,action", [
    ("process-restart", "restart"), ("session-renewal", "restart"),
    ("reboot", "start"), ("", "start"),
    ("process-restart\nreboot", "restart"),
])
def test_configure_activates_static_broker_after_migration(package_machine, impacts, action):
    root, state, run = package_machine
    result = run(IMPACTS=impacts)
    assert result.returncode == 0, result.stderr
    commands = (root / "commands").read_text().splitlines()
    activation = f"systemctl --system {action} {BROKER}"
    assert commands.count(activation) == 1
    assert commands.index("oh-no-parent-control-migrate-state ") < commands.index(activation)
    assert commands.index(f"policy-rc.d {BROKER} {action}") < commands.index(activation)
    assert "inactive static unit skipped" not in result.stderr
    assert not (state / "package-activation-pending").exists()
    assert (root / "run/reboot-required").exists() == ("reboot" in impacts)
    assert ("notify-reboot-required " in commands) == ("reboot" in impacts)
    assert (REBOOT_NOTICE in result.stderr) == ("reboot" in impacts)
    assert "PASS: Oh No! Parent Control package configuration completed successfully." in result.stdout


@pytest.mark.parametrize("impacts", ["", "process-restart", "session-renewal", None],
                         ids=["reinstall", "broker-update", "session-update", "reconfigure"])
def test_reboot_marker_repeats_package_notice_until_reboot(package_machine, impacts):
    root, state, run = package_machine
    result = run(IMPACTS="reboot")
    assert result.returncode == 0, result.stderr
    assert result.stderr.count(REBOOT_NOTICE) == 1
    packages = root / "run/reboot-required.pkgs"
    original_packages = packages.read_text()

    for rebooted in (False, True):
        if rebooted:
            # A reboot clears these files from /run; only the fixture is changed.
            (root / "run/reboot-required").unlink()
            packages.unlink()
        if impacts is not None:
            # preinst records a new comparison for each reinstall or upgrade.
            (state / "package-activation-pending").touch()
            (state / "previous-package-activation.json").touch()
        result = run(IMPACTS=impacts or "")
        assert result.returncode == 0, result.stderr
        assert (REBOOT_NOTICE in result.stderr) == (not rebooted)
        assert not (state / "package-activation-pending").exists()
        if rebooted:
            assert not (root / "run/reboot-required").exists()
            assert not packages.exists()
        else:
            assert (root / "run/reboot-required").is_file()
            assert packages.read_text() == original_packages
    commands = (root / "commands").read_text().splitlines()
    assert commands.count("notify-reboot-required ") == 1


@pytest.mark.parametrize("packages", ["linux-base\ndbus\n", "oh-no-parent-control-extra\n"])
def test_other_packages_do_not_trigger_kiosk_reboot_notice(package_machine, packages):
    root, _, run = package_machine
    (root / "run/reboot-required").write_text("*** System restart required ***\n")
    package_marker = root / "run/reboot-required.pkgs"
    package_marker.write_text(packages)
    result = run(IMPACTS="")
    assert result.returncode == 0, result.stderr
    assert REBOOT_NOTICE not in result.stderr
    assert (root / "run/reboot-required").is_file()
    assert package_marker.read_text() == packages
    assert "notify-reboot-required " not in (root / "commands").read_text().splitlines()


@pytest.mark.parametrize("policy_status,success,activated", [
    ("0", True, True), ("104", True, True), ("101", True, False),
    ("102", False, False), ("106", False, False),
])
def test_configuration_respects_service_policy(package_machine, policy_status, success, activated):
    root, state, run = package_machine
    result = run(POLICY_STATUS=policy_status)
    assert (result.returncode == 0) == success, result.stderr
    commands = (root / "commands").read_text()
    assert (f"systemctl --system restart {BROKER}" in commands) == activated
    assert (state / "package-activation-pending").exists() != success
    if policy_status == "101":
        assert "deferred by policy-rc.d" in result.stderr


def test_configuration_without_policy_helper_starts_broker(package_machine):
    root, _, run = package_machine
    (root / "usr/sbin/policy-rc.d").unlink()
    result = run()
    assert result.returncode == 0, result.stderr
    assert f"systemctl --system restart {BROKER}" in (root / "commands").read_text()


def test_startup_failure_preserves_activation_for_retry(package_machine):
    root, state, run = package_machine
    result = run(BROKER_STATUS="1", IMPACTS="session-renewal\nreboot")
    assert result.returncode != 0
    assert "broker activation failed" in result.stderr
    assert (state / "package-activation-pending").exists()
    assert (state / "previous-package-activation.json").exists()
    result = run(IMPACTS="session-renewal\nreboot")
    assert result.returncode == 0, result.stderr
    assert not (state / "package-activation-pending").exists()
    assert (root / "commands").read_text().count(f"systemctl --system restart {BROKER}") == 2
    assert (root / "run/reboot-required.pkgs").read_text().splitlines() == ["oh-no-parent-control"]
    assert (root / "commands").read_text().splitlines().count("notify-reboot-required ") == 1


@pytest.mark.parametrize("defer", ["0", "1"])
def test_reboot_notification_preserves_other_package_requests(package_machine, defer):
    root, _, run = package_machine
    (root / "run/reboot-required").write_text("*** System restart required ***\n")
    packages = root / "run/reboot-required.pkgs"
    packages.write_text("linux-base\ndbus\n")
    result = run(IMPACTS="reboot", NOTIFIER_DEFER=defer)
    assert result.returncode == 0, result.stderr
    assert packages.read_text().splitlines() == ["linux-base", "dbus", "oh-no-parent-control"]
    assert (root / "run/reboot-required").is_file()


def test_notification_failure_retains_comparison_for_retry(package_machine):
    root, state, run = package_machine
    result = run(IMPACTS="reboot", NOTIFIER_STATUS="1")
    assert result.returncode != 0
    assert (state / "package-activation-pending").exists()
    assert (state / "previous-package-activation.json").exists()
    result = run(IMPACTS="reboot")
    assert result.returncode == 0, result.stderr
    assert (root / "run/reboot-required.pkgs").read_text().splitlines() == ["oh-no-parent-control"]


def test_migration_failure_prevents_broker_activation(package_machine):
    root, state, run = package_machine
    result = run(MIGRATION_STATUS="1")
    assert result.returncode != 0
    assert (state / "migration-in-progress").exists()
    assert (state / "package-activation-pending").exists()
    assert "systemctl" not in (root / "commands").read_text()


def test_configure_without_pending_comparison_starts_broker(package_machine):
    root, state, run = package_machine
    (state / "package-activation-pending").unlink()
    result = run()
    assert result.returncode == 0, result.stderr
    assert f"systemctl --system start {BROKER}" in (root / "commands").read_text()
    assert not (root / "run/reboot-required").exists()


def test_debhelper_automatic_activation_is_disabled():
    result = subprocess.run(
        ["make", "-n", "-f", "debian/rules", "override_dh_installsystemd"],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "dh_installsystemd --no-start --no-stop-on-upgrade" in result.stdout


@pytest.mark.parametrize("profiles,expected", [("0 unix, malcontent", "enabled"), ("0 unix, systemd", "disabled")])
def test_original_pam_selection_is_saved_once(package_machine, profiles, expected):
    _, state, run = package_machine
    result = run(PAM_PROFILES=profiles)
    assert result.returncode == 0, result.stderr
    baseline = state / "malcontent-pam-before-install"
    assert baseline.read_text() == expected + "\n"
    result = run(PAM_PROFILES="0 unix")
    assert result.returncode == 0, result.stderr
    assert baseline.read_text() == expected + "\n"


def test_unowned_kiosk_is_rejected_before_any_configuration(package_machine):
    root, state, run = package_machine
    (state / "package-created-kiosk-uid").unlink()
    result = run()
    assert result.returncode != 0
    commands = (root / "commands").read_text()
    assert "usermod" not in commands
    assert not any(line.startswith("passwd ") for line in commands.splitlines())
    assert "migrate-state" not in commands


def test_local_pam_configuration_cannot_silently_skip_enforcement(package_machine):
    root, _, run = package_machine
    (root / "etc/pam.d/common-auth").write_text("auth required pam_unix.so\n")
    result = run(PAM_LOCAL_CHANGES="1")
    assert result.returncode != 0
    assert "PAM integration was not activated" in result.stderr
    assert f"systemctl --system restart {BROKER}" not in (root / "commands").read_text()


def test_missing_generated_integrations_are_recreated_on_reinstall(package_machine):
    root, state, run = package_machine
    result = run()
    assert result.returncode == 0, result.stderr
    for target in ("etc/gdm3/PreSession/Default", "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules"):
        (root / target).unlink()
    result = run()
    assert result.returncode == 0, result.stderr
    assert (root / "etc/gdm3/PreSession/Default").read_bytes() == (state / "installed-gdm-presession").read_bytes()
    assert (root / "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules").read_bytes() == (state / "installed-fapolicyd-fallback").read_bytes()
