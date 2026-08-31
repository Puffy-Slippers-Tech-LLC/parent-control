import unittest

from oh_no_parent_control_app.model import RequestState, public_error


class AppModelTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
