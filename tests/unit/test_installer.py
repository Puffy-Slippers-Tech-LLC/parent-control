import json
import struct
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from tools.render_polkit_policy import render


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "install.sh"


class InstallerTests(unittest.TestCase):
    def test_product_and_company_branding_assets_are_packaged(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertTrue((ROOT / "data/app_logo.png").is_file())
        self.assertTrue((ROOT / "data/app_logo_gnome_launcher.png").is_file())
        self.assertTrue((ROOT / "data/company_logo.png").is_file())
        self.assertIn(
            "BRANDING_ASSETS := data/brand.json data/app.json "
            "data/app_logo.png data/company_logo.png",
            makefile,
        )
        self.assertNotIn("data/logo.png", makefile)

    def test_shared_logo_is_safe_for_the_kiosk_account(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        icon = ROOT / "data/app_logo.png"

        self.assertTrue(icon.is_file())
        with icon.open("rb") as source:
            self.assertEqual(source.read(8), b"\x89PNG\r\n\x1a\n")
            self.assertEqual(source.read(4), b"\x00\x00\x00\r")
            self.assertEqual(source.read(4), b"IHDR")
            width, height = struct.unpack(">II", source.read(8))
        self.assertLessEqual(width, 128)
        self.assertLessEqual(height, 128)
        self.assertIn(
            "config/config.example.json $(BRANDING_ASSETS) LICENSE "
            "\"$(DESTDIR)$(DATADIR)/oh-no-parent-control/\"",
            makefile,
        )

    def test_kiosk_cairo_bridge_is_a_runtime_dependency(self):
        script = INSTALLER.read_text(encoding="utf-8")
        control = (ROOT / "debian/control").read_text(encoding="utf-8")

        self.assertIn("    python3-gi-cairo \\\n", script)
        runtime_dependencies = next(
            line.removeprefix("Depends: ")
            for line in control.splitlines()
            if line.startswith("Depends: ")
        )
        self.assertIn("python3-gi-cairo", runtime_dependencies.split(", "))

    def test_execution_policy_daemon_and_fallback_rule_are_installed(self):
        script = INSTALLER.read_text(encoding="utf-8")
        control = (ROOT / "debian/control").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("    fapolicyd \\\n", script)
        self.assertIn("fapolicyd", next(
            line for line in control.splitlines() if line.startswith("Depends: ")
        ).split(", "))
        self.assertIn("data/fapolicyd/99-oh-no-parent-control-allow.rules", makefile)
        self.assertIn("require_active fapolicyd.service", script)
        self.assertIn("oh-no-parent-control-execution-policy-ready", makefile)
        self.assertIn("oh-no-parent-control-execution-policy-probe", makefile)
        self.assertIn("display-manager.service.d", makefile)
        self.assertIn("fapolicyd.service.d", makefile)

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

    def test_kiosk_gateway_background_is_packaged(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        background = ROOT / "kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg"

        self.assertTrue(background.is_file())
        self.assertIn(
            "kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg", makefile,
        )

    def test_kiosk_request_form_font_is_packaged(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        font = ROOT / "kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf"
        license_file = ROOT / "kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt"

        self.assertTrue(font.is_file())
        self.assertTrue(license_file.is_file())
        self.assertIn(
            "kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf", makefile,
        )
        self.assertIn(
            "kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt", makefile,
        )

    def test_kiosk_music_and_its_playback_dependencies_are_packaged(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        script = INSTALLER.read_text(encoding="utf-8")
        control = (ROOT / "debian/control").read_text(encoding="utf-8")

        self.assertTrue((ROOT / "data/Gearbox_Waltz.mp3").is_file())
        self.assertIn("data/Gearbox_Waltz.mp3", makefile)
        self.assertIn(
            "test -s /usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/"
            "Gearbox_Waltz.mp3",
            script,
        )
        for dependency in (
            "gir1.2-gstreamer-1.0",
            "gstreamer1.0-plugins-base",
            "gstreamer1.0-plugins-ugly",
        ):
            self.assertIn(f"    {dependency} \\\n", script)
            self.assertIn(dependency, control)

    def test_parent_launcher_is_only_readable_by_administrators(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        script = INSTALLER.read_text(encoding="utf-8")

        self.assertIn(
            "install -m 0640 data/applications/com.puffyslippers.OhNoParentControl.Parent.desktop",
            makefile,
        )
        self.assertIn(
            "chown root:sudo /usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop",
            script,
        )
        self.assertIn('"root:sudo"', script)
        self.assertIn('"640"', script)

    def test_full_resolution_product_artwork_is_installed_as_the_desktop_icon(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        control = (ROOT / "debian/control").read_text(encoding="utf-8")
        parent_entry = (
            ROOT / "data/applications/com.puffyslippers.OhNoParentControl.Parent.desktop"
        ).read_text(encoding="utf-8")
        kiosk_entry = (
            ROOT / "data/wayland-sessions/oh-no-parent-control.desktop"
        ).read_text(encoding="utf-8")

        icon = "com.puffyslippers.OhNoParentControl"
        launcher_icon = ROOT / "data/app_logo_gnome_launcher.png"
        with launcher_icon.open("rb") as source:
            self.assertEqual(source.read(8), b"\x89PNG\r\n\x1a\n")
            self.assertEqual(source.read(4), b"\x00\x00\x00\r")
            self.assertEqual(source.read(4), b"IHDR")
            width, height = struct.unpack(">II", source.read(8))
        self.assertEqual((width, height), (512, 512))
        self.assertIn(
            "data/app_logo_gnome_launcher.png \"$(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps/"
            f"{icon}.png\"",
            makefile,
        )
        self.assertIn(f"Icon={icon}", parent_entry)
        self.assertIn(f"Icon={icon}", kiosk_entry)
        icon_install = installer.index(
            'make --no-print-directory -C "$SCRIPT_DIR" _install-product-files'
        )
        cache_refresh = installer.index(
            "gtk-update-icon-cache --force --quiet /usr/share/icons/hicolor"
        )
        self.assertLess(icon_install, cache_refresh)
        self.assertIn("    gtk-update-icon-cache \\\n", installer)
        runtime_dependencies = next(
            line.removeprefix("Depends: ")
            for line in control.splitlines()
            if line.startswith("Depends: ")
        )
        self.assertIn("gtk-update-icon-cache", runtime_dependencies.split(", "))

    def test_polkit_vendor_metadata_uses_shared_branding(self):
        branding = ROOT / "data/brand.json"
        values = json.loads(branding.read_text(encoding="utf-8"))
        policies = (
            ROOT / "data/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy.in",
            ROOT / "data/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy.in",
        )

        for policy in policies:
            with self.subTest(policy=policy.name):
                rendered = render(policy, branding)
                root = ElementTree.fromstring(rendered)
                self.assertEqual(root.findtext("vendor"), values["vendor_name"])
                self.assertIsNone(root.find("vendor_url"))
                self.assertTrue(values["vendor_url"])
                self.assertNotIn(
                    values["vendor_name"], policy.read_text(encoding="utf-8"),
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

    def test_unrestricted_accounts_skip_the_no_limit_pam_message(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        pam_config = (
            ROOT / "data/pam-configs/oh-no-parent-control-session-limits"
        ).read_text(encoding="utf-8")

        self.assertIn("tools/session_limit_check.py", makefile)
        self.assertIn(
            "[success=1 default=ignore] pam_exec.so quiet quiet_log "
            "/usr/libexec/oh-no-parent-control-session-limit-check",
            pam_config,
        )
        self.assertIn(
            "[success=4 default=ignore] pam_succeed_if.so quiet "
            "service = systemd-user",
            pam_config,
        )
        self.assertIn(
            "[success=3 default=ignore] pam_succeed_if.so quiet "
            "user = oh-no-parent-control",
            pam_config,
        )
        self.assertIn(
            "[success=2 default=ignore] pam_succeed_if.so quiet "
            "user ingroup sudo",
            pam_config,
        )
        self.assertLess(
            pam_config.index("oh-no-parent-control-session-limit-check"),
            pam_config.index("pam_malcontent.so"),
        )
        self.assertIn("Session-Type: Additional", pam_config)
        self.assertLess(
            pam_config.index("required pam_malcontent.so"),
            pam_config.index(
                "optional pam_exec.so quiet "
                "/usr/libexec/oh-no-parent-control-clear-session-runtime-max"
            ),
        )
        self.assertIn("tools/clear_session_runtime_max.py", makefile)
        script = INSTALLER.read_text(encoding="utf-8")
        self.assertIn(
            "oh-no-parent-control-clear-session-runtime-max", script,
        )
        self.assertIn("/etc/pam.d/common-session", script)

    def test_selected_approver_polkit_rule_is_installed(self):
        script = INSTALLER.read_text(encoding="utf-8")
        rule = "data/polkit-1/rules.d/00-oh-no-parent-control-session.rules"
        contents = (ROOT / rule).read_text(encoding="utf-8")

        self.assertIn(rule, script)
        self.assertIn("/etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules", script)
        self.assertIn('action.lookup("approver-user")', contents)
        self.assertIn('return ["unix-user:" + approver]', contents)
        self.assertIn(
            'tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access',
            contents,
        )
        self.assertNotIn("ApproveTimeAndApps", contents)

        child_policy = (
            ROOT / "data/polkit-1/actions/"
            "tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy.in"
        ).read_text(encoding="utf-8")
        self.assertIn("<allow_active>auth_admin</allow_active>", child_policy)
        self.assertNotIn("auth_admin_keep", child_policy)
        self.assertNotIn("org.freedesktop.policykit.imply", child_policy)

    def test_direct_upgrade_removes_obsolete_child_privilege_code(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        obsolete_sources = next(
            line for line in makefile.splitlines()
            if line.startswith("OBSOLETE_EXTENSION_SOURCES :=")
        )

        for obsolete in (
            "aboutDialog.js",
            "appFilterClient.js",
            "appPolicyStore.js",
            "approverClient.js",
            "parentalApproval.js",
            "requestAccessClient.js",
            "requestDialog.js",
            "requestOptions.js",
            "requestPreferencesStore.js",
            "sessionLimitsClient.js",
            "sharedPreferencesClient.js",
        ):
            self.assertIn(obsolete, obsolete_sources)
        self.assertIn(
            '"$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/$(file)"', makefile,
        )
        self.assertIn(
            "org.gnome.shell.extensions.oh-no-parent-control.policy", makefile,
        )

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
            "start_unit oh-no-parent-control-broker.service", provision,
        )

        self.assertLess(provision, restart)
        self.assertIn("require_active oh-no-parent-control-broker.service", script)

    def test_malcontent_timer_units_must_start_but_may_idle(self):
        script = INSTALLER.read_text(encoding="utf-8")
        verify = (ROOT / "tests/integration/guest/verify").read_text(
            encoding="utf-8",
        )

        self.assertIn("require_startable() {", script)
        self.assertIn("require_startable malcontent-timerd.service", script)
        self.assertIn(
            "require_startable malcontent-timer-extension-agent.service", script,
        )
        self.assertNotIn("require_active malcontent-timerd.service", script)
        self.assertNotIn(
            "require_active malcontent-timer-extension-agent.service", script,
        )
        self.assertIn("require_active fapolicyd.service", script)
        self.assertIn("require_active oh-no-parent-control-broker.service", script)
        self.assertIn("systemctl start \"$unit\"", script)
        self.assertIn("systemctl start \"$unit\"", verify)
        resident = verify[
            verify.index("for unit in accounts-daemon.service"):
            verify.index("for unit in malcontent-timerd.service")
        ]
        self.assertNotIn("malcontent-timerd.service", resident)
        self.assertIn("fapolicyd.service", resident)

    def test_package_session_renewal_restarts_broker_to_publish_child_payload(self):
        postinst = (ROOT / "debian/postinst").read_text(encoding="utf-8")

        self.assertIn("*process-restart*|*session-renewal*)", postinst)
        self.assertIn(
            "systemctl restart oh-no-parent-control-broker.service", postinst,
        )

    def test_activation_manifest_is_generated_after_direct_pam_and_gdm_setup(self):
        script = INSTALLER.read_text(encoding="utf-8")

        pam_install = script.index(
            "/usr/share/pam-configs/oh-no-parent-control-session-limits"
        )
        manifest = script.index("_generate-package-activation-manifest")

        self.assertLess(pam_install, manifest)
        self.assertIn("GENERATE_ACTIVATION_MANIFEST=0", script)

    def test_clean_install_passes_a_missing_activation_baseline(self):
        script = INSTALLER.read_text(encoding="utf-8")

        baseline_copy = script.index(
            "cp /usr/share/oh-no-parent-control/package-activation.json"
        )
        first_install = script.index("first_installation=1", baseline_copy)
        missing_baseline = script.index(
            'rm -f "$previous_activation_manifest"', first_install
        )
        comparison = script.index(
            'changed-impacts --old "$previous_activation_manifest"'
        )
        reboot_gate = script.index(
            '[[ "$first_installation" -eq 1 || "$activation_impacts" == *reboot* ]]'
        )

        self.assertLess(baseline_copy, first_install)
        self.assertLess(first_install, missing_baseline)
        self.assertLess(missing_baseline, comparison)
        self.assertLess(comparison, reboot_gate)

    def test_reboot_activation_prompts_interactively_after_signaling_system(self):
        script = INSTALLER.read_text(encoding="utf-8")

        marker = script.index("touch /run/reboot-required.pkgs")
        preserve = script.index("--schedule-uid", marker)
        prompt = script.index("Reboot now? [y/N]", preserve)
        stdin_guard = script.index('if [[ -t 0 ]]', prompt)
        tty_open = script.index("exec 3<>/dev/tty", stdin_guard)
        reboot = script.index("systemctl reboot", prompt)

        self.assertLess(marker, preserve)
        self.assertIn(
            "could not preserve GNOME extension state for reboot",
            script[preserve:prompt],
        )
        self.assertLess(preserve, prompt)
        self.assertLess(prompt, stdin_guard)
        self.assertLess(stdin_guard, tty_open)
        self.assertLess(tty_open, reboot)
        self.assertIn('y|Y|yes|YES|Yes)', script[prompt:reboot])
        self.assertIn("</dev/null", script)
        self.assertIn("install: required check failed:", script)
        accounts_restart = script.index("start_unit accounts-daemon.service")
        fapolicyd_now = script.index("systemctl enable --now")
        self.assertLess(accounts_restart, fapolicyd_now)

    def test_both_install_paths_migrate_saved_data_before_starting_broker(self):
        script = INSTALLER.read_text(encoding="utf-8")
        preinst = (ROOT / "debian/preinst").read_text(encoding="utf-8")
        postinst = (ROOT / "debian/postinst").read_text(encoding="utf-8")
        launcher = (ROOT / "broker/oh-no-parent-control-broker").read_text(
            encoding="utf-8",
        )
        service = (ROOT / "data/systemd/oh-no-parent-control-broker.service").read_text(
            encoding="utf-8",
        )

        marker = "/var/lib/oh-no-parent-control/migration-in-progress"
        command = "/usr/libexec/oh-no-parent-control-migrate-state"
        self.assertIn(marker, preinst)
        self.assertLess(
            preinst.index(marker),
            preinst.index("systemctl stop oh-no-parent-control-broker.service"),
        )
        self.assertLess(postinst.index(command), postinst.index(f"rm -f {marker}"))
        self.assertLess(script.index(command), script.index(f"rm -f {marker}"))
        self.assertLess(script.index(command), script.index(
            "systemctl restart oh-no-parent-control-broker.service",
        ))
        self.assertIn(marker, launcher)
        self.assertIn(f"ConditionPathExists=!{marker}", service)

    def test_data_migration_runner_and_documentation_are_packaged(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("broker/oh-no-parent-control-migrate-state", makefile)
        self.assertIn("docs/Data-Migration.md", makefile)


if __name__ == "__main__":
    unittest.main()
