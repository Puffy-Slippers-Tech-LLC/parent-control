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
from oh_no_parent_control.extension_monitor import ExtensionMonitor, _Watch, MAX_BACKOFF_LEVEL
from common.oh_no_parent_control_ui.reboot import product_reboot_required


from tests.support.paths import ROOT


def test_extension_monitor_coalesces_untrusted_hints_and_bounds_failed_work():
    import threading
    from gi.repository import GLib

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor._later = mock.Mock()
    watch = _Watch(1001)
    for _ in range(100):
        monitor._schedule(watch)
    monitor._later.assert_called_once()
    watch.source = None
    watch.failures = MAX_BACKOFF_LEVEL
    monitor._later.reset_mock()
    for _ in range(100):
        monitor._schedule(watch)
    monitor._later.assert_called_once()
    # Owning/replacing Shell's name is also under child control. Those bus
    # hints cannot bypass the existing probe or failure retry deadline.
    watch.source = None
    watch.next_check = 15
    monitor._later.reset_mock()
    with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", return_value=10):
        for _ in range(100):
            monitor._shell_changed(watch, GLib.Variant("(sss)", ("org.gnome.Shell", "", ":1.42")))
    monitor._later.assert_called_once()
    assert monitor._later.call_args.args[0] == 5
    assert watch.next_check == 15
    monitor._later.reset_mock()
    watch.failures = 0
    monitor._stopped.set()
    monitor._schedule(watch)
    monitor._later.assert_not_called()


def test_extension_monitor_retains_cheap_busy_retry_without_session_probes():
    import threading
    from oh_no_parent_control.core import Busy
    from oh_no_parent_control.extension_manager import ExtensionManager

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor.manager = ExtensionManager()
    monitor.broker = mock.Mock()
    monitor.broker.extension_reconciliation_busy.return_value = True
    monitor.broker.reconcile_enabled_child.side_effect = Busy()
    watch = _Watch(1001, connection=object(), shell_present=True, failures=MAX_BACKOFF_LEVEL)
    monitor.watches = {1001: watch}
    monitor._later = mock.Mock()
    monitor._reconcile = mock.Mock()
    monitor._check(watch)
    monitor._later.assert_called_once()
    assert watch.failures == MAX_BACKOFF_LEVEL
    monitor._reconcile.assert_not_called()


def test_extension_monitor_retries_disabled_state_indefinitely_with_capped_failure_delay():
    import threading
    from oh_no_parent_control.extension_manager import ExtensionManager

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor.manager = ExtensionManager()
    monitor.broker = mock.Mock()
    monitor.broker.extension_reconciliation_busy.return_value = False
    monitor.broker.reconcile_enabled_child.side_effect = lambda _uid, action, **_kwargs: (action(), True)[1]
    monitor._observe = mock.Mock(return_value=({"state": 2}, True))
    monitor.manager.set_enabled = mock.Mock(side_effect=RuntimeError("temporary verification failure"))
    monitor.manager.report_failure = mock.Mock()
    monitor._later = mock.Mock()
    watch = _Watch(1001, connection=object(), shell_present=True)
    monitor.watches = {1001: watch}
    # Fail beyond the old attempt limit: each due retry still attempts the
    # authorized restoration, while the delay/counter stop growing at thirty.
    for attempt in range(12):
        watch.source = None
        with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", return_value=10 + attempt * 32):
            monitor._check(watch)
        assert monitor.manager.set_enabled.call_count == attempt + 1
        assert monitor._later.call_args.args[0] <= 30
    assert watch.failures == MAX_BACKOFF_LEVEL
    assert monitor._later.call_args.args[0] == 30
    monitor.manager.set_enabled.side_effect = None
    watch.source = None
    with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", return_value=500):
        monitor._check(watch)
    assert watch.failures == 0
    assert monitor.manager.set_enabled.call_count == 13
    # Infinite recovery still ends at an actual extension failure, which is
    # reported once and cannot become another activation loop.
    monitor._observe.return_value = ({"state": 3, "error": ""}, True)
    monitor._check(watch)
    monitor._check(watch)
    assert monitor.manager.set_enabled.call_count == 13
    monitor.manager.report_failure.assert_called_once_with(1001)


def test_extension_monitor_keeps_deferred_report_after_recovery_and_reports_it_once():
    import threading
    from oh_no_parent_control.extension_manager import ChildExtensionUnavailable, ExtensionManager

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor.manager = ExtensionManager()
    monitor.manager.set_enabled = mock.Mock()
    monitor.manager.report_failure = mock.Mock(side_effect=[
        ChildExtensionUnavailable(), ChildExtensionUnavailable(),
        ChildExtensionUnavailable(), None])
    monitor.broker = mock.Mock()
    monitor.broker.extension_reconciliation_busy.return_value = False
    monitor.broker.reconcile_enabled_child.side_effect = lambda _uid, action, **_kwargs: (action(), True)[1]
    monitor._observe = mock.Mock(return_value=({"state": 3, "error": ""}, True))
    monitor._later = mock.Mock()
    watch = _Watch(1001, connection=object(), shell_present=True)
    monitor.watches = {1001: watch}
    monitor._check(watch)
    assert watch.failed and not watch.reported and watch.report_pending
    assert 0 < monitor._later.call_args.args[0] <= 30
    # Shell can recover while the user manager still lacks a display. Keep
    # the observed error pending until its report can actually be launched.
    monitor._observe.return_value = ({"state": 1}, True)
    watch.source = None
    monitor._check(watch)
    assert not watch.failed and not watch.reported and watch.report_pending
    # Normal observed recovery rearms enforcement too: another disable must
    # recover while reporting is still unavailable, without parent action.
    monitor._observe.return_value = ({"state": 2}, True)
    watch.source = None
    monitor._check(watch)
    monitor.manager.set_enabled.assert_called_once_with(1001, True, recover_global_switch=True)
    assert not watch.failed and not watch.reported and watch.report_pending
    monitor._observe.return_value = ({"state": 1}, True)
    watch.source = None
    monitor._check(watch)
    assert not watch.failed and watch.reported and not watch.report_pending
    monitor._check(watch)
    assert monitor.manager.report_failure.call_count == 4
    assert monitor.manager.set_enabled.call_count == 1


@pytest.mark.parametrize("deferred", [False, True])
def test_explicit_recovery_rearms_without_a_healthy_observation_and_keeps_deferred_report(deferred):
    import threading
    from oh_no_parent_control.extension_manager import ChildExtensionUnavailable, ExtensionManager

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor._context = mock.Mock()
    monitor._later = mock.Mock()
    monitor._schedule = mock.Mock()
    monitor.manager = ExtensionManager()
    monitor.broker = mock.Mock()
    monitor.broker.extension_reconciliation_busy.return_value = False
    monitor.broker.reconcile_enabled_child.side_effect = lambda _uid, action, **_kwargs: (action(), True)[1]
    monitor._observe = mock.Mock(return_value=({"state": 3, "error": ""}, True))
    effects = []
    display_ready = not deferred

    def report(_uid):
        effects.append("report")
        if not display_ready:
            raise ChildExtensionUnavailable()

    monitor.manager.report_failure = mock.Mock(side_effect=report)
    monitor.manager.set_enabled = mock.Mock(side_effect=lambda *_args, **_kwargs: effects.append("enable"))
    watch = _Watch(1001, connection=object(), shell_present=True)
    monitor.watches = {1001: watch}
    with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", return_value=100):
        monitor._check(watch)
        assert watch.failed and watch.report_pending == deferred
        watch.recovery_interrupted = True
        watch.last_recovery, watch.next_check = 80, 101
        monitor.recovered(1001)
        assert watch.failed  # The service thread cannot mutate the watch.
        monitor._later.call_args.args[1]()
        assert not watch.failed and watch.report_pending == deferred
        assert watch.recovery_interrupted
        assert (watch.last_recovery, watch.next_check) == (80, 101)
        # Deliberately skip healthy: disablement is the first observation after
        # trusted parent recovery, matching coalesced native Shell signals.
        monitor._observe.return_value = ({"state": 2}, True)
        effects.clear()
        monitor._check(watch)
        monitor.manager.set_enabled.assert_called_once_with(1001, True, recover_global_switch=True)
        assert effects == (["enable", "report"] if deferred else ["enable"])
        assert not watch.failed and watch.report_pending == deferred
        if deferred:
            assert 0 < watch.next_check - 100 <= 30
            monitor._observe.return_value = ({"state": 1}, True)
            monitor._check(watch)
            assert not watch.failed and watch.report_pending
            display_ready = True
            monitor._check(watch)
            assert watch.reported and not watch.report_pending
        # A newly observed ERROR still stops further automatic activation.
        monitor._observe.return_value = ({"state": 3, "error": ""}, True)
        monitor._check(watch)
        assert watch.failed
        monitor._observe.return_value = ({"state": 2}, True)
        monitor._check(watch)
        assert monitor.manager.set_enabled.call_count == 1
        monitor.recovered(1001)
        # Owner loss delivered before the queued notification must survive it.
        watch.recovery_interrupted = True
        monitor._later.call_args.args[1]()
        monitor._observe.return_value = ({"state": 2}, False)
        monitor._check(watch)
        assert watch.recovery_interrupted and not watch.failed
        assert monitor.manager.set_enabled.call_count == 1


@pytest.mark.parametrize("interleaving", ["before_busy_check", "during_observation", "after_recovery"])
def test_recovery_notification_preserves_only_faults_observed_after_its_transaction(interleaving):
    import threading
    from oh_no_parent_control.extension_manager import ExtensionManager
    from tests.support.broker import Preferences, make_broker

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor._context = mock.Mock()
    monitor._later = mock.Mock()
    monitor._schedule = mock.Mock()
    monitor.manager = ExtensionManager()
    monitor.manager.set_enabled = mock.Mock()
    monitor.manager.report_failure = mock.Mock()
    preferences = Preferences()
    preferences.values[1001]["parent_control_enabled"] = True
    monitor.broker = make_broker(preferences=preferences, extensions=monitor.manager)
    monitor._observe = mock.Mock(return_value=({"state": 3, "error": ""}, True))
    watch = _Watch(1001, connection=object(), shell_present=True)
    monitor.watches = {1001: watch}
    callbacks = []

    def recover():
        assert monitor.broker.recover_child_extension(0, 1001, on_recovered=monitor.recovered)
        callbacks.append(monitor._later.call_args.args[1])

    with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", return_value=100):
        monitor._check(watch)
        generation = watch.fault_generation
        assert watch.failed
        if interleaving == "before_busy_check":
            # Completing between revision capture and busy check must still
            # invalidate this observation, although the lock is now free.
            with mock.patch.object(monitor.broker, "extension_reconciliation_busy",
                                   side_effect=lambda: (recover(), False)[1]):
                monitor._check(watch)
        elif interleaving == "during_observation":
            monitor._observe.side_effect = lambda _watch: (recover(), ({"state": 3}, True))[1]
            monitor._check(watch)
            monitor._observe.side_effect = None
        else:
            recover()
            # This ERROR is genuinely newer than the successful recovery,
            # but the private-context notification has not run yet.
            monitor._check(watch)
        fresh_error = interleaving == "after_recovery"
        assert watch.fault_generation == generation + int(fresh_error)
        callbacks[0]()
        assert watch.failed == fresh_error
        monitor._observe.return_value = ({"state": 2}, True)
        monitor._check(watch)
        # One call belongs to explicit recovery. Only the pre-recovery stale
        # observations permit another automatic activation after notification.
        assert monitor.manager.set_enabled.call_count == (1 if fresh_error else 2)


@pytest.mark.parametrize("unavailable", ["removed", "replaced", "stopped"])
def test_explicit_recovery_notification_is_safe_when_watch_goes_away(unavailable):
    import threading

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor._context = mock.Mock()
    monitor._later = mock.Mock()
    monitor._schedule = mock.Mock()
    watch = _Watch(1001, failed=True, report_pending=True)
    monitor.watches = {1001: watch}
    monitor.recovered(1001)
    callback = monitor._later.call_args.args[1]
    if unavailable == "removed":
        del monitor.watches[1001]
    elif unavailable == "replaced":
        monitor.watches[1001] = _Watch(1001, failed=True, report_pending=True)
    else:
        monitor._stopped.set()
    callback()
    assert watch.failed and watch.report_pending
    if unavailable == "replaced":
        assert monitor.watches[1001].failed and monitor.watches[1001].report_pending
    monitor._schedule.assert_not_called()
    monitor._stopped.set()
    monitor._later.reset_mock()
    monitor.recovered(1001)
    monitor._later.assert_not_called()


def test_extension_monitor_recovers_repeated_individual_and_global_disables_without_cooldown():
    import threading

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor.manager = mock.Mock()
    monitor._schedule = mock.Mock()
    watch = _Watch(1001)
    clock = [100.0]
    with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", side_effect=lambda: clock[0]):
        for count in range(1, 13):
            # Alternate individual/global disablement without waiting for a
            # healthy observation; native signals can coalesce that transition.
            monitor._reconcile(watch, {"state": 2}, bool(count % 2))
            assert monitor.manager.set_enabled.call_count == count
            assert watch.last_recovery == clock[0]
            assert watch.next_check == 0
            clock[0] += 0.5
    monitor._schedule.assert_not_called()
    assert monitor.manager.set_enabled.call_args_list == [
        mock.call(1001, True, recover_global_switch=True)] * 12
    monitor.manager.report_failure.assert_not_called()


def test_extension_monitor_shell_loss_is_quiet_and_preserves_crash_protection():
    import threading
    from oh_no_parent_control.service import GLib
    from oh_no_parent_control.extension_monitor import _ChangingState

    monitor = ExtensionMonitor.__new__(ExtensionMonitor)
    monitor._stopped = threading.Event()
    monitor.manager = mock.Mock()
    monitor._schedule = mock.Mock()
    watch = _Watch(1001, last_recovery=10)
    with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", return_value=45):
        monitor._shell_changed(watch, GLib.Variant("(sss)", ("org.gnome.Shell", ":1.1", "")))
    assert watch.recovery_interrupted and not watch.failed
    # A rapid normal relogin is allowed to finish initialization quietly.
    with pytest.raises(_ChangingState):
        monitor._reconcile(watch, {"state": 6, "enabled": True}, True)
    monitor._reconcile(watch, {"state": 1}, True)
    monitor.manager.report_failure.assert_not_called()
    monitor.manager.set_enabled.assert_not_called()
    assert not watch.recovery_interrupted
    # Whole-bus loss may precede delivery of the Shell owner-loss signal.
    watch.shell_present = True
    with mock.patch("oh_no_parent_control.extension_monitor.time.monotonic", return_value=45):
        monitor._bus_closed(watch)
    assert watch.recovery_interrupted and not watch.shell_present and not watch.failed
    # If GNOME disabled all extensions after that loss, do not immediately
    # undo its protection or infer which extension caused the exit.
    monitor._reconcile(watch, {"state": 2}, False)
    monitor.manager.report_failure.assert_not_called()
    monitor.manager.set_enabled.assert_not_called()
    # An actual product-extension ERROR remains reportable during the hold.
    monitor._reconcile(watch, {"state": 3, "error": ""}, False)
    monitor.manager.report_failure.assert_called_once_with(1001)


@pytest.mark.parametrize("scope,uid,target", [("Own", 1001, ()), ("Child", 991, (1001,))])
def test_time_grant_presets_dispatch_and_json_guards(scope, uid, target):
    from oh_no_parent_control.service import GLib
    service = Service.__new__(Service)
    service.credentials = mock.Mock()
    service.credentials.uid.return_value = uid
    service.broker = mock.Mock()
    for verb in ("Get", "Set"):
        method = f"{verb}{scope}TimeGrantPresets"
        operation = getattr(service.broker, f"{verb.lower()}_{scope.lower()}_time_grant_presets")
        operation.return_value = []
        signature = "(" + ("u" if target else "") + ("s" if verb == "Set" else "") + ")"
        values = (*target, "[]") if verb == "Set" else target
        invocation = mock.Mock()
        service._method_call(None, ":1.42", None, None, method, GLib.Variant(signature, values), invocation)
        operation.assert_called_once_with(uid, *target, *([[]] if verb == "Set" else []))
        assert json.loads(invocation.return_value.call_args.args[0].unpack()[0]) == []
        invocation.return_dbus_error.assert_not_called()
    setter = getattr(service.broker, f"set_{scope.lower()}_time_grant_presets")
    setter.reset_mock()
    for encoded in ('{', '{"x": 1, "x": 2}', ' ' * (512 * 1024 + 1)):
        invocation = mock.Mock()
        service._method_call(None, ":1.42", None, None, f"Set{scope}TimeGrantPresets",
                             GLib.Variant(signature, (*target, encoded)), invocation)
        assert invocation.return_dbus_error.call_args.args[0].endswith(".InvalidRequest")
        invocation.return_value.assert_not_called()
    with mock.patch("oh_no_parent_control.service.decode_preferences", side_effect=RecursionError):
        invocation = mock.Mock()
        service._method_call(None, ":1.42", None, None, f"Set{scope}TimeGrantPresets",
                             GLib.Variant(signature, (*target, "[]")), invocation)
        assert invocation.return_dbus_error.call_args.args[0].endswith(".InvalidRequest")
    setter.assert_not_called()


@pytest.mark.parametrize("scope,uid,target", [("Own", 1001, ()), ("Child", 991, (1001,))])
def test_time_grant_preset_json_validation_preserves_storage(tmp_path, scope, uid, target):
    from oh_no_parent_control.preferences import PreferenceStore
    from oh_no_parent_control.service import GLib
    from tests.support.broker import Accounts, make_broker

    store = PreferenceStore(tmp_path)
    store.update_time_grant_presets(1001, [123])
    before = (tmp_path / "1001.json").read_bytes()
    service = Service.__new__(Service)
    service.credentials = mock.Mock()
    service.credentials.uid.return_value = uid
    accounts = Accounts()
    service.broker = make_broker(preferences=store, accounts=accounts)
    signature = "(us)" if target else "(s)"
    for encoded in ('null', '{}', '[true]', '[300.0]', '[60, 60]', '[0]',
                    '[' * 2000 + ']' * 2000):
        invocation = mock.Mock()
        service._method_call(None, ":1.42", None, None, f"Set{scope}TimeGrantPresets",
                             GLib.Variant(signature, (*target, encoded)), invocation)
        assert invocation.return_dbus_error.call_args.args[0].endswith(".InvalidRequest")
        invocation.return_value.assert_not_called()
        assert (tmp_path / "1001.json").read_bytes() == before
    assert accounts.events == []


def test_time_grant_preset_dbus_contract():
    methods = signatures(INTROSPECTION_XML)
    assert methods["GetOwnTimeGrantPresets"] == (("presets_json", "s", "out"),)
    assert methods["SetOwnTimeGrantPresets"] == (
        ("presets_json", "s", "in"), ("saved_presets_json", "s", "out"))
    assert methods["GetChildTimeGrantPresets"] == (
        ("target_uid", "u", "in"), ("presets_json", "s", "out"))
    assert methods["SetChildTimeGrantPresets"] == (
        ("target_uid", "u", "in"), ("presets_json", "s", "in"), ("saved_presets_json", "s", "out"))


def test_child_deadline_contract_has_explicit_clocks_and_no_selected_identity():
    assert signatures(INTROSPECTION_XML)["CalculateOwnDeadline"] == (
        ("native_deadline_realtime_usec", "t", "in"),
        ("timer_deadline_realtime_usec", "t", "in"),
        ("deadline_monotonic_usec", "t", "out"),
    )


@pytest.mark.parametrize("method,signature,values,operation,arguments", [
    ("GetOwnWhatsNew", "()", (), "get_own_whats_new", (1001,)),
    ("GetChildWhatsNew", "(u)", (1002,), "get_child_whats_new", (1001, 1002)),
    ("AcknowledgeOwnWhatsNew", "(s)", ("1.4",), "acknowledge_own_whats_new", (1001, "1.4")),
    ("AcknowledgeChildWhatsNew", "(us)", (1002, "1.4"), "acknowledge_child_whats_new", (1001, 1002, "1.4")),
])
def test_whats_new_dispatch_binds_authenticated_caller(method, signature, values, operation, arguments):
    from oh_no_parent_control.service import GLib
    service = Service.__new__(Service)
    service.credentials = mock.Mock()
    service.credentials.uid.return_value = 1001
    service.broker = mock.Mock()
    result = {"product_version": "1.4", "records": [{"ProductVersion": "1.4",
              "Content": "# New\n\n**Markdown**", "auto_show": True}]}
    getattr(service.broker, operation).return_value = result
    invocation = mock.Mock()
    service._method_call(None, ":1.42", None, None, method, GLib.Variant(signature, values), invocation)
    getattr(service.broker, operation).assert_called_once_with(*arguments)
    assert json.loads(invocation.return_value.call_args.args[0].unpack()[0]) == result
    invocation.return_dbus_error.assert_not_called()


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
        dependencies = runtime.production_dependencies(mock.Mock())
    from oh_no_parent_control.core import local_now
    assert dependencies.now is local_now
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
    from oh_no_parent_control.service import GLib, BUS_NAME, CONFIG_PATH
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
    service.broker.diagnostic_user_languages.return_value = {"status": "complete", "users": []}
    for revoke in (False, True):
        service.broker.authorize_diagnostic_export.side_effect = (
            [None, AccessDenied('denied')] if revoke else None)
        invocation = mock.Mock()
        with (mock.patch('oh_no_parent_control.service.threading.Thread') as thread,
              mock.patch('oh_no_parent_control.service.collect_kiosk_admission_diagnostics') as admission_probe,
              mock.patch('oh_no_parent_control.service.collect_kiosk_diagnostics') as kiosk_probe,
              mock.patch('oh_no_parent_control.service.collect_dependency_diagnostics') as dependencies_probe,
              mock.patch('oh_no_parent_control.service.GLib.idle_add') as idle):
            service._method_call(None, ':1.42', None, None, 'ExportDiagnosticLogs',
                                 None, invocation)
            thread.assert_called_once()
            service._export_logs_worker(invocation, 1000)
            admission_probe.assert_called_once_with()
            kiosk_probe.assert_called_once_with(CONFIG_PATH)
            dependencies_probe.assert_called_once_with()
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


def test_login_recovery_dispatch_uses_bus_identity_and_worker_errors():
    from oh_no_parent_control.service import GLib
    service = Service.__new__(Service)
    service.credentials = mock.Mock()
    service.credentials.uid.return_value = 0
    service.broker = mock.Mock()
    service.broker.recover_child_extension.return_value = True
    service._extension_monitor = mock.Mock()
    invocation = mock.Mock()

    def recover(_caller, target, *, on_recovered):
        if service.broker.recover_child_extension.return_value:
            on_recovered(target)
        return service.broker.recover_child_extension.return_value

    service.broker.recover_child_extension.side_effect = recover

    def thread(*, target, args, daemon):
        return mock.Mock(start=lambda: target(*args))

    with (mock.patch("oh_no_parent_control.service.threading.Thread", side_effect=thread),
          mock.patch("oh_no_parent_control.service.GLib.idle_add",
                     side_effect=lambda callback, *args: callback(*args))):
        service._method_call(None, ":1.42", None, None, "RecoverChildExtension",
                             GLib.Variant("(u)", (1001,)), invocation)
        service.broker.recover_child_extension.assert_called_once_with(
            0, 1001, on_recovered=service._extension_monitor.recovered)
        service._extension_monitor.recovered.assert_called_once_with(1001)
        assert invocation.return_value.call_args.args[0].unpack() == (True,)
        service._extension_monitor.reset_mock()
        service.broker.recover_child_extension.return_value = False
        service._method_call(None, ":1.42", None, None, "RecoverChildExtension",
                             GLib.Variant("(u)", (1001,)), invocation)
        assert invocation.return_value.call_args.args[0].unpack() == (False,)
        service._extension_monitor.recovered.assert_not_called()
        service.broker.recover_child_extension.side_effect = AccessDenied("root required")
        service._method_call(None, ":1.42", None, None, "RecoverChildExtension",
                             GLib.Variant("(u)", (1001,)), invocation)
        assert invocation.return_dbus_error.call_args.args[0].endswith("AccessDenied")
        service._extension_monitor.recovered.assert_not_called()


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
    def test_running_soft_app_list_dispatch_uses_authenticated_caller(self):
        service = Service.__new__(Service)
        service.credentials = mock.Mock()
        service.credentials.uid.return_value = 1003
        service.broker = mock.Mock()
        service.broker.list_running_soft_blocked_apps.return_value = ("soft.desktop",)
        from oh_no_parent_control.service import GLib
        invocation = mock.Mock()
        service._method_call(None, ':1.42', None, None, 'ListRunningSoftBlockedApps',
                             GLib.Variant('(u)', (1001,)), invocation)
        service.broker.list_running_soft_blocked_apps.assert_called_once_with(1003, 1001)
        self.assertEqual(invocation.return_value.call_args.args[0].unpack(), (["soft.desktop"],))

    def test_running_soft_apps_dispatch_uses_authenticated_caller(self):
        service = Service.__new__(Service)
        service.credentials = mock.Mock()
        service.credentials.uid.return_value = 1003
        service.broker = mock.Mock()
        service.broker.has_running_soft_blocked_apps.return_value = True
        from oh_no_parent_control.service import GLib
        invocation = mock.Mock()
        service._method_call(None, ':1.42', None, None, 'HasRunningSoftBlockedApps',
                             GLib.Variant('(u)', (1001,)), invocation)
        service.broker.has_running_soft_blocked_apps.assert_called_once_with(1003, 1001)
        self.assertEqual(invocation.return_value.call_args.args[0].unpack(), (True,))

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
        with (mock.patch("oh_no_parent_control.service.GLib.idle_add") as reply,
              mock.patch("oh_no_parent_control.service.collect_kiosk_admission_diagnostics",
                         side_effect=lambda: order.append("admission")),
              mock.patch("oh_no_parent_control.service.collect_kiosk_diagnostics",
                         side_effect=lambda _path: order.append("kiosk")),
              mock.patch("oh_no_parent_control.service.collect_dependency_diagnostics",
                         side_effect=lambda: order.append("dependencies"))):
            service._export_logs_worker(None, 0)
        self.assertEqual(order, ["admission", "kiosk", "dependencies", "observe", "snapshot"])
        self.assertEqual(reply.call_args.args[3], b"report")
        service.broker.collect_extension_diagnostics.side_effect = RuntimeError("private@example.test")
        with (mock.patch("oh_no_parent_control.service.GLib.idle_add") as reply,
              mock.patch("oh_no_parent_control.service.collect_kiosk_admission_diagnostics",
                         side_effect=RuntimeError("private@example.test")),
              mock.patch("oh_no_parent_control.service.collect_kiosk_diagnostics",
                         side_effect=RuntimeError("private@example.test")),
              mock.patch("oh_no_parent_control.service.collect_dependency_diagnostics",
                         side_effect=RuntimeError("private@example.test")),
              self.assertLogs("onpc", "WARNING") as logs):
            service._export_logs_worker(None, 0)
        self.assertEqual(reply.call_args.args[3], b"report")
        self.assertNotIn("private", "\n".join(logs.output))
        self.assertIn("kiosk admission collection outcome=unavailable", "\n".join(logs.output))

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
