import unittest
from types import SimpleNamespace
from unittest import mock

from tools import provision


class ProvisionTests(unittest.TestCase):
    @mock.patch("tools.provision.subprocess.run")
    def test_reads_accounts_service_language(self, run):
        run.return_value = SimpleNamespace(stdout='s "fr_FR.UTF-8"\n')
        user = SimpleNamespace(pw_uid=1000, pw_name="parent")

        self.assertEqual(
            provision.accounts_service_language(user),
            "fr_FR.UTF-8",
        )
        run.assert_called_once_with([
            "busctl", "--system", "get-property", "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts/User1000",
            "org.freedesktop.Accounts.User", "Language",
        ], check=True, stdout=provision.subprocess.PIPE, text=True)

    @mock.patch("tools.provision.subprocess.run")
    def test_empty_language_preserves_machine_default(self, run):
        run.return_value = SimpleNamespace(stdout='s ""\n')
        user = SimpleNamespace(pw_uid=1000, pw_name="parent")

        self.assertEqual(provision.accounts_service_language(user), "")

    @mock.patch("tools.provision.subprocess.run")
    def test_rejects_invalid_accounts_service_language(self, run):
        run.return_value = SimpleNamespace(stdout="u 1\n")
        user = SimpleNamespace(pw_uid=1000, pw_name="parent")

        with self.assertRaisesRegex(SystemExit, "invalid language"):
            provision.accounts_service_language(user)

    @mock.patch("tools.provision.subprocess.run")
    def test_sets_kiosk_account_icon_to_the_packaged_app_logo(self, run):
        user = SimpleNamespace(pw_uid=1002, pw_name="oh-no-parent-control")

        provision.accounts_service_set_icon_file(user)

        run.assert_called_once_with([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts/User1002",
            "org.freedesktop.Accounts.User", "SetIconFile", "s",
            "/usr/share/oh-no-parent-control/app_logo.png",
        ], check=True)


if __name__ == "__main__":
    unittest.main()
