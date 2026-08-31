import unittest

from parent.oh_no_parent_control_parent.main import ParentWindow


class FakeDropDown:
    def __init__(self, owner):
        self.owner = owner
        self.blocked = False

    def handler_block(self, _handler):
        self.blocked = True

    def handler_unblock(self, _handler):
        self.blocked = False

    def set_model(self, _model):
        if not self.blocked:
            self.owner._account_changed()

    def set_selected(self, _index):
        if not self.blocked:
            self.owner._account_changed()


class ParentWindowHarness:
    _users_loaded = ParentWindow._users_loaded
    _account_changed = ParentWindow._account_changed

    def __init__(self):
        self._users = []
        self._account_changed_handler = 1
        self._account = FakeDropDown(self)
        self.load_count = 0
        self.toasts = []

    def _load_selected(self):
        self.load_count += 1

    def _toast(self, message):
        self.toasts.append(message)


class ParentWindowTests(unittest.TestCase):
    def test_loading_users_loads_initial_selection_once(self):
        window = ParentWindowHarness()

        window._users_loaded([(1001, "Child")])

        self.assertEqual(window.load_count, 1)

    def test_loading_no_users_does_not_load_preferences(self):
        window = ParentWindowHarness()

        window._users_loaded([])

        self.assertEqual(window.load_count, 0)
        self.assertEqual(window.toasts, ["No interactive non-admin users were found"])


if __name__ == "__main__":
    unittest.main()
