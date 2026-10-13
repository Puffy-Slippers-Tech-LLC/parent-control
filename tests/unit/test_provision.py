import unittest
import os
import signal
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import provision


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("tools.provision._kiosk_cache_is_visible", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

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
        run.return_value = SimpleNamespace(stdout='s ""\n')

        provision.accounts_service_set_icon_file(
            user, user_path="/org/freedesktop/Accounts/User1002"
        )

        self.assertEqual(run.call_count, 2)
        run.assert_called_with([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts/User1002",
            "org.freedesktop.Accounts.User", "SetIconFile", "s",
            "/usr/share/oh-no-parent-control/kiosk_account_icon.png",
        ], check=True)

    @mock.patch("tools.provision.subprocess.run")
    def test_correct_artwork_is_read_only_to_preserve_retained_metadata(self, run):
        run.return_value = SimpleNamespace(stdout=f's "{provision.KIOSK_ICON_FILE}"\n')
        provision.accounts_service_set_icon_file(SimpleNamespace(pw_uid=1002),
                                                user_path="/org/freedesktop/Accounts/User1002")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-1], "IconFile")

    @mock.patch("tools.provision.subprocess.run")
    def test_retained_custom_artwork_is_preserved(self, run):
        run.return_value = SimpleNamespace(stdout='s "/var/lib/AccountsService/icons/retained"\n')
        provision.accounts_service_set_icon_file(SimpleNamespace(pw_uid=1002),
                                                user_path="/org/freedesktop/Accounts/User1002")
        self.assertEqual(run.call_count, 1)

    @mock.patch("tools.provision.subprocess.run")
    def test_fresh_account_default_face_is_replaced_with_product_artwork(self, run):
        run.return_value = SimpleNamespace(stdout='s "/home/oh-no-parent-control/.face"\n')
        provision.accounts_service_set_icon_file(SimpleNamespace(pw_uid=1002),
                                                user_path="/org/freedesktop/Accounts/User1002",
                                                preserve_existing=False)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0][-3:], ["SetIconFile", "s", provision.KIOSK_ICON_FILE])

    @mock.patch("tools.provision.subprocess.run")
    def test_kiosk_session_and_transport_are_set_and_verified(self, run):
        run.side_effect = [SimpleNamespace(stdout='s "ubuntu"\ns "wayland"\nb false\n'),
                           SimpleNamespace(), SimpleNamespace(),
                           SimpleNamespace(stdout='s "oh-no-parent-control"\ns "wayland"\nb false\n')]
        provision.accounts_service_set_kiosk_session("/org/freedesktop/Accounts/User1002")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual([cmd[-3:] for cmd in commands[1:3]], [
            ["SetSession", "s", "oh-no-parent-control"],
            ["SetSessionType", "s", "wayland"],
        ])
        self.assertEqual(commands[3][-3:], ["Session", "SessionType", "SystemAccount"])

    @mock.patch("tools.provision.subprocess.run")
    def test_correct_retained_account_provisioning_performs_no_metadata_writes(self, run):
        run.side_effect = [
            SimpleNamespace(stdout='o "/org/freedesktop/Accounts/User1002"\n'),
            SimpleNamespace(stdout='b false\nb true\n'),
            SimpleNamespace(stdout='s "/var/lib/AccountsService/icons/retained"\n'),
            SimpleNamespace(stdout='u 0\n'),
            SimpleNamespace(stdout='s "oh-no-parent-control"\ns "wayland"\nb false\n')]
        provision.accounts_service_provision_kiosk(SimpleNamespace(pw_uid=1002, pw_name=provision.KIOSK_USER))
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 5)
        self.assertEqual(commands[0][-3:], ["FindUserById", "x", "1002"])
        self.assertTrue(all(command[2] == "get-property" for command in commands[1:]))

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
    def test_hidden_retained_kiosk_restarts_through_owned_adapter(self, run):
        run.side_effect = [SimpleNamespace(stdout='b true\nb true\n'),
                           SimpleNamespace(), SimpleNamespace(),
                           SimpleNamespace(stdout='b false\nb true\n')]
        provision.accounts_service_cache_kiosk(
            SimpleNamespace(pw_name="oh-no-parent-control"), "/org/freedesktop/Accounts/User1002")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[1:3], [
            ["systemctl", "daemon-reload"], ["systemctl", "restart", "accounts-daemon.service"]])
        self.assertFalse(any("CacheUser" in command for command in commands))

    @mock.patch("tools.provision.subprocess.run")
    def test_transient_visible_state_requires_durable_repair(self, run):
        run.side_effect = [SimpleNamespace(stdout='b false\nb true\n'),
                           SimpleNamespace(), SimpleNamespace(),
                           SimpleNamespace(stdout='b false\nb true\n')]
        with mock.patch("tools.provision._kiosk_cache_is_visible", side_effect=[False, True]):
            provision.accounts_service_cache_kiosk(
                SimpleNamespace(pw_name="oh-no-parent-control"), "/org/freedesktop/Accounts/User1002")
        self.assertIn(mock.call(["systemctl", "restart", "accounts-daemon.service"],
                               check=True, timeout=60, env=provision._ACCOUNT_ENV), run.call_args_list)

    @mock.patch("tools.provision.subprocess.run")
    def test_live_success_without_durable_state_is_refused(self, run):
        path = "/org/freedesktop/Accounts/User1002"
        run.side_effect = [SimpleNamespace(stdout='b true\nb false\n'),
                           SimpleNamespace(stdout=f'o "{path}"\n'),
                           SimpleNamespace(stdout='b false\nb true\n')]
        with mock.patch("tools.provision._kiosk_cache_is_visible", return_value=False), \
                self.assertRaisesRegex(SystemExit, "durable kiosk cache verification"):
            provision.accounts_service_cache_kiosk(SimpleNamespace(pw_name="oh-no-parent-control"), path)

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


class KioskCacheMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache_directory = self.root / "var/lib/AccountsService/users"
        self.cache_directory.mkdir(parents=True)
        self.cache = self.cache_directory / provision.KIOSK_USER
        self.marker = self.root / "var/lib/oh-no-parent-control/package-created-kiosk-uid"
        self.marker.parent.mkdir()
        self.marker.write_text("1002\n")
        self.marker.chmod(0o600)
        self.binary = self.root / "accounts-daemon"
        self.binary.write_bytes(b"test executable identity")
        user = SimpleNamespace(pw_uid=1002, pw_name=provision.KIOSK_USER,
                               pw_dir="/home/oh-no-parent-control")
        for target, value in (("_ACCOUNT_FILESYSTEM_ROOT", self.root),
                              ("_ACCOUNT_OWNER_UID", os.getuid()),
                              ("_ACCOUNT_OWNER_GID", os.getgid()),
                              ("KIOSK_OWNERSHIP", self.marker),
                              ("KIOSK_CACHE_DIRECTORY", self.cache_directory),
                              ("ACCOUNTS_SERVICE_BINARIES", (self.binary,))):
            patcher = mock.patch.object(provision, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(provision, "account", return_value=user)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(provision.subprocess, "run", side_effect=[
            SimpleNamespace(stdout="MainPID=0\nSubState=start-pre\nActiveState=activating\n"),
            SimpleNamespace(stdout="accounts-daemon 23.13.9\n")])
        self.run = patcher.start()
        self.addCleanup(patcher.stop)

    def seed(self, contents=b"[User]\nSystemAccount=true\n"):
        self.cache.write_bytes(contents)
        self.cache.chmod(0o600)
        return contents

    def test_migration_preserves_all_other_bytes_mode_and_extended_metadata(self):
        before = self.seed(b"# retained comment\r\n[User]\r\nEmail=private@example.invalid\r\n"
                           b"UnknownVendorKey=keep\\nexact\r\nSystemAccount = true  \r\n"
                           b"Icon=/var/lib/AccountsService/icons/retained\r\n"
                           b"[vendor.extension]\r\nOpaque=preserve;all;values;\r\n")
        os.setxattr(self.cache, "user.onpc-test", b"preserved metadata")
        info = self.cache.stat()
        provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before.replace(b"SystemAccount = true", b"SystemAccount = false"))
        after = self.cache.stat()
        self.assertEqual((after.st_uid, after.st_gid, after.st_mode), (info.st_uid, info.st_gid, info.st_mode))
        self.assertEqual(os.getxattr(self.cache, "user.onpc-test"), b"preserved metadata")
        self.assertEqual(list(self.cache_directory.iterdir()), [self.cache])

    def test_missing_classification_is_added_inside_user_group(self):
        self.seed(b"[User]\nSession=retained\n[vendor]\nOpaque=true\n")
        provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(),
                         b"[User]\nSession=retained\nSystemAccount=false\n[vendor]\nOpaque=true\n")

    def test_visible_account_is_read_only_and_needs_no_version_or_service_calls(self):
        before = self.seed(b"[User]\nSystemAccount=false\n")
        info = self.cache.stat()
        provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before)
        self.assertEqual(self.cache.stat().st_ino, info.st_ino)
        self.run.assert_not_called()

    def test_precommit_failure_preserves_original_and_retry_succeeds(self):
        before = self.seed()
        with mock.patch.object(provision.os, "replace", side_effect=OSError("injected write failure")), \
                self.assertRaises(OSError):
            provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before)
        self.assertEqual(list(self.cache_directory.iterdir()), [self.cache])
        self.run.side_effect = [SimpleNamespace(stdout="ActiveState=activating\nSubState=start-pre\nMainPID=0\n"),
                                SimpleNamespace(stdout="accounts-daemon 23.13.9\n")]
        provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before.replace(b"true", b"false"))

    def test_postcommit_failure_is_safely_retried_without_metadata_rewrite(self):
        before = self.seed()
        real_fsync = provision.os.fsync
        real_replace = provision.os.replace
        committed = False
        def record_replace(*arguments, **keywords):
            nonlocal committed
            real_replace(*arguments, **keywords)
            committed = True
        def fail_directory_sync(descriptor):
            if committed and provision.stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("injected directory sync failure")
            real_fsync(descriptor)
        with mock.patch.object(provision.os, "fsync", side_effect=fail_directory_sync), \
                mock.patch.object(provision.os, "replace", side_effect=record_replace), \
                self.assertRaises(OSError):
            provision.repair_kiosk_visibility()
        info = self.cache.stat()
        self.run.side_effect = [SimpleNamespace(stdout="ActiveState=activating\nSubState=start-pre\nMainPID=0\n"),
                                SimpleNamespace(stdout="accounts-daemon 23.13.9\n")]
        provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before.replace(b"true", b"false"))
        self.assertEqual(self.cache.stat().st_ino, info.st_ino)

    def test_abrupt_precommit_interruption_recovers_exact_owned_slot(self):
        before = self.seed()
        child = os.fork()
        if child == 0:
            with mock.patch.object(provision.os, "replace", side_effect=lambda *args, **kwargs: os._exit(91)):
                provision.repair_kiosk_visibility()
            os._exit(92)
        deadline = time.monotonic() + 5
        try:
            while True:
                waited, status = os.waitpid(child, os.WNOHANG)
                if waited:
                    child = None
                    self.assertEqual(os.waitstatus_to_exitcode(status), 91)
                    break
                if time.monotonic() >= deadline:
                    self.fail("owned migration child did not finish")
                time.sleep(0.01)
        finally:
            if child is not None:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
        self.assertEqual(self.cache.read_bytes(), before)
        self.assertEqual(len(list(self.cache_directory.iterdir())), 2)
        provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before.replace(b"true", b"false"))
        self.assertEqual(list(self.cache_directory.iterdir()), [self.cache])

    def test_foreign_transaction_slot_is_preserved_and_blocks_migration(self):
        before = self.seed()
        foreign = self.cache_directory / provision._VISIBILITY_SLOT
        foreign.write_bytes(b"unknown retained state")
        foreign.chmod(0o600)
        with self.assertRaisesRegex(SystemExit, "unowned.*slot"):
            provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before)
        self.assertEqual(foreign.read_bytes(), b"unknown retained state")

    def test_same_inode_mode_change_during_write_is_preserved_and_refused(self):
        before = self.seed()
        real_fsync = provision.os.fsync
        changed = False
        def change_original_mode(descriptor):
            nonlocal changed
            if not changed:
                self.cache.chmod(0o640)
                changed = True
            real_fsync(descriptor)
        with mock.patch.object(provision.os, "fsync", side_effect=change_original_mode), \
                self.assertRaisesRegex(SystemExit, "changed during classification repair"):
            provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before)
        self.assertEqual(provision.stat.S_IMODE(self.cache.stat().st_mode), 0o640)
        self.assertEqual(list(self.cache_directory.iterdir()), [self.cache])

    def test_unsafe_or_ambiguous_state_is_preserved(self):
        for contents in (b"[User]\nSystemAccount=true\nSystemAccount=false\n",
                         b"[User]\nSystemAccount=invalid\n", b"[User]\n[User]\n", b"\xff"):
            with self.subTest(contents=contents):
                self.seed(contents)
                with self.assertRaises(SystemExit):
                    provision.repair_kiosk_visibility()
                self.assertEqual(self.cache.read_bytes(), contents)
        self.run.assert_not_called()

    def test_foreign_identity_mode_links_and_service_state_are_refused(self):
        before = self.seed()
        self.marker.write_text("9999\n")
        with self.assertRaisesRegex(SystemExit, "ownership changed"):
            provision.repair_kiosk_visibility()
        self.marker.write_text("1002\n")
        self.cache.chmod(0o666)
        with self.assertRaisesRegex(SystemExit, "unsafe.*file"):
            provision.repair_kiosk_visibility()
        self.cache.chmod(0o600)
        hardlink = self.cache_directory / "foreign"
        hardlink.hardlink_to(self.cache)
        with self.assertRaisesRegex(SystemExit, "unsafe.*file"):
            provision.repair_kiosk_visibility()
        hardlink.unlink()
        self.run.side_effect = [SimpleNamespace(stdout="ActiveState=active\nSubState=running\nMainPID=100\n")]
        with self.assertRaisesRegex(SystemExit, "start boundary"):
            provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before)

    def test_unsupported_version_preserves_cache(self):
        before = self.seed()
        self.run.side_effect = [SimpleNamespace(stdout="ActiveState=activating\nSubState=start-pre\nMainPID=0\n"),
                                SimpleNamespace(stdout="accounts-daemon 99.1\n")]
        with self.assertRaisesRegex(SystemExit, "unsupported.*version"):
            provision.repair_kiosk_visibility()
        self.assertEqual(self.cache.read_bytes(), before)

    def test_fedora_build_date_version_requires_reviewed_source_package(self):
        before = self.seed()
        for package in ("accountsservice 99.1-1.fc44", "accountsservice 23.13.9-16.fc44"):
            with self.subTest(package=package):
                self.run.side_effect = [
                    SimpleNamespace(stdout="ActiveState=activating\nSubState=start-pre\nMainPID=0\n"),
                    SimpleNamespace(stdout="accounts-daemon 26.03.0\n"),
                    SimpleNamespace(stdout=package + "\n")]
                if package == provision.FEDORA_ACCOUNTS_SERVICE_PACKAGE:
                    provision.repair_kiosk_visibility()
                    self.assertEqual(self.cache.read_bytes(), before.replace(b"true", b"false"))
                else:
                    with self.assertRaisesRegex(SystemExit, "unsupported.*version"):
                        provision.repair_kiosk_visibility()
                    self.assertEqual(self.cache.read_bytes(), before)

    def test_substituted_cache_directory_is_not_followed(self):
        self.seed()
        retained = self.cache_directory.with_name("retained")
        self.cache_directory.rename(retained)
        self.cache_directory.symlink_to(retained)
        with self.assertRaises(OSError):
            provision.repair_kiosk_visibility()
        self.assertEqual((retained / provision.KIOSK_USER).read_bytes(), b"[User]\nSystemAccount=true\n")


if __name__ == "__main__":
    unittest.main()
