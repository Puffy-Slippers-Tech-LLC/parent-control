import json
import os
import struct
import subprocess
import unittest
import xml.etree.ElementTree as ElementTree

import pytest

from tools.render_polkit_policy import render


from tests.support.paths import ROOT


@pytest.mark.parametrize("failure, status, step", [
    (None, 0, None),
    ("dpkg-parsechangelog", 2, "reading package version"),
    ("dpkg-architecture", 3, "reading package architecture"),
    ("package", 1, "locating built package"),
    ("apt", 100, "installing package with APT"),
])
def test_installer_hands_off_to_apt_and_preserves_failures(
    tmp_path, failure, status, step,
):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, source in {
        "dpkg-parsechangelog": "#!/bin/sh\necho 1.0\n",
        "dpkg-architecture": "#!/bin/sh\necho amd64\n",
        "apt": (
            "#!/bin/sh\n"
            'printf "%s\\n" "$@" > "$APT_ARGUMENTS"\n'
            "echo 'APT transaction'\n"
            "echo 'Processing triggers for desktop-file-utils ...'\n"
            "echo 'Processing triggers for libc-bin ...'\n"
            "exit 0\n"
        ),
    }.items():
        command = bin_dir / name
        if failure == name:
            source = (
                f"#!/bin/sh\necho '{name} diagnostic' >&2\nexit {status}\n"
            )
        command.write_text(source)
        command.chmod(0o755)
    output = tmp_path / "output"
    output.mkdir()
    if failure != "package":
        (output / "oh-no-parent-control_1.0_amd64.deb").touch()
    # Any Make-side helper invocation is a parity regression, even if installed.
    helper = bin_dir / "oh-no-parent-control-reboot-notice"
    helper.write_text("#!/bin/sh\necho 'unexpected helper invocation'\nexit 99\n")
    helper.chmod(0o755)
    arguments = tmp_path / "apt-arguments"
    result = subprocess.run(
        ["make", "--no-print-directory", "-f", str(ROOT / "Makefile"),
         "installdeb", f"CURDIR={tmp_path}", f"LIBEXECDIR={bin_dir}",
         f"APT={bin_dir / 'apt'}"],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             "APT_ARGUMENTS": str(arguments)},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=10,
    )
    if failure is None:
        assert result.returncode == 0, result.stdout
        assert result.stdout.count("APT transaction") == 1
        assert "Processing triggers for libc-bin" in result.stdout
        assert arguments.read_text().splitlines() == [
            "install", str(output / "oh-no-parent-control_1.0_amd64.deb")]
        assert result.stdout.rstrip().endswith("Processing triggers for libc-bin ...")
        assert "REBOOT REQUIRED" not in result.stdout
        assert "PASS:" not in result.stdout
        assert "FAIL:" not in result.stdout
    else:
        assert result.returncode != 0
        if failure != "apt":
            assert f"FAIL: installdeb: {step} (exit {status})" in result.stdout
        assert f"Error {status}" in result.stdout
        assert "PASS:" not in result.stdout
        assert "REBOOT REQUIRED" not in result.stdout
        if failure in {"dpkg-parsechangelog", "dpkg-architecture", "apt"}:
            assert f"{failure} diagnostic" in result.stdout
        if failure in {"dpkg-parsechangelog", "dpkg-architecture", "package"}:
            assert "Installing " not in result.stdout
            assert "APT transaction" not in result.stdout


class PackageDeploymentTests(unittest.TestCase):
    def test_make_package_targets_delegate_all_product_behavior_to_apt(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("installdeb:\n", 1)[1].split("\n\n", 1)[0]
        self.assertTrue(recipe.rstrip().endswith('exec $(APT) install "$$deb_file"'))
        removal = makefile.split("uninstalldeb:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(removal.strip(), '$(APT) remove oh-no-parent-control')
        self.assertIn("@set -e", recipe)
        self.assertIn("dpkg-parsechangelog -S Version", recipe)
        self.assertIn("dpkg-architecture -qDEB_HOST_ARCH", recipe)
        self.assertIn("run make build first", recipe)
        self.assertNotIn("$(LIBEXECDIR)", recipe)
        self.assertNotIn("reboot-required", recipe)
        self.assertNotIn("REBOOT REQUIRED", recipe)
        self.assertNotIn("Reboot now?", recipe)
        self.assertNotIn("read -r", recipe)
        self.assertNotIn("/dev/tty", recipe)
        self.assertNotIn("systemctl reboot", recipe)
        self.assertNotIn("dpkg --install", recipe)

    def test_reboot_notice_is_owned_by_the_debian_package(self):
        postinst = (ROOT / "debian/postinst").read_text(encoding="utf-8")
        helper = (ROOT / "tools/package_notice").read_text(encoding="utf-8")
        notice = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"
        self.assertNotIn(notice, postinst)
        self.assertIn(notice, helper)
        self.assertIn('[ -t 2 ] && [ "${TERM:-dumb}" != dumb ]', helper)
        self.assertIn("'\\033[1;31m%s\\033[0m\\n'", helper)
        self.assertLess(postinst.index('#DEBHELPER#'), postinst.index(
            '/usr/libexec/oh-no-parent-control-package-notice --configured'))

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
            "parent/oh_no_parent_control_parent/style.css",
            "common/oh_no_parent_control_ui/feedback.css",
            "common/oh_no_parent_control_ui/rich_editor/quill.js",
            "common/oh_no_parent_control_ui/rich_editor/quill.snow.css",
            "common/oh_no_parent_control_ui/rich_editor/quill.js.LICENSE.txt",
            "common/oh_no_parent_control_ui/rich_editor/LICENSE",
            "kiosk/oh_no_parent_control_kiosk/kiosk-background-still.png",
            "kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf",
            "data/fapolicyd/99-oh-no-parent-control-allow.rules", "tools/pam_oh_no_parent_control.c",
            "tools/session_limit_check.py",
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
        for dependency in ("fapolicyd", "gnome-shell", "gir1.2-malcontent-0", "gir1.2-gstreamer-1.0", "gir1.2-webkit-6.0", "gstreamer1.0-plugins-base", "gstreamer1.0-plugins-good", "libpam-malcontent", "mate-polkit-bin", "polkitd", "python3-gi-cairo", "systemd-sysusers", "update-notifier", "update-notifier-common"):
            self.assertIn(dependency, dependencies)

    def test_postinst_reasserts_kiosk_identity_and_enforcement_services(self):
        postinst = (ROOT / "debian/postinst").read_text(encoding="utf-8")
        provision = postinst.index('    /usr/libexec/oh-no-parent-control-provision --kiosk-user "$kiosk_user"\n')
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
        for path in ("/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules", "/etc/oh-no-parent-control/config.json"):
            self.assertIn(path, postrm)
        self.assertIn("package-created-kiosk-uid", postrm)
        self.assertIn('deluser "$kiosk_user"', postrm)
        self.assertIn("remove_tree /home/oh-no-parent-control", postrm)
        self.assertIn("remove_tree /var/log/oh-no-parent-control", postrm)

    def test_branding_and_policies_are_packaged_from_shared_sources(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        branding = ROOT / "data/brand.json"
        values = json.loads(branding.read_text(encoding="utf-8"))
        self.assertIn("BRANDING_ASSETS := data/brand.json data/app.json data/app_logo.png data/company_logo.png", makefile)
        self.assertIn("PARENT_TITLEBAR_ASSET := data/app_logo_titlebar.png", makefile)
        self.assertIn("$(BRANDING_ASSETS) $(PARENT_TITLEBAR_ASSET)", makefile)
        self.assertIn(
            "EXTENSION_BRANDING_ASSETS := data/brand.json data/app_logo_gnome_launcher.png",
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
