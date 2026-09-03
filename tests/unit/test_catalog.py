import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from oh_no_parent_control.catalog import _application, list_apps, suggested_patterns
from oh_no_parent_control.core import UserAccount


class CatalogTests(unittest.TestCase):
    def test_appimage_desktop_launcher_uses_its_absolute_executable_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            appimage = home / "Applications" / "Lunar Client.AppImage"
            appimage.parent.mkdir()
            appimage.touch()
            launcher = home / "lunarclient.desktop"
            launcher.write_text(
                "[Desktop Entry]\nType=Application\nName=Lunar Client\n"
                f"Exec='{appimage}' --no-sandbox\nIcon=lunar-client\n",
                encoding="utf-8",
            )

            application = _application(launcher, "lunarclient.desktop", home)

        self.assertEqual(application["targets"], (str(appimage),))
        self.assertEqual(application["name"], "Lunar Client")

    def test_versioned_appimage_gets_an_editable_pattern_suggestion(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            appimage = home / "Applications" / "Lunar Client-3.7.17-abc.AppImage"
            appimage.parent.mkdir()
            appimage.touch()
            launcher = home / "lunarclient.desktop"
            launcher.write_text(
                "[Desktop Entry]\nType=Application\nName=Lunar Client\n"
                f"Exec='{appimage}'\n", encoding="utf-8",
            )
            application = _application(launcher, "lunarclient.desktop", home)
        self.assertEqual(application["suggested_patterns"], (
            f"{appimage.parent}/Lunar Client-*.AppImage",))

    def test_versioned_appimage_with_guid_gets_a_structured_pattern_suggestion(self):
        target = (
            "/home/adrian/Applications/"
            "Lunar Client-3.7.13-ow_e1eda9a97aab9c00fb9acf48129edd99.AppImage"
        )

        self.assertEqual(suggested_patterns(target), (
            "/home/adrian/Applications/Lunar Client-*-ow_*.AppImage",
        ))

    def test_catalog_reads_the_managed_users_private_desktop_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            executable = home / "Applications" / "Game.AppImage"
            executable.parent.mkdir()
            executable.touch()
            applications = home / ".local" / "share" / "applications"
            applications.mkdir(parents=True)
            (applications / "game.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=Game\n"
                f"Exec='{executable}'\n",
                encoding="utf-8",
            )
            user = UserAccount(1001, "adrian", "Adrian", False, False, True)
            account = SimpleNamespace(pw_uid=1001, pw_dir=str(home))

            with patch("oh_no_parent_control.catalog.pwd.getpwnam", return_value=account), \
                    patch("oh_no_parent_control.catalog.SYSTEM_APPLICATION_DIRS", ()):
                catalog = list_apps(user)

        self.assertEqual(catalog[0]["id"], "game.desktop")
        self.assertEqual(catalog[0]["targets"], (str(executable),))

    def test_catalog_follows_flatpak_exported_desktop_entry_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            deployment = home / ".local/share/flatpak/app/com.mojang.Minecraft/current/active/export/share/applications"
            deployment.mkdir(parents=True)
            launcher = deployment / "com.mojang.Minecraft.desktop"
            launcher.write_text(
                "[Desktop Entry]\nType=Application\nName=Minecraft\n"
                "X-Flatpak=com.mojang.Minecraft\n"
                "Exec=/usr/bin/flatpak run --arch=x86_64 --branch=stable "
                "com.mojang.Minecraft\n",
                encoding="utf-8",
            )
            exports = home / ".local/share/flatpak/exports/share/applications"
            exports.mkdir(parents=True)
            (exports / launcher.name).symlink_to(launcher)
            user = UserAccount(1001, "adrian", "Adrian", False, False, True)
            account = SimpleNamespace(pw_uid=1001, pw_dir=str(home))

            with patch("oh_no_parent_control.catalog.pwd.getpwnam", return_value=account), \
                    patch("oh_no_parent_control.catalog.SYSTEM_APPLICATION_DIRS", ()):
                catalog = list_apps(user)

        self.assertEqual(catalog[0]["id"], "com.mojang.Minecraft.desktop")
        self.assertEqual(catalog[0]["name"], "Minecraft")
        self.assertEqual(
            catalog[0]["targets"],
            ("app/com.mojang.Minecraft/x86_64/stable",),
        )

    def test_snap_launcher_preserves_its_public_command_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snap_binary = root / "usr/bin/snap"
            snap_binary.parent.mkdir(parents=True)
            snap_binary.touch()
            command_directory = root / "snap/bin"
            command_directory.mkdir(parents=True)
            command = command_directory / "thunderbird"
            command.symlink_to(snap_binary)
            launcher = root / "thunderbird_thunderbird.desktop"
            launcher.write_text(
                "[Desktop Entry]\nType=Application\nName=Thunderbird Mail\n"
                "X-SnapInstanceName=thunderbird\nX-SnapAppName=thunderbird\n"
                f"Exec={command} %u\n",
                encoding="utf-8",
            )

            with patch(
                    "oh_no_parent_control.catalog.SNAP_COMMAND_DIRS",
                    (command_directory,),
            ), patch(
                    "oh_no_parent_control.catalog.SNAP_LAUNCHERS",
                    {str(snap_binary)},
            ):
                application = _application(
                    launcher, "thunderbird_thunderbird.desktop", root,
                )

        self.assertEqual(application["name"], "Thunderbird Mail")
        self.assertEqual(application["targets"], (str(command),))

    def test_snap_metadata_does_not_bless_an_unrelated_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unrelated_binary = root / "usr/bin/unrelated"
            unrelated_binary.parent.mkdir(parents=True)
            unrelated_binary.touch()
            command_directory = root / "snap/bin"
            command_directory.mkdir(parents=True)
            command = command_directory / "thunderbird"
            command.symlink_to(unrelated_binary)
            launcher = root / "thunderbird_thunderbird.desktop"
            launcher.write_text(
                "[Desktop Entry]\nType=Application\nName=Thunderbird Mail\n"
                "X-SnapInstanceName=thunderbird\nX-SnapAppName=thunderbird\n"
                f"Exec={command} %u\n",
                encoding="utf-8",
            )

            with patch(
                    "oh_no_parent_control.catalog.SNAP_COMMAND_DIRS",
                    (command_directory,),
            ), patch(
                    "oh_no_parent_control.catalog.SNAP_LAUNCHERS",
                    {str(root / 'usr/bin/snap')},
            ):
                application = _application(
                    launcher, "thunderbird_thunderbird.desktop", root,
                )

        self.assertIsNone(application)
