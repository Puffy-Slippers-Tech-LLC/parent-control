import ast
import array
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from common.oh_no_parent_control_ui.diagnostic_events import decode

from oh_no_parent_control.extension_manager import (
    DISABLE_ALL_KEY, DISABLED_KEY, ENABLED_KEY, UUID, ChildExtensionFailed, ChildExtensionUnavailable,
    ExtensionManager, _load_error_fields,
)
from oh_no_parent_control import child_bus, extension_monitor


class ChildBusTransportTests(unittest.TestCase):
    def test_rejects_extra_transferred_descriptors_and_closes_every_received_fd(self):
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        read_fd, write_fd = os.pipe()
        close = os.close
        try:
            child.sendmsg([b"S"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                array.array("i", [read_fd, write_fd]))])
            with mock.patch.object(child_bus.os, "close", wraps=close) as closed:
                with self.assertRaisesRegex(ValueError, "descriptor message"):
                    child_bus._receive_descriptor(parent)
            received = [call.args[0] for call in closed.call_args_list]
            self.assertEqual(len(received), 2)
            for descriptor in received:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)
        finally:
            parent.close()
            child.close()
            close(read_fd)
            close(write_fd)

    def test_fixed_helper_drops_all_extra_groups_and_cancel_reaps_it_once(self):
        from gi.repository import GLib

        account = SimpleNamespace(pw_uid=1001, pw_gid=1002)
        completed = mock.Mock()
        process = mock.Mock()
        process.poll.return_value = None
        with (mock.patch.object(child_bus, "_validate_target", return_value="/safe/bus"),
              mock.patch.object(child_bus, "_receive_descriptor", side_effect=BlockingIOError),
              mock.patch.object(child_bus.subprocess, "Popen", return_value=process) as popen):
            attempt = child_bus.connect_child_bus(account, "unix:path=/safe/bus",
                GLib.MainContext.new(), completed)
            attempt._poll()
            arguments = popen.call_args
            self.assertEqual(arguments.args[0][:3], ["/usr/bin/python3", "-I", child_bus.HELPER_PATH])
            self.assertEqual(arguments.kwargs["user"], 1001)
            self.assertEqual(arguments.kwargs["group"], 1002)
            self.assertEqual(arguments.kwargs["extra_groups"], ())
            self.assertEqual(arguments.kwargs["env"], {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8", "HOME": "/nonexistent"})
            self.assertEqual(len(arguments.kwargs["pass_fds"]), 1)
            attempt.cancel()
            attempt.cancel()
            self.assertTrue(attempt.pending)
            completed.assert_not_called()
            process.poll.return_value = -9
            attempt._poll()
        process.kill.assert_called_once_with()
        process.wait.assert_not_called()
        completed.assert_called_once()
        self.assertIsInstance(completed.call_args.args[1], InterruptedError)
        self.assertIsNone(attempt.channel)
        self.assertTrue(attempt.source.is_destroyed())

    def test_cancel_interrupts_hello_without_closing_gio_owned_descriptor(self):
        from gi.repository import GLib

        transport, peer = socket.socketpair()
        completed = mock.Mock()
        attempt = child_bus.connect_child_bus(SimpleNamespace(pw_uid=1001, pw_gid=1001),
            "unix:path=/unused", GLib.MainContext.new(), completed)
        try:
            attempt.guardian = socket.socket(fileno=os.dup(transport.fileno()))
            attempt.stream = object()
            attempt.cancel()
            peer.settimeout(1)
            self.assertEqual(peer.recv(1), b"")
            os.fstat(transport.fileno())  # The Gio-owned endpoint is still open.
            self.assertTrue(attempt.cancellable.is_cancelled())
            self.assertIsNone(attempt.guardian)
            completed.assert_called_once()
        finally:
            attempt.cancel()
            transport.close()
            peer.close()

    def test_cleanup_errors_keep_helper_owned_until_reaped_and_monitor_retries(self):
        account = SimpleNamespace(pw_uid=1001, pw_gid=1001)
        manager = mock.Mock()
        manager.session_bus_address.return_value = "unix:path=/safe/bus"
        manager._account.return_value = (account, None)
        process = mock.Mock()
        process.poll.return_value = None
        with (mock.patch.object(extension_monitor.threading.Thread, "start"),
              mock.patch.object(child_bus, "_validate_target", return_value="/safe/bus"),
              mock.patch.object(child_bus, "_receive_descriptor", side_effect=BlockingIOError),
              mock.patch.object(child_bus.subprocess, "Popen", return_value=process) as popen):
            monitor = extension_monitor.ExtensionMonitor(mock.Mock(), manager, mock.Mock())
            watch = extension_monitor._Watch(1001)
            monitor.watches[1001] = watch
            with mock.patch.object(monitor, "_retry") as retry:
                monitor._connect(watch)
                attempt = watch.connecting
                attempt._poll()
                attempt.deadline = 0
                process.poll.side_effect = [subprocess.TimeoutExpired("private", 0),
                                           None, None, -9]
                process.kill.side_effect = [OSError("private cleanup failure"), None]
                with self.assertLogs("onpc", "ERROR") as logs:
                    for _ in range(3):
                        attempt._poll()
                        self.assertIs(watch.connecting, attempt)
                        self.assertIs(attempt.process, process)
                        self.assertTrue(attempt.pending)
                        monitor._connect(watch)
                        retry.assert_not_called()
                    attempt._poll()
                self.assertNotIn("private", "\n".join(logs.output))
                self.assertFalse(attempt.pending)
                self.assertIsNone(attempt.process)
                self.assertIsNone(watch.connecting)
                self.assertEqual(monitor._attempts, {})
                retry.assert_called_once_with(watch)
                self.assertEqual(popen.call_count, 1)
                process.wait.assert_not_called()
                monitor._connect(watch)
                self.assertIsNotNone(watch.connecting)
                monitor._disconnect(watch)
                self.assertEqual(monitor._attempts, {})

    def test_helper_failure_preserves_safe_category_and_differs_from_malformed_fd(self):
        from gi.repository import Gio, GLib
        from common.oh_no_parent_control_ui.diagnostic_events import record_exception

        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        secret = "private@example.test /home/private-child"
        try:
            error = GLib.Error.new_literal(Gio.dbus_error_quark(), secret, Gio.DBusError.AUTH_FAILED)
            status = child_bus._authentication_status(error)
            self.assertEqual(status, b"A")
            child.send(b"E" + status)
            with self.assertLogs("onpc", "ERROR") as logs:
                try:
                    child_bus._receive_descriptor(parent)
                except GLib.Error as received:
                    record_exception(received)
                else:
                    self.fail("authentication refusal was accepted")
            payloads = [decode(row.onpc_payload) for row in logs.records]
            self.assertIn("access-denied", [row["fields"].get("category") for row in payloads])
            fault = next(row for row in payloads if row["event"] == "runtime.fault")
            self.assertEqual(fault["fields"]["source"], "child-bus")
            self.assertGreater(fault["fields"]["line"], 0)
            self.assertNotIn(secret, "\n".join(logs.output))
            closed = GLib.Error.new_literal(Gio.io_error_quark(), secret, Gio.IOErrorEnum.CONNECTION_CLOSED)
            self.assertEqual(child_bus._authentication_status(closed), b"D")
            child.send(b"EX")
            with self.assertRaisesRegex(ValueError, "descriptor message"):
                child_bus._receive_descriptor(parent)
            child.close()
            with self.assertRaisesRegex(RuntimeError, "without a status"):
                child_bus._receive_descriptor(parent)
        finally:
            parent.close()
            child.close()

    def test_refuses_root_identity_and_nonlocal_or_multiple_addresses(self):
        account = SimpleNamespace(pw_uid=0, pw_gid=0)
        with self.assertRaisesRegex(ValueError, "identity"):
            child_bus._validate_target(account, "unix:path=/run/user/0/bus")
        for address in ("autolaunch:", "tcp:host=localhost,port=1",
                        "unix:path=/tmp/a;unix:path=/tmp/b", "unix:path=/tmp/%2fbus"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                child_bus._address_path(address)

    def test_whole_deadline_interrupts_stalled_native_hello_and_releases_stream(self):
        from gi.repository import Gio, GLib

        context = GLib.MainContext.new()
        transport, peer = socket.socketpair()
        completed = mock.Mock()
        context.push_thread_default()
        attempt = child_bus.connect_child_bus(SimpleNamespace(pw_uid=1001, pw_gid=1001),
            "unix:path=/unused", context, completed, timeout=0.05)
        try:
            attempt.process = mock.Mock()
            attempt.process.poll.return_value = 0
            attempt.guardian = socket.socket(fileno=os.dup(transport.fileno()))
            native = Gio.Socket.new_from_fd(os.dup(transport.fileno()))
            attempt.stream = native.connection_factory_create_connection()
            attempt._hello_pending = True
            Gio.DBusConnection.new(attempt.stream, None, Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, attempt.cancellable, attempt._connected)
            deadline = time.monotonic() + 1
            while not completed.called and time.monotonic() < deadline:
                context.iteration(False)
                time.sleep(0.001)
            completed.assert_called_once()
            self.assertIsInstance(completed.call_args.args[1], TimeoutError)
            self.assertFalse(attempt.pending)
            self.assertIsNone(attempt.stream)
            self.assertIsNone(attempt.guardian)
        finally:
            attempt.cancel()
            transport.close()
            peer.close()
            context.pop_thread_default()


class LoadDiagnosticsTests(unittest.TestCase):
    def test_failed_settings_probe_preserves_other_keys_and_live_shell_evidence(self):
        from gi.repository import GLib

        manager = ExtensionManager()
        state = GnomeRecoveryState()
        reply = GLib.Variant("(a{sv})", ({"state": GLib.Variant("d", 2),
                                       "error": GLib.Variant("s", "")},)).print_(True)

        def run(account, args, **kwargs):
            if args[:2] == ("gsettings", "get") and args[3] == ENABLED_KEY:
                raise RuntimeError("private@example.test /home/private-child")
            if args[0] == "gdbus":
                return SimpleNamespace(stdout=reply if args[-1] == UUID else "(true,)")
            return state.run(account, args, **kwargs)

        with (mock.patch.object(manager, "_account", return_value=(object(), None)),
              mock.patch.object(manager, "_session_transport", return_value="live-session"),
              mock.patch.object(manager, "_run_command", side_effect=run),
              self.assertLogs("onpc", "INFO") as logs):
            manager.collect_diagnostics([987654], saved_states={987654: "off"})
        decoded = [decode(row.onpc_payload) for row in logs.records]
        snapshot = next(row for row in decoded if row["event"] == "extension-manager.diagnostic-snapshot")
        self.assertEqual(snapshot["fields"], dict(saved_control="off", session_bus="live-session",
                         global_disabled="true", enabled_entry="unknown", disabled_entry="present"))
        self.assertTrue(any(row["event"] == "extension-manager.load-state" for row in decoded))
        self.assertTrue(all(row["operation"] == snapshot["operation"] != 0 for row in decoded))
        self.assertNotIn("private", "\n".join(logs.output))
        self.assertNotIn("987654", "\n".join(logs.output))

    def test_shell_import_projection_excludes_private_details_and_unknown_assets(self):
        prefix = f"file:///usr/share/gnome-shell/extensions/{UUID}/"
        secret = "private@example.test /home/private-child"
        message = "ImportError: Unable to load file from: " + prefix + "indicatorLogic.mjs (" + secret
        self.assertEqual(_load_error_fields({"state": 3.0, "error": message + ": Operation not permitted)"}), {
            "state": "error", "asset": "indicator-logic", "reason": "import-operation-not-permitted"})
        self.assertEqual(_load_error_fields({"state": 3, "error": message.replace(prefix, "/home/private/")}), {
            "state": "error", "asset": "other", "reason": "other"})
        self.assertEqual(_load_error_fields({"state": 123456, "error": secret}), {
            "state": "other", "asset": "other", "reason": "other"})

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_policy_observation_preserves_trust_filter_cause_without_inventory(self, run):
        secret = "private@example.test /home/private-child"
        run.side_effect = [subprocess.CompletedProcess([], 0, stdout=s, stderr=secret) for s in (
            "application/javascript\n",
            "rpmdb /home/private-child/private app.js 42 " + "a" * 64 + "\n",
            "allow *.js no match\ndecision exclude\n",
            "-> %languages=application/javascript,text/javascript\n"
            "11. allow perm=open all : ftype=%languages trust=1\n"
            "12. deny_audit perm=any all : ftype=%languages\n" + secret)]
        with self.assertLogs("onpc", "INFO") as logs:
            ExtensionManager()._payload_diagnostics("indicator-logic", float("inf"))
        event = decode(logs.records[-1].onpc_payload)
        self.assertEqual(event["event"], "extension-manager.payload-policy")
        self.assertEqual(event["fields"], {"asset": "indicator-logic", "file_type": "javascript",
            "trust": "absent", "filter": "excluded", "language_policy": "trusted-only-rule-present"})
        self.assertNotIn("private", "\n".join(logs.output))

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_unavailable_policy_tools_do_not_claim_absent_trust(self, run):
        run.side_effect = FileNotFoundError("/home/private-child")
        with self.assertLogs("onpc", "INFO") as logs:
            ExtensionManager()._payload_diagnostics("indicator-logic", float("inf"))
        self.assertEqual(decode(logs.records[-1].onpc_payload)["fields"]["trust"], "unknown")
        self.assertNotIn("private", "\n".join(logs.output))

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_malformed_trust_output_is_unknown_rather_than_absent(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="private@example.test", stderr="")
        with self.assertLogs("onpc", "INFO") as logs:
            ExtensionManager()._payload_diagnostics("indicator-logic", float("inf"))
        self.assertEqual(decode(logs.records[-1].onpc_payload)["fields"]["trust"], "unknown")
        self.assertNotIn("private", "\n".join(logs.output))

    def test_live_collection_observes_import_failure_without_settings_writes(self):
        from gi.repository import GLib
        secret = "private@example.test /home/private-child"
        message = (f"ImportError: Unable to load file from: file:///usr/share/gnome-shell/extensions/{UUID}/"
                   "indicatorLogic.mjs (" + secret + ": Operation not permitted)")
        reply = GLib.Variant("(a{sv})", ({"state": GLib.Variant("d", 3),
                                       "error": GLib.Variant("s", message)},)).print_(True)
        manager = ExtensionManager()
        account = SimpleNamespace(pw_uid=123456)
        with (mock.patch.object(manager, "_account", return_value=(account, None)),
              mock.patch.object(manager, "_session_transport", return_value="live-session"),
              mock.patch.object(manager, "_run_command", side_effect=[
                  SimpleNamespace(stdout="[]"), SimpleNamespace(stdout="[]"),
                  SimpleNamespace(stdout="true"), SimpleNamespace(stdout="(true,)"),
                  SimpleNamespace(stdout=reply)]) as run,
              mock.patch.object(manager, "_payload_diagnostics") as policy,
              self.assertLogs("onpc", "INFO") as logs):
            manager.collect_diagnostics([123456])
        self.assertEqual(len(run.call_args_list), 5)
        self.assertTrue(all(call.args[1][:2] == ("gsettings", "get") for call in run.call_args_list[:3]))
        event = next(decode(row.onpc_payload) for row in logs.records
                     if decode(row.onpc_payload)["event"] == "extension-manager.load-state")
        self.assertEqual(event["fields"]["reason"], "import-operation-not-permitted")
        policy.assert_called_once()
        self.assertNotIn("private", "\n".join(logs.output))
        self.assertNotIn("123456", "\n".join(logs.output))

    def test_no_shell_or_offline_session_never_activates_extension_service(self):
        manager = ExtensionManager()
        with (mock.patch.object(manager, "_account", return_value=(object(), None)),
              mock.patch.object(manager, "_session_transport", side_effect=["offline", "live-session"]),
              mock.patch.object(manager, "_run_command", side_effect=lambda _account, args, **_kw:
                  SimpleNamespace(stdout="(false,)" if args[0] == "gdbus" else
                                  "false" if args[3] == DISABLE_ALL_KEY else "[]")) as run):
            manager.collect_diagnostics([1, 2])
        self.assertEqual(len(run.call_args_list), 7)
        self.assertIn("org.freedesktop.DBus.NameHasOwner", run.call_args.args[1])
        self.assertFalse(any("GetExtensionInfo" in str(call.args) for call in run.call_args_list))

    def test_budget_exhaustion_refuses_commands_and_malformed_reply_is_safe(self):
        manager = ExtensionManager()
        with (mock.patch.object(manager, "_account", return_value=(object(), None)),
              mock.patch.object(manager, "_session_transport", return_value="live-session"),
              mock.patch("oh_no_parent_control.extension_manager.time.monotonic", side_effect=[0, 9]),
              mock.patch.object(manager, "_run_command") as run,
              self.assertLogs("onpc", "WARNING") as logs):
            manager.collect_diagnostics([123456])
        run.assert_not_called()
        self.assertEqual(decode(logs.records[-1].onpc_payload)["fields"]["outcome"], "budget-exhausted")
        with (mock.patch.object(manager, "_account", return_value=(object(), None)),
              mock.patch.object(manager, "_session_transport", return_value="live-session"),
              mock.patch.object(manager, "_run_command", side_effect=[SimpleNamespace(stdout="(true,)"),
                  SimpleNamespace(stdout="/home/private-child private@example.test")]),
              self.assertLogs("onpc", "WARNING") as logs):
            manager.collect_diagnostics([123456])
        probes = [decode(row.onpc_payload) for row in logs.records
                  if decode(row.onpc_payload)["event"] == "extension-manager.diagnostic-probe"]
        self.assertEqual(probes[-1]["fields"]["outcome"], "unavailable")
        self.assertNotIn("private", "\n".join(logs.output))


class GnomeRecoveryState:
    """Stateful public-command fake, including GNOME's global disable switch."""

    def __init__(self, *, inactive=False, ignore_switch=False, rollback_failure=False,
                 ignore_lists=False):
        self.values = {
            ENABLED_KEY: ["other-enabled@example.com"],
            DISABLED_KEY: [UUID, "other-disabled@example.com"],
            DISABLE_ALL_KEY: True,
        }
        self.inactive = inactive
        self.ignore_switch = ignore_switch
        self.rollback_failure = rollback_failure
        self.ignore_lists = ignore_lists
        self.commands = []

    def run(self, _account, arguments, **_kwargs):
        self.commands.append(arguments)
        stdout = ""
        if arguments[:2] == ("gsettings", "get"):
            value = self.values[arguments[3]]
            stdout = str(value).lower() if type(value) is bool else repr(value)
        elif arguments[:2] == ("gsettings", "set"):
            key, value = arguments[3:]
            if key == DISABLE_ALL_KEY:
                if value == "true" and self.rollback_failure:
                    raise RuntimeError("private-command-canary")
                if not self.ignore_switch:
                    self.values[key] = value == "true"
            elif not self.ignore_lists:
                self.values[key] = ast.literal_eval(value)
        elif arguments[:2] == ("gnome-extensions", "enable"):
            if UUID in self.values[DISABLED_KEY]:
                self.values[DISABLED_KEY].remove(UUID)
            if UUID not in self.values[ENABLED_KEY]:
                self.values[ENABLED_KEY].append(UUID)
        elif arguments[:2] == ("gnome-extensions", "list"):
            configured = UUID in self.values[ENABLED_KEY]
            active = configured and not self.values[DISABLE_ALL_KEY] and not self.inactive
            if (arguments[2] == "--enabled" and configured or
                    arguments[2] == "--active" and active):
                stdout = UUID + "\n"
        else:
            raise AssertionError("unexpected GNOME command")
        return subprocess.CompletedProcess(arguments, 0, stdout=stdout, stderr="")


class ExtensionManagerTests(unittest.TestCase):
    def setUp(self):
        self.account = SimpleNamespace(
            pw_uid=1001, pw_gid=1001, pw_name="child", pw_dir="/home/child",
        )
        self.runtime = tempfile.TemporaryDirectory()
        self.manager = ExtensionManager(runtime_root=Path(self.runtime.name) / "missing")

    def tearDown(self):
        self.runtime.cleanup()

    def test_loading_error_sentinel_is_not_a_confirmed_failure(self):
        from gi.repository import GLib

        for state, errors, failed in ((3, [], False), (3, [""], True), (4, [], True)):
            with self.subTest(state=state, errors=errors):
                info = GLib.Variant("(a{sv})", ({
                    "state": GLib.Variant("d", state),
                    "error": GLib.Variant("s", "")},)).print_(True)
                history = GLib.Variant("(as)", (errors,)).print_(True)
                with mock.patch.object(self.manager, "_run_command", side_effect=[
                        SimpleNamespace(stdout=info), SimpleNamespace(stdout=history)]) as run:
                    self.assertEqual(self.manager._failed_live_extension(self.account), failed)
                if state == 3:
                    self.assertEqual(run.call_args.args[1][-2:], (
                        "org.gnome.Shell.Extensions.GetExtensionErrors", UUID))
                    self.assertTrue(run.call_args.kwargs["require_live"])

    def test_confirmed_load_failure_refuses_reactivation_before_settings_writes(self):
        state = GnomeRecoveryState(inactive=True)
        with (mock.patch.object(self.manager, "_verify_installation"),
              mock.patch.object(self.manager, "_account", return_value=(self.account, Path(self.runtime.name))),
              mock.patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=1001, st_mode=0o40700)),
              mock.patch.object(self.manager, "_shell_is_available", return_value=True),
              mock.patch.object(self.manager, "_run_as", side_effect=lambda account, *args: state.run(account, args)),
              mock.patch.object(self.manager, "_runtime_state", return_value=(False, False)),
              mock.patch.object(self.manager, "_failed_live_extension", return_value=True)):
            with self.assertRaises(ChildExtensionFailed):
                self.manager.set_enabled(1001, True, recover_global_switch=True)
        self.assertFalse(any(command[:2] == ("gsettings", "set") for command in state.commands))

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_monitor_command_budget_prevents_effects_after_stop_and_nests_for_rollback(self, run):
        stopped = threading.Event()
        stopped.set()
        with self.manager.command_budget(3, stopped):
            with self.assertRaises(TimeoutError):
                self.manager._run_as(self.account, "gsettings", "set", "schema", "key", "value")
            with self.manager.command_budget(3, threading.Event()):
                run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
                self.manager._run_as(self.account, "gsettings", "get", "schema", "key")
            with self.assertRaises(TimeoutError):
                self.manager._run_as(self.account, "gsettings", "set", "schema", "key", "value")
        self.assertEqual(run.call_count, 1)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 3)

    def test_report_uses_fixed_user_manager_launch_and_reuses_existing_report_unit(self):
        with (mock.patch.object(self.manager, "_account", return_value=(self.account, None)),
              mock.patch.object(self.manager, "_run_command", side_effect=[RuntimeError(), None]) as run):
            self.manager.report_failure(1001)
        self.assertEqual(run.call_args_list[0].args[1][-4:], (
            "--", "/usr/bin/oh-no-parent-control-child", "--child-overlay", "--error-report-stdin"))
        self.assertIn("--unit=oh-no-parent-control-extension-error.service", run.call_args_list[0].args[1])
        self.assertEqual(run.call_args_list[1].args[1][:4], ("systemctl", "--user", "is-active", "--quiet"))
        self.assertTrue(all(call.kwargs["require_live"] for call in run.call_args_list))

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_report_command_projects_diagnostics_and_executes_as_the_child(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (mock.patch.object(self.manager, "_account", return_value=(self.account, None)),
              mock.patch.object(self.manager, "_command", side_effect=lambda _account, arguments:
                  (list(arguments), {"XDG_RUNTIME_DIR": "/run/user/1001"}, "live-session")),
              self.assertLogs("onpc", "INFO") as logs):
            self.manager.report_failure(1001)
        self.assertEqual(run.call_args.args[0][0], "systemd-run")
        self.assertEqual(run.call_args.kwargs["user"], 1001)
        self.assertEqual(run.call_args.kwargs["extra_groups"], ())
        events = [decode(record.onpc_payload) for record in logs.records]
        self.assertNotIn("diagnostic.rejected", [row["event"] for row in events])
        self.assertTrue(all(row["fields"].get("operation", "other") == "other" for row in events))

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_command_drops_privileges_without_pam(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="[]\n", stderr="")

        self.manager._run_as(self.account, "gsettings", "get", "schema", "key")

        arguments, = run.call_args.args
        self.assertEqual(arguments, [
            "dbus-run-session", "--", "gsettings", "get", "schema", "key",
        ])
        self.assertEqual(run.call_args.kwargs["user"], 1001)
        self.assertEqual(run.call_args.kwargs["group"], 1001)
        self.assertEqual(run.call_args.kwargs["extra_groups"], ())
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], "/home/child")
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", run.call_args.kwargs["env"])

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_failure_is_reported_as_extension_error(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, ["dbus-run-session"], stderr="session bus failed",
        )

        with self.assertLogs("onpc", "ERROR") as logs:
            with self.assertRaisesRegex(RuntimeError, "GNOME interface is unavailable"):
                self.manager._run_as(
                    self.account, "gsettings", "get", "schema", "key"
                )

        self.assertIn("error_type=CalledProcessError", logs.output[-1])
        self.assertNotIn("session bus failed", logs.output[-1])

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_successful_exit_retains_commit_warning_without_private_text(self, run):
        secret = "/home/private-child/private-file private@example.test"
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="", stderr="failed to commit changes to dconf: Permission denied " + secret)
        with self.assertLogs("onpc", "INFO") as logs:
            result = self.manager._run_as(
                self.account, "gsettings", "set", "org.gnome.shell", ENABLED_KEY, repr([secret]))
        self.assertEqual(result.returncode, 0)
        payloads = [decode(record.onpc_payload) for record in logs.records]
        warning = next(item for item in payloads if item["event"] == "extension-manager.command-warning")
        self.assertEqual(warning["fields"], {
            "tool": "gsettings", "operation": "set", "key": ENABLED_KEY,
            "transport": "offline", "reason": "dconf-access-denied"})
        self.assertNotIn(secret, "\n".join(logs.output))
        self.assertNotIn("diagnostic.rejected", [item["event"] for item in payloads])
        self.assertEqual(run.call_args.kwargs["env"]["LC_MESSAGES"], "C")

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_successful_exit_preserves_offline_bus_root_cause_and_commit_failure(self, run):
        secret = "/home/private-child/private-file private@example.test"
        run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr=(
            "avc: could not open netlink socket: 97 (Address family not supported by protocol)\n"
            "dbus-daemon[987654]: Failed to start message bus: Cannot acquire AVC netlink fd: "
            "Address family not supported by protocol\n"
            "dbus-run-session: dbus-daemon exited with code 1\n"
            "dconf-WARNING: failed to commit changes to dconf: Could not connect: "
            "No such file or directory " + secret))
        with self.assertLogs("onpc", "INFO") as logs:
            result = self.manager._run_as(
                self.account, "gsettings", "set", "org.gnome.shell", ENABLED_KEY, repr([secret]))
        self.assertEqual(result.returncode, 0)
        payloads = [decode(record.onpc_payload) for record in logs.records]
        failure = next(item for item in payloads if item["event"] == "extension-manager.session-bus-failure")
        self.assertEqual(failure["fields"], {
            "tool": "gsettings", "operation": "set", "key": ENABLED_KEY,
            "transport": "offline", "reason": "selinux-netlink-family-unavailable"})
        warning = next(item for item in payloads if item["event"] == "extension-manager.command-warning")
        self.assertEqual(warning["fields"]["reason"], "dconf-commit-failed")
        self.assertEqual(next(record.levelname for record in logs.records
                              if decode(record.onpc_payload)["event"] == failure["event"]), "ERROR")
        self.assertNotIn(secret, "\n".join(logs.output))
        self.assertNotIn("987654", "\n".join(logs.output))
        self.assertNotIn("diagnostic.rejected", [item["event"] for item in payloads])

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_failed_exit_preserves_bus_failure_without_inventing_netlink_cause(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, [], stderr="dbus-run-session: dbus-daemon exited with code 1 private@example.test")
        with self.assertLogs("onpc", "INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "interface is unavailable"):
                self.manager._run_as(self.account, "gsettings", "get", "org.gnome.shell", ENABLED_KEY)
        payloads = [decode(record.onpc_payload) for record in logs.records]
        failure = next(item for item in payloads if item["event"] == "extension-manager.session-bus-failure")
        self.assertEqual(failure["fields"]["reason"], "startup-failed")
        self.assertNotIn("private@example.test", "\n".join(logs.output))

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_failed_exit_retains_warning_category(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, [], stderr="No such schema private@example.test")
        with self.assertLogs("onpc", "INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "interface is unavailable"):
                self.manager._run_as(self.account, "gsettings", "get", "org.gnome.shell", ENABLED_KEY)
        self.assertTrue(any("reason=settings-schema-missing" in row for row in logs.output))
        self.assertNotIn("private@example.test", "\n".join(logs.output))

    def test_readback_failure_and_rollback_name_the_setting(self):
        state = GnomeRecoveryState(ignore_switch=True)
        with self.assertLogs("onpc", "INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "switch verification failed"):
                self._recover(state, live=False)
        payloads = [decode(record.onpc_payload) for record in logs.records]
        verification = [item["fields"] for item in payloads
                        if item["event"] == "extension-manager.setting-verification"]
        self.assertIn({"key": DISABLE_ALL_KEY, "stage": "switch", "matches": False}, verification)
        self.assertIn({"key": ENABLED_KEY, "stage": "rollback", "matches": True}, verification)
        self.assertIn({"key": DISABLED_KEY, "stage": "rollback", "matches": True}, verification)
        fault = next(item for item in payloads if item["event"] == "runtime.fault")
        self.assertEqual(fault["fields"]["source"], "extension-manager")
        self.assertEqual(fault["fields"]["error_type"], "RuntimeError")
        self.assertGreater(fault["fields"]["line"], 0)
        self.assertNotIn("other-enabled@example.com", "\n".join(logs.output))
        self.assertNotIn("diagnostic.rejected", [item["event"] for item in payloads])

    def test_offline_uncommitted_settings_log_failure_and_verified_rollback(self):
        state = GnomeRecoveryState(ignore_lists=True)
        state.values[DISABLE_ALL_KEY] = False
        before = {key: value[:] if isinstance(value, list) else value
                  for key, value in state.values.items()}
        with self.assertLogs("onpc", "INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "activation verification failed"):
                self._recover(state, live=False)
        payloads = [decode(record.onpc_payload) for record in logs.records]
        verification = [item["fields"] for item in payloads
                        if item["event"] == "extension-manager.setting-verification"]
        self.assertIn({"key": ENABLED_KEY, "stage": "offline", "matches": False}, verification)
        self.assertIn({"key": ENABLED_KEY, "stage": "rollback", "matches": True}, verification)
        self.assertIn({"key": DISABLED_KEY, "stage": "rollback", "matches": True}, verification)
        fault = next(item for item in payloads if item["event"] == "runtime.fault")
        self.assertEqual(fault["fields"]["source"], "extension-manager")
        self.assertGreater(fault["fields"]["line"], 0)
        self.assertEqual(state.values, before)
        self.assertNotIn("other-enabled@example.com", "\n".join(logs.output))
        self.assertNotIn("diagnostic.rejected", [item["event"] for item in payloads])

    def test_shell_availability_uses_standard_bus_name_ownership(self):
        result = subprocess.CompletedProcess(
            [], 0, stdout="(true,)\n", stderr="",
        )
        manager = ExtensionManager()
        with (
            mock.patch.object(
                manager, "_session_transport", return_value="live-session"
            ),
            mock.patch.object(manager, "_run_command", return_value=result) as run,
        ):
            self.assertTrue(manager._shell_is_available(self.account))

        _, arguments = run.call_args.args
        self.assertIn("org.freedesktop.DBus.NameHasOwner", arguments)
        self.assertEqual(arguments[-1], "org.gnome.Shell")
        self.assertTrue(run.call_args.kwargs["require_live"])

    def test_shell_is_not_available_without_a_live_user_bus(self):
        with (
            mock.patch.object(
                self.manager, "_session_transport", return_value="offline"
            ),
            mock.patch.object(self.manager, "_run_command") as run,
        ):
            self.assertFalse(self.manager._shell_is_available(self.account))
        run.assert_not_called()

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_command_notifies_an_existing_user_session(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="[]\n", stderr="")
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="/home/child",
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / str(account.pw_uid)
            runtime.mkdir()
            (runtime / "bus").touch()
            manager = ExtensionManager(runtime_root=Path(directory))
            with mock.patch(
                    "oh_no_parent_control.extension_manager.stat.S_ISSOCK",
                    return_value=True):
                manager._run_as(account, "gsettings", "get", "schema", "key")

        arguments, = run.call_args.args
        self.assertEqual(arguments, ["gsettings", "get", "schema", "key"])
        self.assertEqual(
            run.call_args.kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"],
            f"unix:path={runtime}/bus",
        )
        self.assertEqual(
            run.call_args.kwargs["env"]["XDG_RUNTIME_DIR"], str(runtime),
        )

    def test_packaged_extension_requires_root_owned_regular_entry_points(self):
        with tempfile.TemporaryDirectory() as directory:
            installation = Path(directory)
            (installation / "metadata.json").write_text("{}", encoding="utf-8")
            (installation / "extension.js").write_text("", encoding="utf-8")
            manager = ExtensionManager(
                installation=installation,
                installation_owner=os.getuid(),
            )

            manager._verify_installation()

            (installation / "extension.js").unlink()
            with self.assertRaisesRegex(RuntimeError, "payload is unavailable"):
                manager._verify_installation()

    def test_missing_home_refuses_activation_and_retries_after_restoration(self):
        account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
                                  pw_dir="unused")
        state = GnomeRecoveryState()
        state.values[DISABLE_ALL_KEY] = False
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            manager = ExtensionManager(runtime_root=Path(directory) / "missing-runtime")
            with (
                mock.patch.object(manager, "_account", return_value=(account, home)),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(manager, "_shell_is_available", return_value=False),
                mock.patch.object(manager, "_run_command", side_effect=state.run),
            ):
                with self.assertRaisesRegex(ChildExtensionUnavailable, "home directory is unavailable") as failure:
                    manager.set_enabled(account.pw_uid, True, recover_global_switch=True)
                self.assertIsInstance(failure.exception.__cause__, RuntimeError)
                self.assertIn("unsafe ownership", failure.exception.__cause__.args[0])
                self.assertEqual(state.commands, [])
                home.mkdir()
                manager.set_enabled(account.pw_uid, True, recover_global_switch=True)
        self.assertIn(UUID, state.values[ENABLED_KEY])
        self.assertNotIn(UUID, state.values[DISABLED_KEY])

    def test_shared_payload_failure_is_not_isolated_by_an_unavailable_child(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(installation=Path(directory) / "missing-payload")
            with mock.patch.object(manager, "_account") as account:
                with self.assertRaisesRegex(RuntimeError, "payload is unavailable") as failure:
                    manager.set_enabled(1001, True, recover_global_switch=True)
            self.assertNotIsInstance(failure.exception, ChildExtensionUnavailable)
            account.assert_not_called()

    def test_enable_clears_explicit_disable_and_verifies_both_lists(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(manager, "_account", return_value=(account, home)),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list",
                    side_effect=[
                        ["existing@example.com"],
                        [UUID, "disabled@example.com"],
                        ["existing@example.com", UUID],
                        ["disabled@example.com"],
                    ],
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, True)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, DISABLED_KEY, ["disabled@example.com"]),
            mock.call(account, ENABLED_KEY, ["existing@example.com", UUID]),
        ])

    def test_live_enable_uses_gnome_cli_and_verifies_runtime_state(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list", side_effect=[[], [UUID], [UUID], []]
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(manager, "_failed_live_extension", return_value=False),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(False, False), (True, True)],
                ),
                mock.patch.object(manager, "_run_command") as run,
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, True)

        run.assert_called_once_with(
            account,
            ("gnome-extensions", "enable", "--quiet", UUID),
            require_live=True,
        )
        set_list.assert_not_called()

    def test_live_disable_uses_gnome_cli_and_verifies_inactive_state(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager()
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation") as verify,
                mock.patch.object(
                    manager, "_list", side_effect=[[UUID], [], [], [UUID]]
                ),
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(True, True), (False, False)],
                ),
                mock.patch.object(manager, "_run_command") as run,
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, False)

        run.assert_called_once_with(
            account,
            ("gnome-extensions", "disable", "--quiet", UUID),
            require_live=True,
        )
        verify.assert_not_called()
        set_list.assert_not_called()

    def test_live_transition_waits_for_settings_without_replaying_input(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                before = (["private@example.com"], [UUID]) if enabled else ([UUID], [])
                after = ([UUID], []) if enabled else ([], [UUID])
                with (
                    mock.patch.object(self.manager, "_run_command") as run,
                    mock.patch.object(self.manager, "_runtime_state",
                                      return_value=(enabled, enabled)) as runtime,
                    mock.patch.object(self.manager, "_list", side_effect=[*before, *after]) as read,
                    mock.patch.object(self.manager, "_set_list") as write,
                    mock.patch("oh_no_parent_control.extension_manager.time.sleep") as sleep,
                    self.assertLogs("onpc", "INFO") as logs,
                ):
                    self.manager._set_live(self.account, enabled)
                run.assert_called_once_with(self.account,
                    ("gnome-extensions", "enable" if enabled else "disable", "--quiet", UUID),
                    require_live=True)
                write.assert_not_called()
                sleep.assert_called_once_with(0.25)
                self.assertEqual(runtime.call_count, 2)
                for call in read.call_args_list[2:]:
                    self.assertGreater(call.kwargs["timeout"], 0)
                    self.assertLessEqual(call.kwargs["timeout"], 4)
                self.assertNotIn("private@example.com", "\n".join(logs.output))

    def test_runtime_change_during_settings_wait_is_rejected(self):
        with (
            mock.patch.object(self.manager, "_run_command"),
            mock.patch.object(self.manager, "_runtime_state",
                              side_effect=[(True, True), (True, False)]),
            mock.patch.object(self.manager, "_list", side_effect=[[], [UUID], [UUID], []]),
            mock.patch("oh_no_parent_control.extension_manager.time.sleep"),
            self.assertRaisesRegex(RuntimeError, "runtime verification failed"),
        ):
            self.manager._set_live(self.account, True)

    def test_persistent_live_settings_disagreement_rolls_back(self):
        clock = [0.0]
        account = SimpleNamespace(pw_uid=os.getuid())
        def sleep(delay):
            clock[0] += delay
        with (
            mock.patch.object(self.manager, "_account", return_value=(account, Path(self.runtime.name))),
            mock.patch.object(self.manager, "_shell_is_available", return_value=True),
            mock.patch.object(self.manager, "_runtime_state",
                              side_effect=[(True, True), (False, False), (True, True)]),
            mock.patch.object(self.manager, "_list",
                              side_effect=lambda _account, key, **_kw: [UUID] if key == ENABLED_KEY else []),
            mock.patch.object(self.manager, "_run_command") as run,
            mock.patch.object(self.manager, "_set_list") as write,
            mock.patch.object(self.manager, "_observe_disable_settings"),
            mock.patch.object(self.manager, "collect_diagnostics"),
            mock.patch("oh_no_parent_control.extension_manager.time.monotonic", side_effect=lambda: clock[0]),
            mock.patch("oh_no_parent_control.extension_manager.time.sleep", side_effect=sleep),
            self.assertRaisesRegex(RuntimeError, "activation verification failed"),
        ):
            self.manager.set_enabled(account.pw_uid, False)
        self.assertEqual(clock[0], 4)
        run.assert_called_once()
        self.assertEqual(write.call_args_list, [
            mock.call(account, ENABLED_KEY, [UUID]),
            mock.call(account, DISABLED_KEY, []),
        ])

    def test_disable_observations_preserve_failure_and_exclude_identifiers(self):
        for unavailable in (False, True):
            with self.subTest(unavailable=unavailable):
                values = [[UUID, "private@example.com"], [UUID]]
                values += ([RuntimeError("private-error")] if unavailable else
                           [["private@example.com"], [], [], []])
                with (
                    mock.patch.object(self.manager, "_run_command"),
                    mock.patch.object(self.manager, "_runtime_state", return_value=(False, False)),
                    mock.patch.object(self.manager, "_list", side_effect=values) as read,
                    mock.patch.object(self.manager, "_set_list") as write,
                    # Exhaust the persistence wait, then freeze time for the
                    # independent failure-only diagnostic observations.
                    mock.patch("oh_no_parent_control.extension_manager.time.monotonic",
                               side_effect=[0, 4, 4, 4, 4, 4, 4, 4, 4]),
                    mock.patch("oh_no_parent_control.extension_manager.time.sleep") as sleep,
                    self.assertLogs("onpc", "INFO") as logs,
                    self.assertRaisesRegex(RuntimeError, "activation verification failed"),
                ):
                    self.manager._set_live(self.account, False)
                write.assert_not_called()
                observations = [decode(record.onpc_payload) for record in logs.records]
                if not unavailable:
                    fields = [item["fields"] for item in observations
                              if item["event"] == "extension-manager.setting-observation"]
                    self.assertEqual(fields, [
                        {"key": key, "stage": stage, "present": False}
                        for stage in ("live-observation-1", "live-observation-2")
                        for key in (ENABLED_KEY, DISABLED_KEY)])
                    self.assertEqual(sleep.call_args_list, [mock.call(0.25), mock.call(1)])
                for call in read.call_args_list[2:]:
                    self.assertGreater(call.kwargs["timeout"], 0)
                    self.assertLessEqual(call.kwargs["timeout"], 4)
                self.assertNotIn("diagnostic.rejected", [item["event"] for item in observations])
                for secret in (UUID, "private@example.com", "private-error"):
                    self.assertNotIn(secret, "\n".join(logs.output))

    def test_live_enable_rejects_inactive_extension_and_rolls_back(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list", side_effect=[[], [], [], []]
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(False, False), (True, False), (False, False)],
                ),
                mock.patch.object(manager, "_run_command"),
                mock.patch.object(manager, "collect_diagnostics", side_effect=RuntimeError(
                    "private diagnostic failure")) as collect,
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                with self.assertRaisesRegex(
                        RuntimeError, "runtime verification failed"):
                    manager.set_enabled(account.pw_uid, True)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, []),
            mock.call(account, DISABLED_KEY, []),
        ])
        collect.assert_called_once_with((account.pw_uid,))

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_runtime_state_uses_cli_configured_and_active_filters(self, run):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=f"{UUID}\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout=f"{UUID}\n", stderr=""),
        ]
        manager = ExtensionManager()
        with mock.patch.object(
                manager, "_command",
                side_effect=lambda _account, arguments: (
                    list(arguments), {}, "live-session"
                )):
            self.assertEqual(manager._runtime_state(self.account), (True, True))

        self.assertEqual(run.call_args_list[0].args[0], [
            "gnome-extensions", "list", "--enabled", "--quiet",
        ])
        self.assertEqual(run.call_args_list[1].args[0], [
            "gnome-extensions", "list", "--active", "--quiet",
        ])

    def _recover(self, state, *, live, recover_global_switch=True, transaction=None):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            home = mock.Mock(wraps=Path(directory))
            home.stat.return_value = SimpleNamespace(
                st_uid=1001 if transaction is not None else account.pw_uid,
            )
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, home)
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(manager, "_shell_is_available", return_value=live),
                mock.patch.object(manager, "_run_command", side_effect=state.run),
            ):
                if transaction is not None:
                    return transaction(manager)
                return manager.set_enabled(account.pw_uid, True,
                                           recover_global_switch=recover_global_switch)

    def test_parent_first_enablement_recovers_global_switch(self):
        from tests.support.broker import make_broker, Preferences

        for live in (False, True):
            with self.subTest(live=live):
                state, preferences = GnomeRecoveryState(), Preferences()
                saved = self._recover(state, live=live, transaction=lambda manager:
                    make_broker(preferences=preferences, extensions=manager)
                    .set_parent_control(1003, 1001, True, 0))
                self.assertTrue(saved["parent_control_enabled"])
                self.assertFalse(state.values[DISABLE_ALL_KEY])
                self.assertIn(UUID, state.values[ENABLED_KEY])
                self.assertNotIn(UUID, state.values[DISABLED_KEY])

    def test_kiosk_grant_recovers_child_extension_live_and_offline(self):
        from tests.support.broker import make_broker, Accounts, Preferences

        for live in (False, True):
            with self.subTest(live=live):
                state, accounts, preferences = GnomeRecoveryState(), Accounts(), Preferences()
                preferences.values[1001]["parent_control_enabled"] = True
                original = preferences.load(1001)

                def grant(manager):
                    # Shell must see the new time balance when activation starts.
                    activate = manager.set_enabled

                    def enable(uid, enabled, **kwargs):
                        self.assertEqual(accounts.extension[1], 900)
                        return activate(uid, enabled, **kwargs)

                    with mock.patch.object(manager, "set_enabled", side_effect=enable):
                        return make_broker(accounts=accounts, preferences=preferences,
                                           extensions=manager).request_access(
                            991, ":1.2", 1001, 1003, 900, True)

                result = self._recover(state, live=live, transaction=grant)
                self.assertEqual(result[1], "approved")
                self.assertFalse(state.values[DISABLE_ALL_KEY])
                self.assertIn(UUID, state.values[ENABLED_KEY])
                self.assertNotIn(UUID, state.values[DISABLED_KEY])
                self.assertEqual(preferences.load(1001), original)

    def test_kiosk_failed_activation_restores_settings_and_grant(self):
        from tests.support.broker import make_broker, Accounts, Preferences
        from oh_no_parent_control.core import BackendFailure

        state, accounts, preferences = GnomeRecoveryState(inactive=True), Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True
        before = {key: value[:] if isinstance(value, list) else value
                  for key, value in state.values.items()}
        with self.assertRaises(BackendFailure):
            self._recover(state, live=True, transaction=lambda manager:
                make_broker(accounts=accounts, preferences=preferences, extensions=manager)
                .request_access(991, ":1.2", 1001, 1003, 900, True))
        self.assertEqual(state.values, before)
        self.assertEqual(accounts.extension, (1, 2))
        self.assertEqual(accounts.filter, (False, ("old.App",)))
        self.assertEqual(accounts.daily_limit, 3600)
        self.assertEqual(accounts.limit_type, 2)

    def test_kiosk_failed_activation_after_termination_keeps_strict_filter(self):
        from tests.support.broker import make_broker, Accounts, Preferences, RunningApps
        from oh_no_parent_control.core import BackendFailure

        state, accounts, preferences = GnomeRecoveryState(inactive=True), Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True
        broker = None

        def grant(manager):
            nonlocal broker
            broker = make_broker(accounts=accounts, preferences=preferences, extensions=manager,
                                 running_apps=RunningApps(terminated=1))
            return broker.request_access(991, ":1.2", 1001, 1003, 900, False)

        with self.assertRaises(BackendFailure):
            self._recover(state, live=True, transaction=grant)
        self.assertTrue(state.values[DISABLE_ALL_KEY])
        self.assertEqual(accounts.extension, (1, 2))
        self.assertEqual(accounts.filter, (False, ("/usr/bin/game", "org.example.Game")))
        self.assertEqual(broker._last_request, {})

    def test_parent_failure_restores_global_switch_and_exact_extension_lists(self):
        from tests.support.broker import make_broker, Accounts, Preferences
        from oh_no_parent_control.core import BackendFailure

        for live in (False, True):
            for failure in ("account", "preferences"):
                with self.subTest(live=live, failure=failure):
                    state = GnomeRecoveryState()
                    before = {key: value[:] if isinstance(value, list) else value
                              for key, value in state.values.items()}
                    accounts, preferences = Accounts(), Preferences()
                    original = preferences.load(1001)
                    if failure == "account":
                        set_limit_type = accounts.set_limit_type

                        def fail_once(uid, value):
                            accounts.set_limit_type = set_limit_type
                            raise RuntimeError("injected account write failure")

                        accounts.set_limit_type = fail_once
                    else:
                        save = preferences.save

                        def fail_after_save(uid, value):
                            result = save(uid, value)
                            if value["parent_control_enabled"]:
                                raise RuntimeError("injected post-save failure")
                            return result

                        preferences.save = fail_after_save
                    with self.assertRaises(BackendFailure):
                        self._recover(state, live=live, transaction=lambda manager:
                            make_broker(accounts=accounts, preferences=preferences,
                                        extensions=manager)
                            .set_parent_control(1003, 1001, True, 0))
                    self.assertEqual(state.values, before)
                    self.assertEqual(preferences.load(1001), original)
                    self.assertEqual(accounts.extension, (1, 2))
                    self.assertEqual(accounts.filter, (False, ("old.App",)))
                    self.assertEqual(accounts.daily_limit, 3600)
                    self.assertEqual(accounts.limit_type, 2)

    def test_parent_recovery_undo_failure_remains_rollback_failure(self):
        from tests.support.broker import make_broker, Accounts
        from oh_no_parent_control.core import RollbackFailure

        state, accounts = GnomeRecoveryState(rollback_failure=True), Accounts()
        set_daily_limit = accounts.set_daily_limit

        def fail_once(uid, value):
            accounts.set_daily_limit = set_daily_limit
            raise RuntimeError("injected write failure")

        accounts.set_daily_limit = fail_once
        with self.assertRaises(RollbackFailure) as raised:
            self._recover(state, live=False, transaction=lambda manager:
                make_broker(accounts=accounts, extensions=manager)
                .set_parent_control(1003, 1001, True, 0))
        self.assertEqual(str(raised.exception.__cause__),
                         "child GNOME extension rollback could not be verified")
        self.assertEqual(accounts.daily_limit, 3600)
        self.assertEqual(accounts.limit_type, 2)
        self.assertEqual(state.values[ENABLED_KEY], ["other-enabled@example.com"])
        self.assertEqual(state.values[DISABLED_KEY], [UUID, "other-disabled@example.com"])

    def test_parent_recovery_undo_runs_after_account_rollback_failure(self):
        from tests.support.broker import make_broker, Accounts
        from oh_no_parent_control.core import RollbackFailure

        state, accounts = GnomeRecoveryState(), Accounts()
        before = {key: value[:] if isinstance(value, list) else value
                  for key, value in state.values.items()}
        accounts.set_daily_limit = mock.Mock(side_effect=RuntimeError("injected write failure"))
        with self.assertRaises(RollbackFailure):
            self._recover(state, live=False, transaction=lambda manager:
                make_broker(accounts=accounts, extensions=manager)
                .set_parent_control(1003, 1001, True, 0))
        self.assertEqual(state.values, before)

    def test_disabled_global_switch_recovers_live_and_offline(self):
        for live in (False, True):
            with self.subTest(live=live):
                state = GnomeRecoveryState()
                with self.assertLogs("onpc", "INFO") as logs:
                    self._recover(state, live=live)
                self.assertEqual(state.values, {
                    ENABLED_KEY: ["other-enabled@example.com", UUID],
                    DISABLED_KEY: ["other-disabled@example.com"],
                    DISABLE_ALL_KEY: False,
                })
                self.assertTrue(any("recovery outcome=accepted" in row for row in logs.output))

    def test_preference_transaction_does_not_change_global_switch(self):
        state = GnomeRecoveryState()
        with self.assertRaisesRegex(RuntimeError, "user extensions are disabled"):
            self._recover(state, live=True, recover_global_switch=False)
        self.assertTrue(state.values[DISABLE_ALL_KEY])
        self.assertTrue(all(args[1] == "get" for args in state.commands))

    def test_recovery_of_previously_enabled_extension_is_idempotent(self):
        for live in (False, True):
            with self.subTest(live=live):
                state = GnomeRecoveryState()
                state.values[ENABLED_KEY].append(UUID)
                state.values[DISABLED_KEY].remove(UUID)
                self._recover(state, live=live)
                state.commands.clear()
                self._recover(state, live=live)
                self.assertFalse(state.values[DISABLE_ALL_KEY])
                self.assertEqual(state.values[ENABLED_KEY].count(UUID), 1)
                self.assertFalse(any(args[:2] == ("gsettings", "set") or
                                     args[:2] == ("gnome-extensions", "enable")
                                     for args in state.commands))

    def test_failed_recovery_restores_switch_and_individual_extension_choices(self):
        state = GnomeRecoveryState(inactive=True)
        before = {key: value[:] if isinstance(value, list) else value
                  for key, value in state.values.items()}
        with self.assertRaisesRegex(RuntimeError, "runtime verification failed"):
            self._recover(state, live=True)
        self.assertEqual(state.values, before)

    def test_global_switch_recovery_requires_successful_readback(self):
        state = GnomeRecoveryState(ignore_switch=True)
        with self.assertRaisesRegex(RuntimeError, "switch verification failed"):
            self._recover(state, live=False)
        self.assertTrue(state.values[DISABLE_ALL_KEY])
        self.assertNotIn(UUID, state.values[ENABLED_KEY])

    def test_failed_global_switch_rollback_is_reported_without_command_details(self):
        state = GnomeRecoveryState(inactive=True, rollback_failure=True)
        with self.assertLogs("onpc", "WARNING") as logs:
            with self.assertRaisesRegex(RuntimeError, "rollback could not be verified"):
                self._recover(state, live=True)
        self.assertIn("rollback-failed", logs.output[-1])
        faults = [decode(record.onpc_payload) for record in logs.records
                  if decode(record.onpc_payload)["event"] == "runtime.fault"]
        self.assertEqual(len(faults), 2)
        self.assertTrue(all(item["fields"]["source"] == "extension-manager"
                            and item["fields"]["line"] > 0 for item in faults))
        self.assertNotEqual(faults[0]["fields"]["line"], faults[1]["fields"]["line"])
        self.assertNotIn("private-command-canary", "\n".join(logs.output))
        self.assertNotIn(UUID, state.values[ENABLED_KEY])
        self.assertIn(UUID, state.values[DISABLED_KEY])

    def test_disable_does_not_require_the_packaged_payload(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation") as verify,
                mock.patch.object(
                    manager, "_list",
                    side_effect=[[UUID], [UUID], [], []],
                ),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, False)

        verify.assert_not_called()
        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, []),
            mock.call(account, DISABLED_KEY, []),
        ])

    def test_remove_clears_both_extension_lists_offline(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(
                    manager, "_list",
                    side_effect=[
                        ["existing@example.com", UUID],
                        [UUID, "disabled@example.com"],
                        ["existing@example.com"],
                        ["disabled@example.com"],
                    ],
                ),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.remove(account.pw_uid)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, ["existing@example.com"]),
            mock.call(account, DISABLED_KEY, ["disabled@example.com"]),
        ])

    def test_remove_does_not_disable_an_already_inactive_live_extension(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager()
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(False, False), (False, False)],
                ),
                mock.patch.object(manager, "_list", side_effect=[[], [], [], []]),
                mock.patch.object(manager, "_set_live") as set_live,
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.remove(account.pw_uid)

        set_live.assert_not_called()
        set_list.assert_not_called()

    def test_activation_readback_failure_restores_original_settings(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list", side_effect=[[], [], [], [], []]
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                with self.assertRaisesRegex(
                        RuntimeError, "activation verification failed"):
                    manager.set_enabled(account.pw_uid, True)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, [UUID]),
            mock.call(account, ENABLED_KEY, []),
            mock.call(account, DISABLED_KEY, []),
        ])


if __name__ == "__main__":
    unittest.main()
