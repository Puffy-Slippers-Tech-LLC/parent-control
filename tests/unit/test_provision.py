import unittest
import ast
import importlib.util
import io
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import provision


PREPARED_SOURCE = Path(__file__).resolve().parents[2] / "data/kiosk-runtime-unselected/provision.py"
_prepared_spec = importlib.util.spec_from_file_location("prepared_kiosk_provision", PREPARED_SOURCE)
prepared = importlib.util.module_from_spec(_prepared_spec)
with mock.patch.object(sys, "dont_write_bytecode", True):
    _prepared_spec.loader.exec_module(prepared)


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


class KioskConfigurationAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / "var/lib/oh-no-parent-control"
        self.directory.mkdir(parents=True)
        self.marker = self.directory / "package-created-kiosk-uid"
        self.marker.write_text("1002\n")
        self.marker.chmod(0o600)
        self.record = self.directory / "kiosk-configuration-account.json"
        self.user = SimpleNamespace(pw_name=provision.KIOSK_USER, pw_uid=1002)
        self.expiry = None
        self.commands = []
        for target, value in (("_ACCOUNT_FILESYSTEM_ROOT", self.root),
                              ("_ACCOUNT_OWNER_UID", os.getuid()),
                              ("_ACCOUNT_OWNER_GID", os.getgid()),
                              ("KIOSK_OWNERSHIP", self.marker),
                              ("KIOSK_CONFIGURATION_ACCOUNT", self.record)):
            patcher = mock.patch.object(provision, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(provision.os, "chown")
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(provision.subprocess, "run", side_effect=self.shadow_command)
        self.runner = patcher.start()
        self.addCleanup(patcher.stop)

    def shadow_command(self, arguments, **options):
        self.commands.append(arguments)
        if arguments[:2] == ["getent", "shadow"]:
            expiry = "" if self.expiry is None else str(self.expiry)
            return SimpleNamespace(stdout=f"{provision.KIOSK_USER}:private-hash:20000:0:99999:7::{expiry}:\n")
        self.assertEqual(arguments[:2], ["usermod", "--expiredate"])
        self.assertEqual(arguments[-1], provision.KIOSK_USER)
        self.expiry = None if arguments[2] == "-1" else int(arguments[2])
        return SimpleNamespace(returncode=0)

    def test_empty_password_owned_retry_is_expired_and_original_expiry_is_restored(self):
        for original in (None, 0, 1, 24000):
            with self.subTest(original=original):
                self.expiry = original
                provision.configure_account_access(self.user)
                self.assertEqual(self.expiry, 1)
                self.assertEqual(json.loads(self.record.read_text())["expires"], original)
                provision.configure_account_access(self.user)
                provision.configure_account_access(self.user, release=True)
                self.assertEqual(self.expiry, original)
                self.assertFalse(self.record.exists())

    def test_fresh_expired_account_is_journaled_before_uid_ownership_publication(self):
        self.marker.unlink()
        self.expiry = 1
        provision.configure_account_access(self.user, new_account=True)
        self.assertEqual(json.loads(self.record.read_text())["expires"], None)
        self.marker.write_text("1002\n")
        self.marker.chmod(0o600)
        provision.configure_account_access(self.user)
        provision.configure_account_access(self.user, release=True)
        self.assertIsNone(self.expiry)

    def test_interruption_before_shadow_write_retains_original_and_retries(self):
        def fail_write(arguments, **options):
            if arguments[0] == "usermod":
                raise OSError("owned simulated shadow failure")
            return self.shadow_command(arguments, **options)
        self.runner.side_effect = fail_write
        with self.assertRaises(OSError):
            provision.configure_account_access(self.user)
        self.assertIsNone(self.expiry)
        self.assertIsNone(json.loads(self.record.read_text())["expires"])
        self.runner.side_effect = self.shadow_command
        provision.configure_account_access(self.user)
        self.assertEqual(self.expiry, 1)

    def test_interrupted_release_is_requarantined_without_losing_original(self):
        provision.configure_account_access(self.user)
        with mock.patch.object(provision.os, "unlink", side_effect=OSError("owned cleanup failure")):
            with self.assertRaises(OSError):
                provision.configure_account_access(self.user, release=True)
        self.assertIsNone(self.expiry)
        self.assertEqual(json.loads(self.record.read_text())["phase"], "releasing")
        provision.configure_account_access(self.user)
        self.assertEqual(self.expiry, 1)
        provision.configure_account_access(self.user, release=True)
        self.assertIsNone(self.expiry)

    def test_release_failure_keeps_account_expired_and_retry_record(self):
        provision.configure_account_access(self.user)
        def fail_write(arguments, **options):
            if arguments[0] == "usermod":
                raise OSError("owned simulated release failure")
            return self.shadow_command(arguments, **options)
        self.runner.side_effect = fail_write
        with self.assertRaises(OSError):
            provision.configure_account_access(self.user, release=True)
        self.assertEqual(self.expiry, 1)
        self.assertEqual(json.loads(self.record.read_text())["phase"], "releasing")

    def test_foreign_expiry_and_uid_changes_are_preserved(self):
        provision.configure_account_access(self.user)
        before = self.record.read_bytes()
        self.expiry = 12345
        for release in (False, True):
            with self.assertRaisesRegex(SystemExit, "changed kiosk configuration"):
                provision.configure_account_access(self.user, release=release)
        self.assertEqual(self.expiry, 12345)
        self.assertEqual(self.record.read_bytes(), before)
        self.expiry = 1
        self.marker.write_text("9999\n")
        with self.assertRaisesRegex(SystemExit, "ownership changed"):
            provision.configure_account_access(self.user)
        self.assertEqual(self.record.read_bytes(), before)

    def test_unsafe_record_metadata_and_links_are_preserved(self):
        provision.configure_account_access(self.user)
        before = self.record.read_bytes()
        self.record.chmod(0o640)
        with self.assertRaises(SystemExit):
            provision.configure_account_access(self.user)
        self.record.chmod(0o600)
        other = self.directory / "foreign"
        other.hardlink_to(self.record)
        with self.assertRaises(SystemExit):
            provision.configure_account_access(self.user)
        other.unlink()
        self.record.rename(other)
        self.record.symlink_to(other)
        with self.assertRaises(OSError):
            provision.configure_account_access(self.user)
        self.assertEqual(other.read_bytes(), before)
        self.assertEqual(self.expiry, 1)

    def test_unknown_record_schema_is_preserved(self):
        self.record.write_text('{"foreign": true}\n')
        self.record.chmod(0o600)
        with self.assertRaisesRegex(SystemExit, "invalid kiosk configuration"):
            provision.configure_account_access(self.user)
        self.assertEqual(self.record.read_text(), '{"foreign": true}\n')
        self.assertIsNone(self.expiry)


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


class PreparedAccountsService:
    """Public account API double with independent ordinary-account metadata."""

    def __init__(self, *, saved=True, visible=True):
        self.path = "/org/freedesktop/Accounts/User1002"
        self.user = {"SystemAccount": not visible, "Saved": saved,
                     "IconFile": "/var/lib/AccountsService/icons/custom",
                     "LimitType": 0, "Session": prepared.KIOSK_USER, "SessionType": "wayland",
                     "Language": "fr_FR.UTF-8", "Email": "retained@example.invalid"}
        self.ordinary = dict(self.user, Session="ubuntu", SystemAccount=False)
        self.commands = []
        self.fail_method = None
        self.ignore = set()
        self.resolved_path = self.path

    def run(self, command, **options):
        assert command[:4] == ["/usr/bin/busctl", "--system", "--timeout=30",
                               "--allow-interactive-authorization=no"]
        assert options == {"check": True, "capture_output": True, "text": True,
                           "timeout": 35, "env": prepared.ENVIRONMENT}
        arguments = command[4:]
        self.commands.append(arguments)
        operation, bus, path, interface, *arguments = arguments
        assert bus == prepared.BUS
        assert path in (prepared.MANAGER, self.path)
        if operation == "get-property":
            assert path == self.path
            values = []
            for name in arguments:
                value = self.user[name]
                values.extend(["b", str(value).lower()] if type(value) is bool else
                              ["u", str(value)] if type(value) is int else ["s", shlex.quote(value)])
            return SimpleNamespace(stdout=" ".join(values))
        method, *values = arguments
        if method == self.fail_method:
            raise subprocess.CalledProcessError(1, command, stderr="private injected failure")
        if method == "FindUserById":
            assert values == ["x", "1002"]
            return SimpleNamespace(stdout=f'o "{self.resolved_path}"')
        if method == "CacheUser":
            assert values == ["s", prepared.KIOSK_USER]
            if method not in self.ignore:
                self.user.update(SystemAccount=False, Saved=True)
            return SimpleNamespace(stdout=f'o "{self.resolved_path}"')
        assert path == self.path
        if method == "LimitType":
            assert operation == "set-property" and interface == prepared.LIMIT_INTERFACE
            assert values == ["u", "0"]
            if method not in self.ignore:
                self.user[method] = 0
        else:
            assert operation == "call" and interface == prepared.USER_INTERFACE
            assert method in ("SetIconFile", "SetSession", "SetSessionType")
            assert values[0] == "s"
            if method not in self.ignore:
                self.user[method[3:]] = values[1]
        return SimpleNamespace(stdout="")


class PreparedProvisionTests(unittest.TestCase):
    def user(self):
        return SimpleNamespace(pw_name=prepared.KIOSK_USER, pw_uid=1002, pw_gid=1002,
                               pw_dir=prepared.KIOSK_HOME)

    def compose(self, service):
        with mock.patch.object(prepared.subprocess, "run", side_effect=service.run):
            prepared.provision_accounts_service(self.user())

    def test_retained_correct_account_preserves_all_metadata_without_setters(self):
        service = PreparedAccountsService()
        before, ordinary = dict(service.user), dict(service.ordinary)
        self.compose(service)
        self.assertEqual(service.user, before)
        self.assertEqual(service.ordinary, ordinary)
        self.assertEqual([command[0] for command in service.commands],
                         ["call", "get-property", "get-property", "get-property", "get-property"])

    def test_fresh_account_is_cached_and_current_required_settings_are_verified(self):
        service = PreparedAccountsService(saved=False, visible=False)
        service.user.update(IconFile="/home/oh-no-parent-control/.face", LimitType=1,
                            Session="ubuntu", SessionType="x11")
        ordinary = dict(service.ordinary)
        self.compose(service)
        self.assertEqual({key: service.user[key] for key in
                          ("Saved", "SystemAccount", "IconFile", "LimitType", "Session", "SessionType")},
                         {"Saved": True, "SystemAccount": False, "IconFile": prepared.KIOSK_ICON_FILE,
                          "LimitType": 0, "Session": prepared.KIOSK_USER, "SessionType": "wayland"})
        self.assertEqual(service.ordinary, ordinary)
        self.assertEqual(service.user["Language"], "fr_FR.UTF-8")
        self.assertEqual(service.user["Email"], "retained@example.invalid")
        self.assertEqual(service.commands[-1][-4:], ["Session", "SessionType", "SystemAccount", "Saved"])

    def test_retained_routing_repair_preserves_custom_icon_and_other_metadata(self):
        service = PreparedAccountsService()
        service.user.update(Session="ubuntu", SessionType="x11", LimitType=1)
        self.compose(service)
        self.assertEqual(service.user["IconFile"], "/var/lib/AccountsService/icons/custom")
        self.assertEqual(service.user["Language"], "fr_FR.UTF-8")
        self.assertFalse(any("CacheUser" in command or "SetIconFile" in command
                             for command in service.commands))

    def test_optional_artwork_failure_is_sanitized_and_required_provisioning_finishes(self):
        service = PreparedAccountsService(saved=False, visible=False)
        service.user.update(LimitType=1, Session="ubuntu", SessionType="x11")
        service.fail_method = "SetIconFile"
        with mock.patch.object(prepared.sys, "stderr", new_callable=io.StringIO) as warning:
            self.compose(service)
        self.assertEqual(service.user["LimitType"], 0)
        self.assertEqual(service.user["Session"], prepared.KIOSK_USER)
        self.assertEqual(service.user["SessionType"], "wayland")
        self.assertEqual(warning.getvalue(), "provision: optional kiosk artwork unavailable\n")

    def test_optional_artwork_read_failure_or_malformed_value_does_not_veto_routing(self):
        for result in (OSError("private failure"), ValueError("bad value"), ["invalid"]):
            with self.subTest(result=result), \
                    mock.patch.object(prepared, "properties", side_effect=[result] if not isinstance(result, Exception)
                                      else result), \
                    mock.patch.object(prepared, "busctl") as bus, \
                    mock.patch.object(prepared.sys, "stderr", new_callable=io.StringIO) as warning:
                prepared.provision_icon("/org/freedesktop/Accounts/User1002", fresh=True)
                self.assertEqual(warning.getvalue(), "provision: optional kiosk artwork unavailable\n")
                bus.assert_not_called()

    def test_retained_hidden_state_requires_prior_owned_migration_without_mutation(self):
        service = PreparedAccountsService(visible=False)
        before = dict(service.user)
        with self.assertRaisesRegex(SystemExit, "visibility migration must complete"):
            self.compose(service)
        self.assertEqual(service.user, before)
        self.assertEqual(len(service.commands), 2)

    def test_required_readbacks_reject_unapplied_cache_limits_and_routing(self):
        for ignored in ("CacheUser", "LimitType", "SetSession", "SetSessionType"):
            service = PreparedAccountsService(saved=False, visible=False)
            service.user.update(LimitType=1, Session="ubuntu", SessionType="x11")
            service.ignore.add(ignored)
            with self.subTest(ignored=ignored), self.assertRaisesRegex(SystemExit, "verification"):
                self.compose(service)

    def test_foreign_object_and_required_service_failures_are_not_accepted(self):
        service = PreparedAccountsService()
        service.resolved_path = "/org/freedesktop/Accounts/User9999"
        with self.assertRaisesRegex(SystemExit, "invalid object"):
            self.compose(service)
        service = PreparedAccountsService()
        service.fail_method = "FindUserById"
        with self.assertRaises(subprocess.CalledProcessError):
            self.compose(service)

    def test_prepared_entry_has_no_old_framework_or_lifecycle_imports(self):
        tree = ast.parse(PREPARED_SOURCE.read_text())
        modules = {node.module if isinstance(node, ast.ImportFrom) else alias.name
                   for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                   for alias in node.names}
        self.assertEqual(modules, {"argparse", "grp", "json", "os", "pathlib", "pwd", "shlex",
                                   "stat", "subprocess", "sys", "tempfile", "oh_no_parent_control.config"})


class PreparedOwnershipAndConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home/oh-no-parent-control"
        self.home.mkdir(parents=True)
        self.marker = self.root / prepared.KIOSK_OWNERSHIP
        self.marker.parent.mkdir(parents=True)
        self.marker.write_text("1002\n")
        self.marker.chmod(0o600)
        self.user = SimpleNamespace(pw_name=prepared.KIOSK_USER, pw_uid=1002, pw_gid=1002,
                                    pw_dir=prepared.KIOSK_HOME)
        self.home_uid = self.user.pw_uid
        original_stat = Path.stat
        def home_stat(path, **options):
            result = original_stat(path, **options)
            if path == self.home:
                fields = list(result)
                fields[4] = self.home_uid
                return os.stat_result(fields)
            return result
        for patcher in (mock.patch.object(prepared.pwd, "getpwnam", return_value=self.user),
                        mock.patch.object(prepared.grp, "getgrall", return_value=[]),
                        mock.patch.object(prepared, "_OWNER_UID", os.getuid()),
                        mock.patch.object(prepared, "_OWNER_GID", os.getgid()),
                        mock.patch.object(Path, "stat", home_stat),
                        mock.patch.object(prepared.os, "geteuid", return_value=0)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_preflight_validates_owned_identity_without_any_provisioning_writes(self):
        with mock.patch.object(prepared, "provision_configuration") as config, \
                mock.patch.object(prepared.subprocess, "run") as run:
            self.assertEqual(prepared.main(["--kiosk-user", prepared.KIOSK_USER,
                                            "--prefix", str(self.root), "--check-account"]), 0)
        config.assert_not_called()
        run.assert_not_called()
        self.assertEqual(self.marker.read_text(), "1002\n")

    def test_root_changed_name_home_and_admin_membership_are_rejected_before_writes(self):
        for field, value in (("pw_uid", 0), ("pw_name", "ordinary"), ("pw_dir", "/home/ordinary")):
            original = getattr(self.user, field)
            setattr(self.user, field, value)
            with self.subTest(field=field), self.assertRaises(SystemExit):
                prepared.kiosk_account(self.root)
            setattr(self.user, field, original)
        for group in (SimpleNamespace(gr_name="sudo", gr_gid=27, gr_mem=[prepared.KIOSK_USER]),
                      SimpleNamespace(gr_name="wheel", gr_gid=1002, gr_mem=[])):
            with self.subTest(group=group.gr_name), \
                    mock.patch.object(prepared.grp, "getgrall", return_value=[group]), \
                    self.assertRaisesRegex(SystemExit, "administrative"):
                prepared.kiosk_account(self.root)
        with mock.patch.object(prepared, "kiosk_account") as account, self.assertRaises(SystemExit):
            prepared.main(["--kiosk-user", "ordinary", "--prefix", str(self.root)])
        account.assert_not_called()

    def test_missing_changed_unsafe_and_linked_uid_markers_are_preserved(self):
        for contents, mode in (("9999\n", 0o600), ("1002\n", 0o644)):
            self.marker.write_text(contents)
            self.marker.chmod(mode)
            with self.subTest(contents=contents, mode=mode), self.assertRaises(SystemExit):
                prepared.kiosk_account(self.root)
            self.assertEqual(self.marker.read_text(), contents)
        self.marker.chmod(0o600)
        self.marker.write_text("1002\n")
        other = self.marker.with_name("foreign-marker")
        other.hardlink_to(self.marker)
        with self.assertRaises(SystemExit):
            prepared.kiosk_account(self.root)
        other.unlink()
        self.marker.rename(other)
        with self.assertRaises(FileNotFoundError):
            prepared.kiosk_account(self.root)
        self.marker.symlink_to(other)
        with self.assertRaises(OSError):
            prepared.kiosk_account(self.root)
        self.assertEqual(other.read_text(), "1002\n")

    def test_substituted_home_and_marker_directory_are_not_followed(self):
        self.home_uid = 1003
        with self.assertRaisesRegex(SystemExit, "unsafe ownership"):
            prepared.kiosk_account(self.root)
        self.home_uid = 1002
        retained = self.home.with_name("retained-home")
        self.home.rename(retained)
        self.home.symlink_to(retained)
        with self.assertRaisesRegex(SystemExit, "unsafe ownership"):
            prepared.kiosk_account(self.root)
        self.home.unlink()
        retained.rename(self.home)
        parent = self.marker.parent
        retained = parent.with_name("retained-state")
        parent.rename(retained)
        parent.symlink_to(retained)
        with self.assertRaises(OSError):
            prepared.kiosk_account(self.root)
        self.assertEqual((retained / self.marker.name).read_text(), "1002\n")

    def test_trusted_root_group_write_is_accepted_but_other_group_is_preserved(self):
        self.marker.parent.chmod(0o775)
        self.assertEqual(prepared.kiosk_account(self.root), self.user)
        with mock.patch.object(prepared, "_OWNER_GID", os.getgid() + 1), \
                self.assertRaisesRegex(SystemExit, "unsafe kiosk ownership directory"):
            prepared.kiosk_account(self.root)
        self.assertEqual(self.marker.read_text(), "1002\n")

    def test_staged_full_provision_composes_broker_uid_bus_policy_without_live_calls(self):
        template = self.root / "usr/share/oh-no-parent-control"
        template.mkdir(parents=True)
        source = {"version": 3, "kiosk_uid": 9999, "minimum_request_interval_seconds": 17}
        (template / "config.example.json").write_text(json.dumps(source))
        (template / "com.puffyslippers.OhNoParentControl1.conf.in").write_text(
            '<policy user="@KIOSK_USER@">retained policy</policy>\n')
        path_before = list(sys.path)
        with mock.patch.object(prepared.os, "chown"), mock.patch.object(prepared.os, "fchown"), \
                mock.patch.object(prepared.subprocess, "run") as run:
            self.assertEqual(prepared.main(["--kiosk-user", prepared.KIOSK_USER,
                                            "--prefix", str(self.root)]), 0)
        run.assert_not_called()
        self.assertEqual(sys.path, path_before)
        config = self.root / "etc/oh-no-parent-control/config.json"
        policy = self.root / "usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf"
        self.assertEqual(json.loads(config.read_text()), dict(source, kiosk_uid=1002))
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(policy.read_text(), '<policy user="oh-no-parent-control">retained policy</policy>\n')
        self.assertEqual(policy.stat().st_mode & 0o777, 0o644)

    def test_atomic_write_failure_keeps_prior_file_and_removes_only_owned_temporary(self):
        output = self.root / "prior-config"
        output.write_text("retained original\n")
        with mock.patch.object(prepared.os, "fchown"), \
                mock.patch.object(prepared.os, "replace", side_effect=OSError("owned write failure")), \
                self.assertRaises(OSError):
            prepared.atomic_write(output, "replacement\n", 0o600)
        self.assertEqual(output.read_text(), "retained original\n")
        self.assertEqual(list(self.root.glob(".prior-config.*")), [])


if __name__ == "__main__":
    unittest.main()
