"""ID lookup must not silently degrade into geometry or label targeting."""

from types import SimpleNamespace
from unittest.mock import Mock
import warnings

import pytest

from tests.support.automation import Automation, AutomationError, public_action_name
from tests.support.paths import ROOT
from tests.e2e.accessible_ui import (
    AccessibleUI,
    EXTERNAL_PROVIDER_CONTRACTS,
    UiError,
    public_automation_id,
)


class Node:
    def __init__(self, identity, children=(), states=("showing", "visible", "sensitive")):
        self.identity = identity
        self.children = children
        self.states = set(states)
        self.action = SimpleNamespace(get_n_actions=lambda: 1, do_action=Mock(return_value=True))
        self.component = SimpleNamespace(scroll_to=Mock(return_value=True),
                                         grab_focus=Mock(return_value=True))
        self.text = SimpleNamespace(get_character_count=lambda: len(identity),
                                    get_text=lambda start, end: identity[start:end])

    def clear_cache_single(self): pass
    def get_accessible_id(self): return self.identity
    def get_attributes(self): return {}
    def get_role_name(self): return "panel"
    def get_name(self): return self.identity + " label"
    def get_child_count(self): return len(self.children)
    def get_child_at_index(self, index): return self.children[index]
    def get_state_set(self): return SimpleNamespace(contains=self.states.__contains__)
    def get_action_iface(self): return self.action
    def get_component_iface(self): return self.component
    def get_text_iface(self): return self.text


def adapter(root):
    return Automation(SimpleNamespace(
        Action=SimpleNamespace(get_action_name=lambda interface, index:
                               interface.get_action_name(index)),
        Text=SimpleNamespace(get_text=lambda interface, start, end:
                             interface.get_text(start, end)),
        StateType=SimpleNamespace(SHOWING="showing", VISIBLE="visible",
                                  SENSITIVE="sensitive", DEFUNCT="defunct",
                                  FOCUSED="focused"),
        ScrollType=SimpleNamespace(ANYWHERE="anywhere")), lambda: root)


def test_id_is_independent_of_order_and_unnamed_containers():
    target = Node("submit")
    root = Node("", [Node("decoration"), Node("", [target])])
    ui = adapter(root)
    assert ui.target("submit") is target
    root.children.reverse()
    assert ui.target("submit") is target


def test_missing_and_duplicate_ids_refuse_input():
    ui = adapter(Node("", [Node("submit"), Node("submit")]))
    with pytest.raises(AutomationError, match="ambiguous-id"):
        ui.activate("submit")
    with pytest.raises(AutomationError, match="missing-public-id"):
        ui.activate("cancel")


def test_find_all_supports_explicit_cardinality_checks():
    first = Node("surface")
    second = Node("surface")
    assert set(adapter(Node("", [first, second])).find_all("surface")) == {first, second}


def test_reveal_reacquires_and_does_not_activate_hidden_control():
    hidden = Node("submit", states=("visible", "sensitive"))
    ui = adapter(Node("", [hidden]))
    with pytest.raises(AutomationError, match="unreachable"):
        ui.activate("submit")
    hidden.component.scroll_to.assert_called_once_with("anywhere")
    hidden.action.do_action.assert_not_called()


def test_reveal_uses_fresh_replacement_after_scrolling():
    hidden = Node("submit", states=("visible", "sensitive"))
    replacement = Node("submit")
    root = Node("", [hidden])
    def reveal(_where):
        root.children = [replacement]
        return True
    hidden.component.scroll_to.side_effect = reveal
    adapter(root).activate("submit")
    hidden.action.do_action.assert_not_called()
    replacement.action.do_action.assert_called_once_with(0)


def test_uncertain_input_is_never_replayed():
    target = Node("submit")
    target.action.do_action.side_effect = RuntimeError("transport disconnected")
    with pytest.raises(RuntimeError, match="transport disconnected"):
        adapter(target).activate("submit")
    target.action.do_action.assert_called_once_with(0)


def test_disabled_control_and_ambiguous_action_refuse_input():
    target = Node("submit", states=("showing", "visible"))
    with pytest.raises(AutomationError, match="disabled"):
        adapter(target).activate("submit")
    target.states.add("sensitive")
    target.action.get_n_actions = lambda: 2
    with pytest.raises(AutomationError, match="ambiguous-action"):
        adapter(target).activate("submit")
    target.action.do_action.assert_not_called()


def test_text_and_focus_use_only_the_identified_public_node():
    target = Node("entry", states=("showing", "visible", "sensitive", "focused"))
    ui = adapter(Node("", [Node("other"), target]))
    assert ui.text("entry") == "entry label"
    assert ui.content("entry") == "entry"
    assert ui.focus("entry") is target
    target.component.grab_focus.assert_called_once_with()


def test_focus_refusal_never_routes_keyboard_input():
    target = Node("entry")
    target.component.grab_focus.return_value = False
    with pytest.raises(AutomationError, match="focus-refused"):
        adapter(target).focus("entry")
    target.states.add("focused")
    target.component.grab_focus.return_value = True
    assert adapter(target).focus("entry") is target


def test_text_content_is_bounded():
    target = Node("private-draft")
    with pytest.raises(AutomationError, match="text-bound"):
        adapter(target).content("private-draft", maximum=4)


def test_text_read_uses_text_interface_despite_accessible_method_collision():
    target = Node("entry")
    target.text.get_text = Mock(side_effect=AssertionError("deprecated getter"))
    ui = adapter(target)
    ui.api.Text.get_text = Mock(return_value="typed text")
    assert ui.content("entry") == "typed text"
    ui.api.Text.get_text.assert_called_once_with(target.text, 0, 5)
    target.text.get_text.assert_not_called()


@pytest.mark.parametrize("names", [
    ("app.quit", "menu.popup"), ("menu.popup", "app.quit"),
    ("app.quit",), ("menu.popup", "menu.popup"),
])
def test_explicit_action_requires_unique_name_after_id_lookup(names):
    target = Node("menu-button")
    target.action.get_n_actions = lambda: len(names)
    target.action.get_action_name = lambda index: names[index]
    ui = adapter(target)
    if names.count("menu.popup") == 1:
        ui.activate("menu-button", action_name="menu.popup")
        target.action.do_action.assert_called_once_with(names.index("menu.popup"))
    else:
        with pytest.raises(AutomationError, match="ambiguous-action"):
            ui.activate("menu-button", action_name="menu.popup")
        target.action.do_action.assert_not_called()


def test_action_binding_metadata_warning_is_narrowly_scoped():
    api = SimpleNamespace(Action=SimpleNamespace())

    def name(_action, _index):
        warnings.warn("Atspi.Action.get_action_name is deprecated", DeprecationWarning)
        return "menu.popup"

    api.Action.get_action_name = name
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert public_action_name(api, object(), 0) == "menu.popup"
        with pytest.raises(DeprecationWarning):
            name(None, 0)

        def unexpected(_action, _index):
            warnings.warn("different API deprecated", DeprecationWarning)

        api.Action.get_action_name = unexpected
        with pytest.raises(DeprecationWarning, match="different API"):
            public_action_name(api, object(), 0)


def test_generated_rich_editor_controls_receive_stable_ids():
    source = (ROOT / "common/oh_no_parent_control_ui/rich_text_editor.py").read_text()
    for identity in (
        "feedback-format-toolbar", "feedback-editor-input",
        "feedback-format-style", "feedback-format-normal",
        "feedback-format-heading-1", "feedback-format-heading-2",
        "feedback-link-editor", "feedback-link-target", "feedback-link-preview",
        "feedback-link-save", "feedback-link-remove",
    ):
        assert identity in source
    assert "feedback-editor-root .ql-editor" in source


@pytest.mark.parametrize("reader", ["preview", "guest"])
def test_webkit_public_ids_survive_ax_number_changes_and_reject_duplicates(reader):
    target = Node("47")
    target.get_attributes = lambda: {"toolkit": "WebKitGTK", "id": "feedback-editor-input"}
    root = Node("", [target])
    if reader == "preview":
        ui = adapter(root)
        find = ui.find
        error = AutomationError
    else:
        ui = AccessibleUI(SimpleNamespace(get_desktop=lambda _: root))
        find = lambda identity: ui.find_id(identity, showing=False)
        error = UiError
    assert find("feedback-editor-input") is target
    assert find("47") is None
    target.identity = "99"
    assert find("feedback-editor-input") is target
    duplicate = Node("100")
    duplicate.get_attributes = target.get_attributes
    root.children.append(duplicate)
    with pytest.raises(error, match="ambiguous"):
        find("feedback-editor-input")


def test_provider_contract_never_substitutes_other_fields_for_missing_id():
    node = Node("generated-ax-number")
    node.get_attributes = lambda: {"toolkit": "WebKitGTK", "tag": "button"}
    node.get_name = Mock(side_effect=AssertionError("label used for identity"))
    assert public_automation_id(node) == ""
    node.get_attributes = lambda: {"toolkit": "unknown", "id": "unqualified-id"}
    assert public_automation_id(node) == "generated-ax-number"
    node.get_attributes = lambda: {"toolkit": "GTK", "id": "unqualified-id"}
    assert public_automation_id(node) == "generated-ax-number"
    node.get_name.assert_not_called()


def test_disappearing_provider_with_null_attributes_is_an_unidentified_node():
    node = Node("generated-ax-number")
    node.get_attributes = Mock(return_value=None)
    node.get_accessible_id = Mock(side_effect=AssertionError("unqualified ID fallback"))
    ui = AccessibleUI(SimpleNamespace(get_desktop=lambda _: node))
    assert public_automation_id(node) == ""
    assert ui.find_id("generated-ax-number", showing=False) is None
    node.get_accessible_id.assert_not_called()


def test_failed_provider_query_does_not_fall_back_to_accessible_id():
    node = Node("feedback-editor-input")
    node.get_attributes = Mock(side_effect=LookupError("stale provider"))
    with pytest.raises(LookupError, match="stale provider"):
        public_automation_id(node)


def provider_adapter(root):
    contracts = {
        "fixture-provider": {
            "application_id": "fixture-application",
            "surfaces": {
                "primary": ("fixture-primary-surface", {"submit": "fixture-submit"}),
                "secondary": ("fixture-secondary-surface", {"submit": "fixture-submit"}),
            },
            "blocked_consumers": (),
        },
    }
    return AccessibleUI(SimpleNamespace(
        get_desktop=lambda _: root,
        StateType=SimpleNamespace(SHOWING="showing", VISIBLE="visible", DEFUNCT="defunct"),
    ), provider_contracts=contracts)


def test_provider_lookup_is_scoped_to_registered_application_and_surface_ids():
    target = Node("fixture-submit")
    expected_surface = Node("fixture-primary-surface", [target])
    wrong_surface_target = Node("fixture-submit")
    wrong_surface = Node("fixture-secondary-surface", [wrong_surface_target])
    application = Node("fixture-application", [expected_surface, wrong_surface])
    wrong_application_target = Node("fixture-submit")
    wrong_application = Node("other-application", [
        Node("fixture-primary-surface", [wrong_application_target]),
    ])
    ui = provider_adapter(Node("", [wrong_application, application]))

    assert ui.find_provider_control("fixture-provider", "primary", "submit") is target
    assert target is not wrong_surface_target
    assert target is not wrong_application_target


def test_provider_lookup_refuses_wrong_surface_missing_id_and_ambiguity():
    wrong_surface = Node("fixture-secondary-surface", [Node("fixture-submit")])
    application = Node("fixture-application", [wrong_surface])
    ui = provider_adapter(Node("", [application]))
    assert ui.find_provider_control("fixture-provider", "primary", "submit") is None

    primary = Node("fixture-primary-surface", [Node("fixture-submit"), Node("fixture-submit")])
    application.children.append(primary)
    with pytest.raises(UiError, match="ambiguous-automation-id"):
        ui.find_provider_control("fixture-provider", "primary", "submit")

    with pytest.raises(UiError, match="unregistered-provider-control"):
        ui.find_provider_control("fixture-provider", "primary", "cancel")


@pytest.mark.parametrize("scope", ["application", "surface"])
def test_provider_lookup_refuses_ambiguous_scope_ids(scope):
    first = Node("fixture-primary-surface", [Node("fixture-submit")])
    second = Node("fixture-primary-surface", [Node("fixture-submit")])
    if scope == "application":
        root = Node("", [Node("fixture-application", [first]),
                         Node("fixture-application", [second])])
    else:
        root = Node("fixture-application", [first, second])
    with pytest.raises(UiError, match="ambiguous-automation-id"):
        provider_adapter(root).find_provider_control(
            "fixture-provider", "primary", "submit")


def test_provider_lookup_never_accepts_control_from_wrong_application():
    root = Node("other-application", [
        Node("fixture-primary-surface", [Node("fixture-submit")]),
    ])
    assert provider_adapter(root).find_provider_control(
        "fixture-provider", "primary", "submit") is None


@pytest.mark.parametrize("provider,surface,error", [
    ("missing-provider", "primary", "unregistered-provider"),
    ("fixture-provider", "missing-surface", "unregistered-provider-surface"),
])
def test_provider_lookup_refuses_unregistered_provider_or_surface(provider, surface, error):
    with pytest.raises(UiError, match=error):
        provider_adapter(Node("fixture-application")).find_provider_control(
            provider, surface, "submit")


@pytest.mark.parametrize("mutation,error", [
    (("application_id", None), "unqualified-provider-application"),
    (("surface_id", None), "unqualified-provider-surface"),
    (("control_id", None), "unqualified-provider-control"),
])
def test_partial_provider_registration_cannot_authorize_lookup(mutation, error):
    root = Node("fixture-application", [
        Node("fixture-primary-surface", [Node("fixture-submit")]),
    ])
    ui = provider_adapter(root)
    field, value = mutation
    if field == "application_id":
        ui.provider_contracts["fixture-provider"][field] = value
    elif field == "surface_id":
        _surface_id, controls = ui.provider_contracts["fixture-provider"]["surfaces"]["primary"]
        ui.provider_contracts["fixture-provider"]["surfaces"]["primary"] = (value, controls)
    else:
        surface_id, controls = ui.provider_contracts["fixture-provider"]["surfaces"]["primary"]
        ui.provider_contracts["fixture-provider"]["surfaces"]["primary"] = (
            surface_id, {**controls, "submit": value})
    with pytest.raises(UiError, match=error):
        ui.find_provider_control("fixture-provider", "primary", "submit")


def test_installed_external_provider_audit_keeps_partial_builder_ids_blocked():
    assert EXTERNAL_PROVIDER_CONTRACTS["gnome-settings"]["application_id"] is None
    settings = EXTERNAL_PROVIDER_CONTRACTS["gnome-settings"]["surfaces"]["settings"]
    users = EXTERNAL_PROVIDER_CONTRACTS["gnome-settings"]["surfaces"]["users"]
    assert settings == (None, {"search": "search_entry", "panel-list": "panel_list"})
    assert users[1]["account-list"] == "user_list"
    assert users[1]["account-row::<provider-account-id>"] is None

    chooser = EXTERNAL_PROVIDER_CONTRACTS[
        "xdg-desktop-portal-gnome-nautilus"]["surfaces"]["file-chooser"]
    assert chooser[1]["location"] == "filename_entry"
    assert chooser[1]["accept"] == "accept_button"
    assert chooser[0] is chooser[1]["file-choice"] is chooser[1]["cancel"] is None

    native_chooser = EXTERNAL_PROVIDER_CONTRACTS["gtk-file-chooser"]
    assert all(identity is None
               for identity in native_chooser["surfaces"]["file-chooser"][1].values())

    assert set(EXTERNAL_PROVIDER_CONTRACTS).isdisjoint({"native-fixture", "flatpak-fixture"})
    assert {"gnome-shell-polkit-agent", "gcr-keyring-prompter",
            "gtk-file-chooser", "xdg-desktop-portal-gnome-nautilus",
            "gnome-nautilus", "gnome-file-roller", "gnome-text-editor",
            "gnome-papers"} <= set(EXTERNAL_PROVIDER_CONTRACTS)
    for contract in EXTERNAL_PROVIDER_CONTRACTS.values():
        assert contract["application_id"] is None
        assert contract["blocked_consumers"]
