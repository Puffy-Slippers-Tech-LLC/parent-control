import unittest
from types import SimpleNamespace
from unittest import mock

from tools import provision


class ProvisionTests(unittest.TestCase):
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
