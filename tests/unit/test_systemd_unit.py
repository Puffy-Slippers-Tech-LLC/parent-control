import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BROKER_UNIT = ROOT / "data/systemd/oh-no-parent-control-broker.service"
FAPOLICYD_DROP_IN = (
    ROOT / "data/systemd/fapolicyd.service.d/oh-no-parent-control-readiness.conf"
)
DISPLAY_MANAGER_DROP_IN = (
    ROOT / "data/systemd/display-manager.service.d/oh-no-parent-control.conf"
)
FAPOLICYD_FALLBACK = ROOT / "data/fapolicyd/99-oh-no-parent-control-allow.rules"


class BrokerServiceUnitTests(unittest.TestCase):
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
            {"CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_FOWNER", "CAP_KILL"} <= bounded
        )

    def test_broker_starts_with_and_can_reload_execution_policy(self):
        source = BROKER_UNIT.read_text(encoding="utf-8")

        self.assertIn("Requires=fapolicyd.service", source)
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


if __name__ == "__main__":
    unittest.main()
