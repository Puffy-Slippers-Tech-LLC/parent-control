import unittest

from oh_no_parent_control_kiosk.model import RequestState, public_error


class KioskModelTests(unittest.TestCase):
    def test_single_flight(self):
        state = RequestState()
        self.assertTrue(state.begin())
        self.assertFalse(state.begin())
        state.finish()
        self.assertTrue(state.begin())

    def test_errors_are_redacted(self):
        title, detail = public_error(RuntimeError("org.example.Secret /private/path"))
        self.assertNotIn("org.example", title + detail)
        self.assertNotIn("/private", title + detail)
        self.assertIn("return to login", detail)
        overlay_title, overlay_detail = public_error(
            RuntimeError("org.example.Secret /private/path"), child_overlay=True,
        )
        self.assertNotIn("org.example", overlay_title + overlay_detail)
        self.assertNotIn("return to login", overlay_detail)


if __name__ == "__main__":
    unittest.main()
