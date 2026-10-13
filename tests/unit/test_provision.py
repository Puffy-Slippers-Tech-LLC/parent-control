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
    def test_sets_kiosk_account_icon_to_the_padded_logo(self, run):
        user = SimpleNamespace(pw_uid=1002, pw_name="oh-no-parent-control")

        provision.accounts_service_set_icon_file(
            user, user_path="/org/freedesktop/Accounts/User1002"
        )

        run.assert_called_once_with([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts/User1002",
            "org.freedesktop.Accounts.User", "SetIconFile", "s",
            "/usr/share/oh-no-parent-control/kiosk_account_icon.png",
        ], check=True)

    @mock.patch("tools.provision.subprocess.run")
    def test_kiosk_session_and_transport_are_set_and_verified(self, run):
        run.return_value = SimpleNamespace(stdout='s "oh-no-parent-control"\ns "wayland"\nb false\n')
        provision.accounts_service_set_kiosk_session("/org/freedesktop/Accounts/User1002")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual([cmd[-3:] for cmd in commands[:2]], [
            ["SetSession", "s", "oh-no-parent-control"],
            ["SetSessionType", "s", "wayland"],
        ])
        self.assertEqual(commands[2][-3:], ["Session", "SessionType", "SystemAccount"])

    @mock.patch("tools.provision.subprocess.run")
    def test_fresh_nologin_kiosk_uses_public_cache_and_verifies_retained_state(self, run):
        user = SimpleNamespace(pw_uid=1002, pw_name="oh-no-parent-control")
        path = "/org/freedesktop/Accounts/User1002"
        run.side_effect = [SimpleNamespace(stdout='b true\nb false\n'),
                           SimpleNamespace(stdout=f'o "{path}"\n'),
                           SimpleNamespace(stdout='b false\nb true\n')]
        provision.accounts_service_cache_kiosk(user, path)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[1][-3:], ["CacheUser", "s", user.pw_name])
        self.assertEqual(commands[2][-2:], ["SystemAccount", "Saved"])
        self.assertFalse(any("SetSession" in command for command in commands))

    @mock.patch("tools.provision.subprocess.run")
    def test_visible_kiosk_needs_no_cache_mutation(self, run):
        run.return_value = SimpleNamespace(stdout='b false\nb true\n')
        provision.accounts_service_cache_kiosk(
            SimpleNamespace(pw_name="oh-no-parent-control"), "/org/freedesktop/Accounts/User1002")
        self.assertEqual(run.call_count, 1)

    @mock.patch("tools.provision.subprocess.run")
    def test_cache_cannot_substitute_another_identity(self, run):
        run.side_effect = [SimpleNamespace(stdout='b true\nb false\n'),
                           SimpleNamespace(stdout='o "/org/freedesktop/Accounts/User9999"\n')]
        with self.assertRaisesRegex(SystemExit, "invalid cached kiosk"):
            provision.accounts_service_cache_kiosk(
                SimpleNamespace(pw_name="oh-no-parent-control"), "/org/freedesktop/Accounts/User1002")
        self.assertEqual(run.call_count, 2)

    @mock.patch("tools.provision.subprocess.run")
    def test_hidden_retained_kiosk_is_refused_without_metadata_mutation(self, run):
        run.return_value = SimpleNamespace(stdout='b true\nb true\n')
        with self.assertRaisesRegex(SystemExit, "requires an AccountsService fix"):
            provision.accounts_service_cache_kiosk(
                SimpleNamespace(pw_name="oh-no-parent-control"), "/org/freedesktop/Accounts/User1002")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][2], "get-property")

    @mock.patch("tools.provision.subprocess.run")
    def test_visible_but_unsaved_kiosk_is_cached(self, run):
        path = "/org/freedesktop/Accounts/User1002"
        run.side_effect = [SimpleNamespace(stdout='b false\nb false\n'),
                           SimpleNamespace(stdout=f'o "{path}"\n'),
                           SimpleNamespace(stdout='b false\nb true\n')]
        provision.accounts_service_cache_kiosk(SimpleNamespace(pw_name="oh-no-parent-control"), path)
        self.assertEqual(run.call_args_list[1].args[0][-3:], ["CacheUser", "s", "oh-no-parent-control"])

    @mock.patch("tools.provision.subprocess.run")
    def test_cache_success_without_retained_visible_state_is_refused(self, run):
        path = "/org/freedesktop/Accounts/User1002"
        for observed in ('b false\nb false\n', 'b true\nb true\n', 'b false\n'):
            run.side_effect = [SimpleNamespace(stdout='b true\nb false\n'),
                               SimpleNamespace(stdout=f'o "{path}"\n'),
                               SimpleNamespace(stdout=observed)]
            with self.subTest(observed=observed), self.assertRaisesRegex(SystemExit, "cache verification"):
                provision.accounts_service_cache_kiosk(SimpleNamespace(pw_name="oh-no-parent-control"), path)

    @mock.patch("tools.provision.subprocess.run")
    def test_hidden_kiosk_fails_final_provisioning_readback(self, run):
        run.return_value = SimpleNamespace(stdout='s "oh-no-parent-control"\ns "wayland"\nb true\n')
        with self.assertRaisesRegex(SystemExit, "routing failed verification"):
            provision.accounts_service_set_kiosk_session("/org/freedesktop/Accounts/User1002")

    @mock.patch("tools.provision.subprocess.run")
    def test_successful_setter_with_wrong_readback_fails_provisioning(self, run):
        run.return_value = SimpleNamespace(stdout='s "ubuntu"\ns "wayland"\n')
        with self.assertRaisesRegex(SystemExit, "routing failed verification"):
            provision.accounts_service_set_kiosk_session("/org/freedesktop/Accounts/User1002")


if __name__ == "__main__":
    unittest.main()
