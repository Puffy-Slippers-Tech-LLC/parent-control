import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BROKER_UNIT = ROOT / "data/systemd/oh-no-parent-control-broker.service"


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
            {"CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_FOWNER"} <= bounded
        )


if __name__ == "__main__":
    unittest.main()
