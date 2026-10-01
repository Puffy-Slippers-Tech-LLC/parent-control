import unittest
from unittest import mock
import xml.etree.ElementTree as ElementTree

from oh_no_parent_control.service import INTROSPECTION_XML, Service


from tests.support.paths import ROOT


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
