import unittest
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import provision


class ProvisionTests(unittest.TestCase):
    def test_account_preflight_performs_no_provisioning_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home/oh-no-parent-control"
            home.mkdir(parents=True)
            user = SimpleNamespace(pw_uid=os.getuid(), pw_dir="/home/oh-no-parent-control")
            with mock.patch("tools.provision.account", return_value=user), \
                    mock.patch("tools.provision.os.geteuid", return_value=0), \
                    mock.patch("tools.provision.sys.argv", ["provision", "--kiosk-user", "oh-no-parent-control", "--prefix", directory, "--check-account"]), \
                    mock.patch("tools.provision.subprocess.run") as run:
                self.assertEqual(provision.main(), 0)
            run.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [home.parent])

    def test_account_preflight_refuses_symlinked_home(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home/oh-no-parent-control"
            home.parent.mkdir()
            outside = Path(directory) / "unrelated"
            outside.mkdir()
            home.symlink_to(outside)
            user = SimpleNamespace(pw_uid=os.getuid(), pw_dir="/home/oh-no-parent-control")
            with mock.patch("tools.provision.account", return_value=user), \
                    mock.patch("tools.provision.os.geteuid", return_value=0), \
                    mock.patch("tools.provision.sys.argv", ["provision", "--kiosk-user", "oh-no-parent-control", "--prefix", directory, "--check-account"]), \
                    self.assertRaisesRegex(SystemExit, "unsafe ownership"):
                provision.main()
            self.assertTrue(outside.is_dir())

    def test_administrative_kiosk_is_rejected(self):
        user = SimpleNamespace(pw_uid=1006, pw_name="oh-no-parent-control", pw_gid=1006)
        group = SimpleNamespace(gr_name="sudo", gr_gid=27, gr_mem=[user.pw_name])
        with mock.patch("tools.provision.pwd.getpwnam", return_value=user), \
                mock.patch("tools.provision.grp.getgrall", return_value=[group]), \
                self.assertRaisesRegex(SystemExit, "administrative"):
            provision.account(user.pw_name, "kiosk")

    @mock.patch("tools.provision.subprocess.run")
    def test_resolves_new_account_through_accounts_service_manager(self, run):
        run.return_value = SimpleNamespace(
            stdout='o "/org/freedesktop/Accounts/User1002"\n'
        )
        user = SimpleNamespace(pw_uid=1002, pw_name="oh-no-parent-control")

        self.assertEqual(
            provision.accounts_service_user_path(user),
            "/org/freedesktop/Accounts/User1002",
        )
        run.assert_called_once_with([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts", "org.freedesktop.Accounts",
            "FindUserById", "x", "1002",
        ], check=True, stdout=provision.subprocess.PIPE, text=True)

    @mock.patch("tools.provision.subprocess.run")
    def test_rejects_unexpected_accounts_service_user_object(self, run):
        run.return_value = SimpleNamespace(
            stdout='o "/org/freedesktop/Accounts/User9999"\n'
        )
        user = SimpleNamespace(pw_uid=1002, pw_name="oh-no-parent-control")

        with self.assertRaisesRegex(SystemExit, "invalid object"):
            provision.accounts_service_user_path(user)

    @mock.patch("tools.provision.subprocess.run")
    def test_sets_kiosk_account_icon_to_the_shared_logo(self, run):
        user = SimpleNamespace(pw_uid=1002, pw_name="oh-no-parent-control")

        provision.accounts_service_set_icon_file(
            user, user_path="/org/freedesktop/Accounts/User1002"
        )

        run.assert_called_once_with([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts/User1002",
            "org.freedesktop.Accounts.User", "SetIconFile", "s",
            "/usr/share/oh-no-parent-control/app_logo.png",
        ], check=True)


if __name__ == "__main__":
    unittest.main()
