import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "install.sh"


class InstallerTests(unittest.TestCase):
    def test_interrupted_dpkg_state_is_recovered_before_apt_runs(self):
        script = INSTALLER.read_text(encoding="utf-8")

        configure = script.index("dpkg --configure --pending")
        repair = script.index('"${apt_get[@]}" --fix-broken install -y')

        self.assertLess(configure, repair)

    def test_parent_app_stylesheet_is_installed_with_its_package(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn(
            "parent/oh_no_parent_control_parent/style.css", makefile,
        )

    def test_broker_is_restarted_after_configuration_is_provisioned(self):
        script = INSTALLER.read_text(encoding="utf-8")

        provision = script.index(
            '/usr/libexec/oh-no-parent-control-provision "${provision_args[@]}"'
        )
        restart = script.index(
            "systemctl restart oh-no-parent-control-broker.service"
        )

        self.assertLess(provision, restart)
        self.assertIn(
            "systemctl is-active --quiet oh-no-parent-control-broker.service",
            script,
        )


if __name__ == "__main__":
    unittest.main()
