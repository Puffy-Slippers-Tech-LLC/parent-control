import configparser
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


class BrokerServiceUnitTests(unittest.TestCase):
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
        self.assertIn('ConditionPathExists=!/run/oh-no-parent-control-child-trust-reboot',
                      BROKER_UNIT.read_text())

    def test_broker_start_budget_allows_the_child_trust_deadline(self):
        unit = configparser.ConfigParser(strict=False, interpolation=None)
        unit.read(BROKER_UNIT, encoding='utf-8')
        # The launcher can spend 125 seconds awaiting the helper before it
        # constructs the broker and acquires its D-Bus name.
        self.assertGreater(int(unit['Service']['TimeoutStartSec']), 125)


if __name__ == "__main__":
    unittest.main()
