import configparser
import shlex
import subprocess
import unittest


from tests.support.paths import ROOT
BROKER_UNIT = ROOT / "data/systemd/oh-no-parent-control-broker.service"
FAPOLICYD_DROP_IN = (
    ROOT / "data/systemd/fapolicyd.service.d/oh-no-parent-control-readiness.conf"
)
DISPLAY_MANAGER_DROP_IN = (
    ROOT / "data/systemd/display-manager.service.d/oh-no-parent-control.conf"
)
FAPOLICYD_FALLBACK = ROOT / "data/fapolicyd/99-oh-no-parent-control-allow.rules"


def test_kiosk_notification_script_loads_without_a_package_context(tmp_path):
    unit = configparser.ConfigParser(interpolation=None)
    unit.read(ROOT / 'data/systemd/user/oh-no-parent-control-notifications.service')
    command = shlex.split(unit['Service']['ExecStart'])
    interpreter, installed_script = command[2:]
    script = ROOT / installed_script.removeprefix('/usr/lib/oh-no-parent-control/')
    # Match direct-file execution's empty package context without opening a
    # window or bus. Disable Apport in this owned child so a regression cannot
    # generate a host crash report. Real imports catch launch-only failures
    # which the preview's package import does not exercise.
    result = subprocess.run(
        [interpreter, '-I', '-B', '-c',
         'import runpy, sys; sys.excepthook = sys.__excepthook__; '
         'runpy.run_path(sys.argv[1])', str(script)],
        cwd=tmp_path,
        env={'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path),
             'XDG_CACHE_HOME': str(tmp_path / 'cache'), 'LC_ALL': 'C.UTF-8'},
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_kiosk_excludes_systemd_crash_notifier_with_stop_ordering():
    source = (ROOT / 'data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf').read_text()
    settings = {}
    for line in source.splitlines():
        key, separator, value = line.partition('=')
        if separator:
            settings.setdefault(key, set()).update(value.split())
    notifier = {'update-notifier-crash.path', 'update-notifier-crash.service'}
    assert notifier <= settings['Conflicts']
    assert notifier <= settings['After']
    # Suppression must leave the request form and its notification provider
    # in the kiosk transaction, rather than disabling notifications globally.
    assert 'oh-no-parent-control-app.service' in settings['Requires']
    assert 'oh-no-parent-control-notifications.service' in settings['Wants']


class BrokerServiceUnitTests(unittest.TestCase):
    def test_kiosk_agent_locale_is_limited_to_its_own_service(self):
        agent = (ROOT / 'data/systemd/user/oh-no-parent-control-polkit-agent.service').read_text()
        self.assertIn('EnvironmentFile=-%t/oh-no-parent-control/polkit-agent.env', agent)
    def test_offline_session_bus_can_monitor_selinux_without_internet_sockets(self):
        unit = configparser.ConfigParser(strict=False, interpolation=None)
        unit.read(BROKER_UNIT, encoding="utf-8")
        service = unit["Service"]
        self.assertEqual(
            set(service["RestrictAddressFamilies"].split()),
            {"AF_UNIX", "AF_NETLINK"},
        )
        for key, value in {
            "NoNewPrivileges": "yes", "PrivateDevices": "yes",
            "PrivateTmp": "yes", "ProtectSystem": "strict",
            "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
            "ProtectControlGroups": "yes", "RestrictNamespaces": "yes",
            "LockPersonality": "yes", "MemoryDenyWriteExecute": "yes",
            "SystemCallArchitectures": "native",
        }.items():
            with self.subTest(key=key):
                self.assertEqual(service[key], value)

    def test_child_identity_capabilities_survive_broker_exec(self):
        settings = {}
        for raw_line in BROKER_UNIT.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith(("#", "[")) and "=" in line:
                key, value = line.split("=", 1)
                settings[key] = value.split()

        bounded = set(settings["CapabilityBoundingSet"])
        ambient = set(settings["AmbientCapabilities"])

        self.assertEqual(ambient, {"CAP_SETGID", "CAP_SETUID"})
        self.assertTrue(ambient <= bounded)
        self.assertTrue(
            {
                "CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_FOWNER", "CAP_KILL",
                "CAP_SYS_PTRACE",
            } <= bounded
        )
        self.assertNotIn("CAP_SYS_PTRACE", ambient)

    def test_broker_starts_with_and_can_reload_execution_policy(self):
        source = BROKER_UNIT.read_text(encoding="utf-8")

        self.assertIn("Wants=fapolicyd.service", source)
        self.assertNotIn("Requires=fapolicyd.service", source)
        self.assertIn("After=fapolicyd.service", source)
        self.assertIn("ReadWritePaths=/etc/fapolicyd", source)

    def test_display_manager_waits_for_real_execution_enforcement(self):
        fapolicyd = FAPOLICYD_DROP_IN.read_text(encoding="utf-8")
        display_manager = DISPLAY_MANAGER_DROP_IN.read_text(encoding="utf-8")
        fallback = FAPOLICYD_FALLBACK.read_text(encoding="utf-8")

        self.assertIn(
            "ExecStartPost=/usr/libexec/oh-no-parent-control-execution-policy-ready",
            fapolicyd,
        )
        self.assertIn("Requires=fapolicyd.service", display_manager)
        self.assertIn("After=fapolicyd.service", display_manager)
        canary = (
            "deny perm=execute uid=0 : "
            "path=/usr/libexec/oh-no-parent-control-execution-policy-probe"
        )
        self.assertIn(canary, fallback)
        self.assertLess(
            fallback.index(canary), fallback.index("allow perm=any all : all")
        )

    def test_boot_checks_child_trust_before_admitting_graphical_logins(self):
        source = FAPOLICYD_DROP_IN.read_text()
        checks = [line.partition('=')[2] for line in source.splitlines()
                  if line.startswith('ExecStartPost=')]
        self.assertEqual(checks, [
            '/usr/libexec/oh-no-parent-control-execution-policy-ready',
            '/usr/libexec/oh-no-parent-control-package-activation wait-child-trust',
        ])
        self.assertIn('TimeoutStartSec=180', source)
        # Trust gates policy in the launcher/service, while diagnostics must
        # remain activatable to explain the pending reboot to support.
        self.assertNotIn('ConditionPathExists=!/run/oh-no-parent-control-child-trust-reboot',
                         BROKER_UNIT.read_text())
        self.assertIn('ConditionPathExists=!/var/lib/oh-no-parent-control/migration-in-progress',
                      BROKER_UNIT.read_text())

    def test_broker_start_budget_allows_the_child_trust_deadline(self):
        unit = configparser.ConfigParser(strict=False, interpolation=None)
        unit.read(BROKER_UNIT, encoding='utf-8')
        # The launcher can spend 125 seconds awaiting the helper before it
        # constructs the broker and acquires its D-Bus name.
        self.assertGreater(int(unit['Service']['TimeoutStartSec']), 125)


if __name__ == "__main__":
    unittest.main()
