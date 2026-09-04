import json
import struct
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from tools.render_polkit_policy import render


ROOT = Path(__file__).resolve().parents[2]


class PackageDeploymentTests(unittest.TestCase):
    def test_make_installdeb_repairs_dependencies_installs_package_and_offers_reboot(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("installdeb:\n", 1)[1].split("\n\n", 1)[0]
        repair = recipe.index("$(APT) --fix-broken install")
        install = recipe.index('$(APT) install "$$deb_file"')
        marker = recipe.index("grep -Fxq 'oh-no-parent-control' /run/reboot-required.pkgs")
        prompt = recipe.index("Reboot now? [y/N]", marker)
        self.assertIn("@set -e", recipe)
        self.assertIn("dpkg-parsechangelog -S Version", recipe)
        self.assertIn("dpkg-architecture -qDEB_HOST_ARCH", recipe)
        self.assertIn("run make build first", recipe)
        self.assertLess(repair, install)
        self.assertLess(install, marker)
        self.assertLess(marker, prompt)
        self.assertIn("exec 3<>/dev/tty", recipe[prompt:])
        self.assertNotIn("dpkg --install", recipe)

    def test_make_build_keeps_changes_file_artifacts_together(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("build: check-release-version\n", 1)[1].split(
            "\n\ninstalldeb:", 1
        )[0]

        self.assertIn(
            'mv "../oh-no-parent-control_$${version}_$${architecture}.deb"',
            recipe,
        )
        self.assertIn(
            'ddeb_file="../oh-no-parent-control-dbgsym_$${version}_$${architecture}.ddeb"',
            recipe,
        )
        self.assertIn('if test -f "$$ddeb_file"; then mv', recipe)
        self.assertIn(
            'mv "../oh-no-parent-control_$${version}_$${architecture}.changes"',
            recipe,
        )
        self.assertIn(
            'mv "../oh-no-parent-control_$${version}_$${architecture}.buildinfo"',
            recipe,
        )

    def test_package_payload_contains_product_assets_and_system_integration(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        for source in (
            "parent/oh_no_parent_control_parent/style.css", "kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg",
            "kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf", "data/Gearbox_Waltz.mp3",
            "data/fapolicyd/99-oh-no-parent-control-allow.rules", "tools/pam_oh_no_parent_control.c",
            "tools/session_limit_check.py", "tools/clear_session_runtime_max.py",
            "broker/oh-no-parent-control-migrate-state", "broker/oh-no-parent-control-query-usage",
        ):
            self.assertIn(source, makefile)
        self.assertIn('SYSTEM_EXTENSION_DIR := $(DATADIR)/gnome-shell/extensions/$(UUID)', makefile)
        self.assertIn('"$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/"', makefile)
        product_files = makefile.split("_install-product-files:\n", 1)[1].split(
            "\n_generate-package-activation-manifest:", 1
        )[0]
        self.assertNotIn("rm -f", product_files)
        self.assertNotIn("rm -rf", product_files)

    def test_package_has_all_runtime_dependencies(self):
        control = (ROOT / "debian/control").read_text(encoding="utf-8")
        dependencies = next(line.removeprefix("Depends: ") for line in control.splitlines() if line.startswith("Depends: ")).split(", ")
        for dependency in ("fapolicyd", "gnome-shell", "gir1.2-malcontent-0", "gir1.2-gstreamer-1.0", "gstreamer1.0-plugins-base", "gstreamer1.0-plugins-ugly", "libpam-malcontent", "mate-polkit-bin", "polkitd", "python3-gi-cairo", "systemd-sysusers"):
            self.assertIn(dependency, dependencies)

    def test_postinst_reasserts_kiosk_identity_and_enforcement_services(self):
        postinst = (ROOT / "debian/postinst").read_text(encoding="utf-8")
        provision = postinst.index("/usr/libexec/oh-no-parent-control-provision")
        enable = postinst.index("systemctl enable")
        start = postinst.index("deb-systemd-invoke start", enable)
        owned_guard = postinst.index('if [ "$package_created_kiosk" -eq 1 ]')
        self.assertIn("usermod --comment \"Oh No! Parent Control\"", postinst)
        self.assertIn("passwd --delete \"$kiosk_user\"", postinst)
        self.assertLess(owned_guard, postinst.index("passwd --delete"))
        self.assertLess(postinst.index("passwd --delete"), provision)
        self.assertLess(provision, enable)
        self.assertLess(enable, start)
        for unit in ("fapolicyd.service", "malcontent-timerd.service", "malcontent-timer-extension-agent.service"):
            self.assertIn(unit, postinst[enable:start])
        for account in ("malcontent-timer-ext-agent", "malcontent-timerd", "malcontent-webd"):
            self.assertIn(account, postinst)

    def test_package_migrates_before_broker_can_run_and_activates_updates(self):
        preinst = (ROOT / "debian/preinst").read_text(encoding="utf-8")
        postinst = (ROOT / "debian/postinst").read_text(encoding="utf-8")
        marker = "/var/lib/oh-no-parent-control/migration-in-progress"
        command = "/usr/libexec/oh-no-parent-control-migrate-state"
        self.assertLess(preinst.index(marker), preinst.index("deb-systemd-invoke stop"))
        self.assertLess(postinst.index(command), postinst.index(f"rm -f {marker}"))
        self.assertIn("*process-restart*|*session-renewal*", postinst)
        self.assertIn("/run/reboot-required.pkgs", postinst)

    def test_package_removal_clears_generated_enforcement_and_only_its_account(self):
        prerm = (ROOT / "debian/prerm").read_text(encoding="utf-8")
        postrm = (ROOT / "debian/postrm").read_text(encoding="utf-8")
        self.assertLess(prerm.index("deb-systemd-invoke stop"), prerm.index("--remove"))
        for path in ("/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules", "/etc/oh-no-parent-control/config.json", "/etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules"):
            self.assertIn(path, postrm)
        self.assertIn("package-created-kiosk-uid", postrm)
        self.assertIn('deluser --remove-home "$kiosk_user"', postrm)
        self.assertNotIn("/var/log/oh-no-parent-control", postrm)

    def test_branding_and_policies_are_packaged_from_shared_sources(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        branding = ROOT / "data/brand.json"
        values = json.loads(branding.read_text(encoding="utf-8"))
        self.assertIn("BRANDING_ASSETS := data/brand.json data/app.json data/app_logo.png data/company_logo.png", makefile)
        self.assertIn("PARENT_TITLEBAR_ASSET := data/app_logo_titlebar.png", makefile)
        self.assertIn("$(BRANDING_ASSETS) $(PARENT_TITLEBAR_ASSET)", makefile)
        self.assertIn(
            "EXTENSION_BRANDING_ASSETS := $(BRANDING_ASSETS) data/app_logo_gnome_launcher.png",
            makefile,
        )
        self.assertIn(
            "EXTENSION_PACK_ASSETS := $(EXTENSION_BRANDING_ASSETS:data/%=../data/%)",
            makefile,
        )
        with (ROOT / "data/app_logo_gnome_launcher.png").open("rb") as source:
            source.read(16)
            self.assertEqual(struct.unpack(">II", source.read(8)), (512, 512))
        for name in ("tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy.in", "tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy.in"):
            rendered = ElementTree.fromstring(render(ROOT / "data/polkit-1/actions" / name, branding))
            self.assertEqual(rendered.findtext("vendor"), values["vendor_name"])


if __name__ == "__main__":
    unittest.main()
