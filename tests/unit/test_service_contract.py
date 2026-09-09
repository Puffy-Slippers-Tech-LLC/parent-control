import unittest
import xml.etree.ElementTree as ElementTree

from oh_no_parent_control.service import INTROSPECTION_XML


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
