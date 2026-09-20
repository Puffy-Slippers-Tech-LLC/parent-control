import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.execution_policy import (
    ExecutionPolicyError, FapolicydPolicy,
)


class ExecutionPolicyTests(unittest.TestCase):
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
