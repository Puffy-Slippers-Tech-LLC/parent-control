"""ID lookup must not silently degrade into geometry or label targeting."""

from types import SimpleNamespace
from unittest.mock import Mock
import importlib.util
import sys
import warnings

import pytest

from tests.support.automation import Automation, AutomationError, public_action_name
from tests.support.automation_ids import audit_owned_controls
from tests.support.keyboard import deliver
from tests.support.paths import ROOT
from tests.support.accessible_ui import product_tree
from tests.e2e.accessible_ui import (
    AccessibleUI,
    EXTERNAL_PROVIDER_CONTRACTS,
    UiError,
    WATCH_APPLICATION,
    owned_applications,
    owned_surface_id,
    public_automation_id,
)


class Node:
    def __init__(self, identity, children=(), states=("showing", "visible", "sensitive")):
        self.identity = identity
        self.children = children
        self.states = set(states)
        self.action = SimpleNamespace(get_n_actions=lambda: 1, do_action=Mock(return_value=True),
                                      get_action_name=lambda _index: "click")
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
    def get_process_id(self): return 100
    def get_relation_set(self): return getattr(self, 'relations', ())


def adapter(root, **kwargs):
    root = product_tree(root)
    return Automation(SimpleNamespace(
        Action=SimpleNamespace(get_action_name=lambda interface, index:
                               interface.get_action_name(index)),
        Text=SimpleNamespace(get_text=lambda interface, start, end:
                             interface.get_text(start, end)),
        StateType=SimpleNamespace(SHOWING="showing", VISIBLE="visible",
                                  SENSITIVE="sensitive", DEFUNCT="defunct",
                                  FOCUSED="focused"),
        RelationType=SimpleNamespace(CONTROLLED_BY="controlled-by"),
        ScrollType=SimpleNamespace(ANYWHERE="anywhere")), lambda: root, **kwargs)


def test_id_is_independent_of_order_and_unnamed_containers():
    target = Node("submit")
    root = Node("", [Node("decoration"), Node("", [target])])
    ui = adapter(root)
    assert ui.target("submit") is target
    root.children.reverse()
    assert ui.target("submit") is target


def test_spectator_ids_are_scoped_to_the_owned_window_and_application():
    assert owned_surface_id("e2e-watch-progress") == "e2e-watch-window"
    assert owned_surface_id("e2e-watch-window") is None
    assert owned_applications("e2e-watch-close") == (WATCH_APPLICATION,)
    progress = Node("e2e-watch-progress")
    window = Node("e2e-watch-window", [progress])
    ui = adapter(window)
    ui.application_ids = lambda: {WATCH_APPLICATION}
    ui.application_owners = lambda: {WATCH_APPLICATION: {100}}
    assert ui.find("e2e-watch-progress") is progress


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


def test_activation_invokes_clipped_control_without_reveal_or_focus():
    clipped = Node("submit", states=("visible", "sensitive"))
    ui = adapter(Node("", [clipped]))
    ui.activate("submit")
    clipped.component.scroll_to.assert_not_called()
    clipped.component.grab_focus.assert_not_called()
    clipped.action.do_action.assert_called_once_with(0)


def test_explicit_reveal_uses_fresh_replacement_after_scrolling():
    hidden = Node("submit", states=("visible", "sensitive"))
    replacement = Node("submit")
    root = Node("", [hidden])
    def reveal(_where):
        root.children = [replacement]
        return True
    hidden.component.scroll_to.side_effect = reveal
    assert adapter(root).reveal("submit") is replacement
    hidden.action.do_action.assert_not_called()
    replacement.action.do_action.assert_not_called()


def test_activation_refuses_application_hidden_control_without_reveal():
    hidden = Node("submit", states=("sensitive",))
    ui = adapter(Node("", [hidden]))
    with pytest.raises(AutomationError, match="hidden"):
        ui.activate("submit")
    hidden.component.scroll_to.assert_not_called()
    hidden.component.grab_focus.assert_not_called()
    hidden.action.do_action.assert_not_called()


def test_uncertain_input_is_never_replayed():
    target = Node("submit")
    target.action.do_action.side_effect = RuntimeError("transport disconnected")
    with pytest.raises(RuntimeError, match="transport disconnected"):
        adapter(target).activate("submit")
    target.action.do_action.assert_called_once_with(0)


def test_keyboard_delivery_reacquires_id_and_latches_uncertain_backend_failure():
    stale = Node("entry", states=("showing", "visible", "sensitive", "focused"))
    fresh = Node("entry", states=("showing", "visible", "sensitive", "focused"))
    root = Node("", [stale])
    ui = adapter(root)
    root.children = [fresh]
    sent = Mock(side_effect=RuntimeError("backend disconnected"))

    with pytest.raises(RuntimeError, match="backend disconnected"):
        deliver(ui, "entry", ui.api.StateType.FOCUSED, sent)
    sent.assert_called_once_with()
    assert ui.input_uncertain
    with pytest.raises(AssertionError, match="uncertain"):
        deliver(ui, "entry", ui.api.StateType.FOCUSED, Mock())


def test_keyboard_delivery_refuses_missing_recipient_state_before_input():
    ui = adapter(Node("entry"))
    sent = Mock()
    with pytest.raises(AssertionError, match="lacks"):
        deliver(ui, "entry", ui.api.StateType.FOCUSED, sent)
    sent.assert_not_called()
    assert not ui.input_uncertain


def test_pre_action_incomplete_read_retries_without_replaying_input():
    target = Node("parent-menu-button")
    root = Node("parent-window", [target])
    complete_reads = 0

    def child_at_index(index):
        nonlocal complete_reads
        complete_reads += 1
        if complete_reads == 1:
            return None
        return root.children[index]

    root.get_child_at_index = child_at_index

    def wait(predicate, _description):
        for _attempt in range(2):
            try:
                if predicate():
                    return
            except AutomationError as error:
                assert str(error) == "automation:incomplete-tree"
        raise AssertionError("complete read did not recover")

    ui = adapter(root, complete_read_wait=wait)
    ui.activate("parent-menu-button")
    # One discarded incomplete snapshot and one complete action-boundary
    # snapshot; ownership validation must not traverse the tree again.
    assert complete_reads == 2
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


def test_owned_gtk_surfaces_share_the_core_identity_publisher(monkeypatch):
    from common.oh_no_parent_control_ui import gtk_automation

    exposed = []
    gtk = SimpleNamespace(Builder=lambda: SimpleNamespace(
        expose_object=lambda identity, widget: exposed.append((identity, widget))))
    monkeypatch.setitem(sys.modules, "gi", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "gi.repository", SimpleNamespace(Gtk=gtk))
    widget = SimpleNamespace(set_name=Mock())
    assert gtk_automation.set_automation_id(widget, "e2e-watch-close") is widget
    widget.set_name.assert_called_once_with("e2e-watch-close")
    assert exposed == [("e2e-watch-close", widget)]
    for invalid in (None, "", "E2E-Watch", "e2e_watch", "-e2e-watch"):
        with pytest.raises(ValueError, match="lowercase hyphenated"):
            gtk_automation.set_automation_id(widget, invalid)

    viewer = (ROOT / "tools/e2e_watch_viewer.py").read_text()
    fixture = (ROOT / "tests/fixtures/gui_application.py").read_text()
    assert "def set_automation_id" not in viewer
    assert "def identify" not in fixture
    for source in (viewer, fixture):
        assert "gtk_automation import" in source
        assert "set_automation_id" in source
        assert "add_identified_window_controls" in source


def test_owned_control_inventory_supports_product_spectator_and_fixture_namespaces():
    for surface_identity in (
        "parent-window", "e2e-watch-window", "onpc-fixture-native-primary",
    ):
        control = Node(surface_identity + "-submit")
        control.get_role_name = lambda: "button"
        surface = Node(surface_identity, [control])
        ui = adapter(surface)
        root = None if surface_identity != "onpc-fixture-native-primary" else surface
        identities = audit_owned_controls(ui, surface_identity, root=root)
        assert identities[control.identity] is control

    missing = Node("")
    missing.get_role_name = lambda: "button"
    root = Node("e2e-watch-window", [missing])
    with pytest.raises(AssertionError, match="owned controls without public IDs"):
        audit_owned_controls(adapter(root), "e2e-watch-window")


def test_toolkit_title_buttons_require_an_identified_window_controls_owner():
    internal = Node("")
    internal.get_role_name = lambda: "button"
    controls = Node("parent-window-controls", [internal])
    surface = Node("parent-window", [controls])
    assert audit_owned_controls(adapter(surface), "parent-window")

    controls.identity = "parent-titlebar"
    with pytest.raises(AssertionError, match="owned controls without public IDs"):
        audit_owned_controls(adapter(surface), "parent-window")


def test_generic_action_on_text_is_presentation_but_anonymous_entry_is_not():
    text = Node("")
    text.get_role_name = lambda: "text"
    surface = Node("child-screen-time-indicator", [text])
    assert audit_owned_controls(
        adapter(surface), "child-screen-time-indicator", root=surface,
    )

    text.get_role_name = lambda: "entry"
    with pytest.raises(AssertionError, match="owned controls without public IDs"):
        audit_owned_controls(
            adapter(surface), "child-screen-time-indicator", root=surface,
        )


@pytest.mark.parametrize("reader", ["preview", "guest"])
def test_webkit_public_ids_survive_ax_number_changes_and_reject_duplicates(reader):
    target = Node("47")
    target.get_attributes = lambda: {"toolkit": "WebKitGTK", "id": "feedback-editor-input"}
    root = Node("feedback-dialog", [target])
    desktop = product_tree(Node("parent-window", [root]))
    if reader == "preview":
        ui = adapter(desktop)
        find = ui.find
        error = AutomationError
    else:
        ui = AccessibleUI(SimpleNamespace(get_desktop=lambda _: desktop))
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


def test_owned_control_cannot_be_borrowed_from_another_surface():
    foreign = Node("parent-screen-limit-toggle")
    parent = Node("parent-window")
    ui = adapter(Node("", [parent, Node("unrelated-window", [foreign])]))
    assert ui.find("parent-screen-limit-toggle") is None
    with pytest.raises(AutomationError, match="missing-public-id"):
        ui.activate("parent-screen-limit-toggle")
    foreign.action.do_action.assert_not_called()


def test_owned_surface_requires_the_explicitly_launched_process():
    target = Node("parent-screen-limit-toggle")
    parent = Node("parent-window", [target])
    parent.get_process_id = Mock(return_value=100)
    ui = adapter(Node("", [parent]))
    ui.owner_pids = lambda: {200}
    with pytest.raises(AutomationError, match="wrong-owner"):
        ui.activate("parent-screen-limit-toggle")
    target.action.do_action.assert_not_called()
    ui.owner_pids = lambda: {100}
    assert ui.find("parent-screen-limit-toggle") is target


def test_owned_webkit_control_uses_gtk_surface_ownership():
    target = Node("feedback-editor-input")
    target.get_process_id = Mock(side_effect=AssertionError("WebKit child PID is not the owner"))
    surface = Node("feedback-dialog", [target])
    surface.get_process_id = lambda: 100
    ui = adapter(Node("parent-window", [surface]))
    ui.owner_pids = lambda: {100}
    assert ui.find("feedback-editor-input") is target


def test_duplicate_owned_surfaces_refuse_before_control_input():
    target = Node("kiosk-request-submit")
    ui = adapter(Node("", [Node("kiosk-request-window", [target]),
                           Node("kiosk-request-window")]))
    with pytest.raises(AutomationError, match="ambiguous-id"):
        ui.activate("kiosk-request-submit")
    target.action.do_action.assert_not_called()


@pytest.mark.parametrize("fault", [None, "incomplete", "null-attributes", "null-child", "defunct", "missing-anchor", "present"])
def test_absence_requires_a_complete_read_and_positive_owned_surface(fault):
    surface = Node("parent-window")
    root = Node("", [surface, Node("unrelated")])
    ui = adapter(root)
    ui.query_errors = (LookupError,)
    if fault == "incomplete":
        root.children[1].get_child_count = Mock(side_effect=LookupError("incomplete"))
    if fault == "null-attributes":
        root.children[1].get_attributes = lambda: None
    if fault == "null-child":
        root.children[1].children = [None]
    if fault == "defunct":
        root.children[1].states.add("defunct")
    if fault == "missing-anchor":
        root.children.remove(surface)
    if fault == "present":
        surface.children = [Node("feedback-dialog")]
    assert ui.absent("feedback-dialog", within="parent-window") is (fault is None)


def test_absence_uses_one_complete_snapshot_per_observation():
    dialog = Node("feedback-success-dialog")
    surrounding = Node("kiosk-request-window", [dialog])
    root = Node("", [surrounding])
    automation = adapter(root)
    reader = AccessibleUI(automation.api)
    reader.nodes = Mock(wraps=automation.nodes)
    assert reader.absent_id("feedback-success-dialog", within="kiosk-request-window") is False
    assert reader.nodes.call_count == 1
    surrounding.children.remove(dialog)
    assert reader.absent_id("feedback-success-dialog", within="kiosk-request-window") is True
    assert reader.nodes.call_count == 2


def test_absence_rejects_a_stable_dialog_outside_its_owned_application():
    surrounding = Node("kiosk-request-window")
    application = Node("com.puffyslippers.OhNoParentControl", [surrounding])
    foreign = Node("foreign-application", [Node("feedback-success-dialog")])
    automation = adapter(Node("", [application, foreign]))
    reader = AccessibleUI(automation.api)
    reader.nodes = automation.nodes

    with pytest.raises(UiError, match="wrong-absence-owner"):
        reader.absent_id("feedback-success-dialog", within="kiosk-request-window")


def test_absence_retries_a_cached_node_from_an_exited_exact_owner():
    surrounding = Node("kiosk-request-window")
    kiosk = Node("com.puffyslippers.OhNoParentControl", [surrounding])
    stale = Node("parent-access-denied-window")
    stale.get_process_id = Mock(return_value=200)
    automation = adapter(Node("", [kiosk, stale]))
    reader = AccessibleUI(
        automation.api,
        application_ids=lambda: {"com.puffyslippers.OhNoParentControl"},
        application_owners=lambda: {
            "com.puffyslippers.OhNoParentControl": {100},
        },
        application_owner_history=lambda: {
            "com.puffyslippers.OhNoParentControl.Parent": {200},
            "com.puffyslippers.OhNoParentControl": {100},
        },
    )
    reader.nodes = automation.nodes

    assert not reader.absent_id(
        "parent-access-denied-window", within="kiosk-request-window",
    )
    automation.root().children.remove(stale)
    assert reader.absent_id(
        "parent-access-denied-window", within="kiosk-request-window",
    )


def test_absence_accepts_an_unmapped_dialog_after_its_owner_relation_is_removed():
    parent = Node("parent-window")
    feedback = Node("feedback-dialog")
    privacy = Node("feedback-privacy-dialog", states=("sensitive",))
    application = Node(
        "com.puffyslippers.OhNoParentControl.Parent",
        [parent, feedback, privacy],
    )
    feedback.relations = [SimpleNamespace(
        get_relation_type=lambda: "controlled-by", get_n_targets=lambda: 1,
        get_target=lambda _index: parent,
    )]
    ui = adapter(application)

    assert ui.absent("feedback-privacy-dialog", within="feedback-dialog")
    privacy.states.update(("showing", "visible"))
    with pytest.raises(AutomationError, match="missing-surface-owner"):
        ui.absent("feedback-privacy-dialog", within="feedback-dialog")


def test_live_launches_cannot_exchange_their_application_identity():
    ui = adapter(Node("parent-window", [Node("parent-menu-button")]))
    ui.owner_pids = lambda: {100, 200}
    ui.application_owners = lambda: {"com.puffyslippers.OhNoParentControl.Parent": {200}}
    with pytest.raises(AutomationError, match="wrong-application-owner"):
        ui.activate("parent-menu-button")


@pytest.mark.parametrize("fault", [None, "missing", "unconfirmed", "uncertain", "disappeared"])
def test_native_focus_is_public_surface_action_with_fresh_id_readback(fault):
    target = Node("parent-app-search")
    replacement = Node("parent-app-search", states=("showing", "visible", "sensitive", "focused"))
    surface = Node("parent-window", [target])
    surface.action.get_action_name = lambda _index: (
        "other" if fault == "missing" else "focus.parent-app-search")
    def focus(_index):
        if fault == "uncertain":
            raise LookupError("transport uncertainty")
        if fault == "disappeared":
            surface.children = []
        elif fault != "unconfirmed":
            surface.children = [replacement]
        return True
    surface.action.do_action.side_effect = focus
    ui = adapter(surface)
    if fault:
        with pytest.raises((AutomationError, LookupError)):
            ui.focus("parent-app-search")
        if fault in ("unconfirmed", "uncertain", "disappeared"):
            with pytest.raises(AutomationError, match="uncertain-input"):
                ui.focus("parent-app-search")
    else:
        assert ui.focus("parent-app-search") is replacement
    assert surface.action.do_action.call_count == (0 if fault == "missing" else 1)
    target.component.grab_focus.assert_not_called()
    target.action.do_action.assert_not_called()


@pytest.mark.parametrize("fault", [None, "missing", "wrong-parent", "foreign-parent", "duplicate-parent"])
def test_separate_dialog_requires_its_public_owner_relation(fault):
    parent = Node("parent-window")
    target = Node("feedback-close")
    dialog = Node("feedback-dialog", [target])
    application = Node("com.puffyslippers.OhNoParentControl.Parent", [parent, dialog])
    owner = parent
    if fault == "wrong-parent":
        owner = Node("about-dialog")
        application.children.append(owner)
    elif fault == "foreign-parent":
        owner = Node("parent-window")
    elif fault == "duplicate-parent":
        application.children.append(Node("parent-window"))
    dialog.relations = [] if fault == "missing" else [SimpleNamespace(
        get_relation_type=lambda: "controlled-by", get_n_targets=lambda: 1,
        get_target=lambda _index: owner)]
    ui = adapter(application)
    if fault:
        with pytest.raises(AutomationError, match="surface-owner"):
            ui.activate("feedback-close")
        target.action.do_action.assert_not_called()
    else:
        assert ui.target("feedback-close") is target


def test_nested_privacy_dialog_cannot_borrow_the_primary_window_owner():
    parent = Node("parent-window")
    privacy = Node("feedback-privacy-dialog", [Node("feedback-privacy-text")])
    feedback = Node("feedback-dialog")
    application = Node("com.puffyslippers.OhNoParentControl.Parent", [parent, feedback, privacy])
    def controlled_by(owner):
        return [SimpleNamespace(get_relation_type=lambda: "controlled-by",
                                get_n_targets=lambda: 1, get_target=lambda _index: owner)]
    feedback.relations = controlled_by(parent)
    privacy.relations = controlled_by(parent)
    ui = adapter(application)
    with pytest.raises(AutomationError, match="wrong-surface-owner"):
        ui.target("feedback-privacy-text")
    privacy.relations = controlled_by(feedback)
    assert ui.target("feedback-privacy-text") is privacy.children[0]


@pytest.mark.parametrize("fault", [None, "foreign-menu", "duplicate-anchor"])
def test_child_chrome_siblings_stay_in_the_indicator_application(fault):
    indicator = Node("child-screen-time-indicator")
    tooltip = Node("child-request-tooltip")
    toggle = Node("child-countdown-animation-toggle")
    menu = Node("child-countdown-menu", [toggle])
    shell = Node("", [indicator, tooltip, menu])
    indicator.get_application = lambda: shell
    desktop = Node("", [shell])
    if fault == "foreign-menu":
        shell.children.remove(menu)
        desktop.children.append(Node("foreign-app", [menu]))
    elif fault == "duplicate-anchor":
        shell.children.append(Node("child-screen-time-indicator"))
    ui = adapter(desktop)
    if fault == "duplicate-anchor":
        with pytest.raises(AutomationError, match="ambiguous-id"):
            ui.target("child-request-tooltip")
    else:
        assert ui.target("child-request-tooltip") is tooltip
        assert ui.find("child-countdown-animation-toggle") is (None if fault else toggle)


def test_navigation_actions_cannot_be_default_activation():
    target = Node("submit")
    target.action.get_action_name = lambda _index: "focus.submit"
    with pytest.raises(AutomationError, match="ambiguous-action"):
        adapter(target).activate("submit")
    target.action.do_action.assert_not_called()


@pytest.mark.parametrize("initial_parent_sensitive", [False, True])
def test_owned_disabled_state_tracks_inheritance_and_local_notifications(monkeypatch,
                                                                       initial_parent_sensitive):
    gtk = SimpleNamespace(
        AccessibleState=SimpleNamespace(DISABLED="disabled"),
        Builder=lambda: SimpleNamespace(expose_object=lambda *_args: None),
        MenuButton=type("MenuButton", (), {}), CheckButton=type("CheckButton", (), {}),
        ListBoxRow=type("ListBoxRow", (), {}),
    )
    monkeypatch.setitem(sys.modules, "gi", SimpleNamespace(require_version=Mock()))
    monkeypatch.setitem(sys.modules, "gi.repository", SimpleNamespace(Gtk=gtk, Gio=SimpleNamespace()))
    spec = importlib.util.spec_from_file_location(
        "owned_accessibility_test", ROOT / "common/oh_no_parent_control_ui/accessibility.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Widget:
        def __init__(self):
            self.local_sensitive = True
            self.parent_sensitive = initial_parent_sensitive
            self.handlers = {}
            self.disabled = None

        def connect(self, signal, callback):
            self.handlers.setdefault(signal, []).append(callback)

        def emit(self, signal):
            for callback in self.handlers[signal]:
                callback(self, None)

        def set_name(self, _name): pass
        def get_mapped(self): return False
        def is_sensitive(self): return self.local_sensitive and self.parent_sensitive

        def update_state(self, states, values):
            assert states == ["disabled"]
            self.disabled, = values

    widget = Widget()
    module.set_automation_id(widget, "parent-child-selector")
    assert widget.disabled is (not initial_parent_sensitive)
    widget.parent_sensitive = False
    widget.emit("state-flags-changed")
    assert widget.disabled is True
    # GTK overwrites the local accessible value even when effective state
    # flags remain unchanged under an insensitive parent.
    widget.disabled = False
    widget.emit("notify::sensitive")
    assert widget.disabled is True
    widget.parent_sensitive = True
    widget.emit("state-flags-changed")
    assert widget.disabled is False
    widget.local_sensitive = False
    widget.emit("notify::sensitive")
    assert widget.disabled is True
    handlers = {signal: tuple(callbacks) for signal, callbacks in widget.handlers.items()}
    module.set_automation_id(widget, "parent-child-selector")
    assert {signal: tuple(callbacks) for signal, callbacks in widget.handlers.items()} == handlers


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
