import unittest
import json
import pytest
from unittest import mock
import xml.etree.ElementTree as ElementTree
from io import BytesIO
from zipfile import ZipFile

from common.oh_no_parent_control_ui.diagnostic_bundle import validate_bundle
from common.oh_no_parent_control_ui.diagnostic_events import encode, event
from oh_no_parent_control.logs import DailyLogWriter
from oh_no_parent_control.core import AccessDenied

from oh_no_parent_control.service import INTROSPECTION_XML, Service
from common.oh_no_parent_control_ui.reboot import product_reboot_required


from tests.support.paths import ROOT


def test_notification_dispatch_uses_bus_uid_and_rejects_duplicate_or_oversized_json():
    from oh_no_parent_control.service import GLib
    service = Service.__new__(Service)
    service.credentials = mock.Mock()
    service.credentials.uid.return_value = 1001
    service.broker = mock.Mock()
    settings = {"show_in_fullscreen": True, "reminders": []}
    service.broker.get_own_notifications.return_value = settings
    service.broker.set_own_notifications.return_value = settings
    invocation = mock.Mock()
    for method in ("GetOwnNotifications", "SetOwnNotifications"):
        params = GLib.Variant("()", ()) if method.startswith("Get") else GLib.Variant("(s)", (json.dumps(settings),))
        service._method_call(None, ":1.42", None, None, method, params, invocation)
        assert json.loads(invocation.return_value.call_args.args[0].unpack()[0]) == settings
    service.broker.get_own_notifications.assert_called_once_with(1001)
    service.broker.set_own_notifications.assert_called_once_with(1001, settings)
    service.broker.set_own_notifications.reset_mock()
    for encoded in ('{', '{"reminders": [], "reminders": []}', ' ' * (512 * 1024 + 1)):
        refused = mock.Mock()
        service._method_call(None, ":1.42", None, None, "SetOwnNotifications",
                             GLib.Variant("(s)", (encoded,)), refused)
        assert refused.return_dbus_error.call_args.args[0].endswith(".InvalidRequest")
        refused.return_value.assert_not_called()
    service.broker.set_own_notifications.assert_not_called()
    # The runner may raise Python's recursion limit. Exercise the decoder's
    # refusal deterministically rather than assuming a particular nesting limit.
    with mock.patch("oh_no_parent_control.service.decode_preferences", side_effect=RecursionError):
        refused = mock.Mock()
        service._method_call(None, ":1.42", None, None, "SetOwnNotifications",
                             GLib.Variant("(s)", ("[]",)), refused)
        assert refused.return_dbus_error.call_args.args[0].endswith(".InvalidRequest")
        refused.return_value.assert_not_called()
    service.broker.set_own_notifications.assert_not_called()


def test_notification_dbus_contract_has_no_target_uid():
    assert signatures(INTROSPECTION_XML)["GetOwnSessionAllowsSoftApps"] == (("allow_soft_blocked_apps", "b", "out"),)
    assert signatures(INTROSPECTION_XML)["GetOwnNotifications"] == (("notifications_json", "s", "out"),)
    assert signatures(INTROSPECTION_XML)["SetOwnNotifications"] == (
        ("notifications_json", "s", "in"), ("saved_notifications_json", "s", "out"))


def test_kiosk_notification_dispatch_preserves_caller_target_and_json_guards():
    from oh_no_parent_control.service import GLib
    service = Service.__new__(Service)
    service.credentials = mock.Mock()
    service.credentials.uid.return_value = 991
    service.broker = mock.Mock()
    settings = {'show_in_fullscreen': False, 'reminders': []}
    service.broker.get_child_notifications.return_value = settings
    service.broker.set_child_notifications.return_value = settings
    for method, params in (
            ('GetChildNotifications', GLib.Variant('(u)', (1001,))),
            ('SetChildNotifications', GLib.Variant('(us)', (1001, json.dumps(settings))))):
        invocation = mock.Mock()
        service._method_call(None, ':1.42', None, None, method, params, invocation)
        assert json.loads(invocation.return_value.call_args.args[0].unpack()[0]) == settings
    service.broker.get_child_notifications.assert_called_once_with(991, 1001)
    service.broker.set_child_notifications.assert_called_once_with(991, 1001, settings)
    service.broker.set_child_notifications.reset_mock()
    for encoded in ('{', '{"reminders": [], "reminders": []}', ' ' * (512 * 1024 + 1)):
        invocation = mock.Mock()
        service._method_call(None, ':1.42', None, None, 'SetChildNotifications',
                             GLib.Variant('(us)', (1001, encoded)), invocation)
        assert invocation.return_dbus_error.call_args.args[0].endswith('.InvalidRequest')
    service.broker.set_child_notifications.assert_not_called()


def test_session_soft_apps_dispatch_uses_authenticated_caller():
    from oh_no_parent_control.service import GLib
    service = Service.__new__(Service)
    service.credentials = mock.Mock()
    service.credentials.uid.return_value = 1001
    service.broker = mock.Mock()
    service.broker.get_own_session_allows_soft_apps.return_value = True
    invocation = mock.Mock()
    service._method_call(None, ":1.42", None, None, "GetOwnSessionAllowsSoftApps",
                         GLib.Variant("()", ()), invocation)
    service.broker.get_own_session_allows_soft_apps.assert_called_once_with(1001)
    assert invocation.return_value.call_args.args[0].unpack() == (True,)


@pytest.mark.parametrize('permissive', [False, True])
def test_production_policy_uses_only_validated_original_permissive_mode(permissive):
    from oh_no_parent_control import service as runtime
    with (mock.patch.object(runtime, 'originally_permissive_policy', return_value=permissive) as mode,
          mock.patch.object(runtime, 'FapolicydPolicy') as policy,
          mock.patch.object(runtime, 'AccountsService'),
          mock.patch.object(runtime, 'CallerCredentials'),
          mock.patch.object(runtime, 'PolkitAuthorizer'),
          mock.patch.object(runtime, 'PreferenceStore'),
          mock.patch.object(runtime, 'ExtensionManager'),
          mock.patch.object(runtime, 'TimerUsage'),
          mock.patch.object(runtime, 'RunningAppTerminator')):
        runtime.production_dependencies(mock.Mock())
    mode.assert_called_once_with()
    policy.assert_called_once_with(tolerate_rule_errors=True, early_pattern_guards=permissive)


@pytest.mark.parametrize('markers, expected', (
    ({}, False),
    ({'reboot-required': ''}, False),
    ({'reboot-required': '', 'reboot-required.pkgs': 'linux-image-generic\nlibc6\n'}, False),
    ({'reboot-required.pkgs': 'oh-no-parent-control\n'}, False),
    ({'reboot-required': '', 'reboot-required.pkgs': 'oh-no-parent-control\n'}, True),
    ({'reboot-required': '', 'reboot-required.pkgs': 'libc6\noh-no-parent-control\nlinux-base\n'}, True),
    ({'reboot-required': '', 'reboot-required.pkgs': 'oh-no-parent-control'}, True),
    ({'reboot-required': '', 'reboot-required.pkgs': 'oh-no-parent-control-extra\n'}, False),
    ({'reboot-required': '', 'reboot-required.pkgs': 'other-oh-no-parent-control\n'}, False),
    ({'reboot-required': '', 'reboot-required.pkgs': ' oh-no-parent-control\n'}, False),
    ({'reboot-required': '', 'reboot-required.pkgs': b'\xff'}, False),
    ({'oh-no-parent-control-reboot-required': 'reboot\n'}, True),
    ({'oh-no-parent-control-child-trust-reboot': ''}, True),
), ids=('no-reboot', 'unattributed-reboot', 'unrelated-reboot', 'orphan-package-list',
        'fresh-install', 'mixed-packages', 'no-final-newline', 'package-suffix',
        'package-prefix', 'whitespace', 'invalid-package-list', 'fedora', 'trust-upgrade'))
def test_shared_product_reboot_detection_selects_broker_startup(tmp_path, markers, expected):
    from oh_no_parent_control import service as runtime
    for name, contents in markers.items():
        path = tmp_path / name
        path.write_bytes(contents if isinstance(contents, bytes) else contents.encode())
    assert product_reboot_required(tmp_path) is expected
    # Exercise both service entry paths through main, retaining the launcher's
    # early trust gate even if package markers have not yet been written.
    for early_guard in (False, True):
        connection = mock.Mock()

        def acquire(_bus, _name, _flags, acquired, *_callbacks):
            acquired(connection, runtime.BUS_NAME)
            return 42

        with (mock.patch.object(runtime.os, 'geteuid', return_value=0),
              mock.patch.object(runtime, 'product_reboot_required',
                                side_effect=lambda: product_reboot_required(tmp_path)),
              mock.patch.object(runtime, 'DailyLogWriter') as writer,
              mock.patch.object(runtime, 'configure_broker_logging'),
              mock.patch.object(runtime, 'log_version'),
              mock.patch.object(runtime.GLib, 'MainLoop'),
              mock.patch.object(runtime.GLib, 'unix_signal_add'),
              mock.patch.object(runtime.Gio, 'bus_own_name', side_effect=acquire),
              mock.patch.object(runtime.Gio, 'bus_unown_name') as release,
              mock.patch.object(runtime, 'Service') as service):
            assert runtime.main(diagnostics_only=early_guard) == 0
            service.assert_called_once_with(connection, writer.return_value,
                                            diagnostics_only=early_guard or expected)
            service.return_value.register.assert_called_once_with()
            service.return_value.close.assert_called_once_with()
            release.assert_called_once_with(42)
    # Boot-scoped requests disappearing must restore normal operation.
    for name in markers:
        (tmp_path / name).unlink()
    assert product_reboot_required(tmp_path) is False


def test_public_method_diagnostics_preserve_only_registered_method_names():
    for event_id in ('service.006', 'service.007', 'service.008', 'service.009', 'service.010'):
        for method in (*signatures(INTROSPECTION_XML), 'private-unrecognized-method'):
            values = {'method': method}
            if event_id in ('service.009', 'service.010'):
                values['error_type'] = 'AccessDenied'
            diagnostic = event(event_id, values, normalize=True)
            assert diagnostic['fields']['method'] == (
                'other' if method == 'private-unrecognized-method' else method)


def test_reboot_diagnostics_mode_never_starts_or_dispatches_policy(tmp_path):
    from oh_no_parent_control.service import GLib, BUS_NAME
    dependencies = mock.Mock()
    dependencies.credentials.uid.return_value = 1000
    connection = mock.Mock()
    service = Service(connection, DailyLogWriter(tmp_path),
                      dependencies=dependencies, diagnostics_only=True)
    service.register()
    assert service._policy_rescan_thread is None
    connection.signal_subscribe.assert_not_called()
    dependencies.accounts.sync_execution_policy.assert_not_called()
    service.broker.refresh_enabled_extensions.assert_not_called()
    service.broker.clear_live_session_runtime_caps.assert_not_called()
    service.broker.reset_mock()
    for method in signatures(INTROSPECTION_XML).keys() - {
            'LogEvent', 'ExportDiagnosticLogs', 'ListKioskUsers', 'GetChildLanguageContext'}:
        invocation = mock.Mock()
        service._method_call(None, ':1.42', None, None, method,
                             GLib.Variant('()', ()), invocation)
        invocation.return_value.assert_not_called()
        invocation.return_dbus_error.assert_called_once_with(
            BUS_NAME + '.Error.RebootRequired', 'product activation requires a reboot')
    assert not service.broker.mock_calls
    service.close()
    connection.signal_unsubscribe.assert_not_called()
    connection.unregister_object.assert_called_once()


def test_reboot_mode_collects_real_report_and_rechecks_role(tmp_path):
    from oh_no_parent_control.service import GLib, BUS_NAME
    dependencies = mock.Mock()
    dependencies.credentials.uid.return_value = 1000
    writer = DailyLogWriter(tmp_path)
    service = Service(mock.Mock(), writer, dependencies=dependencies, diagnostics_only=True)
    # History from the previous broker remains available, and frontends can
    # record their startup/feedback failures while policy is unavailable.
    writer.write('broker', 'INFO', encode(event('runtime.version', {'version': '1.2'})))
    logged = mock.Mock()
    service._method_call(None, ':1.42', None, None, 'LogEvent',
        GLib.Variant('(sss)', ('parent', 'WARNING', encode(event('parent.021')))), logged)
    logged.return_value.assert_called_once_with(None)
    service.broker.authorize_log_component.assert_called_once_with(1000, 'parent')
    service._health_snapshot = mock.Mock(return_value={})
    for revoke in (False, True):
        service.broker.authorize_diagnostic_export.side_effect = (
            [None, AccessDenied('denied')] if revoke else None)
        invocation = mock.Mock()
        with (mock.patch('oh_no_parent_control.service.threading.Thread') as thread,
              mock.patch('oh_no_parent_control.service.GLib.idle_add') as idle):
            service._method_call(None, ':1.42', None, None, 'ExportDiagnosticLogs',
                                 None, invocation)
            thread.assert_called_once()
            service._export_logs_worker(invocation, 1000)
        callback, reply, uid, data = idle.call_args.args
        validate_bundle(data)
        with ZipFile(BytesIO(data)) as archive:
            text = ''.join(archive.read(name).decode() for name in archive.namelist())
        assert 'version=1.2' in text
        assert 'parent.021' in text
        callback(reply, uid, data)
        assert not service._diagnostic_export_lock.locked()
        if revoke:
            invocation.return_value.assert_not_called()
            invocation.return_dbus_error.assert_called_once_with(
                BUS_NAME + '.Error.AccessDenied', 'denied')
        else:
            invocation.return_dbus_error.assert_not_called()
            invocation.return_value.assert_called_once()
    service.broker.collect_extension_diagnostics.assert_not_called()
    service.close()


def test_reboot_mode_production_graph_has_no_enforcement_adapters(tmp_path):
    with (mock.patch('oh_no_parent_control.service.production_dependencies') as production,
          mock.patch('oh_no_parent_control.service.CallerCredentials'),
          mock.patch('oh_no_parent_control.service.AccountsService') as accounts):
        service = Service(mock.Mock(), DailyLogWriter(tmp_path), diagnostics_only=True)
    production.assert_not_called()
    assert service.broker._accounts is accounts.return_value
    from oh_no_parent_control.preferences import PreferenceStore
    assert isinstance(service.broker._preferences, PreferenceStore)
    assert service.broker._extensions is None
    assert service.broker._running_apps is None
    service.close()


def test_reboot_mode_dispatches_only_role_checked_kiosk_presentation_reads(tmp_path):
    from oh_no_parent_control.service import GLib
    from tests.support.broker import Accounts
    dependencies = mock.Mock()
    dependencies.credentials.uid.return_value = 991
    service = Service(mock.Mock(), DailyLogWriter(tmp_path), dependencies=dependencies,
                      diagnostics_only=True)
    service.broker.list_kiosk_users.return_value = (Accounts().users[1001],)
    service.broker.get_child_language_context.return_value = ('', 'zh_CN.UTF-8')
    for method, parameters, expected in (
            ('ListKioskUsers', None, ([(1001, 'Child', '')],)),
            ('GetChildLanguageContext', GLib.Variant('(u)', (1001,)), ('', 'zh_CN.UTF-8'))):
        invocation = mock.Mock()
        service._method_call(None, ':1.42', None, None, method, parameters, invocation)
        assert invocation.return_value.call_args.args[0].unpack() == expected
    service.broker.list_kiosk_users.assert_called_once_with(991)
    service.broker.get_child_language_context.assert_called_once_with(991, 1001)
    service.broker.get_child_language_context.side_effect = AccessDenied('denied')
    invocation = mock.Mock()
    service._method_call(None, ':1.42', None, None, 'GetChildLanguageContext',
                         GLib.Variant('(u)', (1001,)), invocation)
    invocation.return_value.assert_not_called()
    assert invocation.return_dbus_error.call_args.args[0].endswith('.Error.AccessDenied')
    service.close()


def signatures(xml):
    interface = ElementTree.fromstring(xml).find("interface")
    return {
        method.attrib["name"]: tuple(
            (argument.attrib["name"], argument.attrib["type"],
             argument.attrib.get("direction", "in"))
            for argument in method.findall("arg")
        )
        for method in interface.findall("method")
    }


class ServiceContractTests(unittest.TestCase):
    def test_child_language_dispatch_passes_authenticated_caller_and_target(self):
        service = Service.__new__(Service)
        service.credentials = mock.Mock()
        service.credentials.uid.return_value = 991
        service.broker = mock.Mock()
        service.broker.get_child_language.return_value = 'de'
        service.broker.set_child_language.return_value = 'fr'
        from oh_no_parent_control.service import GLib
        invocation = mock.Mock()
        service._method_call(None, ':1.42', None, None, 'GetChildLanguage',
                            GLib.Variant('(u)', (1001,)), invocation)
        service.broker.get_child_language.assert_called_once_with(991, 1001)
        self.assertEqual(invocation.return_value.call_args.args[0].unpack(), ('de',))
        service._method_call(None, ':1.42', None, None, 'SetChildLanguage',
                            GLib.Variant('(us)', (1001, 'fr')), invocation)
        service.broker.set_child_language.assert_called_once_with(991, 1001, 'fr')
        self.assertEqual(invocation.return_value.call_args.args[0].unpack(), ('fr',))

    def test_language_contract_never_accepts_target_identity(self):
        self.assertEqual(signatures(INTROSPECTION_XML)["GetOwnLanguage"],
                         (("language", "s", "out"),))
        self.assertEqual(signatures(INTROSPECTION_XML)["SetOwnLanguage"],
                         (("language", "s", "in"), ("saved_language", "s", "out")))

    def test_language_dispatch_uses_bus_credentials(self):
        service = Service.__new__(Service)
        service.credentials = mock.Mock()
        service.credentials.uid.return_value = 1001
        service.broker = mock.Mock()
        service.broker.get_own_language.return_value = "fr"
        service.broker.set_own_language.return_value = "de"
        from oh_no_parent_control.service import GLib
        invocation = mock.Mock()
        service._method_call(None, ":1.42", None, None, "GetOwnLanguage",
                             GLib.Variant("()", ()), invocation)
        service.broker.get_own_language.assert_called_once_with(1001)
        self.assertEqual(invocation.return_value.call_args.args[0].unpack(), ("fr",))
        service._method_call(None, ":1.42", None, None, "SetOwnLanguage",
                             GLib.Variant("(s)", ("de",)), invocation)
        service.broker.set_own_language.assert_called_once_with(1001, "de")
        self.assertEqual(invocation.return_value.call_args.args[0].unpack(), ("de",))

    def test_export_collects_extension_evidence_before_snapshot_and_survives_failure(self):
        service = Service.__new__(Service)
        service.broker = mock.Mock()
        service.log_writer = mock.Mock()
        service._health_snapshot = mock.Mock(return_value={})
        order = []
        service.broker.collect_extension_diagnostics.side_effect = lambda: order.append("observe")
        service.log_writer.snapshot.side_effect = lambda **_kwargs: order.append("snapshot") or b"report"
        with mock.patch("oh_no_parent_control.service.GLib.idle_add") as reply:
            service._export_logs_worker(None, 0)
        self.assertEqual(order, ["observe", "snapshot"])
        self.assertEqual(reply.call_args.args[3], b"report")
        service.broker.collect_extension_diagnostics.side_effect = RuntimeError("private@example.test")
        with (mock.patch("oh_no_parent_control.service.GLib.idle_add") as reply,
              self.assertLogs("onpc", "WARNING") as logs):
            service._export_logs_worker(None, 0)
        self.assertEqual(reply.call_args.args[3], b"report")
        self.assertNotIn("private", "\n".join(logs.output))

    def test_service_uses_current_binding_friendly_registration_api(self):
        source = (
            ROOT / "broker/oh_no_parent_control/service.py"
        ).read_text(encoding="utf-8")

        self.assertIn("register_object_with_closures2", source)

    def test_embedded_and_installed_dbus_contracts_match(self):
        canonical = (
            ROOT / "data/dbus-1/com.puffyslippers.OhNoParentControl1.xml"
        ).read_text(encoding="utf-8")

        self.assertEqual(signatures(INTROSPECTION_XML), signatures(canonical))

    def test_own_request_derives_target_from_caller(self):
        method = signatures(INTROSPECTION_XML)["RequestOwnAccess"]

        self.assertEqual(method, (
            ("approver_uid", "u", "in"),
            ("duration_seconds", "u", "in"),
            ("allow_soft_blocked_apps", "b", "in"),
            ("correlation_id", "s", "out"),
            ("result_code", "s", "out"),
            ("granted_duration_seconds", "u", "out"),
        ))
        self.assertNotIn("target_uid", [name for name, _type, _direction in method])

    def test_session_preparation_derives_target_from_child_caller(self):
        self.assertEqual(
            signatures(INTROSPECTION_XML)["PrepareOwnSession"],
            (("reconciled", "b", "out"),),
        )

    def test_diagnostic_export_accepts_no_path_or_identity_from_client(self):
        self.assertEqual(
            signatures(INTROSPECTION_XML)["ExportDiagnosticLogs"],
            (("archive", "ay", "out"),),
        )

    def test_user_lists_include_the_accounts_service_icon_file(self):
        self.assertEqual(
            signatures(INTROSPECTION_XML)["ListManagedUsers"],
            (("users", "a(uss)", "out"),),
        )
        self.assertEqual(
            signatures(INTROSPECTION_XML)["ListApprovers"],
            (("users", "a(uss)", "out"),),
        )

    def test_own_account_and_mute_are_explicit_child_overlay_contracts(self):
        self.assertEqual(
            signatures(INTROSPECTION_XML)["GetOwnAccount"],
            (
                ("uid", "u", "out"),
                ("label", "s", "out"),
                ("icon_file", "s", "out"),
            ),
        )
        self.assertEqual(
            signatures(INTROSPECTION_XML)["SetRequestMuted"],
            (
                ("target_uid", "u", "in"),
                ("surface", "s", "in"),
                ("muted", "b", "in"),
                ("saved_json", "s", "out"),
            ),
        )
        self.assertEqual(
            signatures(INTROSPECTION_XML)["UpdateRequestPreferences"],
            (
                ("target_uid", "u", "in"),
                ("selected_duration", "s", "in"),
                ("custom_minutes", "d", "in"),
                ("allow_soft_blocked_apps", "b", "in"),
                ("last_selected_approver_uid", "u", "in"),
                ("saved_json", "s", "out"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
