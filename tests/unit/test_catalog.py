import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from oh_no_parent_control.catalog import _application, list_apps
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
