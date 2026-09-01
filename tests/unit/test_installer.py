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

    def test_identity_scoped_usage_helper_is_installed(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        helper = ROOT / "broker/oh-no-parent-control-query-usage"

        self.assertTrue(helper.is_file())
        self.assertIn(
            "install -m 0755 broker/oh-no-parent-control-query-usage", makefile,
        )
        self.assertIn(
            "test -x /usr/libexec/oh-no-parent-control-query-usage",
            INSTALLER.read_text(encoding="utf-8"),
        )

    def test_selected_approver_polkit_rule_is_installed(self):
        script = INSTALLER.read_text(encoding="utf-8")
        rule = "data/polkit-1/rules.d/00-oh-no-parent-control-session.rules"
        contents = (ROOT / rule).read_text(encoding="utf-8")

        self.assertIn(rule, script)
        self.assertIn("/etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules", script)
        self.assertIn('action.lookup("approver-user")', contents)
        self.assertIn('return ["unix-user:" + approver]', contents)

    def test_kiosk_uses_current_restartable_polkit_agent(self):
        script = INSTALLER.read_text(encoding="utf-8")
        service = (ROOT / "data/systemd/user/oh-no-parent-control-polkit-agent.service").read_text(
            encoding="utf-8",
        )
        session = (
            ROOT
            / "data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf"
        ).read_text(encoding="utf-8")

        self.assertIn("    mate-polkit-bin \\\n", script)
        self.assertNotIn("lxqt-policykit", script)
        self.assertNotIn("policykit-1-gnome", script)
        self.assertNotIn("malcontent-gui", script)
        self.assertIn("test -x /usr/bin/mate-polkit", script)
        self.assertIn("Type=forking", service)
        self.assertNotIn("Type=simple", service)
        self.assertIn("ExecStart=/usr/bin/mate-polkit", service)
        self.assertIn("Restart=on-failure", service)
        self.assertNotIn("OnFailure=gnome-session-shutdown.target", service)
        self.assertIn("Wants=oh-no-parent-control-polkit-agent.service", session)
        self.assertNotIn("Requires=oh-no-parent-control-polkit-agent.service", session)

    def test_debian_package_avoids_transitional_polkit_dependency(self):
        control = (ROOT / "debian/control").read_text(encoding="utf-8")

        self.assertIn("mate-polkit-bin", control)
        self.assertNotIn("lxqt-policykit", control)
        self.assertIn("polkitd", control)
        self.assertNotIn("policykit-1,", control)

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
