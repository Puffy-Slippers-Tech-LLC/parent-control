import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.catalog import suggested_patterns
from oh_no_parent_control.execution_policy import (
    ExecutionPolicyError, FapolicydPolicy,
)


class ExecutionPolicyTests(unittest.TestCase):
    @staticmethod
    def _decision(rules, uid, permission, path, ftype="application/x-executable"):
        """Evaluate the emitted subset using fapolicyd's first-match semantics.

        These are policy event tests, not a substitute for daemon qualification.
        In particular the caller supplies the observed object type explicitly.
        """
        for line in rules.splitlines():
            if not line or line.startswith("#"):
                continue
            subject, obj = line.split(" : ")
            decision, *fields = subject.split()
            subject = dict(field.split("=", 1) for field in fields)
            obj = dict(field.split("=", 1) for field in obj.split())
            assert set(subject) == {"perm", "uid"}
            assert set(obj) <= {"path", "dir", "sha256hash", "ftype"}
            if int(subject["uid"]) != uid or subject["perm"] not in (permission, "any"):
                continue
            if "path" in obj and str(path) != obj["path"]:
                continue
            if "dir" in obj and not str(path).startswith(obj["dir"]):
                continue
            if "ftype" in obj and ftype not in obj["ftype"].split(","):
                continue
            if "sha256hash" in obj and hashlib.sha256(path.read_bytes()).hexdigest() != obj["sha256hash"]:
                continue
            return decision.split("_", 1)[0]
        # The packaged fallback permits operations outside the product blocks.
        return "allow"

    def test_appimage_read_is_denied_before_launcher_can_copy_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name in ("Lunar.AppImage", "Lunar Client.AppImage", "Lunar,Client.AppImage"):
                with self.subTest(name=name):
                    target = Path(temporary) / name
                    target.write_bytes(b"\x7fELF appimage runtime and payload")
                    rules = FapolicydPolicy.render({1001: (str(target),)})
                    for permission in ("open", "execute"):
                        self.assertEqual(self._decision(rules, 1001, permission, target), "deny")
                        self.assertEqual(self._decision(rules, 1000, permission, target), "allow")
                    # Approving soft apps removes the target from the live filter.
                    approved = FapolicydPolicy.render({1001: ()})
                    self.assertEqual(self._decision(approved, 1001, "open", target), "allow")

    def test_pattern_denies_future_appimage_reads_and_preserves_other_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old = directory / "Lunar Client-1.AppImage"
            allowed = directory / "pCloud.AppImage"
            library = directory / "other.so"
            document = directory / "My Notes.txt"
            for path in (allowed, library):
                path.write_bytes(b"\x7fELF same bytes")
            allowed.chmod(0o755)
            document.write_text("ordinary document")
            (directory / ".trash").mkdir()
            rules = FapolicydPolicy.render(
                {1001: (str(old),)}, {1001: (f"{directory}/Lunar Client-*.AppImage",)})
            # Install/update AFTER rendering: there must be no rescan window.
            future = directory / "Lunar Client-2.AppImage"
            future.write_bytes(allowed.read_bytes())
            future.chmod(0o755)
            for ftype in ("application/x-executable", "application/x-sharedlib", "application/x-bad-elf"):
                with self.subTest(ftype=ftype):
                    self.assertEqual(self._decision(rules, 1001, "open", future, ftype), "deny")
                    self.assertEqual(self._decision(rules, 1001, "open", allowed, ftype), "allow")
                    self.assertEqual(self._decision(rules, 1001, "open", library, ftype), "allow")
                    self.assertEqual(self._decision(rules, 1000, "open", future, ftype), "allow")
            for name in ("My Notes.txt", "new notes.txt", "photo.png"):
                for ftype in ("text/plain", "image/png"):
                    self.assertEqual(self._decision(rules, 1001, "open", directory / name, ftype), "allow")
            self.assertEqual(self._decision(rules, 1001, "execute", future), "deny")
            self.assertEqual(self._decision(rules, 1001, "open", directory / ".trash" / future.name), "allow")
            self.assertNotIn("allow perm=open uid=1001 : sha256hash=", rules)

    def test_open_denials_precede_enclosing_directory_exceptions(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            child = parent / "nested"
            child.mkdir()
            target = child / "Other.AppImage"
            target.write_bytes(b"\x7fELF blocked")
            rules = FapolicydPolicy.render(
                {1001: (str(target),)},
                {1001: (f"{parent}/Game-*.AppImage", f"{child}/Lunar-*.AppImage")})
            future = child / "Lunar-2.AppImage"
            self.assertEqual(self._decision(rules, 1001, "open", target), "deny")
            self.assertEqual(self._decision(rules, 1001, "open", future), "deny")

    def test_non_executable_elf_with_unsafe_name_omits_entire_pattern_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            library = directory / "Other Library.so"
            library.write_bytes(b"\x7fELF library")
            library.chmod(0o644)
            (directory / "safe-subdirectory").mkdir()
            target = directory / "Lunar.AppImage"
            target.write_bytes(b"\x7fELF blocked")
            pattern = f"{directory}/Lunar*.AppImage"
            with self.assertRaises(ExecutionPolicyError):
                FapolicydPolicy.render({1001: (str(target),)}, {1001: (pattern,)})
            issues = []
            rules = FapolicydPolicy.render(
                {1001: (str(target),)}, {1001: (pattern,)}, issues=issues)
            self.assertEqual(issues, [(1001, "pattern", pattern)])
            self.assertNotIn("dir=", rules)
            self.assertEqual(self._decision(rules, 1001, "open", target), "deny")
            library.rename(directory / "OtherLibrary.so")
            rules = FapolicydPolicy.render({1001: (str(target),)}, {1001: (pattern,)})
            self.assertEqual(self._decision(rules, 1001, "open", directory / "Lunar-new.AppImage"), "deny")

    def test_elf_header_inspection_refuses_symlink_and_special_file_replacements(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / "target"
            target.write_bytes(b"\x7fELF")
            link = directory / "link"
            link.symlink_to(target)
            fifo = directory / "fifo"
            os.mkfifo(fifo)
            self.assertTrue(FapolicydPolicy._has_elf_header(str(target)))
            with self.assertRaises(OSError):
                FapolicydPolicy._has_elf_header(str(link))
            with self.assertRaises(ExecutionPolicyError):
                FapolicydPolicy._has_elf_header(str(fifo))

    def test_appimage_open_policy_follows_live_soft_approval_and_restoration(self):
        from oh_no_parent_control.adapters import AccountsService
        from oh_no_parent_control.core import UserAccount

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            soft, hard = root / "soft", root / "hard"
            soft.mkdir()
            hard.mkdir()
            soft_target, hard_target = soft / "Lunar Client-1.AppImage", hard / "Game-1.AppImage"
            for target in (soft_target, hard_target):
                target.write_bytes(b"\x7fELF " + target.name.encode())
            preferences = mock.Mock()
            preferences.load.return_value = {"apps": {
                "lunar.desktop": {"state": "conditional", "targets": [str(soft_target)],
                                  "patterns": [f"{soft}/Lunar Client-*.AppImage"]},
                "hard.desktop": {"state": "permanent", "targets": [str(hard_target)],
                                 "patterns": [f"{hard}/Game-*.AppImage"]},
            }}
            policy = FapolicydPolicy(root / "policy.rules")
            accounts = AccountsService(object(), policy, preferences)
            users = (UserAccount(1001, "child", "Child", False, False, True),)
            live = (False, ())

            def write(_uid, _interface, _prop, value):
                nonlocal live
                allowlist, targets = value.unpack()
                live = (allowlist, tuple(targets))

            with mock.patch.object(accounts, "_set", side_effect=write), \
                    mock.patch.object(accounts, "list_users", return_value=users), \
                    mock.patch.object(accounts, "get_filter", side_effect=lambda _uid: live), \
                    mock.patch.object(policy, "_reload") as reload:
                for include_soft in (True, False, True):
                    accounts.set_filter(1001, (False, (
                        (str(soft_target), str(hard_target)) if include_soft else (str(hard_target),))))
                    rules = policy._rules_path.read_text()
                    expected = "deny" if include_soft else "allow"
                    self.assertEqual(self._decision(rules, 1001, "open", soft_target), expected)
                    future = soft / "Lunar Client-2.AppImage"
                    future.write_bytes(b"\x7fELF new version")
                    self.assertEqual(self._decision(rules, 1001, "open", future), expected)
                    self.assertEqual(self._decision(rules, 1001, "open", hard_target), "deny")
                    self.assertEqual(self._decision(rules, 1000, "open", soft_target), "allow")
            self.assertEqual(reload.call_count, 3)

    def test_generated_lunar_pattern_guards_update_without_integration_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old = directory / 'Lunar Client-3.7.17-ow_2efff2fd1cdfecc506766be231242432.AppImage'
            updated = directory / 'Lunar Client-3.7.20-ow.AppImage'
            other = directory / 'pCloud_42870ec3026efef69e0bdaa75c9347c4.AppImage'
            for path in (updated, other):
                path.write_bytes(b'app')
                path.chmod(0o755)
            (directory / '.trash').mkdir()
            issues = []
            rules = FapolicydPolicy.render(
                {1001: (str(old),)}, {1001: suggested_patterns(str(old))}, issues=issues)
            self.assertEqual(issues, [])
            self.assertIn(f'deny_syslog perm=execute uid=1001 : dir={directory}/', rules)
            self.assertIn(f'allow perm=execute uid=1001 : path={other}', rules)
            self.assertIn(f'allow perm=execute uid=1001 : dir={directory}/.trash/', rules)
            self.assertNotIn(f'path={updated}', rules)
            self.assertNotIn('sha256hash=', rules)

    def test_recoverable_pattern_failure_keeps_other_rules_and_retries_saved_pattern(self):
        for name in ("Other Client.AppImage", "Other,Client.AppImage"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                broken, healthy = root / "broken", root / "healthy"
                broken.mkdir()
                healthy.mkdir()
                unrelated = broken / name
                unrelated.write_bytes(b"same bytes can also appear under a blocked name")
                unrelated.chmod(0o755)
                lunar = broken / "Lunar Client-1.AppImage"
                lunar.write_bytes(b"lunar")
                lunar.chmod(0o755)
                filters = {1001: (str(lunar), "/usr/bin/game"), 1002: ("/usr/bin/other",)}
                patterns = {1001: (f"{broken}/Lunar Client-*.AppImage",
                                   f"{healthy}/Game-*.AppImage"),
                            1002: (f"{healthy}/Other-*.AppImage",)}
                policy = FapolicydPolicy(root / "policy.rules", tolerate_rule_errors=True)
                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                                return_value=SimpleNamespace(returncode=0)):
                    with self.assertLogs("onpc.execution-policy", level="ERROR") as logs:
                        policy.reconcile(filters, patterns)
                    rules = policy._rules_path.read_text()
                    self.assertNotIn(f"dir={broken}/", rules)
                    self.assertIn(f"deny_syslog perm=execute uid=1001 : dir={healthy}/", rules)
                    self.assertIn(f"deny_syslog perm=execute uid=1002 : dir={healthy}/", rules)
                    self.assertIn("deny_syslog perm=execute uid=1001 : sha256hash=", rules)
                    self.assertIn("uid=1001 : path=/usr/bin/game", rules)
                    self.assertIn("uid=1002 : path=/usr/bin/other", rules)
                    self.assertNotIn("allow perm=execute uid=1001 : sha256hash=", rules)
                    self.assertEqual(policy.rule_issues, (
                        (1001, "pattern", patterns[1001][0]),))
                    self.assertNotIn(str(root), "\n".join(logs.output))
                    self.assertNotIn("Lunar", "\n".join(logs.output))
                    # Resolving the folder problem restores the SAME saved glob.
                    unrelated.rename(broken / "Other.AppImage")
                    policy.reconcile(filters, patterns)
                    self.assertEqual(policy.rule_issues, ())
                    self.assertIn(f"deny_syslog perm=execute uid=1001 : dir={broken}/",
                                  policy._rules_path.read_text())

    def test_lunar_pattern_covers_new_versions_even_after_original_disappears(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old = directory / "Lunar Client-1.AppImage"
            future = directory / "Lunar Client-2.AppImage"
            allowed = directory / "Other.AppImage"
            for path in (future, allowed):
                path.write_bytes(b"identical bytes")
                path.chmod(0o755)
            issues = []
            rules = FapolicydPolicy.render(
                {1001: (str(old),)}, {1001: (f"{directory}/Lunar Client-*.AppImage",)},
                issues=issues,
            )
            self.assertEqual(issues, [])
            self.assertIn(f"deny_syslog perm=execute uid=1001 : dir={directory}/", rules)
            self.assertIn(f"allow perm=execute uid=1001 : path={allowed}", rules)
            self.assertNotIn(str(future), rules)
            self.assertNotIn("sha256hash=", rules)

    def test_local_file_error_does_not_remove_other_exact_denials(self):
        issues = []
        with mock.patch.object(FapolicydPolicy, "_digest", side_effect=PermissionError("private")):
            rules = FapolicydPolicy.render(
                {1001: ("/apps/Unreadable Client.AppImage", "/usr/bin/game")}, issues=issues)
        self.assertIn("uid=1001 : path=/usr/bin/game", rules)
        self.assertEqual(issues, [(1001, "target", "/apps/Unreadable Client.AppImage")])

    def test_invalid_identity_and_reload_failures_are_not_ignored(self):
        with self.assertRaises(ExecutionPolicyError):
            FapolicydPolicy.render({0: ("/usr/bin/game",)}, issues=[])
        with tempfile.TemporaryDirectory() as temporary:
            policy = FapolicydPolicy(Path(temporary) / "policy.rules", tolerate_rule_errors=True)
            with mock.patch.object(policy, "_reload", side_effect=ExecutionPolicyError("reload")):
                with self.assertRaisesRegex(ExecutionPolicyError, "rollback"):
                    policy.reconcile({1001: ("/usr/bin/game",)})

    def test_validation_does_not_publish_uncommitted_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            invalid = directory / "Other Client.AppImage"
            invalid.write_bytes(b"app")
            invalid.chmod(0o755)
            policy = FapolicydPolicy(directory / "policy.rules", tolerate_rule_errors=True)
            policy.validate({1001: ()}, {1001: (f"{directory}/Lunar*.AppImage",)})
            self.assertEqual(policy.rule_issues, ())
            self.assertFalse(policy._rules_path.exists())

    def test_nested_guards_and_exact_denials_precede_parent_directory_allowances(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            child = parent / "nested"
            child.mkdir()
            target = child / "Other.AppImage"
            rules = FapolicydPolicy.render(
                {1001: (str(target),)},
                {1001: (f"{parent}/Game-*.AppImage", f"{child}/Lunar-*.AppImage")})
            allowance = rules.index(f"allow perm=execute uid=1001 : dir={child}/")
            self.assertLess(rules.index(f"deny_syslog perm=execute uid=1001 : dir={child}/"), allowance)
            self.assertLess(rules.index(f"path={target}"), allowance)

    def test_native_targets_are_denied_for_only_the_managed_uid(self):
        rules = FapolicydPolicy.render({
            1001: ("/usr/bin/game", "app/org.example.Game/x86_64/stable"),
        })

        self.assertIn(
            "deny_syslog perm=execute uid=1001 : path=/usr/bin/game", rules,
        )
        self.assertNotIn("org.example.Game", rules)

    def test_path_with_spaces_uses_stable_executable_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            appimage = Path(temporary) / "Lunar Client.AppImage"
            appimage.write_bytes(b"lunar")

            rules = FapolicydPolicy.render({1001: (str(appimage),)})

        self.assertIn(
            "deny_syslog perm=execute uid=1001 : "
            "sha256hash=9738b6bf3ae32f433b04b1c3687ac8fec5bf4383b44086c7fb09c5e2a81991cf",
            rules,
        )
        self.assertNotIn("Lunar Client", rules)

    def test_missing_saved_target_does_not_prevent_policy_activation(self):
        rules = FapolicydPolicy.render({
            1001: ("/home/child/Missing Game.AppImage", "/usr/bin/game"),
        })

        self.assertNotIn("Missing", rules)
        self.assertIn("path=/usr/bin/game", rules)

    def test_explicitly_blocked_nonmatching_filename_does_not_break_reconciliation(self):
        for name in ("Other Client.AppImage", "Other,Client.AppImage"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                unrelated = directory / name
                unrelated.write_bytes(b"unrelated application")
                unrelated.chmod(0o755)
                rules_path = directory / "policy.rules"
                policy = FapolicydPolicy(rules_path)
                with mock.patch(
                        "oh_no_parent_control.execution_policy.subprocess.run",
                        return_value=SimpleNamespace(returncode=0)) as run:
                    policy.reconcile(
                        {1001: (str(unrelated), str(directory / "Game-1.AppImage"))},
                        {1001: (f"{directory}/Game-*.AppImage",)},
                    )

                self.assertTrue(rules_path.is_file())
                rules = rules_path.read_text()
                self.assertIn("deny_syslog perm=execute uid=1001 : sha256hash=", rules)
                self.assertNotIn("allow perm=execute", rules)
                self.assertLess(rules.index("sha256hash="), rules.index(f"dir={directory}/"))
                self.assertEqual([call.args[0] for call in run.call_args_list], [
                    ("/usr/sbin/fagenrules",),
                    ("/usr/sbin/fapolicyd-cli", "--reload-rules"),
                ])

    def test_unrelated_unsupported_filename_preserves_rules_without_hash_allowance(self):
        for name in ("Other Client.AppImage", "Other,Client.AppImage"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                unrelated = directory / name
                unrelated.write_bytes(b"unrelated application")
                unrelated.chmod(0o755)
                rules_path = directory / "policy.rules"
                rules_path.write_text("previous rules\n")
                policy = FapolicydPolicy(rules_path)
                with mock.patch(
                        "oh_no_parent_control.execution_policy.subprocess.run") as run:
                    with self.assertRaisesRegex(ExecutionPolicyError, "nonmatching executable"):
                        policy.reconcile(
                            {1001: (str(directory / "Game-1.AppImage"),)},
                            {1001: (f"{directory}/Game-*.AppImage",)},
                        )
                self.assertEqual(rules_path.read_text(), "previous rules\n")
                run.assert_not_called()

    def test_pattern_guards_future_matching_updates_and_preserves_existing_nonmatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            lunar = directory / "Lunar Client-3.7.17.AppImage"
            prism = directory / "PrismLauncher.AppImage"
            lunar.write_bytes(b"lunar")
            prism.write_bytes(b"prism")
            lunar.chmod(0o755)
            prism.chmod(0o755)

            rules = FapolicydPolicy.render(
                {1001: (str(lunar),)}, {1001: (f"{directory}/Lunar Client-*.AppImage",)},
            )

        self.assertIn("sha256hash=", rules)
        self.assertIn(f"allow perm=execute uid=1001 : path={prism}", rules)
        self.assertIn(f"deny_syslog perm=execute uid=1001 : dir={directory}/", rules)
        self.assertLess(rules.index("sha256hash="), rules.index(f"dir={directory}/"))

    def test_reconcile_atomically_writes_and_loads_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            policy = FapolicydPolicy(rules_path)
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    return_value=completed) as run:
                policy.reconcile({1001: ("/usr/bin/game",)})

            self.assertIn("uid=1001", rules_path.read_text(encoding="utf-8"))
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ("/usr/sbin/fagenrules",),
                ("/usr/sbin/fapolicyd-cli", "--reload-rules"),
            ])

    def test_failed_reload_restores_previous_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            rules_path.write_text("old\n", encoding="utf-8")
            policy = FapolicydPolicy(rules_path)
            outcomes = [
                SimpleNamespace(returncode=1, stdout="", stderr="bad"),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    side_effect=outcomes), self.assertRaises(ExecutionPolicyError):
                policy.reconcile({1001: ("/usr/bin/game",)})

            self.assertEqual(rules_path.read_text(encoding="utf-8"), "old\n")

    def test_remove_deletes_rules_and_loads_the_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            rules_path.write_text("old\n", encoding="utf-8")
            policy = FapolicydPolicy(rules_path)
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    return_value=completed) as run:
                policy.remove()

            self.assertFalse(rules_path.exists())
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ("/usr/sbin/fagenrules",),
                ("/usr/sbin/fapolicyd-cli", "--reload-rules"),
            ])

    def test_failed_remove_reload_restores_previous_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            rules_path.write_text("old\n", encoding="utf-8")
            policy = FapolicydPolicy(rules_path)
            outcomes = [
                SimpleNamespace(returncode=1, stdout="", stderr="bad"),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    side_effect=outcomes), self.assertRaises(ExecutionPolicyError):
                policy.remove()

            self.assertEqual(rules_path.read_text(encoding="utf-8"), "old\n")

    def test_notification_failure_recompiles_restored_rules_before_notifying(self):
        for operation in ("reconcile", "remove"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
                rules_path.write_text("old\n", encoding="utf-8")
                policy = FapolicydPolicy(rules_path)
                seen = []

                def run(command, **kwargs):
                    seen.append((command, rules_path.read_bytes() if rules_path.exists() else None))
                    return SimpleNamespace(returncode=1 if len(seen) == 2 else 0)

                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run", side_effect=run):
                    with self.assertRaisesRegex(ExecutionPolicyError, "could not reload"):
                        if operation == "reconcile":
                            policy.reconcile({1001: ("/usr/bin/game",)})
                        else:
                            policy.remove()
                self.assertEqual(len(seen), 4)
                self.assertEqual(seen[2:], [
                    (("/usr/sbin/fagenrules",), b"old\n"),
                    (("/usr/sbin/fapolicyd-cli", "--reload-rules"), b"old\n"),
                ])

    def test_compile_failure_never_notifies_candidate(self):
        policy = FapolicydPolicy()
        with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                        return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaises(ExecutionPolicyError):
                policy._reload()
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ("/usr/sbin/fagenrules",),
        ])

    def test_identical_rules_after_failed_rollback_retry_daemon_notification(self):
        for operation in ("reconcile", "remove"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                rules_path = Path(temporary) / "policy.rules"
                policy = FapolicydPolicy(rules_path)
                original = {1001: ("/usr/bin/game",)}
                compiled = None
                active = None
                fail_notification = False
                notifications = []

                def run(command, **kwargs):
                    nonlocal compiled, active
                    if command == ("/usr/sbin/fagenrules",):
                        compiled = rules_path.read_bytes() if rules_path.exists() else None
                    else:
                        notifications.append(compiled)
                        # A failed command cannot establish whether the daemon
                        # consumed the notification. Model candidate application
                        # followed by rejection of the rollback notification.
                        if not fail_notification or len(notifications) == 2:
                            active = compiled
                        if fail_notification:
                            return SimpleNamespace(returncode=1)
                    return SimpleNamespace(returncode=0)

                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run", side_effect=run):
                    policy.reconcile(original)
                    expected = active
                    fail_notification = True
                    with self.assertRaisesRegex(ExecutionPolicyError, "rollback"):
                        if operation == "reconcile":
                            policy.reconcile({})
                        else:
                            policy.remove()
                    self.assertEqual(rules_path.read_bytes(), expected)
                    self.assertNotEqual(active, expected)
                    # Matching disk state must not conceal another failed retry.
                    with self.assertRaises(ExecutionPolicyError):
                        policy.reconcile(original)
                    fail_notification = False
                    policy.reconcile(original)
                    self.assertEqual(active, expected)
                    count = len(notifications)
                    policy.reconcile(original)
                    self.assertEqual(len(notifications), count)

    def test_new_adapter_reloads_existing_identical_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "policy.rules"
            filters = {1001: ("/usr/bin/game",)}
            rules_path.write_text(FapolicydPolicy.render(filters), encoding="utf-8")
            for _ in range(2):
                policy = FapolicydPolicy(rules_path)
                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                                return_value=SimpleNamespace(returncode=0)) as run:
                    policy.reconcile(filters)
                    self.assertEqual(run.call_count, 2)
                    policy.reconcile(filters)
                    self.assertEqual(run.call_count, 2)

    def test_successful_rollback_allows_unchanged_notification_cache(self):
        for operation in ("reconcile", "remove"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                rules_path = Path(temporary) / "policy.rules"
                policy = FapolicydPolicy(rules_path)
                filters = {1001: ("/usr/bin/game",)}
                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                                return_value=SimpleNamespace(returncode=0)):
                    policy.reconcile(filters)
                outcomes = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=1),
                            SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)]
                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                                side_effect=outcomes) as run:
                    with self.assertRaises(ExecutionPolicyError):
                        if operation == "reconcile":
                            policy.reconcile({})
                        else:
                            policy.remove()
                    policy.reconcile(filters)
                    self.assertEqual(run.call_count, 4)

    def test_reload_command_errors_are_bounded_and_do_not_log_output(self):
        import subprocess

        for error in (OSError("private-output"), subprocess.TimeoutExpired("private-command", 15)):
            with self.subTest(error=type(error).__name__):
                policy = FapolicydPolicy()
                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                                side_effect=error) as run:
                    with self.assertLogs("onpc.execution-policy", level="ERROR") as logs:
                        with self.assertRaises(ExecutionPolicyError):
                            policy._reload()
                self.assertEqual(run.call_args.kwargs["timeout"], 15)
                self.assertNotIn("private-", " ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
