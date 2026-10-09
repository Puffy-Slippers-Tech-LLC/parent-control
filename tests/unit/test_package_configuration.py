"""Run postinst with fake commands and all system paths in a temporary tree.

No host service, account, process, or policy is changed.
"""

import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


from tests.support.paths import ROOT
BROKER = "oh-no-parent-control-broker.service"
REBOOT_NOTICE = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"


from tests.support.package_scripts import package_machine, use_real_state_migration


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('schema', [1, 2, 3, 4])
def test_v1_4_configuration_upgrades_legacy_policy_without_losing_choices(package_machine, schema):
    from oh_no_parent_control.preferences import PreferenceStore

    root, state, run = package_machine
    use_real_state_migration(root)
    product = root / 'usr/share/oh-no-parent-control/app.json'
    product.write_text('{"version": "1.4"}')
    (state / 'previous-product.json').write_text('{"version": "1.3"}')
    (state / 'previous-product.json').chmod(0o600)
    entry = {'state': 'conditional', 'targets': ['/opt/game/game']}
    if schema >= 2:
        entry['patterns'] = ['/opt/game/*']
    if schema >= 3:
        entry['user_saved_match_rule'] = True
    legacy = {
        'version': schema, 'parent_control_enabled': True,
        'daily_time_limit_minutes': 75, 'apps': {'game.desktop': entry},
        'request': {'last_selected_duration': 'custom', 'last_custom_minutes': 12.5,
                    'allow_soft_blocked_apps': True, 'last_selected_approver_uid': 1003,
                    'child_muted': False, 'kiosk_muted': False},
    }
    if schema == 4:
        legacy['personal'] = {'language': 'fr'}
    directory = state / 'preferences'
    directory.mkdir(mode=0o700)
    record = directory / '1001.json'
    record.write_text(json.dumps(legacy))
    record.chmod(0o600)
    before = record.read_bytes()
    # Reconfiguration must establish its own exclusion and stop a running broker.
    (state / 'migration-in-progress').unlink()
    (root / 'broker-active').touch()

    result = run()
    assert result.returncode == 0, result.stderr
    saved = PreferenceStore(directory).load(1001)
    assert saved['version'] == 4
    assert saved['parent_control_enabled'] is True
    assert saved['daily_time_limit_minutes'] == 75
    assert saved['request'] == legacy['request']
    assert saved['apps'] == {'game.desktop': {
        **entry, 'patterns': ['/opt/game/*'] if schema >= 2 else [],
        'user_saved_match_rule': schema >= 2,
    }}
    assert saved['personal'] == {
        'language': 'fr' if schema == 4 else '',
        'time_grant_presets': [300, 900, 1800, 3600, 7200, 14400],
        'notifications': {'show_in_fullscreen': True, 'reminders': [
            {'id': name, 'value': value, 'unit': unit, 'text': ''}
            for name, value, unit in [('ten-minutes', 10, 'minute'), ('five-minutes', 5, 'minute'),
                                     ('one-minute', 1, 'minute'), ('fifteen-seconds', 15, 'second')]]
        },
    }
    if schema == 4:
        assert record.read_bytes() == before, 'compatible additions need no on-disk rewrite'
    assert record.stat().st_mode & 0o777 == 0o600
    assert json.loads((state / 'whats-new-installation.json').read_text()) == {
        'version': 1, 'first_version': '1.3', 'current_version': '1.4',
    }
    assert not (state / 'previous-product.json').exists()
    commands = (root / 'commands').read_text().splitlines()
    assert commands.index('oh-no-parent-control-migrate-state ') < commands.index(
        f'systemctl --system restart {BROKER}')
    after = record.read_bytes()
    result = run()
    assert result.returncode == 0, result.stderr
    assert record.read_bytes() == after


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('personal_only', [False, True])
@pytest.mark.parametrize('fields', ['reminders', 'presets', 'both', 'empty'])
def test_v1_4_configuration_retains_personal_customizations(package_machine, personal_only, fields):
    from oh_no_parent_control.preferences import PreferenceStore, default_preferences

    root, state, run = package_machine
    use_real_state_migration(root)
    (root / 'usr/share/oh-no-parent-control/app.json').write_text('{"version": "1.4"}')
    personal = {'language': 'fr', 'whats_new_seen': ['1.3:Child']}
    if fields in ('reminders', 'both', 'empty'):
        personal['notifications'] = {'show_in_fullscreen': False, 'reminders': [] if fields == 'empty' else [
            {'id': 'save-game', 'value': 42, 'unit': 'second', 'text': '  Save <game>!  '}]}
    if fields in ('presets', 'both', 'empty'):
        personal['time_grant_presets'] = [] if fields == 'empty' else [123, 6, 86400]
    value = {'version': 4, 'personal': personal}
    if not personal_only:
        value = {**default_preferences(), **value}
        # A remembered duration remains valid even when deleted from presets.
        value['request']['last_selected_duration'] = '900'
    directory = state / 'preferences'
    directory.mkdir(mode=0o700)
    record = directory / '0.json'
    record.write_text(json.dumps(value))
    record.chmod(0o600)
    before = record.read_bytes()

    for _ in range(2):
        result = run()
        assert result.returncode == 0, result.stderr
        assert record.read_bytes() == before
        saved = PreferenceStore(directory).load(0)
        assert saved['personal']['language'] == 'fr'
        assert saved['personal']['whats_new_seen'] == ['1.3:Child']
        if 'notifications' in personal:
            assert saved['personal']['notifications'] == personal['notifications']
        if 'time_grant_presets' in personal:
            assert saved['personal']['time_grant_presets'] == sorted(personal['time_grant_presets'])
        if not personal_only:
            assert saved['request'] == value['request']


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('invalid', [
    {'version': 5, 'personal': {'language': ''}},
    {'version': 4, 'personal': {'language': '', 'time_grant_presets': [0]}},
    {'version': 4, 'personal': {'language': '', 'notifications': {}}},
], ids=['future-schema', 'invalid-presets', 'invalid-reminders'])
def test_v1_4_configuration_validation_failure_blocks_activation_and_allows_retry(package_machine, invalid):
    root, state, run = package_machine
    use_real_state_migration(root)
    (root / 'usr/share/oh-no-parent-control/app.json').write_text('{"version": "1.4"}')
    directory = state / 'preferences'
    directory.mkdir(mode=0o700)
    record = directory / '1001.json'
    record.write_text(json.dumps(invalid))
    record.chmod(0o600)
    before = record.read_bytes()

    result = run()
    assert result.returncode != 0
    assert (state / 'migration-in-progress').exists()
    assert record.read_bytes() == before
    assert f'--system restart {BROKER}' not in (root / 'commands').read_text()
    assert f'--system start {BROKER}' not in (root / 'commands').read_text()
    assert not (state / 'whats-new-installation.json').exists()

    # Model correcting the rejected input, then retry normal configuration.
    record.write_text('{"version": 4, "personal": {"language": "fr"}}')
    corrected = record.read_bytes()
    result = run()
    assert result.returncode == 0, result.stderr
    assert not (state / 'migration-in-progress').exists()
    assert record.read_bytes() == corrected


@pytest.mark.parametrize('package_machine', ['fedora'], indirect=True)
def test_native_policy_directory_permissions_and_restore_order_survive_retry(package_machine):
    root, state, run = package_machine
    for relative in ('etc/fapolicyd/rules.d', 'etc/fapolicyd/trust.d'):
        directory = root / relative
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o750)
    (state / 'uninstall-enforcement.json').write_text('{}')
    helper = root / 'usr/libexec/oh-no-parent-control-uninstall'
    helper.write_text('''#!/bin/sh
test "$1" = --restore || exit 96
test -f "$AUDIT_ROOT/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules" || exit 97
test -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 98
printf '%s\\n' 'restored original-policy snapshot' >> "$AUDIT_ROOT/commands"
''')
    helper.chmod(0o755)
    result = run(ORIGINAL_POLICY_ELIGIBLE='yes', ORIGINAL_POLICY_COMMIT_STATUS='7')
    assert result.returncode == 7
    assert 'restored original-policy snapshot' not in (root / 'commands').read_text()
    result = run(ORIGINAL_POLICY_ELIGIBLE='yes')
    assert result.returncode == 0, result.stderr
    commands = (root / 'commands').read_text().splitlines()
    assert commands.index('oh-no-parent-control-fedora-execution-policy commit') < commands.index(
        'restored original-policy snapshot')
    for relative in ('etc/fapolicyd/rules.d', 'etc/fapolicyd/trust.d'):
        assert (root / relative).stat().st_mode & 0o777 == 0o750


@pytest.mark.parametrize("boot_order_changed", [False, True])
def test_v1_1_upgrade_uses_real_activation_manifest(package_machine, boot_order_changed):
    root, state, run = package_machine
    activation = runpy.run_path(str(ROOT / "debian/package_activation.py"))
    # v1.1 marked all three diagnostic-only changes as requiring a reboot.
    old_levels = {
        "usr/libexec/oh-no-parent-control-session-limit-check": "reboot",
        "usr/libexec/oh-no-parent-control-execution-policy-ready": "reboot",
        "usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so": "reboot",
        "usr/libexec/oh-no-parent-control-broker": "process-restart",
        "usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/extension.js": "session-renewal",
        "usr/lib/systemd/system/display-manager.service.d/oh-no-parent-control.conf": "reboot",
    }
    old_files = []
    for path, level in old_levels.items():
        old_files.append({
            "path": path,
            "sha256": hashlib.sha256(b"old payload").hexdigest(),
            "activation": level,
        })
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        changed = boot_order_changed or "display-manager.service.d/" not in path
        target.write_text("updated payload" if changed else "old payload")
    (state / "previous-package-activation.json").write_text(json.dumps({
        "version": 1, "files": old_files,
    }))
    activation["generate"](
        root, root / "usr/share/oh-no-parent-control/package-activation.json",
        [Path(path) for path in old_levels],
    )
    # Replace only this fixture's comparison stub with the shipped helper.
    helper = root / "usr/libexec/oh-no-parent-control-package-activation"
    helper.unlink()
    source = (ROOT / "packaging/package_activation.py").read_text()
    # Only comparison runs for real in this relocated machine. Keep the
    # daemon-readiness double: the host has neither this fixture's installed
    # trust file nor a fixture fapolicyd database. Exact live-record matching
    # has separate helper tests, and lifecycle tests cover its failure status.
    source = source.replace('    args = parser.parse_args()',
        '    args = parser.parse_args()\n'
        '    if args.command == "prepare-child-trust-backend":\n'
        '        print("none")\n'
        '        raise SystemExit(0)\n'
        '    if args.command == "complete-child-trust-backend":\n'
        '        raise SystemExit(0)\n'
        '    if args.command == "wait-child-trust":\n'
        '        import os\n'
        '        raise SystemExit(int(os.environ.get("TRUST_READY_STATUS", "0")))')
    helper.write_text(f"#!{sys.executable}\n" + source.split("\n", 1)[1])
    helper.chmod(0o755)

    result = run()
    assert result.returncode == 0, result.stderr
    commands = (root / "commands").read_text().splitlines()
    assert f"systemctl --system restart {BROKER}" in commands
    assert ("notify-reboot-required " in commands) == boot_order_changed
    assert (root / "run/reboot-required").exists() == boot_order_changed
    assert (REBOOT_NOTICE in result.stderr) == boot_order_changed


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


def test_ubuntu_does_not_start_fedora_readiness_unit(package_machine):
    root, _, run = package_machine
    result = run(READINESS_STATUS='9')
    assert result.returncode == 0, result.stderr
    assert 'oh-no-parent-control-execution-policy-ready.service' not in (root / 'commands').read_text()
    assert 'fagenrules' not in (root / 'commands').read_text()
    assert 'fapolicyd-cli --reload-rules' not in (root / 'commands').read_text()


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
    assert f"systemctl --system start {BROKER}" not in (root / "commands").read_text()
    assert f"systemctl --system restart {BROKER}" not in (root / "commands").read_text()


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


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
def test_child_module_trust_install_upgrade_and_reinstall(package_machine):
    root, state, run = package_machine
    template = root / 'usr/share/oh-no-parent-control/child-extension.trust'
    target = root / 'etc/fapolicyd/trust.d/oh-no-parent-control.trust'
    record = state / 'installed-child-extension-trust'
    # Existing administrator trust and the distribution filter are never edited.
    admin = target.parent / 'administrator.trust'
    admin.parent.mkdir(parents=True)
    admin.write_text('administrator trust\n')
    filter_path = root / 'etc/fapolicyd/fapolicyd-filter.conf'
    filter_path.write_text('+ /\n - usr/share/\n  + *.js\n')
    for payload in ('first packaged hashes\n', 'replacement packaged hashes\n'):
        template.write_text(payload)
        result = run()
        assert result.returncode == 0, result.stderr
        assert target.read_text() == record.read_text() == payload
        assert target.stat().st_mode & 0o777 == 0o644
        assert record.stat().st_mode & 0o777 == 0o600
    target.unlink()
    assert run().returncode == 0
    assert target.read_bytes() == template.read_bytes()
    assert admin.read_text() == 'administrator trust\n'
    assert filter_path.read_text() == '+ /\n - usr/share/\n  + *.js\n'
    commands = (root / 'commands').read_text().splitlines()
    refresh = commands.index('fapolicyd-cli --update')
    ready = commands.index('oh-no-parent-control-package-activation wait-child-trust --refresh')
    assert ready < refresh < commands.index(f'systemctl --system restart {BROKER}')


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('failure', ['TRUST_UPDATE_STATUS', 'TRUST_READY_STATUS'])
def test_child_trust_refresh_failure_blocks_activation_and_is_retryable(package_machine, failure):
    root, state, run = package_machine
    result = run(**{failure: '7'})
    assert result.returncode == 7
    assert (state / 'package-activation-pending').exists()
    assert (state / 'migration-in-progress').exists()
    assert f'systemctl --system restart {BROKER}' not in (root / 'commands').read_text()
    assert run().returncode == 0
    assert not (state / 'package-activation-pending').exists()
    assert not (state / 'migration-in-progress').exists()


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('state', ['inactive', 'failed', 'active', 'activating', 'deactivating'])
def test_canceled_stop_requires_confirmed_broker_exit_before_migration(package_machine, state):
    root, saved, run = package_machine
    (root / 'broker-active').touch()
    result = run(BROKER_STOP_STATUS='1', BROKER_STOP_STATE=state)
    stopped = state in ('inactive', 'failed')
    assert (result.returncode == 0) == stopped, result.stderr
    commands = (root / 'commands').read_text()
    assert ('oh-no-parent-control-migrate-state ' in commands) == stopped
    assert (saved / 'migration-in-progress').exists() != stopped
    assert (f'systemctl --system restart {BROKER}' in commands) == stopped


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('stop_refused', [False, True])
def test_reconfigure_guards_and_stops_an_existing_broker(package_machine, stop_refused):
    root, state, run = package_machine
    (state / 'migration-in-progress').unlink()
    (root / 'broker-active').touch()
    result = run(BROKER_STOP_REFUSED=str(int(stop_refused)))
    commands = (root / 'commands').read_text()
    if stop_refused:
        assert result.returncode != 0
        assert (state / 'migration-in-progress').exists()
        assert 'oh-no-parent-control-migrate-state ' not in commands
        assert 'wait-child-trust' not in commands
    else:
        assert result.returncode == 0, result.stderr
        assert not (state / 'migration-in-progress').exists()
        assert commands.index(f'stop {BROKER}') < commands.index('oh-no-parent-control-migrate-state ')


@pytest.mark.parametrize('package_machine', ['ubuntu', 'fedora'], indirect=True)
def test_dbus_startup_exclusion_survives_until_trust_is_ready(package_machine):
    root, state, run = package_machine
    # Model a concurrent activation at the actual readiness boundary using the
    # two shipped startup checks, without a host bus or installed service.
    launcher = root / 'broker-launcher'
    source = (ROOT / 'broker/oh-no-parent-control-broker').read_text()
    source = source.replace('/var/lib/oh-no-parent-control', str(state))
    source = source.replace('/run/oh-no-parent-control-child-trust-reboot',
                            str(root / 'run/oh-no-parent-control-child-trust-reboot'))
    launcher.write_text(source.split('# Check trust', 1)[0] + 'raise SystemExit(0)\n')
    unit = (ROOT / 'data/systemd/oh-no-parent-control-broker.service').read_text()
    assert 'ConditionPathExists=!/var/lib/oh-no-parent-control/migration-in-progress' in unit
    helper = root / 'usr/libexec/oh-no-parent-control-package-activation'
    helper.unlink()
    helper.write_text(f'''#!{sys.executable}
import pathlib, subprocess, sys
if sys.argv[1] == 'wait-child-trust':
    assert pathlib.Path({str(state / 'migration-in-progress')!r}).is_file()
    result = subprocess.run([{sys.executable!r}, {str(launcher)!r}], capture_output=True)
    assert result.returncode != 0
    assert b'saved-data migration is incomplete' in result.stderr
elif sys.argv[1] == 'prepare-child-trust-backend':
    print('none')
else:
    print('process-restart')
''')
    helper.chmod(0o755)
    result = run()
    assert result.returncode == 0, result.stderr
    assert subprocess.run([sys.executable, str(launcher)], capture_output=True).returncode == 0


@pytest.mark.parametrize('active', [False, True])
def test_backend_change_preserves_active_desktops_and_configuration_guard(package_machine, active):
    root, state, run = package_machine
    result = run(TRUST_BACKEND_ACTION='changed', FAPOLICYD_ACTIVE_STATUS='0' if active else '3')
    commands = (root / 'commands').read_text()
    assert 'restart fapolicyd.service' not in commands
    assert result.returncode == 0, result.stderr
    assert not (state / 'migration-in-progress').exists()
    assert not (state / 'package-activation-pending').exists()
    if active:
        assert 'activation deferred until reboot' in result.stderr
        guard = root / 'run/oh-no-parent-control-child-trust-reboot'
        assert guard.is_file()
        assert guard.stat().st_mode & 0o777 == 0o600
        assert (root / 'run/reboot-required').exists()
        assert (root / 'run/reboot-required.pkgs').read_text().splitlines() == ['oh-no-parent-control']
        assert REBOOT_NOTICE in result.stderr
        assert 'wait-child-trust' not in commands
        assert f'systemctl --system restart {BROKER}' not in commands
        assert f'systemctl --system start {BROKER}' not in commands
        # An unchanged same-boot reconfigure must retain the activation guard.
        assert run().returncode == 0
        assert guard.exists()
        assert (root / 'run/reboot-required.pkgs').read_text().splitlines() == ['oh-no-parent-control']
    else:
        # This double keeps the daemon stopped after the package-service call.
        assert 'deb-systemd-invoke start fapolicyd.service' in commands
        assert not (root / 'run/oh-no-parent-control-child-trust-reboot').exists()


def test_backend_acknowledgement_failure_blocks_activation(package_machine):
    root, state, run = package_machine
    result = run(TRUST_COMPLETE_STATUS='7')
    assert result.returncode == 7
    assert (state / 'migration-in-progress').exists()
    assert (state / 'package-activation-pending').exists()
    assert f'systemctl --system restart {BROKER}' not in (root / 'commands').read_text()
    assert run().returncode == 0


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('active', [False, True])
def test_real_backend_upgrade_completes_and_broker_guard_expires_on_reboot(package_machine, legacy, active):
    root, state, run = package_machine
    # The real helper also compares manifests. Give it valid equal manifests
    # so only the backend transition can require a reboot in this scenario.
    manifest = json.dumps({'version': 1, 'files': []})
    (state / 'previous-package-activation.json').write_text(manifest)
    (root / 'usr/share/oh-no-parent-control/package-activation.json').write_text(manifest)
    config = root / 'etc/fapolicyd/fapolicyd.conf'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('trust = debdb\n')
    receipt = state / 'child-trust-backend'
    if legacy:
        receipt.mkdir()
        (receipt / 'before').write_bytes(config.read_bytes())
        config.write_text('trust = debdb,file\n')
        (receipt / 'after').write_bytes(config.read_bytes())
    boot = root / 'boot-id'
    boot.write_text('11111111-1111-1111-1111-111111111111\n')
    helper = root / 'usr/libexec/oh-no-parent-control-package-activation'
    helper.unlink()
    source = (ROOT / 'packaging/package_activation.py').read_text()
    source = source.replace('/etc/fapolicyd/fapolicyd.conf', str(config))
    source = source.replace('/var/lib/oh-no-parent-control/child-trust-backend', str(receipt))
    source = source.replace('/proc/sys/kernel/random/boot_id', str(boot))
    # Only the live database is doubled; configuration and receipts run for real.
    source = source.replace('    args = parser.parse_args()',
        '    args = parser.parse_args()\n'
        '    if args.command == "wait-child-trust":\n'
        '        import os\n'
        '        if args.refresh:\n'
        '            subprocess.run([os.environ["AUDIT_ROOT"] + "/usr/sbin/fapolicyd-cli", "--update"], check=True)\n'
        '        raise SystemExit(int(os.environ.get("TRUST_READY_STATUS", "0")))')
    helper.write_text(f'#!{sys.executable}\n' + source.split('\n', 1)[1])
    helper.chmod(0o755)
    launcher = root / 'broker-launcher'
    source = (ROOT / 'broker/oh-no-parent-control-broker').read_text()
    source = source.replace('/var/lib/oh-no-parent-control', str(state))
    guard = root / 'run/oh-no-parent-control-child-trust-reboot'
    source = source.replace('/run/', str(root / 'run') + '/')
    source = source.replace('/usr/libexec/oh-no-parent-control-package-activation', str(helper))
    launcher.write_text(source.split('sys.path.insert', 1)[0] +
                        'print("diagnostics-only" if diagnostics_only else "policy-ready")\n')
    for _ in range(2):
        result = run(IMPACTS='', FAPOLICYD_ACTIVE_STATUS='0' if active else '3',
                     FAPOLICYD_STARTS='1')
        assert result.returncode == 0, result.stderr
        assert 'PASS:' in result.stdout
        assert guard.exists() == active
        blocked = subprocess.run([sys.executable, str(launcher)], capture_output=True)
        if active:
            assert blocked.returncode == 0, blocked.stderr
            assert blocked.stdout.strip() == b'diagnostics-only'
        else:
            assert blocked.returncode == 0, blocked.stderr
            assert blocked.stdout.strip() == b'policy-ready'
            assert (receipt / 'activation').read_text() == 'ready\n'
            commands = (root / 'commands').read_text()
            assert f'systemctl --system start {BROKER}' in commands
            assert 'fapolicyd-cli --update' in commands
            assert not (root / 'run/reboot-required').exists()
    # Reboot clears volatile state; successful postinst already released migration.
    assert not (state / 'migration-in-progress').exists()
    if active:
        guard.unlink()
    boot.write_text('22222222-2222-2222-2222-222222222222\n')
    assert subprocess.run([sys.executable, str(launcher)], capture_output=True).returncode == 0
    # Expiring the guard is insufficient if live exact trust is still missing.
    import os
    blocked = subprocess.run([sys.executable, str(launcher)], capture_output=True,
                             env={**os.environ, 'TRUST_READY_STATUS': '7'})
    assert blocked.returncode != 0
    assert b'child trust database is not ready' in blocked.stderr
    result = run(IMPACTS='')
    assert result.returncode == 0, result.stderr
    assert (receipt / 'activation').read_text() == 'ready\n'
    assert not guard.exists()
    # An unrelated OS update must not put this broker into diagnostics-only mode.
    (root / 'run/reboot-required').write_text('System restart required\n')
    (root / 'run/reboot-required.pkgs').write_text('linux-image-generic\nlibc6\n')
    allowed = subprocess.run([sys.executable, str(launcher)], capture_output=True)
    assert allowed.returncode == 0, allowed.stderr
    assert allowed.stdout.strip() == b'policy-ready'


def test_deferred_backend_notifier_failure_remains_retryable(package_machine):
    root, state, run = package_machine
    result = run(TRUST_BACKEND_ACTION='changed', NOTIFIER_STATUS='7')
    assert result.returncode == 7
    assert (state / 'migration-in-progress').exists()
    assert (state / 'package-activation-pending').exists()
    assert (root / 'run/oh-no-parent-control-child-trust-reboot').exists()
    assert run().returncode == 0


def test_substituted_deferred_backend_guard_is_preserved(package_machine):
    root, state, run = package_machine
    sentinel = root / 'sentinel'
    sentinel.write_text('preserve\n')
    (root / 'run/oh-no-parent-control-child-trust-reboot').symlink_to(sentinel)
    result = run(TRUST_BACKEND_ACTION='changed')
    assert result.returncode != 0
    assert sentinel.read_text() == 'preserve\n'
    assert (state / 'migration-in-progress').exists()


def test_deferred_daemon_start_does_not_request_trust_refresh(package_machine):
    root, _, run = package_machine
    assert run(FAPOLICYD_ACTIVE_STATUS='3', POLICY_STATUS='101').returncode == 0
    assert 'fapolicyd-cli --update' not in (root / 'commands').read_text()
    assert (root / 'etc/fapolicyd/trust.d/oh-no-parent-control.trust').is_file()


@pytest.mark.parametrize('substitution', ['modified', 'target-link', 'directory-link', 'record-link'])
def test_child_trust_configuration_preserves_modified_or_substituted_paths(package_machine, substitution):
    root, state, run = package_machine
    assert run().returncode == 0
    target = root / 'etc/fapolicyd/trust.d/oh-no-parent-control.trust'
    record = state / 'installed-child-extension-trust'
    sentinel = root / 'sentinel'
    sentinel.write_text('keep administrator content\n')
    if substitution == 'modified':
        target.write_bytes(sentinel.read_bytes())
    elif substitution == 'target-link':
        target.unlink()
        target.symlink_to(sentinel)
    elif substitution == 'record-link':
        record.unlink()
        record.symlink_to(sentinel)
    else:
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(sentinel.parent)
    assert run().returncode != 0
    assert sentinel.read_text() == 'keep administrator content\n'
