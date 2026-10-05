"""Read-only native coordinate metadata and GApplication export lifetime."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gi.repository import GLib

from parent.oh_no_parent_control_parent import main
from tests.support.objects import bind_methods


@pytest.fixture
def provider(monkeypatch):
    parent_register = Mock(return_value=True)
    parent_unregister = Mock()
    monkeypatch.setattr(main, "Adw", SimpleNamespace(Application=SimpleNamespace(
        do_dbus_register=parent_register, do_dbus_unregister=parent_unregister,
    )))
    monkeypatch.setattr(main, "Gtk", SimpleNamespace(
        Buildable=SimpleNamespace(get_buildable_id=lambda window: window.identity),
        Native=SimpleNamespace(
            get_surface=lambda window: window.surface,
            get_surface_transform=lambda window: window.transform(),
        ),
    ))
    window = SimpleNamespace(
        identity="parent-window", get_mapped=Mock(return_value=True),
        get_visible=Mock(return_value=True), is_active=Mock(return_value=True),
        surface=object(), transform=Mock(return_value=(-12.5, -8.0)),
        get_display=Mock(return_value=SimpleNamespace(sync=Mock())),
        present=Mock(), grab_focus=Mock(),
    )
    application = bind_methods(SimpleNamespace(
        get_windows=Mock(return_value=[window]), _accessibility_registration_id=0,
    ), main.Application, (
        "do_dbus_register", "do_dbus_unregister", "_native_surface_transform",
        "_accessibility_method_call",
    ))
    return application, window, parent_register, parent_unregister


def invoke(application, surface_id="parent-window", method="GetNativeSurfaceTransform"):
    invocation = Mock()
    application._accessibility_method_call(
        None, ":1.42", "/com/puffyslippers/OhNoParentControl/Parent",
        main.ACCESSIBILITY_INTERFACE, method, GLib.Variant("(s)", (surface_id,)),
        invocation,
    )
    return invocation


def test_transform_is_fresh_raw_public_pair_including_negative_offsets(provider):
    application, window, *_ = provider
    for expected in ((-12.5, -8.0), (0.0, 0.0), (3.25, -2.75)):
        window.transform.return_value = expected
        invocation = invoke(application)
        invocation.return_dbus_error.assert_not_called()
        reply, = invocation.return_value.call_args.args
        assert reply.get_type_string() == "(dd)"
        assert reply.unpack() == expected
    assert window.transform.call_count == 3


def test_transform_synchronizes_then_reobserves_without_product_input(provider):
    application, window, *_ = provider
    display = window.get_display.return_value

    def synchronized():
        window.transform.assert_not_called()
        assert application.get_windows.call_count == 1
        window.transform.return_value = (3.25, 4.5)

    display.sync.side_effect = synchronized
    invocation = invoke(application)
    invocation.return_dbus_error.assert_not_called()
    assert invocation.return_value.call_args.args[0].unpack() == (3.25, 4.5)
    assert application.get_windows.call_count == 2
    display.sync.assert_called_once_with()
    window.transform.assert_called_once_with()
    window.present.assert_not_called()
    window.grab_focus.assert_not_called()


@pytest.mark.parametrize("fault", [
    "missing", "duplicate", "replaced", "identity", "unmapped", "hidden",
    "inactive", "no-surface", "sync-error",
])
def test_transform_refuses_surface_changed_during_synchronization(provider, fault):
    application, window, *_ = provider
    display = window.get_display.return_value
    replacement = SimpleNamespace(**vars(window))
    assert replacement == window and replacement is not window

    def synchronized():
        window.transform.assert_not_called()
        if fault == "missing":
            application.get_windows.return_value = []
        elif fault == "duplicate":
            application.get_windows.return_value = [window, replacement]
        elif fault == "replaced":
            application.get_windows.return_value = [replacement]
        elif fault == "identity":
            window.identity = "feedback-dialog"
        elif fault in ("unmapped", "hidden", "inactive"):
            getattr(window, {"unmapped": "get_mapped", "hidden": "get_visible",
                             "inactive": "is_active"}[fault]).return_value = False
        elif fault == "no-surface":
            window.surface = None
        else:
            raise GLib.Error("PRIVATE_SYNC_DIAGNOSTIC")

    display.sync.side_effect = synchronized
    invocation = invoke(application)
    invocation.return_value.assert_not_called()
    invocation.return_dbus_error.assert_called_once_with(
        main.ACCESSIBILITY_INTERFACE + ".SurfaceUnavailable",
        "Native surface transform is unavailable",
    )
    display.sync.assert_called_once_with()
    window.transform.assert_not_called()
    replacement.transform.assert_not_called()
    window.present.assert_not_called()
    window.grab_focus.assert_not_called()


@pytest.mark.parametrize("fault", [
    "unknown-id", "missing", "duplicate", "unmapped", "hidden", "inactive",
    "no-surface", "nan-x", "infinite-y", "provider-error",
])
def test_unavailable_or_ambiguous_surface_never_returns_coordinates(provider, fault):
    application, window, *_ = provider
    surface_id = "parent-window"
    if fault == "unknown-id":
        surface_id = "feedback-dialog"
    elif fault == "missing":
        application.get_windows.return_value = []
    elif fault == "duplicate":
        application.get_windows.return_value = [window, window]
    elif fault in ("unmapped", "hidden", "inactive"):
        getattr(window, {"unmapped": "get_mapped", "hidden": "get_visible",
                         "inactive": "is_active"}[fault]).return_value = False
    elif fault == "no-surface":
        window.surface = None
    elif fault == "nan-x":
        window.transform.return_value = (float("nan"), 1.0)
    elif fault == "infinite-y":
        window.transform.return_value = (1.0, float("inf"))
    elif fault == "provider-error":
        window.transform.side_effect = GLib.Error("private details")
    invocation = invoke(application, surface_id)
    invocation.return_value.assert_not_called()
    invocation.return_dbus_error.assert_called_once_with(
        main.ACCESSIBILITY_INTERFACE + ".SurfaceUnavailable",
        "Native surface transform is unavailable",
    )
    if fault not in ("nan-x", "infinite-y", "provider-error"):
        window.transform.assert_not_called()


def test_unrelated_application_windows_do_not_supply_transform(provider):
    application, window, *_ = provider
    application.get_windows.return_value = [SimpleNamespace(identity="about-dialog"), window]
    invocation = invoke(application)
    assert invocation.return_value.call_args.args[0].unpack() == (-12.5, -8.0)


def test_unknown_method_never_queries_widgets(provider):
    application, window, *_ = provider
    invocation = invoke(application, method="SetNativeSurfaceTransform")
    invocation.return_dbus_error.assert_called_once_with(
        "org.freedesktop.DBus.Error.UnknownMethod", "Unknown method",
    )
    application.get_windows.assert_not_called()
    window.transform.assert_not_called()


def test_export_uses_application_connection_path_and_preserves_parent_lifecycle(provider):
    application, _, parent_register, parent_unregister = provider
    connection = Mock(register_object=Mock(return_value=41))
    path = "/com/puffyslippers/OhNoParentControl/Parent"
    assert application.do_dbus_register(connection, path)
    parent_register.assert_called_once_with(application, connection, path)
    exported_path, info, callback, getter, setter = connection.register_object.call_args.args
    assert exported_path == path
    assert info.name == main.ACCESSIBILITY_INTERFACE
    method, = info.methods
    assert method.name == "GetNativeSurfaceTransform"
    assert [arg.signature for arg in method.in_args] == ["s"]
    assert [arg.signature for arg in method.out_args] == ["d", "d"]
    assert callback == application._accessibility_method_call
    assert getter is setter is None
    assert application._accessibility_registration_id == 41
    application.do_dbus_unregister(connection, path)
    connection.unregister_object.assert_called_once_with(41)
    assert application._accessibility_registration_id == 0
    parent_unregister.assert_called_once_with(application, connection, path)
    connection.reset_mock()
    application.do_dbus_unregister(connection, path)
    connection.unregister_object.assert_not_called()


def test_parent_registration_failure_does_not_export_bridge(provider):
    application, _, parent_register, _ = provider
    parent_register.return_value = False
    connection = Mock()
    assert not application.do_dbus_register(connection, "/application")
    connection.register_object.assert_not_called()
    assert application._accessibility_registration_id == 0


def test_failed_export_can_unregister_without_leaking_registration(provider):
    application, _, _, parent_unregister = provider
    connection = Mock(register_object=Mock(side_effect=GLib.Error("export failed")))
    with pytest.raises(GLib.Error):
        application.do_dbus_register(connection, "/application")
    application.do_dbus_unregister(connection, "/application")
    connection.unregister_object.assert_not_called()
    parent_unregister.assert_called_once_with(application, connection, "/application")
