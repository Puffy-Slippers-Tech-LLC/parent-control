import unittest
import ast
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import provision as prepared


PROVISION_SOURCE = Path(__file__).resolve().parents[2] / "tools/provision.py"


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

    def test_selected_entry_has_no_old_framework_or_lifecycle_imports(self):
        tree = ast.parse(PROVISION_SOURCE.read_text())
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
